# -*- coding: utf-8 -*-
"""
首次运行配置界面 - 配置MySQL连接信息
"""
import json

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QWidget,
)

import config as cfg
from core.encrypt import encrypt_password
from core.db_client import DBClient


class ConnectionTestThread(QThread):
    """后台线程测试数据库连接"""
    result = pyqtSignal(bool, str)

    def __init__(self, host, port, database, user, password):
        super().__init__()
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

    def run(self):
        try:
            client = DBClient(self.host, self.port, self.database, self.user, self.password)
            ok = client.test_connection()
            if ok:
                self.result.emit(True, "连接成功！")
            else:
                self.result.emit(False, "连接失败，请检查配置")
        except Exception as e:
            self.result.emit(False, f"连接失败: {e}")


class SetupDialog(QDialog):
    """首次运行配置弹窗 - 填写MySQL连接信息"""

    setup_done = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("爱客服采集客户端 - 初始配置")
        self.setFixedSize(460, 400)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self._test_thread = None
        self._init_ui()
        self._load_existing()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        title = QLabel("配置MySQL数据库连接")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        desc = QLabel(
            "请填写 aikefu 服务器的MySQL数据库连接信息。\n"
            "密码将加密存储在本地配置文件中。"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)

        self.host_edit = QLineEdit(cfg.MYSQL_CONFIG["host"])
        self.port_edit = QLineEdit(str(cfg.MYSQL_CONFIG["port"]))
        self.database_edit = QLineEdit(cfg.MYSQL_CONFIG["database"])
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("数据库用户名")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("数据库密码")
        self.server_url_edit = QLineEdit(cfg.AIKEFU_SERVER)
        self.server_url_edit.setPlaceholderText("http://8.145.43.255:6000")

        form.addRow("MySQL 主机:", self.host_edit)
        form.addRow("MySQL 端口:", self.port_edit)
        form.addRow("数据库名:", self.database_edit)
        form.addRow("用户名:", self.user_edit)
        form.addRow("密码:", self.password_edit)
        form.addRow("服务器地址:", self.server_url_edit)

        layout.addLayout(form)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.save_btn = QPushButton("保存并开始")
        self.save_btn.setDefault(True)

        self.test_btn.clicked.connect(self._test_connection)
        self.save_btn.clicked.connect(self._save_and_accept)

        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _load_existing(self):
        """加载已有配置"""
        existing = cfg.load_config()
        mysql = existing.get("mysql", {})
        if mysql.get("host"):
            self.host_edit.setText(mysql["host"])
        if mysql.get("port"):
            self.port_edit.setText(str(mysql["port"]))
        if mysql.get("database"):
            self.database_edit.setText(mysql["database"])
        if mysql.get("user"):
            self.user_edit.setText(mysql["user"])
        if existing.get("server_url"):
            self.server_url_edit.setText(existing["server_url"])

    def _get_form_data(self) -> dict:
        return {
            "host": self.host_edit.text().strip(),
            "port": int(self.port_edit.text().strip() or "3306"),
            "database": self.database_edit.text().strip(),
            "user": self.user_edit.text().strip(),
            "password": self.password_edit.text(),
        }

    def _test_connection(self):
        """测试数据库连接"""
        data = self._get_form_data()
        if not data["user"]:
            self._set_status("请填写用户名", "red")
            return

        self.test_btn.setEnabled(False)
        self._set_status("连接中...", "blue")

        self._test_thread = ConnectionTestThread(
            data["host"], data["port"], data["database"],
            data["user"], data["password"]
        )
        self._test_thread.result.connect(self._on_test_result)
        self._test_thread.start()

    def _on_test_result(self, success: bool, message: str):
        self.test_btn.setEnabled(True)
        color = "green" if success else "red"
        self._set_status(message, color)

    def _set_status(self, text: str, color: str = "black"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def _save_and_accept(self):
        """保存配置并关闭对话框"""
        data = self._get_form_data()
        if not data["user"]:
            QMessageBox.warning(self, "提示", "请填写数据库用户名")
            return

        # 加密密码
        try:
            enc_password = encrypt_password(data["password"]) if data["password"] else ""
        except Exception:
            enc_password = ""

        config_data = cfg.load_config()
        config_data["mysql"] = {
            "host": data["host"],
            "port": data["port"],
            "database": data["database"],
            "user": data["user"],
            "password_enc": enc_password,
        }
        config_data["server_url"] = self.server_url_edit.text().strip() or cfg.AIKEFU_SERVER

        if cfg.save_config(config_data):
            self.setup_done.emit()
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存配置失败，请检查磁盘空间")
