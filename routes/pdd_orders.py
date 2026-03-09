# -*- coding: utf-8 -*-
"""
拼多多订单管理路由模块
功能说明：展示订单数据，支持多来源（客户端采集/浏览器插件/手动录入）
V2新增：
  - 来源筛选（客户端采集/浏览器插件/手动录入）
  - POST /api/orders/push API（供客户端直接推送订单数据，shop_token鉴权）
预留扩展：其他平台（淘宝、京东、抖店）可参照此文件创建对应路由
"""

import json
import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import Shop, Message
from models.pdd_order import PddOrder
from models.database import db, get_beijing_time

# 创建PDD订单蓝图
pdd_orders_bp = Blueprint('pdd_orders', __name__)

logger = logging.getLogger(__name__)


@pdd_orders_bp.route('/')
@login_required
def index():
    """
    拼多多订单列表页
    功能：分页展示所有已采集的订单，支持按店铺、买家、状态、来源筛选
    """
    page = request.args.get('page', 1, type=int)
    shop_id = request.args.get('shop_id', type=int)
    buyer_q = request.args.get('buyer', '').strip()
    order_q = request.args.get('order', '').strip()
    status_filter = request.args.get('status', '').strip()
    # V2新增：来源筛选
    source_filter = request.args.get('source', '').strip()

    # 获取当前用户可见的店铺
    if current_user.is_admin():
        shops = Shop.query.filter_by(is_active=True).all()
    else:
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id, is_active=True
        ).all()

    shop_ids = [s.id for s in shops]

    # 构建订单查询
    query = PddOrder.query.filter(PddOrder.shop_id.in_(shop_ids))

    if shop_id and shop_id in shop_ids:
        query = query.filter_by(shop_id=shop_id)
    if buyer_q:
        query = query.filter(
            (PddOrder.buyer_id.contains(buyer_q)) |
            (PddOrder.buyer_name.contains(buyer_q))
        )
    if order_q:
        query = query.filter(PddOrder.order_id.contains(order_q))
    if status_filter:
        query = query.filter_by(status=status_filter)
    # V2新增：按来源筛选
    if source_filter:
        query = query.filter_by(source=source_filter)

    orders = query.order_by(PddOrder.captured_at.desc()).paginate(
        page=page, per_page=20
    )

    return render_template(
        'pdd_orders/index.html',
        orders=orders,
        shops=shops,
        selected_shop=shop_id,
        buyer_q=buyer_q,
        order_q=order_q,
        status_filter=status_filter,
        source_filter=source_filter,
        status_options=['待付款', '待发货', '已发货', '已完成', '退款中', '已退款'],
        # 来源选项（V2新增）
        source_options=[
            ('client', '客户端采集'),
            ('browser_plugin', '浏览器插件'),
            ('manual', '手动录入'),
        ],
    )


@pdd_orders_bp.route('/<order_id>')
@login_required
def detail(order_id: str):
    """
    拼多多订单详情页
    功能：展示订单完整信息，以及该买家在该店铺的所有聊天记录
    """
    # 权限：只查看当前用户可访问店铺下的订单
    if current_user.is_admin():
        shop_ids = [s.id for s in Shop.query.filter_by(is_active=True).all()]
    else:
        shop_ids = [s.id for s in Shop.query.filter_by(
            industry_id=current_user.industry_id, is_active=True
        ).all()]

    order = PddOrder.query.filter(
        PddOrder.order_id == order_id,
        PddOrder.shop_id.in_(shop_ids),
    ).first_or_404()

    # 查询该买家在该店铺的聊天记录
    messages = Message.query.filter_by(
        shop_id=order.shop_id,
        buyer_id=order.buyer_id,
    ).order_by(Message.msg_time.desc()).limit(50).all()

    return render_template(
        'pdd_orders/detail.html',
        order=order,
        messages=messages,
    )


# ================================================================
# 客户端推送API（用shop_token鉴权，无需登录）
# ================================================================

@pdd_orders_bp.route('/api/orders/push', methods=['POST'])
def push_orders():
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
                "amount": 9900,        // 订单金额（分），传整数
                "status": "待发货",
                "created_at": "2026-03-09 10:00:00"
            }
        ],
        "source": "client"             // 数据来源（client/browser_plugin/manual）
    }
    返回：{'success': true, 'created': 新增数量, 'updated': 更新数量}
    """
    # 从请求头获取shop_token并验证
    token = request.headers.get('X-Shop-Token', '').strip()
    if not token:
        return jsonify({'success': False, 'message': '缺少X-Shop-Token请求头'}), 401

    shop = Shop.query.filter_by(shop_token=token, is_active=True).first()
    if not shop:
        return jsonify({'success': False, 'message': 'shop_token无效或店铺不存在'}), 401

    data = request.get_json() or {}
    orders_data = data.get('orders', [])
    source = data.get('source', 'client')

    if not orders_data:
        return jsonify({'success': False, 'message': '没有订单数据'}), 400

    # 验证source合法性
    valid_sources = ('client', 'browser_plugin', 'manual')
    if source not in valid_sources:
        source = 'client'

    created_count = 0
    updated_count = 0
    now = get_beijing_time()

    try:
        for order_item in orders_data:
            order_id = str(order_item.get('order_id', '')).strip()
            if not order_id:
                continue  # 跳过没有订单号的记录

            # 查找是否已存在（按shop_id+order_id唯一）
            existing = PddOrder.query.filter_by(
                shop_id=shop.id,
                order_id=order_id,
            ).first()

            # 处理金额（可能是分或元，统一转为数值）
            amount_raw = order_item.get('amount', 0)
            try:
                amount = float(amount_raw) / 100 if int(amount_raw) > 10000 else float(amount_raw)
            except Exception:
                amount = 0.0

            # 处理创建时间
            created_at_str = order_item.get('created_at', '')
            created_at = None
            if created_at_str:
                try:
                    from datetime import datetime
                    created_at = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass

            if existing:
                # 更新已有订单
                existing.buyer_name = order_item.get('buyer_name', existing.buyer_name) or existing.buyer_name
                existing.goods_name = order_item.get('goods_name', existing.goods_name) or existing.goods_name
                existing.amount = amount or existing.amount
                existing.status = order_item.get('status', existing.status) or existing.status
                existing.source = source
                existing.captured_at = now
                updated_count += 1
            else:
                # 创建新订单
                new_order = PddOrder(
                    shop_id=shop.id,
                    order_id=order_id,
                    buyer_id=str(order_item.get('buyer_id', '')),
                    buyer_name=order_item.get('buyer_name', ''),
                    goods_name=order_item.get('goods_name', ''),
                    amount=amount,
                    quantity=int(order_item.get('quantity', 1)),
                    status=order_item.get('status', ''),
                    source=source,
                    created_at=created_at,
                    captured_at=now,
                    raw_data=json.dumps(order_item, ensure_ascii=False),
                )
                db.session.add(new_order)
                created_count += 1

        db.session.commit()
        logger.info(f"[订单推送] shop={shop.name}, created={created_count}, "
                    f"updated={updated_count}, source={source}")
        return jsonify({
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'total': created_count + updated_count,
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"[订单推送] 处理异常: {e}")
        return jsonify({'success': False, 'message': f'处理失败: {str(e)}'}), 500
