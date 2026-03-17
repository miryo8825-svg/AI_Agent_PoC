# main.py

from dotenv import load_dotenv
load_dotenv()

import uuid
import time
from agent import root_agent
from tools import synonym_search
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

import asyncio
from google.genai import types

APP_NAME = "AI_Agent_PoC"
USER_ID = "mark"
SESSION_ID = f"session_{uuid.uuid4()}" # 毎回ユニークにする

async def call_agent_async(runner, query: str): 
    # メッセージ作成
    content = types.Content(role='user', parts=[types.Part(text=query)])
    
    response = "Agent did not produce a final response."
    
    # イベントを反復処理
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        
        # ツール呼び出しの試行を確認
        if hasattr(event, 'tool_calls') and event.tool_calls:
            print(f"[DEBUG] LLMがツール呼び出しを生成: {event.tool_calls}")

        # エラーイベントを捕捉
        # ADKではエラーが起きると actions.escalate や error_message が入ることがあります
        if hasattr(event, 'actions') and event.actions and event.actions.escalate:
            print(f"!!! [ERROR EVENT] Agent escalated: {event.error_message}")
        
        if hasattr(event, 'tool_outputs') and event.tool_outputs:
            for output in event.tool_outputs:
                print(f"\n>>> [検索結果ログ] {output}")
        
        # デバッグ用（全イベント出力）
        print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}")

        # 属性リストを表示
        attrs = [a for a in dir(event) if not a.startswith('__')]
        print(f"\n--- [DEBUG] Event Type: {type(event).__name__} ---")
        
        # 重要な属性があるか一つずつ確認
        for attr in attrs:
            try:
                val = getattr(event, attr)
                # 辞書やオブジェクトの中身が大きすぎる場合を考慮
                if val is not None:
                    # 'tool' や 'action' という言葉を含む属性があれば詳しく表示
                    if any(x in attr.lower() for x in ['tool', 'action', 'content', 'message']):
                        print(f"  [Attr: {attr}] = {val}")
            except Exception:
                continue

        if event.is_final_response():
            if event.content and event.content.parts:
                response = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                response = f"Agent escalated: {event.error_message or 'No specific message.'}"
            break 
    
    print(f"Response: {response}")

async def main():
    # 1. セッションサービスの準備
    session_service = InMemorySessionService()

    # 2. セッション作成
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    # 3. Runner を初期化
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service
    )
    
    while True:

        # 4. ユーザー入力を取得
        query = input("\n[AIAgent] クエリを入力 (qで終了): ")
        if query.lower() == 'q': break
        
        # --- 計測開始 ---
        start_all = time.time()
        
        # 5. 類義語追加
        query_with_synonyms = synonym_search(query)
        
        # 6. エージェント呼び出し
        await call_agent_async(runner, query_with_synonyms)
        
        # --- 計測終了と表示 ---
        end_all = time.time()
        elapsed_time = end_all - start_all
        print(f"\n-------------------------------------------")
        print(f"実行時間: {elapsed_time:.2f} s")
        print(f"-------------------------------------------")
    

if __name__ == "__main__":
    asyncio.run(main())