# agent.py
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

from google.adk.agents import LlmAgent
from google.adk.tools import VertexAiSearchTool
from google.adk.tools import google_search

DATA_STORE_PATH = 'projects/gen-lang-client-0531287984/locations/global/collections/default_collection/dataStores/ai-agent-poc-1_1772677284079_ai_agent_poc_external_formatted'
DEFAULT_MODEL = 'gemini-3.1-flash-lite-preview'

# ------------------------------------------
# メインエージェント
# ------------------------------------------
root_agent = LlmAgent(
    name='root_agent',
    model=DEFAULT_MODEL,
    description='Analyze the intent of the query and invoke various tools.',
    sub_agents=[],
    instruction=config.INSTRUCTION_AGENT,
    tools=[VertexAiSearchTool(data_store_id=DATA_STORE_PATH, max_results=10), google_search]
)