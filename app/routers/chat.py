from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database import crud
from app.services.rag_service import answer_question
from app.models.schemas import ChatRequest, ChatResponse
from app.config import get_settings

router = APIRouter(tags=["Chat"])
settings = get_settings()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    user = crud.get_user(db, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Pull the last few turns for THIS user so the model can resolve
    # follow-up questions ("what about half-days?"). get_chat_history
    # returns newest-first, so reverse it to feed the model oldest-first,
    # matching how a real conversation actually reads.
    recent_messages = crud.get_chat_history(
        db, user_id=user.id, limit=settings.conversation_history_turns
    )
    history = [
        {"question": m.question, "answer": m.answer}
        for m in reversed(recent_messages)
    ]

    answer, sources = answer_question(
        request.question, history=history, document_id=request.document_id
    )

    saved = crud.save_chat_message(
        db,
        user_id=user.id,
        question=request.question,
        answer=answer,
        source_chunks=[s.model_dump() for s in sources],
    )

    return ChatResponse(answer=answer, sources=sources, chat_message_id=saved.id)