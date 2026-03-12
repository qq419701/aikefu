# -*- coding: utf-8 -*-
"""
系统设置路由模块
功能说明：后台可视化管理系统配置（AI参数、知识库、系统行为等）
替代手动修改 .env 文件，支持实时生效（无需重启）
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models.system_config import SystemConfig
from models.database import db, get_beijing_time

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/')
@login_required
def index():
    """系统设置首页"""
    if not current_user.is_admin():
        flash('无权限访问系统设置', 'danger')
        return redirect(url_for('dashboard.index'))

    groups = {
        'ai':        {'label': '🤖 AI参数设置',    'icon': 'robot',    'desc': '豆包AI模型、Token、温度等参数'},
        'context':   {'label': '💬 多轮对话设置',  'icon': 'comments',  'desc': '会话上下文轮次、超时时间'},
        'knowledge': {'label': '📚 知识库设置',    'icon': 'book',     'desc': 'MaxKB语义检索、相似度阈值'},
        'learning':  {'label': '🎓 学习中心设置',  'icon': 'mortarboard', 'desc': '学习模式、去重、自动同步MaxKB（v3.0）'},
        'behavior':  {'label': '⚙️ 系统行为',      'icon': 'cogs',     'desc': '回复延迟、黑名单、数据保留'},
    }
    configs = {}
    for g in groups:
        configs[g] = SystemConfig.query.filter_by(group=g).order_by(SystemConfig.id).all()

    return render_template('settings/index.html', groups=groups, configs=configs)


@settings_bp.route('/save', methods=['POST'])
@login_required
def save():
    """保存系统设置"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '参数错误'}), 400

    saved_count = 0
    for key, value in data.items():
        cfg = SystemConfig.query.filter_by(key=key).first()
        if cfg:
            cfg.value = str(value).strip()
            cfg.updated_at = get_beijing_time()
            saved_count += 1

    db.session.commit()
    return jsonify({'success': True, 'message': f'已保存 {saved_count} 项配置'})


@settings_bp.route('/test-doubao', methods=['POST'])
@login_required
def test_doubao():
    """测试豆包AI连接"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403
    try:
        from modules.doubao_ai import DoubaoAI
        ai = DoubaoAI()
        result = ai.chat('你好，测试连接', '你是客服助手', None, use_cache=False)
        if result.get('success'):
            return jsonify({'success': True, 'message': f'连接成功！回复：{result["reply"][:30]}'})
        return jsonify({'success': False, 'message': 'AI返回失败，请检查API Key和模型名称'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'连接失败：{str(e)[:100]}'})


@settings_bp.route('/test-maxkb', methods=['POST'])
@login_required
def test_maxkb():
    """测试MaxKB连接"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403
    try:
        from modules.maxkb_client import MaxKBClient
        client = MaxKBClient()
        ok = client.health_check()
        if ok:
            return jsonify({'success': True, 'message': 'MaxKB连接正常'})
        return jsonify({'success': False, 'message': 'MaxKB连接失败，请检查地址和API Key'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'连接异常：{str(e)[:100]}'})


@settings_bp.route('/maxkb')
@login_required
def maxkb_panel():
    """MaxKB管理面板：连接状态、数据集统计、差异对比"""
    if not current_user.is_admin():
        flash('无权限访问', 'danger')
        return redirect(url_for('settings.index'))

    from models.knowledge import KnowledgeBase
    import config as cfg

    maxkb_stats = {'connected': False, 'total_docs': 0, 'dataset_id': cfg.MAXKB_DATASET_ID}
    if cfg.MAXKB_ENABLED:
        try:
            from modules.maxkb_client import MaxKBClient
            maxkb_stats = MaxKBClient().get_stats()
        except Exception:
            pass

    local_total = KnowledgeBase.query.count()
    local_synced = KnowledgeBase.query.filter_by(maxkb_synced=True).count()

    # 按行业统计本地条目数
    from models.industry import Industry
    from models.database import db
    from sqlalchemy import func
    industry_stats = db.session.query(
        Industry.id, Industry.name, Industry.icon,
        func.count(KnowledgeBase.id).label('total'),
        func.sum(db.case((KnowledgeBase.maxkb_synced == True, 1), else_=0)).label('synced'),
    ).outerjoin(KnowledgeBase, KnowledgeBase.industry_id == Industry.id
    ).filter(Industry.is_active == True).group_by(Industry.id).all()

    return render_template('settings/maxkb.html',
        maxkb_stats=maxkb_stats,
        local_total=local_total,
        local_synced=local_synced,
        industry_stats=industry_stats,
        maxkb_enabled=cfg.MAXKB_ENABLED,
    )


@settings_bp.route('/maxkb/sync-all', methods=['POST'])
@login_required
def maxkb_sync_all():
    """一键全量同步：将所有本地知识库推送到MaxKB"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403

    import config as cfg
    if not cfg.MAXKB_ENABLED:
        return jsonify({'success': False, 'message': 'MaxKB未启用，请先在系统设置中启用'})

    try:
        from models.knowledge import KnowledgeBase
        from modules.maxkb_client import MaxKBClient
        from models.database import db, get_beijing_time

        client = MaxKBClient()
        items = KnowledgeBase.query.filter_by(is_active=True).all()
        total = len(items)
        synced = 0
        failed = 0
        now = get_beijing_time()

        for item in items:
            ok = client.upsert(item.id, item.question, item.answer, item.keywords or '')
            if ok:
                item.maxkb_synced = True
                item.maxkb_synced_at = now
                synced += 1
            else:
                failed += 1

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'全量同步完成：成功{synced}条，失败{failed}条',
            'synced': synced,
            'failed': failed,
            'total': total,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'同步失败：{str(e)[:200]}'})
