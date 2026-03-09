# -*- coding: utf-8 -*-
"""
拼多多订单模型
功能说明：存储由浏览器插件从拼多多商家后台抓取的订单数据
订单数据按店铺隔离，shop_id 区分
预留扩展：其他平台（淘宝、京东、抖店）可参照此模型建立对应表
"""

from .database import db, get_beijing_time


class PddOrder(db.Model):
    """
    拼多多订单表（由浏览器插件抓取）
    说明：记录买家订单的关键信息，供AI退款决策使用
    """
    __tablename__ = 'pdd_orders'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属店铺ID（外键）
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)

    # 拼多多订单号（唯一标识）
    order_id = db.Column(db.String(64), nullable=False, index=True)

    # 买家ID（拼多多用户ID）
    buyer_id = db.Column(db.String(64))

    # 买家昵称
    buyer_name = db.Column(db.String(64))

    # 商品名称
    goods_name = db.Column(db.String(255))

    # 商品图片URL
    goods_img = db.Column(db.String(500))

    # 订单金额
    amount = db.Column(db.Numeric(10, 2))

    # 商品数量
    quantity = db.Column(db.Integer, default=1)

    # 订单状态（待付款/待发货/已发货/已完成/退款中）
    status = db.Column(db.String(32))

    # 退款状态
    refund_status = db.Column(db.String(32))

    # 退款原因
    refund_reason = db.Column(db.Text)

    # 收货地址（脱敏处理）
    address = db.Column(db.Text)

    # 订单创建时间（拼多多平台时间）
    created_at = db.Column(db.DateTime)

    # 数据抓取时间（北京时间）
    captured_at = db.Column(db.DateTime, default=get_beijing_time)

    # 数据来源：client=客户端采集, browser_plugin=浏览器插件, manual=手动录入
    source = db.Column(db.String(20), default='browser_plugin')

    # 原始数据JSON（备用，存储插件推送的完整数据）
    raw_data = db.Column(db.Text)

    # 关联店铺
    shop = db.relationship('Shop', backref='pdd_orders')

    def to_info_string(self) -> str:
        """
        生成供AI退款决策使用的订单信息字符串
        功能：将订单关键字段拼接为自然语言，传入豆包AI做退款决策
        """
        return (
            f"订单号：{self.order_id}，"
            f"商品：{self.goods_name or '未知商品'}，"
            f"金额：{self.amount or 0}元，"
            f"数量：{self.quantity or 1}件，"
            f"状态：{self.status or '未知'}，"
            f"退款状态：{self.refund_status or '无'}，"
            f"退款原因：{self.refund_reason or '无'}，"
            f"下单时间：{self.created_at.strftime('%Y-%m-%d') if self.created_at else '未知'}"
        )

    def to_dict(self) -> dict:
        """转换为字典格式，用于API响应和模板渲染"""
        # source中文映射
        source_labels = {
            'client': '客户端采集',
            'browser_plugin': '浏览器插件',
            'manual': '手动录入',
        }
        return {
            'id': self.id,
            'shop_id': self.shop_id,
            'order_id': self.order_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer_name,
            'goods_name': self.goods_name,
            'goods_img': self.goods_img,
            'amount': float(self.amount) if self.amount else 0,
            'quantity': self.quantity or 1,
            'status': self.status,
            'refund_status': self.refund_status,
            'refund_reason': self.refund_reason,
            'address': self.address,
            'source': self.source or 'browser_plugin',
            'source_label': source_labels.get(self.source or 'browser_plugin', '未知'),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'captured_at': self.captured_at.strftime('%Y-%m-%d %H:%M') if self.captured_at else '',
        }

    def __repr__(self):
        return f'<PddOrder {self.order_id}: {self.goods_name}>'
