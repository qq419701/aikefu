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
import config

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

        # 如果MaxKB已启用，自动同步新条目到MaxKB向量库
        if config.MAXKB_ENABLED:
            from modules.maxkb_client import MaxKBClient
            MaxKBClient().upsert(item.id, question, answer, keywords)

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

        # 如果MaxKB已启用，自动同步更新到MaxKB向量库
        if config.MAXKB_ENABLED:
            from modules.maxkb_client import MaxKBClient
            MaxKBClient().upsert(item.id, item.question, item.answer, item.keywords or '')

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
    item_id_for_maxkb = item.id  # 先保存ID，删除后无法访问
    db.session.delete(item)
    db.session.commit()

    # 如果MaxKB已启用，同步删除MaxKB中的向量文档
    if config.MAXKB_ENABLED:
        from modules.maxkb_client import MaxKBClient
        MaxKBClient().delete(item_id_for_maxkb)

    flash('知识库条目已删除', 'success')
    return redirect(url_for('knowledge.index', industry_id=industry_id))


@knowledge_bp.route('/generate', methods=['GET'])
@login_required
def generate():
    """
    AI批量生成知识库页面
    功能：根据行业和主题，调用豆包AI批量生成问答对，人工审核后批量入库
    """
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id, is_active=True
        ).all()

    return render_template('knowledge/generate.html', industries=industries)


@knowledge_bp.route('/api/generate', methods=['POST'])
@login_required
def api_generate():
    """
    调用AI批量生成知识库条目接口
    功能：通过doubao-lite生成问答对，返回JSON供前端展示和编辑
    请求格式（JSON）：
    {
        "industry_id": 1,
        "topic": "换号问题",
        "count": 10
    }
    返回：{'success': True, 'items': [{'question':..., 'answer':..., 'category':...}]}
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        data = request.get_json() or {}
        industry_id = int(data.get('industry_id') or 0)
        topic = (data.get('topic') or '').strip()
        count = min(int(data.get('count') or 10), 30)  # 最多一次生成30条

        if not industry_id or not topic:
            return jsonify({'success': False, 'message': '行业和主题为必填项'})

        if not current_user.can_manage_industry(industry_id):
            return jsonify({'success': False, 'message': '无权限操作该行业'})

        industry = Industry.query.get(industry_id)
        if not industry:
            return jsonify({'success': False, 'message': '行业不存在'})

        from modules.doubao_ai import DoubaoAI
        ai = DoubaoAI()
        result = ai.generate_knowledge(
            industry_name=industry.name,
            topic=topic,
            count=count,
        )

        return jsonify({
            'success': result.get('success', False),
            'items': result.get('items', []),
            'tokens': result.get('tokens', 0),
            'error': result.get('error', ''),
        })

    except Exception as e:
        logger.error(f"[知识库] AI生成异常: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)})


@knowledge_bp.route('/api/batch-save', methods=['POST'])
@login_required
def api_batch_save():
    """
    批量保存AI生成的知识库条目
    功能：前端审核并勾选后，一次性入库多条知识
    请求格式（JSON）：
    {
        "industry_id": 1,
        "items": [
            {"question": "...", "answer": "...", "category": "general"},
            ...
        ]
    }
    返回：{'success': True, 'saved': 保存数量}
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        data = request.get_json() or {}
        industry_id = int(data.get('industry_id') or 0)
        items = data.get('items') or []

        if not industry_id:
            return jsonify({'success': False, 'message': '缺少industry_id'})

        if not current_user.can_manage_industry(industry_id):
            return jsonify({'success': False, 'message': '无权限操作该行业'})

        if not items:
            return jsonify({'success': False, 'message': '没有可保存的条目'})

        saved_count = 0
        now = get_beijing_time()
        for item in items:
            question = (item.get('question') or '').strip()
            answer = (item.get('answer') or '').strip()
            if not question or not answer:
                continue
            kb = KnowledgeBase(
                industry_id=industry_id,
                question=question,
                answer=answer,
                keywords=item.get('keywords', ''),
                category=item.get('category', 'general'),
                priority=0,
                is_active=True,
                created_at=now,
            )
            db.session.add(kb)
            saved_count += 1

        db.session.commit()
        return jsonify({'success': True, 'saved': saved_count})

    except Exception as e:
        logger.error(f"[知识库] 批量保存异常: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
