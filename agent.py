#agent.py
import os
from typing import Annotated, Sequence, TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from google.cloud import discoveryengine_v1beta as discoveryengine

# プロンプト等は既存のconfig.pyから読み込み
import config

# --- 設定値 ---
PROJECT_ID = "gen-lang-client-0531287984"
LOCATION = "us"
DATA_STORE_ID = "ai-agent-poc2_1774259178825_opensearch_output_formatted" # 既存のデータストアID
DEFAULT_MODEL = 'gemini-3.1-flash-lite-preview'
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- カスタムツールの定義 ---

@tool
def vertex_ai_search(query: str):
    """Marklines社内データを詳細に検索します。
    引数:
        query: 検索クエリ
    """
    # ADKを使わずSDKを直接呼び出し
    client = discoveryengine.SearchServiceClient()
    serving_config = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/data_stores/{DATA_STORE_ID}/servingConfigs/default_search"

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=10,
        content_search_spec={
            "summary_spec": {
                "summary_result_count": 10,
                "include_citations": True
            },
            "snippet_spec": {"max_snippet_count": 1}
        }
    )
    
    response = client.search(request)
    
    # 検索結果を整形してAgentに渡す
    results = []
    for result in response.results:
        data = result.document.derived_struct_data
        results.append({
            "title": data.get("title"),
            "link": data.get("link"),
            "snippet": data.get("snippets", [{}])[0].get("snippet", "")
        })
    
    return str(results)

@tool
def google_search_tool(query: str):
    """最新のニュースや一般的な公開情報をGoogle検索で調査します。社内データではクエリ意図を満たすのに不十分な場合のみ使用します。"""
    return f"Google Search Results for: {query} (Simulated)"

# --- Agent（Graph）の構築 ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "会話履歴"]

# モデルの初期化 (ChatVertexAI の代替)
llm = ChatGoogleGenerativeAI (
    model="gemini-2.5-flash",
    api_key=GEMINI_API_KEY,
    project=PROJECT_ID,
    vertexai=True,
).bind_tools([vertex_ai_search, google_search_tool])

def call_model(state: AgentState):
    """モデルを呼び出して次のアクションを決定する"""
    # システムプロンプトを先頭に挿入
    messages = [{"role": "system", "content": config.INSTRUCTION_AGENT}] + list(state["messages"])
    response = llm.invoke(messages)
    return {"messages": [response]}

# グラフ定義
workflow = StateGraph(AgentState)

# ノードの追加
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode([vertex_ai_search, google_search_tool]))

# エッジの設定
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    tools_condition, # モデルがツールを呼ぶ必要があるか自動判断
)
workflow.add_edge("tools", "agent")

# コンパイル (チェックポインタをメモリ上に配置)
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
app_agent = workflow.compile(checkpointer=memory)