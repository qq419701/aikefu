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
        from .system_config import SystemConfig  # noqa: F401

        # 创建所有数据表
        db.create_all()

        # 插入初始数据（行业分类、管理员账号等）
        _insert_default_data(app)
        # 初始化系统配置默认值
        _init_system_configs(app)


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


def _init_system_configs(app):
    """初始化系统配置默认值"""
    defaults = [
        # ---- AI参数配置 ----
        dict(key='doubao_api_key',     label='豆包API Key',      group='ai', value_type='string', is_secret=True,  description='从火山方舟控制台获取', need_restart=False, value=''),
        dict(key='doubao_lite_model',  label='Lite模型名称',     group='ai', value_type='string', description='用于意图识别/多轮对话/FAQ（速度快）', value='doubao-lite-32k'),
        dict(key='doubao_pro_model',   label='Pro模型名称',      group='ai', value_type='string', description='用于退款决策/情绪安抚（更准确）', value='doubao-pro-32k'),
        dict(key='doubao_max_tokens',  label='AI最大Token数',    group='ai', value_type='int',    description='单次AI回复的最大Token数，越大回复越详细但越贵', value='500'),
        dict(key='doubao_temperature', label='AI温度参数',        group='ai', value_type='float',  description='0.0=精确稳定，1.0=创意多变，建议0.3', value='0.3'),
        # ---- 多轮对话/上下文配置 ----
        dict(key='max_context_turns',       label='多轮对话保留轮次',  group='context', value_type='int',   description='每轮=买家+AI各一条，保留越多记忆越好但越贵', value='10'),
        dict(key='context_timeout_minutes', label='会话超时分钟',      group='context', value_type='int',   description='超过此时间无消息则重置上下文', value='30'),
        # ---- 知识库配置 ----
        dict(key='maxkb_enabled',         label='启用MaxKB语义检索', group='knowledge', value_type='bool',   description='true=使用MaxKB向量检索（命中率更高），false=关键词相似度', value='false'),
        dict(key='maxkb_api_url',         label='MaxKB服务地址',     group='knowledge', value_type='string', description='MaxKB的HTTP地址，如 http://localhost:8080', value='http://localhost:8080'),
        dict(key='maxkb_api_key',         label='MaxKB API Key',     group='knowledge', value_type='string', is_secret=True, description='MaxKB后台生成的API密钥', value=''),
        dict(key='maxkb_dataset_id',      label='MaxKB数据集ID',     group='knowledge', value_type='string', description='MaxKB后台创建数据集后获取的ID', value=''),
        dict(key='knowledge_similarity',  label='知识库相似度阈值',   group='knowledge', value_type='float',  description='0.0-1.0，超过此值才认为匹配，越高越精准但漏匹配越多', value='0.6'),
        dict(key='maxkb_min_similarity',  label='MaxKB最低相似度',   group='knowledge', value_type='float',  description='MaxKB检索时低于此分数不返回结果', value='0.6'),
        # ---- 学习中心配置（v3.0新增）----
        dict(key='learning_mode',                   label='学习模式',                   group='learning', value_type='string', description='全量(all)/阈值(threshold)/自动(auto)/关闭(off)。threshold=低置信度才进审核；all=所有AI回复入队列；auto=高置信度自动入库；off=停止学习', value='threshold'),
        dict(key='learning_confidence_threshold',   label='审核队列置信度上限',         group='learning', value_type='float',  description='低于此值才进审核队列（模式threshold），0.0-1.0', value='0.7'),
        dict(key='learning_auto_approve_threshold', label='自动入库置信度下限',         group='learning', value_type='float',  description='高于此值直接自动入库不需人工（模式auto），0.0-1.0', value='0.85'),
        dict(key='learning_dedup_enabled',          label='入库前去重检测',             group='learning', value_type='bool',   description='开启后入库时检查是否有精确相同的问题，避免重复', value='true'),
        dict(key='learning_dedup_similarity',        label='语义去重相似度阈值',         group='learning', value_type='float',  description='关键词重叠率高于此值判定为相似，0.0-1.0', value='0.8'),
        dict(key='learning_auto_keywords',           label='入库时AI自动生成关键词',     group='learning', value_type='bool',   description='入库时AI自动生成关键词（v3.0）', value='false'),
        dict(key='kb_maxkb_full_sync_on_save',       label='知识库保存后触发MaxKB全量同步', group='learning', value_type='bool', description='知识库保存后触发MaxKB全量同步', value='false'),
        dict(key='learning_page_size',              label='学习中心每页显示条数',       group='learning', value_type='int',    description='学习中心每页显示待审核记录数量', value='20'),
        dict(key='learning_maxkb_sync',             label='入库后自动同步MaxKB',        group='learning', value_type='bool',   description='审核入库后自动将新知识同步到MaxKB向量库', value='true'),
        dict(key='kb_dedup_enabled',                label='知识库手动新增去重',         group='learning', value_type='bool',   description='手动添加/批量保存知识库条目时检测重复', value='true'),
        # ---- 系统行为配置 ----
        dict(key='auto_reply_delay_min',      label='自动回复最小延迟(秒)', group='behavior', value_type='int',   description='模拟人工输入，避免平台检测', value='1'),
        dict(key='auto_reply_delay_max',      label='自动回复最大延迟(秒)', group='behavior', value_type='int',   description='模拟人工输入，避免平台检测', value='3'),
        dict(key='human_intervention_level',  label='情绪转人工等级',        group='behavior', value_type='int',   description='0=正常,1=轻度,2=中度,3=严重,4=危机。达到此等级转人工', value='3'),
        dict(key='blacklist_refund_threshold',label='黑名单退款次数阈值',    group='behavior', value_type='int',   description='30天内超过此次数自动加入风险名单', value='3'),
        dict(key='data_retention_days',       label='数据保留天数',           group='behavior', value_type='int',   description='日志和消息记录保留天数', value='90'),
    ]
    from models.system_config import SystemConfig
    for d in defaults:
        if not SystemConfig.query.filter_by(key=d['key']).first():
            cfg = SystemConfig(
                key=d['key'], value=d.get('value', ''), value_type=d['value_type'],
                group=d['group'], label=d['label'], description=d.get('description', ''),
                need_restart=d.get('need_restart', False), is_secret=d.get('is_secret', False),
                updated_at=get_beijing_time()
            )
            db.session.add(cfg)
    db.session.commit()


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
