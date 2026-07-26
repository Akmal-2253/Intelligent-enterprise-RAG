import uuid

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database import crud
from app.services.document_service import ingest_document
from app.models.schemas import DocumentUploadResponse
from app.config import get_settings

router = APIRouter(tags=["Documents"])
settings = get_settings()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_email: str = Form(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported in V1.")

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds max size of {settings.max_upload_size_mb} MB.",
        )

    user = crud.get_or_create_user(db, email=user_email)

    try:
        doc = ingest_document(db, owner_id=user.id, file_bytes=file_bytes, original_filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {e}")

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        num_chunks=doc.num_chunks,
    )


@router.get("/documents", response_model=list[DocumentUploadResponse])
def list_all_documents(db: Session = Depends(get_db)):
    docs = crud.list_documents(db)
    return [
        DocumentUploadResponse(document_id=d.id, filename=d.filename, status=d.status, num_chunks=d.num_chunks)
        for d in docs
    ]