# -*- coding: utf-8 -*-
"""
API接口路由模块
功能说明：提供Webhook回调和AI助手接口，接收平台消息并调用AI引擎处理
支持拼多多等平台的消息推送，以及知识库AI助手功能
"""

import json
import logging
import secrets
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
        order_sn = data.get('order_sn', '') or order_id
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
            order_sn=order_sn,
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


@api_bp.route('/webhook/pdd', methods=['POST'])
def webhook_pdd():
    """
    拼多多Chrome插件消息推送接口
    功能：接收浏览器插件推送的买家消息和订单数据，调用AI引擎处理
    鉴权：使用shop_token（从插件配置中读取，对应后台店铺Token）
    请求格式（JSON）：
    {
        "shop_token": "店铺Token",
        "buyer_id": "买家用户ID",
        "buyer_name": "买家昵称",
        "content": "消息内容",
        "msg_type": "text",
        "order_id": "订单号",
        "order_info": {
            "order_id": "订单号",
            "goods_name": "商品名",
            "amount": 99.00,
            "status": "待发货",
            "create_time": "2026-03-06"
        }
    }
    返回：{'success': True, 'reply': 'AI回复', 'needs_human': False}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求体不能为空'}), 400

        shop_token = data.get('shop_token', '').strip()
        buyer_id = data.get('buyer_id', '').strip()
        buyer_name = data.get('buyer_name', '')
        content = data.get('content', '').strip()
        msg_type = data.get('msg_type', 'text')
        order_id = data.get('order_id', '')
        order_sn = data.get('order_sn', '') or order_id
        order_info_data = data.get('order_info') or {}

        if not shop_token:
            return jsonify({'success': False, 'message': '缺少shop_token'}), 401

        if not buyer_id:
            return jsonify({'success': False, 'message': '缺少buyer_id'}), 400

        if not content:
            return jsonify({'success': False, 'message': '消息内容不能为空'}), 400

        # 通过shop_token查找店铺
        shop = Shop.query.filter_by(shop_token=shop_token, is_active=True).first()
        if not shop:
            return jsonify({'success': False, 'message': 'Token无效或店铺已禁用'}), 401

        # 保存或更新订单数据到PddOrder表
        if order_id and order_info_data:
            _save_pdd_order(shop.id, buyer_id, buyer_name, order_id, order_info_data, data)

        if not shop.auto_reply_enabled:
            return jsonify({'success': True, 'reply': '', 'process_by': 'disabled', 'needs_human': True})

        # 调用AI引擎处理消息
        engine = get_ai_engine()
        result = engine.process_message(
            shop_id=shop.id,
            buyer_id=buyer_id,
            buyer_name=buyer_name,
            message=content,
            order_id=order_id,
            order_sn=order_sn,
            msg_type=msg_type,
        )

        logger.info(f"[PDD插件] shop={shop.id} buyer={buyer_id} "
                    f"process_by={result.get('process_by')} intent={result.get('intent')}")

        return jsonify({
            'success': True,
            'reply': result.get('reply', ''),
            'process_by': result.get('process_by', ''),
            'needs_human': result.get('needs_human', False),
            'emotion_level': result.get('emotion_level', 0),
            'intent': result.get('intent', 'other'),
        })

    except Exception as e:
        logger.error(f"[PDD插件] Webhook处理异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'系统错误: {str(e)}'}), 500


def _save_pdd_order(shop_id: int, buyer_id: str, buyer_name: str,
                    order_id: str, order_info: dict, raw_data: dict):
    """
    保存或更新拼多多订单数据
    功能：插件推送消息时同步持久化订单信息，供AI退款决策使用
    """
    import json as _json
    from models.pdd_order import PddOrder
    from models.database import db, get_beijing_time
    from datetime import datetime

    try:
        # 尝试查找已存在订单（同一店铺+订单号）
        order = PddOrder.query.filter_by(shop_id=shop_id, order_id=order_id).first()
        if not order:
            order = PddOrder(shop_id=shop_id, order_id=order_id)
            db.session.add(order)

        # 更新订单字段
        order.buyer_id = buyer_id
        order.buyer_name = buyer_name
        order.goods_name = order_info.get('goods_name', '')
        order.goods_img = order_info.get('goods_img', '')

        amount_val = order_info.get('amount')
        if amount_val is not None:
            try:
                order.amount = float(amount_val)
            except (ValueError, TypeError):
                pass

        order.quantity = order_info.get('quantity', 1)
        order.status = order_info.get('status', '')
        order.refund_status = order_info.get('refund_status', '')
        order.refund_reason = order_info.get('refund_reason', '')
        order.address = order_info.get('address', '')
        order.captured_at = get_beijing_time()
        order.raw_data = _json.dumps(raw_data, ensure_ascii=False)

        # 解析订单创建时间
        create_time = order_info.get('create_time', '')
        if create_time:
            try:
                order.created_at = datetime.strptime(create_time[:10], '%Y-%m-%d')
            except (ValueError, TypeError):
                pass

        db.session.commit()
    except Exception as e:
        logger.warning(f"[PDD订单] 保存订单失败 order_id={order_id}: {e}")
        db.session.rollback()


@api_bp.route('/shop/token', methods=['GET'])
@login_required
def get_shop_token():
    """
    获取当前店铺的插件认证Token
    功能：运营人员在后台获取Token，复制到Chrome插件配置中
    如果店铺还没有Token，则自动生成并保存
    返回：{'success': True, 'token': '...', 'shop_name': '...'}
    """
    try:
        # 管理员需要指定shop_id，操作员默认取自己行业第一个店铺
        shop_id = request.args.get('shop_id', type=int)
        if shop_id:
            shop = Shop.query.get(shop_id)
        elif not current_user.is_admin():
            shop = Shop.query.filter_by(
                industry_id=current_user.industry_id, is_active=True
            ).first()
        else:
            return jsonify({'success': False, 'message': '管理员请指定shop_id参数'})

        if not shop:
            return jsonify({'success': False, 'message': '店铺不存在'})

        # 无Token则自动生成
        if not shop.shop_token:
            from models.database import db
            shop.generate_token()
            db.session.commit()

        return jsonify({
            'success': True,
            'token': shop.shop_token,
            'shop_id': shop.id,
            'shop_name': shop.name,
        })

    except Exception as e:
        logger.error(f"[API] 获取店铺Token异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/shop/token/regenerate', methods=['POST'])
@login_required
def regenerate_shop_token():
    """
    重新生成店铺Token
    功能：Token泄露时重置，旧Token立即失效
    """
    try:
        request_data = request.get_json(silent=True, force=True) or {}
        if not isinstance(request_data, dict):
            request_data = {}
        shop_id = request_data.get('shop_id')
        shop = Shop.query.get(shop_id) if shop_id else None

        if not shop:
            return jsonify({'success': False, 'message': '店铺不存在'}), 404

        from models.database import db
        shop.generate_token()
        db.session.commit()

        return jsonify({'success': True, 'token': shop.shop_token})

    except Exception as e:
        logger.error(f"[API] 重置Token异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/pdd/orders', methods=['GET'])
@login_required
def pdd_orders():
    """
    获取已抓取的拼多多订单列表（分页）
    功能：供前端订单管理页调用
    参数：shop_id（可选）、buyer_id（可选）、status（可选）、page（页码）
    返回：{'success': True, 'orders': [...], 'total': N, 'pages': N}
    """
    try:
        from models.pdd_order import PddOrder

        page = request.args.get('page', 1, type=int)
        shop_id = request.args.get('shop_id', type=int)
        buyer_id = request.args.get('buyer_id', '')
        status = request.args.get('status', '')
        per_page = request.args.get('per_page', 20, type=int)

        # 权限过滤
        if current_user.is_admin():
            shops = Shop.query.filter_by(is_active=True).all()
        else:
            shops = Shop.query.filter_by(
                industry_id=current_user.industry_id, is_active=True
            ).all()
        shop_ids = [s.id for s in shops]

        query = PddOrder.query.filter(PddOrder.shop_id.in_(shop_ids))

        if shop_id and shop_id in shop_ids:
            query = query.filter_by(shop_id=shop_id)
        if buyer_id:
            query = query.filter(PddOrder.buyer_id.contains(buyer_id))
        if status:
            query = query.filter_by(status=status)

        pagination = query.order_by(PddOrder.captured_at.desc()).paginate(
            page=page, per_page=per_page
        )

        return jsonify({
            'success': True,
            'orders': [o.to_dict() for o in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
        })

    except Exception as e:
        logger.error(f"[API] 获取PDD订单列表异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


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



@api_bp.route('/orders/push', methods=['POST'])
def orders_push():
    """
    客户端推送订单数据接口（V2新增）
    功能：供客户端（dskehuduan）直接推送订单数据到aikefu
    鉴权：X-Shop-Token请求头（店铺Token）
    请求格式（JSON）：
    {
        "orders": [
            {
                "order_id": "订单号",
                "buyer_id": "买家ID",
                "buyer_name": "买家昵称",
                "goods_name": "商品名",
                "amount": 9900,
                "status": "待发货",
                "created_at": "2026-03-09 10:00:00"
            }
        ],
        "source": "client"
    }
    返回：{'success': true, 'created': 新增数量, 'updated': 更新数量}
    """
    # 复用pdd_orders路由中的推送逻辑
    from routes.pdd_orders import push_orders
    return push_orders()
