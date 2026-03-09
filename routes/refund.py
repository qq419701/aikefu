# -*- coding: utf-8 -*-
"""
退款管理路由模块（页面6）
功能说明：管理拼多多及其他平台的退款申请
支持AI自动处理退款（同意/拒绝），显示倒计时（红色=紧急）
记录恶意买家，统计驳回成功率
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import case
from models import RefundRecord, Industry, Shop, Blacklist
from models.database import db, get_beijing_time

# 创建退款管理蓝图
refund_bp = Blueprint('refund', __name__)


@refund_bp.route('/')
@login_required
def index():
    """
    退款管理首页
    功能：
      - 显示待处理退款列表（含倒计时）
      - 紧急退款红色高亮（距截止时间<24小时）
      - AI处理记录查看
      - 驳回成功率统计
    """
    industry_id = request.args.get('industry_id', type=int)
    status_filter = request.args.get('status', 'pending')
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

    # 查询退款记录
    query = RefundRecord.query
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    # 待处理的按紧急程度排序（截止时间最近的排前面，NULL排最后）
    # 使用 case() 替代 .nullslast()，兼容MySQL（MySQL不支持NULLS LAST语法）
    if status_filter == 'pending':
        deadline_null_last = case(
            (RefundRecord.deadline_at.is_(None), 1),
            else_=0
        )
        refunds = query.order_by(
            deadline_null_last.asc(),
            RefundRecord.deadline_at.asc(),
            RefundRecord.applied_at.desc()
        ).paginate(page=page, per_page=20)
    else:
        refunds = query.order_by(RefundRecord.applied_at.desc()).paginate(
            page=page, per_page=20
        )

    # 统计数据
    base_query = RefundRecord.query
    if industry_id:
        base_query = base_query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        base_query = base_query.filter_by(industry_id=current_user.industry_id)

    stats = {
        'pending_count': base_query.filter_by(status='pending').count(),
        'ai_approved_count': base_query.filter_by(status='ai_approved').count(),
        'ai_rejected_count': base_query.filter_by(status='ai_rejected').count(),
        'rejected_count': base_query.filter_by(status='rejected').count(),
        'approved_count': base_query.filter(
            RefundRecord.status.in_(['approved', 'ai_approved'])
        ).count(),
        'malicious_count': base_query.filter_by(is_malicious=True).count(),
    }

    # 驳回成功率
    total_processed = stats['rejected_count'] + stats['ai_rejected_count'] + stats['approved_count']
    if total_processed > 0:
        stats['reject_rate'] = round(
            (stats['rejected_count'] + stats['ai_rejected_count']) / total_processed * 100, 1
        )
    else:
        stats['reject_rate'] = 0

    return render_template('refund/index.html',
        refunds=refunds,
        industries=industries,
        selected_industry=industry_id,
        status_filter=status_filter,
        stats=stats,
    )


@refund_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    手动添加退款记录
    功能：运营人员手动录入拼多多退款申请（无API时通过截图手动输入）
    GET：显示添加表单
    POST：保存退款记录
    """
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
        shops = Shop.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id, is_active=True
        ).all()
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id, is_active=True
        ).all()

    if request.method == 'POST':
        shop_id = request.form.get('shop_id', type=int)
        order_id = request.form.get('order_id', '').strip()
        buyer_id = request.form.get('buyer_id', '').strip()
        buyer_name = request.form.get('buyer_name', '').strip()
        refund_amount = int(float(request.form.get('refund_amount', 0)) * 100)
        refund_reason = request.form.get('refund_reason', '').strip()
        deadline_str = request.form.get('deadline_at', '').strip()

        if not shop_id or not order_id or not buyer_id:
            flash('店铺、订单号和买家ID为必填项', 'danger')
            return render_template('refund/add.html', industries=industries, shops=shops)

        shop = Shop.query.get(shop_id)
        if not shop:
            flash('店铺不存在', 'danger')
            return render_template('refund/add.html', industries=industries, shops=shops)

        # 解析截止时间
        deadline_at = None
        if deadline_str:
            try:
                from datetime import datetime
                deadline_at = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass

        record = RefundRecord(
            shop_id=shop_id,
            industry_id=shop.industry_id,
            order_id=order_id,
            buyer_id=buyer_id,
            buyer_name=buyer_name,
            refund_amount=refund_amount,
            refund_reason=refund_reason,
            status='pending',
            deadline_at=deadline_at,
            applied_at=get_beijing_time(),
        )
        db.session.add(record)
        db.session.commit()

        flash('退款记录已添加', 'success')
        return redirect(url_for('refund.index'))

    return render_template('refund/add.html', industries=industries, shops=shops)


@refund_bp.route('/<int:record_id>/ai_process', methods=['POST'])
@login_required
def ai_process(record_id):
    """
    AI自动处理退款（doubao-pro，关键决策）
    功能：调用AI分析退款原因，给出处理建议（同意/拒绝/转人工）
    返回：JSON格式结果
    """
    record = RefundRecord.query.get_or_404(record_id)

    if record.status != 'pending':
        return jsonify({'success': False, 'message': '该退款已处理'})

    shop = Shop.query.get(record.shop_id)
    if not shop:
        return jsonify({'success': False, 'message': '店铺不存在'})

    # 调用doubao-pro进行退款决策
    from modules.doubao_ai import DoubaoAI
    ai = DoubaoAI()
    order_info = f'订单号：{record.order_id}，退款金额：{record.get_amount_yuan()}元'
    result = ai.handle_refund_decision(
        record.refund_reason,
        order_info,
        shop.get_effective_prompt()
    )

    # 更新退款记录
    record.ai_decision = result.get('decision', 'human')
    record.ai_reason = result.get('reason', '')
    record.ai_reply = result.get('reply', '')

    if result['success']:
        decision = result.get('decision', 'human')
        if decision == 'approve':
            record.status = 'ai_approved'
        elif decision == 'reject':
            record.status = 'ai_rejected'
        else:
            record.status = 'pending'  # 需要人工

        record.processed_at = get_beijing_time()
        db.session.commit()

        return jsonify({
            'success': True,
            'decision': decision,
            'reply': result.get('reply', ''),
            'reason': result.get('reason', ''),
        })
    else:
        db.session.commit()
        return jsonify({
            'success': False,
            'message': result.get('error', 'AI处理失败'),
        })


@refund_bp.route('/<int:record_id>/approve', methods=['POST'])
@login_required
def approve(record_id):
    """
    人工同意退款
    功能：运营人员手动同意退款申请
    """
    record = RefundRecord.query.get_or_404(record_id)
    note = request.form.get('note', '').strip()

    record.status = 'approved'
    record.admin_note = note
    record.processed_at = get_beijing_time()
    db.session.commit()

    flash(f'已同意退款（订单：{record.order_id}）', 'success')
    return redirect(url_for('refund.index'))


@refund_bp.route('/<int:record_id>/reject', methods=['POST'])
@login_required
def reject(record_id):
    """
    人工拒绝退款（驳回）
    功能：运营人员手动驳回退款申请，并可选择加入恶意买家名单
    """
    record = RefundRecord.query.get_or_404(record_id)
    note = request.form.get('note', '').strip()
    mark_malicious = request.form.get('mark_malicious') == '1'

    record.status = 'rejected'
    record.admin_note = note
    record.processed_at = get_beijing_time()

    # 标记为恶意买家并加入黑名单
    if mark_malicious:
        record.is_malicious = True
        _add_to_blacklist(record.buyer_id, record.buyer_name,
                          record.industry_id, f'恶意退款：{record.order_id}', level=2)
        # 主动删除 Redis 黑名单缓存，保证黑名单实时生效
        from models.database import redis_client, get_blacklist_cache_key
        if redis_client:
            try:
                redis_client.delete(get_blacklist_cache_key(record.industry_id, record.buyer_id))
            except Exception:
                pass

    db.session.commit()
    flash(f'已驳回退款（订单：{record.order_id}）', 'success')
    return redirect(url_for('refund.index'))


@refund_bp.route('/malicious_buyers')
@login_required
def malicious_buyers():
    """
    恶意买家列表
    功能：展示被标记为恶意退款的买家列表
    """
    industry_id = request.args.get('industry_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = RefundRecord.query.filter_by(is_malicious=True)
    if industry_id:
        query = query.filter_by(industry_id=industry_id)
    elif not current_user.is_admin():
        query = query.filter_by(industry_id=current_user.industry_id)

    malicious = query.order_by(RefundRecord.applied_at.desc()).paginate(
        page=page, per_page=20
    )

    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id, is_active=True
        ).all()

    return render_template('refund/malicious.html',
        malicious=malicious,
        industries=industries,
        selected_industry=industry_id,
    )


def _add_to_blacklist(buyer_id: str, buyer_name: str,
                      industry_id: int, reason: str, level: int = 2):
    """
    将买家加入黑名单（内部工具函数）
    功能：退款驳回时自动加入行业黑名单
    """
    existing = Blacklist.query.filter_by(
        buyer_id=buyer_id,
        industry_id=industry_id,
    ).first()

    if existing:
        existing.level = max(existing.level, level)
        existing.reason = reason
        existing.is_active = True
        existing.updated_at = get_beijing_time()
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
