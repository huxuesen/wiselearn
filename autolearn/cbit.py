     1|"""CBIT (learning.cbit.com.cn) 学习平台"""
     2|from __future__ import annotations
     3|
     4|import asyncio
     5|import base64
     6|import random
     7|import subprocess
     8|import time
     9|import urllib.parse
    10|from typing import Any, Dict, List, Optional
    11|
    12|from autolearn.crypto import AESCipher
    13|from autolearn.exceptions import CaptchaError, LoginFailed
    14|from autolearn.base import BasePlatform
    15|
    16|# 直接 print 输出日志，确保 Docker 中能看到
    17|def _log(msg: str):
    18|    print(f"[cbit] {msg}", flush=True)
    19|
    20|OCR_CWD = "/app/ocr"
    21|OCR_SCRIPT = "/app/ocr/scripts/ocr.js"
    22|
    23|
    24|class CbitPlatform(BasePlatform):
    25|    def __init__(self, user_info: Dict[str, str], progress_callback=None) -> None:
    26|        super().__init__(user_info, progress_callback)
    27|        self.phone: str = user_info["phone"]
    28|        self.password: str = user_info.get("passwd", "123456")
    29|        self.lesson_library_id: str = user_info.get("tcid", "")
    30|        _log(f"初始化刷课任务: phone={self.phone}, tcid={self.lesson_library_id}")
    31|
    32|    async def _report(self, msg: str, progress: int = 0):
    33|        """报告进度"""
    34|        _log(f"[{self.phone}] {msg} ({progress}%)")
    35|        if self.progress_callback:
    36|            await self.progress_callback(msg, progress)
    37|
    38|    async def _run_ocr(self, image_bytes: bytes) -> str:
    39|        temp_path = "/tmp/cbit_captcha_ocr.jpg"
    40|        with open(temp_path, "wb") as f:
    41|            f.write(image_bytes)
    42|
    43|        loop = asyncio.get_running_loop()
    44|
    45|        def _run() -> str:
    46|            result = subprocess.run(
    47|                ["node", OCR_SCRIPT, temp_path, "--lang", "eng"],
    48|                capture_output=True, text=True, timeout=30,
    49|                cwd=OCR_CWD
    50|            )
    51|            lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
    52|            return lines[-1].strip() if lines else ""
    53|
    54|        captcha_text = await loop.run_in_executor(None, _run)
    55|        if not captcha_text:
    56|            _log(f"[{self.phone}] OCR 识别失败")
    57|            raise CaptchaError("OCR failed to recognize captcha")
    58|        _log(f"[{self.phone}] OCR 识别成功: {captcha_text}")
    59|        return captcha_text
    60|
    61|    async def _login(self) -> None:
    62|        if not self.aes_key or not self.aes_iv:
    63|            raise LoginFailed("AES key/iv not configured")
    64|        encryption = AESCipher(self.aes_key, self.aes_iv)
    65|        await self._report("正在登录...", 0)
    66|
    67|        captcha_base = "https://learning.cbit.com.cn/www/views/checking.jsp?dt="
    68|        dt = urllib.parse.quote(
    69|            " " + time.strftime("%a %b %d %Y %H:%M:%S")
    70|            + " GMT+0800 (%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)"
    71|        )
    72|        captcha_url = captcha_base + dt
    73|        login_url = "https://learning.cbit.com.cn/www/login/userlogin.do"
    74|
    75|        login_response = None
    76|        import aiohttp
    77|        login_headers = {
    78|            **self.http._headers,
    79|            "Accept": "application/json, text/javascript, */*; q=0.01",
    80|            "X-Requested-With": "XMLHttpRequest",
    81|            "Referer": "https://learning.cbit.com.cn/www/views/index/index.html",
    82|            "Origin": "https://learning.cbit.com.cn",
    83|        }
    84|
    85|        for attempt in range(self.retry):
    86|            _log(f"[{self.phone}] 登录尝试 {attempt+1}/{self.retry}")
    87|            async with aiohttp.ClientSession() as aio_session:
    88|                async with aio_session.get(captcha_url) as resp:
    89|                    body = await resp.read()
    90|                    session_id = ""
    91|                    for c in resp.headers.getall("set-cookie", []):
    92|                        if c.startswith("sessionIdCookie="):
    93|                            session_id = c.split("=", 1)[1].split(";")[0]
    94|                            break
    95|
    96|                if not session_id:
    97|                    _log(f"[{self.phone}] 获取 session_id 失败，重试")
    98|                    await asyncio.sleep(1)
    99|                    continue
   100|
   101|                verification_code = await self._run_ocr(body)
   102|                if not verification_code:
   103|                    continue
   104|
   105|                en_name = encryption.encrypt(self.phone).decode()
   106|                en_passwd = encryption.encrypt(self.password).decode()
   107|
   108|                login_data = {
   109|                    "username": en_name,
   110|                    "password": en_passwd,
   111|                    "yzm": verification_code,
   112|                    "convHtmlField": "username,password",
   113|                    "loginType": "pcLogin",
   114|                    "sessionID": session_id,
   115|                }
   116|                async with aio_session.post(url=login_url, data=login_data, headers=login_headers) as resp:
   117|                    result: dict = await resp.json(content_type=None)
   118|
   119|                if result.get("success"):
   120|                    login_response = result
   121|                    _log(f"[{self.phone}] 登录成功")
   122|                    break
   123|                else:
   124|                    _log(f"[{self.phone}] 登录失败: {result}")
   125|                    await asyncio.sleep(1)
   126|
   127|        if login_response is None:
   128|            raise LoginFailed(f"{self.name} login failed after {self.retry} attempts")
   129|
   130|        token = login_response["token"]
   131|        self.http.headers["token"] = token
   132|        await self._report("登录成功", 5)
   133|
   134|    async def _get_lesson_ids(self) -> List[str]:
   135|        url = "https://learning.cbit.com.cn/www/lesson/selectLessonApp.do"
   136|        data = {
   137|            "leName": "", "keyword": "", "pageSize": 9999,
   138|            "sort": "createtime", "id": self.lesson_library_id,
   139|            "level": 5, "pagetitle": "lessonLibrary",
   140|        }
   141|        resp = await self.http.post(url=url, data=data)
   142|        result: dict = resp.json()
   143|        lesson_list: list = result.get("lessonList", [])
   144|        _log(f"[{self.phone}] 获取到 {len(lesson_list)} 门课程 (tcid={self.lesson_library_id})")
   145|        if not lesson_list and self.lesson_library_id:
   146|            _log(f"[{self.phone}] tcid 可能不正确，没有获取到课程: {self.lesson_library_id}")
   147|        return [str(lesson["id"]) for lesson in lesson_list]
   148|
   149|    async def _get_lesson_items(self, lesson_id: str) -> List[Dict[str, Any]]:
   150|        url = "https://learning.cbit.com.cn/www/lessonDetails/details.do"
   151|        data = {"lessonId": lesson_id}
   152|        for _ in range(self.retry):
   153|            resp = await self.http.post(url=url, data=data)
   154|            if len(resp.body) > 6:
   155|                result: dict = resp.json()
   156|                lesson_items: list = result.get("lessonitem", [])
   157|                if lesson_items:
   158|                    return [{"id": item["id"], "time": float(item.get("all_times", 0)), "name": item.get("itemname", "unknown")} for item in lesson_items]
   159|        return []
   160|
   161|    async def _post_schedule(self, lesson_id: str, item_id: str, total_time: float, lesson_name: str, tcid: str, study_plan: float = 0) -> None:
   162|        base_url = "https://learning.cbit.com.cn/www/lessonDetails/updateLessonProcessPC.do?"
   163|        data_template = {
   164|            "lessonId": lesson_id, "lessonItemId": item_id,
   165|            "process": "-2", "tcid": tcid, "totalTime": total_time,
   166|        }
   167|        if self.mode == "fast":
   168|            data = {**data_template, "suspendTime": total_time, "studytime": total_time}
   169|            url = base_url + urllib.parse.urlencode(data)
   170|            for attempt in range(self.retry):
   171|                resp = await self.http.post(url=url, data=data)
   172|                result: dict = resp.json()
   173|                if result.get("success"):
   174|                    _log(f"[{self.phone}] 课时上报成功: {lesson_name} ({total_time}s) tcid={tcid}")
   175|                    return
   176|                else:
   177|                    _log(f"[{self.phone}] 课时上报失败 (第{attempt+1}次): {lesson_name} - {result}")
   178|        elif self.mode == "normal":
   179|            study_time = total_time * study_plan / 100
   180|            while total_time > study_time:
   181|                random_interval = random.randint(20, 80) // self.speed
   182|                await asyncio.sleep(random_interval)
   183|                study_time = study_time + random_interval * self.speed if total_time > study_time + random_interval * self.speed else total_time
   184|                data = {**data_template, "suspendTime": study_time, "studytime": study_time}
   185|                url = base_url + urllib.parse.urlencode(data)
   186|                for _ in range(self.retry):
   187|                    await self.http.post(url=url, data=data)
   188|
   189|    async def learn(self) -> None:
   190|        await self._login()
   191|
   192|        await self._report("正在获取课程列表...", 10)
   193|        lesson_ids = await self._get_lesson_ids()
   194|        if not lesson_ids:
   195|            await self._report("未发现课程", 100)
   196|            return
   197|
   198|        total = len(lesson_ids)
   199|        await self._report(f"共找到 {total} 门课程，开始刷课", 15)
   200|
   201|        completed = 0
   202|        for lesson_id in lesson_ids:
   203|            lesson_items = await self._get_lesson_items(lesson_id)
   204|            if not lesson_items:
   205|                _log(f"[{self.phone}] 课程 {lesson_id} 无学习项，跳过")
   206|                continue
   207|
   208|            _log(f"[{self.phone}] 课程 {lesson_id}: {len(lesson_items)} 个学习项")
   209|
   210|            for item in lesson_items:
   211|                _log(f"[{self.phone}] 上报课时: {item['name']} ({item['time']}s)")
   212|                await self._post_schedule(
   213|                    lesson_id=lesson_id, item_id=item["id"],
   214|                    total_time=item["time"], lesson_name=item["name"],
   215|                    tcid=self.lesson_library_id,
   216|                )
   217|
   218|            completed += 1
   219|            pct = 15 + int(85 * completed / total)
   220|            await self._report(f"进度: {completed}/{total} 门课程完成", pct)
   221|
   222|        await self._report(f"全部完成！共完成 {total} 门课程", 100)
   223|