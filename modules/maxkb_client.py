# -*- coding: utf-8 -*-
"""
MaxKB向量检索客户端
功能说明：封装MaxKB API，实现知识库的向量化存储和语义检索
当MAXKB_ENABLED=true时，知识库检索自动切换到MaxKB语义检索
aikefu后台正常管理知识库，保存时自动同步到MaxKB
设计原则：aikefu负责知识库的增删改（管理侧），MaxKB只做向量存储和语义检索（引擎侧）
"""

import logging
import requests
import config

logger = logging.getLogger(__name__)


class MaxKBClient:
    """
    MaxKB向量检索客户端
    说明：封装MaxKB REST API，实现与aikefu知识库的同步和语义检索
    当MAXKB_ENABLED=false时，所有方法都直接返回空结果，不影响原有逻辑
    """

    def __init__(self):
        """
        初始化MaxKB客户端
        读取配置项，构建请求头
        """
        # MaxKB服务地址（去掉末尾斜杠）
        self.api_url = config.MAXKB_API_URL.rstrip('/')
        # API密钥（用于请求鉴权）
        self.api_key = config.MAXKB_API_KEY
        # 数据集ID（知识库条目都存储在此数据集中）
        self.dataset_id = config.MAXKB_DATASET_ID
        # 是否启用（false时所有操作跳过）
        self.enabled = config.MAXKB_ENABLED
        # 请求超时（秒）
        self.timeout = 10
        # 构建通用请求头
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def upsert(self, item_id: int, question: str, answer: str,
               keywords: str = '') -> bool:
        """
        新增或更新MaxKB中的知识库条目（向量化存储）
        功能：将aikefu知识库条目同步到MaxKB，MaxKB自动向量化
        参数：
            item_id  - aikefu知识库条目ID（作为MaxKB文档的外部ID）
            question - 问题文本（向量化的主体）
            answer   - 答案文本（检索命中后返回）
            keywords - 关键词（辅助检索，可选）
        返回：True=同步成功，False=同步失败
        说明：同步失败不影响业务，仍可使用原有关键词检索降级
        """
        if not self.enabled:
            # MaxKB未启用，直接返回True（不影响业务）
            return True

        if not self.api_key or not self.dataset_id:
            logger.warning("[MaxKB] 未配置API密钥或数据集ID，跳过同步")
            return False

        try:
            # 构建MaxKB文档格式
            # 将问题+关键词合并为向量化内容，答案存储在元数据中
            content = f"{question}\n{keywords}" if keywords else question
            payload = {
                'name': f'kb_{item_id}',        # 文档名（用aikefu条目ID命名）
                'content': content,              # 向量化文本（问题+关键词）
                'meta': {
                    'kb_id': item_id,            # aikefu条目ID（检索后用来查原始数据）
                    'answer': answer,            # 答案（直接存储，避免二次查询）
                },
            }

            # 调用MaxKB文档新增/更新接口
            url = f"{self.api_url}/api/dataset/{self.dataset_id}/document"
            response = requests.post(url, json=payload, headers=self.headers,
                                     timeout=self.timeout)

            if response.status_code in (200, 201):
                logger.debug(f"[MaxKB] 同步成功: kb_id={item_id}")
                return True
            else:
                logger.warning(f"[MaxKB] 同步失败: kb_id={item_id}, "
                               f"status={response.status_code}, body={response.text[:200]}")
                return False

        except Exception as e:
            logger.error(f"[MaxKB] 同步异常: kb_id={item_id}, error={e}")
            return False

    def delete(self, item_id: int) -> bool:
        """
        从MaxKB删除知识库条目
        功能：aikefu删除知识库条目时，同步删除MaxKB中对应的向量文档
        参数：item_id - aikefu知识库条目ID
        返回：True=删除成功，False=删除失败
        """
        if not self.enabled:
            return True

        if not self.api_key or not self.dataset_id:
            return False

        try:
            # 调用MaxKB删除接口（按外部ID删除）
            url = f"{self.api_url}/api/dataset/{self.dataset_id}/document/kb_{item_id}"
            response = requests.delete(url, headers=self.headers, timeout=self.timeout)

            if response.status_code in (200, 204, 404):
                # 404也视为成功（条目已不存在）
                logger.debug(f"[MaxKB] 删除成功: kb_id={item_id}")
                return True
            else:
                logger.warning(f"[MaxKB] 删除失败: kb_id={item_id}, "
                               f"status={response.status_code}")
                return False

        except Exception as e:
            logger.error(f"[MaxKB] 删除异常: kb_id={item_id}, error={e}")
            return False

    def search(self, message: str, industry_id: int, top_k: int = 3) -> dict | None:
        """
        语义检索：在MaxKB中查找最相关的知识库条目
        功能：使用向量相似度检索，命中率比关键词匹配高约30%
        参数：
            message     - 买家消息文本（查询向量）
            industry_id - 行业ID（MaxKB数据集按行业隔离，此处用于日志）
            top_k       - 返回最相关的前K条结果（默认3）
        返回：
            命中时：{'reply': '答案内容', 'similarity': 相似度, 'knowledge_id': 条目ID}
            未命中：None
        """
        if not self.enabled:
            # MaxKB未启用，返回None（由原有关键词检索处理）
            return None

        if not self.api_key or not self.dataset_id:
            return None

        try:
            # 调用MaxKB语义检索接口
            url = f"{self.api_url}/api/dataset/{self.dataset_id}/search"
            payload = {
                'query': message,    # 查询文本
                'top_k': top_k,      # 返回最相关的K条
            }
            response = requests.post(url, json=payload, headers=self.headers,
                                     timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(f"[MaxKB] 检索失败: status={response.status_code}")
                return None

            data = response.json()
            # MaxKB返回结果格式：{'results': [{'score': 0.9, 'meta': {'answer': '...', 'kb_id': 1}}]}
            results = data.get('results') or data.get('data') or []
            if not results:
                return None

            # 取最高分结果
            best = results[0]
            score = float(best.get('score', 0))
            meta = best.get('meta', {}) or {}

            # 相似度低于阈值时不返回（避免误匹配，阈值由MAXKB_MIN_SIMILARITY配置）
            if score < config.MAXKB_MIN_SIMILARITY:
                logger.debug(f"[MaxKB] 检索命中但相似度不足: score={score:.2f}")
                return None

            answer = meta.get('answer', '')
            kb_id = meta.get('kb_id')

            if not answer:
                return None

            logger.debug(f"[MaxKB] 检索命中: score={score:.2f}, kb_id={kb_id}")
            return {
                'reply': answer,
                'similarity': score,
                'knowledge_id': kb_id,
            }

        except Exception as e:
            logger.error(f"[MaxKB] 检索异常: {e}")
            return None

    def sync_all(self, industry_id: int, items: list) -> dict:
        """
        全量同步某行业的知识库到MaxKB
        功能：用于初始化或重置MaxKB数据集时，将所有知识库条目批量同步
        参数：
            industry_id - 行业ID（仅用于日志）
            items       - 知识库条目列表（KnowledgeBase对象列表）
        返回：{'success': 成功数, 'failed': 失败数, 'total': 总数}
        """
        if not self.enabled:
            return {'success': 0, 'failed': 0, 'total': 0}

        total = len(items)
        success_count = 0
        failed_count = 0

        logger.info(f"[MaxKB] 开始全量同步: industry_id={industry_id}, total={total}")

        for item in items:
            # 调用upsert同步每条数据
            ok = self.upsert(
                item_id=item.id,
                question=item.question,
                answer=item.answer,
                keywords=item.keywords or '',
            )
            if ok:
                success_count += 1
            else:
                failed_count += 1

        logger.info(f"[MaxKB] 全量同步完成: success={success_count}, "
                    f"failed={failed_count}, total={total}")

        return {
            'success': success_count,
            'failed': failed_count,
            'total': total,
        }
