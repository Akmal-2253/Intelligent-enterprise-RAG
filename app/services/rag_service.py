import re

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_settings
from app.services.llm_service import get_llm
from app.services.vector_store_service import hybrid_search, get_opening_chunks
from app.models.schemas import SourceChunk
from app.utils.logger import logger

settings = get_settings()

SYSTEM_PROMPT = """You are an expert internal assistant that helps employees understand \
company documents -- policies, manuals, SOPs, and contracts. You are given document \
excerpts relevant to the user's question. Follow these rules:

1. Base your answer only on the facts, figures, and claims in the document excerpts \
below. Do not add outside knowledge, and never invent policy numbers, dates, names, \
or figures that aren't present in the context.
2. Do NOT copy sentences verbatim from the excerpts. Read them, understand the \
underlying facts, and explain the answer in your own words, like a knowledgeable \
colleague would -- clearly, naturally, and in a conversational tone. Only quote \
directly when the exact wording genuinely matters (e.g. a legal clause, a defined \
term, an exact figure) and even then keep it brief.
3. Where the excerpts support it, explain the "why" or "how" behind a fact, not just \
the fact itself -- connect ideas the way a person who actually understood the \
document would, rather than listing disconnected sentences.
4. If the context does not contain the answer, say clearly that the information isn't \
available in the uploaded documents -- do not guess, and do not pad the answer with \
generic knowledge to compensate.
5. Cite the source filename when it's useful for the user to know where something \
came from, but don't let citation mechanics get in the way of a natural explanation.
6. You may be shown earlier turns of this conversation. Use them ONLY to understand \
what a follow-up question like "what about half-days?" is referring to -- never treat \
anything said in the conversation itself as a fact unless it's also backed by the \
document excerpts below.
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "Conversation so far (for understanding follow-ups only, oldest first):\n"
            "{history}\n\n"
            "Document excerpts:\n{context}\n\n"
            "Current question: {question}",
        ),
    ]
)

# --- Small talk / capability questions ------------------------------------
# Greetings, "how are you", "what can you do" etc. are common in real usage
# but aren't document questions -- forcing them through retrieval usually
# produces an awkward "I couldn't find that in the documents" response.
# These are matched and answered directly, skipping retrieval AND the LLM
# call entirely: faster, and avoids spending an API call on "hi".
#
# Greetings/thanks/bye are anchored to the WHOLE message (^...$) so a real
# question like "hi, what's the leave policy?" still falls through to
# normal retrieval -- only a bare "hi" on its own is treated as small talk.
_SMALLTALK_RULES: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"^\s*(hi|hello|hey|hiya|yo|good (morning|afternoon|evening))[\s!.,]*$", re.IGNORECASE),
        "Hey there! 👋 I'm your internal document assistant — ask me anything "
        "about the company PDFs that have been uploaded (policies, manuals, "
        "SOPs, contracts) and I'll answer using only what's actually in them.",
    ),
    (
        re.compile(r"\b(how are (you|u)|how'?s it going|what'?s up|how r u|hows u)\b", re.IGNORECASE),
        "I'm doing well, thanks for asking! Ready whenever you are — what "
        "would you like to know from the uploaded documents?",
    ),
    (
        re.compile(
            r"\b(what can you (do|help( me)? with|provide)|what do you do|"
            r"who are you|what are you|how (do|can) (i|you) use (you|this)|"
            r"what is this (app|tool|assistant|system))\b",
            re.IGNORECASE,
        ),
        "I'm an AI assistant that answers questions using your company's "
        "uploaded documents -- things like policies, manuals, SOPs, and "
        "contracts. Upload a PDF and ask me anything about it; I'll only "
        "answer from what's actually written there, and I'll say so if the "
        "answer isn't in the documents rather than guessing. You can also "
        "ask follow-up questions -- I keep track of the last few turns of "
        "our conversation.",
    ),
    (
        re.compile(r"^\s*(thanks|thank you|thx|appreciate it)[\s!.,a-z]{0,25}$", re.IGNORECASE),
        "You're welcome! Let me know if there's anything else you'd like to "
        "check in the documents.",
    ),
    (
        re.compile(r"^\s*(bye|goodbye|see you|see ya|later)[\s!.,]*$", re.IGNORECASE),
        "Goodbye! Come back anytime you have a question about the documents.",
    ),
    (
        re.compile(r"\b(what are (you|u) (doing|up to)|what'?re (you|u) (doing|up to))\b", re.IGNORECASE),
        "Just sitting here ready to dig through your uploaded documents! "
        "Ask me something about a policy, manual, or contract and I'll "
        "find the answer for you.",
    ),
    (
        re.compile(r"^\s*(ok|okay|cool|nice|great|awesome|got it|alright|sounds good)[\s!.,]*$", re.IGNORECASE),
        "Great! Let me know whenever you have a question about the documents.",
    ),
    (
        re.compile(r"\b(who (made|built|created) you|who is your (creator|developer)|are you (an? )?ai|are you (a )?bot|are you human)\b", re.IGNORECASE),
        "I'm an AI assistant built to answer questions about your company's "
        "uploaded documents. I'm not human, but I'm pretty good at reading "
        "policies and manuals so you don't have to!",
    ),
    (
        re.compile(r"\b(can you (help|assist) me|i need help|help me( out)?)\b", re.IGNORECASE),
        "Of course! I can answer questions about any of the documents "
        "that have been uploaded -- just ask naturally, like you would ask "
        "a colleague. For example: \"What's the leave policy?\" or "
        "\"Summarize this document.\"",
    ),
    (
        re.compile(r"\b(you (there|around)|anyone (there|around)|hello\?+)\b", re.IGNORECASE),
        "Yep, I'm here! Go ahead and ask your question.",
    ),
    (
        re.compile(r"^\s*(test|testing|123|hello world)[\s!.,]*$", re.IGNORECASE),
        "Test received! I'm up and running. Ask me something about the "
        "documents whenever you're ready.",
    ),
    (
        re.compile(r"\b(i (don'?t|do not) know what to ask|what should i ask|any (suggestions|examples)|give me an example)\b", re.IGNORECASE),
        "Good question! Try things like: \"What's the refund policy?\", "
        "\"Summarize this document\", or \"What are the steps for "
        "onboarding?\" -- anything that could plausibly be answered by "
        "one of the uploaded documents.",
    ),
    (
        re.compile(r"\b(i love (you|this)|you'?re (great|awesome|amazing|the best)|good (job|bot))\b", re.IGNORECASE),
        "Thank you, that's kind! Happy to keep helping -- what would you "
        "like to know from the documents?",
    ),
]


def _smalltalk_reply(question: str) -> str | None:
    for pattern, reply in _SMALLTALK_RULES:
        if pattern.search(question):
            return reply
    return None


# --- Structural query detection -----------------------------------------
# Queries about document STRUCTURE (not content) need different handling
# than normal semantic search -- see get_opening_chunks() docstring for why.
_STRUCTURAL_PATTERNS = re.compile(
    r"\b(introduction|intro|summary|summarize|overview|abstract|"
    r"executive summary|what.?s? this (document|file|report|pdf) about|"
    r"tl;?dr)\b",
    re.IGNORECASE,
)


def is_structural_query(question: str) -> bool:
    return bool(_STRUCTURAL_PATTERNS.search(question))


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(this is the first question -- no prior conversation)"
    lines = []
    for turn in history:
        lines.append(f"User: {turn['question']}")
        lines.append(f"Assistant: {turn['answer']}")
    return "\n".join(lines)


def _build_retrieval_query(question: str, history: list[dict]) -> str:
    """
    Vector search has no idea what "what about half-days?" refers to on its
    own. Folding the previous user question into the search text gives
    retrieval the missing context for follow-ups.
    """
    if not history:
        return question
    last_question = history[-1]["question"]
    return f"{last_question} {question}"


def _hyde_expand_query(question: str) -> str:
    """
    HyDE (Hypothetical Document Embeddings): instead of embedding the raw
    question, ask the LLM to write a short PASSAGE that would plausibly
    answer it, and embed that instead. A hypothetical answer resembles the
    real document text far more closely than the question does, which
    often improves retrieval for vague/structural queries when we don't
    know which specific document to scope to (so get_opening_chunks isn't
    usable -- no single document_id to target).

    Only called for structural queries with no document_id, to avoid the
    extra LLM call (and latency) on every normal question.
    """
    llm = get_llm()
    prompt = (
        "Write a short, plausible paragraph (3-4 sentences) that could be "
        f"the opening/introduction of a company document, in response to: "
        f'"{question}". Do not mention you are guessing -- just write the '
        "hypothetical passage itself, nothing else."
    )
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception:
        logger.exception("HyDE expansion failed, falling back to raw question")
        return question


def _to_source_chunks(retrieved) -> list[SourceChunk]:
    return [
        SourceChunk(
            document_id=str(c.metadata.get("document_id", "")),
            filename=c.metadata.get("filename", "unknown"),
            chunk_preview=c.page_content[:200],
        )
        for c in retrieved
    ]


def answer_question(
    question: str,
    history: list[dict] | None = None,
    document_id: str | None = None,
) -> tuple[str, list[SourceChunk]]:
    """
    Retrieves relevant chunks and generates a grounded answer.

    Three retrieval paths:
      1. Structural query + known document_id -> pull the document's own
         opening chunks directly (no semantic search at all).
      2. Structural query + no document_id -> HyDE-expand the query before
         embedding, since raw questions like "give me the intro" match
         poorly against real document text.
      3. Everything else -> normal semantic search (optionally scoped to
         document_id), with the previous turn folded in for follow-ups.
    """
    history = history or []

    smalltalk = _smalltalk_reply(question)
    if smalltalk:
        return smalltalk, []

    if is_structural_query(question) and document_id:
        retrieved = get_opening_chunks(document_id)
        if not retrieved:
            return (
                "I couldn't find an introduction/summary section for that document.",
                [],
            )
    else:
        if is_structural_query(question):
            search_text = _hyde_expand_query(question)
        else:
            search_text = _build_retrieval_query(question, history)

        retrieved = hybrid_search(search_text, k=settings.retrieval_top_k, document_id=document_id)

    if not retrieved:
        return (
            "I couldn't find anything relevant to that in the uploaded documents.",
            [],
        )

    context_text = "\n\n---\n\n".join(
        f"[Source: {c.metadata.get('filename', 'unknown')}]\n{c.page_content}" for c in retrieved
    )

    llm = get_llm()
    chain = PROMPT | llm
    response = chain.invoke(
        {
            "history": _format_history(history),
            "context": context_text,
            "question": question,
        }
    )

    return response.content, _to_source_chunks(retrieved)