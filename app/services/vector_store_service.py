"""
Wraps FAISS so the rest of the app never touches it directly.

Key differences from Chroma, worth understanding:
  1. No auto-persistence. Chroma writes to disk as you go; FAISS lives
     in memory until you explicitly call save_local(). We save after
     every write so nothing is lost on a crash/restart.
  2. No native metadata filtering. Chroma's `.delete(where={...})` has
     no FAISS equivalent -- delete_by_document_id() below has to scan
     the docstore itself to find matching chunk ids. (The FAISS wrapper
     DOES support a `filter` argument in similarity_search() itself,
     used below for document-scoped chat.)
  3. Needs at least one vector to be initialized. An empty FAISS index
     can't be created directly, so get_vector_store() bootstraps with
     a throwaway document and immediately deletes it.
"""

import os
import re

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.services.embedding_service import get_embedding_function
from app.utils.logger import logger

settings = get_settings()

_store: FAISS | None = None  # module-level cache -- one index per process

# --- BM25 keyword index (separate from FAISS, rebuilt from the same chunks) ---
_bm25_index: BM25Okapi | None = None
_bm25_doc_ids: list[str] = []  # parallel array: _bm25_doc_ids[i] matches row i of the BM25 index


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def get_vector_store() -> FAISS:
    global _store
    if _store is not None:
        return _store

    index_file = os.path.join(settings.faiss_index_dir, "index.faiss")

    if os.path.exists(index_file):
        _store = FAISS.load_local(
            settings.faiss_index_dir,
            get_embedding_function(),
            allow_dangerous_deserialization=True,
        )
        logger.info(f"Loaded FAISS index from {settings.faiss_index_dir}")
    else:
        _store = FAISS.from_texts(["__init__"], embedding=get_embedding_function())
        bootstrap_id = list(_store.docstore._dict.keys())[0]
        _store.delete([bootstrap_id])
        os.makedirs(settings.faiss_index_dir, exist_ok=True)
        _store.save_local(settings.faiss_index_dir)
        logger.info(f"Created new FAISS index at {settings.faiss_index_dir}")

    return _store


def add_chunks(document_id: str, filename: str, chunks: list[LCDocument]) -> int:
    store = get_vector_store()

    for i, chunk in enumerate(chunks):
        chunk.metadata["document_id"] = document_id
        chunk.metadata["filename"] = filename
        # chunk_index preserves original document order -- PyPDFLoader already
        # sets metadata["page"] per chunk, but chunk_index lets us sort/limit
        # reliably even for chunks that share the same page.
        chunk.metadata["chunk_index"] = i

    ids = [f"{document_id}_{i}" for i in range(len(chunks))]
    store.add_documents(documents=chunks, ids=ids)
    store.save_local(settings.faiss_index_dir)

    global _bm25_index
    _bm25_index = None  # invalidate -- rebuilt lazily on next hybrid_search call

    return len(chunks)


def similarity_search(query: str, k: int, document_id: str | None = None) -> list[LCDocument]:
    """
    Normal semantic search. If document_id is given, results are scoped to
    just that document -- needed so "summarize this file" or "the intro"
    isn't ambiguous when multiple documents are uploaded.
    """
    store = get_vector_store()
    if document_id:
        return store.similarity_search(query, k=k, filter={"document_id": document_id})
    return store.similarity_search(query, k=k)


def _get_bm25_index() -> tuple[BM25Okapi | None, list[str]]:
    """
    Rebuilds the BM25 keyword index from the current FAISS docstore
    contents. Cheap enough to rebuild lazily (tokenizing a few thousand
    chunks takes well under a second) rather than maintaining two indexes
    in sync on every write -- simpler and less error-prone for this scale.
    """
    global _bm25_index, _bm25_doc_ids
    if _bm25_index is not None:
        return _bm25_index, _bm25_doc_ids

    store = get_vector_store()
    doc_ids = list(store.docstore._dict.keys())
    if not doc_ids:
        return None, []

    corpus = [store.docstore._dict[doc_id].page_content for doc_id in doc_ids]
    tokenized_corpus = [_tokenize(text) for text in corpus]

    _bm25_index = BM25Okapi(tokenized_corpus)
    _bm25_doc_ids = doc_ids
    logger.info(f"Built BM25 index over {len(doc_ids)} chunks")
    return _bm25_index, _bm25_doc_ids


def _bm25_search(query: str, k: int, document_id: str | None = None) -> list[str]:
    """Returns chunk ids ranked by BM25 keyword score, best first."""
    bm25, doc_ids = _get_bm25_index()
    if bm25 is None:
        return []

    scores = bm25.get_scores(_tokenize(query))
    store = get_vector_store()

    ranked = sorted(range(len(doc_ids)), key=lambda i: scores[i], reverse=True)

    if document_id:
        ranked = [
            i for i in ranked
            if store.docstore._dict[doc_ids[i]].metadata.get("document_id") == document_id
        ]

    return [doc_ids[i] for i in ranked[: k * 2]]  # a bit of headroom before fusion


def hybrid_search(
    query: str, k: int, document_id: str | None = None, rrf_k: int = 60
) -> list[LCDocument]:
    """
    Combines FAISS semantic search with BM25 keyword search using
    Reciprocal Rank Fusion (RRF). Instead of comparing raw scores (cosine
    similarity and BM25 scores live on incomparable scales), RRF combines
    each result's RANK in each list:

        fused_score = 1/(rrf_k + rank_in_semantic) + 1/(rrf_k + rank_in_bm25)

    A chunk that ranks well in EITHER list gets pulled toward the top --
    this is what lets an exact term like "STP" surface a chunk even if its
    embedding similarity alone wasn't quite the closest match.
    """
    store = get_vector_store()

    semantic_kwargs = {"filter": {"document_id": document_id}} if document_id else {}
    semantic_results = store.similarity_search(query, k=k * 2, **semantic_kwargs)
    semantic_ids = [
        f"{d.metadata.get('document_id')}_{d.metadata.get('chunk_index', 0)}"
        for d in semantic_results
    ]

    bm25_ids = _bm25_search(query, k=k, document_id=document_id)

    fused_scores: dict[str, float] = {}
    for rank, chunk_id in enumerate(semantic_ids):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0) + 1 / (rrf_k + rank + 1)
    for rank, chunk_id in enumerate(bm25_ids):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0) + 1 / (rrf_k + rank + 1)

    top_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)[:k]
    return [store.docstore._dict[chunk_id] for chunk_id in top_ids if chunk_id in store.docstore._dict]


def get_opening_chunks(document_id: str, max_page: int = 1, max_chunks: int = 6) -> list[LCDocument]:
    """
    Bypasses semantic search entirely and returns the document's own
    opening chunks (page 0 and 1, i.e. PyPDFLoader's 0-indexed first two
    pages), ordered as they appear in the source file.

    Used for structural queries like "give me the introduction" or
    "summarize this document" -- these don't have a good semantic match
    against any single chunk (the word "introduction" doesn't closely
    resemble what's actually *written* in an introduction), so similarity
    search on the raw question tends to retrieve the wrong section
    entirely. Going straight to "what's actually at the start of the
    file" is both simpler and more reliable for this specific case.
    """
    store = get_vector_store()
    matches = [
        doc
        for doc in store.docstore._dict.values()
        if doc.metadata.get("document_id") == document_id
        and doc.metadata.get("page", 99) <= max_page
    ]
    matches.sort(key=lambda d: d.metadata.get("chunk_index", 0))
    return matches[:max_chunks]


def delete_by_document_id(document_id: str) -> None:
    store = get_vector_store()

    matching_ids = [
        chunk_id
        for chunk_id, doc in store.docstore._dict.items()
        if doc.metadata.get("document_id") == document_id
    ]

    if matching_ids:
        store.delete(matching_ids)
        store.save_local(settings.faiss_index_dir)
        global _bm25_index
        _bm25_index = None  # invalidate -- rebuilt lazily on next hybrid_search call
        logger.info(f"Deleted {len(matching_ids)} chunks for document {document_id}")