# -*- coding: utf-8 -*-
"""
用户模型
功能说明：管理系统用户（管理员、操作员）
支持角色权限控制，不同角色看到不同功能
"""

from .database import db, get_beijing_time
from flask_login import UserMixin


class User(UserMixin, db.Model):
    """
    用户表
    说明：系统管理员和操作员账号
    角色：admin=超级管理员，operator=操作员
    """
    __tablename__ = 'users'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True)

    # 登录用户名
    username = db.Column(db.String(50), unique=True, nullable=False)

    # 密码哈希（使用werkzeug加密）
    password_hash = db.Column(db.String(256), nullable=False)

    # 显示名称
    display_name = db.Column(db.String(100), default='')

    # 角色（admin=超管, operator=操作员）
    role = db.Column(db.String(20), default='operator')

    # 绑定的行业ID（操作员只能管理指定行业，admin可以管理所有）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=True)

    # 是否启用
    is_active = db.Column(db.Boolean, default=True)

    # 最后登录时间（北京时间）
    last_login_at = db.Column(db.DateTime, nullable=True)

    # 创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    def is_admin(self):
        """
        判断是否为超级管理员
        超管可以管理所有行业和功能
        """
        return self.role == 'admin'

    def can_manage_industry(self, industry_id):
        """
        判断用户是否有权限管理指定行业
        超管：可以管理所有行业
        操作员：只能管理自己绑定的行业
        """
        if self.is_admin():
            return True
        return self.industry_id == industry_id

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'role': self.role,
            'industry_id': self.industry_id,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.strftime('%Y-%m-%d %H:%M') if self.last_login_at else '',
        }

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
