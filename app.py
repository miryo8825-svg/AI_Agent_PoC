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

# LangGraph関連
from agent import app_agent
from langchain_core.messages import HumanMessage

# --- 環境設定 ---
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Firestoreクライアント初期化
db = firestore.Client(database="ai-agent-poc-02")

# --- ユーザー管理 ---
valid_users_raw = os.getenv("VALID_USERS_JSON", "{}")
try:
    # 前後の不要な引用符や空白を削除してからパース
    clean_json = valid_users_raw.strip().strip("'").strip('"')
    VALID_USERS = json.loads(clean_json)
except json.JSONDecodeError as e:
    st.error(f"VALID_USERS_JSONの形式が不正です: {e}")
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
    try:
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
    except Exception as e:
        print(f"Firestore Save Error: {e}")
        return 0

def load_history(user):
    try:
        docs = db.collection("chat_history").where("user", "==", user).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
        return [d.to_dict() for d in docs]
    except Exception as e:
        print(f"Firestore Load Error: {e}")
        return []

async def call_agent_async(user_id, session_id, query: str):
    # 明示的に HumanMessage オブジェクトでラップして渡す
    inputs = {"messages": [HumanMessage(content=query)]}
    
    # 最終回答を取り出すためのロジック
    final_content = ""
    print(f"INFO: call_agent_async started for query: {query}")
    
    try:
        async for event in app_agent.astream(inputs, config={"configurable": {"thread_id": session_id}}):
            for node, output in event.items():
                print(f"DEBUG: Node Finished -> {node}")
                if "messages" in output:
                    last_msg = output["messages"][-1]
                    # 回答テキストがある場合のみ取得
                    if last_msg.content and (not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls):
                        if isinstance(last_msg.content, list):
                            final_content = "".join(part.get("text", "") for part in last_msg.content if isinstance(part, dict))
                        else:
                            final_content = last_msg.content

        return final_content if final_content else "回答を生成できませんでした。"
    except Exception as e:
        error_msg = f"Agent Error: {str(e)}"
        print(error_msg)
        return error_msg

# --- サイドバー表示 ---
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
        h_id = item.get("id", "?")
        if st.button(f"No.{h_id}: {item['query'][:15]}...", key=f"hist_{i}"):
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

# 検索フォーム
with st.form("search_form", clear_on_submit=True):
    query_input = st.text_input("質問を入力してください")
    submit_button = st.form_submit_button("検索")

if submit_button:
    if query_input:
        start_all = time.time()
        with st.spinner("検索中..."):
            # synonym_searchを実行してクエリを拡張
            enhanced_query = synonym_search(query_input)
            print(f"Enhanced Query: {enhanced_query}")
            
            res = asyncio.run(call_agent_async(current_user, st.session_state.session_id, enhanced_query))
            elapsed = time.time() - start_all
            
            # 履歴保存
            h_id = save_history(current_user, query_input, res, elapsed)
            st.session_state.selected_history = {"id": h_id, "query": query_input, "res": res, "time": elapsed}
    else:
        st.warning("質問を入力してください")

# 結果表示
if st.session_state.get("selected_history"):
    hist = st.session_state.selected_history
    st.divider()
    with st.container(border=True):
        st.caption(f"質問 No.{hist.get('id', '?')}")
        st.write(hist['query'])
    with st.container(border=True):
        st.caption("回答")
        st.write(hist['res'])
    st.info(f"実行時間: {hist['time']:.2f} 秒")