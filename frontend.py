"""
Streamlit chat UI (ChatGPT-style) with PERSISTENT multi-chat history,
talking to the FastAPI backend, which talks to local Ollama.

Run with:
    streamlit run frontend.py

Make sure the backend is already running:
    uvicorn backend:app --reload --port 8000

History is stored in chat_history.db (SQLite) in this folder and
survives restarts/refreshes.
"""

import requests
import streamlit as st
import db

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Local Ollama Chat", page_icon="💬", layout="wide")
db.init_db()

# ---------- Session state bootstrap ----------
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------- Sidebar: chat history list ----------
st.sidebar.title("💬 Chats")

if st.sidebar.button("➕ New chat", use_container_width=True):
    st.session_state.current_session_id = None
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")

sessions = db.get_all_sessions()
for s in sessions:
    col1, col2 = st.sidebar.columns([5, 1])
    is_active = s["id"] == st.session_state.current_session_id
    label = ("🟢 " if is_active else "") + s["title"]
    if col1.button(label, key=f"select_{s['id']}", use_container_width=True):
        st.session_state.current_session_id = s["id"]
        st.session_state.messages = db.get_messages(s["id"])
        st.rerun()
    if col2.button("🗑️", key=f"delete_{s['id']}"):
        db.delete_session(s["id"])
        if st.session_state.current_session_id == s["id"]:
            st.session_state.current_session_id = None
            st.session_state.messages = []
        st.rerun()

st.sidebar.markdown("---")

# ---------- Sidebar: model settings ----------
st.sidebar.subheader("⚙️ Settings")


@st.cache_data(ttl=30)
def get_models():
    try:
        resp = requests.get(f"{BACKEND_URL}/models", timeout=10)
        resp.raise_for_status()
        return resp.json().get("models", [])
    except Exception:
        return []


available_models = get_models()

if available_models:
    model = st.sidebar.selectbox("Model", available_models)
else:
    st.sidebar.warning("Could not fetch models. Is the backend + Ollama running?")
    model = st.sidebar.text_input("Model (manual)", value="llama3.2")

temperature = st.sidebar.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
system_prompt = st.sidebar.text_area(
    "System prompt", value="You are a helpful assistant.", height=100
)

st.sidebar.markdown("---")
st.sidebar.caption("Backend: " + BACKEND_URL)

# ---------- Main chat area ----------
st.title("💬 Local Chat (Ollama)")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Type your message...")

if prompt:
    # If this is a brand-new chat, create the session now (titled from this message)
    if st.session_state.current_session_id is None:
        st.session_state.current_session_id = db.create_session(prompt)

    session_id = st.session_state.current_session_id

    st.session_state.messages.append({"role": "user", "content": prompt})
    db.save_message(session_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    chat_history = [{"role": "system", "content": system_prompt}] + st.session_state.messages

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        try:
            with requests.post(
                f"{BACKEND_URL}/chat",
                json={
                    "model": model,
                    "messages": chat_history,
                    "temperature": temperature,
                },
                stream=True,
                timeout=None,
            ) as resp:
                for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        full_response += chunk
                        placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except requests.exceptions.ConnectionError:
            full_response = "⚠️ Could not reach the backend. Is `uvicorn backend:app` running on port 8000?"
            placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    db.save_message(session_id, "assistant", full_response)
    st.rerun()  # refresh sidebar so the new/updated chat title shows immediately