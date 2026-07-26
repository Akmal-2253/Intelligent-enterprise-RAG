"""
Thin data-access layer. Routers/services should call these functions
instead of writing raw SQLAlchemy queries inline -- keeps DB logic in
one place and makes it easy to unit test later.
"""

import json
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.db_models import User, Document, ChatMessage, Feedback


# ---------- Users ----------

def get_or_create_user(db: Session, email: str, full_name: str | None = None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(email=email, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


# ---------- Documents ----------

def create_document(
    db: Session, owner_id: uuid.UUID, filename: str, storage_path: str
) -> Document:
    doc = Document(
        owner_id=owner_id,
        filename=filename,
        storage_path=storage_path,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def mark_document_ready(db: Session, document_id: uuid.UUID, num_chunks: int) -> None:
    db.query(Document).filter(Document.id == document_id).update(
        {"status": "ready", "num_chunks": num_chunks}
    )
    db.commit()


def mark_document_failed(db: Session, document_id: uuid.UUID) -> None:
    db.query(Document).filter(Document.id == document_id).update({"status": "failed"})
    db.commit()


def get_document(db: Session, document_id: uuid.UUID) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def list_documents(db: Session, owner_id: uuid.UUID | None = None) -> list[Document]:
    q = db.query(Document)
    if owner_id:
        q = q.filter(Document.owner_id == owner_id)
    return q.order_by(Document.uploaded_at.desc()).all()


def delete_document(db: Session, document_id: uuid.UUID) -> None:
    db.query(Document).filter(Document.id == document_id).delete()
    db.commit()


# ---------- Chat history ----------

def save_chat_message(
    db: Session,
    user_id: uuid.UUID,
    question: str,
    answer: str,
    source_chunks: list[dict],
) -> ChatMessage:
    msg = ChatMessage(
        user_id=user_id,
        question=question,
        answer=answer,
        source_chunks=json.dumps(source_chunks),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_chat_history(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )


# ---------- Feedback ----------

def save_feedback(
    db: Session, chat_message_id: uuid.UUID, rating: int, comment: str | None = None
) -> Feedback:
    """
    Saves new feedback or updates existing feedback for a given chat_message_id 
    to handle duplicate key constraint violations gracefully.
    """
    stmt = insert(Feedback).values(
        chat_message_id=chat_message_id,
        rating=rating,
        comment=comment,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["chat_message_id"],
        set_={
            "rating": stmt.excluded.rating,
            "comment": stmt.excluded.comment,
        },
    )
    db.execute(stmt)
    db.commit()
    
    return (
        db.query(Feedback)
        .filter(Feedback.chat_message_id == chat_message_id)
        .first()
    )