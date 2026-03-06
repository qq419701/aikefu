# -*- coding: utf-8 -*-
"""
风险管理路由模块（页面7）
功能说明：管理风险买家、黑名单，监控退款和换号异常，提醒可疑订单
整合黑名单和退款数据，自动分析风险等级
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Blacklist, RefundRecord, Industry
from models.database import db, get_beijing_time

# 创建风险管理蓝图
risk_bp = Blueprint('risk', __name__)


@risk_bp.route('/')
@login_required
def index():
    """
    风险管理首页
    功能：
      - 风险买家列表（自动标记，按风险等级排序）
      - 黑名单管理入口
      - 退款/换号异常统计
      - 可疑订单提醒（高频退款买家）
    """
    industry_id = request.args.get('industry_id', type=int)
    page = request.args.get('page', 1, type=int)

    # 权限过滤
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id, is_active=True
        ).all()
        if not industry_id:
            industry_id = current_user.industry_id

    # 风险买家列表（黑名单，按级别排序）
    bl_query = Blacklist.query.filter_by(is_active=True)
    if industry_id:
        bl_query = bl_query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        bl_query = bl_query.filter_by(industry_id=current_user.industry_id)

    risk_buyers = bl_query.order_by(
        Blacklist.level.desc(), Blacklist.created_at.desc()
    ).paginate(page=page, per_page=20)

    # 退款异常统计（同一买家多次退款）
    from sqlalchemy import func
    rf_query = db.session.query(
        RefundRecord.buyer_id,
        RefundRecord.buyer_name,
        RefundRecord.industry_id,
        func.count(RefundRecord.id).label('refund_count'),
        func.sum(RefundRecord.refund_amount).label('total_amount'),
    ).filter(RefundRecord.is_malicious)

    if industry_id:
        rf_query = rf_query.filter(RefundRecord.industry_id == industry_id)
    elif not current_user.is_admin():
        rf_query = rf_query.filter(
            RefundRecord.industry_id == current_user.industry_id
        )

    malicious_stats = rf_query.group_by(
        RefundRecord.buyer_id, RefundRecord.buyer_name, RefundRecord.industry_id
    ).order_by(func.count(RefundRecord.id).desc()).limit(10).all()
    level_stats = {
        'level1': bl_query.filter(Blacklist.level == 1).count(),
        'level2': bl_query.filter(Blacklist.level == 2).count(),
        'level3': bl_query.filter(Blacklist.level == 3).count(),
    }

    # 本月退款总次数（含恶意）
    from datetime import timedelta
    now = get_beijing_time()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    rf_month_query = RefundRecord.query.filter(RefundRecord.applied_at >= month_start)
    if industry_id:
        rf_month_query = rf_month_query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        rf_month_query = rf_month_query.filter_by(industry_id=current_user.industry_id)

    refund_stats = {
        'month_total': rf_month_query.count(),
        'month_malicious': rf_month_query.filter(RefundRecord.is_malicious).count(),
        'month_rejected': rf_month_query.filter(
            RefundRecord.status.in_(['rejected', 'ai_rejected'])
        ).count(),
    }

    return render_template('risk/index.html',
        risk_buyers=risk_buyers,
        industries=industries,
        selected_industry=industry_id,
        malicious_stats=malicious_stats,
        level_stats=level_stats,
        refund_stats=refund_stats,
    )


@risk_bp.route('/blacklist/<int:entry_id>/upgrade', methods=['POST'])
@login_required
def upgrade_level(entry_id):
    """
    升级黑名单等级
    功能：将风险买家的黑名单等级提升一级（最高3级）
    """
    entry = Blacklist.query.get_or_404(entry_id)

    if not current_user.can_manage_industry(entry.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('risk.index'))

    if entry.level < 3:
        entry.level += 1
        entry.updated_at = get_beijing_time()
        db.session.commit()
        flash(f'已将 {entry.buyer_name or entry.buyer_id} 升级为{entry.level}级风险', 'warning')
    else:
        flash('已是最高风险等级（3级）', 'info')

    return redirect(url_for('risk.index'))


@risk_bp.route('/blacklist/<int:entry_id>/remove', methods=['POST'])
@login_required
def remove_blacklist(entry_id):
    """
    移除黑名单
    功能：将买家从黑名单中移除（标记为不活跃）
    """
    entry = Blacklist.query.get_or_404(entry_id)

    if not current_user.can_manage_industry(entry.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('risk.index'))

    entry.is_active = False
    entry.updated_at = get_beijing_time()
    db.session.commit()

    flash(f'已将 {entry.buyer_name or entry.buyer_id} 从风险名单移除', 'success')
    return redirect(url_for('risk.index'))


@risk_bp.route('/api/summary')
@login_required
def api_summary():
    """
    风险数据汇总API
    功能：返回当前风险统计数据（用于控制面板实时更新）
    返回：JSON格式的风险统计数据
    """
    industry_id = request.args.get('industry_id', type=int)

    bl_query = Blacklist.query.filter_by(is_active=True)
    if industry_id:
        bl_query = bl_query.filter_by(industry_id=industry_id)

    rf_query = RefundRecord.query.filter_by(status='pending')
    if industry_id:
        rf_query = rf_query.filter_by(industry_id=industry_id)

    return jsonify({
        'blacklist_count': bl_query.count(),
        'level3_count': bl_query.filter(Blacklist.level == 3).count(),
        'pending_refunds': rf_query.count(),
        'urgent_refunds': sum(1 for r in rf_query.all() if r.is_urgent()),
    })
