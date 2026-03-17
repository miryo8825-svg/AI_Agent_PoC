# agent.py
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from tools import CustomVertexAISearchTool

from google import genai
from google.genai import types

client = genai.Client(http_options={'api_version': 'v1alpha'})

DATA_STORE_PATH = 'projects/gen-lang-client-0531287984/locations/global/collections/default_collection/dataStores/ai-agent-poc-1_1772677284079_ai_agent_poc_external_formatted'
DEFAULT_MODEL = 'gemini-3.1-flash-lite-preview'


# 必要な情報をセット
PROJECT_ID = 'gen-lang-client-0531287984'
LOCATION = 'global'
ENGINE_ID = 'ai-agent-poc-20260305-1_1772677316058'

# インスタンス化
tool_internal_search = CustomVertexAISearchTool(
    project_id=PROJECT_ID,
    location=LOCATION,
    engine_id=ENGINE_ID
)

# ------------------------------------------
# メインエージェント
# ------------------------------------------
root_agent = LlmAgent(
    name='root_agent',
    model=DEFAULT_MODEL,
    description='Analyze the intent of the query and invoke various tools.',
    sub_agents=[],
    instruction=config.INSTRUCTION_AGENT,
    tools=[tool_internal_search]
)