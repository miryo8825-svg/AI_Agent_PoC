2026/03/05
# AI Agent 環境構築トラブルシューティング

## 権限エラー
AI AgentからVertex AI Searchをツールとして呼び出したときに、下記エラーが出た場合

> Please grant discovery engine user role to your agent project's p4sa account in the data store project

### 解決手順
https://docs.cloud.google.com/agent-builder/agent-designer?hl=ja#set-up-tools

### 補足 (Gemini-3.1-Flash)
        このエラーは、「エージェントを動かしているシステム（サービスアカウント）が、検索対象の社内データストア（Vertex AI Search）にアクセスするための権限を持っていない」 というセキュリティ（IAM）上の制限によるものです。

        エラーメッセージを直訳すると、「エージェント側のプロジェクトのP4SA（専用サービスアカウント）に対して、データストア側のプロジェクトで『Discovery Engine User』のロール（権限）を付与してください」という意味になります。

        エージェントとデータストアが別のGoogle Cloudプロジェクトにある場合はもちろん、同じプロジェクト内にある場合でも、明示的な権限付与が必要になることがあります。

        以下の手順で権限（IAMロール）を付与してください。

        解決手順
        1. エージェント側プロジェクトの「プロジェクト番号」を確認する
        Google Cloud コンソールを開きます。
        エージェントを作成したプロジェクトを選択します。
        ダッシュボードの「プロジェクト情報」パネルから**「プロジェクト番号」**（12桁程度の数字）をメモします。

        2. P4SA（サービスアカウント）のメールアドレスを特定する
        エラーメッセージに出ている「p4sa」とは、Google Cloudが内部連携用に自動生成するサービスアカウントのことです。
        今回権限を付与すべきアカウントは、以下の形式になります。

                - service-[プロジェクト番号]@gcp-sa-aiplatform-re.iam.gserviceaccount.com
                - service-[プロジェクト番号]@gcp-sa-dialogflow.iam.gserviceaccount.com
                - service-[プロジェクト番号]@gcp-sa-discoveryengine.iam.gserviceaccount.com

        3. データストア側プロジェクトで権限（IAM）を付与する
        エージェントとデータストアが同じプロジェクトならそのまま、別のプロジェクトにあるならデータストアが存在するプロジェクトに切り替えてから以下の操作を行います。

        左側のナビゲーションメニューから [IAM と管理] > [IAM] を開きます。
        画面上部の [+ アクセス権を付与]（または [追加]）をクリックします。

        [新しいプリンシパル] の欄に、手順2で特定したサービスアカウントのメールアドレスを貼り付けます。
        （例：service-123456789012@ggcp-sa-discoveryengine.iam.gserviceaccount.com

                ※"service-[プロジェクト番号]@gcp-sa-dialogflow.iam.gserviceaccount.com"が使用できない場合、
                下記URLからDialogflow APIを有効化する
                https://console.cloud.google.com/marketplace/product/google/dialogflow.googleapis.com?q=search&referrer=search&authuser=0&hl=ja&project=gen-lang-client-0531287984

                ※それでも使用できない場合、Cloud Shell上で強制的に認証情報を作成→IAMページを再読み込みすると使用可能になる
                # gcloud beta services identity create --service=dialogflow.googleapis.com --project=[プロジェクトID]

        [ロールの割り当て] のドロップダウンをクリックし、検索窓に **「Discovery Engine User」または「Discovery Engine ユーザー」** と入力して、以下のロールを選択します。

                Discovery Engine ユーザー (または Discovery Engine User / roles/discoveryengine.user)

        [保存] をクリックします。

        💡 補足事項
        反映までの時間: IAM権限の変更がシステム全体に反映されるまで、数分〜最大10分程度かかることがあります。保存後、少し待ってから再度プレビュー画面でプロンプトを実行してみてください。

        同じプロジェクトの場合: もしプロジェクトが同一で、上記のDialogflowサービスアカウントが見つからない場合は、コンソールのIAM画面の右側にある「Google 提供のロール付与を含める」にチェックを入れると表示されるようになります。


        [参考：IAM を使用した Vertex AI のアクセス制御]
        https://docs.cloud.google.com/vertex-ai/docs/general/access-control?hl=ja

        Agent Builderは名称に「Vertex AI」とついていますが、システム内部では主に以下の3つのAPIが連携して動いています。

        - エージェントの会話制御: Dialogflow API (gcp-sa-dialogflow)
        - データストア（検索グラウンディング）: Discovery Engine API (gcp-sa-discoveryengine)
        - LLMモデル（Geminiなど）の呼び出し: Vertex AI API (gcp-sa-aiplatform) ※これが「Vertex AI サービスエージェント」です

## 「Internal Error」の内容を確認する
Agent AIのプレビュー画面ではツール呼び出し時のInternalErrorの内容を確認できないため、ローカルのPython仮想環境でAgentを実行する

### ローカル実行手順
https://google.github.io/adk-docs/get-started/quickstart/

## データストアのパスが見つからないエラー

- コレクション ID：基本的に「default_collection」

        ※ Vertex AI Serch > データストア詳細の Collection ID を入れるとエラーになるため注意

- データストアID：Vertex AI Serch > データストア詳細 > エンティティのID

        ※ Vertex AI Serch > データストア一覧で確認できるID(データストアID)を入れるとエラーになるため注意

        サンプル:

        projects/[プロジェクト番号]/locations/global/collections/default_collection/dataStores/[データストアのエンティティID]