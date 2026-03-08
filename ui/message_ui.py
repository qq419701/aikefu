# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QScrollArea, QFrame, QSizePolicy, QSplitter, QPushButton,
)

BASE_STYLE = 'background-color: #ffffff; color: #222222;'
BUBBLE_MAX_WIDTH = 560

class MessageBubble(QFrame):
    def __init__(self, content, direction, msg_type='text', process_by='', timestamp='', parent=None):
        super().__init__(parent)
        self.setStyleSheet('background: transparent;')
        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(0)
        is_out = direction == 'out'

        inner = QVBoxLayout()
        inner.setSpacing(2)
        inner.setContentsMargins(0, 0, 0, 0)

        # 判断是否图片消息
        is_image = (msg_type == 'image' or
                    (content.startswith('https://chat-img.') and content.endswith(('.jpg','.jpeg','.png','.webp'))))

        if is_image and not is_out:
            # 图片气泡：点击可打开
            img_label = QLabel()
            img_label.setFixedSize(200, 150)
            img_label.setStyleSheet('background:#e0e0e0;border-radius:6px;color:#666;')
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setText('🖼️ 图片\n(点击查看)')
            img_label.setCursor(Qt.CursorShape.PointingHandCursor)
            _url = content
            img_label.mousePressEvent = lambda e, u=_url: QDesktopServices.openUrl(QUrl(u))
            inner.addWidget(img_label)
        else:
            text = QLabel(content)
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            if is_out:
                text.setStyleSheet('background:#1890ff;color:white;border-radius:8px;padding:8px 12px;')
            else:
                text.setStyleSheet('background:#f0f0f0;color:#222;border-radius:8px;padding:8px 12px;')
            inner.addWidget(text)

        # 时间戳
        if timestamp:
            ts = QLabel(str(timestamp))
            ts.setStyleSheet('color:#bbb;font-size:9px;background:transparent;')
            ts.setAlignment(Qt.AlignmentFlag.AlignRight if is_out else Qt.AlignmentFlag.AlignLeft)
            inner.addWidget(ts)

        # 处理方式标签
        if process_by and is_out:
            tag_map = {'rule':'规则','knowledge':'知识库','ai':'AI','human':'人工'}
            tag = QLabel('[{}]'.format(tag_map.get(process_by, process_by)))
            tag.setStyleSheet('color:#999;font-size:10px;background:transparent;')
            tag.setAlignment(Qt.AlignmentFlag.AlignRight)
            inner.addWidget(tag)

        if is_out:
            outer.addStretch(1)
            outer.addLayout(inner)
        else:
            outer.addLayout(inner)
            outer.addStretch(1)


class ConversationItem(QListWidgetItem):
    def __init__(self, shop_id, buyer_id, buyer_name, unread=0):
        super().__init__()
        self.shop_id = shop_id
        self.buyer_id = buyer_id
        self.buyer_name = buyer_name
        self.unread = unread
        self._update_text()

    def _update_text(self):
        name = self.buyer_name or self.buyer_id
        badge = ' {}🔴'.format(self.unread) if self.unread > 0 else ''
        self.setText('{}{}'.format(name, badge))

    def add_unread(self):
        self.unread += 1
        self._update_text()

    def clear_unread(self):
        self.unread = 0
        self._update_text()


class OrderInfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet('background:#f8f9fa;border:1px solid #e0e0e0;border-radius:6px;')
        self.setMaximumHeight(90)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)
        title = QLabel('📦 买家最近订单')
        title.setStyleSheet('color:#333;font-weight:bold;font-size:11px;background:transparent;')
        layout.addWidget(title)
        self.order_label = QLabel('暂无订单信息')
        self.order_label.setStyleSheet('color:#666;font-size:11px;background:transparent;')
        self.order_label.setWordWrap(True)
        layout.addWidget(self.order_label)

    def set_order(self, order_text):
        self.order_label.setText(order_text)


class MessagePage(QWidget):
    def __init__(self, db_client=None, parent=None):
        super().__init__(parent)
        self.db_client = db_client
        self._conversations = {}
        self._current_buyer = ''
        self._current_shop = 0
        self.setStyleSheet(BASE_STYLE)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧会话列表（固定宽度）
        left = QWidget()
        left.setStyleSheet('background:#f5f5f5;')
        left.setFixedWidth(200)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 8, 6, 8)
        ll.setSpacing(6)

        top_row = QHBoxLayout()
        title = QLabel('💬 会话')
        title.setStyleSheet('color:#222;font-size:13px;font-weight:bold;')
        top_row.addWidget(title)
        top_row.addStretch()
        clear_btn = QPushButton('清空')
        clear_btn.setFixedSize(36, 22)
        clear_btn.setStyleSheet('font-size:10px;color:#666;background:#e0e0e0;border-radius:3px;border:none;')
        clear_btn.clicked.connect(self._clear_all)
        top_row.addWidget(clear_btn)
        ll.addLayout(top_row)

        self.conversation_list = QListWidget()
        self.conversation_list.setStyleSheet(
            'QListWidget{background:#f5f5f5;border:none;color:#222;}'
            'QListWidget::item{padding:8px 4px;border-bottom:1px solid #e0e0e0;}'
            'QListWidget::item:selected{background:#1890ff;color:white;}'
            'QListWidget::item:hover{background:#e6f0ff;}'
        )
        self.conversation_list.currentItemChanged.connect(self._on_conversation_selected)
        ll.addWidget(self.conversation_list)

        # 右侧消息区（自适应剩余宽度）
        right = QWidget()
        right.setStyleSheet('background:#ffffff;')
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(6)

        self.buyer_info_label = QLabel('请选择左侧会话')
        self.buyer_info_label.setStyleSheet(
            'color:#222;font-size:14px;font-weight:bold;padding:4px;border-bottom:1px solid #e0e0e0;')
        rl.addWidget(self.buyer_info_label)

        self.order_widget = OrderInfoWidget()
        rl.addWidget(self.order_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet('QScrollArea{border:none;background:#ffffff;}')

        self.message_container = QWidget()
        self.message_container.setStyleSheet('background:#ffffff;')
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.message_layout.setSpacing(6)
        self.message_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_area.setWidget(self.message_container)
        rl.addWidget(self.scroll_area)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([200, 800])
        splitter.setCollapsible(0, False)
        layout.addWidget(splitter)

    def set_db_client(self, db_client):
        self.db_client = db_client

    def add_message(self, shop_id, msg):
        buyer_id = msg.get('buyer_id', '')
        buyer_name = msg.get('buyer_name', '') or buyer_id
        if not buyer_id or buyer_id in ('4', '0', ''):
            return
        content = msg.get('content', '')
        if not content:
            return
        key = '{}_{}'.format(shop_id, buyer_id)
        if key not in self._conversations:
            item = ConversationItem(shop_id, buyer_id, buyer_name)
            self.conversation_list.insertItem(0, item)
            self._conversations[key] = item
        else:
            item = self._conversations[key]
            row = self.conversation_list.row(item)
            self.conversation_list.takeItem(row)
            self.conversation_list.insertItem(0, item)
        if self._current_buyer == buyer_id and self._current_shop == shop_id:
            self._append_bubble(msg)
        else:
            item.add_unread()

    def _on_conversation_selected(self, current, _prev):
        if not isinstance(current, ConversationItem):
            return
        self._current_buyer = current.buyer_id
        self._current_shop = current.shop_id
        current.clear_unread()
        self.buyer_info_label.setText('👤 {}  (ID: {})'.format(
            current.buyer_name or current.buyer_id, current.buyer_id))
        self._load_orders(current.buyer_id)
        self._load_messages()

    def _load_orders(self, buyer_id):
        if not self.db_client:
            self.order_widget.set_order('暂无订单信息')
            return
        try:
            orders = self.db_client.get_buyer_orders(self._current_shop, buyer_id, limit=2)
            if not orders:
                self.order_widget.set_order('该买家暂无订单记录')
                return
            lines = []
            for o in orders:
                oid = str(o.get('order_id',''))[:18]
                name = str(o.get('goods_name',''))[:18]
                status = o.get('order_status_text','')
                amt = o.get('pay_amount_yuan','')
                lines.append('• {} | {} | {} {}'.format(oid, name, amt, status).strip())
            self.order_widget.set_order('\n'.join(lines))
        except Exception:
            self.order_widget.set_order('订单加载失败')

    def _load_messages(self):
        self._clear_messages()
        if not self.db_client or not self._current_buyer:
            return
        seen = set()
        try:
            messages = self.db_client.get_recent_messages(self._current_shop, limit=100)
            for msg in messages:
                if msg.get('buyer_id') == self._current_buyer:
                    key = '{}|{}|{}'.format(
                        msg.get('content',''), msg.get('direction',''),
                        str(msg.get('created_at',''))[:16])
                    if key in seen:
                        continue
                    seen.add(key)
                    self._append_bubble(msg)
        except Exception:
            pass
        self._scroll_to_bottom()

    def _append_bubble(self, msg):
        content = msg.get('content','')
        if not content:
            return
        direction = msg.get('direction','in')
        msg_type = msg.get('msg_type','text')
        process_by = msg.get('process_by','')
        ts = msg.get('created_at','')
        bubble = MessageBubble(content, direction, msg_type, process_by, str(ts)[:16] if ts else '')
        self.message_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def _clear_messages(self):
        while self.message_layout.count():
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_all(self):
        self.conversation_list.clear()
        self._conversations.clear()
        self._current_buyer = ''
        self._current_shop = 0
        self._clear_messages()
        self.buyer_info_label.setText('请选择左侧会话')
        self.order_widget.set_order('暂无订单信息')

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
