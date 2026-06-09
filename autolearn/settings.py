"""配置管理模块"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigError(Exception):
    pass


class Config:
    _config: Optional[Dict[str, Any]] = None
    _file_path: str = str(Path(__file__).resolve().parent / "config.yaml")

    @classmethod
    def load(cls, file_path: str = "") -> None:
        if file_path:
            cls._file_path = file_path
        with open(cls._file_path, "r", encoding="utf-8") as stream:
            cls._config = yaml.safe_load(stream)

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        if cls._config is None:
            cls.load()
        return cls._config or {}


Config.load()
