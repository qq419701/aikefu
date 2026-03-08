# -*- coding: utf-8 -*-
"""
店铺管理界面
从MySQL shops表读取店铺列表，管理采集任务的启动/停止
"""
import asyncio
import logging

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QMessageBox, QSizePolicy,
)

import config as cfg

logger = logging.getLogger(__name__)


class ShopCard(QFrame):
    """单个店铺卡片组件"""

    start_requested = pyqtSignal(dict)
    stop_requested = pyqtSignal(dict)

    def __init__(self, shop_info: dict, parent=None):
        super().__init__(parent)
        self.shop_info = shop_info
        self.is_running = False
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 店铺名称
        name_label = QLabel(f"🏪 {self.shop_info.get('name', '未命名店铺')}")
        name_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(name_label)

        # 平台标签
        platform = self.shop_info.get("platform", "pdd")
        platform_text = {"pdd": "拼多多", "taobao": "淘宝", "jd": "京东"}.get(platform, platform)
        platform_label = QLabel(f"平台：{platform_text}")
        platform_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(platform_label)

        # 状态指示
        status_layout = QHBoxLayout()
        self.status_dot = QLabel("🔴")
        self.status_text = QLabel("已停止")
        self.status_text.setStyleSheet("color: #666; font-size: 12px;")
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # 统计信息
        self.stats_label = QLabel("今日消息：-")
        self.stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.stats_label)

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 启动采集")
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)

        self.start_btn.clicked.connect(lambda: self.start_requested.emit(self.shop_info))
        self.stop_btn.clicked.connect(lambda: self.stop_requested.emit(self.shop_info))

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

    def set_running(self, running: bool):
        self.is_running = running
        if running:
            self.status_dot.setText("🟢")
            self.status_text.setText("运行中")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_dot.setText("🔴")
            self.status_text.setText("已停止")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def set_today_count(self, count: int):
        self.stats_label.setText(f"今日消息：{count} 条")


class ShopPage(QWidget):
    """店铺管理页面"""

    channel_start_requested = pyqtSignal(dict)
    channel_stop_requested = pyqtSignal(dict)

    def __init__(self, db_client=None, parent=None):
        super().__init__(parent)
        self.db_client = db_client
        self._cards: dict = {}  # shop_id -> ShopCard
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 顶部工具栏
        top_layout = QHBoxLayout()
        title = QLabel("🏪 店铺管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        refresh_btn = QPushButton("🔄 刷新店铺列表")
        refresh_btn.clicked.connect(self.load_shops)
        top_layout.addWidget(refresh_btn)

        main_layout.addLayout(top_layout)

        hint = QLabel(
            "💡 提示：店铺在 aikefu 后台创建后，点击「刷新店铺列表」即可在此管理。"
        )
        hint.setStyleSheet("color: #888; font-size: 12px;")
        main_layout.addWidget(hint)

        # 店铺卡片滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.cards_container)
        main_layout.addWidget(scroll)

        # 初始加载
        if self.db_client:
            self.load_shops()

    def set_db_client(self, db_client):
        self.db_client = db_client
        self.load_shops()

    def load_shops(self):
        """从MySQL重新加载店铺列表"""
        if not self.db_client:
            return

        # 清空现有卡片
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        try:
            shops = self.db_client.get_shops()
        except Exception as e:
            logger.error("加载店铺列表失败: %s", e)
            return

        if not shops:
            no_shop = QLabel(
                f"暂无店铺。\n请先在 aikefu 后台（{cfg.get_server_url()}）添加店铺，\n然后点击上方「刷新店铺列表」。"
            )
            no_shop.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_shop.setStyleSheet("color: #999; font-size: 13px; margin: 40px;")
            self.cards_layout.addWidget(no_shop, 0, 0)
            return

        # 加载今日统计
        for i, shop in enumerate(shops):
            card = ShopCard(shop)
            card.start_requested.connect(self.channel_start_requested)
            card.stop_requested.connect(self.channel_stop_requested)

            # 加载今日消息数
            try:
                stats = self.db_client.get_today_stats(shop.get("shop_id"))
                card.set_today_count(stats.get("total", 0))
            except Exception:
                pass

            row, col = divmod(i, 3)
            self.cards_layout.addWidget(card, row, col)
            self._cards[shop.get("shop_id")] = card

    def set_shop_running(self, shop_id: int, running: bool):
        """更新店铺运行状态"""
        card = self._cards.get(shop_id)
        if card:
            card.set_running(running)
