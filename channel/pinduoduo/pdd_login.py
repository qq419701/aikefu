# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import os
import requests
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

PDD_LOGIN_URL = "https://mms.pinduoduo.com/"
BROWSER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".aikefu-client", "browser_data")


class PddLogin:
    def __init__(self, shop_id, db_client=None):
        self.shop_id = shop_id
        self.db_client = db_client
        self.cookies = {}
        self.im_token = ""

    def get_user_data_dir(self):
        d = os.path.join(BROWSER_DATA_DIR, f"shop_{self.shop_id}")
        os.makedirs(d, exist_ok=True)
        return d

    async def login(self, username="", password=""):
        user_data_dir = self.get_user_data_dir()
        logger.info("店铺 %s 开始登录流程", self.shop_id)
        async with async_playwright() as pw:
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=["--no-sandbox"],
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(PDD_LOGIN_URL, timeout=30000)
            await asyncio.sleep(3)
            logger.info("店铺 %s 当前URL: %s", self.shop_id, page.url)

            # 等待用户完成登录和滑块验证，直到稳定停留在非login页面
            logger.info("店铺 %s 等待用户完成登录/验证（最多5分钟）...", self.shop_id)
            try:
                await page.wait_for_function(
                    """() => {
                        const url = window.location.href;
                        return !url.includes('login') && !url.includes('verify') &&
                               !url.includes('captcha') && !url.includes('slide');
                    }""",
                    timeout=300000
                )
                await asyncio.sleep(3)
                logger.info("店铺 %s 登录/验证完成，URL: %s", self.shop_id, page.url)
            except Exception as e:
                logger.error("店铺 %s 等待超时: %s", self.shop_id, e)
                await ctx.close()
                return False

            # 获取 cookies
            raw = await ctx.cookies()
            self.cookies = {c["name"]: c["value"] for c in raw}
            logger.info("店铺 %s cookies: %d个", self.shop_id, len(self.cookies))

            # 获取 im_token
            await self._fetch_im_token(page)
            logger.info("店铺 %s im_token: [%s]", self.shop_id,
                       self.im_token[:30] if self.im_token else "未获取到!")

            await ctx.close()

        if not self.im_token:
            logger.warning("店铺 %s 尝试用requests获取token", self.shop_id)
            await self._fetch_im_token_by_requests()

        logger.info("店铺 %s 登录流程完成, im_token=%s",
                   self.shop_id, "成功" if self.im_token else "失败")
        return True

    async def _fetch_im_token(self, page):
        try:
            resp = await page.evaluate("""async () => {
                const r = await fetch("https://mms.pinduoduo.com/chats/getToken",
                    {method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
                    body:"version=3",credentials:"include"});
                return await r.text();
            }""")
            logger.info("token响应(方法1): %s", str(resp)[:300])
            data = json.loads(resp)
            token = (data.get("token") or
                     (data.get("result") or {}).get("token") or
                     (data.get("result") or {}).get("imToken") or "")
            if token:
                self.im_token = token
                logger.info("im_token获取成功(方法1)")
        except Exception as e:
            logger.error("token方法1失败: %s", e)

    async def _fetch_im_token_by_requests(self):
        try:
            r = requests.post(
                "https://mms.pinduoduo.com/chats/getToken",
                data={"version": "3"},
                cookies=self.cookies,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://mms.pinduoduo.com/",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=10
            )
            logger.info("token响应(方法2): %s", r.text[:300])
            data = r.json()
            token = (data.get("token") or
                     (data.get("result") or {}).get("token") or
                     (data.get("result") or {}).get("imToken") or "")
            if token:
                self.im_token = token
                logger.info("im_token获取成功(方法2)")
        except Exception as e:
            logger.error("token方法2失败: %s", e)

    def get_page(self):
        return None

    async def close(self):
        pass
