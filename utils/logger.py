# -*- coding: utf-8 -*-
"""
日志工具模块
"""
import logging
import logging.handlers
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.expanduser("~"), ".aikefu-client", "logs")


def setup_logger(name: str = "aikefu", level: int = logging.INFO) -> logging.Logger:
    """
    初始化日志系统。
    日志同时输出到控制台和按日期轮转的文件。
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（按天轮转，保留30天）
    log_file = os.path.join(LOG_DIR, "aikefu-client.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """获取模块级别的日志器"""
    return logging.getLogger(f"aikefu.{module_name}")
