# -*- coding: utf-8 -*-
import sys
import logging
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QGroupBox, QMessageBox, QCheckBox, QScrollArea,
)
import config as cfg
from core.encrypt import encrypt_password
from core.db_client import DBClient

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
QCheckBox { color: #222; }
QLabel { color: #222; }
'''

class SettingPage(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self, db_client=None, parent=None):
        super().__init__(parent)
        self.db_client = db_client
        self._test_thread = None
        self.setStyleSheet(BASE_STYLE)
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea{border:none;background:#ffffff;}')

        content = QWidget()
        content.setStyleSheet('background:#ffffff;')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel('⚙️ 设置')
        title.setStyleSheet('font-size:20px;font-weight:bold;color:#222;')
        layout.addWidget(title)

        # 服务器配置
        server_group = QGroupBox('aikefu 服务器配置')
        server_form = QFormLayout(server_group)
        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText('http://8.145.43.255:5000')
        server_form.addRow('服务器地址:', self.server_url_edit)
        layout.addWidget(server_group)

        # MySQL配置
        mysql_group = QGroupBox('MySQL 数据库配置')
        mysql_form = QFormLayout(mysql_group)
        self.mysql_host_edit = QLineEdit()
        self.mysql_port_edit = QLineEdit()
        self.mysql_db_edit = QLineEdit()
        self.mysql_user_edit = QLineEdit()
        self.mysql_pass_edit = QLineEdit()
        self.mysql_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.mysql_pass_edit.setPlaceholderText('留空表示不修改密码')
        mysql_form.addRow('主机:', self.mysql_host_edit)
        mysql_form.addRow('端口:', self.mysql_port_edit)
        mysql_form.addRow('数据库:', self.mysql_db_edit)
        mysql_form.addRow('用户名:', self.mysql_user_edit)
        mysql_form.addRow('密码:', self.mysql_pass_edit)

        test_btn = QPushButton('测试连接')
        test_btn.setFixedWidth(100)
        test_btn.clicked.connect(self._test_connection)
        self.mysql_test_label = QLabel('')
        self.mysql_test_label.setStyleSheet('color:#222;')
        test_row = QHBoxLayout()
        test_row.addWidget(test_btn)
        test_row.addWidget(self.mysql_test_label)
        test_row.addStretch()
        mysql_form.addRow('', test_row)
        layout.addWidget(mysql_group)

        # 通知配置
        notify_group = QGroupBox('通知设置')
        notify_form = QFormLayout(notify_group)
        self.notify_enabled = QCheckBox('启用桌面通知')
        self.notify_enabled.setChecked(True)
        notify_form.addRow('', self.notify_enabled)
        layout.addWidget(notify_group)

        # 开机自启
        startup_group = QGroupBox('开机启动')
        startup_form = QFormLayout(startup_group)
        self.startup_enabled = QCheckBox('开机时自动启动客户端')
        startup_form.addRow('', self.startup_enabled)
        layout.addWidget(startup_group)

        # 保存
        save_btn = QPushButton('💾  保存设置')
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _load_settings(self):
        current = cfg.load_config()
        self.server_url_edit.setText(current.get('server_url', cfg.AIKEFU_SERVER))
        mysql = current.get('mysql', {})
        self.mysql_host_edit.setText(mysql.get('host', cfg.MYSQL_CONFIG.get('host', '')))
        self.mysql_port_edit.setText(str(mysql.get('port', cfg.MYSQL_CONFIG.get('port', 3306))))
        self.mysql_db_edit.setText(mysql.get('database', cfg.MYSQL_CONFIG.get('database', '')))
        self.mysql_user_edit.setText(mysql.get('user', ''))
        self.notify_enabled.setChecked(current.get('notify_enabled', True))
        self.startup_enabled.setChecked(current.get('startup_enabled', False))

    def _test_connection(self):
        host = self.mysql_host_edit.text().strip()
        port = int(self.mysql_port_edit.text().strip() or '3306')
        database = self.mysql_db_edit.text().strip()
        user = self.mysql_user_edit.text().strip()
        password = self.mysql_pass_edit.text()
        if not password:
            saved = cfg.get_mysql_config()
            if saved:
                password = saved.get('password', '')
        self.mysql_test_label.setText('连接中...')

        class TestThread(QThread):
            done = pyqtSignal(bool, str)
            def __init__(self, h, p, d, u, pw):
                super().__init__()
                self._h,self._p,self._d,self._u,self._pw = h,p,d,u,pw
            def run(self):
                try:
                    c = DBClient(self._h,self._p,self._d,self._u,self._pw)
                    ok = c.test_connection()
                    self.done.emit(ok, '连接成功' if ok else '连接失败')
                except Exception as e:
                    self.done.emit(False, str(e))

        self._test_thread = TestThread(host, port, database, user, password)
        self._test_thread.done.connect(lambda ok, msg: self.mysql_test_label.setText(
            f"{'✅' if ok else '❌'} {msg}"
        ))
        self._test_thread.start()

    def _save_settings(self):
        current = cfg.load_config()
        current['server_url'] = self.server_url_edit.text().strip() or cfg.AIKEFU_SERVER
        mysql = current.get('mysql', {})
        mysql['host'] = self.mysql_host_edit.text().strip()
        mysql['port'] = int(self.mysql_port_edit.text().strip() or '3306')
        mysql['database'] = self.mysql_db_edit.text().strip()
        mysql['user'] = self.mysql_user_edit.text().strip()
        new_password = self.mysql_pass_edit.text()
        if new_password:
            try:
                mysql['password_enc'] = encrypt_password(new_password)
            except Exception:
                pass
        current['mysql'] = mysql
        current['notify_enabled'] = self.notify_enabled.isChecked()
        current['startup_enabled'] = self.startup_enabled.isChecked()
        if cfg.save_config(current):
            if self.startup_enabled.isChecked():
                self._setup_autostart()
            else:
                self._remove_autostart()
            QMessageBox.information(self, '成功', '设置已保存，重启后生效')
            self.settings_saved.emit()
        else:
            QMessageBox.critical(self, '错误', '保存失败')

    def _setup_autostart(self):
        if sys.platform != 'win32': return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'AiKeFuClient', 0, winreg.REG_SZ, sys.executable)
            winreg.CloseKey(key)
        except Exception as e:
            logger.warning('设置开机自启失败: %s', e)

    def _remove_autostart(self):
        if sys.platform != 'win32': return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
            try: winreg.DeleteValue(key, 'AiKeFuClient')
            except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.warning('取消开机自启失败: %s', e)
