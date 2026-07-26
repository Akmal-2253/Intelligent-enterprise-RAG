"""
Groq does not currently expose an embeddings endpoint, so embeddings are
handled by a separate provider. Two options are supported and selected
via EMBEDDING_PROVIDER in .env:

  - "gemini":    Google's text-embedding-004 (cloud, no local compute, needs API key)
  - "fastembed": local ONNX model (fully offline, no API key, lightweight --
                 no PyTorch, unlike sentence-transformers)

Swapping providers never touches any other file -- everything else just
calls get_embedding_function().
"""

from functools import lru_cache

from app.config import get_settings

settings = get_settings()


@lru_cache
def get_embedding_function():
    if settings.embedding_provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=settings.google_api_key,
        )

    if settings.embedding_provider == "fastembed":
        from langchain_community.embeddings import FastEmbedEmbeddings

        # bge-small-en-v1.5: ~130MB ONNX model, good quality/speed tradeoff
        # for CPU-only local embedding. Downloads once, caches to disk after.
        return FastEmbedEmbeddings(model_name=settings.fastembed_model)

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}")