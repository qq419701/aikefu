# -*- coding: utf-8 -*-
"""
行业管理路由模块
功能说明：多行业配置管理，支持添加、编辑、删除行业
管理员可设置每个行业的AI提示词、功能开关等
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Industry
from models.database import db, get_beijing_time

# 创建行业管理蓝图
industry_bp = Blueprint('industry', __name__)


@industry_bp.route('/')
@login_required
def index():
    """
    行业列表页
    功能：显示所有行业，管理员看全部，操作员只看自己行业
    """
    if current_user.is_admin():
        industries = Industry.query.order_by(Industry.created_at).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id
        ).all()

    return render_template('industry/index.html', industries=industries)


@industry_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    添加行业
    GET：显示添加行业表单
    POST：保存新行业
    仅管理员可操作
    """
    if not current_user.is_admin():
        flash('无权限操作', 'danger')
        return redirect(url_for('industry.index'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        icon = request.form.get('icon', '🏢').strip()
        platform = request.form.get('platform', 'general')
        ai_system_prompt = request.form.get('ai_system_prompt', '').strip()

        # 验证必填字段
        if not code or not name:
            flash('行业代码和名称为必填项', 'danger')
            return render_template('industry/add.html')

        # 检查代码唯一性
        if Industry.query.filter_by(code=code).first():
            flash('行业代码已存在，请使用其他代码', 'danger')
            return render_template('industry/add.html')

        industry = Industry(
            code=code,
            name=name,
            description=description,
            icon=icon,
            platform=platform,
            ai_system_prompt=ai_system_prompt,
            auto_reply_enabled=True,
            is_active=True,
            created_at=get_beijing_time(),
        )
        db.session.add(industry)
        db.session.commit()

        flash(f'行业「{name}」添加成功', 'success')
        return redirect(url_for('industry.index'))

    return render_template('industry/add.html')


@industry_bp.route('/<int:industry_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(industry_id):
    """
    编辑行业配置
    GET：显示编辑表单
    POST：保存修改
    """
    industry = Industry.query.get_or_404(industry_id)

    # 权限检查
    if not current_user.can_manage_industry(industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('industry.index'))

    if request.method == 'POST':
        industry.name = request.form.get('name', industry.name).strip()
        industry.description = request.form.get('description', '').strip()
        industry.icon = request.form.get('icon', industry.icon).strip()
        industry.platform = request.form.get('platform', industry.platform)
        industry.ai_system_prompt = request.form.get('ai_system_prompt', '').strip()
        industry.auto_reply_enabled = 'auto_reply_enabled' in request.form
        industry.vision_enabled = 'vision_enabled' in request.form
        industry.emotion_enabled = 'emotion_enabled' in request.form
        industry.updated_at = get_beijing_time()

        db.session.commit()
        flash('行业配置已保存', 'success')
        return redirect(url_for('industry.index'))

    return render_template('industry/edit.html', industry=industry)


@industry_bp.route('/<int:industry_id>/toggle', methods=['POST'])
@login_required
def toggle(industry_id):
    """
    切换行业启用/禁用状态
    功能：快速启停行业，禁用后该行业不处理消息
    """
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403

    industry = Industry.query.get_or_404(industry_id)
    industry.is_active = not industry.is_active
    industry.updated_at = get_beijing_time()
    db.session.commit()

    status = '启用' if industry.is_active else '禁用'
    return jsonify({'success': True, 'message': f'行业已{status}', 'is_active': industry.is_active})


@industry_bp.route('/<int:industry_id>/delete', methods=['POST'])
@login_required
def delete(industry_id):
    """
    删除行业
    功能：删除行业及相关配置（不删除消息记录）
    注意：有店铺的行业不允许删除
    """
    if not current_user.is_admin():
        flash('无权限操作', 'danger')
        return redirect(url_for('industry.index'))

    industry = Industry.query.get_or_404(industry_id)

    # 检查是否有关联店铺
    if industry.shops.count() > 0:
        flash('该行业下有店铺，请先删除或迁移店铺', 'danger')
        return redirect(url_for('industry.index'))

    db.session.delete(industry)
    db.session.commit()

    flash(f'行业「{industry.name}」已删除', 'success')
    return redirect(url_for('industry.index'))
