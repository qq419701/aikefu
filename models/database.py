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

# Redis 客户端（全局单例，None 表示 Redis 不可用）
redis_client = None

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


def get_beijing_time():
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def get_blacklist_cache_key(industry_id: int, buyer_id: str) -> str:
    """生成黑名单 Redis 缓存键（统一格式，避免多处重复）"""
    return f"blacklist:{industry_id}:{buyer_id}"


def init_redis(app):
    """
    初始化 Redis 连接
    功能：尝试连接 Redis，失败时静默降级（不影响主流程）
    """
    global redis_client
    import config
    if not config.REDIS_ENABLED:
        return
    try:
        import redis
        client = redis.from_url(config.REDIS_URL, decode_responses=False,
                                socket_connect_timeout=3,
                                socket_timeout=3)
        client.ping()  # 测试连接
        redis_client = client
        import logging
        logging.getLogger(__name__).info("✅ Redis 连接成功: %s", config.REDIS_URL)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "⚠️ Redis 连接失败，降级为纯MySQL模式: %s", e
        )
        redis_client = None


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
    init_redis(app)  # 初始化 Redis

    with app.app_context():
        # 提前导入所有模型，确保 create_all 能创建所有表
        from .intent_rule import IntentRule  # noqa: F401

        # 创建所有数据表
        db.create_all()

        # 插入初始数据（行业分类、管理员账号等）
        _insert_default_data(app)


def _insert_default_data(app):
    """插入默认初始数据"""
    from .industry import Industry
    from .user import User
    from .intent_rule import IntentRule
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

    # 插入默认意图规则
    _init_intent_rules()


def _init_intent_rules():
    """初始化默认意图规则"""
    from .intent_rule import IntentRule

    if IntentRule.query.count() > 0:
        return

    DEFAULT_INTENT_RULES = [
        ('exchange', '换号请求',
         ['换号', '换个', '重新给', '换一个', '换账号', '换个号', '换货'],
         'auto_exchange',
         '好的，正在为您自动换号，请稍候～',
         '换号完成！新账号：{new_account}，如有问题请联系我们😊', 0),
        ('refund', '退款申请',
         ['退款', '退钱', '不要了', '申请退', '退货', '要退'],
         'handle_refund', '您的退款申请已收到，正在处理中～', '', 1),
        ('login', '登录问题',
         ['登不上', '进不去', '密码', '登录失败', '打不开', '登录不了', '进不了'],
         '', '', '', 2),
        ('complaint', '投诉举报',
         ['投诉', '举报', '差评', '太差', '骗人', '骗子', '维权'],
         '', '', '', 3),
        ('query', '查询咨询',
         ['多久', '什么时候', '怎么', '如何', '能不能', '可以吗', '会不会'],
         '', '', '', 4),
        ('payment', '付款问题',
         ['付款', '付钱', '怎么付', '支付', '怎么买', '如何付'],
         '', '', '', 5),
    ]

    import json
    now = get_beijing_time()
    for intent_code, intent_name, keywords, action_code, auto_reply_tpl, done_reply_tpl, priority in DEFAULT_INTENT_RULES:
        rule = IntentRule(
            industry_id=None,
            intent_code=intent_code,
            intent_name=intent_name,
            keywords=json.dumps(keywords, ensure_ascii=False),
            action_code=action_code or None,
            auto_reply_tpl=auto_reply_tpl or None,
            done_reply_tpl=done_reply_tpl or None,
            priority=priority,
            is_active=True,
            created_at=now,
        )
        db.session.add(rule)

    db.session.commit()
