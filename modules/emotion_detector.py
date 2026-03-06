# -*- coding: utf-8 -*-
"""
情绪识别模块
功能说明：分析买家消息情绪，分级处理
情绪过激时自动转人工，保护平台账号安全
"""

import re


class EmotionDetector:
    """
    情绪识别引擎
    说明：基于关键词和规则识别买家情绪级别
    情绪级别：0=正常, 1=轻微不满, 2=中度不满, 3=严重不满, 4=危机
    """

    # 各情绪级别的关键词（按严重程度分层）
    EMOTION_KEYWORDS = {
        # 危机级别（4）：威胁、极端言辞
        4: [
            '投诉', '举报', '曝光', '律师', '法院', '起诉', '骗子', '欺诈',
            '消费者协会', '315', '黑猫投诉', '差评', '告你',
        ],
        # 严重不满（3）：强烈情绪词汇
        3: [
            '退款', '退钱', '骗人', '假货', '虚假', '不给', '不行', '滚',
            '垃圾', '太差了', '差劲', '无耻', '混蛋', '傻逼', '去死',
        ],
        # 中度不满（2）：明显负面情绪
        2: [
            '不满意', '失望', '不好用', '问题', '故障', '坏了', '不能用',
            '什么情况', '怎么回事', '搞什么', '烦死了', '气死了',
        ],
        # 轻微不满（1）：轻微负面
        1: [
            '等等', '怎么', '为什么', '不太好', '稍微', '有点',
            '麻烦', '不方便', '希望改进',
        ],
    }

    # 情绪级别对应的文字描述
    LEVEL_TEXT = {
        0: '正常',
        1: '轻微不满',
        2: '中度不满',
        3: '严重不满',
        4: '危机',
    }

    def detect(self, message: str) -> dict:
        """
        检测消息情绪级别
        功能：扫描消息中的情绪关键词，返回最高情绪级别
        参数：message - 买家消息内容
        返回：
            {
                'level': 情绪级别(0-4),
                'level_text': 级别描述,
                'keywords_hit': 命中的关键词列表,
                'needs_human': 是否需要转人工
            }
        """
        msg_lower = message.lower()
        max_level = 0
        keywords_hit = []

        # 从最高级别开始检查（危机 -> 严重 -> 中等 -> 轻微）
        for level in [4, 3, 2, 1]:
            for keyword in self.EMOTION_KEYWORDS[level]:
                if keyword in msg_lower:
                    keywords_hit.append(keyword)
                    if level > max_level:
                        max_level = level

        # 情绪级别 >= 3 时需要转人工
        needs_human = max_level >= 3

        return {
            'level': max_level,
            'level_text': self.LEVEL_TEXT.get(max_level, '正常'),
            'keywords_hit': list(set(keywords_hit)),  # 去重
            'needs_human': needs_human,
        }

    def get_response_strategy(self, level: int) -> str:
        """
        根据情绪级别获取回复策略建议
        功能：不同情绪级别使用不同的回复语气和策略
        参数：level - 情绪级别
        返回：回复策略描述
        """
        strategies = {
            0: '正常友好回复',
            1: '多一分耐心，语气温柔',
            2: '深度道歉，表达理解，提出解决方案',
            3: '立即转人工，发送安抚话术',
            4: '紧急转人工，记录到黑名单观察',
        }
        return strategies.get(level, '正常回复')

    def get_appease_message(self, level: int) -> str:
        """
        获取对应情绪级别的安抚话术
        功能：严重情绪时发送安抚消息，缓解买家情绪
        参数：level - 情绪级别
        返回：安抚话术文本
        """
        messages = {
            2: '非常抱歉给您带来不便，我们非常重视您的反馈，请稍等，我马上为您处理！',
            3: '非常抱歉！我完全理解您的不满，这确实是我们的失误，我立即为您安排专属客服解决！',
            4: '非常非常抱歉！我已将您的问题标记为紧急，资深客服将在1分钟内联系您，请稍候！',
        }
        return messages.get(level, '')
