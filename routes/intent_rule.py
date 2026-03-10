# -*- coding: utf-8 -*-
"""
意图规则管理路由模块
功能说明：提供意图规则的增删改查后台管理页面
意图规则替代原代码中的硬编码关键词列表，运营可自行配置
蓝图名：intent_rule_bp，URL前缀：/intent-rules
接口列表：
  GET  /intent-rules/           - 意图规则列表（支持按行业筛选）
  GET  /intent-rules/add        - 新增规则表单
  POST /intent-rules/add        - 提交新增规则
  GET  /intent-rules/<id>/edit  - 编辑规则表单
  POST /intent-rules/<id>/edit  - 提交编辑规则
  POST /intent-rules/<id>/toggle - 启用/禁用切换（JSON）
  POST /intent-rules/<id>/delete - 删除规则
"""

import json
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models.database import db, get_beijing_time
from models.intent_rule import IntentRule
from models.industry import Industry
from models.plugin import ClientPlugin

intent_rule_bp = Blueprint('intent_rule', __name__)

logger = logging.getLogger(__name__)


# ================================================================
# 列表页
# ================================================================

@intent_rule_bp.route('/')
@login_required
def index():
    """
    意图规则列表
    功能：显示所有意图规则，支持按行业筛选
    路径：GET /intent-rules/
    """
    industry_filter = request.args.get('industry_id', '', type=str)

    # 查询规则列表
    query = IntentRule.query

    # 权限过滤：非管理员只能看本行业和全局规则
    if not current_user.is_admin():
        industry_filter = str(current_user.industry_id) if current_user.industry_id else ''
        query = query.filter(
            db.or_(
                IntentRule.industry_id == current_user.industry_id,
                IntentRule.industry_id == None,  # noqa: E711
            )
        )
    elif industry_filter:
        if industry_filter == 'global':
            query = query.filter(IntentRule.industry_id == None)  # noqa: E711
        else:
            try:
                query = query.filter(IntentRule.industry_id == int(industry_filter))
            except ValueError:
                pass

    rules = query.order_by(IntentRule.priority.asc(), IntentRule.id.asc()).all()

    # 获取行业列表（供筛选下拉框使用）
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).order_by(Industry.name).all()
    else:
        industries = []

    return render_template(
        'intent_rule/index.html',
        rules=rules,
        industries=industries,
        industry_filter=industry_filter,
        action_labels=IntentRule.get_action_code_labels(),
        intent_labels=IntentRule.get_intent_code_labels(),
    )


# ================================================================
# 新增规则
# ================================================================

@intent_rule_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    新增意图规则
    功能：GET显示表单，POST提交创建
    路径：GET/POST /intent-rules/add
    """
    if request.method == 'GET':
        industries = Industry.query.filter_by(is_active=True).order_by(Industry.name).all()
        # 收集已注册插件的所有动作码（供下拉选择）
        action_codes = _get_all_action_codes()
        return render_template(
            'intent_rule/form.html',
            rule=None,
            industries=industries,
            action_codes=action_codes,
            action_labels=IntentRule.get_action_code_labels(),
            title='新增意图规则',
        )

    # POST：处理表单提交
    try:
        industry_id = request.form.get('industry_id', '').strip()
        intent_code = request.form.get('intent_code', '').strip()
        intent_name = request.form.get('intent_name', '').strip()
        keywords_raw = request.form.get('keywords', '').strip()
        # 动作码：优先取 action_code，若为 '__custom__' 则取 action_code_custom
        action_code = request.form.get('action_code', '').strip()
        if action_code == '__custom__':
            action_code = request.form.get('action_code_custom', '').strip()
        auto_reply_tpl = request.form.get('auto_reply_tpl', '').strip()
        done_reply_tpl = request.form.get('done_reply_tpl', '').strip()
        priority = request.form.get('priority', 0, type=int)
        is_active = request.form.get('is_active') == '1'
        intent_code_label = request.form.get('intent_code_label', '').strip()
        action_code_label = request.form.get('action_code_label', '').strip()

        if not intent_code or not intent_name:
            flash('意图标识和意图名称不能为空', 'danger')
            return redirect(url_for('intent_rule.add'))

        # 解析关键词（逗号分隔转为 JSON 数组）
        keywords_list = [kw.strip() for kw in keywords_raw.split(',') if kw.strip()]
        if not keywords_list:
            flash('至少需要填写一个触发关键词', 'danger')
            return redirect(url_for('intent_rule.add'))

        now = get_beijing_time()
        rule = IntentRule(
            industry_id=int(industry_id) if industry_id else None,
            intent_code=intent_code,
            intent_name=intent_name,
            keywords=json.dumps(keywords_list, ensure_ascii=False),
            action_code=action_code or None,
            auto_reply_tpl=auto_reply_tpl or None,
            done_reply_tpl=done_reply_tpl or None,
            priority=priority,
            is_active=is_active,
            intent_code_label=intent_code_label or None,
            action_code_label=action_code_label or None,
            created_at=now,
            updated_at=now,
        )
        db.session.add(rule)
        db.session.commit()

        flash(f'意图规则「{intent_name}」创建成功', 'success')
        logger.info(f"[意图规则] 新增: intent_code={intent_code}, by={current_user.username}")
        return redirect(url_for('intent_rule.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"[意图规则] 新增失败: {e}", exc_info=True)
        flash(f'创建失败：{str(e)}', 'danger')
        return redirect(url_for('intent_rule.add'))


# ================================================================
# 编辑规则
# ================================================================

@intent_rule_bp.route('/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(rule_id: int):
    """
    编辑意图规则
    功能：GET显示编辑表单，POST提交修改
    路径：GET/POST /intent-rules/<id>/edit
    """
    rule = IntentRule.query.get_or_404(rule_id)

    # 权限检查：非管理员只能编辑本行业规则
    if not current_user.is_admin():
        if rule.industry_id and rule.industry_id != current_user.industry_id:
            flash('无权编辑其他行业的规则', 'danger')
            return redirect(url_for('intent_rule.index'))

    if request.method == 'GET':
        industries = Industry.query.filter_by(is_active=True).order_by(Industry.name).all()
        action_codes = _get_all_action_codes()
        return render_template(
            'intent_rule/form.html',
            rule=rule,
            industries=industries,
            action_codes=action_codes,
            action_labels=IntentRule.get_action_code_labels(),
            title=f'编辑规则：{rule.intent_name}',
        )

    # POST：处理表单提交
    try:
        industry_id = request.form.get('industry_id', '').strip()
        intent_code = request.form.get('intent_code', '').strip()
        intent_name = request.form.get('intent_name', '').strip()
        keywords_raw = request.form.get('keywords', '').strip()
        # 动作码：优先取 action_code，若为 '__custom__' 则取 action_code_custom
        action_code = request.form.get('action_code', '').strip()
        if action_code == '__custom__':
            action_code = request.form.get('action_code_custom', '').strip()
        auto_reply_tpl = request.form.get('auto_reply_tpl', '').strip()
        done_reply_tpl = request.form.get('done_reply_tpl', '').strip()
        priority = request.form.get('priority', 0, type=int)
        is_active = request.form.get('is_active') == '1'

        if not intent_code or not intent_name:
            flash('意图标识和意图名称不能为空', 'danger')
            return redirect(url_for('intent_rule.edit', rule_id=rule_id))

        keywords_list = [kw.strip() for kw in keywords_raw.split(',') if kw.strip()]
        if not keywords_list:
            flash('至少需要填写一个触发关键词', 'danger')
            return redirect(url_for('intent_rule.edit', rule_id=rule_id))

        rule.industry_id = int(industry_id) if industry_id else None
        rule.intent_code = intent_code
        rule.intent_name = intent_name
        rule.keywords = json.dumps(keywords_list, ensure_ascii=False)
        rule.action_code = action_code or None
        rule.auto_reply_tpl = auto_reply_tpl or None
        rule.done_reply_tpl = done_reply_tpl or None
        rule.priority = priority
        rule.is_active = is_active
        rule.intent_code_label = request.form.get('intent_code_label', '').strip() or None
        rule.action_code_label = request.form.get('action_code_label', '').strip() or None
        rule.updated_at = get_beijing_time()

        db.session.commit()

        flash(f'意图规则「{intent_name}」更新成功', 'success')
        logger.info(f"[意图规则] 编辑: rule_id={rule_id}, by={current_user.username}")
        return redirect(url_for('intent_rule.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"[意图规则] 编辑失败: rule_id={rule_id}, error={e}", exc_info=True)
        flash(f'更新失败：{str(e)}', 'danger')
        return redirect(url_for('intent_rule.edit', rule_id=rule_id))


# ================================================================
# 启用/禁用切换（JSON接口）
# ================================================================

@intent_rule_bp.route('/<int:rule_id>/toggle', methods=['POST'])
@login_required
def toggle(rule_id: int):
    """
    启用/禁用意图规则
    功能：切换规则的 is_active 状态，JSON接口
    路径：POST /intent-rules/<id>/toggle
    返回：{'success': true, 'is_active': false}
    """
    rule = IntentRule.query.get_or_404(rule_id)

    # 权限检查
    if not current_user.is_admin():
        if rule.industry_id and rule.industry_id != current_user.industry_id:
            return jsonify({'success': False, 'message': '无权操作'}), 403

    try:
        rule.is_active = not rule.is_active
        rule.updated_at = get_beijing_time()
        db.session.commit()
        status = '启用' if rule.is_active else '禁用'
        logger.info(f"[意图规则] {status}: rule_id={rule_id}, by={current_user.username}")
        return jsonify({'success': True, 'is_active': rule.is_active})
    except Exception as e:
        db.session.rollback()
        logger.error(f"[意图规则] 切换状态失败: rule_id={rule_id}, error={e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ================================================================
# 删除规则
# ================================================================

@intent_rule_bp.route('/<int:rule_id>/delete', methods=['POST'])
@login_required
def delete(rule_id: int):
    """
    删除意图规则
    功能：删除指定规则
    路径：POST /intent-rules/<id>/delete
    """
    rule = IntentRule.query.get_or_404(rule_id)

    # 权限检查：非管理员只能删除本行业规则
    if not current_user.is_admin():
        if rule.industry_id and rule.industry_id != current_user.industry_id:
            flash('无权删除其他行业的规则', 'danger')
            return redirect(url_for('intent_rule.index'))

    try:
        intent_name = rule.intent_name
        db.session.delete(rule)
        db.session.commit()
        flash(f'规则「{intent_name}」已删除', 'success')
        logger.info(f"[意图规则] 删除: rule_id={rule_id}, by={current_user.username}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[意图规则] 删除失败: rule_id={rule_id}, error={e}")
        flash(f'删除失败：{str(e)}', 'danger')

    return redirect(url_for('intent_rule.index'))


# ================================================================
# 辅助函数
# ================================================================

def _get_all_action_codes() -> list:
    """
    获取所有已注册插件的动作码列表
    功能：供表单下拉框显示可选的动作码
    返回：去重后的动作码列表
    """
    try:
        plugins = ClientPlugin.query.filter_by(is_active=True).all()
        codes = set()
        for plugin in plugins:
            codes.update(plugin.get_action_codes())
        return sorted(codes)
    except Exception:
        return []
