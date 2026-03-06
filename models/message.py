# -*- coding: utf-8 -*-
"""
消息模型
功能说明：存储客服消息记录和AI回复缓存
支持多店铺消息管理，缓存AI回复以节省成本
"""

from .database import db, get_beijing_time


class Message(db.Model):
    """
    消息记录表
    说明：记录所有买家消息和AI回复
    用于数据统计、人工复核、AI学习
    """
    __tablename__ = 'messages'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属店铺ID（外键）
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)

    # 买家ID（平台用户ID）
    buyer_id = db.Column(db.String(100), nullable=False)

    # 买家昵称
    buyer_name = db.Column(db.String(100), default='')

    # 订单号
    order_id = db.Column(db.String(100), default='')

    # 消息方向（in=买家发来，out=系统发出）
    direction = db.Column(db.String(10), default='in')

    # 消息内容
    content = db.Column(db.Text, nullable=False)

    # 消息类型（text=文字, image=图片, voice=语音）
    msg_type = db.Column(db.String(20), default='text')

    # 图片URL（消息类型为图片时）
    image_url = db.Column(db.String(500), default='')

    # 处理方式（rule=规则, knowledge=知识库, ai=豆包AI, human=人工）
    process_by = db.Column(db.String(20), default='')

    # AI回复的令牌消耗（用于成本统计）
    token_used = db.Column(db.Integer, default=0)

    # 情绪级别（0=正常，1=轻微，2=中等，3=严重，4=危机）
    emotion_level = db.Column(db.Integer, default=0)

    # 是否需要人工干预
    needs_human = db.Column(db.Boolean, default=False)

    # 是否已转人工
    is_transferred = db.Column(db.Boolean, default=False)

    # 处理状态（pending=待处理, processed=已处理, failed=失败）
    status = db.Column(db.String(20), default='pending')

    # 消息时间（北京时间）
    msg_time = db.Column(db.DateTime, default=get_beijing_time)

    # 处理完成时间（北京时间）
    processed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'shop_id': self.shop_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer_name,
            'order_id': self.order_id,
            'direction': self.direction,
            'content': self.content,
            'msg_type': self.msg_type,
            'process_by': self.process_by,
            'emotion_level': self.emotion_level,
            'needs_human': self.needs_human,
            'status': self.status,
            'msg_time': self.msg_time.strftime('%Y-%m-%d %H:%M:%S') if self.msg_time else '',
        }

    def __repr__(self):
        return f'<Message {self.id}: {self.buyer_id} -> {self.content[:30]}>'


class MessageCache(db.Model):
    """
    消息回复缓存表
    说明：缓存豆包AI的回复内容，相同或相似问题直接返回缓存
    有效减少API调用费用（相同问题命中率80%，节省80%AI成本）
    """
    __tablename__ = 'message_cache'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属行业ID（缓存按行业隔离）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=False)

    # 问题的哈希值（用于快速查找）
    question_hash = db.Column(db.String(64), nullable=False, index=True)

    # 原始问题内容
    question = db.Column(db.Text, nullable=False)

    # 缓存的回复内容
    answer = db.Column(db.Text, nullable=False)

    # 命中次数
    hit_count = db.Column(db.Integer, default=0)

    # 缓存创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 缓存过期时间（北京时间）
    expires_at = db.Column(db.DateTime, nullable=True)

    def is_valid(self):
        """
        检查缓存是否有效（未过期）
        """
        if not self.expires_at:
            return True
        return get_beijing_time() < self.expires_at

    def __repr__(self):
        return f'<MessageCache {self.id}: {self.question[:30]}>'
