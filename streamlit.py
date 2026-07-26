"""
Streamlit frontend for the RAG system. This is a SEPARATE process from
the FastAPI backend -- it talks to it purely over HTTP, exactly like
Swagger's "Try it out" does. It never imports from `app/` or touches
the database/FAISS directly.

Run the backend first:  uvicorn app.main:app --reload
Then run this:          streamlit run streamlit_app.py
"""

import os
import requests
import streamlit as st


# Config

# Reads API_URL from the environment if set (e.g. "http://backend:8000"
# inside Docker, where containers reach each other by service name, not
# localhost) -- falls back to localhost for running this standalone.
DEFAULT_API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Enterprise Document Q&A",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "api_url" not in st.session_state:
    st.session_state.api_url = DEFAULT_API_URL
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []


def api(method: str, path: str, **kwargs):
    url = f"{st.session_state.api_url}{path}"
    try:
        resp = requests.request(method, url, timeout=60, **kwargs)
    except requests.exceptions.ConnectionError:
        st.error(
            f"Can't reach the backend at {st.session_state.api_url}. "
            "Is `uvicorn app.main:app --reload` running?"
        )
        st.stop()
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        st.error(f"API error ({resp.status_code}): {detail}")
        st.stop()
    return resp.json()


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
# chat UI. Deliberately avoids gradients, emoji-heavy copy, and the
# default chat-bubble avatars.
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
    st.markdown('<div class="section-label">Connection</div>', unsafe_allow_html=True)
    st.session_state.api_url = st.text_input(
        "Backend URL", value=st.session_state.api_url, label_visibility="collapsed"
    )

    st.divider()
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
            result = api("POST", "/users", json={"email": email})
            st.session_state.user_id = result["id"]
            st.session_state.user_email = result["email"]
            st.rerun()

    st.divider()
    if st.button("Check backend status", use_container_width=True):
        health = api("GET", "/health")
        st.success(f"Backend is {health['status']} · {health['environment']}")

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
    docs_for_picker = api("GET", "/documents")
    doc_options = {"All documents": None}
    doc_options.update({d["filename"]: d["document_id"] for d in docs_for_picker})

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

    # Render past conversation history
    for entry in st.session_state.chat_log:
        # User Question
        st.markdown(
            f"""<div class="msg-row user"><div class="bubble user">{entry['question']}</div></div>""",
            unsafe_allow_html=True,
        )
        
        # Audio Player (Displays BEFORE / WITH text response if audio exists)
        if entry.get("audio_bytes"):
            st.audio(entry["audio_bytes"], format="audio/mp3", autoplay=entry.get("autoplay", False))
            # Turn off autoplay after first render so it doesn't replay on unrelated UI updates
            entry["autoplay"] = False

        # Assistant Answer
        st.markdown(
            f"""<div class="msg-row assistant"><div class="bubble assistant">{entry['answer']}</div></div>""",
            unsafe_allow_html=True,
        )

        if entry.get("sources"):
            with st.expander(f"{len(entry['sources'])} source(s)"):
                for s in entry["sources"]:
                    st.markdown(f"**{s['filename']}**")
                    st.caption(s["chunk_preview"])

        fcol1, fcol2, _ = st.columns([1, 1, 10])
        with fcol1:
            if st.button("👍", key=f"up_{entry['chat_message_id']}"):
                api("POST", "/feedback", json={"chat_message_id": entry["chat_message_id"], "rating": 5})
                st.toast("Thanks for the feedback")
        with fcol2:
            if st.button("👎", key=f"down_{entry['chat_message_id']}"):
                api("POST", "/feedback", json={"chat_message_id": entry["chat_message_id"], "rating": 1})
                st.toast("Thanks for the feedback")

    # Initialize dynamic recorder key in session state to prevent widget crash
    if "recorder_key_counter" not in st.session_state:
        st.session_state.recorder_key_counter = 0

    question_from_voice = None
    with st.container(border=True):
        st.markdown('<div class="section-label">Voice</div>', unsafe_allow_html=True)
        
        # Dynamic key prevents "An error has occurred" on state reload
        current_key = f"voice_input_{st.session_state.recorder_key_counter}"
        audio_value = st.audio_input("Record a question", key=current_key, label_visibility="collapsed")
        
        if audio_value is not None:
            if st.button("Transcribe & ask", type="primary"):
                with st.spinner("Transcribing..."):
                    files = {"file": ("question.wav", audio_value.getvalue(), "audio/wav")}
                    transcribed = api("POST", "/voice/transcribe", files=files)
                question_from_voice = transcribed["text"]
                st.caption(f'Heard: "{question_from_voice}"')
                # Increment counter so next render mounts a fresh recorder widget
                st.session_state.recorder_key_counter += 1
        else:
            st.caption("Click the microphone button to record your question.")

    question = st.chat_input("Ask a question about your documents...") or question_from_voice
    
    if question:
        with st.spinner("Searching documents & generating response..."):
            # 1. Fetch text answer from RAG backend
            result = api(
                "POST",
                "/chat",
                json={
                    "user_id": st.session_state.user_id,
                    "question": question,
                    "document_id": selected_document_id,
                },
            )
            
            # 2. If requested via voice, fetch audio response BEFORE appending to log & rerunning
            generated_audio_bytes = None
            if bool(question_from_voice):
                try:
                    audio_resp = requests.post(
                        f"{st.session_state.api_url}/voice/speak",
                        json={"text": result["answer"]},
                        timeout=30,
                    )
                    if audio_resp.ok:
                        generated_audio_bytes = audio_resp.content
                except Exception as e:
                    st.warning("Failed to generate voice playback.")

        # 3. Store everything together so audio renders WITH text
        st.session_state.chat_log.append(
            {
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
                "chat_message_id": result["chat_message_id"],
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
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                data = {"user_email": st.session_state.user_email}
                result = api("POST", "/upload", files=files, data=data)
            st.success(f"{result['filename']} processed — {result['num_chunks']} chunks")

# ---------------------- Documents tab ----------------------
with tab_docs:
    col_a, col_b = st.columns([5, 1])
    with col_a:
        st.markdown('<div class="section-label">All uploaded documents</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("Refresh", use_container_width=True, key="refresh_docs"):
            st.rerun()

    docs = api("GET", "/documents")
    if not docs:
        st.info("No documents uploaded yet.")
    for doc in docs:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 1.5, 1.5, 1])
            with c1:
                st.markdown(f"**{doc['filename']}**")
            with c2:
                color = STATUS_COLORS.get(doc["status"], "#64748b")
                st.markdown(
                    f'<span class="badge" style="background:{color}">{doc["status"]}</span>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.caption(f"{doc['num_chunks']} chunks")
            with c4:
                if st.button("Delete", key=f"del_{doc['document_id']}", use_container_width=True):
                    api("DELETE", f"/document/{doc['document_id']}")
                    st.toast(f"Deleted {doc['filename']}")
                    st.rerun()

# ---------------------- History tab ----------------------
with tab_history:
    col_a, col_b = st.columns([5, 1])
    with col_a:
        st.markdown('<div class="section-label">Your chat history</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("Refresh", use_container_width=True, key="refresh_history"):
            st.rerun()

    history = api("GET", f"/history?user_id={st.session_state.user_id}")
    if not history:
        st.info("No questions asked yet.")
    for item in history:
        with st.container(border=True):
            st.caption(item["created_at"])
            st.markdown(f"**Q:** {item['question']}")
            st.markdown(f"{item['answer']}")