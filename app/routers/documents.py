import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database import crud
from app.services.document_service import remove_document
from app.models.schemas import FeedbackCreate

router = APIRouter(tags=["Documents"])


@router.delete("/document/{document_id}")
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    deleted = remove_document(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "deleted", "document_id": str(document_id)}


@router.post("/feedback")
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    fb = crud.save_feedback(
        db,
        chat_message_id=payload.chat_message_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    return {"status": "recorded", "feedback_id": str(fb.id)}