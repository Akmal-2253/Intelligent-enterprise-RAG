import os
import uuid

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import crud
from app.services.chunking_service import load_and_chunk_pdf
from app.services import vector_store_service
from app.utils.logger import logger

settings = get_settings()


def save_upload_to_disk(file_bytes: bytes, original_filename: str) -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{original_filename}"
    path = os.path.join(settings.upload_dir, safe_name)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def ingest_document(db: Session, owner_id: uuid.UUID, file_bytes: bytes, original_filename: str):
    """
    Full V1 ingestion pipeline:
    save file -> DB row (status=processing) -> chunk -> embed & store in
    FAISS -> mark DB row ready (or failed).
    """
    storage_path = save_upload_to_disk(file_bytes, original_filename)

    doc_row = crud.create_document(
        db,
        owner_id=owner_id,
        filename=original_filename,
        storage_path=storage_path,
    )

    try:
        chunks = load_and_chunk_pdf(storage_path)
        num_chunks = vector_store_service.add_chunks(
            document_id=str(doc_row.id), filename=original_filename, chunks=chunks
        )
        crud.mark_document_ready(db, doc_row.id, num_chunks)
        doc_row.status = "ready"
        doc_row.num_chunks = num_chunks
        logger.info(f"Ingested '{original_filename}' -> {num_chunks} chunks (doc_id={doc_row.id})")
        return doc_row

    except Exception:
        logger.exception(f"Failed to ingest '{original_filename}'")
        crud.mark_document_failed(db, doc_row.id)
        doc_row.status = "failed"
        raise


def remove_document(db: Session, document_id: uuid.UUID) -> bool:
    doc_row = crud.get_document(db, document_id)
    if not doc_row:
        return False

    vector_store_service.delete_by_document_id(str(document_id))

    if os.path.exists(doc_row.storage_path):
        os.remove(doc_row.storage_path)

    crud.delete_document(db, document_id)
    logger.info(f"Deleted document {document_id} ({doc_row.filename})")
    return True