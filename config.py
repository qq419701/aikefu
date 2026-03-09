# -*- coding: utf-8 -*-
"""
配置文件 - 爱客服AI智能客服系统
功能说明：系统全局配置，包括数据库、端口、时区、AI接口等参数
数据库：优先使用MySQL，回退到SQLite（开发环境）
时间：使用北京时间（Asia/Shanghai，UTC+8）
"""

import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
import pytz

# ============================================================
# 基础配置
# ============================================================

# 系统名称及版本
SYSTEM_NAME = "爱客服AI智能客服系统"
SYSTEM_VERSION = "v2.0.0"

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
# 数据库配置（优先MySQL，回退SQLite）
# ============================================================

# MySQL连接配置（生产环境使用环境变量）
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'aikefu')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'aikefu')

# SQLite回退路径（开发/测试环境）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'aikefu.db')

# 数据库URI：有MySQL密码则用MySQL，否则用SQLite
if MYSQL_PASSWORD or os.environ.get('USE_MYSQL', 'false').lower() == 'true':
    # MySQL连接（使用PyMySQL驱动）
    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}'
        f'@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}'
        f'?charset=utf8mb4'
    )
else:
    # SQLite（开发/测试用）
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

SQLALCHEMY_TRACK_MODIFICATIONS = False
# MySQL连接池配置（SQLite下忽略）
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_recycle': 3600,   # 1小时回收连接，防止MySQL断开
    'pool_pre_ping': True,  # 使用前检测连接是否有效
}


# ============================================================
# 豆包AI配置（字节跳动火山方舟）
# 模型分工：
#   doubao-lite → 意图识别、日常FAQ回复、多轮对话、批量知识生成（速度快成本低）
#   doubao-pro  → 换号/退款决策、情绪安抚（关键决策要更准）
#   doubao-vision-pro → 图片分析（唯一支持图片的多模态模型）
# ============================================================

# 火山方舟API地址
DOUBAO_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"

# API密钥（从火山方舟控制台获取）
DOUBAO_API_KEY = os.environ.get('DOUBAO_API_KEY', '')

# doubao-lite 模型端点（意图识别/FAQ/多轮对话/知识生成，速度快成本低）
DOUBAO_LITE_MODEL = os.environ.get('DOUBAO_LITE_MODEL', 'doubao-lite-32k')

# doubao-pro 模型端点（退款/换号决策、情绪安抚，准确度更高）
DOUBAO_PRO_MODEL = os.environ.get('DOUBAO_PRO_MODEL', 'doubao-pro-32k')

# doubao-vision-pro 模型端点（图片分析，多模态）
DOUBAO_VISION_MODEL = os.environ.get('DOUBAO_VISION_MODEL', 'doubao-vision-pro-32k')

# 兼容旧配置：默认模型（FAQ回复用lite）
DOUBAO_MODEL = DOUBAO_LITE_MODEL

# AI请求超时时间（秒）
DOUBAO_TIMEOUT = 30

# AI回复最大token数
DOUBAO_MAX_TOKENS = 500

# AI温度参数（0.0-1.0，越低越精确）
DOUBAO_TEMPERATURE = 0.3

# 知识库批量生成时的最大token数（通常需要更多输出）
DOUBAO_KB_MAX_TOKENS = 2000


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
# 多轮对话配置
# ============================================================

# 多轮对话上下文保留的最大轮次（每轮=买家+AI各一条）
MAX_CONTEXT_TURNS = 10

# 多轮对话会话超时时间（分钟，超时则重置上下文）
CONTEXT_TIMEOUT_MINUTES = 30


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
        'platform': 'pdd',  # 当前重点支持拼多多
    },
    {
        'code': 'ecommerce',
        'name': '电商客服',
        'description': '通用电商平台客服，适用于各类商品销售',
        'icon': '🛍️',
        'platform': 'pdd',
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
# 黑名单/风险管理配置
# ============================================================

# 触发黑名单的退款次数阈值（30天内超过此次数自动加入风险名单）
BLACKLIST_REFUND_THRESHOLD = 3

# 黑名单检查周期（天）
BLACKLIST_CHECK_PERIOD = 30

# 退款超时预警（小时，距离平台强制退款时间小于此值时标红）
REFUND_URGENT_HOURS = 24


# ============================================================
# 日志配置
# ============================================================

LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_LEVEL = 'INFO'
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5


# ============================================================
# MaxKB向量检索引擎配置（可选）
# 说明：
#   MAXKB_ENABLED=false → 使用原有关键词重叠率检索（默认，0成本）
#   MAXKB_ENABLED=true  → 使用MaxKB语义检索，命中率更高（~85%）
# 部署方式：docker run -d -p 8080:8080 1panel/maxkb
# ============================================================

# 是否启用MaxKB向量检索（默认false，使用关键词检索）
MAXKB_ENABLED = os.environ.get('MAXKB_ENABLED', 'false').lower() == 'true'

# MaxKB服务地址（本地或远程部署）
MAXKB_API_URL = os.environ.get('MAXKB_API_URL', 'http://localhost:8080')

# MaxKB API密钥（在MaxKB后台生成）
MAXKB_API_KEY = os.environ.get('MAXKB_API_KEY', '')

# MaxKB数据集ID（在MaxKB后台创建数据集后获取）
MAXKB_DATASET_ID = os.environ.get('MAXKB_DATASET_ID', '')

# MaxKB语义检索最低相似度阈值（低于此分数不返回结果，避免误匹配）
# 范围：0.0-1.0，默认0.6（可通过环境变量调整）
MAXKB_MIN_SIMILARITY = float(os.environ.get('MAXKB_MIN_SIMILARITY', '0.6'))

