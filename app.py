import uuid
import time
import asyncio
import streamlit as st
from dotenv import load_dotenv
from agent import root_agent
from tools import synonym_search
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

APP_NAME = "AI_Agent_PoC"

# 1. ユーザー管理
VALID_USERS = {
    "marklines": {"password": "hK7En*XQ", "name": "marklines"}
}

def login_form():
    """ログインフォーム"""
    if "user" not in st.session_state:
        st.session_state.user = None
    
    if st.session_state.user is None:
        st.title("AI Agent PoC - ログイン")
        with st.form("login_form"):
            username = st.text_input("ユーザー名")
            password = st.text_input("パスワード", type="password")
            if st.form_submit_button("ログイン"):
                if username in VALID_USERS and VALID_USERS[username]["password"] == password:
                    st.session_state.user = username
                    st.rerun()
                else:
                    st.error("ユーザー名またはパスワードが違います")
        st.stop()

# --- 認証実行 ---
login_form()
current_user = st.session_state.user

# --- 以降は認証済みユーザーのみ ---
st.title("AI Agent PoC")
st.write(f"ログイン中　ユーザー：{current_user}")

# 2. Runner初期化
@st.cache_resource
def init_runner(user_id):
    session_service = InMemorySessionService()
    session_id = f"session_{user_id}_{uuid.uuid4()}"
    asyncio.run(session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id))
    runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)
    return runner, session_id

async def call_agent_async(runner, user_id, session_id, query: str): 
    content = types.Content(role='user', parts=[types.Part(text=query)])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response():
            return event.content.parts[0].text if event.content else "回答なし"
    return "Agent did not produce a final response."

# 実行部
runner, session_id = init_runner(current_user)

# フォームで囲むことでエンターキー送信を有効化
with st.form("search_form"):
    query = st.text_input("質問を入力してください")
    submit_button = st.form_submit_button("検索")

if submit_button:
    if query:
        start_all = time.time()
        with st.spinner("検索中…"):
            q = synonym_search(query)
            res = asyncio.run(call_agent_async(runner, current_user, session_id, q))
            st.subheader("回答:")
            st.write(res)
            
            # 実行時間計測の復活
            end_all = time.time()
            elapsed_time = end_all - start_all
            st.divider()
            st.info(f"実行時間: {elapsed_time:.2f} 秒")
    else:
        st.warning("質問を入力してください")