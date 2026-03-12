# -*- coding: utf-8 -*-
"""
学习中心路由模块（页面4）
功能说明：AI学习中心，每天5分钟快速审核AI回复质量
运营人员可确认AI正确回复入库知识库，或填写正确答案替换错误回复
支持批量AI生成知识库条目，由AI主动汇总行业常见问题
v3.0新增：批量操作、MaxKB全同步、学习模式、去重检测
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import LearningRecord, KnowledgeBase, Industry
from models.database import db, get_beijing_time
import config

logger = logging.getLogger(__name__)

# 创建学习中心蓝图
learning_bp = Blueprint('learning', __name__)


@learning_bp.route('/')
@login_required
def index():
    """
    学习中心首页
    功能：展示待审核的AI回复列表，按行业筛选，显示本周学习进度
    """
    from models.system_config import SystemConfig
    industry_id = request.args.get('industry_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = SystemConfig.get('learning_page_size', 20)
    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = 20

    # 权限过滤：管理员可看全部，操作员只看自己的行业
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id, is_active=True
        ).all()
        if not industry_id:
            industry_id = current_user.industry_id

    # 查询待审核记录
    query = LearningRecord.query.filter_by(review_status='pending')
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    pending_items = query.order_by(LearningRecord.created_at.desc()).paginate(
        page=page, per_page=per_page
    )

    # 本周进度统计
    from datetime import timedelta
    week_start = get_beijing_time().replace(hour=0, minute=0, second=0)
    week_start = week_start - timedelta(days=week_start.weekday())

    week_approved = LearningRecord.query.filter(
        LearningRecord.reviewed_at >= week_start,
        LearningRecord.review_status.in_(['approved', 'modified'])
    ).count()
    week_rejected = LearningRecord.query.filter(
        LearningRecord.reviewed_at >= week_start,
        LearningRecord.review_status == 'rejected'
    ).count()
    week_total = week_approved + week_rejected

    # 总待审核数量
    total_pending = LearningRecord.query.filter_by(review_status='pending').count()

    # 当前学习模式
    learning_mode = SystemConfig.get('learning_mode', 'threshold')

    return render_template('learning/index.html',
        pending_items=pending_items,
        industries=industries,
        selected_industry=industry_id,
        week_approved=week_approved,
        week_rejected=week_rejected,
        week_total=week_total,
        total_pending=total_pending,
        learning_mode=learning_mode,
    )


@learning_bp.route('/<int:record_id>/approve', methods=['POST'])
@login_required
def approve(record_id):
    """
    审核确认：AI回复正确，直接入库知识库
    功能：将AI回复标记为正确，添加到行业知识库中
    v3.0：入库前去重检测 + MaxKB自动同步
    """
    record = LearningRecord.query.get_or_404(record_id)

    if not current_user.can_manage_industry(record.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('learning.index'))

    # B5 去重检测：精确匹配已有知识库条目
    from models.system_config import SystemConfig
    dedup_enabled = SystemConfig.get('learning_dedup_enabled', True)
    if dedup_enabled:
        existing = KnowledgeBase.query.filter_by(
            industry_id=record.industry_id,
            question=record.buyer_message,
        ).first()
        if existing:
            flash(f'该问题已存在于知识库（ID:{existing.id}），已跳过重复入库', 'warning')
            record.review_status = 'approved'
            record.reviewed_by = current_user.username
            record.reviewed_at = get_beijing_time()
            record.is_added_to_kb = True
            record.kb_item_id = existing.id
            db.session.commit()
            return redirect(url_for('learning.index', industry_id=record.industry_id))

    # 将AI回复入库知识库
    kb_item = KnowledgeBase(
        industry_id=record.industry_id,
        question=record.buyer_message,
        answer=record.ai_reply,
        keywords='',
        category=_intent_to_category(record.intent),
        priority=0,
        is_active=True,
        created_at=get_beijing_time(),
    )
    db.session.add(kb_item)
    db.session.flush()  # 获取kb_item.id

    # 更新学习记录状态
    record.review_status = 'approved'
    record.reviewed_by = current_user.username
    record.reviewed_at = get_beijing_time()
    record.is_added_to_kb = True
    record.kb_item_id = kb_item.id
    db.session.commit()

    # B1 MaxKB同步（入库后自动同步到向量库）
    maxkb_sync = SystemConfig.get('learning_maxkb_sync', True)
    if config.MAXKB_ENABLED and maxkb_sync:
        try:
            from modules.maxkb_client import MaxKBClient
            MaxKBClient().upsert(kb_item.id, kb_item.question, kb_item.answer, kb_item.keywords or '')
        except Exception as e:
            logger.warning(f"[学习中心] approve MaxKB同步失败: {e}")

    flash('已确认入库，AI回复已添加到知识库', 'success')
    return redirect(url_for('learning.index', industry_id=record.industry_id))


@learning_bp.route('/<int:record_id>/modify', methods=['POST'])
@login_required
def modify(record_id):
    """
    修改后入库：用运营人员填写的正确答案替换AI回复，然后入库
    功能：AI回复有误时，填写正确答案后入库知识库
    v3.0：入库前去重检测 + MaxKB自动同步
    """
    record = LearningRecord.query.get_or_404(record_id)

    if not current_user.can_manage_industry(record.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('learning.index'))

    correct_answer = request.form.get('correct_answer', '').strip()
    if not correct_answer:
        flash('请填写正确答案', 'warning')
        return redirect(url_for('learning.index'))

    record.correct_answer = correct_answer

    # B5 去重检测：精确匹配已有知识库条目
    from models.system_config import SystemConfig
    dedup_enabled = SystemConfig.get('learning_dedup_enabled', True)
    if dedup_enabled:
        existing = KnowledgeBase.query.filter_by(
            industry_id=record.industry_id,
            question=record.buyer_message,
        ).first()
        if existing:
            # 更新现有条目的答案（人工修正优先级更高）
            existing.answer = correct_answer
            existing.updated_at = get_beijing_time()
            record.review_status = 'modified'
            record.reviewed_by = current_user.username
            record.reviewed_at = get_beijing_time()
            record.is_added_to_kb = True
            record.kb_item_id = existing.id
            db.session.commit()
            if config.MAXKB_ENABLED and SystemConfig.get('learning_maxkb_sync', True):
                try:
                    from modules.maxkb_client import MaxKBClient
                    MaxKBClient().upsert(existing.id, existing.question, existing.answer, existing.keywords or '')
                except Exception as e:
                    logger.warning(f"[学习中心] modify MaxKB同步失败: {e}")
            flash('已修改并覆盖已有知识库条目，正确答案已更新', 'success')
            return redirect(url_for('learning.index', industry_id=record.industry_id))

    # 将正确答案入库知识库
    kb_item = KnowledgeBase(
        industry_id=record.industry_id,
        question=record.buyer_message,
        answer=correct_answer,
        keywords='',
        category=_intent_to_category(record.intent),
        priority=1,  # 人工修正的优先级更高
        is_active=True,
        created_at=get_beijing_time(),
    )
    db.session.add(kb_item)
    db.session.flush()

    record.review_status = 'modified'
    record.reviewed_by = current_user.username
    record.reviewed_at = get_beijing_time()
    record.is_added_to_kb = True
    record.kb_item_id = kb_item.id
    db.session.commit()

    # B2 MaxKB同步（入库后自动同步到向量库）
    maxkb_sync = SystemConfig.get('learning_maxkb_sync', True)
    if config.MAXKB_ENABLED and maxkb_sync:
        try:
            from modules.maxkb_client import MaxKBClient
            MaxKBClient().upsert(kb_item.id, kb_item.question, kb_item.answer, kb_item.keywords or '')
        except Exception as e:
            logger.warning(f"[学习中心] modify MaxKB同步失败: {e}")

    flash('已修改并入库，正确答案已添加到知识库', 'success')
    return redirect(url_for('learning.index', industry_id=record.industry_id))


@learning_bp.route('/<int:record_id>/reject', methods=['POST'])
@login_required
def reject(record_id):
    """
    拒绝：AI回复不合适，丢弃（不入库）
    功能：标记该问答对不适合入库
    """
    record = LearningRecord.query.get_or_404(record_id)

    if not current_user.can_manage_industry(record.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('learning.index'))

    record.review_status = 'rejected'
    record.reviewed_by = current_user.username
    record.reviewed_at = get_beijing_time()
    db.session.commit()

    flash('已标记为不入库', 'info')
    return redirect(url_for('learning.index', industry_id=record.industry_id))


@learning_bp.route('/generate', methods=['POST'])
@login_required
def generate_knowledge():
    """
    AI批量生成知识库条目（doubao-lite，便宜批量处理）
    功能：根据行业和主题，让AI自动生成问答对，存入待审核列表
    参数（JSON）：industry_id, topic, count
    返回：JSON格式结果
    """
    data = request.get_json() or {}
    industry_id = int(data.get('industry_id') or 0) or None
    topic = data.get('topic', '').strip()
    count = min(int(data.get('count', 10)), 20)  # 最多20条

    if not industry_id or not topic:
        return jsonify({'success': False, 'message': '行业ID和主题不能为空'})

    industry = Industry.query.get(industry_id)
    if not industry:
        return jsonify({'success': False, 'message': '行业不存在'})

    if not current_user.can_manage_industry(industry_id):
        return jsonify({'success': False, 'message': '无权限操作该行业'})

    # 调用AI批量生成
    from modules.doubao_ai import DoubaoAI
    ai = DoubaoAI()
    result = ai.generate_knowledge(industry.name, topic, count)

    if not result['success']:
        return jsonify({'success': False, 'message': result.get('error', 'AI生成失败')})

    # 将生成的条目存入待审核列表
    added = 0
    for item in result.get('items', []):
        question = item.get('question', '').strip()
        answer = item.get('answer', '').strip()
        if question and answer:
            record = LearningRecord(
                industry_id=industry_id,
                buyer_message=question,
                ai_reply=answer,
                process_by='ai_generated',
                intent=_category_to_intent(item.get('category', 'general')),
                confidence=0.8,
                review_status='pending',
                created_at=get_beijing_time(),
            )
            db.session.add(record)
            added += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'AI已生成{added}条知识，请在下方审核后入库',
        'count': added,
        'tokens': result.get('tokens', 0),
    })


def _intent_to_category(intent: str) -> str:
    """
    将意图类型转换为知识库分类
    功能：意图→分类映射，用于自动分类入库
    """
    mapping = {
        'refund': 'refund',
        'exchange': 'exchange',
        'login': 'login',
        'payment': 'payment',
        'query': 'general',
        'complaint': 'general',
        'other': 'general',
    }
    return mapping.get(intent, 'general')


def _category_to_intent(category: str) -> str:
    """
    将知识库分类转换为意图类型（反向映射）
    """
    mapping = {
        'refund': 'refund',
        'exchange': 'exchange',
        'login': 'login',
        'payment': 'payment',
        'general': 'query',
    }
    return mapping.get(category, 'other')


def _approve_record(record, answer: str, status: str, maxkb_sync: bool, dedup_enabled: bool):
    """
    内部辅助：将单条学习记录入库知识库（含去重+MaxKB同步）
    返回：(kb_item_id, is_duplicate) 元组
    """
    if dedup_enabled:
        existing = KnowledgeBase.query.filter_by(
            industry_id=record.industry_id,
            question=record.buyer_message,
        ).first()
        if existing:
            record.review_status = status
            record.reviewed_by = current_user.username
            record.reviewed_at = get_beijing_time()
            record.is_added_to_kb = True
            record.kb_item_id = existing.id
            return existing.id, True

    kb_item = KnowledgeBase(
        industry_id=record.industry_id,
        question=record.buyer_message,
        answer=answer,
        keywords='',
        category=_intent_to_category(record.intent),
        priority=1 if status == 'modified' else 0,
        is_active=True,
        created_at=get_beijing_time(),
    )
    db.session.add(kb_item)
    db.session.flush()

    record.review_status = status
    record.reviewed_by = current_user.username
    record.reviewed_at = get_beijing_time()
    record.is_added_to_kb = True
    record.kb_item_id = kb_item.id

    if config.MAXKB_ENABLED and maxkb_sync:
        try:
            from modules.maxkb_client import MaxKBClient
            MaxKBClient().upsert(kb_item.id, kb_item.question, kb_item.answer, '')
        except Exception as e:
            logger.warning(f"[学习中心] 批量审核MaxKB同步失败: {e}")

    return kb_item.id, False


@learning_bp.route('/batch-approve', methods=['POST'])
@login_required
def batch_approve():
    """
    B4 批量确认入库
    请求格式（JSON）：{"record_ids": [1,2,3]}
    返回：{"success": True, "approved": N, "skipped": M}
    """
    from models.system_config import SystemConfig
    data = request.get_json() or {}
    record_ids = data.get('record_ids', [])
    if not record_ids:
        return jsonify({'success': False, 'message': '未选择任何记录'})

    dedup_enabled = SystemConfig.get('learning_dedup_enabled', True)
    maxkb_sync = SystemConfig.get('learning_maxkb_sync', True)

    approved = 0
    skipped = 0
    for rid in record_ids:
        record = LearningRecord.query.get(rid)
        if not record or record.review_status != 'pending':
            continue
        if not current_user.can_manage_industry(record.industry_id):
            continue
        _, is_dup = _approve_record(record, record.ai_reply, 'approved', maxkb_sync, dedup_enabled)
        if is_dup:
            skipped += 1
        else:
            approved += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'批量入库完成：新增{approved}条，跳过重复{skipped}条',
        'approved': approved,
        'skipped': skipped,
    })


@learning_bp.route('/batch-reject', methods=['POST'])
@login_required
def batch_reject():
    """
    B4 批量拒绝
    请求格式（JSON）：{"record_ids": [1,2,3]}
    """
    data = request.get_json() or {}
    record_ids = data.get('record_ids', [])
    if not record_ids:
        return jsonify({'success': False, 'message': '未选择任何记录'})

    rejected = 0
    now = get_beijing_time()
    for rid in record_ids:
        record = LearningRecord.query.get(rid)
        if not record or record.review_status != 'pending':
            continue
        if not current_user.can_manage_industry(record.industry_id):
            continue
        record.review_status = 'rejected'
        record.reviewed_by = current_user.username
        record.reviewed_at = now
        rejected += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'已批量拒绝{rejected}条记录',
        'rejected': rejected,
    })


@learning_bp.route('/batch-approve-high', methods=['POST'])
@login_required
def batch_approve_high():
    """
    B4 一键入库高置信度记录（≥阈值的全部确认入库）
    请求格式（JSON）：{"industry_id": 1}（可选）
    """
    from models.system_config import SystemConfig
    data = request.get_json() or {}
    industry_id = data.get('industry_id')

    threshold = float(SystemConfig.get('learning_confidence_threshold', 0.7))
    dedup_enabled = SystemConfig.get('learning_dedup_enabled', True)
    maxkb_sync = SystemConfig.get('learning_maxkb_sync', True)

    query = LearningRecord.query.filter_by(review_status='pending').filter(
        LearningRecord.confidence >= threshold
    )
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    records = query.all()
    approved = 0
    skipped = 0
    for record in records:
        if not current_user.can_manage_industry(record.industry_id):
            continue
        _, is_dup = _approve_record(record, record.ai_reply, 'approved', maxkb_sync, dedup_enabled)
        if is_dup:
            skipped += 1
        else:
            approved += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'一键入库完成：新增{approved}条（置信度≥{int(threshold*100)}%），跳过重复{skipped}条',
        'approved': approved,
        'skipped': skipped,
    })
