# -*- coding: utf-8 -*-
"""
对话上下文存储适配器
优先使用 Redis（速度快，TTL自动过期），降级到 MySQL
"""

import json
import uuid
from models.database import get_beijing_time


class ContextStore:
    """对话上下文存储（Redis优先，MySQL降级）"""

    def __init__(self):
        from models.database import redis_client
        self._redis = redis_client

    def _key(self, shop_id: int, buyer_id: str) -> str:
        return f"ctx:{shop_id}:{buyer_id}"

    def get_context(self, shop_id: int, buyer_id: str) -> list:
        """获取对话历史（Redis优先）"""
        if self._redis:
            try:
                data = self._redis.get(self._key(shop_id, buyer_id))
                if data:
                    return json.loads(data)
                return []
            except Exception:
                pass
        # 降级：MySQL
        from models import ConversationContext
        ctx = ConversationContext.query.filter_by(
            shop_id=shop_id, buyer_id=buyer_id
        ).first()
        return ctx.get_context() if ctx else []

    def save_context(self, shop_id: int, buyer_id: str, turns: list,
                     timeout_minutes: int = 30):
        """保存对话历史（Redis优先，同步MySQL）"""
        if self._redis:
            try:
                self._redis.setex(
                    self._key(shop_id, buyer_id),
                    timeout_minutes * 60,
                    json.dumps(turns, ensure_ascii=False)
                )
                return
            except Exception:
                pass
        # 降级：MySQL
        from models import ConversationContext
        from models.database import db
        ctx = ConversationContext.query.filter_by(
            shop_id=shop_id, buyer_id=buyer_id
        ).first()
        if not ctx:
            ctx = ConversationContext(
                shop_id=shop_id,
                buyer_id=buyer_id,
                session_id=uuid.uuid4().hex,
                created_at=get_beijing_time(),
            )
            db.session.add(ctx)
        ctx.context_json = json.dumps(turns, ensure_ascii=False)
        ctx.turn_count = len(turns) // 2
        ctx.last_active_at = get_beijing_time()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    def is_expired(self, shop_id: int, buyer_id: str,
                   timeout_minutes: int = 30) -> bool:
        """检查会话是否过期（Redis Key不存在即过期）"""
        if self._redis:
            try:
                return not self._redis.exists(self._key(shop_id, buyer_id))
            except Exception:
                pass
        # 降级：MySQL
        from models import ConversationContext
        ctx = ConversationContext.query.filter_by(
            shop_id=shop_id, buyer_id=buyer_id
        ).first()
        if not ctx:
            return True
        return ctx.is_expired(timeout_minutes)

    def reset(self, shop_id: int, buyer_id: str):
        """重置会话"""
        if self._redis:
            try:
                self._redis.delete(self._key(shop_id, buyer_id))
            except Exception:
                pass
        # 同时重置MySQL
        from models import ConversationContext
        from models.database import db
        ctx = ConversationContext.query.filter_by(
            shop_id=shop_id, buyer_id=buyer_id
        ).first()
        if ctx:
            ctx.reset()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
