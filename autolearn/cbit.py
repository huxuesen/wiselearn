"""CBIT (learning.cbit.com.cn) 学习平台"""
from __future__ import annotations

import asyncio
import base64
import random
import subprocess
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from autolearn.crypto import AESCipher
from autolearn.exceptions import CaptchaError, LoginFailed
from autolearn.base import BasePlatform

OCR_CWD = "/app/ocr"
OCR_SCRIPT = "/app/ocr/scripts/ocr.js"


class CbitPlatform(BasePlatform):
    def __init__(self, user_info: Dict[str, str], progress_callback=None) -> None:
        super().__init__(user_info, progress_callback)
        self.phone: str = user_info["phone"]
        self.password: str = user_info.get("passwd", "123456")
        self.lesson_library_id: str = user_info.get("tcid", "")

    async def _report(self, msg: str, progress: int = 0):
        """报告进度"""
        if self.progress_callback:
            await self.progress_callback(msg, progress)

    async def _run_ocr(self, image_bytes: bytes) -> str:
        temp_path = "/tmp/cbit_captcha_ocr.jpg"
        with open(temp_path, "wb") as f:
            f.write(image_bytes)

        loop = asyncio.get_running_loop()

        def _run() -> str:
            result = subprocess.run(
                ["node", OCR_SCRIPT, temp_path, "--lang", "eng"],
                capture_output=True, text=True, timeout=30,
                cwd=OCR_CWD
            )
            lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
            return lines[-1].strip() if lines else ""

        captcha_text = await loop.run_in_executor(None, _run)
        if not captcha_text:
            raise CaptchaError("OCR failed to recognize captcha")
        return captcha_text

    async def _login(self) -> None:
        if not self.aes_key or not self.aes_iv:
            raise LoginFailed("AES key/iv not configured")
        encryption = AESCipher(self.aes_key, self.aes_iv)
        await self._report("正在登录...", 0)

        captcha_base = "https://learning.cbit.com.cn/www/views/checking.jsp?dt="
        dt = urllib.parse.quote(
            " " + time.strftime("%a %b %d %Y %H:%M:%S")
            + " GMT+0800 (%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)"
        )
        captcha_url = captcha_base + dt
        login_url = "https://learning.cbit.com.cn/www/login/userlogin.do"

        login_response = None
        import aiohttp
        login_headers = {
            **self.http._headers,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://learning.cbit.com.cn/www/views/index/index.html",
            "Origin": "https://learning.cbit.com.cn",
        }

        for attempt in range(self.retry):
            async with aiohttp.ClientSession() as aio_session:
                async with aio_session.get(captcha_url) as resp:
                    body = await resp.read()
                    session_id = ""
                    for c in resp.headers.getall("set-cookie", []):
                        if c.startswith("sessionIdCookie="):
                            session_id = c.split("=", 1)[1].split(";")[0]
                            break

                if not session_id:
                    await asyncio.sleep(1)
                    continue

                verification_code = await self._run_ocr(body)
                if not verification_code:
                    continue

                en_name = encryption.encrypt(self.phone).decode()
                en_passwd = encryption.encrypt(self.password).decode()

                login_data = {
                    "username": en_name,
                    "password": en_passwd,
                    "yzm": verification_code,
                    "convHtmlField": "username,password",
                    "loginType": "pcLogin",
                    "sessionID": session_id,
                }
                async with aio_session.post(url=login_url, data=login_data, headers=login_headers) as resp:
                    result: dict = await resp.json(content_type=None)

                if result.get("success"):
                    login_response = result
                    break
                else:
                    await asyncio.sleep(1)

        if login_response is None:
            raise LoginFailed(f"{self.name} login failed after {self.retry} attempts")

        token = login_response["token"]
        self.http.headers["token"] = token
        await self._report("登录成功", 5)

    async def _get_lesson_ids(self) -> List[str]:
        url = "https://learning.cbit.com.cn/www/lesson/selectLessonApp.do"
        data = {
            "leName": "", "keyword": "", "pageSize": 9999,
            "sort": "createtime", "id": self.lesson_library_id,
            "level": 5, "pagetitle": "lessonLibrary",
        }
        resp = await self.http.post(url=url, data=data)
        result: dict = resp.json()
        lesson_list: list = result.get("lessonList", [])
        return [str(lesson["id"]) for lesson in lesson_list]

    async def _get_lesson_items(self, lesson_id: str) -> List[Dict[str, Any]]:
        url = "https://learning.cbit.com.cn/www/lessonDetails/details.do"
        data = {"lessonId": lesson_id}
        for _ in range(self.retry):
            resp = await self.http.post(url=url, data=data)
            if len(resp.body) > 6:
                result: dict = resp.json()
                lesson_items: list = result.get("lessonitem", [])
                if lesson_items:
                    return [{"id": item["id"], "time": float(item.get("all_times", 0)), "name": item.get("itemname", "unknown")} for item in lesson_items]
        return []

    async def _post_schedule(self, lesson_id: str, item_id: str, total_time: float, lesson_name: str, tcid: str, study_plan: float = 0) -> None:
        base_url = "https://learning.cbit.com.cn/www/lessonDetails/updateLessonProcessPC.do?"
        data_template = {
            "lessonId": lesson_id, "lessonItemId": item_id,
            "process": "-2", "tcid": tcid, "totalTime": total_time,
        }
        if self.mode == "fast":
            data = {**data_template, "suspendTime": total_time, "studytime": total_time}
            url = base_url + urllib.parse.urlencode(data)
            for _ in range(self.retry):
                resp = await self.http.post(url=url, data=data)
                result: dict = resp.json()
                if result.get("success"):
                    return
        elif self.mode == "normal":
            study_time = total_time * study_plan / 100
            while total_time > study_time:
                random_interval = random.randint(20, 80) // self.speed
                await asyncio.sleep(random_interval)
                study_time = study_time + random_interval * self.speed if total_time > study_time + random_interval * self.speed else total_time
                data = {**data_template, "suspendTime": study_time, "studytime": study_time}
                url = base_url + urllib.parse.urlencode(data)
                for _ in range(self.retry):
                    await self.http.post(url=url, data=data)

    async def learn(self) -> None:
        await self._login()

        await self._report("正在获取课程列表...", 10)
        lesson_ids = await self._get_lesson_ids()
        if not lesson_ids:
            await self._report("未发现课程", 100)
            return

        total = len(lesson_ids)
        await self._report(f"共找到 {total} 门课程，开始刷课", 15)

        completed = 0
        for lesson_id in lesson_ids:
            lesson_items = await self._get_lesson_items(lesson_id)
            if not lesson_items:
                continue

            for item in lesson_items:
                await self._post_schedule(
                    lesson_id=lesson_id, item_id=item["id"],
                    total_time=item["time"], lesson_name=item["name"],
                    tcid=self.lesson_library_id,
                )

            completed += 1
            pct = 15 + int(85 * completed / total)
            await self._report(f"进度: {completed}/{total} 门课程完成", pct)

        await self._report(f"全部完成！共完成 {total} 门课程", 100)
