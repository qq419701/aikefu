# -*- coding: utf-8 -*-
"""
黑名单管理路由模块
功能说明：管理恶意买家黑名单
同一行业的所有店铺共享黑名单，一次拉黑全行业生效
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Blacklist, Industry
from models.database import db, get_beijing_time

# 创建黑名单蓝图
blacklist_bp = Blueprint('blacklist', __name__)


@blacklist_bp.route('/')
@login_required
def index():
    """
    黑名单列表页
    功能：显示恶意买家列表，支持按行业和级别筛选
    """
    industry_id = request.args.get('industry_id', type=int)
    level = request.args.get('level', type=int)
    page = request.args.get('page', 1, type=int)

    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()
        industry_id = industry_id or current_user.industry_id

    query = Blacklist.query
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    if level:
        query = query.filter_by(level=level)

    entries = query.order_by(
        Blacklist.level.desc(),
        Blacklist.created_at.desc()
    ).paginate(page=page, per_page=20)

    return render_template('blacklist/index.html',
        entries=entries,
        industries=industries,
        selected_industry=industry_id,
        selected_level=level,
    )


@blacklist_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    手动添加黑名单
    GET：显示添加表单
    POST：保存新黑名单记录
    """
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()

    if request.method == 'POST':
        industry_id = request.form.get('industry_id', type=int)
        buyer_id = request.form.get('buyer_id', '').strip()
        buyer_name = request.form.get('buyer_name', '').strip()
        reason = request.form.get('reason', '').strip()
        level = request.form.get('level', 1, type=int)

        if not buyer_id or not industry_id:
            flash('买家ID和所属行业为必填项', 'danger')
            return render_template('blacklist/add.html', industries=industries)

        if not current_user.can_manage_industry(industry_id):
            flash('无权限操作', 'danger')
            return render_template('blacklist/add.html', industries=industries)

        # 检查是否已在黑名单
        existing = Blacklist.query.filter_by(
            buyer_id=buyer_id,
            industry_id=industry_id,
        ).first()

        if existing:
            # 升级级别
            existing.level = max(existing.level, level)
            existing.reason = reason
            existing.is_active = True
            existing.updated_at = get_beijing_time()
            flash(f'买家 {buyer_id} 黑名单已更新', 'info')
        else:
            entry = Blacklist(
                industry_id=industry_id,
                buyer_id=buyer_id,
                buyer_name=buyer_name,
                reason=reason,
                level=level,
                is_active=True,
                created_at=get_beijing_time(),
            )
            db.session.add(entry)
            flash(f'买家 {buyer_id} 已加入黑名单', 'success')

        db.session.commit()
        return redirect(url_for('blacklist.index', industry_id=industry_id))

    return render_template('blacklist/add.html', industries=industries)


@blacklist_bp.route('/<int:entry_id>/remove', methods=['POST'])
@login_required
def remove(entry_id):
    """
    解除黑名单
    功能：将买家从黑名单中移除（设为不活跃，保留记录）
    """
    entry = Blacklist.query.get_or_404(entry_id)

    if not current_user.can_manage_industry(entry.industry_id):
        return jsonify({'success': False, 'message': '无权限'}), 403

    entry.is_active = False
    entry.updated_at = get_beijing_time()
    db.session.commit()

    return jsonify({'success': True, 'message': '已解除黑名单'})
