"""异步 HTTP 客户端"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp

from autolearn.base import Non200Error, RequestError, RetryExhaustedError

DEFAULT_RETRIES = 5
DEFAULT_TIMEOUT = 15

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.0.0",
    "X-Requested-With": "XMLHttpRequest",
    "isapp": "0",
    "sec-ch-ua": '"Not/A)Brand";v="99", "Microsoft Edge";v="115", "Chromium";v="115"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

RETRIABLE_STATUSES = frozenset({500, 502, 503, 504})
RETRIABLE_EXCEPTIONS = (
    aiohttp.ClientConnectionError,
    aiohttp.ClientResponseError,
    asyncio.TimeoutError,
)


class HttpResponse:
    def __init__(self, status: int, headers: Dict[str, str], body: bytes, url: str = ""):
        self.status = status
        self.headers = headers
        self.body = body
        self.url = url

    def json(self) -> Any:
        import json
        return json.loads(self.body)

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)


class HttpClient:
    def __init__(self, headers: Optional[Dict[str, str]] = None, max_retries: int = DEFAULT_RETRIES, timeout: float = DEFAULT_TIMEOUT):
        self._headers = {**DEFAULT_HEADERS, **(headers or {})}
        self._max_retries = max_retries
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @headers.setter
    def headers(self, value: Dict[str, str]) -> None:
        self._headers = value

    async def __aenter__(self) -> "HttpClient":
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, override_headers: Optional[Dict[str, str]] = None) -> HttpResponse:
        return await self._request("GET", url, params=params, override_headers=override_headers)

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None, override_headers: Optional[Dict[str, str]] = None) -> HttpResponse:
        return await self._request("POST", url, data=data, json=json, override_headers=override_headers)

    async def _request(self, method: str, url: str, params=None, data=None, json=None, override_headers=None) -> HttpResponse:
        headers = {**self._headers, **(override_headers or {})}
        last_exception: Optional[Exception] = None
        response: Optional[aiohttp.ClientResponse] = None

        for attempt in range(self._max_retries + 1):
            try:
                if method == "GET":
                    response = await self._session.get(url, headers=headers, params=params)
                else:
                    response = await self._session.post(url, headers=headers, data=data, json=json)
                body = await response.read()
                hr = HttpResponse(response.status, dict(response.headers), body, str(response.url))
                if response.status != 200 and response.status in RETRIABLE_STATUSES:
                    raise Non200Error(f"HTTP {response.status}", str(response.url), response.status)
                return hr
            except RETRIABLE_EXCEPTIONS as e:
                last_exception = e
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2**attempt, 10))
            except Non200Error as e:
                last_exception = e
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2**attempt, 10))

        raise RetryExhaustedError(
            f"Max retries ({self._max_retries}) exceeded",
            str(response.url) if response else "",
            response.status if response else 0,
        ) from last_exception
