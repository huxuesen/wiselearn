"""平台基类"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from autolearn.exceptions import LoginFailed, CaptchaError, RequestError, Non200Error, RetryExhaustedError, CourseNotFound
from autolearn.settings import Config
from autolearn.http_client import HttpClient


logging.getLogger(__name__).addHandler(logging.NullHandler())


class BasePlatform(ABC):
    def __init__(self, user_info: Dict[str, str], progress_callback=None) -> None:
        config = Config.get_config()
        self.user_info = user_info
        self.name: str = user_info.get("name", "unknown")
        self.progress_callback = progress_callback

        learn_cbit = config.get("Learn_Cbit", {})
        self.retry: int = learn_cbit.get("retry", 5)
        self.speed: float = learn_cbit.get("speed", 1.5)
        self.mode: str = learn_cbit.get("mode", "fast")

        aes_config = config.get("aes", {})
        self.aes_key: str = aes_config.get("key", "")
        self.aes_iv: str = aes_config.get("iv", "")

        self._http: Optional[HttpClient] = None

    @property
    def http(self) -> HttpClient:
        if self._http is None:
            raise RuntimeError("HttpClient not initialized. Use async context manager.")
        return self._http

    async def __aenter__(self) -> "BasePlatform":
        self._http = HttpClient(max_retries=self.retry)
        await self._http.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._http:
            await self._http.__aexit__()

    @abstractmethod
    async def learn(self) -> None:
        ...
