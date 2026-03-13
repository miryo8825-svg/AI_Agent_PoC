# tools.py
import csv
import os

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
            f"\n\n【追加条件】\n"
            f"検索条件を作成する際、ユーザーの意図を網羅するために、"
            f"以下の類義語も必ず「OR条件」に含めて検索すること: {synonyms_str}"
        )
        return user_query + system_context
    
    return user_query