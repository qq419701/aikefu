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
from .rule import Rule
from .stats import DailyStats

__all__ = [
    'db', 'init_db',
    'Industry', 'Shop',
    'KnowledgeBase',
    'Message', 'MessageCache',
    'User',
    'Blacklist',
    'Rule',
    'DailyStats',
]
