# -*- coding: utf-8 -*-
"""
渠道基类
定义所有采集渠道的通用接口
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class BaseChannel(ABC):
    """采集渠道基类"""

    def __init__(self, shop_id: int, shop_info: dict):
        self.shop_id = shop_id
        self.shop_info = shop_info
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """设置收到新消息时的回调函数"""
        self._message_callback = callback

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接，返回是否成功"""

    @abstractmethod
    async def disconnect(self):
        """断开连接"""

    @abstractmethod
    async def run(self):
        """主运行循环（阻塞）"""

    async def start(self):
        """在后台任务中启动渠道"""
        if self.is_running:
            logger.warning("渠道 %s 已在运行", self.shop_id)
            return
        self.is_running = True
        self._task = asyncio.create_task(self.run_with_reconnect())

    async def stop(self):
        """停止渠道"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.disconnect()
        logger.info("渠道 %s 已停止", self.shop_id)

    async def run_with_reconnect(self):
        """带自动重连的运行循环（指数退避，最多重试5次）"""
        retry_count = 0
        max_retries = 5
        base_delay = 5

        while self.is_running and retry_count <= max_retries:
            try:
                connected = await self.connect()
                if connected:
                    retry_count = 0
                    await self.run()
                else:
                    logger.error("连接失败，店铺ID: %s", self.shop_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("渠道运行异常: %s", e, exc_info=True)

            if not self.is_running:
                break

            retry_count += 1
            delay = base_delay * (2 ** (retry_count - 1))
            logger.info(
                "第%d次重连，等待%d秒... (店铺: %s)",
                retry_count, delay, self.shop_id,
            )
            await asyncio.sleep(delay)

        if retry_count > max_retries:
            logger.error("店铺 %s 超过最大重试次数，停止采集", self.shop_id)
        self.is_running = False
