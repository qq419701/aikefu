# -*- coding: utf-8 -*-
"""
客户端插件管理路由模块
功能说明：提供插件注册、心跳、任务下发、任务回调等API接口
客户端（dskehuduan）通过这些API与aikefu交互
设计原则：
  - 客户端API（无需登录）：用shop_token鉴权（X-Shop-Token请求头）
  - 管理后台API（需登录）：查看插件列表和任务记录
接口列表：
  POST /api/plugin/register       - 客户端注册插件能力
  POST /api/plugin/heartbeat      - 客户端心跳保活（每30秒一次）
  GET  /api/plugin/tasks          - 客户端轮询待执行任务
  POST /api/plugin/tasks/<task_id>/done - 客户端上报任务完成（task_id为UUID字符串）
  POST /api/plugin/tasks/<task_id>/fail - 客户端上报任务失败（task_id为UUID字符串）
  GET  /plugins/                  - 管理后台：插件列表页
  GET  /plugins/tasks             - 管理后台：任务记录列表
"""

import json
import logging
import config
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import Shop
from models.plugin import ClientPlugin, PluginTask
from models.database import db, get_beijing_time

# 创建两个蓝图：
#   plugin_api_bp - 客户端API接口（注册到 /api/plugin/...）
#   plugin_bp     - 管理后台页面（注册到 /plugins/...）
plugin_api_bp = Blueprint('plugin_api', __name__)
plugin_bp = Blueprint('plugin', __name__)

logger = logging.getLogger(__name__)


# ================================================================
# 辅助函数：通过shop_token验证客户端身份
# ================================================================

def _get_shop_by_token() -> Shop | None:
    """
    从请求头中获取shop_token并验证店铺
    功能：客户端API的鉴权方式，使用X-Shop-Token请求头
    返回：Shop对象（验证通过）或None（验证失败）
    """
    # 从请求头获取token
    token = request.headers.get('X-Shop-Token', '').strip()
    if not token:
        return None
    # 查询数据库验证token
    shop = Shop.query.filter_by(shop_token=token, is_active=True).first()
    return shop


# ================================================================
# 客户端API（用shop_token鉴权，无��登录）
# ================================================================

@plugin_api_bp.route('/register', methods=['POST'])
def register():
    """
    客户端注册插件能力
    功能：客户端（dskehuduan）启动时调用此接口，向aikefu注册自己支持的插件
    鉴权：X-Shop-Token请求头（店铺Token）
    路径：POST /api/plugin/register（通过api_bp注册，前缀为/api/plugin）
    请求格式（JSON）：
    {
        "plugin_id": "auto_exchange",        // 插件唯一标识
        "name": "自动换号",                  // 插件中文名
        "description": "自动完成账号更换",   // 功能描述
        "action_codes": ["exchange", "login"], // 支持的动作码
        "client_version": "1.0.0"            // 客户端版本
    }
    返回：{'success': True, 'plugin_id': '...', 'message': '注册成功'}
    """
    shop = _get_shop_by_token()
    if not shop:
        return jsonify({'success': False, 'message': 'shop_token无效'}), 401

    data = request.get_json() or {}
    plugin_id = data.get('plugin_id', '').strip()
    name = data.get('name', plugin_id)
    description = data.get('description', '')
    action_codes = data.get('action_codes', [])
    client_version = data.get('client_version', '')

    if not plugin_id:
        return jsonify({'success': False, 'message': '缺少plugin_id'}), 400

    # 查找已有记录（同一店铺+插件ID唯一）
    plugin = ClientPlugin.query.filter_by(
        shop_id=shop.id,
        plugin_id=plugin_id,
    ).first()

    if not plugin:
        # 首次注册：创建新记录
        plugin = ClientPlugin(
            shop_id=shop.id,
            plugin_id=plugin_id,
            name=name,
            description=description,
            action_codes=json.dumps(action_codes, ensure_ascii=False),
            client_version=client_version,
            is_active=True,
            created_at=get_beijing_time(),
        )
        db.session.add(plugin)
        logger.info(f"[插件注册] 新插件注册: shop={shop.id} plugin_id={plugin_id}")
    else:
        # 重复注册：更新基本信息（版本可能升级）
        plugin.name = name or plugin.name
        plugin.description = description or plugin.description
        plugin.action_codes = json.dumps(action_codes, ensure_ascii=False)
        plugin.client_version = client_version
        plugin.is_active = True
        plugin.last_heartbeat = get_beijing_time()
        logger.info(f"[插件注册] 插件重新注册: shop={shop.id} plugin_id={plugin_id}")

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'plugin_id': plugin_id,
            'shop_id': shop.id,
            'message': '注册成功',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@plugin_api_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    客户端心跳保活
    功能：客户端每30秒发送一次心跳，aikefu据此判断客户端是否在线
    鉴权：X-Shop-Token请求头
    请求格式（JSON）：{"plugin_id": "auto_exchange"}
    返回：{'success': true, 'pending_tasks': 待处理任务数量}
    """
    shop = _get_shop_by_token()
    if not shop:
        return jsonify({'success': False, 'message': 'shop_token无效'}), 401

    data = request.get_json() or {}
    plugin_id = data.get('plugin_id', '').strip()

    if not plugin_id:
        return jsonify({'success': False, 'message': '缺少plugin_id'}), 400

    plugin = ClientPlugin.query.filter_by(
        shop_id=shop.id,
        plugin_id=plugin_id,
    ).first()

    if not plugin:
        return jsonify({'success': False, 'message': '插件未注册，请先调用register接口'}), 404

    plugin.last_heartbeat = get_beijing_time()

    try:
        db.session.commit()
        # 同时返回当前待处理任务数量（方便客户端决定是否立即轮询）
        pending_count = PluginTask.query.filter_by(
            shop_id=shop.id,
            plugin_id=plugin_id,
            status='pending',
        ).count()
        return jsonify({'success': True, 'pending_tasks': pending_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@plugin_api_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """
    客户端轮询待执行任务
    功能：客户端定时轮询此接口，获取aikefu下发的待执行任务
    鉴权：X-Shop-Token请求头
    查询参数：plugin_id（指定插件ID，只返回该插件的任务）
    返回：{'success': true, 'tasks': [...待处理任务列表...]}\n    任务格式：
    {
        "task_id": "UUID",
        "action_code": "auto_exchange",
        "payload": {"buyer_id": "...", "order_id": "..."},
        "created_at": "2026-03-09 10:00:00"
    }
    """
    shop = _get_shop_by_token()
    if not shop:
        return jsonify({'success': False, 'message': 'shop_token无效'}), 401

    plugin_id = request.args.get('plugin_id', '').strip()

    # 查询该店铺的待处理任务
    query = PluginTask.query.filter_by(shop_id=shop.id, status='pending')
    if plugin_id:
        query = query.filter_by(plugin_id=plugin_id)

    # 按创建时间升序（先进先出）
    tasks = query.order_by(PluginTask.created_at.asc()).limit(10).all()

    # 使用 Redis 原子锁过滤已被其他客户端锁定的任务
    from models.database import redis_client
    result_tasks = []
    for task in tasks:
        if redis_client:
            try:
                lock_key = f"task_lock:{task.task_id}"
                acquired = redis_client.set(lock_key, plugin_id or 'default',
                                            nx=True, ex=config.REDIS_TASK_LOCK_TTL)
                if not acquired:
                    continue  # 已被其他客户端锁定，跳过该任务
            except Exception:
                pass  # Redis 不可用时降级为不加锁
        result_tasks.append(task)

    return jsonify({
        'success': True,
        'tasks': [t.to_dict() for t in result_tasks],
        'count': len(result_tasks),
    })


@plugin_api_bp.route('/tasks/<string:task_id>/done', methods=['POST'])
def task_done(task_id: str):
    """
    客户端上报任务完成
    功能：客户端执行成功后，调用此接口上报结果；
          aikefu 自动根据 intent_rules.done_reply_tpl 生成买家回复话术，
          通过响应中的 reply_to_buyer 字段返回，客户端负责将其发送给买家
    鉴权：X-Shop-Token请求头
    路径参数：task_id 为 UUID 字符串（如 "550e8400-e29b-41d4-a716-446655440000"）
    请求格式（JSON）：
    {
        "result": {
            "success": true,
            "new_account": "账号----密码",
            "message": "换号成功"
        }
    }
    返回：
    {
        "success": true,
        "reply_to_buyer": "换号完成！新账号：xxx（话术模板填充后），空字符串表示无需回复"
    }
    """
    shop = _get_shop_by_token()
    if not shop:
        return jsonify({'success': False, 'message': 'shop_token无效'}), 401

    # 用 UUID task_id 字段查询（兼容旧整数 id 降级查询）
    task = PluginTask.query.filter_by(task_id=task_id, shop_id=shop.id).first()
    if not task:
        # 降级：尝试用整数 id 查询（兼容旧版客户端）
        try:
            task = PluginTask.query.filter_by(id=int(task_id), shop_id=shop.id).first()
        except (ValueError, TypeError):
            pass
    if not task:
        return jsonify({'success': False, 'message': '任务不存在或无权访问'}), 404

    data = request.get_json() or {}
    result = data.get('result', {'success': True})

    # 更新任务状态为完成
    task.status = 'done'
    task.result = json.dumps(result, ensure_ascii=False)
    task.done_at = get_beijing_time()

    # 根据 action_code 查找对应意图规则，生成完成回复话术
    reply_to_buyer = ''
    try:
        from models.intent_rule import IntentRule
        from models.database import db as _db
        rule = IntentRule.query.filter(
            IntentRule.action_code == task.action_code,
            IntentRule.is_active.is_(True),
        ).order_by(IntentRule.priority.asc()).first()
        if rule and rule.done_reply_tpl:
            # 用任务结果填充话术模板变量（如 {new_account}, {order_id}）
            reply_to_buyer = rule.get_reply_for_done(result)
    except Exception as e:
        logger.warning(f"[插件任务] 获取完成话术失败: task_id={task_id}, error={e}")

    try:
        db.session.commit()
        logger.info(f"[插件任务] 任务完成: task_id={task_id} shop={shop.id}")
        return jsonify({
            'success': True,
            'message': '任务已标记为完成',
            'reply_to_buyer': reply_to_buyer,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@plugin_api_bp.route('/tasks/<string:task_id>/fail', methods=['POST'])
def task_fail(task_id: str):
    """
    客户端上报任务失败
    功能：客户端执行失败后，调用此接口上报失败原因
    鉴权：X-Shop-Token请求头
    路径参数：task_id 为 UUID 字符串（如 "550e8400-e29b-41d4-a716-446655440000"）
    请求格式（JSON）：
    {
        "reason": "账号库已空，无可用账号"
    }
    返回：{'success': true, 'message': '任务已标记为失败'}
    """
    shop = _get_shop_by_token()
    if not shop:
        return jsonify({'success': False, 'message': 'shop_token无效'}), 401

    # 用 UUID task_id 字段查询（兼容旧整数 id 降级查询）
    task = PluginTask.query.filter_by(task_id=task_id, shop_id=shop.id).first()
    if not task:
        # 降级：尝试用整数 id 查询（兼容旧版客户端）
        try:
            task = PluginTask.query.filter_by(id=int(task_id), shop_id=shop.id).first()
        except (ValueError, TypeError):
            pass
    if not task:
        return jsonify({'success': False, 'message': '任务不存在或无权访问'}), 404

    data = request.get_json() or {}
    reason = data.get('reason', '未知错误')

    # 更新任务状态为失败
    task.status = 'failed'
    task.result = json.dumps({'success': False, 'reason': reason}, ensure_ascii=False)
    task.done_at = get_beijing_time()

    try:
        db.session.commit()
        logger.warning(f"[插件任务] 任务失败: task_id={task_id} shop={shop.id} reason={reason}")
        return jsonify({'success': True, 'message': '任务已标记为失败'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ================================================================
# 管理后台页面（需登录）
# ================================================================

@plugin_bp.route('/')
@login_required
def index():
    """
    插件列表页
    功能：显示所有已注册的客户端插件，包括在线状态
    """
    if current_user.is_admin():
        shops = Shop.query.filter_by(is_active=True).all()
        shop_ids = [s.id for s in shops]
    else:
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id, is_active=True
        ).all()
        shop_ids = [s.id for s in shops]

    plugins = ClientPlugin.query.filter(
        ClientPlugin.shop_id.in_(shop_ids)
    ).order_by(ClientPlugin.created_at.desc()).all()

    return render_template('plugins/index.html', plugins=plugins, shops=shops)

@plugin_bp.route('/tasks')
@login_required
def task_list():
    """
    任务记录列表
    功能：显示所有插件任务记录，支持按状态和店铺筛选
    """
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    shop_id_filter = request.args.get('shop_id', type=int)

    if current_user.is_admin():
        shops = Shop.query.filter_by(is_active=True).all()
        shop_ids = [s.id for s in shops]
    else:
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id, is_active=True
        ).all()
        shop_ids = [s.id for s in shops]

    query = PluginTask.query.filter(PluginTask.shop_id.in_(shop_ids))

    if status_filter:
        query = query.filter_by(status=status_filter)
    if shop_id_filter and shop_id_filter in shop_ids:
        query = query.filter_by(shop_id=shop_id_filter)

    tasks = query.order_by(PluginTask.created_at.desc()).paginate(
        page=page, per_page=20
    )

    # 统计各状态数量
    stats = {
        'pending': PluginTask.query.filter(
            PluginTask.shop_id.in_(shop_ids), PluginTask.status == 'pending'
        ).count(),
        'done': PluginTask.query.filter(
            PluginTask.shop_id.in_(shop_ids), PluginTask.status == 'done'
        ).count(),
        'failed': PluginTask.query.filter(
            PluginTask.shop_id.in_(shop_ids), PluginTask.status == 'failed'
        ).count(),
    }

    return render_template('plugins/tasks.html',
        tasks=tasks,
        shops=shops,
        stats=stats,
        status_filter=status_filter,
        shop_id_filter=shop_id_filter,
    )
