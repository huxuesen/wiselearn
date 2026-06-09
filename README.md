# WiseLearn

智慧学习平台，带 Web 界面。

## 快速启动

### 用 Docker Compose（推荐）

```bash
# 先配置 TCID（可选），编辑 docker-compose.yml 取消 TCID 注释并填入你的课程库 ID
docker compose up -d
```

打开 http://localhost:8080 即可使用。

### 用 Docker

```bash
docker build -t wiselearn .
docker run -d -p 8080:8080 \
  -v $(pwd)/data:/data \
  -e TCID="你的课程库ID" \
  --name wiselearn wiselearn
```

### 本地直接运行

```bash
pip install -r requirements.txt
cd ocr && npm install && cd ..
TCID="你的课程库ID" uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## 课程库 ID（TCID）配置

默认情况下，前端页面会有一个「课程库 ID」输入框，留空则刷全部课程。

如果你只想刷指定课程库，可以通过环境变量 `TCID` 设置默认值：

- **Docker Compose**: 编辑 `docker-compose.yml`，取消 `TCID` 环境变量注释并填入 ID
- **Docker run**: 添加 `-e TCID="你的ID"`
- **本地运行**: `export TCID="你的ID"` 后再启动

设置后前端会自动填充，用户无需手动填写。

TCID 示例格式：`9c3e6c321ad44664878e0077b9851764`

## 使用

1. 打开 http://localhost:8080
2. 输入姓名、手机号、密码
3. 课程库 ID 如果环境已配置，会自动填充
4. 点击「开始学习」
5. 实时查看任务进度

## 配置

AES 加密密钥在 `autolearn/config.yaml` 中配置：

```yaml
aes:
  key: "dacf107e4bdbbef0"
  iv: "bcancid682e09aec"
```

## 技术栈

- FastAPI + Uvicorn
- SQLite
- Tesseract.js（本地 OCR）
- Docker
