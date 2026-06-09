"""FastAPI 主应用"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from app.database import init_db, create_task, get_task, get_tasks, update_task
from autolearn import run_cbit_user

app = FastAPI(title="WiseLearn 学习平台")

# 默认 TCID（从环境变量读取，Docker 部署时设置）
DEFAULT_TCID = os.environ.get("TCID", "")

# 手动渲染模板，避免 Starlette Jinja2Templates 兼容性问题
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

def render_template(name: str, **context) -> str:
    """渲染 Jinja2 模板"""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(name)
    return template.render(**context)

# 存储运行中的后台任务
_running_tasks: dict[int, asyncio.Task] = {}
_cancel_events: dict[int, asyncio.Event] = {}


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, client_id: str = ""):
    # 没有 client_id 时不显示任何历史任务
    tasks = get_tasks(client_id) if client_id else []
    html = render_template("index.html", request=request, tasks=tasks, default_tcid=DEFAULT_TCID)
    return HTMLResponse(html)


@app.post("/api/tasks")
async def submit_task(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    passwd: str = Form(...),
    tcid: str = Form(default=""),
    client_id: str = Form(default=""),
):
    # tcid 已由前端预填环境变量值，用户删掉即为留空（自动发现课程）
    task_id = create_task(name, phone, passwd, tcid, client_id)

    # 创建取消事件
    cancel_event = asyncio.Event()
    _cancel_events[task_id] = cancel_event

    # 启动后台任务
    task = asyncio.create_task(run_worker(task_id, cancel_event))
    _running_tasks[task_id] = task

    # 如果是浏览器直接提交（非 JS），重定向回首页
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse('<script>location.href="/?submitted=1"</script>')

    return JSONResponse({"id": task_id, "status": "queued"})


@app.get("/api/tasks")
async def list_tasks(client_id: str = ""):
    return JSONResponse(get_tasks(client_id or ""))


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: int):
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return JSONResponse(task)


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: int):
    # 先更新数据库
    update_task(task_id, status="cancelled", message="正在取消...")
    # 设置取消事件
    if task_id in _cancel_events:
        _cancel_events[task_id].set()
    # 取消 asyncio task
    if task_id in _running_tasks:
        _running_tasks[task_id].cancel()
        del _running_tasks[task_id]
    return JSONResponse({"ok": True})


async def run_worker(task_id: int, cancel_event: asyncio.Event):
    """后台运行刷课任务"""
    task_info = get_task(task_id)
    if not task_info:
        return

    async def progress_callback(msg: str, progress: int):
        # 检查是否已被取消
        if cancel_event.is_set():
            raise asyncio.CancelledError()
        update_task(task_id, message=msg, progress=progress)

    try:
        update_task(task_id, status="running", message="初始化...")

        await run_cbit_user({
            "name": task_info["name"],
            "phone": task_info["phone"],
            "passwd": task_info["passwd"],
            "tcid": task_info["tcid"],
        }, progress_callback)

        # 正常完成
        if not cancel_event.is_set():
            # 如果已经设置了完成消息，保留它（比如"未发现课程"）
            current = get_task(task_id)
            if current and current.get("progress", 0) >= 100 and current.get("message"):
                # 已有完整消息，不再覆盖
                update_task(task_id, status="completed", progress=100)
            else:
                update_task(task_id, status="completed", progress=100, message="全部课程已完成！")
    except asyncio.CancelledError:
        update_task(task_id, status="cancelled", message="任务已取消")
    except Exception as e:
        update_task(task_id, status="failed", message=f"错误: {str(e)}")
    finally:
        _running_tasks.pop(task_id, None)
        _cancel_events.pop(task_id, None)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
