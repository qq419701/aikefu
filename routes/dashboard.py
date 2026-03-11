# -*- coding: utf-8 -*-
"""
控制面板路由模块
功能说明：系统首页，显示实时监控数据和统计报表
"""

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import Message, Shop, Industry, DailyStats
from models.database import get_beijing_time
from datetime import timedelta
import config

# 创建控制面板蓝图
dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """
    系统首页 - 控制面板
    功能：显示系统概览数据、今日统计、最新消息
    """
    now = get_beijing_time()
    today = now.strftime('%Y-%m-%d')

    # 根据用户权限获取数据范围
    if current_user.is_admin():
        # 超管看所有数据
        shops = Shop.query.filter_by(is_active=True).all()
        shop_ids = [s.id for s in shops]
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        # 操作员只看自己行业的数据
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id,
            is_active=True
        ).all()
        shop_ids = [s.id for s in shops]

    # 今日统计数据
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if shop_ids:
        today_messages = Message.query.filter(
            Message.shop_id.in_(shop_ids),
            Message.direction == 'in',
            Message.msg_time >= today_start,
        ).count()

        # 今日AI自动处理数
        today_auto = Message.query.filter(
            Message.shop_id.in_(shop_ids),
            Message.direction == 'in',
            Message.msg_time >= today_start,
            Message.process_by.in_(['rule', 'knowledge', 'ai', 'ai_vision']),
        ).count()

        # 今日需人工处理数
        today_human = Message.query.filter(
            Message.shop_id.in_(shop_ids),
            Message.direction == 'in',
            Message.msg_time >= today_start,
            Message.needs_human == True,
        ).count()

        # 最新10条消息
        recent_messages = Message.query.filter(
            Message.shop_id.in_(shop_ids),
            Message.direction == 'in',
        ).order_by(Message.msg_time.desc()).limit(10).all()
    else:
        today_messages = 0
        today_auto = 0
        today_human = 0
        recent_messages = []

    # 计算AI自动解决率
    ai_solve_rate = round(today_auto / today_messages * 100, 1) if today_messages else 0

    # 近7天统计数据（用于图表）
    week_stats = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        stat = DailyStats.query.filter_by(stat_date=day_str).first()
        week_stats.append({
            'date': day_str,
            'date_short': day.strftime('%m/%d'),
            'total': stat.total_messages if stat else 0,
            'auto': (stat.rule_handled + stat.knowledge_handled + stat.ai_handled) if stat else 0,
        })

    return render_template('dashboard.html',
        total_shops=len(shops),
        total_industries=len(industries),
        today_messages=today_messages,
        today_auto=today_auto,
        today_human=today_human,
        ai_solve_rate=ai_solve_rate,
        recent_messages=recent_messages,
        week_stats=week_stats,
        now=now,
    )


@dashboard_bp.route('/health')
@login_required
def health():
    """
    系统健康状态API（前端每30秒轮询）
    返回各组件的连接状态和今日统计
    """
    now = get_beijing_time()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = {}

    # 1. 插件在线状态
    try:
        from models.plugin import ClientPlugin
        total_plugins = ClientPlugin.query.filter_by(is_active=True).count()
        online_plugins = sum(1 for p in ClientPlugin.query.filter_by(is_active=True).all() if p.is_online())
        result['plugin'] = {
            'total': total_plugins,
            'online': online_plugins,
            'status': 'ok' if online_plugins > 0 else 'warn'
        }
    except Exception:
        result['plugin'] = {'total': 0, 'online': 0, 'status': 'error'}

    # 2. MaxKB连接状态
    try:
        from models.system_config import SystemConfig
        maxkb_enabled = SystemConfig.get('maxkb_enabled', config.MAXKB_ENABLED)
        if maxkb_enabled:
            from modules.maxkb_client import MaxKBClient
            ok = MaxKBClient().health_check()
            result['maxkb'] = {'enabled': True, 'status': 'ok' if ok else 'error'}
        else:
            result['maxkb'] = {'enabled': False, 'status': 'disabled'}
    except Exception:
        result['maxkb'] = {'enabled': False, 'status': 'error'}

    # 3. 豆包AI状态（检查API Key是否配置）
    try:
        from models.system_config import SystemConfig
        api_key = SystemConfig.get('doubao_api_key', config.DOUBAO_API_KEY)
        result['doubao'] = {
            'configured': bool(api_key),
            'status': 'ok' if api_key else 'warn'
        }
    except Exception:
        result['doubao'] = {'configured': False, 'status': 'warn'}

    # 4. 今日各层命中率
    try:
        if current_user.is_admin():
            shops = Shop.query.filter_by(is_active=True).all()
        else:
            shops = Shop.query.filter_by(industry_id=current_user.industry_id).all()
        shop_ids = [s.id for s in shops]

        base = Message.query.filter(
            Message.shop_id.in_(shop_ids),
            Message.direction == 'in',
            Message.msg_time >= today_start,
        )
        total = base.count()
        intent_plugin = base.filter(Message.process_by.in_(['plugin', 'intent_reply'])).count()
        knowledge = base.filter(Message.process_by == 'knowledge').count()
        ai = base.filter(Message.process_by.in_(['ai', 'ai_vision', 'human'])).count()
        result['layers'] = {
            'total': total,
            'intent_plugin': intent_plugin,
            'knowledge': knowledge,
            'ai': ai,
        }
    except Exception:
        result['layers'] = {'total': 0, 'intent_plugin': 0, 'knowledge': 0, 'ai': 0}

    return jsonify(result)
