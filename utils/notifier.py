# -*- coding: utf-8 -*-
"""
桌面通知工具
使用系统原生通知功能推送消息提醒
"""
import logging
import sys

logger = logging.getLogger(__name__)


def send_notification(title: str, message: str, icon_path: str = "") -> bool:
    """
    发送桌面通知。
    Windows 使用 win10toast 或 plyer，其他系统使用 plyer。
    """
    # 优先使用 plyer（跨平台）
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="爱客服采集客户端",
            app_icon=icon_path if icon_path else None,
            timeout=5,
        )
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug("plyer通知失败: %s", e)

    # Windows 后备方案
    if sys.platform == "win32":
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title,
                message,
                icon_path=icon_path if icon_path else None,
                duration=5,
                threaded=True,
            )
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.debug("win10toast通知失败: %s", e)

    logger.debug("桌面通知不可用: %s - %s", title, message)
    return False


class Notifier:
    """通知管理器（支持开关控制）"""

    def __init__(self):
        self._enabled = True
        self._icon_path = ""

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def set_icon(self, icon_path: str):
        self._icon_path = icon_path

    def notify(self, title: str, message: str) -> bool:
        if not self._enabled:
            return False
        return send_notification(title, message, self._icon_path)

    def notify_new_message(self, shop_name: str, buyer_name: str, content: str):
        """新消息通知"""
        self.notify(
            title=f"新消息 - {shop_name}",
            message=f"{buyer_name}: {content[:50]}",
        )

    def notify_needs_human(self, shop_name: str, buyer_name: str):
        """需要人工介入通知"""
        self.notify(
            title=f"⚠️ 需要人工处理 - {shop_name}",
            message=f"买家 {buyer_name} 需要人工客服介入",
        )
