# -*- coding: utf-8 -*-
"""
意图规则数据模型
功能说明：存储可自定义的意图识别规则，支持关键词匹配、插件动作触发和话术模板
可热更新，运营无需修改代码即可添加/修改意图规则
替代原 ai_engine.py 中的硬编码 LOCAL_INTENT_RULES 和 PLUGIN_INTENT_ACTIONS
"""

import json
from .database import db, get_beijing_time


class IntentRule(db.Model):
    """
    意图规则表
    说明：将意图识别规则存入数据库，替代代码中的硬编码规则
    支持按行业隔离（industry_id=None 表示全局规则，所有行业共用）
    优先匹配行业规则，再匹配全局规则
    """
    __tablename__ = 'intent_rules'

    # 主键ID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 所属行业ID（外键 industries.id），NULL=全局规则（所有行业共用）
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'), nullable=True)

    # 意图标识（如 exchange/refund/login），程序内部使用
    intent_code = db.Column(db.String(50), nullable=False)

    # 意图标识中文说明（如 "换号请求 — 买家要求更换游戏账号"），选填
    intent_code_label = db.Column(db.String(200), nullable=True)

    # 显示名（如 换号请求），后台管理界面显示用
    intent_name = db.Column(db.String(100), nullable=False)

    # 触发关键词 JSON数组（如 ["换号","换个号","换一个"]）
    keywords = db.Column(db.Text, nullable=False, default='[]')

    # 触发的插件动作码（如 auto_exchange），可为空（无需插件处理的意图）
    action_code = db.Column(db.String(50), nullable=True)

    # 插件动作码中文说明（如 "🔄 自动换号 — 触发U号租自动换号流程"），选填
    action_code_label = db.Column(db.String(200), nullable=True)

    # 识别后立即回复的话术模板（如 "好的，正在为您换号，请稍候～"），可为空
    auto_reply_tpl = db.Column(db.Text, nullable=True)

    # 插件完成后回复模板（如 "换号完成！新账号：{new_account}"），可为空
    # 支持 {变量名} 占位符，由插件返回的 result 字典填充
    done_reply_tpl = db.Column(db.Text, nullable=True)

    # 优先级（数字越小越先匹配）
    priority = db.Column(db.Integer, default=0, nullable=False)

    # 是否启用
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # 创建时间
    created_at = db.Column(db.DateTime, nullable=False)

    # 最后修改时间
    updated_at = db.Column(db.DateTime, nullable=True)

    # 关联关系：所属行业
    industry = db.relationship(
        'Industry',
        backref=db.backref('intent_rules', lazy='dynamic')
    )

    def get_keywords(self) -> list:
        """
        解析关键词JSON数组，返回列表
        返回：关键词列表（如 ['换号', '换个号']）；解析失败返回空列表
        """
        try:
            return json.loads(self.keywords) if self.keywords else []
        except (json.JSONDecodeError, TypeError):
            return []

    def get_reply_for_done(self, result: dict) -> str:
        """
        用插件执行结果填充完成回复模板
        参数：result - 插件返回的结果字典（如 {"new_account": "acc123", "order_id": "..."}）
        返回：填充后的回复文本；模板为空则返回空字符串
        说明：模板中的 {变量名} 占位符会被 result 中对应键的值替换
        """
        tpl = self.done_reply_tpl or ''
        if not tpl:
            return ''
        try:
            return tpl.format(**result)
        except (KeyError, IndexError, ValueError):
            # 模板变量不匹配时，返回原模板（不报错，避免影响主流程）
            return tpl

    def __repr__(self):
        return f'<IntentRule {self.intent_code}: {self.intent_name}>'

    @staticmethod
    def get_action_code_labels() -> dict:
        """
        内置动作码中文说明字典
        用于前端下拉选择框展示，key=动作码，value=中文说明
        """
        return {
            "auto_exchange":  "🔄 自动换号 — 触发U号租自动换号流程",
            "handle_refund":  "💰 退款处理 — 记录退款申请，通知人工处理",
            "auto_order":     "📦 自动下单 — 自动在U号租下单选号（开发中）",
            "transfer_human": "👤 转人工 — 自动将会话转移给人工客服",
            "refund_guide":   "📋 退款引导 — 引导买家申请退款流程",
        }

    @staticmethod
    def get_intent_code_labels() -> dict:
        """
        常用意图标识中文说明字典
        用于前端输入框提示
        """
        return {
            "exchange":       "换号请求 — 买家要求更换游戏账号",
            "refund":         "退款申请 — 买家申请退款或退货",
            "login":          "登录问题 — 买家反映账号登录异常",
            "complaint":      "投诉举报 — 买家投诉、差评或维权",
            "query":          "查询咨询 — 买家询问订单、发货等信息",
            "payment":        "付款问题 — 买家反映付款相关问题",
            "transfer_human": "转人工 — 买家主动要求转接人工客服",
            "other":          "其他 — 无法归类的其他意图",
        }
