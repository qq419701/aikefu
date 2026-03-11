# -*- coding: utf-8 -*-
"""
数据库模型初始化
功能说明：导出所有数据库模型，供其他模块使用
"""

from .database import db, init_db
from .industry import Industry
from .shop import Shop
from .knowledge import KnowledgeBase
from .message import Message, MessageCache
from .user import User
from .blacklist import Blacklist
from .stats import DailyStats
from .conversation import ConversationContext
# RefundRecord 不再导出（退款管理模块已删除），但保留 models/refund.py 防止数据库迁移报错
from .learning import LearningRecord
from .pdd_order import PddOrder
from .plugin import ClientPlugin, PluginTask
from .system_config import SystemConfig

__all__ = [
    'db', 'init_db',
    'Industry', 'Shop',
    'KnowledgeBase',
    'Message', 'MessageCache',
    'User',
    'Blacklist',
    'DailyStats',
    'ConversationContext',
    'LearningRecord',
    'PddOrder',
    'ClientPlugin', 'PluginTask',
    'SystemConfig',
]
