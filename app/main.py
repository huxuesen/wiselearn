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
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from app.database import init_db, create_task, get_task, get_all_tasks, update_task
from autolearn import run_cbit_user

app = FastAPI(title="WiseLearn 学习平台")

# 默认 TCID（从环境变量读取，Docker 部署时设置）
DEFAULT_TCID = os.environ.get("TCID", "")

# Serve templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# 存储运行中的后台任务
_running_tasks: dict[int, asyncio.Task] = {}


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tasks = get_all_tasks(20)
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks, "default_tcid": DEFAULT_TCID})


@app.post("/api/tasks")
async def submit_task(
    name: str = Form(...),
    phone: str = Form(...),
    passwd: str = Form(...),
    tcid: str = Form(default=""),
):
    # 如果前端没填 tcid，使用环境变量中的默认值
    if not tcid:
        tcid = DEFAULT_TCID
    task_id = create_task(name, phone, passwd, tcid)
    
    # 启动后台任务
    task = asyncio.create_task(run_worker(task_id))
    _running_tasks[task_id] = task
    
    return JSONResponse({"id": task_id, "status": "queued"})


@app.get("/api/tasks")
async def list_tasks():
    return JSONResponse(get_all_tasks(50))


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: int):
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return JSONResponse(task)


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: int):
    if task_id in _running_tasks:
        _running_tasks[task_id].cancel()
        del _running_tasks[task_id]
        update_task(task_id, status="cancelled", message="已取消")
    return JSONResponse({"ok": True})


async def run_worker(task_id: int):
    """后台运行刷课任务"""
    task_info = get_task(task_id)
    if not task_info:
        return

    async def progress_callback(msg: str, progress: int):
        update_task(task_id, message=msg, progress=progress)

    try:
        update_task(task_id, status="running", message="初始化...")
        
        await run_cbit_user({
            "name": task_info["name"],
            "phone": task_info["phone"],
            "passwd": task_info["passwd"],
            "tcid": task_info["tcid"],
        }, progress_callback)
        
        update_task(task_id, status="completed", progress=100, message="全部课程已完成！")
    except asyncio.CancelledError:
        update_task(task_id, status="cancelled", message="任务已取消")
    except Exception as e:
        update_task(task_id, status="failed", message=f"错误: {str(e)}")
    finally:
        _running_tasks.pop(task_id, None)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
