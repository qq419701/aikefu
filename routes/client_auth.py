# -*- coding: utf-8 -*-
"""
客户端账号认证路由模块
功能说明：为桌面客户端（dskehuduan）提供账号登录、多店铺同步等API接口
客户端通过账号密码登录后获得 client_token，再用 token 拉取名下所有店铺列表
（含 shop_token），实现一个客户端管理多个店铺。

Token 存储策略：
  - 优先使用 Redis：key = client_token:{token}，value = username，TTL = 604800（7天）
  - Redis 不可用时降级为模块级内存字典 _token_store

接口列表：
  POST /api/client/login       - 账号密码登录，返回 client_token
  GET  /api/client/shops       - 获取当前用户名下的店铺列表（含 shop_token）
  POST /api/client/logout      - 使 token 失效
  POST /api/client/refresh     - 刷新 token 有效期（再续 7 天）
"""

import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash

from models import Shop
from models.user import User
import models.database as _db_mod

# ----------------------------------------------------------------
# 蓝图定义
# ----------------------------------------------------------------
client_auth_bp = Blueprint('client_auth', __name__)

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------
# Token 有效期（7 天，单位秒）
# ----------------------------------------------------------------
TOKEN_TTL = 604800  # 7 * 24 * 3600

# ----------------------------------------------------------------
# 内存降级存储
# 结构：{token: {"username": str, "expires_at": datetime}}
# 仅在 Redis 不可用时使用
# ----------------------------------------------------------------
_token_store: dict = {}


# ================================================================
# 辅助函数
# ================================================================

def _make_redis_key(token: str) -> str:
    """生成 Redis 存储键"""
    return f"client_token:{token}"


def _store_token(token: str, username: str) -> None:
    """
    持久化 client_token
    优先写入 Redis；Redis 不可用时写入内存字典
    """
    rc = _db_mod.redis_client
    if rc is not None:
        try:
            rc.setex(_make_redis_key(token), TOKEN_TTL, username)
            return
        except Exception as e:
            logger.warning("Redis 写入失败，降级内存存储: %s", e)

    # 降级：写内存字典
    _token_store[token] = {
        "username": username,
        "expires_at": datetime.utcnow() + timedelta(seconds=TOKEN_TTL),
    }


def _refresh_token(token: str) -> bool:
    """
    刷新 token 有效期（续期 TOKEN_TTL 秒）
    返回 True 表示刷新成功，False 表示 token 不存在
    """
    rc = _db_mod.redis_client
    if rc is not None:
        try:
            key = _make_redis_key(token)
            if rc.exists(key):
                rc.expire(key, TOKEN_TTL)
                return True
            return False
        except Exception as e:
            logger.warning("Redis 刷新失败，尝试内存存储: %s", e)

    # 降级：刷新内存字典
    entry = _token_store.get(token)
    if entry and entry["expires_at"] > datetime.utcnow():
        entry["expires_at"] = datetime.utcnow() + timedelta(seconds=TOKEN_TTL)
        return True
    return False


def _delete_token(token: str) -> None:
    """
    使 token 失效
    优先删除 Redis 中的记录；降级删除内存字典中的记录
    """
    rc = _db_mod.redis_client
    if rc is not None:
        try:
            rc.delete(_make_redis_key(token))
            return
        except Exception as e:
            logger.warning("Redis 删除失败，尝试内存存储: %s", e)

    # 降级：删除内存字典
    _token_store.pop(token, None)


def _verify_client_token(token: str) -> Optional[User]:
    """
    验证 client_token，返回对应 User 对象；失败返回 None
    先查 Redis，降级查内存字典
    """
    if not token:
        return None

    username = None

    # 优先查 Redis
    rc = _db_mod.redis_client
    if rc is not None:
        try:
            val = rc.get(_make_redis_key(token))
            if val:
                username = val.decode('utf-8') if isinstance(val, bytes) else val
        except Exception as e:
            logger.warning("Redis 读取失败，降级内存存储: %s", e)

    # 降级查内存字典
    if username is None:
        entry = _token_store.get(token)
        if entry and entry["expires_at"] > datetime.utcnow():
            username = entry["username"]

    if not username:
        return None

    # 通过 username 查数据库
    user = User.query.filter_by(username=username, is_active=True).first()
    return user


# ================================================================
# 接口：POST /api/client/login
# ================================================================

@client_auth_bp.route('/login', methods=['POST'])
def client_login():
    """
    客户端账号登录
    请求体：{"username": "admin", "password": "xxx"}
    成功返回：{"success": true, "client_token": "...", "username": "...",
               "display_name": "...", "expires_in": 604800}
    失败返回：401
    """
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    # 查用户
    user = User.query.filter_by(username=username, is_active=True).first()
    if not user or not check_password_hash(user.password_hash, password):
        logger.warning("客户端登录失败，用户名或密码错误: %s", username)
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    # 生成 token 并存储
    token = secrets.token_hex(32)
    _store_token(token, user.username)

    logger.info("客户端登录成功: %s", username)
    return jsonify({
        "success": True,
        "client_token": token,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "expires_in": TOKEN_TTL,
    })


# ================================================================
# 接口：GET /api/client/shops
# ================================================================

@client_auth_bp.route('/shops', methods=['GET'])
def client_shops():
    """
    获取当前用户名下的店铺列表（含 shop_token）
    请求头：X-Client-Token: <client_token>
    成功返回：{"success": true, "shops": [...]}
    每个店铺包含 shop_token 字段，供客户端插件鉴权使用
    权限规则：
      - 管理员：返回所有激活店铺
      - 普通用户：返回该用户 industry_id 对应的激活店铺
    """
    token = request.headers.get('X-Client-Token', '').strip()
    user = _verify_client_token(token)
    if not user:
        return jsonify({"success": False, "message": "token 无效或已过期，请重新登录"}), 401

    # 根据角色查询店铺
    if user.is_admin():
        # 管理员返回所有激活店铺
        shops = Shop.query.filter_by(is_active=True).all()
    else:
        # 普通用户只返回同行业的激活店铺
        shops = Shop.query.filter_by(industry_id=user.industry_id, is_active=True).all()

    shop_list = []
    for shop in shops:
        shop_list.append({
            "id": shop.id,
            "name": shop.name,
            "platform": shop.platform,
            "platform_shop_id": shop.platform_shop_id,
            "shop_token": shop.shop_token,
            "is_active": shop.is_active,
            "auto_reply_enabled": shop.auto_reply_enabled,
        })

    return jsonify({"success": True, "shops": shop_list})


# ================================================================
# 接口：POST /api/client/logout
# ================================================================

@client_auth_bp.route('/logout', methods=['POST'])
def client_logout():
    """
    客户端退出登录
    请求头：X-Client-Token: <client_token>
    成功返回：{"success": true}
    """
    token = request.headers.get('X-Client-Token', '').strip()
    if not token:
        return jsonify({"success": False, "message": "缺少 X-Client-Token 请求头"}), 400

    _delete_token(token)
    logger.info("客户端登出: token=%s...", token[:8] if token else '')
    return jsonify({"success": True})


# ================================================================
# 接口：POST /api/client/refresh
# ================================================================

@client_auth_bp.route('/refresh', methods=['POST'])
def client_refresh():
    """
    刷新 client_token 有效期（续期 7 天）
    请求头：X-Client-Token: <client_token>
    成功返回：{"success": true, "expires_in": 604800}
    失败返回：401
    """
    token = request.headers.get('X-Client-Token', '').strip()
    if not token:
        return jsonify({"success": False, "message": "缺少 X-Client-Token 请求头"}), 400

    # 先验证 token 是否有效
    user = _verify_client_token(token)
    if not user:
        return jsonify({"success": False, "message": "token 无效或已过期，请重新登录"}), 401

    # 刷新有效期
    _refresh_token(token)

    return jsonify({"success": True, "expires_in": TOKEN_TTL})
