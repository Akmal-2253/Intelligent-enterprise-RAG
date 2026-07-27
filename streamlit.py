"""
Streamlit frontend for the RAG system.
Communicates with the FastAPI backend via HTTP endpoints using requests.
"""

import os
import requests
import streamlit as st

# Environment variable for backend URL (defaults to localhost for local dev)
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

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
# UI Stylesheet
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
        .app-header {
            display: flex; align-items: center; gap: 14px; padding: 20px 24px;
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 10px; margin-bottom: 20px;
        }
        .app-header .icon {
            width: 44px; height: 44px; background: var(--accent-soft);
            border-radius: 8px; display: flex; align-items: center; justify-content: center;
            font-size: 22px; flex-shrink: 0;
        }
        .app-header h1 { font-size: 20px; font-weight: 600; color: var(--text); margin: 0; }
        .app-header p { font-size: 13px; color: var(--text-muted); margin: 2px 0 0 0; }
        .msg-row { display: flex; margin-bottom: 14px; }
        .msg-row.user { justify-content: flex-end; }
        .msg-row.assistant { justify-content: flex-start; }
        .bubble { max-width: 72%; padding: 12px 16px; border-radius: 10px; font-size: 14.5px; line-height: 1.55; }
        .bubble.user { background: var(--accent); color: white; border-bottom-right-radius: 3px; }
        .bubble.assistant { background: var(--surface); border: 1px solid var(--border); color: var(--text); border-bottom-left-radius: 3px; }
        .badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; color: white; text-transform: capitalize; }
        .section-label { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px; }
        div[data-testid="stChatInput"] { background: var(--surface); }
        section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# Sidebar (Account Management)
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
            try:
                # HTTP Call to POST /users
                resp = requests.post(
                    f"{BACKEND_URL}/users",
                    json={"email": email}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.user_id = str(data["id"])
                    st.session_state.user_email = data["email"]
                    st.rerun()
                else:
                    st.error(f"Login failed ({resp.status_code}): {resp.text}")
            except Exception as e:
                st.error(f"Cannot connect to backend: {e}")

    st.divider()
    if st.button("Check system status", use_container_width=True):
        try:
            r = requests.get(f"{BACKEND_URL}/health")
            if r.status_code == 200:
                st.success(f"System status: {r.json().get('status', 'ok')}")
            else:
                st.error("Backend error")
        except Exception as e:
            st.error(f"Backend offline: {e}")

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

# ---------------------- Chat Tab ----------------------
with tab_chat:
    docs_for_picker = []
    try:
        r = requests.get(f"{BACKEND_URL}/documents")
        if r.status_code == 200:
            docs_for_picker = r.json()
    except Exception:
        pass

    doc_options = {"All documents": None}
    for d in docs_for_picker:
        d_id = d.get("id") or d.get("document_id")
        d_name = d.get("filename", "Document")
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

    for entry in st.session_state.chat_log:
        st.markdown(
            f"""<div class="msg-row user"><div class="bubble user">{entry['question']}</div></div>""",
            unsafe_allow_html=True,
        )
        if entry.get("audio_bytes"):
            st.audio(entry["audio_bytes"], format="audio/mp3")

        st.markdown(
            f"""<div class="msg-row assistant"><div class="bubble assistant">{entry['answer']}</div></div>""",
            unsafe_allow_html=True,
        )

        if entry.get("sources"):
            with st.expander(f"{len(entry['sources'])} source(s)"):
                for s in entry["sources"]:
                    st.markdown(f"**{s.get('filename', 'Source')}**")
                    st.caption(s.get("chunk_preview", ""))

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
                    try:
                        files = {"file": ("audio.wav", audio_value.getvalue(), "audio/wav")}
                        v_resp = requests.post(f"{BACKEND_URL}/voice/transcribe", files=files)
                        if v_resp.status_code == 200:
                            question_from_voice = v_resp.json().get("text", "")
                            st.success(f'Transcribed: "{question_from_voice}"')
                        else:
                            st.error(f"Voice error: {v_resp.text}")
                    except Exception as e:
                        st.error(f"Voice error: {e}")
                st.session_state.recorder_key_counter += 1

    question = st.chat_input("Ask a question about your documents...") or question_from_voice
    
    if question:
        with st.spinner("Searching documents & generating response..."):
            try:
                chat_payload = {
                    "user_id": st.session_state.user_id,
                    "question": question,
                    "document_id": selected_document_id
                }
                c_resp = requests.post(f"{BACKEND_URL}/chat", json=chat_payload)
                if c_resp.status_code == 200:
                    res_data = c_resp.json()
                    answer_text = res_data.get("answer", "")
                    sources_list = res_data.get("sources", [])
                    msg_id = res_data.get("chat_message_id", 0)

                    st.session_state.chat_log.append({
                        "question": question,
                        "answer": answer_text,
                        "sources": sources_list,
                        "chat_message_id": msg_id,
                    })
                    st.rerun()
                else:
                    st.error(f"Chat request failed ({c_resp.status_code}): {c_resp.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

# ---------------------- Upload Tab ----------------------
with tab_upload:
    st.markdown('<div class="section-label">Upload a document</div>', unsafe_allow_html=True)
    with st.container(border=True):
        uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded_file:
            st.caption(f"{uploaded_file.name} · {uploaded_file.size / 1024:.0f} KB")
        if st.button("Upload and process", type="primary", disabled=not uploaded_file):
            with st.spinner("Chunking, embedding, and indexing..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    data = {"user_email": st.session_state.user_email}
                    u_resp = requests.post(f"{BACKEND_URL}/upload", files=files, data=data)
                    if u_resp.status_code in [200, 201]:
                        st.success("File uploaded and processed successfully!")
                    else:
                        st.error(f"Upload failed ({u_resp.status_code}): {u_resp.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

# ---------------------- Documents Tab ----------------------
with tab_docs:
    col_a, col_b = st.columns([5, 1])
    with col_a:
        st.markdown('<div class="section-label">All uploaded documents</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("Refresh", use_container_width=True, key="refresh_docs"):
            st.rerun()

    docs = []
    try:
        r = requests.get(f"{BACKEND_URL}/documents")
        if r.status_code == 200:
            docs = r.json()
    except Exception:
        pass

    if not docs:
        st.info("No documents uploaded yet.")
    for doc in docs:
        doc_id = doc.get("id") or doc.get("document_id")
        fname = doc.get("filename", "")
        status = doc.get("status", "ready")
        chunks = doc.get("num_chunks", 0)

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
                    try:
                        del_r = requests.delete(f"{BACKEND_URL}/documents/{doc_id}")
                        if del_r.status_code == 200:
                            st.toast(f"Deleted {fname}")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete: {del_r.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ---------------------- History Tab ----------------------
with tab_history:
    col_a, col_b = st.columns([5, 1])
    with col_a:
        st.markdown('<div class="section-label">Your chat history</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("Refresh", use_container_width=True, key="refresh_history"):
            st.rerun()

    hist_data = []
    try:
        r = requests.get(f"{BACKEND_URL}/history", params={"user_id": st.session_state.user_id})
        if r.status_code == 200:
            hist_data = r.json()
    except Exception:
        pass

    if not hist_data:
        st.info("No questions asked yet.")
    for item in hist_data:
        created = item.get("created_at", "")
        q_text = item.get("question", "")
        a_text = item.get("answer", "")

        with st.container(border=True):
            st.caption(str(created))
            st.markdown(f"**Q:** {q_text}")
            st.markdown(f"{a_text}")
