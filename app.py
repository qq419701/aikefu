# -*- coding: utf-8 -*-
"""
爱客服采集客户端 - 主入口
"""
import sys
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

import config as cfg
from utils.logger import setup_logger


def main():
    # 初始化日志
    setup_logger("aikefu", logging.DEBUG)
    logger = logging.getLogger("aikefu")
    logger.info("爱客服采集客户端 v%s 启动", cfg.APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(cfg.APP_NAME)
    app.setApplicationVersion(cfg.APP_VERSION)
    app.setQuitOnLastWindowClosed(False)

    # 首次运行 - 显示配置向导
    if not cfg.is_configured():
        from ui.login_ui import SetupDialog
        dialog = SetupDialog()
        result = dialog.exec()
        if result != SetupDialog.DialogCode.Accepted:
            logger.info("用户取消配置，退出")
            sys.exit(0)

    # 启动主窗口
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
