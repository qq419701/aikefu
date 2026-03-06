# -*- coding: utf-8 -*-
"""
知识库管理路由模块
功能说明：行业知识库的增删改查
同一行业的多个店铺共享知识库，三层处理的第二层
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import KnowledgeBase, Industry
from models.database import db, get_beijing_time

# 创建知识库蓝图
knowledge_bp = Blueprint('knowledge', __name__)


@knowledge_bp.route('/')
@login_required
def index():
    """
    知识库列表页
    功能：按行业展示知识库条目，支持按分类筛选
    """
    industry_id = request.args.get('industry_id', type=int)
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)

    # 权限过滤
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()
        # 操作员强制只看自己行业
        if not industry_id:
            industry_id = current_user.industry_id

    # 查询知识库
    query = KnowledgeBase.query
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    if category:
        query = query.filter_by(category=category)

    items = query.order_by(
        KnowledgeBase.priority.desc(),
        KnowledgeBase.created_at.desc()
    ).paginate(page=page, per_page=20)

    return render_template('knowledge/index.html',
        items=items,
        industries=industries,
        selected_industry=industry_id,
        selected_category=category,
    )


@knowledge_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    添加知识库条目
    GET：显示添加表单
    POST：保存新条目
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
        question = request.form.get('question', '').strip()
        answer = request.form.get('answer', '').strip()
        keywords = request.form.get('keywords', '').strip()
        category = request.form.get('category', 'general').strip()
        priority = request.form.get('priority', 0, type=int)

        if not question or not answer or not industry_id:
            flash('问题、答案和所属行业为必填项', 'danger')
            return render_template('knowledge/add.html', industries=industries)

        if not current_user.can_manage_industry(industry_id):
            flash('无权限操作该行业', 'danger')
            return render_template('knowledge/add.html', industries=industries)

        item = KnowledgeBase(
            industry_id=industry_id,
            question=question,
            answer=answer,
            keywords=keywords,
            category=category,
            priority=priority,
            is_active=True,
            created_at=get_beijing_time(),
        )
        db.session.add(item)
        db.session.commit()

        flash('知识库条目添加成功', 'success')
        return redirect(url_for('knowledge.index', industry_id=industry_id))

    return render_template('knowledge/add.html', industries=industries)


@knowledge_bp.route('/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    """
    编辑知识库条目
    """
    item = KnowledgeBase.query.get_or_404(item_id)

    if not current_user.can_manage_industry(item.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('knowledge.index'))

    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()

    if request.method == 'POST':
        item.question = request.form.get('question', '').strip()
        item.answer = request.form.get('answer', '').strip()
        item.keywords = request.form.get('keywords', '').strip()
        item.category = request.form.get('category', 'general').strip()
        item.priority = request.form.get('priority', 0, type=int)
        item.is_active = 'is_active' in request.form
        item.updated_at = get_beijing_time()

        db.session.commit()
        flash('知识库条目已更新', 'success')
        return redirect(url_for('knowledge.index', industry_id=item.industry_id))

    return render_template('knowledge/edit.html', item=item, industries=industries)


@knowledge_bp.route('/<int:item_id>/delete', methods=['POST'])
@login_required
def delete(item_id):
    """
    删除知识库条目
    """
    item = KnowledgeBase.query.get_or_404(item_id)

    if not current_user.can_manage_industry(item.industry_id):
        return jsonify({'success': False, 'message': '无权限'}), 403

    industry_id = item.industry_id
    db.session.delete(item)
    db.session.commit()

    flash('知识库条目已删除', 'success')
    return redirect(url_for('knowledge.index', industry_id=industry_id))
