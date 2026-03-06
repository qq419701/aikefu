# -*- coding: utf-8 -*-
"""
规则引擎管理路由模块
功能说明：管理三层处理第一层的关键词规则
规则匹配0成本，目标覆盖20%的消息
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Rule, Industry
from models.database import db, get_beijing_time

# 创建规则管理蓝图
rules_bp = Blueprint('rules', __name__)


@rules_bp.route('/')
@login_required
def index():
    """
    规则列表页
    功能：按行业显示所有规则，支持筛选
    """
    industry_id = request.args.get('industry_id', type=int)

    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()
        industry_id = industry_id or current_user.industry_id

    query = Rule.query
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    rules = query.order_by(Rule.priority.desc(), Rule.created_at.desc()).all()

    return render_template('rules/index.html',
        rules=rules,
        industries=industries,
        selected_industry=industry_id,
    )


@rules_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    添加规则
    GET：显示添加规则表单
    POST：保存新规则
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
        name = request.form.get('name', '').strip()
        trigger_keywords = request.form.get('trigger_keywords', '').strip()
        match_mode = request.form.get('match_mode', 'any')
        reply_content = request.form.get('reply_content', '').strip()
        action_type = request.form.get('action_type', '').strip()
        priority = request.form.get('priority', 0, type=int)

        if not name or not trigger_keywords or not reply_content or not industry_id:
            flash('规则名称、触发关键词、回复内容和所属行业为必填项', 'danger')
            return render_template('rules/add.html', industries=industries)

        if not current_user.can_manage_industry(industry_id):
            flash('无权限操作该行业', 'danger')
            return render_template('rules/add.html', industries=industries)

        rule = Rule(
            industry_id=industry_id,
            name=name,
            trigger_keywords=trigger_keywords,
            match_mode=match_mode,
            reply_content=reply_content,
            action_type=action_type,
            priority=priority,
            is_active=True,
            created_at=get_beijing_time(),
        )
        db.session.add(rule)
        db.session.commit()

        flash(f'规则「{name}」添加成功', 'success')
        return redirect(url_for('rules.index', industry_id=industry_id))

    return render_template('rules/add.html', industries=industries)


@rules_bp.route('/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(rule_id):
    """
    编辑规则
    """
    rule = Rule.query.get_or_404(rule_id)

    if not current_user.can_manage_industry(rule.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('rules.index'))

    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()

    if request.method == 'POST':
        rule.name = request.form.get('name', rule.name).strip()
        rule.trigger_keywords = request.form.get('trigger_keywords', '').strip()
        rule.match_mode = request.form.get('match_mode', 'any')
        rule.reply_content = request.form.get('reply_content', '').strip()
        rule.action_type = request.form.get('action_type', '').strip()
        rule.priority = request.form.get('priority', 0, type=int)
        rule.is_active = 'is_active' in request.form

        db.session.commit()
        flash('规则已更新', 'success')
        return redirect(url_for('rules.index', industry_id=rule.industry_id))

    return render_template('rules/edit.html', rule=rule, industries=industries)


@rules_bp.route('/<int:rule_id>/toggle', methods=['POST'])
@login_required
def toggle(rule_id):
    """
    切换规则启用/禁用状态
    """
    rule = Rule.query.get_or_404(rule_id)

    if not current_user.can_manage_industry(rule.industry_id):
        return jsonify({'success': False, 'message': '无权限'}), 403

    rule.is_active = not rule.is_active
    db.session.commit()

    status = '启用' if rule.is_active else '禁用'
    return jsonify({'success': True, 'message': f'规则已{status}', 'is_active': rule.is_active})


@rules_bp.route('/<int:rule_id>/delete', methods=['POST'])
@login_required
def delete(rule_id):
    """
    删除规则
    """
    rule = Rule.query.get_or_404(rule_id)

    if not current_user.can_manage_industry(rule.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('rules.index'))

    industry_id = rule.industry_id
    rule_name = rule.name
    db.session.delete(rule)
    db.session.commit()

    flash(f'规则「{rule_name}」已删除', 'success')
    return redirect(url_for('rules.index', industry_id=industry_id))
