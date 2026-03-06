# -*- coding: utf-8 -*-
"""
配置文件 - 爱客服AI智能客服系统
功能说明：系统全局配置，包括数据库、端口、时区、AI接口等参数
作者：aikefu
时间：北京时间
"""

import os
import pytz

# ============================================================
# 基础配置
# ============================================================

# 系统名称
SYSTEM_NAME = "爱客服AI智能客服系统"
SYSTEM_VERSION = "v1.0.0"

# 服务端口（按需求设置为6000）
PORT = 6000

# 应用目录名称
APP_DIR = "aikefu"

# 北京时区（中国标准时间 UTC+8）
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

# 密钥（生产环境请修改为随机强密钥）
SECRET_KEY = os.environ.get('SECRET_KEY', 'aikefu-secret-key-2024-change-in-production')

# 调试模式（生产环境设为 False）
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'


# ============================================================
# 数据库配置
# ============================================================

# 数据库文件路径（SQLite）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'aikefu.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False


# ============================================================
# 豆包AI配置（字节跳动火山方舟）
# ============================================================

# 火山方舟API地址
DOUBAO_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"

# API密钥（从火山方舟控制台获取，生产环境使用环境变量）
DOUBAO_API_KEY = os.environ.get('DOUBAO_API_KEY', '')

# 默认使用的豆包模型（豆包-pro-32k）
DOUBAO_MODEL = os.environ.get('DOUBAO_MODEL', 'ep-20240601-xxxx')  # 替换为实际endpoint

# 豆包视觉模型（图片识别）
DOUBAO_VISION_MODEL = os.environ.get('DOUBAO_VISION_MODEL', 'ep-vision-xxxx')

# AI请求超时时间（秒）
DOUBAO_TIMEOUT = 30

# AI回复最大token数
DOUBAO_MAX_TOKENS = 500

# AI温度参数（0.0-1.0，越低越精确）
DOUBAO_TEMPERATURE = 0.3


# ============================================================
# 三层处理配置
# ============================================================

# 知识库相似度阈值（0.0-1.0，超过此值认为匹配）
KNOWLEDGE_SIMILARITY_THRESHOLD = 0.6

# 规则引擎覆盖率目标（%）
RULES_COVERAGE_TARGET = 20

# 知识库覆盖率目标（%）
KNOWLEDGE_COVERAGE_TARGET = 55

# AI处理覆盖率目标（%）
AI_COVERAGE_TARGET = 25

# 缓存有效期（秒，默认24小时）
CACHE_TTL = 86400


# ============================================================
# 情绪识别配置
# ============================================================

# 情绪级别定义
EMOTION_LEVELS = {
    'normal': 0,     # 正常
    'mild': 1,       # 轻度不满
    'moderate': 2,   # 中度不满
    'severe': 3,     # 严重不满
    'crisis': 4,     # 危机级别
}

# 触发人工干预的情绪级别
HUMAN_INTERVENTION_LEVEL = 3


# ============================================================
# 定时任务配置（北京时间）
# ============================================================

# 每日AI学习时间（北京时间，凌晨3点执行，避免高峰）
DAILY_LEARNING_HOUR = 3
DAILY_LEARNING_MINUTE = 0

# 每日数据统计时间（北京时间，凌晨1点）
DAILY_STATS_HOUR = 1
DAILY_STATS_MINUTE = 0

# 数据保留天数（日志、消息记录）
DATA_RETENTION_DAYS = 90


# ============================================================
# 多行业配置
# ============================================================

# 预置行业列表
DEFAULT_INDUSTRIES = [
    {
        'code': 'game_rental',
        'name': '游戏租号',
        'description': '游戏账号租赁平台客服，支持拼多多/淘宝等电商平台',
        'icon': '🎮',
        'platform': 'pdd',  # 主要平台
    },
    {
        'code': 'ecommerce',
        'name': '电商客服',
        'description': '通用电商平台客服，适用于各类商品销售',
        'icon': '🛍️',
        'platform': 'general',
    },
    {
        'code': 'education',
        'name': '教育培训',
        'description': '教育培训机构客服，处理课程咨询、退款等',
        'icon': '📚',
        'platform': 'general',
    },
    {
        'code': 'hotel',
        'name': '酒店民宿',
        'description': '酒店民宿预订客服，处理预订、退款、投诉等',
        'icon': '🏨',
        'platform': 'general',
    },
]


# ============================================================
# 消息配置
# ============================================================

# 每次拉取消息的最大条数
MAX_MESSAGES_PER_FETCH = 50

# 消息处理超时（秒）
MESSAGE_PROCESS_TIMEOUT = 10

# 自动回复延迟（秒，模拟人工，避免被平台检测）
AUTO_REPLY_DELAY_MIN = 1
AUTO_REPLY_DELAY_MAX = 3


# ============================================================
# 黑名单配置
# ============================================================

# 触发黑名单的退款次数阈值
BLACKLIST_REFUND_THRESHOLD = 3

# 黑名单检查周期（天）
BLACKLIST_CHECK_PERIOD = 30


# ============================================================
# 日志配置
# ============================================================

LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_LEVEL = 'INFO'
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
