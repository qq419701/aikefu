# -*- coding: utf-8 -*-
import logging
import json
from datetime import datetime
from typing import Optional
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

ORDER_STATUS_MAP = {
    'waitpay': '待付款', 'waitdeliver': '待发货', 'waitreceive': '已发货',
    'finish': '已完成', 'cancel': '已取消', 'refund': '退款中',
    '0': '待付款', '1': '待发货', '2': '已发货', '3': '已完成',
    '4': '已取消', '5': '退款中', '6': '已退款',
}

class DBClient:
    def __init__(self, host, port, database, user, password):
        url = 'mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8mb4'.format(user, password, host, port, database)
        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600, echo=False)
        self.Session = sessionmaker(bind=self.engine)

    def test_connection(self):
        try:
            with self.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True
        except Exception as e:
            logger.error('数据库连接失败: %s', e)
            return False

    def get_shops(self):
        sql = text('SELECT id AS shop_id, name, platform, platform_shop_id, shop_token, auto_reply_enabled, is_active FROM shops WHERE is_active = 1')
        try:
            with self.engine.connect() as conn:
                return [dict(row) for row in conn.execute(sql).mappings()]
        except SQLAlchemyError as e:
            logger.error('获取店铺列表失败: %s', e)
            return []

    def get_shop_by_token(self, shop_token):
        sql = text('SELECT id AS shop_id, name, platform, platform_shop_id, shop_token, auto_reply_enabled, is_active FROM shops WHERE shop_token = :token LIMIT 1')
        try:
            with self.engine.connect() as conn:
                row = conn.execute(sql, {'token': shop_token}).mappings().first()
                return dict(row) if row else None
        except SQLAlchemyError as e:
            logger.error('通过token获取店铺失败: %s', e)
            return None

    def update_shop_token(self, shop_id, access_token, expires_at):
        sql = text('UPDATE shops SET access_token = :token, token_expires_at = :expires WHERE id = :shop_id')
        try:
            with self.engine.begin() as conn:
                conn.execute(sql, {'token': access_token, 'expires': expires_at, 'shop_id': shop_id})
            return True
        except SQLAlchemyError as e:
            logger.error('更��access_token失败: %s', e)
            return False

    def insert_message(self, shop_id, buyer_id, buyer_name, order_id, direction, content, msg_type, image_url='', needs_human=False, status='pending'):
        # 过滤无效消息
        if not buyer_id or buyer_id in ('', '0', 'None'):
            return 0
        if direction == 'in' and not content and msg_type == 'text':
            return 0
        sql = text(
            'INSERT INTO messages (shop_id, buyer_id, buyer_name, order_id, direction, content, msg_type, image_url, needs_human, status, msg_time) '
            'VALUES (:shop_id, :buyer_id, :buyer_name, :order_id, :direction, :content, :msg_type, :image_url, :needs_human, :status, :msg_time)'
        )
        try:
            with self.engine.begin() as conn:
                result = conn.execute(sql, {
                    'shop_id': shop_id, 'buyer_id': str(buyer_id), 'buyer_name': buyer_name or '',
                    'order_id': order_id or '', 'direction': direction, 'content': content or '',
                    'msg_type': msg_type, 'image_url': image_url or '',
                    'needs_human': needs_human, 'status': status, 'msg_time': datetime.now(),
                })
                return result.lastrowid
        except SQLAlchemyError as e:
            logger.error('插入消息失败: %s', e)
            return 0

    def update_message_reply(self, message_id, reply_content, process_by, needs_human, token_used=0):
        sql = text(
            'UPDATE messages SET status = "processed", process_by = :process_by, '
            'needs_human = :needs_human, token_used = :token_used, processed_at = :processed_at '
            'WHERE id = :message_id'
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(sql, {
                    'process_by': process_by, 'needs_human': needs_human,
                    'token_used': token_used, 'processed_at': datetime.now(),
                    'message_id': message_id,
                })
            return True
        except SQLAlchemyError as e:
            logger.error('更新消息回复失败: %s', e)
            return False

    def get_pending_messages(self, shop_id):
        sql = text(
            'SELECT id, shop_id, buyer_id, buyer_name, order_id, direction, content, msg_type, image_url, needs_human, status, msg_time '
            'FROM messages WHERE shop_id = :shop_id AND status = "pending" ORDER BY msg_time ASC LIMIT 100'
        )
        try:
            with self.engine.connect() as conn:
                return [dict(row) for row in conn.execute(sql, {'shop_id': shop_id}).mappings()]
        except SQLAlchemyError as e:
            logger.error('获取待处理消息失败: %s', e)
            return []

    def get_today_stats(self, shop_id=None):
        base_where = 'DATE(msg_time) = CURDATE()'
        params = {}
        if shop_id:
            base_where += ' AND shop_id = :shop_id'
            params['shop_id'] = shop_id
        try:
            with self.engine.connect() as conn:
                total = conn.execute(text('SELECT COUNT(*) FROM messages WHERE {} AND direction = "in"'.format(base_where)), params).scalar() or 0
                ai_count = conn.execute(text('SELECT COUNT(*) FROM messages WHERE {} AND process_by IN ("rule","knowledge","ai")'.format(base_where)), params).scalar() or 0
                human_count = conn.execute(text('SELECT COUNT(*) FROM messages WHERE {} AND needs_human = 1'.format(base_where)), params).scalar() or 0
            return {'total': total, 'ai_handled': ai_count, 'human_handled': human_count}
        except SQLAlchemyError as e:
            logger.error('获取统计数据失败: %s', e)
            return {'total': 0, 'ai_handled': 0, 'human_handled': 0}

    def get_recent_messages(self, shop_id, limit=80):
        sql = text(
            'SELECT id, buyer_id, buyer_name, order_id, direction, content, msg_type, '
            'image_url, process_by, needs_human, status, msg_time as created_at '
            'FROM messages WHERE shop_id = :shop_id AND buyer_id != "4" AND buyer_id != "" '
            'ORDER BY msg_time DESC LIMIT :limit'
        )
        try:
            with self.engine.connect() as conn:
                rows = [dict(row) for row in conn.execute(sql, {'shop_id': shop_id, 'limit': limit}).mappings()]
                return list(reversed(rows))
        except SQLAlchemyError as e:
            logger.error('获取最近消息失败: %s', e)
            return []

    def get_buyer_orders(self, shop_id, buyer_id, limit=5):
        """获取买家最近订单 - 使用真实表结构"""
        sql = text(
            'SELECT order_id, status, goods_name, goods_img, amount, quantity, created_at '
            'FROM pdd_orders WHERE shop_id = :shop_id AND buyer_id = :buyer_id '
            'ORDER BY created_at DESC LIMIT :limit'
        )
        try:
            with self.engine.connect() as conn:
                rows = [dict(row) for row in conn.execute(sql, {'shop_id': shop_id, 'buyer_id': str(buyer_id), 'limit': limit}).mappings()]
                for row in rows:
                    status_code = str(row.get('status') or '')
                    row['order_status_text'] = ORDER_STATUS_MAP.get(status_code, status_code or '未知')
                    amt = row.get('amount', 0)
                    row['pay_amount_yuan'] = '{}元'.format(float(amt or 0))
                return rows
        except SQLAlchemyError as e:
            logger.error('获取买家订单失败: %s', e)
            return []

    def get_buyer_latest_order(self, shop_id, buyer_id):
        orders = self.get_buyer_orders(shop_id, buyer_id, limit=1)
        return orders[0] if orders else {}

    def insert_order(self, shop_id, order_data):
        """插入订单 - 使用真实表结构"""
        sql = text(
            'INSERT INTO pdd_orders (shop_id, order_id, buyer_id, buyer_name, goods_name, goods_img, '
            'amount, quantity, status, address, raw_data, created_at, captured_at) '
            'VALUES (:shop_id, :order_id, :buyer_id, :buyer_name, :goods_name, :goods_img, '
            ':amount, :quantity, :status, :address, :raw_data, :created_at, :captured_at) '
            'ON DUPLICATE KEY UPDATE '
            'status=VALUES(status), goods_name=VALUES(goods_name), amount=VALUES(amount), '
            'address=VALUES(address), raw_data=VALUES(raw_data)'
        )
        # 金额转换：分->元
        amount = order_data.get('pay_amount') or order_data.get('amount') or 0
        if isinstance(amount, int) and amount > 1000:
            amount = round(amount / 100, 2)

        created_at = None
        try:
            ct = order_data.get('created_time') or order_data.get('createdTime')
            if ct:
                created_at = datetime.fromtimestamp(int(ct))
        except Exception:
            pass

        try:
            with self.engine.begin() as conn:
                conn.execute(sql, {
                    'shop_id': shop_id,
                    'order_id': str(order_data.get('order_sn') or order_data.get('order_id') or ''),
                    'buyer_id': str(order_data.get('buyer_id') or ''),
                    'buyer_name': str(order_data.get('buyer_name') or ''),
                    'goods_name': str(order_data.get('goods_name') or ''),
                    'goods_img': str(order_data.get('goods_img') or order_data.get('thumbUrl') or ''),
                    'amount': amount,
                    'quantity': int(order_data.get('goods_count') or order_data.get('quantity') or 1),
                    'status': str(order_data.get('order_status') or order_data.get('status') or ''),
                    'address': str(order_data.get('receiver_address') or order_data.get('address') or ''),
                    'raw_data': json.dumps(order_data, ensure_ascii=False)[:4000],
                    'created_at': created_at,
                    'captured_at': datetime.now(),
                })
            return True
        except SQLAlchemyError as e:
            logger.error('插入订单失败: %s', e)
            return False
