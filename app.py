# app.py
import os
import json
import uuid
import time
import asyncio
import streamlit as st
from datetime import datetime
from google.cloud import firestore
from pathlib import Path
from dotenv import load_dotenv
from tools import synonym_search

# LangGraph関連のインポート
from agent import app_agent
from langchain_core.messages import HumanMessage

# デバッグ
# st.write(f"Files in /app: {os.listdir('.')}")
load_dotenv()

# Firestoreクライアントの初期化
db = firestore.Client(database="ai-agent-poc-02")

APP_NAME = "AI_Agent_PoC"

# --- ユーザー管理 ---
valid_users_raw = os.getenv("VALID_USERS_JSON", "{}")

# デバッグ用（エラーが出る場合のみコメントを外して確認）
# st.write(f"DEBUG: {valid_users_raw}") 

try:
    # 前後の不要な引用符や空白を削除してからパース
    clean_json = valid_users_raw.strip().strip("'").strip('"')
    VALID_USERS = json.loads(clean_json)
except json.JSONDecodeError as e:
    st.error(f"環境変数 VALID_USERS_JSON の形式が正しくありません。エラー: {e}")
    VALID_USERS = {}

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

# セッションIDの管理
# ブラウザを閉じるか「新規チャット」を押すまで同一の thread_id を維持し会話履歴を保持する
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{current_user}_{uuid.uuid4()}"

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

async def call_agent_async(user_id, session_id, query: str):
    # LangGraphでの実行
    inputs = {"messages": [HumanMessage(content=query)]}
    
    # 最終回答を取り出すためのロジック
    final_content = ""
    async for event in app_agent.astream(inputs, config={"configurable": {"thread_id": session_id}}):
        for node, output in event.items():
            if "messages" in output:
                # 最後のAgentの発言を取得
                last_msg = output["messages"][-1]
                if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
                    final_content = last_msg.content

    return final_content if final_content else "回答を生成できませんでした。"

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
            # セッションIDを更新して会話をリセット
            st.session_state.session_id = f"session_{current_user}_{uuid.uuid4()}"
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
        st.session_state.pop("session_id", None)
        st.rerun()

# 検索フォーム
with st.form("search_form", clear_on_submit=True):
    query = st.text_input("質問を入力してください")
    submit_button = st.form_submit_button("検索")

if submit_button:
    if query:
        start_all = time.time()
        with st.spinner("検索中…"):
            res = asyncio.run(call_agent_async(current_user, st.session_state.session_id, synonym_search(query)))
            elapsed = time.time() - start_all
            
            # DBに保存しIDを取得
            id = save_history(current_user, query, res, elapsed)
            
            # 表示用にセット
            st.session_state.selected_history = {
                "id": id,
                "query": query, 
                "res": res, 
                "time": elapsed
            }
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