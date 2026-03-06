# -*- coding: utf-8 -*-
"""
规则引擎模型
功能说明：存储三层处理第一层的规则配置
规则处理0成本，目标覆盖20%的消息
"""

from .database import db, get_beijing_time


class Rule(db.Model):
    """
    规则表
    说明：存储关键词触发规则
    当消息匹配规则时，直接返回预设回复（不调用AI，0成本）
    """
    __tablename__ = 'rules'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属行业ID（规则按行业隔离）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=False)

    # 规则名称（描述用）
    name = db.Column(db.String(100), nullable=False)

    # 触发关键词（逗号分隔，任一匹配即触发）
    trigger_keywords = db.Column(db.Text, nullable=False)

    # 匹配模式（any=任一词匹配, all=所有词匹配, exact=完全匹配）
    match_mode = db.Column(db.String(20), default='any')

    # 回复内容（支持变量：{buyer_name}, {order_id}等）
    reply_content = db.Column(db.Text, nullable=False)

    # 是否触发动作（换号、退款等）
    action_type = db.Column(db.String(50), default='')

    # 动作参数（JSON格式）
    action_params = db.Column(db.Text, default='{}')

    # 优先级（数值越大越先匹配）
    priority = db.Column(db.Integer, default=0)

    # 命中次数
    hit_count = db.Column(db.Integer, default=0)

    # 是否启用
    is_active = db.Column(db.Boolean, default=True)

    # 创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    def get_keywords_list(self):
        """
        获取触发关键词列表
        """
        if not self.trigger_keywords:
            return []
        return [kw.strip() for kw in self.trigger_keywords.split(',') if kw.strip()]

    def increment_hit(self):
        """增加命中次数"""
        self.hit_count = (self.hit_count or 0) + 1
        self.updated_at = get_beijing_time()

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'industry_id': self.industry_id,
            'name': self.name,
            'trigger_keywords': self.trigger_keywords,
            'match_mode': self.match_mode,
            'reply_content': self.reply_content,
            'action_type': self.action_type,
            'priority': self.priority,
            'hit_count': self.hit_count,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<Rule {self.id}: {self.name}>'
