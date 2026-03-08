# -*- coding: utf-8 -*-
"""
拼多多商品信息采集模块
采集店铺商品数据，用于同步到 aikefu 知识库
"""
import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

PDD_GOODS_LIST_URL = "https://mms.pinduoduo.com/mms/api/goods/list"


class PddProductCollector:
    """拼多多商品采集器"""

    def __init__(self, shop_id: int, db_client=None, server_api=None):
        self.shop_id = shop_id
        self.db_client = db_client
        self.server_api = server_api

    async def fetch_products(self, cookies: dict, page: int = 1, page_size: int = 20) -> list:
        """
        获取商品列表
        GET https://mms.pinduoduo.com/mms/api/goods/list
        """
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers = {
            "Cookie": cookie_str,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://mms.pinduoduo.com/",
        }
        params = {"page": page, "pageSize": page_size}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    PDD_GOODS_LIST_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                    ssl=False,
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

            if not data.get("success"):
                return []

            result = data.get("result") or data.get("data") or {}
            goods = result.get("list") or result.get("goods") or []
            return goods

        except Exception as e:
            logger.error("获取商品列表异常: %s", e)
            return []

    async def sync_products(self, cookies: dict):
        """同步商品信息"""
        logger.info("开始同步店铺 %s 的商品信息...", self.shop_id)
        page = 1
        total = 0

        while True:
            products = await self.fetch_products(cookies, page=page)
            if not products:
                break
            total += len(products)
            if len(products) < 20:
                break
            page += 1
            await asyncio.sleep(1)

        logger.info("店铺 %s 商品同步完成，共 %d 件", self.shop_id, total)
