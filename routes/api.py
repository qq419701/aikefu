# -*- coding: utf-8 -*-
"""
API接口路由模块
功能说明：提供Webhook回调和AI助手接口，接收平台消息并调用AI引擎处理
支持拼多多等平台的消息推送，以及知识库AI助手功能
"""

import json
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import Shop, Industry
from modules.ai_engine import AIEngine

logger = logging.getLogger(__name__)

# 创建API蓝图
api_bp = Blueprint('api', __name__)

# 全局AI引擎实例（避免重复初始化）
_ai_engine = None


def get_ai_engine() -> AIEngine:
    """
    获取AI引擎单例
    功能：懒加载AI引擎，避免在导入时就初始化
    """
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = AIEngine()
    return _ai_engine


@api_bp.route('/webhook/message', methods=['POST'])
def webhook_message():
    """
    平台消息Webhook回调接口
    功能：接收平台推送的买家消息，调用AI引擎处理
    请求格式（JSON）：
    {
        "shop_id": 店铺ID,
        "buyer_id": "买家ID",
        "buyer_name": "买家昵称",
        "order_id": "订单号",
        "content": "消息内容",
        "msg_type": "text/image",
        "image_url": "图片URL（可选）"
    }
    返回：
    {
        "success": true,
        "reply": "AI回复内容",
        "process_by": "处理方式",
        "needs_human": false,
        "intent": "意图类型"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求体不能为空'}), 400

        shop_id = data.get('shop_id')
        buyer_id = data.get('buyer_id', '')
        buyer_name = data.get('buyer_name', '')
        content = data.get('content', '')
        order_id = data.get('order_id', '')
        msg_type = data.get('msg_type', 'text')
        image_url = data.get('image_url', '')

        if not shop_id or not buyer_id:
            return jsonify({'success': False, 'message': '缺少必要参数: shop_id, buyer_id'}), 400

        if not content and not image_url:
            return jsonify({'success': False, 'message': '消息内容和图片不能同时为空'}), 400

        # 验证店铺是否存在且启用
        shop = Shop.query.get(shop_id)
        if not shop or not shop.is_active:
            return jsonify({'success': False, 'message': '店铺不存在或已禁用'}), 404

        if not shop.auto_reply_enabled:
            return jsonify({'success': True, 'reply': '', 'process_by': 'disabled', 'needs_human': True})

        # 调用AI引擎处理消息
        engine = get_ai_engine()
        result = engine.process_message(
            shop_id=shop_id,
            buyer_id=buyer_id,
            buyer_name=buyer_name,
            message=content,
            order_id=order_id,
            msg_type=msg_type,
            image_url=image_url,
        )

        logger.info(f"[API] shop={shop_id} buyer={buyer_id} process_by={result.get('process_by')} "
                    f"emotion={result.get('emotion_level')} intent={result.get('intent')}")

        return jsonify({
            'success': True,
            'reply': result.get('reply', ''),
            'process_by': result.get('process_by', ''),
            'needs_human': result.get('needs_human', False),
            'emotion_level': result.get('emotion_level', 0),
            'intent': result.get('intent', 'other'),
            'action': result.get('action', ''),
        })

    except Exception as e:
        logger.error(f"[API] Webhook处理异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'}), 500


@api_bp.route('/test-message', methods=['POST'])
def test_message():
    """
    测试消息处理接口（管理后台测试用）
    功能：在后台测试AI回复效果，不需要真实买家消息
    请求格式：
    {
        "shop_id": 店铺ID,
        "message": "测试消息"
    }
    """
    try:
        data = request.get_json()
        shop_id = data.get('shop_id')
        message = data.get('message', '')

        if not shop_id or not message:
            return jsonify({'success': False, 'message': '缺少参数'}), 400

        shop = Shop.query.get(shop_id)
        if not shop:
            return jsonify({'success': False, 'message': '店铺不存在'}), 404

        engine = get_ai_engine()
        result = engine.process_message(
            shop_id=shop_id,
            buyer_id='test_user',
            buyer_name='测试用户',
            message=message,
        )

        return jsonify({
            'success': True,
            'reply': result.get('reply', ''),
            'process_by': result.get('process_by', ''),
            'emotion_level': result.get('emotion_level', 0),
            'intent': result.get('intent', 'other'),
        })

    except Exception as e:
        logger.error(f"[API] 测试消息异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/ai-assistant/chat', methods=['POST'])
@login_required
def ai_assistant_chat():
    """
    AI知识库助手对话接口（知识库页面的AI小窗口）
    功能：运营人员主动问AI，获取行业知识建议和话术模板
    使用doubao-lite模型（成本低，速度快）
    请求格式（JSON）：
    {
        "question": "请问游戏租号行业可能出现什么问题？",
        "industry_id": 1（可选，用于获取行业背景）
    }
    返回：{'success': True, 'reply': 'AI回答'}
    """
    try:
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        industry_id = int(data.get('industry_id') or 0) or None

        if not question:
            return jsonify({'success': False, 'message': '问题不能为空'})

        # 获取行业背景信息（用于增强AI理解）
        context_prompt = ''
        if industry_id:
            industry = Industry.query.get(industry_id)
            if industry:
                context_prompt = (
                    f"当前行业：{industry.name}\n"
                    f"行业描述：{industry.description or ''}\n"
                    f"AI系统提示词：{industry.ai_system_prompt or ''}"
                )

        from modules.doubao_ai import DoubaoAI
        ai = DoubaoAI()
        result = ai.ask_assistant(question, context_prompt)

        return jsonify({
            'success': result.get('success', False),
            'reply': result.get('reply', ''),
            'tokens': result.get('tokens', 0),
        })

    except Exception as e:
        logger.error(f"[API] AI助手异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)})


@api_bp.route('/health', methods=['GET'])
def health():
    """
    健康检查接口
    功能：用于监控系统运行状态（宝塔面板等）
    返回：系统状态信息
    """
    from models.database import get_beijing_time
    import config

    return jsonify({
        'status': 'ok',
        'system': config.SYSTEM_NAME,
        'version': config.SYSTEM_VERSION,
        'time': get_beijing_time().strftime('%Y-%m-%d %H:%M:%S'),
        'timezone': 'Asia/Shanghai (北京时间)',
        'db': 'MySQL' if 'mysql' in config.SQLALCHEMY_DATABASE_URI else 'SQLite',
        'ai_configured': bool(config.DOUBAO_API_KEY),
    })

