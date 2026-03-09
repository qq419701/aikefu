# -*- coding: utf-8 -*-
"""
客户端插件模型
功能说明：存储客户端注册的自动化插件信息
插件由客户端（dskehuduan）启动时注册，aikefu负责下发任务指令
插件设计原则：所有自动化操作在客户端执行，aikefu只做决策下发
表结构：
  client_plugins - 插件注册表（客户端能力清单）
  plugin_tasks   - 插件任务队列（aikefu下发给客户端的任务）
"""

import uuid
from .database import db, get_beijing_time


class ClientPlugin(db.Model):
    """
    客户端插件注册表
    说明：客户端启动时向aikefu注册自己支持的插件能力
    aikefu根据意图识别结果，将任务下发给对应插件
    每个插件绑定一个店铺（shop_id），通过shop_token鉴权
    """
    __tablename__ = 'client_plugins'

    # 主键ID（自增）
    id = db.Column(db.Integer, primary_key=True)

    # 插件唯一标识（如：auto_exchange、order_sync、auto_ship）
    # 命名规范：小写字母+下划线，与action_code保持一致
    plugin_id = db.Column(db.String(64), nullable=False, index=True)

    # 插件中文名称（如：自动换号、订单同步、自动发货）
    name = db.Column(db.String(100), nullable=False, default='')

    # 插件功能描述（详细说明插件的能力范围）
    description = db.Column(db.Text, default='')

    # 绑定的店铺ID（外键，插件只处理该店铺的任务）
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)

    # 支持的意图动作码（JSON数组格式，如：["exchange","login"]）
    # 客户端注册时声明自己能处理哪些动作
    action_codes = db.Column(db.Text, default='[]')

    # 客户端版本号（用于兼容性管理）
    client_version = db.Column(db.String(32), default='')

    # 最后心跳时间（客户端定时发送心跳，判断是否在线）
    last_heartbeat = db.Column(db.DateTime, nullable=True)

    # 是否启用（管理员可临时禁用某个插件）
    is_active = db.Column(db.Boolean, default=True)

    # 注册时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 关联店铺（用于获取店铺名称等信息）
    shop = db.relationship('Shop', foreign_keys=[shop_id])

    def get_action_codes(self) -> list:
        """
        获取支持的动作码列表
        返回：动作码字符串列表，如 ['exchange', 'login']
        """
        import json
        try:
            return json.loads(self.action_codes or '[]')
        except Exception:
            return []

    def is_online(self) -> bool:
        """
        判断客户端是否在线
        规则：最近5分钟内有心跳则视为在线
        返回：True=在线，False=离线或未知
        """
        if not self.last_heartbeat:
            return False
        from datetime import timedelta
        now = get_beijing_time()
        # 5分钟内有心跳视为在线
        return (now - self.last_heartbeat).total_seconds() < 300

    def to_dict(self) -> dict:
        """转换为字典格式，用于API响应"""
        import json
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'name': self.name,
            'description': self.description,
            'shop_id': self.shop_id,
            'shop_name': self.shop.name if self.shop else '',
            'action_codes': json.loads(self.action_codes or '[]'),
            'client_version': self.client_version,
            'last_heartbeat': self.last_heartbeat.strftime('%Y-%m-%d %H:%M:%S') if self.last_heartbeat else None,
            'is_online': self.is_online(),
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<ClientPlugin {self.plugin_id}: shop={self.shop_id}>'


class PluginTask(db.Model):
    """
    插件任务队列
    说明：aikefu根据AI决策生成任务，客户端轮询获取并执行
    任务执行后回调aikefu更新状态，形成完整的决策-执行-反馈闭环
    状态流转：pending → claimed（客户端领取）→ done/failed（执行完成）
    """
    __tablename__ = 'plugin_tasks'

    # 主键ID（自增）
    id = db.Column(db.Integer, primary_key=True)

    # 任务唯一ID（UUID，客户端轮询和回调使用）
    task_id = db.Column(db.String(36), unique=True, nullable=False,
                        default=lambda: str(uuid.uuid4()))

    # 所属店铺ID（任务只对该店铺的客户端可见）
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)

    # 目标插件ID（指定哪个插件来处理此任务）
    plugin_id = db.Column(db.String(64), nullable=False)

    # 动作码（如：exchange=换号, refund=退款, send_message=发消息）
    action_code = db.Column(db.String(50), nullable=False)

    # 任务参数（JSON格式，包含buyer_id/order_id/message等）
    payload = db.Column(db.Text, default='{}')

    # 任务状态：
    #   pending  = 待领取（客户端轮询时可见）
    #   claimed  = 已领取（客户端已开始执行）
    #   done     = 已完成（执行成功）
    #   failed   = 执行失败（需人工处理）
    status = db.Column(db.String(20), default='pending', index=True)

    # 执行结果（JSON格式，客户端执行完成后回传）
    result = db.Column(db.Text, default='{}')

    # 任务创建时间（北京时间）
    created_at = db.Column(db.DateTime, default=get_beijing_time)

    # 客户端领取时间（claimed状态时记录）
    claimed_at = db.Column(db.DateTime, nullable=True)

    # 任务完成时间（done/failed状态时记录）
    done_at = db.Column(db.DateTime, nullable=True)

    # 关联店铺
    shop = db.relationship('Shop', foreign_keys=[shop_id])

    def get_payload(self) -> dict:
        """
        获取任务参数字典
        返回：参数字典，如 {'buyer_id': '123', 'order_id': 'ABC'}
        """
        import json
        try:
            return json.loads(self.payload or '{}')
        except Exception:
            return {}

    def get_result(self) -> dict:
        """
        获取执行结果字典
        返回：结果字典，如 {'success': True, 'message': '换号成功'}
        """
        import json
        try:
            return json.loads(self.result or '{}')
        except Exception:
            return {}

    def to_dict(self) -> dict:
        """转换为字典格式，用于API响应（客户端轮询时的数据格式）"""
        import json
        return {
            'id': self.id,
            'task_id': self.task_id,
            'shop_id': self.shop_id,
            'plugin_id': self.plugin_id,
            'action_code': self.action_code,
            'payload': json.loads(self.payload or '{}'),
            'status': self.status,
            'result': json.loads(self.result or '{}'),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'claimed_at': self.claimed_at.strftime('%Y-%m-%d %H:%M:%S') if self.claimed_at else None,
            'done_at': self.done_at.strftime('%Y-%m-%d %H:%M:%S') if self.done_at else None,
        }

    def __repr__(self):
        return f'<PluginTask {self.task_id}: {self.action_code} {self.status}>'
