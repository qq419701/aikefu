# -*- coding: utf-8 -*-
"""
主窗口 - FluentWindow
使用 PyQt6-Fluent-Widgets 实现现代化界面
"""
import logging
import sys

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu

try:
    from qfluentwidgets import (
        FluentWindow, NavigationItemPosition, FluentIcon,
        setTheme, Theme,
    )
    HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QMainWindow as FluentWindow
    HAS_FLUENT = False

from ui.dashboard_ui import DashboardPage
from ui.shop_ui import ShopPage
from ui.message_ui import MessagePage
from ui.setting_ui import SettingPage
from core.db_client import DBClient
from core.server_api import ServerAPI
import config as cfg

logger = logging.getLogger(__name__)


class ChannelWorker(QThread):
    """在独立线程中运行采集渠道的 asyncio 事件循环"""

    message_received = pyqtSignal(int, dict)  # shop_id, msg
    status_changed = pyqtSignal(int, bool)    # shop_id, is_running

    def __init__(self, shop_info: dict, db_client: DBClient, server_api: ServerAPI, parent=None):
        super().__init__(parent)
        self.shop_info = shop_info
        self.db_client = db_client
        self.server_api = server_api
        self._channel = None
        self._loop = None
        self._pdd_login = None

    def run(self):
        import asyncio
        from channel.pinduoduo.pdd_login import PddLogin
        from channel.pinduoduo.pdd_channel import PddChannel
        from channel.pinduoduo.pdd_sender import PddSender

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._start_channel())
        except Exception as e:
            logger.error("采集线程异常: %s", e)
        finally:
            self._loop.close()

    async def _start_channel(self):
        import asyncio
        from channel.pinduoduo.pdd_login import PddLogin
        from channel.pinduoduo.pdd_channel import PddChannel
        from channel.pinduoduo.pdd_sender import PddSender
        from channel.pinduoduo.pdd_order import PddOrderCollector

        shop_id = self.shop_info.get("shop_id")

        # 登录
        self._pdd_login = PddLogin(shop_id=shop_id, db_client=self.db_client)
        success = await self._pdd_login.login()
        if not success:
            logger.error("店铺 %s 登录失败", shop_id)
            self.status_changed.emit(shop_id, False)
            return

        # 创建发送器（使用cookies直接发送，不依赖浏览器page）
        sender = PddSender(cookies=self._pdd_login.cookies, shop_id=shop_id)

        # 创建 WebSocket 渠道
        self._channel = PddChannel(
            shop_id=shop_id,
            shop_info=self.shop_info,
            im_token=self._pdd_login.im_token,
            cookies=self._pdd_login.cookies,
            db_client=self.db_client,
            server_api=self.server_api,
            sender=sender,
        )

        def on_message(sid, msg):
            self.message_received.emit(sid, msg)

        self._channel.set_message_callback(on_message)
        self._channel.is_running = True

        self.status_changed.emit(shop_id, True)

        # 订单同步已禁用

        # 运行 WebSocket 采集（带自动重连）
        await self._channel.run_with_reconnect()
        self.status_changed.emit(shop_id, False)

    def stop_channel(self):
        """停止采集"""
        if self._channel and self._loop:
            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(self._channel.stop())
            )


class MainWindow(FluentWindow):
    """爱客服采集客户端主窗口"""

    def __init__(self):
        super().__init__()
        self.db_client: DBClient = None
        self.server_api: ServerAPI = None
        self._workers: dict = {}  # shop_id -> ChannelWorker

        self._init_db()
        self._init_ui()
        self._setup_tray()

    def _init_db(self):
        """初始化数据库连接"""
        mysql_cfg = cfg.get_mysql_config()
        if mysql_cfg:
            try:
                self.db_client = DBClient(
                    host=mysql_cfg["host"],
                    port=mysql_cfg["port"],
                    database=mysql_cfg["database"],
                    user=mysql_cfg["user"],
                    password=mysql_cfg["password"],
                )
                logger.info("数据库连接初始化完成")
            except Exception as e:
                logger.error("数据库初始化失败: %s", e)

        server_url = cfg.get_server_url()
        self.server_api = ServerAPI(base_url=server_url)

    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"{cfg.APP_NAME} v{cfg.APP_VERSION}")
        self.resize(1280, 800)

        # 创建页面
        self.dashboard_page = DashboardPage(db_client=self.db_client)
        self.shop_page = ShopPage(db_client=self.db_client)
        self.message_page = MessagePage(db_client=self.db_client)
        self.setting_page = SettingPage(db_client=self.db_client)

        # 连接信号
        self.shop_page.channel_start_requested.connect(self._start_shop)
        self.shop_page.channel_stop_requested.connect(self._stop_shop)
        self.setting_page.settings_saved.connect(self._on_settings_saved)

        if HAS_FLUENT:
            self._add_fluent_pages()
        else:
            self._add_basic_pages()

    def _add_fluent_pages(self):
        """使用 FluentWindow 添加导航页"""
        from qfluentwidgets import FluentIcon

        self.dashboard_page.setObjectName("dashboardPage")
        self.shop_page.setObjectName("shopPage")
        self.message_page.setObjectName("messagePage")
        self.setting_page.setObjectName("settingPage")

        self.addSubInterface(self.dashboard_page, FluentIcon.HOME, "首页")
        self.addSubInterface(self.shop_page, FluentIcon.SHOPPING_CART, "店铺管理")
        self.addSubInterface(self.message_page, FluentIcon.CHAT, "消息监控")
        self.addSubInterface(
            self.setting_page,
            FluentIcon.SETTING,
            "设置",
            NavigationItemPosition.BOTTOM,
        )

    def _add_basic_pages(self):
        """后备方案：使用标准 QMainWindow"""
        from PyQt6.QtWidgets import QTabWidget
        tabs = QTabWidget()
        tabs.addTab(self.dashboard_page, "首页")
        tabs.addTab(self.shop_page, "店铺管理")
        tabs.addTab(self.message_page, "消息监控")
        tabs.addTab(self.setting_page, "设置")
        self.setCentralWidget(tabs)

    def _setup_tray(self):
        """设置系统托盘图标"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip(cfg.APP_NAME)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示主界面")
        show_action.triggered.connect(self.show)
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    def _start_shop(self, shop_info: dict):
        """启动店铺采集"""
        shop_id = shop_info.get("shop_id")
        if not shop_id:
            return
        if shop_id in self._workers:
            logger.warning("店铺 %s 已在运行", shop_id)
            return

        if not self.db_client or not self.server_api:
            QMessageBox.warning(self, "提示", "请先完成数据库配置")
            return

        worker = ChannelWorker(
            shop_info=shop_info,
            db_client=self.db_client,
            server_api=self.server_api,
            parent=self,
        )
        worker.message_received.connect(self.message_page.add_message)
        worker.status_changed.connect(self._on_status_changed)
        self._workers[shop_id] = worker
        worker.start()

        logger.info("已启动店铺 %s 的采集线程", shop_id)

    def _stop_shop(self, shop_info: dict):
        """停止店铺采集"""
        shop_id = shop_info.get("shop_id")
        worker = self._workers.pop(shop_id, None)
        if worker:
            worker.stop_channel()
            worker.quit()
            worker.wait(5000)

    def _on_status_changed(self, shop_id: int, is_running: bool):
        """采集状态变化回调"""
        self.shop_page.set_shop_running(shop_id, is_running)
        self.dashboard_page.set_running_shops_count(
            sum(1 for w in self._workers.values() if w.isRunning())
        )
        if not is_running:
            self._workers.pop(shop_id, None)

    def _on_settings_saved(self):
        """设置保存后重新初始化连接"""
        self._init_db()
        self.shop_page.set_db_client(self.db_client)
        self.dashboard_page.set_db_client(self.db_client)
        self.message_page.set_db_client(self.db_client)

    def closeEvent(self, event):
        """最小化到系统托盘而非关闭"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            cfg.APP_NAME,
            "程序已最小化到系统托盘，双击图标可重新显示",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )


