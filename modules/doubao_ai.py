# -*- coding: utf-8 -*-
"""
豆包AI模块（三层处理 - 第三层）
功能说明：调用字节跳动火山方舟豆包AI API，处理复杂问题
包含缓存机制，相同问题直接返回缓存，节省约80%费用
"""

import hashlib
import json
import time
import requests
from datetime import datetime, timedelta
from models import MessageCache
from models.database import db, get_beijing_time
import config


class DoubaoAI:
    """
    豆包AI接口封装
    说明：调用火山方舟API生成AI回复
    内置缓存机制，相同或相似问题复用缓存
    """

    def __init__(self):
        """初始化豆包AI模块"""
        self.api_base = config.DOUBAO_API_BASE
        self.api_key = config.DOUBAO_API_KEY
        self.model = config.DOUBAO_MODEL
        self.vision_model = config.DOUBAO_VISION_MODEL
        self.timeout = config.DOUBAO_TIMEOUT
        self.max_tokens = config.DOUBAO_MAX_TOKENS
        self.temperature = config.DOUBAO_TEMPERATURE

    def chat(self, message: str, system_prompt: str, industry_id: int,
             use_cache: bool = True) -> dict:
        """
        调用豆包AI生成回复（文字）
        功能：先查询缓存，缓存未命中再调用API
        参数：
            message - 买家消息
            system_prompt - 系统提示词（行业专属）
            industry_id - 行业ID（用于缓存隔离）
            use_cache - 是否使用缓存（默认True）
        返回：
            {'reply': '回复内容', 'from_cache': 是否来自缓存, 'tokens': 消耗token数}
        """
        # 1. 检查缓存
        if use_cache:
            cached = self._get_cache(message, industry_id)
            if cached:
                return {
                    'reply': cached.answer,
                    'from_cache': True,
                    'tokens': 0,
                    'success': True,
                }

        # 2. API未配置时返回默认回复
        if not self.api_key:
            return {
                'reply': '您好，我是AI客服，稍后将由人工客服为您服务，请稍候。',
                'from_cache': False,
                'tokens': 0,
                'success': False,
                'error': 'API未配置',
            }

        # 3. 调用豆包API
        try:
            result = self._call_api(message, system_prompt)
            if result['success']:
                # 存入缓存
                if use_cache:
                    self._save_cache(message, result['reply'], industry_id)
                return result
            else:
                return result
        except Exception as e:
            return {
                'reply': '您好，系统处理中遇到问题，请稍候再试。',
                'from_cache': False,
                'tokens': 0,
                'success': False,
                'error': str(e),
            }

    def analyze_image(self, image_url: str, message: str, system_prompt: str) -> dict:
        """
        调用豆包Vision模型分析图片（豆包Vision图片识别）
        功能：识别买家发送的截图，判断问题类型
        参数：
            image_url - 图片URL
            message - 买家描述（如有）
            system_prompt - 系统提示词
        返回：{'reply': '分析结果', 'success': True/False}
        """
        if not self.api_key:
            return {
                'reply': '收到您的截图，我会尽快处理，请稍等。',
                'success': False,
                'error': 'API未配置',
            }

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            # 构造图片分析请求（多模态消息格式）
            payload = {
                'model': self.vision_model,
                'messages': [
                    {
                        'role': 'system',
                        'content': system_prompt or '你是专业的游戏租号客服，请分析买家截图并给出处理建议。',
                    },
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image_url',
                                'image_url': {'url': image_url},
                            },
                            {
                                'type': 'text',
                                'text': message or '请分析这张截图',
                            }
                        ],
                    }
                ],
                'max_tokens': self.max_tokens,
            }

            response = requests.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                reply = data['choices'][0]['message']['content']
                tokens = data.get('usage', {}).get('total_tokens', 0)
                return {
                    'reply': reply,
                    'success': True,
                    'tokens': tokens,
                }
            else:
                return {
                    'reply': '收到您的截图，正在处理中。',
                    'success': False,
                    'error': f'API返回错误: {response.status_code}',
                }

        except Exception as e:
            return {
                'reply': '收到您的截图，请稍候处理。',
                'success': False,
                'error': str(e),
            }

    def _call_api(self, message: str, system_prompt: str) -> dict:
        """
        实际调用火山方舟API
        功能：发送HTTP请求到豆包API并解析响应
        参数：
            message - 用户消息
            system_prompt - 系统提示词
        返回：{'reply': 回复内容, 'tokens': token消耗, 'success': 是否成功}
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': system_prompt or '你是专业的AI客服助手，请礼貌、简洁地回答用户问题。',
                },
                {
                    'role': 'user',
                    'content': message,
                }
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }

        response = requests.post(
            f'{self.api_base}/chat/completions',
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code == 200:
            data = response.json()
            reply = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)
            return {
                'reply': reply,
                'from_cache': False,
                'tokens': tokens,
                'success': True,
            }
        else:
            return {
                'reply': '抱歉，我暂时无法处理您的请求，请稍后再试。',
                'from_cache': False,
                'tokens': 0,
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text[:200]}',
            }

    def _get_cache(self, message: str, industry_id: int) -> MessageCache | None:
        """
        查询消息回复缓存
        功能：计算消息哈希，在缓存表中查找有效缓存
        参数：
            message - 消息内容
            industry_id - 行业ID
        返回：缓存对象（有效）或 None
        """
        msg_hash = self._hash_message(message)
        cache = MessageCache.query.filter_by(
            industry_id=industry_id,
            question_hash=msg_hash,
        ).first()

        if cache and cache.is_valid():
            # 更新命中次数
            cache.hit_count = (cache.hit_count or 0) + 1
            db.session.commit()
            return cache

        return None

    def _save_cache(self, message: str, answer: str, industry_id: int):
        """
        保存AI回复到缓存
        功能：将AI生成的回复缓存，有效期24小时
        参数：
            message - 原始问题
            answer - AI回复
            industry_id - 行业ID
        """
        msg_hash = self._hash_message(message)
        now = get_beijing_time()
        expires = now + timedelta(seconds=config.CACHE_TTL)

        # 更新或创建缓存
        cache = MessageCache.query.filter_by(
            industry_id=industry_id,
            question_hash=msg_hash,
        ).first()

        if cache:
            cache.answer = answer
            cache.expires_at = expires
        else:
            cache = MessageCache(
                industry_id=industry_id,
                question_hash=msg_hash,
                question=message,
                answer=answer,
                created_at=now,
                expires_at=expires,
            )
            db.session.add(cache)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    def _hash_message(self, message: str) -> str:
        """
        计算消息的哈希值（用于缓存键）
        功能：对消息标准化后计算MD5哈希
        """
        # 标准化：去除多余空格，转小写
        normalized = ' '.join(message.lower().split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
