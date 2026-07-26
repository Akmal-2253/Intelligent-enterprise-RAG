import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database import crud
from app.models.schemas import ChatHistoryItem

router = APIRouter(tags=["History"])


@router.get("/history", response_model=list[ChatHistoryItem])
def get_history(
    user_id: uuid.UUID = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    messages = crud.get_chat_history(db, user_id=user_id, limit=limit)
    return messages