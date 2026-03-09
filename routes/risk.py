# -*- coding: utf-8 -*-
"""
风险管理路由模块
功能说明：管理风险买家、黑名单，监控可疑买家，提醒操作人员
V2重构：退款管理模块已删除，风险管理只保留黑名单功能
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Blacklist, Industry
from models.database import db, get_beijing_time

# 创建风险管理蓝图
risk_bp = Blueprint('risk', __name__)


@risk_bp.route('/')
@login_required
def index():
    """
    风险管理首页
    功能：
      - 风险买家列表（黑名单，按风险等级排序）
      - 黑名单管理入口
      - 各风险等级统计
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

    # 各风险等级统计
    level_stats = {
        'level1': bl_query.filter(Blacklist.level == 1).count(),
        'level2': bl_query.filter(Blacklist.level == 2).count(),
        'level3': bl_query.filter(Blacklist.level == 3).count(),
    }

    return render_template('risk/index.html',
        risk_buyers=risk_buyers,
        industries=industries,
        selected_industry=industry_id,
        malicious_stats=[],         # V2已删除退款管理，此处返回空列表
        level_stats=level_stats,
        refund_stats={              # V2已删除退款管理，此处返回空统计
            'month_total': 0,
            'month_malicious': 0,
            'month_rejected': 0,
        },
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
    V2说明：退款管理已删除，urgent_refunds和pending_refunds均返回0
    """
    industry_id = request.args.get('industry_id', type=int)

    bl_query = Blacklist.query.filter_by(is_active=True)
    if industry_id:
        bl_query = bl_query.filter_by(industry_id=industry_id)

    return jsonify({
        'blacklist_count': bl_query.count(),
        'level3_count': bl_query.filter(Blacklist.level == 3).count(),
        'pending_refunds': 0,   # V2已删除退款管理
        'urgent_refunds': 0,    # V2已删除退款管理
    })
