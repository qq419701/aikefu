# -*- coding: utf-8 -*-
"""
控制面板路由模块
功能说明：系统首页，显示实时监控数据和统计报表
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Message, Shop, Industry, DailyStats
from models.database import get_beijing_time
from datetime import timedelta

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
