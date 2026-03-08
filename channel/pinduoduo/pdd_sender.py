# -*- coding: utf-8 -*-
"""
通过 HTTP API 直接发送拼多多消息（不依赖 Playwright）
"""
import logging
import time
import random
import requests

logger = logging.getLogger(__name__)


class PddSender:
    """通过 HTTP API 直接发送拼多多消息"""

    def __init__(self, cookies: dict = None, shop_id=None, page=None):
        """
        :param cookies: 登录后的 cookies 字典
        :param shop_id: 店铺ID（仅用于日志）
        :param page: 兼容旧接口，忽略
        """
        self.cookies = cookies or {}
        self.shop_id = shop_id
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Referer': 'https://mms.pinduoduo.com/',
            'Origin': 'https://mms.pinduoduo.com',
        }

    def _generate_request_id(self) -> str:
        """生成唯一请求ID"""
        return f"{int(time.time() * 1000)}{random.randint(1000, 9999)}"

    async def send_text(self, buyer_id: str, text: str) -> bool:
        """
        向指定买家发送文字消息（HTTP API）
        :param buyer_id: 买家平台ID
        :param text: 要发送的文本内容
        :return: 是否发送成功
        """
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._send_text_sync, buyer_id, text)
        return result

    def _send_text_sync(self, buyer_id: str, text: str) -> bool:
        """同步发送文字消息"""
        url = "https://mms.pinduoduo.com/plateau/chat/send_message"
        data = {
            "data": {
                "cmd": "send_message",
                "request_id": self._generate_request_id(),
                "message": {
                    "to": {
                        "role": "user",
                        "uid": buyer_id
                    },
                    "from": {
                        "role": "mall_cs"
                    },
                    "content": text,
                    "msg_id": None,
                    "type": 0,
                    "is_aut": 1,
                    "manual_reply": 0,
                },
            },
            "client": "WEB"
        }
        try:
            resp = requests.post(
                url,
                json=data,
                cookies=self.cookies,
                headers=self.headers,
                timeout=10
            )
            result = resp.json()
            logger.info("发送消息到买家 %s 响应: %s", buyer_id, str(result)[:200])
            if result.get("success"):
                logger.info("发送消息到买家 %s 成功", buyer_id)
                return True
            else:
                error_code = result.get("result", {}).get("error_code")
                error_msg = result.get("result", {}).get("error") or result.get("errorMsg", "")
                logger.error("发送消息失败: code=%s msg=%s", error_code, error_msg)
                return False
        except Exception as e:
            logger.error("发送消息异常: %s", e)
            return False
