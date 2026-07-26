from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database import crud
from app.models.schemas import UserLoginRequest, UserOut

router = APIRouter(tags=["Users"])


@router.post("/users", response_model=UserOut)
def get_or_create_user(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Resolves an email to a user_id, creating the user if they don't exist
    yet. This lets a frontend (Streamlit, etc.) get a user_id up front,
    rather than only ever getting one as a side effect of /upload.
    """
    user = crud.get_or_create_user(db, email=payload.email, full_name=payload.full_name)
    return user