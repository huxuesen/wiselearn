# ===== 构建阶段：安装 Node.js 依赖 (tesseract.js) =====
FROM node:20-slim AS node-builder
WORKDIR /app/ocr
COPY ocr/package.json ./
RUN npm install --production

# ===== 运行阶段：Python + Node.js 混合镜像 =====
FROM python:3.12-slim

# 从 node-builder 复制 Node.js 运行时和依赖
COPY --from=node-builder /usr/local /usr/local
COPY --from=node-builder /app/ocr /app/ocr

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建 app 目录
WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY autolearn/ ./autolearn/
COPY ocr/ ./ocr/

# 创建数据目录
RUN mkdir -p /data
ENV DB_PATH=/data/tasks.db

EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8080/ || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
