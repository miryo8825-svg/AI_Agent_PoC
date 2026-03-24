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
USER_ID = "mark"

# パスワード認証
def check_password():
    # 認証済みならTrueを返す
    if st.session_state.get("password_correct"):
        return True

    # 未認証なら入力欄を表示
    password = st.text_input("パスワードを入力してください", type="password")
    
    if st.button("ログイン"):
        if password == "hK7En*XQ":
            st.session_state["password_correct"] = True
            st.rerun()  # 画面再読み込み
        else:
            st.error("パスワードが違います")
            return False
    return False

# セッションIDをキャッシュさせるために関数化
@st.cache_resource
def get_session_info():
    return f"session_{uuid.uuid4()}"

# Runnerとセッションをキャッシュ（初期化コスト削減）
@st.cache_resource
def init_runner():
    session_service = InMemorySessionService()
    session_id = get_session_info()
    
    # セッション作成を同期的に実行
    asyncio.run(session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    ))
    
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service
    )
    return runner, session_id

# エージェント呼び出し関数を「結果を返す」ように修正
async def call_agent_async(runner, session_id, query: str): 
    content = types.Content(role='user', parts=[types.Part(text=query)])
    response = "Agent did not produce a final response."

    async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
        if event.is_final_response():
            if event.content and event.content.parts:
                response = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                response = f"Agent escalated: {event.error_message or 'No specific message.'}"
            break 
    return response

def main():
    st.title("AI Agent PoC")
    
    # 認証チェックを実行
    if not check_password():
        st.stop()  # ここで処理を止める
    
    # 初期化
    runner, session_id = init_runner()
    
    query = st.text_input("質問を入力してください")
    
    if st.button("検索"):
        if query:
            start_all = time.time()
            with st.spinner("検索中…"):
                # 類義語追加
                query_with_synonyms = synonym_search(query)
                
                # エージェント呼び出し（戻り値を取得）
                response = asyncio.run(call_agent_async(runner, session_id, query_with_synonyms))
                
                # 結果表示
                st.subheader("回答:")
                st.write(response)
                
                # 計測結果表示
                end_all = time.time()
                elapsed_time = end_all - start_all
                st.divider()
                st.info(f"実行時間: {elapsed_time:.2f} 秒")
        else:
            st.warning("質問を入力してください")

if __name__ == "__main__":
    main()