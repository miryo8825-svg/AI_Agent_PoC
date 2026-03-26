import uuid
import time
import asyncio
import streamlit as st
from datetime import datetime
from google.cloud import firestore
from dotenv import load_dotenv
from agent import root_agent
from tools import synonym_search
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# Firestoreクライアントの初期化
db = firestore.Client(database="ai-agent-poc-01")

APP_NAME = "AI_Agent_PoC"

# ユーザー管理 
VALID_USERS = {
    "marklines": {"password": "hK7En*XQ", "name": "marklines"},
    "test001": {"password": "3901ir@", "name": "test001"}
}

# ログインフォーム
def login_form():
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

# 認証実行
login_form()
current_user = st.session_state.user

# 履歴管理 (Firestore)
def save_history(user, query, res, elapsed):
    # 全体の件数をカウントしてIDを生成
    total_count = db.collection("chat_history").count().get()[0][0].value
    db.collection("chat_history").add({
        "user": user,
        "query": query,
        "res": res,
        "time": elapsed,
        "timestamp": datetime.now(),
        "id": total_count + 1
    })
    return total_count + 1

def load_history(user):
    # Firestoreからログインユーザーの履歴を最新順に取得
    docs = db.collection("chat_history").where("user", "==", user).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    return [d.to_dict() for d in docs]

# Runner初期化
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

# サイドバーとメインのロジック
runner, session_id = init_runner(current_user)

with st.sidebar:
    st.header("AI Agent PoC")
    col1, col2 = st.columns(2)
    with col1:
        # 会話履歴の更新(自動更新されない場合)
        if st.button("履歴を更新"):
            st.rerun()
    with col2:
        if st.button("新規チャット"):
            st.session_state.selected_history = None
            st.rerun()
    
    st.divider()
    # DBから読み込み
    histories = load_history(current_user)
    for i, item in enumerate(histories):
        # 履歴選択時にIDも含めてセット
        h_id = item.get("id", "?") # 過去データ用
        if st.button(f"No.{h_id}: {item['query'][:20]}...", key=f"hist_{i}"):
            st.session_state.selected_history = {**item, "id": h_id}
            st.rerun()

# --- メイン画面 ---
st.title("AI Agent PoC")

col1, col2 = st.columns([4, 1])
with col1:
    st.write(f"*ログイン中*　ユーザー：{current_user}")
with col2:
    if st.button("ログアウト"):
        # セッション状態をクリアしてリロード
        st.session_state.user = None
        st.session_state.selected_history = None
        st.rerun()

# 検索フォームを常に上部に配置
with st.form("search_form", clear_on_submit=True):
    query = st.text_input("質問を入力してください")
    submit_button = st.form_submit_button("検索")

if submit_button:
    if query:
        start_all = time.time()
        with st.spinner("検索中…"):
            res = asyncio.run(call_agent_async(runner, current_user, session_id, synonym_search(query)))
            elapsed = time.time() - start_all
            
            # DBに保存しIDを取得
            id = save_history(current_user, query, res, elapsed)
            
            # 直後の検索結果を表示用にセット
            st.session_state.selected_history = {
                "id": id,
                "query": query, 
                "res": res, 
                "time": elapsed
            }
            # 検索時は履歴の表示状態を維持したいため、rerunは不要（そのまま以下の表示処理へ進む）
    else:
        st.warning("質問を入力してください")

# 結果表示
if st.session_state.get("selected_history"):
    st.divider()
    h_id = st.session_state.selected_history.get("id", "?")
    
    # 質問カード
    with st.container(border=True):
        st.caption(f"質問 *No.{h_id}*")
        st.write(st.session_state.selected_history['query'])
    
    # 回答カード
    with st.container(border=True):
        st.caption("回答")
        res_text = st.session_state.selected_history['res']
        st.write(res_text)
        
        # コピーボタン
        # if st.button("Copy"):
        #     st.write(f'<script>navigator.clipboard.writeText(`{res_text.replace("`", "")}`)</script>', unsafe_allow_html=True)
        #     st.toast("クリップボードにコピーしました")

    st.info(f"実行時間：{st.session_state.selected_history['time']:.2f} 秒")