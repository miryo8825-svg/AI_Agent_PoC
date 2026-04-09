#agent.py
import os
from typing import Annotated, Sequence, TypedDict

from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1beta as discoveryengine

# プロンプト読み込み
import config

# --- 設定値 ---
PROJECT_ID = "gen-lang-client-0531287984"
LOCATION = "global"  # Discovery Engine用
GCP_LOCATION = "us-central1"  # Vertex AI (Gemini)用
DATA_STORE_ID = "ai-agent-poc2_1774259178825_opensearch_output_formatted"
ENGINE_ID = "ai-agent-poc4-natural-lang_1774512163529"
DEFAULT_MODEL = 'gemini-2.5-flash-lite'

# --- カスタムツールの定義 ---

@tool
def vertex_ai_search(query: str):
    """Marklines社内データを詳細に検索します。
    引数:
        query: 検索クエリ
    """
    
    try:
        client_options = (
            ClientOptions(api_endpoint=f"{LOCATION}-discoveryengine.googleapis.com")
            if LOCATION != "global"
            else None
        )
        client = discoveryengine.SearchServiceClient(client_options=client_options)

        # パス構築: engines を使用する形式
        serving_config = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection/engines/{ENGINE_ID}/servingConfigs/default_config"

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5,
            content_search_spec={
                "summary_spec": {
                    "summary_result_count": 5, # 制限値に合わせる
                    "include_citations": True
                },
                "snippet_spec": {"max_snippet_count": 1}
            }
        )
        
        response = client.search(request)
        
        results = []
        for result in response.results:
            data = getattr(result.document, "derived_struct_data", {})
            results.append({
                "title": data.get("title", "No Title"),
                "link": data.get("link", ""),
                "snippet": data.get("snippets", [{}])[0].get("snippet", "") if data.get("snippets") else ""
            })
        
        print(f"Search found {len(results)} results.")
        return str(results) if results else "関連する社内データは見つかりませんでした。"
    
    except Exception as e:
        print(f"Error in vertex_ai_search tool: {e}")
        return f"検索中にエラーが発生しました: {str(e)}"

@tool
def google_search_tool(query: str):
    """最新のニュースや一般的な公開情報をGoogle検索で調査します。社内データではクエリ意図を満たすのに不十分な場合のみ使用します。"""
    return f"Google Search Results for: {query} (Simulated)"

# --- Agent（Graph）の構築 ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "会話履歴"]

# モデルの初期化
llm = ChatVertexAI(
    model_name=DEFAULT_MODEL,
    project=PROJECT_ID,
    location=GCP_LOCATION,
    # システムプロンプトをリストではなく引数として渡す（パースエラー対策）
    system_instruction=config.INSTRUCTION_AGENT, 
).bind_tools([vertex_ai_search, google_search_tool])

def call_model(state: AgentState):
    """モデルを呼び出して次のアクションを決定する"""
    
    # state["messages"] から SystemMessage を除外（system_instructionと重複させない）
    # かつ、リストが空にならないようにフィルタリング
    input_messages = [m for m in state["messages"] if not isinstance(m, SystemMessage)]
    
    if not input_messages:
        print("Warning: No messages to send to LLM.")
        return {"messages": []}

    print(f"DEBUG LLM Invoke: Sending {len(input_messages)} messages.")
    
    try:
        response = llm.invoke(input_messages)
        return {"messages": [response]}
    except Exception as e:
        print(f"LLM Invoke Error: {e}")
        raise e

# グラフ定義
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode([vertex_ai_search, google_search_tool]))

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

# コンパイル (チェックポインタをメモリ上に配置)
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
app_agent = workflow.compile(checkpointer=memory)