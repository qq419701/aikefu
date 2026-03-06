# -*- coding: utf-8 -*-
"""
知识库模型
功能说明：存储各行业的问答知识库，用于三层处理的第二层
支持关键词匹配，相似度计算
"""

from .database import db, get_beijing_time


class KnowledgeBase(db.Model):
    """
    知识库表
    说明：存储行业专属的问答对
    第二层处理时，先在知识库中检索，匹配则直接返回答案（0成本）
    """
    __tablename__ = 'knowledge_base'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 所属行业ID（外键，知识库按行业隔离）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=False)

    # 问题（用户可能问的问题）
    question = db.Column(db.Text, nullable=False)

    # 答案（AI回复内容）
    answer = db.Column(db.Text, nullable=False)

    # 关键词列表（逗号分隔，用于快速匹配）
    keywords = db.Column(db.Text, default='')

    # 分类标签（如：换号、退款、登录问题等）
    category = db.Column(db.String(50), default='general')

    # 优先级（数值越大越优先匹配）
    priority = db.Column(db.Integer, default=0)

    # 命中次数（统计最常用的问答）
    hit_count = db.Column(db.Integer, default=0)

    # 是否启用
    is_active = db.Column(db.Boolean, default=True)

    # 创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 更新时间（北京时间）
    updated_at = db.Column(db.DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    def get_keywords_list(self):
        """
        获取关键词列表
        将逗号分隔的关键词字符串转为列表
        """
        if not self.keywords:
            return []
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]

    def increment_hit(self):
        """
        增加命中次数（记录该问答被使用多少次）
        """
        self.hit_count = (self.hit_count or 0) + 1
        self.updated_at = get_beijing_time()

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'industry_id': self.industry_id,
            'question': self.question,
            'answer': self.answer,
            'keywords': self.keywords,
            'category': self.category,
            'priority': self.priority,
            'hit_count': self.hit_count,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<KnowledgeBase {self.id}: {self.question[:30]}>'
