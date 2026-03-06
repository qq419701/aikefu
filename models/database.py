# -*- coding: utf-8 -*-
"""
数据库初始化模块
功能说明：创建SQLAlchemy数据库实例，提供数据库初始化函数
使用北京时间记录所有时间戳
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

# SQLAlchemy 数据库实例（全局单例）
db = SQLAlchemy()

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


def get_beijing_time():
    """
    获取当前北京时间
    返回：北京时间的 datetime 对象
    """
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def init_db(app):
    """
    初始化数据库
    功能：绑定Flask应用，创建所有数据表，插入初始数据
    参数：app - Flask应用实例
    """
    import os
    # 确保 instance 目录存在
    instance_dir = os.path.join(app.root_path, 'instance')
    os.makedirs(instance_dir, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        # 创建所有数据表
        db.create_all()

        # 插入初始数据（行业分类、管理员账号等）
        _insert_default_data(app)


def _insert_default_data(app):
    """
    插入默认初始数据
    功能：系统首次运行时，插入预置行业和默认管理员账号
    """
    from .industry import Industry
    from .user import User
    from config import DEFAULT_INDUSTRIES
    from werkzeug.security import generate_password_hash

    # 插入预置行业（如果不存在）
    for ind_data in DEFAULT_INDUSTRIES:
        existing = Industry.query.filter_by(code=ind_data['code']).first()
        if not existing:
            industry = Industry(
                code=ind_data['code'],
                name=ind_data['name'],
                description=ind_data['description'],
                icon=ind_data.get('icon', '🏢'),
                platform=ind_data.get('platform', 'general'),
                is_active=True,
                created_at=get_beijing_time()
            )
            db.session.add(industry)

    # 创建默认管理员账号（首次运行）
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            display_name='系统管理员',
            role='admin',
            is_active=True,
            created_at=get_beijing_time()
        )
        db.session.add(admin)

    db.session.commit()
