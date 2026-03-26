### 0.目的
Google Cloudサーバー上でDockerイメージをビルドし、AI Agentのテスト実行を行う

### 1.準備
app.pyと同一ディレクトリに以下を作成する

```
/src
├── app.py
├── Dockerfile
└── requirements.txt
```

#### Dockerfile

```
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8080
# Streamlitは8080ポートで動かすのがCloud Runの標準
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
```
#### requirements.txt
```
streamlit>=1.25.0
google-adk>=1.26.0
python-dotenv>=1.2.2
requests>=2.32.0
google-cloud-discoveryengine>=0.13.0
```


### 1.リポジトリ作成

```
gcloud artifacts repositories create agent_ai_poc --repository-format=docker --location=grobal
```

実行結果：
```
Enabling service [artifactregistry.googleapis.com] on project [gen-lang-client-0531287984]...
Operation "operations/acat.p2-180873355418-192a951d-a56e-4581-86fb-fa13148e8f49" finished successfully.
Create request issued for: [agent-ai-poc]
Waiting for operation [projects/gen-lang-client-0531287984/locations/asia-northeast1/operations/3cf68773-a7b4-43bf-9191-b289faa4c0fc] to complete...done.
Created repository [agent-ai-poc].
```

### 2.アプリデプロイ
app.pyと同じディレクトリで以下を実行しアプリをデプロイする。

アプリ更新のたびにデプロイが必要。

```
/src  <-- ここでターミナルを開く
├── app.py
├── Dockerfile
└── requirements.txt
```

```
gcloud run deploy agent-ai-poc-01 --source . --region asia-northeast1 --allow-unauthenticated
```
- --allow-unauthenticated：認証不要…Cloud Load Balancing + Cloud Armorを用いる場合はこちら
- --no-allow-unauthenticated：認証が必要

実行結果：
```
Building using Dockerfile and deploying container to Cloud Run service [agent-ai-poc-01] in project [gen-lang-client-0531287984] region [asia-northeast1]
✓ Building and deploying new service... Done.
  ✓ Creating Container Repository...
  ✓ Validating configuration...
  ✓ Uploading sources...
  ✓ Building Container... Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=asia-northeast1/196baee5-f114-4d40-8e4c-2ceb0beda702?project 
  =180873355418].
  ✓ Creating Revision...
  ✓ Routing traffic...
  ✓ Setting IAM Policy...
Done.
Service [agent-ai-poc-01] revision [agent-ai-poc-01-00001-bhd] has been deployed and is serving 100 percent of traffic.
Service URL: https://agent-ai-poc-01-180873355418.asia-northeast1.run.app
```