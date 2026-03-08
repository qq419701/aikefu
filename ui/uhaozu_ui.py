# -*- coding: utf-8 -*-
"""
U号租专区页面
包含：账号管理、自动换号、自动选号、编号自动下单（预留）四个 Tab
"""
import asyncio
import logging
import uuid
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QMessageBox, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QCheckBox, QSpinBox, QDoubleSpinBox, QSizePolicy, QFrame,
)

import config as cfg

logger = logging.getLogger(__name__)

BASE_STYLE = '''
QWidget { background-color: #ffffff; color: #222222; }
QGroupBox {
    background-color: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    margin-top: 8px;
    color: #222;
    font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #222; }
QLineEdit {
    background: #fff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 4px 8px;
    color: #222;
}
QLineEdit:focus { border: 1px solid #1890ff; }
QPushButton {
    background: #1890ff;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
}
QPushButton:hover { background: #40a9ff; }
QPushButton:pressed { background: #096dd9; }
QPushButton.danger {
    background: #ff4d4f;
}
QPushButton.danger:hover { background: #ff7875; }
QCheckBox { color: #222; }
QLabel { color: #222; }
QTableWidget {
    border: 1px solid #e0e0e0;
    gridline-color: #f0f0f0;
    background: #fff;
}
QHeaderView::section {
    background-color: #fafafa;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    padding: 4px 8px;
    font-weight: bold;
}
QTabWidget::pane { border: 1px solid #e0e0e0; }
QTabBar::tab {
    background: #f5f5f5;
    border: 1px solid #e0e0e0;
    padding: 6px 16px;
    min-width: 80px;
}
QTabBar::tab:selected { background: #fff; border-bottom: none; color: #1890ff; }
'''


# ─── Worker thread for async automation ───────────────────────────────────────

class UHaozuWorker(QThread):
    """在独立线程中运行 U号租自动化操作"""

    result_ready = pyqtSignal(object)   # 操作完成，结果对象
    error_occurred = pyqtSignal(str)    # 发生错误

    def __init__(self, coro_factory, parent=None):
        """
        :param coro_factory: 无参数可调用对象，返回 coroutine
        """
        super().__init__(parent)
        self._coro_factory = coro_factory

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._coro_factory())
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()


# ─── Add Account Dialog ────────────────────────────────────────────────────────

class AddAccountDialog(QDialog):
    """添加/编辑 U号租账号的弹窗"""

    def __init__(self, parent=None, account: dict = None):
        super().__init__(parent)
        self.setWindowTitle("添加账号" if account is None else "编辑账号")
        self.setFixedSize(360, 200)
        self.setStyleSheet(BASE_STYLE)
        self._account = account or {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入U号租账号")
        self.username_edit.setText(self._account.get("username", ""))

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("请输入密码（留空则不修改）" if self._account else "请输入密码")

        form.addRow("账号:", self.username_edit)
        form.addRow("密码:", self.password_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background:#f5f5f5;color:#333;border:1px solid #d0d0d0;")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        return {
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
        }


# ─── Account Management Tab ───────────────────────────────────────────────────

class AccountTab(QWidget):
    """账号管理 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("👤 账号管理")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        # 操作按钮行
        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ 添加账号")
        add_btn.clicked.connect(self._add_account)
        del_btn = QPushButton("🗑 删除")
        del_btn.setStyleSheet("background:#ff4d4f;color:white;border:none;border-radius:4px;padding:6px 16px;")
        del_btn.clicked.connect(self._delete_account)
        default_btn = QPushButton("⭐ 设为默认")
        default_btn.clicked.connect(self._set_default)
        check_btn = QPushButton("🔍 检测登录状态")
        check_btn.clicked.connect(self._check_login)
        balance_btn = QPushButton("💰 刷新余额")
        balance_btn.clicked.connect(self._refresh_balance)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(default_btn)
        btn_row.addWidget(check_btn)
        btn_row.addWidget(balance_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 账号列表表格
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["账号", "状态", "余额", "默认", "ID", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnHidden(4, True)  # 隐藏 ID 列
        self.table.setColumnHidden(5, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(self.status_label)

    def _load_accounts(self):
        accounts = cfg.get_uhaozu_accounts()
        self.table.setRowCount(len(accounts))
        for row, acc in enumerate(accounts):
            self.table.setItem(row, 0, QTableWidgetItem(acc.get("username", "")))
            self.table.setItem(row, 1, QTableWidgetItem("—"))
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            self.table.setItem(row, 3, QTableWidgetItem("✓" if acc.get("is_default") else ""))
            self.table.setItem(row, 4, QTableWidgetItem(acc.get("id", "")))

    def _get_selected_row(self) -> int:
        rows = self.table.selectedItems()
        if not rows:
            return -1
        return rows[0].row()

    def _add_account(self):
        dlg = AddAccountDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        if not data["username"] or not data["password"]:
            QMessageBox.warning(self, "提示", "账号和密码不能为空")
            return

        accounts = cfg.get_uhaozu_accounts()
        new_acc = {
            "id": str(uuid.uuid4()),
            "username": data["username"],
            "password": data["password"],
            # 若当前无账号，则自动将第一个账号设为默认账号
            "is_default": len(accounts) == 0,
            "cookies": {},
        }
        accounts.append(new_acc)
        cfg.save_uhaozu_accounts(accounts)
        self._load_accounts()

    def _delete_account(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的账号")
            return
        acc_id = self.table.item(row, 4).text()
        accounts = cfg.get_uhaozu_accounts()
        accounts = [a for a in accounts if a.get("id") != acc_id]
        cfg.save_uhaozu_accounts(accounts)
        self._load_accounts()

    def _set_default(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要设为默认的账号")
            return
        acc_id = self.table.item(row, 4).text()
        accounts = cfg.get_uhaozu_accounts()
        for acc in accounts:
            acc["is_default"] = acc.get("id") == acc_id
        cfg.save_uhaozu_accounts(accounts)
        self._load_accounts()

    def _check_login(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择账号")
            return
        acc_id = self.table.item(row, 4).text()
        accounts = cfg.get_uhaozu_accounts()
        acc = next((a for a in accounts if a.get("id") == acc_id), None)
        if not acc:
            return

        self.status_label.setText("检测中...")
        self.table.setItem(row, 1, QTableWidgetItem("检测中..."))

        from automation.uhaozu import UHaozuAutomation

        automation = UHaozuAutomation(
            username=acc["username"],
            password=acc.get("password", ""),
            cookies=acc.get("cookies", {}),
        )

        async def _do():
            try:
                online = await automation.check_login_status()
                return online
            finally:
                await automation.close()

        worker = UHaozuWorker(_do, self)

        def on_result(online):
            status = "🟢 在线" if online else "🔴 离线"
            self.table.setItem(row, 1, QTableWidgetItem(status))
            self.status_label.setText(f"检测完成：{acc['username']} {status}")

        def on_error(msg):
            self.table.setItem(row, 1, QTableWidgetItem("❌ 异常"))
            self.status_label.setText(f"检测失败：{msg}")

        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        self._workers.append(worker)
        worker.start()

    def _refresh_balance(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择账号")
            return
        acc_id = self.table.item(row, 4).text()
        accounts = cfg.get_uhaozu_accounts()
        acc = next((a for a in accounts if a.get("id") == acc_id), None)
        if not acc:
            return

        self.status_label.setText("获取余额中...")
        self.table.setItem(row, 2, QTableWidgetItem("获取中..."))

        from automation.uhaozu import UHaozuAutomation

        automation = UHaozuAutomation(
            username=acc["username"],
            password=acc.get("password", ""),
            cookies=acc.get("cookies", {}),
        )

        async def _do():
            try:
                balance = await automation.get_balance()
                return balance
            finally:
                await automation.close()

        worker = UHaozuWorker(_do, self)

        def on_result(balance):
            self.table.setItem(row, 2, QTableWidgetItem(f"¥{balance:.2f}"))
            self.status_label.setText(f"余额刷新完成：¥{balance:.2f}")

        def on_error(msg):
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            self.status_label.setText(f"获取余额失败：{msg}")

        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        self._workers.append(worker)
        worker.start()


# ─── Exchange Tab ─────────────────────────────────────────────────────────────

class ExchangeTab(QWidget):
    """自动换号 Tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._settings = cfg.get_uhaozu_settings()
        self._build_ui()
        self._load_records()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🔄 自动换号")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        # 说明文字
        desc = QLabel(
            "💡 AI识别到买家换号请求后，自动获取买家订单号，"
            "到U号租一键换货页面完成换号。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#888;font-size:13px;")
        layout.addWidget(desc)

        # 设置区
        settings_group = QGroupBox("换号设置")
        settings_form = QFormLayout(settings_group)
        self.max_exchange_spin = QSpinBox()
        self.max_exchange_spin.setRange(1, 50)
        self.max_exchange_spin.setValue(self._settings.get("max_exchange_per_order", 5))
        settings_form.addRow("每订单最大换号次数:", self.max_exchange_spin)

        save_btn = QPushButton("💾 保存设置")
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save_settings)
        settings_form.addRow("", save_btn)
        layout.addWidget(settings_group)

        # 手动触发换号区
        manual_group = QGroupBox("手动触发换号")
        manual_layout = QHBoxLayout(manual_group)
        self.order_id_edit = QLineEdit()
        self.order_id_edit.setPlaceholderText("输入拼多多订单号")
        exchange_btn = QPushButton("🔄 立即换号")
        exchange_btn.clicked.connect(self._manual_exchange)
        manual_layout.addWidget(QLabel("订单号:"))
        manual_layout.addWidget(self.order_id_edit)
        manual_layout.addWidget(exchange_btn)
        layout.addWidget(manual_group)

        # 换号记录表格
        records_group = QGroupBox("换号记录")
        records_layout = QVBoxLayout(records_group)
        self.records_table = QTableWidget(0, 4)
        self.records_table.setHorizontalHeaderLabels(["订单号", "已换次数", "最后换号时间", "状态"])
        self.records_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.records_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.records_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.records_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.records_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        records_layout.addWidget(self.records_table)
        layout.addWidget(records_group)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(self.status_label)

    def _load_records(self):
        # 从配置加载换号记录（简易实现）
        settings = cfg.get_uhaozu_settings()
        records = settings.get("exchange_records", [])
        self.records_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self.records_table.setItem(row, 0, QTableWidgetItem(rec.get("order_id", "")))
            self.records_table.setItem(row, 1, QTableWidgetItem(str(rec.get("count", 0))))
            self.records_table.setItem(row, 2, QTableWidgetItem(rec.get("last_time", "")))
            self.records_table.setItem(row, 3, QTableWidgetItem(rec.get("status", "")))

    def _save_settings(self):
        settings = cfg.get_uhaozu_settings()
        settings["max_exchange_per_order"] = self.max_exchange_spin.value()
        if cfg.save_uhaozu_settings(settings):
            QMessageBox.information(self, "成功", "设置已保存")
        else:
            QMessageBox.critical(self, "错误", "保存失败")

    def _manual_exchange(self):
        order_id = self.order_id_edit.text().strip()
        if not order_id:
            QMessageBox.warning(self, "提示", "请输入拼多多订单号")
            return

        acc = cfg.get_default_uhaozu_account()
        if not acc:
            QMessageBox.warning(self, "提示", "请先在账号管理中添加并设置默认账号")
            return

        self.status_label.setText(f"换号中，订单号：{order_id}...")

        from automation.uhaozu import UHaozuAutomation

        automation = UHaozuAutomation(
            username=acc["username"],
            password=acc.get("password", ""),
            cookies=acc.get("cookies", {}),
        )

        async def _do():
            try:
                result = await automation.exchange_number(order_id)
                return result
            finally:
                await automation.close()

        worker = UHaozuWorker(_do, self)

        def on_result(result):
            success = result.get("success", False)
            msg = result.get("message", "")
            new_acc = result.get("new_account", "")
            self.status_label.setText(
                f"{'✅ 换号成功' if success else '❌ 换号失败'}：{msg}"
            )
            # 写入记录
            settings = cfg.get_uhaozu_settings()
            records = settings.setdefault("exchange_records", [])
            existing = next((r for r in records if r.get("order_id") == order_id), None)
            if existing:
                existing["count"] = existing.get("count", 0) + 1
                existing["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                existing["status"] = "成功" if success else "失败"
            else:
                records.insert(0, {
                    "order_id": order_id,
                    "count": 1,
                    "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "成功" if success else "失败",
                })
            cfg.save_uhaozu_settings(settings)
            self._load_records()
            if success:
                QMessageBox.information(self, "换号成功", f"新账号：{new_acc or '（请查看页面）'}")
            else:
                QMessageBox.warning(self, "换号失败", msg)

        def on_error(msg):
            self.status_label.setText(f"❌ 换号异常：{msg}")
            QMessageBox.critical(self, "错误", msg)

        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        self._workers.append(worker)
        worker.start()


# ─── Price Markup Rule Row ─────────────────────────────────────────────────────

class MarkupRuleRow(QWidget):
    """加价规则中的一行"""

    delete_requested = pyqtSignal(object)

    def __init__(self, rule: dict = None, parent=None):
        super().__init__(parent)
        rule = rule or {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0, 9999)
        self.min_spin.setDecimals(2)
        self.min_spin.setValue(rule.get("min", 0.0))

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(0, 9999)
        self.max_spin.setDecimals(2)
        self.max_spin.setValue(rule.get("max", 0.0))

        self.markup_spin = QDoubleSpinBox()
        self.markup_spin.setRange(0, 9999)
        self.markup_spin.setDecimals(2)
        self.markup_spin.setValue(rule.get("markup", 0.0))

        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(32)
        del_btn.setStyleSheet("background:#ff4d4f;color:white;border:none;border-radius:4px;")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        layout.addWidget(QLabel("价格下限:"))
        layout.addWidget(self.min_spin)
        layout.addWidget(QLabel("上限:"))
        layout.addWidget(self.max_spin)
        layout.addWidget(QLabel("加价(元):"))
        layout.addWidget(self.markup_spin)
        layout.addWidget(del_btn)
        layout.addStretch()

    def get_rule(self) -> dict:
        return {
            "min": self.min_spin.value(),
            "max": self.max_spin.value(),
            "markup": self.markup_spin.value(),
        }


# ─── Game Config Widget ────────────────────────────────────────────────────────

class GameConfigWidget(QGroupBox):
    """单个游戏的配置展开面板"""

    FILTER_LABELS = [
        ("no_deposit", "无押金"),
        ("time_rental_bonus", "时租满送"),
        ("login_tool", "登号器"),
        ("anti_addiction", "防沉迷"),
        ("non_cloud", "非云"),
        ("high_login_rate", "上号率高"),
        ("no_friend_add", "禁言/不能加好友"),
        ("allow_ranked", "排位赛允许"),
    ]

    def __init__(self, game_name: str, game_cfg: dict = None, parent=None):
        super().__init__(game_name, parent)
        self.game_name = game_name
        game_cfg = game_cfg or {}
        self.setCheckable(True)
        self.setChecked(False)
        self._build_ui(game_cfg)

    def _build_ui(self, game_cfg: dict):
        layout = QVBoxLayout(self)

        # 平台
        platforms_row = QHBoxLayout()
        platforms_row.addWidget(QLabel("平台:"))
        self.android_cb = QCheckBox("安卓")
        self.ios_cb = QCheckBox("苹果")
        platforms = game_cfg.get("platforms", ["安卓", "苹果"])
        self.android_cb.setChecked("安卓" in platforms)
        self.ios_cb.setChecked("苹果" in platforms)
        platforms_row.addWidget(self.android_cb)
        platforms_row.addWidget(self.ios_cb)
        platforms_row.addStretch()
        layout.addLayout(platforms_row)

        # 登录方式
        login_row = QHBoxLayout()
        login_row.addWidget(QLabel("登录方式:"))
        self.wechat_cb = QCheckBox("微信")
        self.qq_cb = QCheckBox("QQ")
        login_methods = game_cfg.get("login_methods", ["微信", "QQ"])
        self.wechat_cb.setChecked("微信" in login_methods)
        self.qq_cb.setChecked("QQ" in login_methods)
        login_row.addWidget(self.wechat_cb)
        login_row.addWidget(self.qq_cb)
        login_row.addStretch()
        layout.addLayout(login_row)

        # 筛选项
        filters = game_cfg.get("filters", {})
        filter_defaults = {
            "no_deposit": True, "time_rental_bonus": True, "login_tool": True,
            "anti_addiction": True, "non_cloud": True, "high_login_rate": True,
            "no_friend_add": False, "allow_ranked": True,
        }
        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("筛选项:"))
        self._filter_cbs = {}
        filter_widget = QWidget()
        filter_grid = QHBoxLayout(filter_widget)
        filter_grid.setContentsMargins(0, 0, 0, 0)
        for key, label in self.FILTER_LABELS:
            cb = QCheckBox(label)
            cb.setChecked(filters.get(key, filter_defaults.get(key, False)))
            self._filter_cbs[key] = cb
            filter_grid.addWidget(cb)
        filter_grid.addStretch()
        filters_row.addWidget(filter_widget)
        layout.addLayout(filters_row)

    def get_config(self) -> dict:
        platforms = []
        if self.android_cb.isChecked():
            platforms.append("安卓")
        if self.ios_cb.isChecked():
            platforms.append("苹果")

        login_methods = []
        if self.wechat_cb.isChecked():
            login_methods.append("微信")
        if self.qq_cb.isChecked():
            login_methods.append("QQ")

        filters = {key: cb.isChecked() for key, cb in self._filter_cbs.items()}

        return {
            "platforms": platforms,
            "login_methods": login_methods,
            "filters": filters,
        }


# ─── Auto Select Tab ──────────────────────────────────────────────────────────

class AutoSelectTab(QWidget):
    """自动选号 Tab"""

    DEFAULT_GAMES = ["王者荣耀", "火影忍者", "和平精英"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._settings = cfg.get_uhaozu_settings()
        self._markup_rows: list[MarkupRuleRow] = []
        self._game_widgets: dict[str, GameConfigWidget] = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#ffffff;}")

        content = QWidget()
        content.setStyleSheet("background:#ffffff;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("🎯 自动选号")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        # ── 加价规则 ──
        markup_group = QGroupBox("加价规则设置")
        markup_layout = QVBoxLayout(markup_group)

        add_rule_btn = QPushButton("➕ 新增规则")
        add_rule_btn.setFixedWidth(120)
        add_rule_btn.clicked.connect(self._add_markup_rule)
        markup_layout.addWidget(add_rule_btn)

        self.markup_rules_container = QVBoxLayout()
        markup_layout.addLayout(self.markup_rules_container)

        # 载入已有规则
        existing_rules = self._settings.get("price_markup_rules", [
            {"min": 0.1, "max": 0.5, "markup": 0.5},
            {"min": 0.5, "max": 1.0, "markup": 1.0},
            {"min": 1.0, "max": 10.0, "markup": 2.0},
        ])
        for rule in existing_rules:
            self._append_markup_row(rule)

        layout.addWidget(markup_group)

        # ── 游戏筛选配置 ──
        game_group = QGroupBox("游戏筛选默认配置")
        game_layout = QVBoxLayout(game_group)

        # 新增游戏按钮
        add_game_row = QHBoxLayout()
        self.new_game_edit = QLineEdit()
        self.new_game_edit.setPlaceholderText("输入游戏名称")
        self.new_game_edit.setFixedWidth(200)
        add_game_btn = QPushButton("➕ 新增游戏")
        add_game_btn.setFixedWidth(120)
        add_game_btn.clicked.connect(self._add_game)
        add_game_row.addWidget(QLabel("新增游戏:"))
        add_game_row.addWidget(self.new_game_edit)
        add_game_row.addWidget(add_game_btn)
        add_game_row.addStretch()
        game_layout.addLayout(add_game_row)

        self.game_configs_layout = QVBoxLayout()
        game_layout.addLayout(self.game_configs_layout)

        # 载入已有游戏配置
        existing_games = self._settings.get("game_configs", {})
        all_games = list(existing_games.keys())
        for g in self.DEFAULT_GAMES:
            if g not in all_games:
                all_games.append(g)
        for game in all_games:
            self._append_game_widget(game, existing_games.get(game, {}))

        layout.addWidget(game_group)

        # 保存按钮
        save_btn = QPushButton("💾 保存选号设置")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _append_markup_row(self, rule: dict = None):
        row_widget = MarkupRuleRow(rule, self)
        row_widget.delete_requested.connect(self._delete_markup_row)
        self.markup_rules_container.addWidget(row_widget)
        self._markup_rows.append(row_widget)

    def _add_markup_rule(self):
        self._append_markup_row({"min": 0.0, "max": 0.0, "markup": 0.0})

    def _delete_markup_row(self, row_widget):
        self.markup_rules_container.removeWidget(row_widget)
        self._markup_rows.remove(row_widget)
        row_widget.deleteLater()

    def _append_game_widget(self, game_name: str, game_cfg: dict):
        widget = GameConfigWidget(game_name, game_cfg, self)
        self.game_configs_layout.addWidget(widget)
        self._game_widgets[game_name] = widget

    def _add_game(self):
        name = self.new_game_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入游戏名称")
            return
        if name in self._game_widgets:
            QMessageBox.warning(self, "提示", f"游戏「{name}」已存在")
            return
        self._append_game_widget(name, {})
        self.new_game_edit.clear()

    def _save_settings(self):
        settings = cfg.get_uhaozu_settings()
        settings["price_markup_rules"] = [r.get_rule() for r in self._markup_rows]
        settings["game_configs"] = {
            name: widget.get_config()
            for name, widget in self._game_widgets.items()
        }
        if cfg.save_uhaozu_settings(settings):
            QMessageBox.information(self, "成功", "选号设置已保存")
        else:
            QMessageBox.critical(self, "错误", "保存失败")


# ─── Placeholder Tab ──────────────────────────────────────────────────────────

class PlaceholderTab(QWidget):
    """编号自动下单 Tab（预留）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("🚧 编号自动下单功能开发中，敬请期待…")
        label.setStyleSheet("font-size:18px;color:#aaa;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


# ─── Main UHaozu Page ─────────────────────────────────────────────────────────

class UHaozuPage(QWidget):
    """U号租专区主页面"""

    def __init__(self, db_client=None, parent=None):
        super().__init__(parent)
        self.db_client = db_client
        self.setStyleSheet(BASE_STYLE)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 页面标题区
        header = QWidget()
        header.setStyleSheet("background:#1890ff;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        title_label = QLabel("🎮  U号租专区")
        title_label.setStyleSheet("font-size:20px;font-weight:bold;color:#fff;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        subtitle = QLabel("b.uhaozu.com  商户端自动化")
        subtitle.setStyleSheet("color:rgba(255,255,255,0.8);font-size:13px;")
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        # Tab 切换
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(BASE_STYLE)

        self.account_tab = AccountTab(self)
        self.exchange_tab = ExchangeTab(self)
        self.select_tab = AutoSelectTab(self)
        self.placeholder_tab = PlaceholderTab(self)

        self.tabs.addTab(self.account_tab, "账号管理")
        self.tabs.addTab(self.exchange_tab, "自动换号")
        self.tabs.addTab(self.select_tab, "自动选号")
        self.tabs.addTab(self.placeholder_tab, "编号自动下单")

        layout.addWidget(self.tabs)
