#agent.py
import os
from typing import Annotated, Sequence, Optional

# LangGraph 公式推奨の State 管理
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import tool

from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1beta as discoveryengine

# プロンプト読み込み
import config

# --- 設定値 ---
PROJECT_ID = "gen-lang-client-0531287984"
LOCATION = "global"
GCP_LOCATION = "us-central1"
DATA_STORE_ID = "ai-agent-poc2_1774259178825_opensearch_output_formatted"
ENGINE_ID = "ai-agent-poc4-natural-lang_1774512163529"
DEFAULT_MODEL = 'gemini-2.5-flash-lite'

# --- カスタムツール定義 ---
@tool("marklines_search")
def marklines_search(query: str, filter: Optional[str] = None):
    """
    Marklinesの自動車業界専門データベースを検索します。
    引数:
        query: 検索キーワード
        filter: 検索フィルタ（例: datetimeやurl_categoryの指定）
    販売台数、スペック、企業情報、市場動向などの社内データが必要な場合に必ず使用してください。
    """
    try:
        client_options = ClientOptions(api_endpoint=f"{LOCATION}-discoveryengine.googleapis.com") if LOCATION != "global" else None
        client = discoveryengine.SearchServiceClient(client_options=client_options)
        serving_config = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/engines/{ENGINE_ID}/servingConfigs/default_config"

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            filter=filter, # モデルが生成したフィルタを適用
            page_size=5,
            content_search_spec={
                "summary_spec": {"summary_result_count": 5, "include_citations": True},
                "snippet_spec": {"max_snippet_count": 1}
            }
        )
        response = client.search(request)
        results = []
        for result in response.results:
            # 検索結果取得
            doc = result.document
            raw_data = dict(doc.struct_data) 

            # スキーマに合わせて抽出キーを修正 (link -> uri, snippet -> content)
            results.append({
                "title": raw_data.get("title", "No Title"),
                "link": raw_data.get("uri", ""),
                "snippet": raw_data.get("content", "")
            })
        return str(results) if results else "関連データは見つかりませんでした。"
    except Exception as e:
        return f"検索エラー: {str(e)}"

@tool("google_search_tool")
def google_search_tool(query: str):
    """
    最新ニュースや一般的な公開情報をGoogle検索します。社内データのみではクエリ意図を満たせないケースのみに使用してください。
    """
    return f"Google Search Result for: {query} (Simulated)"

tools = [marklines_search, google_search_tool]

# --- Agent（Graph）構築 ---

# モデルの初期化
llm = ChatGoogleGenerativeAI(
    model=DEFAULT_MODEL,
    project=PROJECT_ID,
    vertexai=True,
).bind_tools(tools)

def call_model(state: MessagesState):
    """モデル呼び出しとメッセージ成型"""
    
    # MessagesState の state["messages"] には全履歴が含まれる
    # Vertex AI SDK のバグ回避のため、一時的に履歴を加工
    processed_messages = []
    
    # 最初のメッセージが SystemMessage でない場合、先頭に挿入
    if not any(isinstance(m, SystemMessage) for m in state["messages"]):
        processed_messages.append(SystemMessage(content=config.INSTRUCTION_AGENT))
    
    for m in state["messages"]:
        if isinstance(m, SystemMessage): continue
            
        # 【重要】IndexError回避策：空のAIMessageにスペースを入れる
        if isinstance(m, AIMessage) and m.tool_calls:
            if not m.content or m.content.strip() == "":
                m.content = " " 
        processed_messages.append(m)

    try:
        response = llm.invoke(processed_messages)
        if response.content is None:
            response.content = ""
        return {"messages": [response]}
    except Exception as e:
        print(f"LLM ERROR: {e}")
        # 万が一のIndexError時のフォールバック
        if "IndexError" in str(e):
            last_human = [m for m in processed_messages if isinstance(m, HumanMessage)][-1]
            return {"messages": [llm.invoke([processed_messages[0], last_human])]}
        raise e

# グラフ定義
workflow = StateGraph(MessagesState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

# コンパイル (チェックポインタをメモリ上に配置)
from langgraph.checkpoint.memory import MemorySaver
app_agent = workflow.compile(checkpointer=MemorySaver())