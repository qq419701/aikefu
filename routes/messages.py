# -*- coding: utf-8 -*-
"""
消息管理路由模块
功能说明：查看所有消息记录，支持人工回复和消息筛选
实时监控买家消息，处理需要人工干预的情况
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Message, Shop
from models.database import db, get_beijing_time

# 创建消息管理蓝图
messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/')
@login_required
def index():
    """
    消息列表页
    功能：显示所有消息，支持按店铺、状态、日期筛选
    """
    page = request.args.get('page', 1, type=int)
    shop_id = request.args.get('shop_id', type=int)
    status_filter = request.args.get('status', '')
    needs_human = request.args.get('needs_human', '')

    # 获取可见店铺
    if current_user.is_admin():
        shops = Shop.query.filter_by(is_active=True).all()
    else:
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id
        ).all()

    shop_ids = [s.id for s in shops]

    # 构建查询
    query = Message.query.filter(
        Message.shop_id.in_(shop_ids),
        Message.direction == 'in',
    )

    if shop_id and shop_id in shop_ids:
        query = query.filter_by(shop_id=shop_id)

    if status_filter:
        query = query.filter_by(status=status_filter)

    if needs_human == '1':
        query = query.filter_by(needs_human=True)

    # 统计待人工处理数
    pending_human = Message.query.filter(
        Message.shop_id.in_(shop_ids),
        Message.needs_human == True,
        Message.is_transferred == False,
    ).count()

    messages = query.order_by(Message.msg_time.desc()).paginate(page=page, per_page=30)

    return render_template('messages/index.html',
        messages=messages,
        shops=shops,
        selected_shop=shop_id,
        status_filter=status_filter,
        needs_human_filter=needs_human,
        pending_human=pending_human,
    )


@messages_bp.route('/<int:msg_id>/mark-handled', methods=['POST'])
@login_required
def mark_handled(msg_id):
    """
    标记消息为人工处理完成
    功能：人工客服处理完毕后标记，更新状态
    """
    msg = Message.query.get_or_404(msg_id)

    # 权限检查（通过店铺行业判断）
    shop = Shop.query.get(msg.shop_id)
    if shop and not current_user.can_manage_industry(shop.industry_id):
        return jsonify({'success': False, 'message': '无权限'}), 403

    msg.is_transferred = True
    msg.status = 'processed'
    msg.processed_at = get_beijing_time()
    db.session.commit()

    return jsonify({'success': True, 'message': '已标记为处理完成'})


@messages_bp.route('/api/stats')
@login_required
def api_stats():
    """
    消息实时统计API
    功能：前端定时拉取，实时更新控制面板数据
    返回：今日消息统计JSON
    """
    now = get_beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if current_user.is_admin():
        shops = Shop.query.filter_by(is_active=True).all()
    else:
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id
        ).all()

    shop_ids = [s.id for s in shops]

    if not shop_ids:
        return jsonify({'total': 0, 'auto': 0, 'human': 0, 'rate': 0, 'pending': 0})

    total = Message.query.filter(
        Message.shop_id.in_(shop_ids),
        Message.direction == 'in',
        Message.msg_time >= today_start,
    ).count()

    auto = Message.query.filter(
        Message.shop_id.in_(shop_ids),
        Message.direction == 'in',
        Message.msg_time >= today_start,
        Message.process_by.in_(['rule', 'knowledge', 'ai', 'ai_vision']),
    ).count()

    pending = Message.query.filter(
        Message.shop_id.in_(shop_ids),
        Message.needs_human == True,
        Message.is_transferred == False,
    ).count()

    rate = round(auto / total * 100, 1) if total else 0

    return jsonify({
        'total': total,
        'auto': auto,
        'human': total - auto,
        'rate': rate,
        'pending': pending,
    })
