"""WiseLearn 入口模块"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autolearn.cbit import CbitPlatform

async def run_cbit_user(user_info: Dict[str, str], progress_callback=None) -> str:
    """运行单个用户的 CBIT 学习任务
    
    Args:
        user_info: 用户信息
        progress_callback: 可选的回调函数，用于报告进度
        
    Returns:
        结果消息
    """
    async with CbitPlatform(user_info, progress_callback) as platform:
        await platform.learn()
    return "完成所有课程"
