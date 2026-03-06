# -*- coding: utf-8 -*-
"""
统计报表路由模块
功能说明：显示运营数据统计报表，包括AI解决率、成本分析、退款驳回率
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import DailyStats, Shop, Industry
from models.database import get_beijing_time
from datetime import timedelta

# 创建统计蓝图
stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/')
@login_required
def index():
    """
    统计报表首页
    功能：展示近30天的核心运营指标
    """
    now = get_beijing_time()

    # 获取近30天的统计数据
    stats_list = []
    for i in range(29, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')

        if current_user.is_admin():
            # 管理员查所有
            day_stats = DailyStats.query.filter_by(
                stat_date=day_str,
                shop_id=None  # 全局统计
            ).first()
            if not day_stats:
                # 汇总该天所有店铺数据
                shop_stats = DailyStats.query.filter_by(stat_date=day_str).all()
                if shop_stats:
                    day_stats = _aggregate_stats(day_str, shop_stats)
        else:
            # 操作员只看自己行业
            ind_shops = Shop.query.filter_by(
                industry_id=current_user.industry_id
            ).all()
            shop_ids = [s.id for s in ind_shops]
            shop_stats = DailyStats.query.filter(
                DailyStats.stat_date == day_str,
                DailyStats.shop_id.in_(shop_ids) if shop_ids else False,
            ).all()
            day_stats = _aggregate_stats(day_str, shop_stats) if shop_stats else None

        stats_list.append(day_stats or _empty_stats(day_str))

    # 汇总统计
    total_messages = sum(s.get('total_messages', 0) for s in stats_list)
    total_tokens = sum(s.get('total_tokens', 0) for s in stats_list)
    total_cost = sum(s.get('ai_cost', 0.0) for s in stats_list)
    avg_solve_rate = (
        sum(s.get('ai_solve_rate', 0) for s in stats_list) / len(stats_list)
        if stats_list else 0
    )

    return render_template('stats/index.html',
        stats_list=stats_list,
        total_messages=total_messages,
        total_tokens=total_tokens,
        total_cost=round(total_cost, 4),
        avg_solve_rate=round(avg_solve_rate, 1),
        now=now,
    )


@stats_bp.route('/api/chart-data')
@login_required
def chart_data():
    """
    图表数据API
    功能：返回近7天图表所需数据（JSON格式）
    """
    now = get_beijing_time()
    labels = []
    totals = []
    autos = []
    costs = []

    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        labels.append(day.strftime('%m/%d'))

        stats = DailyStats.query.filter_by(stat_date=day_str).all()
        if stats:
            total = sum(s.total_messages or 0 for s in stats)
            auto = sum((s.rule_handled or 0) + (s.knowledge_handled or 0) + (s.ai_handled or 0)
                       for s in stats)
            cost = sum(s.ai_cost or 0.0 for s in stats)
        else:
            total, auto, cost = 0, 0, 0.0

        totals.append(total)
        autos.append(auto)
        costs.append(round(cost, 4))

    return jsonify({
        'labels': labels,
        'totals': totals,
        'autos': autos,
        'costs': costs,
    })


def _aggregate_stats(date_str: str, stats: list) -> dict:
    """
    汇总多店铺统计数据为单条记录
    功能：将多个店铺的当天统计合并为行业总计
    参数：
        date_str - 日期字符串
        stats - DailyStats对象列表
    返回：汇总字典
    """
    total = sum(s.total_messages or 0 for s in stats)
    auto_rule = sum(s.rule_handled or 0 for s in stats)
    auto_kb = sum(s.knowledge_handled or 0 for s in stats)
    auto_ai = sum(s.ai_handled or 0 for s in stats)
    total_auto = auto_rule + auto_kb + auto_ai

    return {
        'stat_date': date_str,
        'total_messages': total,
        'rule_handled': auto_rule,
        'knowledge_handled': auto_kb,
        'ai_handled': auto_ai,
        'total_tokens': sum(s.total_tokens or 0 for s in stats),
        'ai_cost': sum(s.ai_cost or 0.0 for s in stats),
        'ai_solve_rate': round(total_auto / total * 100, 1) if total else 0,
        'refund_count': sum(s.refund_count or 0 for s in stats),
        'refund_rejected': sum(s.refund_rejected or 0 for s in stats),
    }


def _empty_stats(date_str: str) -> dict:
    """
    生成空的统计记录（该日无数据时）
    """
    return {
        'stat_date': date_str,
        'total_messages': 0,
        'rule_handled': 0,
        'knowledge_handled': 0,
        'ai_handled': 0,
        'total_tokens': 0,
        'ai_cost': 0.0,
        'ai_solve_rate': 0,
        'refund_count': 0,
        'refund_rejected': 0,
    }
