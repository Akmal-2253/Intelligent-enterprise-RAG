"""
Wraps the LLM used for answer generation. Only Groq is wired up for V1,
matching the tech stack, but it's isolated behind get_llm() the same way
embeddings are -- so adding Gemini as an LLM option later is a one-line change.
"""

from functools import lru_cache

from app.config import get_settings

settings = get_settings()


@lru_cache
def get_llm():
    if settings.llm_provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            groq_api_key=settings.groq_api_key,
            temperature=0.2,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")