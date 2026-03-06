# -*- coding: utf-8 -*-
"""
行业模型
功能说明：定义行业数据结构，支持多行业配置
每个行业可以有独立的AI提示词、知识库、回复规则
"""

from .database import db, get_beijing_time


class Industry(db.Model):
    """
    行业表
    说明：系统支持多个行业，每个行业有独立的配置
    行业之间数据完全隔离，UI只显示所属行业的内容
    """
    __tablename__ = 'industries'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 行业唯一代码（如：game_rental, ecommerce）
    code = db.Column(db.String(50), unique=True, nullable=False)

    # 行业名称（显示用）
    name = db.Column(db.String(100), nullable=False)

    # 行业描述
    description = db.Column(db.Text, default='')

    # 行业图标（emoji）
    icon = db.Column(db.String(10), default='🏢')

    # 适用平台（pdd=拼多多, taobao=淘宝, jd=京东, general=通用）
    platform = db.Column(db.String(50), default='general')

    # 豆包AI系统提示词（行业专属）
    ai_system_prompt = db.Column(db.Text, default='')

    # 自动回复是否开启
    auto_reply_enabled = db.Column(db.Boolean, default=True)

    # 是否启用图片识别
    vision_enabled = db.Column(db.Boolean, default=False)

    # 是否启用情绪识别
    emotion_enabled = db.Column(db.Boolean, default=True)

    # 触发人工干预的情绪阈值
    human_intervention_level = db.Column(db.Integer, default=3)

    # 行业状态（是否启用）
    is_active = db.Column(db.Boolean, default=True)

    # 创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 更新时间（北京时间）
    updated_at = db.Column(db.DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联的店铺（一个行业可以有多个店铺）
    shops = db.relationship('Shop', backref='industry', lazy='dynamic',
                            foreign_keys='Shop.industry_id')

    # 关联的知识库
    knowledge_items = db.relationship('KnowledgeBase', backref='industry', lazy='dynamic',
                                      foreign_keys='KnowledgeBase.industry_id')

    # 关联的规则
    rules = db.relationship('Rule', backref='industry', lazy='dynamic',
                            foreign_keys='Rule.industry_id')

    def to_dict(self):
        """
        转换为字典格式
        用于API响应或模板渲染
        """
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'platform': self.platform,
            'auto_reply_enabled': self.auto_reply_enabled,
            'vision_enabled': self.vision_enabled,
            'emotion_enabled': self.emotion_enabled,
            'is_active': self.is_active,
            'shop_count': self.shops.count(),
            'knowledge_count': self.knowledge_items.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<Industry {self.code}: {self.name}>'
