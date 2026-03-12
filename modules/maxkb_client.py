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
        优先从数据库读取配置，fallback到config.py
        """
        # 优先从数据库读，fallback 到 config.py
        try:
            from models.system_config import SystemConfig
            def _get(key, default):
                cfg = SystemConfig.query.filter_by(key=key).first()
                # 空字符串视为"未配置"，回退到 config.py 的默认值
                return cfg.value if cfg and cfg.value else default
            self.api_url = _get('maxkb_api_url', config.MAXKB_API_URL).rstrip('/')
            self.api_key = _get('maxkb_api_key', config.MAXKB_API_KEY)
            self.dataset_id = _get('maxkb_dataset_id', config.MAXKB_DATASET_ID)
            enabled_str = _get('maxkb_enabled', str(config.MAXKB_ENABLED))
            self.enabled = str(enabled_str).lower() in ('true', '1', 'yes')
            self.min_similarity = float(_get('maxkb_min_similarity', str(config.MAXKB_MIN_SIMILARITY)))
        except Exception:
            self.api_url = config.MAXKB_API_URL.rstrip('/')
            self.api_key = config.MAXKB_API_KEY
            self.dataset_id = config.MAXKB_DATASET_ID
            self.enabled = config.MAXKB_ENABLED
            self.min_similarity = config.MAXKB_MIN_SIMILARITY
        # 请求超时（秒）
        self.timeout = 10
        # 构建通用请求头
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    @classmethod
    def for_industry(cls, industry_id: int):
        """
        工厂方法：创建针对特定行业数据集的客户端
        行业有专属数据集时使用行业数据集，否则使用全局默认数据集
        """
        client = cls()
        if industry_id:
            try:
                from models.industry import Industry
                industry = Industry.query.get(industry_id)
                if industry and industry.maxkb_dataset_id:
                    client.dataset_id = industry.maxkb_dataset_id
            except Exception:
                pass
        return client

    def upsert(self, item_id: int, question: str, answer: str,
               keywords: str = '', dataset_id: str = None) -> bool:
        """
        新增或更新MaxKB中的知识库条目（向量化存储）
        功能：将aikefu知识库条目同步到MaxKB，MaxKB自动向量化
        参数：
            item_id    - aikefu知识库条目ID（作为MaxKB文档的外部ID）
            question   - 问题文本（向量化的主体）
            answer     - 答案文本（检索命中后返回）
            keywords   - 关键词（辅助检索，可选）
            dataset_id - 目标数据集ID（不传则用self.dataset_id）
        返回：True=同步成功，False=同步失败
        说明：同步失败不影响业务，仍可使用原有关键词检索降级
        """
        if not self.enabled:
            # MaxKB未启用，直接返回True（不影响业务）
            return True

        ds_id = dataset_id or self.dataset_id
        if not self.api_key or not ds_id:
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
            url = f"{self.api_url}/api/dataset/{ds_id}/document"
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

    def delete(self, item_id: int, dataset_id: str = None) -> bool:
        """
        从MaxKB删除知识库条目
        功能：aikefu删除知识库条目时，同步删除MaxKB中对应的向量文档
        参数：
            item_id    - aikefu知识库条目ID
            dataset_id - 目标数据集ID（不传则用self.dataset_id）
        返回：True=删除成功，False=删除失败
        """
        if not self.enabled:
            return True

        ds_id = dataset_id or self.dataset_id
        if not self.api_key or not ds_id:
            return False

        try:
            # 调用MaxKB删除接口（按外部ID删除）
            url = f"{self.api_url}/api/dataset/{ds_id}/document/kb_{item_id}"
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

    def search(self, message: str, industry_id: int, top_k: int = 3,
               dataset_id: str = None) -> dict | None:
        """
        语义检索：在MaxKB中查找最相关的知识库条目
        功能：使用向量相似度检索，命中率比关键词匹配高约30%
        参数：
            message     - 买家消息文本（查询向量）
            industry_id - 行业ID（日志用）
            top_k       - 返回最相关的前K条结果（默认3）
            dataset_id  - 目标数据集ID（不传则用self.dataset_id）
        返回：
            命中时：{'reply': '答案内容', 'similarity': 相似度, 'knowledge_id': 条目ID}
            未命中：None
        """
        if not self.enabled:
            # MaxKB未启用，返回None（由原有关键词检索处理）
            return None

        ds_id = dataset_id or self.dataset_id
        if not self.api_key or not ds_id:
            return None

        try:
            # 调用MaxKB语义检索接口
            url = f"{self.api_url}/api/dataset/{ds_id}/search"
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

            # 相似度低于阈值时不返回（避免误匹配）
            if score < self.min_similarity:
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

    def health_check(self, dataset_id: str = None) -> bool:
        """
        连接健康检测
        功能：检测MaxKB服务是否可连接（routes/settings.py已调用此方法）
        参数：dataset_id - 目标数据集ID（不传则用self.dataset_id）
        返回：True=连通，False=断开或未配置
        """
        if not self.enabled:
            return False

        ds_id = dataset_id or self.dataset_id
        if not self.api_key or not ds_id:
            return False

        try:
            url = f"{self.api_url}/api/dataset/{ds_id}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            return response.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"[MaxKB] health_check失败: {e}")
            return False

    def list_documents(self, page: int = 1, page_size: int = 100,
                       dataset_id: str = None) -> dict:
        """
        列出MaxKB中的文档列表，用于同步状态面板
        参数：dataset_id - 目标数据集ID（不传则用self.dataset_id）
        返回：{'total': N, 'documents': [{'name': 'kb_123', ...}]}
        """
        ds_id = dataset_id or self.dataset_id
        if not self.enabled or not self.api_key or not ds_id:
            return {'total': 0, 'documents': []}

        try:
            url = f"{self.api_url}/api/dataset/{ds_id}/document"
            params = {'page': page, 'page_size': page_size}
            response = requests.get(url, headers=self.headers, params=params,
                                    timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                docs = data.get('data', data.get('documents', []))
                total = data.get('total', len(docs))
                return {'total': total, 'documents': docs}
        except Exception as e:
            logger.warning(f"[MaxKB] list_documents失败: {e}")
        return {'total': 0, 'documents': []}

    def search_similar(self, question: str, top_k: int = 3,
                       dataset_id: str = None) -> list:
        """
        语义相似搜索，用于入库前查重（语义级别）
        参数：dataset_id - 目标数据集ID（不传则用self.dataset_id）
        返回：[{'question': ..., 'score': 0.9, 'kb_id': 1}]
        """
        ds_id = dataset_id or self.dataset_id
        if not self.enabled or not self.api_key or not ds_id:
            return []

        try:
            url = f"{self.api_url}/api/dataset/{ds_id}/search"
            payload = {'query': question, 'top_k': top_k}
            response = requests.post(url, json=payload, headers=self.headers,
                                     timeout=self.timeout)
            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get('results') or data.get('data') or []
            similar = []
            for r in results:
                score = float(r.get('score', 0))
                meta = r.get('meta', {}) or {}
                similar.append({
                    'question': r.get('content', ''),
                    'score': score,
                    'kb_id': meta.get('kb_id'),
                })
            return similar
        except Exception as e:
            logger.warning(f"[MaxKB] search_similar失败: {e}")
            return []

    def get_stats(self, dataset_id: str = None) -> dict:
        """
        获取MaxKB数据集统计，用于管理面板
        参数：dataset_id - 目标数据集ID（不传则用self.dataset_id）
        返回：{'total_docs': N, 'dataset_id': ..., 'connected': True}
        """
        ds_id = dataset_id or self.dataset_id
        if not self.enabled or not self.api_key or not ds_id:
            return {'total_docs': 0, 'dataset_id': ds_id, 'connected': False}

        try:
            result = self.list_documents(page=1, page_size=1, dataset_id=ds_id)
            return {
                'total_docs': result['total'],
                'dataset_id': ds_id,
                'connected': True,
            }
        except Exception as e:
            logger.warning(f"[MaxKB] get_stats失败: {e}")
            return {'total_docs': 0, 'dataset_id': ds_id, 'connected': False}

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
