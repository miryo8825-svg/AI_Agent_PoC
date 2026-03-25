# ライブラリインストール
# pip install opensearch-py requests-aws4auth boto3 tqdm

# 実行コマンド(tmpの仮想環境起動後、rootユーザーで実行)
# sudo -u ai_navi /tmp/.venv/bin/python /tmp/get_csv_from_opensearch.py

import csv
import boto3
from opensearchpy import OpenSearch, helpers, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from tqdm import tqdm

# --- 設定 ---
# プロファイル名とリージョンを指定
PROFILE_NAME = 'ai_navi_prod'
REGION = 'us-west-2'
# OpenSearchのホストURL（HTTPSである必要があります）
HOST = 'search-ai-test-wg5kuv6rj7zwnaojbbua63wz7m.us-west-2.es.amazonaws.com'

INDEX_NAME = '*' 

# 必要なカラムをリストで定義（順序もこの通りに出力されます）
TARGET_COLUMNS = [
    'title', 'uri', 'content', 'category', 'datetime', 'country', 'weight'
]

# AWSセッション設定
session = boto3.Session(profile_name=PROFILE_NAME)
credentials = session.get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    'es',
    session_token=credentials.token
)

# クライアントの設定
client = OpenSearch(
    hosts=[{'host': HOST, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

def export_to_csv():
    # 1. 総件数を取得
    count_response = client.count(index=INDEX_NAME)
    total_hits = count_response['count']
    print(f"対象データ総数: {total_hits} 件")

    query = {"query": {"match_all": {}}}
    csv_file_path = '/tmp/output_data.csv'
    
    # CSV書き込み
    with open(csv_file_path, mode='w', encoding='utf-8', newline='') as f:
        # 指定したカラムのみを抽出・書き込み
        writer = csv.DictWriter(f, fieldnames=TARGET_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        
        print("CSV書き込み開始...")
        with tqdm(total=total_hits, unit="件") as pbar:
            for hit in helpers.scan(client, index=INDEX_NAME, query=query, scroll='5m', size=1000):
                # 取得データから必要なフィールドのみを抽出
                source_data = hit.get('_source', {})
                # extrasaction='ignore' が指定されているため、指定外の項目は自動で無視されます
                writer.writerow(source_data)
                pbar.update(1)

if __name__ == "__main__":
    print("エクスポート開始...")
    try:
        export_to_csv()
        print(f"完了しました: {csv_file_path}")
    except Exception as e:
        print(f"エラーが発生しました: {e}")