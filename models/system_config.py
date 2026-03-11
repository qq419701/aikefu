# -*- coding: utf-8 -*-
"""
系统配置数据模型
功能说明：将 config.py 中的动态配置迁移到数据库，支持后台可视化编辑，无需重启服务
配置项按分组存储：ai / knowledge / behavior / context
"""
from .database import db, get_beijing_time


class SystemConfig(db.Model):
    """系统配置表（Key-Value 存储）"""
    __tablename__ = 'system_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 配置Key（全局唯一）
    key = db.Column(db.String(100), nullable=False, unique=True)
    # 配置值（字符串存储，使用时按类型转换）
    value = db.Column(db.Text, nullable=True)
    # 值类型：string / int / float / bool / json
    value_type = db.Column(db.String(20), default='string', nullable=False)
    # 分组：ai / knowledge / behavior / context
    group = db.Column(db.String(50), default='ai', nullable=False)
    # 标签（前端显示用）
    label = db.Column(db.String(200), nullable=False)
    # 说明
    description = db.Column(db.Text, nullable=True)
    # 是否需要重启才生效（提示用）
    need_restart = db.Column(db.Boolean, default=False, nullable=False)
    # 是否隐藏（敏感配置，前端不显示值）
    is_secret = db.Column(db.Boolean, default=False, nullable=False)
    # 更新时间
    updated_at = db.Column(db.DateTime, nullable=True)

    def get_value(self):
        """按类型返回配置值"""
        if self.value is None:
            return None
        if self.value_type == 'int':
            return int(self.value)
        if self.value_type == 'float':
            return float(self.value)
        if self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes')
        return self.value

    @staticmethod
    def get(key: str, default=None):
        """快速获取配置值"""
        cfg = SystemConfig.query.filter_by(key=key).first()
        return cfg.get_value() if cfg else default

    @staticmethod
    def set(key: str, value):
        """快速设置配置值"""
        cfg = SystemConfig.query.filter_by(key=key).first()
        if cfg:
            cfg.value = str(value)
            cfg.updated_at = get_beijing_time()
            db.session.commit()

    def __repr__(self):
        return f'<SystemConfig {self.key}={self.value}>'
