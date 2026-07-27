"""
Streamlit frontend for the RAG system.
Runs standalone on Streamlit Community Cloud by importing directly from 
the database, crud, and service layers — no external FastAPI server needed.
"""

import os
import io
import streamlit as st

# Database & CRUD imports
from app.database.connection import engine, Base, SessionLocal
from app.database import crud
from app.config import get_settings

# Attempt to import routers/services safely
from app.routers import voice, upload, chat, history, documents

# Ensure tables are created on launch
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    st.warning(f"Database setup note: {e}")

settings = get_settings()

st.set_page_config(
    page_title="Enterprise Document Q&A",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []


def initials(email: str) -> str:
    name_part = email.split("@")[0]
    parts = [p for p in name_part.replace(".", " ").replace("_", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name_part[:2].upper()


STATUS_COLORS = {"ready": "#16a34a", "processing": "#d97706", "failed": "#dc2626"}

# ---------------------------------------------------------------------
# Design system -- overrides Streamlit's default look with a flat,
# neutral, enterprise-style theme instead of the default rounded/playful
# chat UI.
# ---------------------------------------------------------------------
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        :root {
            --bg: #0b1220;
            --surface: #131c2e;
            --surface-2: #1a2540;
            --border: #263252;
            --text: #e5e9f2;
            --text-muted: #8a94ab;
            --accent: #3b82f6;
            --accent-soft: #1e3a6d;
        }

        .stApp { background-color: var(--bg); }

        /* Header */
        .app-header {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 20px 24px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .app-header .icon {
            width: 44px; height: 44px;
            background: var(--accent-soft);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px; flex-shrink: 0;
        }
        .app-header h1 {
            font-size: 20px; font-weight: 600; color: var(--text);
            margin: 0; line-height: 1.3;
        }
        .app-header p {
            font-size: 13px; color: var(--text-muted); margin: 2px 0 0 0;
        }

        /* Chat bubbles */
        .msg-row { display: flex; margin-bottom: 14px; }
        .msg-row.user { justify-content: flex-end; }
        .msg-row.assistant { justify-content: flex-start; }
        .bubble {
            max-width: 72%;
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 14.5px;
            line-height: 1.55;
        }
        .bubble.user {
            background: var(--accent);
            color: white;
            border-bottom-right-radius: 3px;
        }
        .bubble.assistant {
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text);
            border-bottom-left-radius: 3px;
        }
        .msg-label {
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 4px;
            font-weight: 500;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }

        /* Status badge */
        .badge {
            display: inline-block;
            padding: 2px 9px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            color: white;
            text-transform: capitalize;
        }

        /* Section label */
        .section-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 8px;
        }

        div[data-testid="stChatInput"] { background: var(--surface); }

        section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="section-label">Account</div>', unsafe_allow_html=True)

    if st.session_state.user_id:
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(
                f"""<div style="width:36px;height:36px;border-radius:50%;background:#3b82f6;
                color:white;display:flex;align-items:center;justify-content:center;
                font-weight:600;font-size:13px;">{initials(st.session_state.user_email)}</div>""",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(f"**{st.session_state.user_email}**")
            st.caption("Signed in")

        with st.expander("Session details"):
            st.code(st.session_state.user_id, language=None)

        if st.button("Sign out", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.user_email = None
            st.session_state.chat_log = []
            st.rerun()
    else:
        email = st.text_input("Email", placeholder="you@company.com", label_visibility="collapsed")
        if st.button("Continue", type="primary", use_container_width=True, disabled=not email):
            db = SessionLocal()
            try:
                # Direct call to crud layer
                user_obj = crud.get_or_create_user(db, email=email)
                st.session_state.user_id = str(user_obj.id)
                st.session_state.user_email = user_obj.email
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
            finally:
                db.close()

    st.divider()
    if st.button("Check system status", use_container_width=True):
        st.success(f"System is ready · {settings.environment}")

# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <div class="icon">📄</div>
        <div>
            <h1>Enterprise Document Q&A</h1>
            <p>Ask questions about uploaded company documents — policies, manuals, SOPs, and contracts.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.user_id:
    st.info("Enter your email in the sidebar to get started.")
    st.stop()

tab_chat, tab_upload, tab_docs, tab_history = st.tabs(["Chat", "Upload", "Documents", "History"])

# ---------------------- Chat tab ----------------------
with tab_chat:
    docs_for_picker = []
    if hasattr(documents, "get_documents"):
        try:
            db = SessionLocal()
            docs_for_picker = documents.get_documents(db=db) if "db" in documents.get_documents.__code__.co_varnames else documents.get_documents()
        except Exception:
            pass
        finally:
            if 'db' in locals(): db.close()

    doc_options = {"All documents": None}
    for d in docs_for_picker:
        d_id = getattr(d, "document_id", d.get("document_id") if isinstance(d, dict) else None)
        d_name = getattr(d, "filename", d.get("filename") if isinstance(d, dict) else "Document")
        doc_options[d_name] = d_id

    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown('<div class="section-label">Scope</div>', unsafe_allow_html=True)
        selected_doc_label = st.selectbox(
            "Ask about", options=list(doc_options.keys()), label_visibility="collapsed"
        )
        selected_document_id = doc_options[selected_doc_label]
    with col_b:
        st.markdown('<div class="section-label">&nbsp;</div>', unsafe_allow_html=True)
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.chat_log = []
            st.rerun()

    st.write("")

    if not st.session_state.chat_log:
        st.markdown(
            """<div style="text-align:center; padding: 48px 0; color:#8a94ab;">
            <div style="font-size:32px;margin-bottom:8px;">💬</div>
            <div style="font-size:14px;">No messages yet — ask a question about your documents below.</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # Render conversation history
    for entry in st.session_state.chat_log:
        st.markdown(
            f"""<div class="msg-row user"><div class="bubble user">{entry['question']}</div></div>""",
            unsafe_allow_html=True,
        )
        
        if entry.get("audio_bytes"):
            st.audio(entry["audio_bytes"], format="audio/mp3", autoplay=entry.get("autoplay", False))
            entry["autoplay"] = False

        st.markdown(
            f"""<div class="msg-row assistant"><div class="bubble assistant">{entry['answer']}</div></div>""",
            unsafe_allow_html=True,
        )

        if entry.get("sources"):
            with st.expander(f"{len(entry['sources'])} source(s)"):
                for s in entry["sources"]:
                    st.markdown(f"**{s.get('filename', 'Source')}**")
                    st.caption(s.get("chunk_preview", ""))

        fcol1, fcol2, _ = st.columns([1, 1, 10])
        with fcol1:
            if st.button("👍", key=f"up_{entry['chat_message_id']}"):
                st.toast("Thanks for the feedback")
        with fcol2:
            if st.button("👎", key=f"down_{entry['chat_message_id']}"):
                st.toast("Thanks for the feedback")

    if "recorder_key_counter" not in st.session_state:
        st.session_state.recorder_key_counter = 0

    question_from_voice = None
    with st.container(border=True):
        st.markdown('<div class="section-label">Voice</div>', unsafe_allow_html=True)
        
        current_key = f"voice_input_{st.session_state.recorder_key_counter}"
        audio_value = st.audio_input("Record a question", key=current_key, label_visibility="collapsed")
        
        if audio_value is not None:
            if st.button("Transcribe & ask", type="primary"):
                with st.spinner("Transcribing..."):
                    if hasattr(voice, "transcribe_audio"):
                        transcribed = voice.transcribe_audio(audio_value.getvalue())
                        question_from_voice = getattr(transcribed, "text", transcribed.get("text", "")) if isinstance(transcribed, dict) else str(transcribed)
                st.caption(f'Heard: "{question_from_voice}"')
                st.session_state.recorder_key_counter += 1
        else:
            st.caption("Click the microphone button to record your question.")

    question = st.chat_input("Ask a question about your documents...") or question_from_voice
    
    if question:
        with st.spinner("Searching documents & generating response..."):
            db = SessionLocal()
            answer_text = ""
            sources_list = []
            msg_id = 0
            try:
                # Call chat function directly
                if hasattr(chat, "chat_endpoint"):
                    from app.models.schemas import ChatRequest
                    payload = ChatRequest(user_id=st.session_state.user_id, question=question, document_id=selected_document_id)
                    res = chat.chat_endpoint(payload=payload, db=db)
                    answer_text = getattr(res, "answer", res.get("answer", ""))
                    sources_list = getattr(res, "sources", res.get("sources", []))
                    msg_id = getattr(res, "chat_message_id", res.get("chat_message_id", 0))
            except Exception as e:
                answer_text = f"Error processing query: {e}"
            finally:
                db.close()

            generated_audio_bytes = None
            if bool(question_from_voice) and hasattr(voice, "synthesize_speech"):
                try:
                    generated_audio_bytes = voice.synthesize_speech(text=answer_text)
                except Exception:
                    st.warning("Failed to generate voice playback.")

        st.session_state.chat_log.append(
            {
                "question": question,
                "answer": answer_text,
                "sources": sources_list,
                "chat_message_id": msg_id,
                "audio_bytes": generated_audio_bytes,
                "autoplay": True,
            }
        )
        st.rerun()

# ---------------------- Upload tab ----------------------
with tab_upload:
    st.markdown('<div class="section-label">Upload a document</div>', unsafe_allow_html=True)
    with st.container(border=True):
        uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded_file:
            st.caption(f"{uploaded_file.name} · {uploaded_file.size / 1024:.0f} KB")
        if st.button("Upload and process", type="primary", disabled=not uploaded_file):
            with st.spinner("Chunking, embedding, and indexing..."):
                db = SessionLocal()
                try:
                    if hasattr(upload, "process_pdf_upload"):
                        res = upload.process_pdf_upload(file_name=uploaded_file.name, file_bytes=uploaded_file.getvalue(), user_email=st.session_state.user_email, db=db)
                        st.success("File processed successfully.")
                    else:
                        st.info("Upload module ready.")
                except Exception as e:
                    st.error(f"Upload error: {e}")
                finally:
                    db.close()

# ---------------------- Documents tab ----------------------
with tab_docs:
    col_a, col_b = st.columns([5, 1])
    with col_a:
        st.markdown('<div class="section-label">All uploaded documents</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("Refresh", use_container_width=True, key="refresh_docs"):
            st.rerun()

    docs = []
    db = SessionLocal()
    try:
        docs = crud.get_all_documents(db) if hasattr(crud, "get_all_documents") else []
    except Exception:
        pass
    finally:
        db.close()

    if not docs:
        st.info("No documents uploaded yet.")
    for doc in docs:
        doc_id = getattr(doc, "id", getattr(doc, "document_id", ""))
        fname = getattr(doc, "filename", "")
        status = getattr(doc, "status", "ready")
        chunks = getattr(doc, "num_chunks", 0)

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 1.5, 1.5, 1])
            with c1:
                st.markdown(f"**{fname}**")
            with c2:
                color = STATUS_COLORS.get(status, "#64748b")
                st.markdown(
                    f'<span class="badge" style="background:{color}">{status}</span>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.caption(f"{chunks} chunks")
            with c4:
                if st.button("Delete", key=f"del_{doc_id}", use_container_width=True):
                    db = SessionLocal()
                    try:
                        if hasattr(crud, "delete_document"):
                            crud.delete_document(db, doc_id)
                        st.toast(f"Deleted {fname}")
                    finally:
                        db.close()
                    st.rerun()

# ---------------------- History tab ----------------------
with tab_history:
    col_a, col_b = st.columns([5, 1])
    with col_a:
        st.markdown('<div class="section-label">Your chat history</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("Refresh", use_container_width=True, key="refresh_history"):
            st.rerun()

    hist_data = []
    db = SessionLocal()
    try:
        if hasattr(crud, "get_user_chat_history"):
            hist_data = crud.get_user_chat_history(db, user_id=st.session_state.user_id)
    except Exception:
        pass
    finally:
        db.close()

    if not hist_data:
        st.info("No questions asked yet.")
    for item in hist_data:
        created = getattr(item, "created_at", "")
        q_text = getattr(item, "question", "")
        a_text = getattr(item, "answer", "")

        with st.container(border=True):
            st.caption(str(created))
            st.markdown(f"**Q:** {q_text}")
            st.markdown(f"{a_text}")
