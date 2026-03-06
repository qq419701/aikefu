# -*- coding: utf-8 -*-
"""
黑名单模型
功能说明：管理恶意买家黑名单
自动识别频繁退款、投诉的买家并加入黑名单
"""

from .database import db, get_beijing_time


class Blacklist(db.Model):
    """
    黑名单表
    说明：记录被标记为恶意的买家
    黑名单买家消息优先转人工处理，不使用自动回复
    """
    __tablename__ = 'blacklist'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属行业ID（黑名单按行业共享，同行业所有店铺共用）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=False)

    # 买家平台ID
    buyer_id = db.Column(db.String(100), nullable=False)

    # 买家昵称
    buyer_name = db.Column(db.String(100), default='')

    # 加入黑名单原因
    reason = db.Column(db.Text, default='')

    # 退款次数（超过阈值自动加入黑名单）
    refund_count = db.Column(db.Integer, default=0)

    # 投诉次数
    complaint_count = db.Column(db.Integer, default=0)

    # 黑名单级别（1=观察, 2=警告, 3=封禁）
    level = db.Column(db.Integer, default=1)

    # 是否启用（可以手动解除黑名单）
    is_active = db.Column(db.Boolean, default=True)

    # 加入时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 更新时间（北京时间）
    updated_at = db.Column(db.DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    def get_level_text(self):
        """
        获取黑名单级别文字描述
        """
        level_map = {1: '观察', 2: '警告', 3: '封禁'}
        return level_map.get(self.level, '未知')

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'industry_id': self.industry_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer_name,
            'reason': self.reason,
            'refund_count': self.refund_count,
            'complaint_count': self.complaint_count,
            'level': self.level,
            'level_text': self.get_level_text(),
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<Blacklist {self.buyer_id} level={self.level}>'
