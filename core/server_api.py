# -*- coding: utf-8 -*-
"""
aikefu 服务器 REST API 客户端
主接口：POST /api/webhook/message
"""
import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15


class ServerAPI:
    """调用 aikefu Flask 服务器的 REST API"""

    def __init__(self, base_url: str = "http://8.145.43.255:6000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # 主消息处理接口
    # ------------------------------------------------------------------

    def send_message(
        self,
        shop_id: int,
        buyer_id: str,
        buyer_name: str,
        content: str,
        order_id: str = "",
        msg_type: str = "text",
        image_url: str = "",
    ) -> dict:
        """
        推送买家消息到aikefu服务器，获取AI回复
        POST /api/webhook/message
        返回：{"success": true, "reply": "...", "needs_human": false, "process_by": "rule"}
        """
        payload = {
            "shop_id": shop_id,
            "buyer_id": buyer_id,
            "buyer_name": buyer_name,
            "order_id": order_id or "",
            "content": content,
            "msg_type": msg_type,
            "image_url": image_url or "",
        }
        try:
            resp = self.session.post(
                f"{self.base_url}/api/webhook/message",
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error("调用服务器API失败: %s", e)
            return {"success": False, "error": str(e)}

    def send_message_by_token(
        self,
        shop_token: str,
        buyer_id: str,
        buyer_name: str,
        content: str,
        order_id: str = "",
        msg_type: str = "text",
        order_info: dict = None,
    ) -> dict:
        """
        通过shop_token推送买家消息（插件接口）
        POST /api/webhook/pdd
        """
        payload = {
            "shop_token": shop_token,
            "buyer_id": buyer_id,
            "buyer_name": buyer_name,
            "content": content,
            "msg_type": msg_type,
            "order_id": order_id or "",
            "order_info": order_info or {},
        }
        try:
            resp = self.session.post(
                f"{self.base_url}/api/webhook/pdd",
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error("调用pdd webhook失败: %s", e)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """检查服务器是否可达"""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/health",
                timeout=5,
            )
            return resp.status_code < 500
        except requests.RequestException:
            return False
