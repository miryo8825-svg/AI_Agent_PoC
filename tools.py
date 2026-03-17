# tools.py
import csv
import os
import logging
from google.cloud import discoveryengine_v1
from google.api_core.client_options import ClientOptions
from google.adk.tools.base_tool import BaseTool
from google import genai
from google.genai import types

logger = logging.getLogger("SearchLogger")
logging.basicConfig(level=logging.INFO)

client = genai.Client(http_options={'api_version': 'v1alpha'})


# =========================================================
# 類義語辞書作成（モジュールロード時に1回だけ実行）
# =========================================================
SYNONYM_DICT = {}
SYNONYMS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'synonyms.csv')

# synonyms.csv が存在する場合に辞書を作成
if os.path.exists(SYNONYMS_FILE_PATH):
    with open(SYNONYMS_FILE_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            words = [w.strip() for w in row if w.strip()]
            for word in words:
                if word not in SYNONYM_DICT:
                    SYNONYM_DICT[word] = set()
                # 自分以外の単語を類義語リストとして追加
                SYNONYM_DICT[word].update([w for w in words if w != word])

def synonym_search(user_query: str) -> str:
    if not SYNONYM_DICT:
        return user_query

    found_synonyms = set()
    # クエリ文字列に類義語が存在するかマッチング
    for key, synonyms in SYNONYM_DICT.items():
        if key in user_query:
            found_synonyms.update(synonyms)
    
    if found_synonyms:
        synonyms_str = ", ".join(list(found_synonyms))
        system_context = (
            f"\n\n**【追加条件】**\n"
            f"**以下の類義語も必ず「OR条件」に含めて検索すること、出力時に類義語の列挙や説明は行わないこと: {synonyms_str}**"
        )
        return user_query + system_context
    
    return user_query

# 出力をコンソールに確実に出すための設定
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class CustomVertexAISearchTool(BaseTool):
    """Vertex AI Search APIを直接叩くロギング対応ツール"""
    
    def __init__(self, project_id: str, location: str, engine_id: str):
        super().__init__(
            name="tool_internal_search",
            description="社内データベースを検索します。検索時はqueryと、必要であればfilterを使用すること。"
        )
        self.project_id = project_id
        self.location = location
        self.engine_id = engine_id
        self.client = discoveryengine_v1.SearchServiceClient()
        
        # モデルに引数の構造を教えるためのスキーマ
        self.input_schema = {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "検索キーワード"},
                "filter": {"type": "STRING", "description": "検索フィルタ条件 (例: url_category = 'report')"}
            },
            "required": ["query"]
        }

    def run(self, query: str, filter: str = None) -> str:
        # 1. ロギング（検索条件）
        logger.info(f"--- [Search Request] Query: {query}, Filter: {filter} ---")

        serving_config = f"projects/{self.project_id}/locations/{self.location}/collections/default_collection/engines/{self.engine_id}/servingConfigs/default_config"

        request = discoveryengine_v1.SearchRequest(
            serving_config=serving_config,
            query=query,
            filter=filter,
            page_size=5,
        )

        try:
            response = self.client.search(request)
            
            # 2. ロギングと結果抽出
            results_text = []
            for result in response:
                doc = result.document
                title = doc.derived_struct_data.get('title', 'No Title')
                snippet = doc.derived_struct_data.get('snippets', [{'snippet': ''}])[0].get('snippet', '')
                results_text.append(f"Title: {title}\nSnippet: {snippet}")
            
            formatted_results = "\n\n".join(results_text)
            logger.info(f"--- [Search Response] Success. Retrieved {len(results_text)} items ---")
            
            return formatted_results if formatted_results else "検索結果が見つかりませんでした。"
            
        except Exception as e:
            logger.error(f"Search API Error: {str(e)}")
            return f"検索エラー: {str(e)}"

    async def run_async(self, query: str, filter: str = None) -> str:
        return self.run(query, filter)