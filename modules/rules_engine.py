# -*- coding: utf-8 -*-
"""
规则引擎模块（三层处理 - 第一层）
功能说明：基于关键词规则匹配，0成本处理约20%的消息
规则优先级最高，匹配即返回，不调用AI
"""

import re
import json
from models import Rule
from models.database import db


class RulesEngine:
    """
    规则引擎
    说明：通过关键词匹配快速回复常见问题
    支持三种匹配模式：任一词匹配(any)、所有词匹配(all)、精确匹配(exact)
    """

    def __init__(self):
        """初始化规则引擎"""
        pass

    def match(self, message: str, industry_id: int) -> dict | None:
        """
        尝试匹配消息到规则
        功能：按优先级从高到低遍历规则，找到第一个匹配的规则
        参数：
            message - 买家消息内容
            industry_id - 行业ID（规则按行业隔离）
        返回：
            匹配成功：{'reply': '回复内容', 'rule_id': 规则ID, 'action': 动作类型}
            匹配失败：None
        """
        # 获取该行业所有启用的规则，按优先级倒序排列
        rules = Rule.query.filter_by(
            industry_id=industry_id,
            is_active=True
        ).order_by(Rule.priority.desc()).all()

        for rule in rules:
            if self._is_matched(message, rule):
                # 记录命中次数
                rule.hit_count = (rule.hit_count or 0) + 1
                db.session.commit()

                # 解析动作参数
                action_params = {}
                try:
                    action_params = json.loads(rule.action_params or '{}')
                except Exception:
                    pass

                return {
                    'reply': rule.reply_content,
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'action': rule.action_type,
                    'action_params': action_params,
                }

        return None

    def _is_matched(self, message: str, rule: Rule) -> bool:
        """
        判断消息是否匹配规则
        功能：根据规则的匹配模式进行匹配判断
        参数：
            message - 消息内容
            rule - 规则对象
        返回：True=匹配，False=不匹配
        """
        keywords = rule.get_keywords_list()
        if not keywords:
            return False

        # 消息转为小写，便于不区分大小写匹配
        msg_lower = message.lower()

        if rule.match_mode == 'exact':
            # 精确匹配：消息完全等于某个关键词
            return any(msg_lower == kw.lower() for kw in keywords)

        elif rule.match_mode == 'all':
            # 全词匹配：消息包含所有关键词
            return all(kw.lower() in msg_lower for kw in keywords)

        else:
            # 任一匹配（默认）：消息包含任一关键词
            return any(kw.lower() in msg_lower for kw in keywords)

    def format_reply(self, template: str, context: dict) -> str:
        """
        格式化回复内容，替换模板变量
        功能：将回复模板中的变量替换为实际值
        参数：
            template - 回复模板，如 "您好 {buyer_name}，您的订单 {order_id} ..."
            context - 上下文变量字典，如 {'buyer_name': '张三', 'order_id': '123456'}
        返回：格式化后的回复内容
        """
        try:
            for key, value in context.items():
                template = template.replace(f'{{{key}}}', str(value))
            return template
        except Exception:
            return template

    def get_industry_rules(self, industry_id: int) -> list:
        """
        获取行业所有规则
        功能：返回指定行业的规则列表，用于管理界面展示
        参数：industry_id - 行业ID
        返回：规则列表
        """
        rules = Rule.query.filter_by(
            industry_id=industry_id
        ).order_by(Rule.priority.desc()).all()
        return [r.to_dict() for r in rules]
