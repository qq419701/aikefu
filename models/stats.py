# -*- coding: utf-8 -*-
"""
每日统计模型
功能说明：记录每日运营数据统计
包括消息量、AI成本、换号次数等关键指标
"""

from .database import db, get_beijing_time


class DailyStats(db.Model):
    """
    每日统计表
    说明：每天凌晨统计前一天的运营数据
    用于生成数据报表、ROI分析
    """
    __tablename__ = 'daily_stats'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 统计日期（格式：2024-01-01）
    stat_date = db.Column(db.String(20), nullable=False)

    # 所属店铺ID（为空则为全局统计）
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=True)

    # 所属行业ID
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=True)

    # 总消息数
    total_messages = db.Column(db.Integer, default=0)

    # 规则引擎处理数
    rule_handled = db.Column(db.Integer, default=0)

    # 知识库处理数
    knowledge_handled = db.Column(db.Integer, default=0)

    # AI处理数
    ai_handled = db.Column(db.Integer, default=0)

    # 人工处理数
    human_handled = db.Column(db.Integer, default=0)

    # AI消耗的token数
    total_tokens = db.Column(db.Integer, default=0)

    # 估算AI费用（元）
    ai_cost = db.Column(db.Float, default=0.0)

    # 换号次数（游戏租号专用）
    exchange_count = db.Column(db.Integer, default=0)

    # 退款申请数
    refund_count = db.Column(db.Integer, default=0)

    # 退款驳回成功数
    refund_rejected = db.Column(db.Integer, default=0)

    # 情绪危机处理数
    crisis_count = db.Column(db.Integer, default=0)

    # 新增黑名单数
    blacklist_added = db.Column(db.Integer, default=0)

    # 统计时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    def get_ai_solve_rate(self):
        """
        计算AI自动解决率（%）
        目标：≥90%（上线1个月后）
        """
        if not self.total_messages:
            return 0.0
        auto_handled = (self.rule_handled or 0) + (self.knowledge_handled or 0) + (self.ai_handled or 0)
        return round(auto_handled / self.total_messages * 100, 2)

    def get_refund_reject_rate(self):
        """
        计算退款驳回成功率（%）
        目标：≥70%
        """
        if not self.refund_count:
            return 0.0
        return round((self.refund_rejected or 0) / self.refund_count * 100, 2)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'stat_date': self.stat_date,
            'shop_id': self.shop_id,
            'total_messages': self.total_messages,
            'rule_handled': self.rule_handled,
            'knowledge_handled': self.knowledge_handled,
            'ai_handled': self.ai_handled,
            'human_handled': self.human_handled,
            'total_tokens': self.total_tokens,
            'ai_cost': self.ai_cost,
            'exchange_count': self.exchange_count,
            'refund_count': self.refund_count,
            'refund_rejected': self.refund_rejected,
            'ai_solve_rate': self.get_ai_solve_rate(),
            'refund_reject_rate': self.get_refund_reject_rate(),
        }

    def __repr__(self):
        return f'<DailyStats {self.stat_date} shop={self.shop_id}>'
