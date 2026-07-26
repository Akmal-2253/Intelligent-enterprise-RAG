from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LCDocument

from app.config import get_settings

settings = get_settings()


def load_and_chunk_pdf(file_path: str) -> list[LCDocument]:
    """
    Loads a PDF (page by page) and splits it into overlapping chunks.
    Returns a list of LangChain Document objects, each with:
      - page_content: the chunk text
      - metadata: {source, page, ...}
    """
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)
    return chunks