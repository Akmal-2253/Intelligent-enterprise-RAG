import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Voice ----------

class TranscriptionResponse(BaseModel):
    text: str


class TextToSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


# ---------- Users ----------

class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------- Documents ----------

class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    num_chunks: int

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    num_chunks: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ---------- Chat ----------

class ChatRequest(BaseModel):
    user_id: uuid.UUID
    question: str = Field(..., min_length=1, max_length=2000)
    document_id: Optional[str] = None  # scope the answer to one document; None = search all


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    chunk_preview: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    chat_message_id: uuid.UUID


# ---------- History ----------

class ChatHistoryItem(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Feedback ----------

class FeedbackCreate(BaseModel):
    chat_message_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None