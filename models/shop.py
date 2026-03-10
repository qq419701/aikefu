# -*- coding: utf-8 -*-
"""
店铺模型
功能说明：定义店铺数据结构，支持多店铺管理
每个店铺属于一个行业，同一行业的多个店铺共享行业知识库
"""

from .database import db, get_beijing_time


class Shop(db.Model):
    """
    店铺表
    说明：每个店铺对应一个电商平台的账号
    同一行业的多个店铺共用该行业的知识库和规则，但各自有独立的平台凭证
    """
    __tablename__ = 'shops'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 店铺名称
    name = db.Column(db.String(100), nullable=False)

    # 所属行业ID（外键）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=False)

    # 平台类型（pdd=拼多多, taobao=淘宝, jd=京东）
    platform = db.Column(db.String(20), default='pdd')

    # 平台店铺ID（拼多多店铺ID等）
    platform_shop_id = db.Column(db.String(100), default='')

    # 平台API的 client_id（AppKey）
    client_id = db.Column(db.String(200), default='')

    # 平台API的 client_secret（AppSecret），实际部署需加密存储
    client_secret = db.Column(db.String(200), default='')

    # 平台访问令牌（access_token），定期刷新
    access_token = db.Column(db.Text, default='')

    # 令牌过期时间（北京时间）
    token_expires_at = db.Column(db.DateTime, nullable=True)

    # 店铺头像/Logo URL
    avatar_url = db.Column(db.String(500), default='')

    # 是否启用自动回复
    auto_reply_enabled = db.Column(db.Boolean, default=True)

    # 是否启用自动换号（游戏租号专用）
    auto_exchange_enabled = db.Column(db.Boolean, default=False)

    # u号租平台账号（游戏租号专用）
    uzuzu_account = db.Column(db.String(100), default='')

    # u号租平台密码（实际部署需加密存储）
    uzuzu_password = db.Column(db.String(200), default='')

    # u号租平台API Token
    uzuzu_token = db.Column(db.String(500), default='')

    # 自定义系统提示词（覆盖行业默认提示词）
    custom_prompt = db.Column(db.Text, default='')

    # 店铺备注
    note = db.Column(db.Text, default='')

    # 是否启用
    is_active = db.Column(db.Boolean, default=True)

    # 插件认证Token（用于Chrome插件向本地服务推送消息时鉴权）
    shop_token = db.Column(db.String(64), unique=True, index=True)

    # 创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 更新时间（北京时间）
    updated_at = db.Column(db.DateTime, default=get_beijing_time, onupdate=get_beijing_time)

    # 关联消息记录
    messages = db.relationship('Message', backref='shop', lazy='dynamic',
                               foreign_keys='Message.shop_id')

    def generate_token(self) -> str:
        """
        生成店铺Token（用于Chrome插件认证）
        功能：生成64位随机十六进制字符串，保证唯一性
        返回：生成的Token字符串
        """
        import secrets
        self.shop_token = secrets.token_hex(32)
        return self.shop_token

    def get_effective_prompt(self):
        """
        获取有效的AI系统提示词
        优先使用店铺自定义提示词，否则使用行业默认提示词
        """
        if self.custom_prompt and self.custom_prompt.strip():
            return self.custom_prompt
        # 通过关联获取行业提示词
        if self.industry:
            return self.industry.ai_system_prompt
        return ''

    def is_token_valid(self):
        """
        检查令牌是否有效
        优先判断 shop_token（客户端插件鉴权Token）是否存在
        其次判断 access_token（平台OAuth令牌）是否未过期
        """
        # 客户端插件Token存在即视为有效
        if self.shop_token:
            return True
        # 兼容旧逻辑：检查平台OAuth令牌
        if not self.access_token:
            return False
        if not self.token_expires_at:
            return False
        now = get_beijing_time()
        return now < self.token_expires_at

    def to_dict(self):
        """
        转换为字典格式
        用于API响应或模板渲染
        """
        return {
            'id': self.id,
            'name': self.name,
            'industry_id': self.industry_id,
            'industry_name': self.industry.name if self.industry else '',
            'industry_icon': self.industry.icon if self.industry else '',
            'platform': self.platform,
            'platform_shop_id': self.platform_shop_id,
            'auto_reply_enabled': self.auto_reply_enabled,
            'auto_exchange_enabled': self.auto_exchange_enabled,
            'is_active': self.is_active,
            'token_valid': self.is_token_valid(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<Shop {self.id}: {self.name}>'
