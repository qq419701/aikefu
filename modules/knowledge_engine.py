# -*- coding: utf-8 -*-
"""
知识库引擎模块（三层处理 - 第二层）
功能说明：基于关键词相似度检索知识库，0成本处理约55%的消息
通过关键词匹配和简单的相似度计算，找到最相关的问答
"""

import re
from models import KnowledgeBase
from models.database import db


class KnowledgeEngine:
    """
    知识库引擎
    说明：在知识库中检索最相关的问答
    使用关键词重叠率计算相似度（简单高效，无需向量计算）
    """

    def __init__(self, similarity_threshold: float = 0.6):
        """
        初始化知识库引擎
        参数：similarity_threshold - 相似度阈值，超过才认为匹配
        """
        self.similarity_threshold = similarity_threshold

    def search(self, message: str, industry_id: int) -> dict | None:
        """
        在知识库中搜索最相关的答案
        功能：提取消息关键词，在知识库中计算相似度，返回最佳匹配
        参数：
            message - 买家消息内容
            industry_id - 行业ID（知识库按行业隔离）
        返回：
            匹配成功：{'reply': '答案内容', 'knowledge_id': 知识库ID, 'similarity': 相似度}
            匹配失败：None
        """
        # 获取该行业的所有启用知识库条目，按优先级排序
        items = KnowledgeBase.query.filter_by(
            industry_id=industry_id,
            is_active=True
        ).order_by(KnowledgeBase.priority.desc()).all()

        if not items:
            return None

        # 提取消息的词汇
        msg_words = self._extract_words(message)
        msg_lower = message.lower()

        best_match = None
        best_score = 0.0

        for item in items:
            score = self._calculate_similarity(msg_words, msg_lower, item)
            if score > best_score:
                best_score = score
                best_match = item

        # 检查是否超过相似度阈值
        if best_match and best_score >= self.similarity_threshold:
            # 记录命中次数
            best_match.hit_count = (best_match.hit_count or 0) + 1
            db.session.commit()

            return {
                'reply': best_match.answer,
                'knowledge_id': best_match.id,
                'question': best_match.question,
                'similarity': best_score,
            }

        return None

    def _extract_words(self, text: str) -> set:
        """
        从文本中提取词汇
        功能：简单分词，去除标点符号，支持中英文
        参数：text - 输入文本
        返回：词汇集合
        """
        # 去除标点符号
        text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
        # 分割单词
        words = text.lower().split()
        # 中文按字符切分（简单分词）
        chinese_chars = set()
        for w in words:
            if re.search(r'[\u4e00-\u9fff]', w):
                chinese_chars.update(list(w))
            else:
                chinese_chars.add(w)
        return chinese_chars

    def _calculate_similarity(self, msg_words: set, msg_original: str, item: KnowledgeBase) -> float:
        """
        计算消息与知识库条目的相似度
        功能：综合考虑问题相似度和关键词匹配
        参数：
            msg_words - 消息词汇集合（用于字符级重叠率计算）
            msg_original - 原始消息文本（用于关键词精确匹配）
            item - 知识库条目
        返回：相似度分数（0.0-1.0）
        """
        if not msg_words:
            return 0.0

        msg_lower = msg_original.lower()

        # 1. 计算与问题的词汇重叠率（字符级）
        question_words = self._extract_words(item.question)
        if question_words:
            overlap = len(msg_words & question_words)
            question_similarity = overlap / max(len(msg_words), len(question_words))
        else:
            question_similarity = 0.0

        # 2. 检查关键词匹配（在原始文本中搜索，支持多字词）
        keyword_score = 0.0
        keywords = item.get_keywords_list()
        if keywords:
            # 使用原始消息文本匹配关键词，支持多字中文词（如"登不上"）
            matched_keywords = sum(
                1 for kw in keywords
                if kw.lower() in msg_lower
            )
            keyword_score = matched_keywords / len(keywords)

        # 综合分数（关键词权重60%，问题相似度40%）
        if keywords:
            final_score = keyword_score * 0.6 + question_similarity * 0.4
        else:
            final_score = question_similarity

        return final_score

    def get_by_category(self, industry_id: int, category: str) -> list:
        """
        按分类获取知识库条目
        功能：用于管理界面分类展示知识库
        参数：
            industry_id - 行业ID
            category - 分类标签
        返回：知识库条目列表
        """
        items = KnowledgeBase.query.filter_by(
            industry_id=industry_id,
            category=category,
            is_active=True
        ).order_by(KnowledgeBase.priority.desc()).all()
        return [item.to_dict() for item in items]
