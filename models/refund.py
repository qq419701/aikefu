# -*- coding: utf-8 -*-
"""
退款记录模型
功能说明：记录拼多多及其他平台的退款申请，支持AI自动处理和人工审核
退款超时预警（红色高亮显示距离平台强制退款的剩余时间）
"""

from .database import db, get_beijing_time


class RefundRecord(db.Model):
    """
    退款记录表
    说明：跟踪所有买家退款申请的处理状态
    支持AI自动处理（同意/拒绝）和人工干预
    """
    __tablename__ = 'refund_records'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属店铺ID（外键）
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)

    # 所属行业ID（冗余存储，方便查询）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=False)

    # 订单号
    order_id = db.Column(db.String(100), nullable=False)

    # 买家平台ID
    buyer_id = db.Column(db.String(100), nullable=False)

    # 买家昵称
    buyer_name = db.Column(db.String(100), default='')

    # 退款金额（分，整数，100=1元）
    refund_amount = db.Column(db.Integer, default=0)

    # 退款原因（买家填写）
    refund_reason = db.Column(db.Text, default='')

    # 退款状态：
    #   pending   = 待处理（新申请）
    #   ai_approved = AI同意退款
    #   ai_rejected = AI拒绝退款（需人工复核）
    #   approved  = 人工同意退款
    #   rejected  = 人工拒绝退款（驳回成功）
    #   expired   = 已超时（平台强制退款）
    #   cancelled = 买家取消退款
    status = db.Column(db.String(30), default='pending')

    # AI处理决策（approve/reject/human）
    ai_decision = db.Column(db.String(20), default='')

    # AI处理原因
    ai_reason = db.Column(db.Text, default='')

    # AI给买家的回复
    ai_reply = db.Column(db.Text, default='')

    # 人工处理备注
    admin_note = db.Column(db.Text, default='')

    # 是否标记为恶意退款（加入风险名单）
    is_malicious = db.Column(db.Boolean, default=False)

    # 平台退款截止时间（超过此时间平台将强制退款）
    deadline_at = db.Column(db.DateTime, nullable=True)

    # 申请时间（北京时间）
    applied_at = db.Column(db.DateTime, default=get_beijing_time)

    # 处理时间（北京时间）
    processed_at = db.Column(db.DateTime, nullable=True)

    # 关联店铺
    shop = db.relationship('Shop', backref=db.backref('refund_records', lazy='dynamic'),
                           foreign_keys=[shop_id])

    # 关联行业
    industry = db.relationship('Industry', foreign_keys=[industry_id])

    def is_urgent(self) -> bool:
        """
        检查退款是否紧急（距离截止时间小于预警阈值）
        返回：True=紧急（红色高亮），False=正常
        """
        import config
        from datetime import timedelta
        if not self.deadline_at or self.status != 'pending':
            return False
        now = get_beijing_time()
        threshold = timedelta(hours=config.REFUND_URGENT_HOURS)
        return (self.deadline_at - now) < threshold

    def get_remaining_hours(self) -> float:
        """
        获取距离截止时间的剩余小时数
        返回：剩余小时数（负数表示已超时）
        """
        if not self.deadline_at:
            return 999.0
        now = get_beijing_time()
        delta = self.deadline_at - now
        return round(delta.total_seconds() / 3600, 1)

    def get_amount_yuan(self) -> str:
        """
        获取退款金额（元，格式化显示）
        返回：如 "12.50"
        """
        return f'{self.refund_amount / 100:.2f}'

    def to_dict(self) -> dict:
        """转换为字典格式（用于API响应）"""
        return {
            'id': self.id,
            'shop_id': self.shop_id,
            'order_id': self.order_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer_name,
            'refund_amount_yuan': self.get_amount_yuan(),
            'refund_reason': self.refund_reason,
            'status': self.status,
            'ai_decision': self.ai_decision,
            'is_urgent': self.is_urgent(),
            'remaining_hours': self.get_remaining_hours(),
            'applied_at': self.applied_at.strftime('%Y-%m-%d %H:%M') if self.applied_at else '',
            'deadline_at': self.deadline_at.strftime('%Y-%m-%d %H:%M') if self.deadline_at else '',
        }

    def __repr__(self):
        return f'<RefundRecord {self.id}: order={self.order_id} status={self.status}>'
