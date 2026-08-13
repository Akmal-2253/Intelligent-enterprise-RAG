from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings
from app.database.connection import engine, Base
from app.routers import upload, chat, history, documents, users, voice
from app.utils.logger import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist yet.
    # V1 uses create_all() directly. From V2 onward this should be
    # replaced by running `alembic upgrade head` as a deploy step instead
    # -- create_all() can't handle schema changes to existing tables.
    Base.metadata.create_all(bind=engine)
    logger.info(f"{settings.app_name} started in '{settings.environment}' mode.")
    yield
    # Shutdown: nothing to clean up in V1 (no background workers, no
    # open connections beyond what SQLAlchemy's pool already manages).
    logger.info(f"{settings.app_name} shutting down.")


app = FastAPI(
    title="Internal Document Q&A (RAG System) - V1",
    description="Ask questions about company PDFs (policies, manuals, SOPs, contracts).",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allows a separate frontend (running on a different port/origin) to
# call this API from the browser. Locked down to explicit origins rather
# than "*" so it's not wide open even in dev.
# Replace this line in app/main.py:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://rag-enterprise.duckdns.org",
        "https://rag-enterprise.duckdns.org",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches anything not already turned into an HTTPException so the
    client always gets clean JSON, never a raw traceback. The real
    traceback still goes to the server logs for debugging.
    """
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "environment": settings.environment}


app.include_router(users.router)
app.include_router(voice.router)
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(documents.router)