FROM --platform=linux/amd64 python:3.11-slim

# Pythonのログ出力をバッファリングせず即座に表示させる（デバッグに必須）
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 1. requirements.txt だけコピーしてインストール
# requirements.txt を変えない限り pip は実行されない
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. ソースをコピー
COPY . .

EXPOSE 8080
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]