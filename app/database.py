"""数据库模块"""
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).resolve().parent / "tasks.db"))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            passwd TEXT NOT NULL,
            tcid TEXT DEFAULT '',
            client_id TEXT DEFAULT '',
            status TEXT DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)
    # 启动时清除旧任务记录，防止他人看到历史
    conn.execute("DELETE FROM tasks")
    # 兼容旧数据库：添加 client_id 字段（如果不存在）
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN client_id TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 字段已存在
    conn.commit()
    conn.close()


def create_task(name: str, phone: str, passwd: str, tcid: str = "", client_id: str = "") -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (name, phone, passwd, tcid, client_id) VALUES (?, ?, ?, ?, ?)",
        (name, phone, passwd, tcid, client_id),
    )
    conn.commit()
    task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return task_id


def get_task(task_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tasks(client_id: str = "", limit: int = 50) -> list[dict]:
    """获取任务列表，按 client_id 过滤"""
    conn = get_db()
    if client_id:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit),
        ).fetchall()
    else:
        # 没有 client_id 时不返回任何历史记录
        conn.close()
        return []


def update_task(task_id: int, status: str = None, progress: int = None, message: str = None):
    conn = get_db()
    fields = []
    values = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if progress is not None:
        fields.append("progress = ?")
        values.append(progress)
    if message is not None:
        fields.append("message = ?")
        values.append(message)
    fields.append("updated_at = datetime('now', 'localtime')")
    values.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
