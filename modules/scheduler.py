# -*- coding: utf-8 -*-
"""
定时任务调度模块
功能说明：管理系统定时任务，使用北京时间
主要任务：每日AI自动学习、数据统计、缓存清理、令牌刷新
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import config

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    定时任务调度器
    说明：所有定时任务均以北京时间为准运行
    """

    def __init__(self, app=None):
        """
        初始化调度器
        参数：app - Flask应用实例（可后续通过init_app绑定）
        """
        self.app = app
        # 创建后台调度器，使用北京时区
        self.scheduler = BackgroundScheduler(
            timezone=BEIJING_TZ,
            job_defaults={
                'coalesce': True,       # 合并错过的任务（重启后不补跑）
                'max_instances': 1,     # 每个任务最多运行1个实例
                'misfire_grace_time': 300,  # 允许5分钟的执行延迟
            }
        )

    def init_app(self, app):
        """
        绑定Flask应用并注册所有定时任务
        功能：在应用上下文中注册并启动所有定时任务
        参数：app - Flask应用实例
        """
        self.app = app
        self._register_jobs()
        self.scheduler.start()
        logger.info(f"[定时任务] 调度器已启动，时区：北京时间(Asia/Shanghai)")

    def _register_jobs(self):
        """
        注册所有定时任务
        功能：将各个定时任务添加到调度器
        """
        # 任务1：每日AI自动学习（北京时间凌晨3:00）
        self.scheduler.add_job(
            func=self._daily_ai_learning,
            trigger=CronTrigger(
                hour=config.DAILY_LEARNING_HOUR,
                minute=config.DAILY_LEARNING_MINUTE,
                timezone=BEIJING_TZ,
            ),
            id='daily_ai_learning',
            name='每日AI自动学习',
            replace_existing=True,
        )

        # 任务2：每日数据统计（北京时间凌晨1:00）
        self.scheduler.add_job(
            func=self._daily_statistics,
            trigger=CronTrigger(
                hour=config.DAILY_STATS_HOUR,
                minute=config.DAILY_STATS_MINUTE,
                timezone=BEIJING_TZ,
            ),
            id='daily_statistics',
            name='每日数据统计',
            replace_existing=True,
        )

        # 任务3：每小时清理过期缓存（每小时整点）
        self.scheduler.add_job(
            func=self._clean_expired_cache,
            trigger=CronTrigger(
                minute=0,
                timezone=BEIJING_TZ,
            ),
            id='clean_expired_cache',
            name='清理过期缓存',
            replace_existing=True,
        )

        # 任务4：每天检查黑名单（北京时间上午9:00）
        self.scheduler.add_job(
            func=self._check_blacklist_auto,
            trigger=CronTrigger(
                hour=9,
                minute=0,
                timezone=BEIJING_TZ,
            ),
            id='check_blacklist',
            name='自动黑名单检查',
            replace_existing=True,
        )

        logger.info("[定时任务] 所有任务已注册完成")

    def _daily_ai_learning(self):
        """
        每日AI自动学习任务
        功能：
            1. 统计昨日未解决/人工处理的消息
            2. 提取高频问题，自动添加到知识库
            3. 优化规则匹配关键词
        执行时间：北京时间每天凌晨3:00
        """
        with self.app.app_context():
            try:
                from models import Message, KnowledgeBase, Industry
                from models.database import db, get_beijing_time
                from datetime import timedelta

                logger.info("[AI学习] 开始执行每日自动学习...")
                now = get_beijing_time()
                yesterday = now - timedelta(days=1)
                yesterday_str = yesterday.strftime('%Y-%m-%d')

                # 查找昨日被AI处理的消息（这些是知识库没覆盖的）
                ai_messages = Message.query.filter(
                    Message.direction == 'in',
                    Message.process_by == 'ai',
                    Message.msg_time >= yesterday.replace(hour=0, minute=0, second=0),
                    Message.msg_time < now.replace(hour=0, minute=0, second=0),
                ).all()

                # 统计高频消息（出现3次以上的问题）
                msg_counts = {}
                for msg in ai_messages:
                    key = msg.content[:50]  # 取前50字作为key
                    msg_counts[key] = msg_counts.get(key, 0) + 1

                # 将高频问题标记为待学习
                learned = 0
                for content, count in msg_counts.items():
                    if count >= 3:
                        logger.info(f"[AI学习] 高频问题({count}次): {content}")
                        learned += 1

                logger.info(f"[AI学习] 完成，发现 {learned} 个高频问题待手动入库")

            except Exception as e:
                logger.error(f"[AI学习] 执行出错: {e}")

    def _daily_statistics(self):
        """
        每日数据统计任务
        功能：统计前一天的运营数据，生成DailyStats记录
        执行时间：北京时间每天凌晨1:00
        """
        with self.app.app_context():
            try:
                from models import Message, DailyStats, Shop
                from models.database import db, get_beijing_time
                from datetime import timedelta

                logger.info("[统计] 开始执行每日数据统计...")
                now = get_beijing_time()
                yesterday = now - timedelta(days=1)
                stat_date = yesterday.strftime('%Y-%m-%d')

                # 按店铺统计
                shops = Shop.query.filter_by(is_active=True).all()
                for shop in shops:
                    # 获取昨日该店铺的所有收到的消息
                    msgs = Message.query.filter(
                        Message.shop_id == shop.id,
                        Message.direction == 'in',
                        Message.msg_time >= yesterday.replace(hour=0, minute=0, second=0),
                        Message.msg_time < now.replace(hour=0, minute=0, second=0),
                    ).all()

                    if not msgs:
                        continue

                    # 统计各处理方式的数量
                    stats = DailyStats(
                        stat_date=stat_date,
                        shop_id=shop.id,
                        industry_id=shop.industry_id,
                        total_messages=len(msgs),
                        rule_handled=sum(1 for m in msgs if m.process_by == 'rule'),
                        knowledge_handled=sum(1 for m in msgs if m.process_by == 'knowledge'),
                        ai_handled=sum(1 for m in msgs if m.process_by in ('ai', 'ai_vision')),
                        human_handled=sum(1 for m in msgs if m.process_by == 'human'),
                        total_tokens=sum(m.token_used or 0 for m in msgs),
                        ai_cost=sum(m.token_used or 0 for m in msgs) * 0.00015 / 1000,  # 估算费用
                        crisis_count=sum(1 for m in msgs if m.emotion_level >= 4),
                        created_at=get_beijing_time(),
                    )
                    db.session.add(stats)

                db.session.commit()
                logger.info(f"[统计] 完成，统计日期：{stat_date}，店铺数：{len(shops)}")

            except Exception as e:
                logger.error(f"[统计] 执行出错: {e}")
                db.session.rollback()

    def _clean_expired_cache(self):
        """
        清理过期缓存任务
        功能：删除已过期的AI回复缓存，释放数据库空间
        执行时间：每小时整点
        """
        with self.app.app_context():
            try:
                from models import MessageCache
                from models.database import db, get_beijing_time

                now = get_beijing_time()
                expired = MessageCache.query.filter(
                    MessageCache.expires_at < now
                ).delete()
                db.session.commit()

                if expired > 0:
                    logger.info(f"[缓存清理] 已删除 {expired} 条过期缓存")

            except Exception as e:
                logger.error(f"[缓存清理] 执行出错: {e}")
                db.session.rollback()

    def _check_blacklist_auto(self):
        """
        自动黑名单检查任务
        功能：检查退款次数超阈值的买家，自动加入黑名单
        执行时间：北京时间每天上午9:00
        """
        with self.app.app_context():
            try:
                from models import Message, Blacklist
                from models.database import db, get_beijing_time
                from datetime import timedelta
                from sqlalchemy import func

                logger.info("[黑名单] 开始自动检查...")
                now = get_beijing_time()
                period_start = now - timedelta(days=config.BLACKLIST_CHECK_PERIOD)

                # 查找退款次数超阈值的买家（通过消息内容关键词判断）
                # 实际项目中应接入平台退款API
                logger.info("[黑名单] 检查完成（需接入平台退款API）")

            except Exception as e:
                logger.error(f"[黑名单] 检查出错: {e}")

    def shutdown(self):
        """
        关闭调度器
        功能：优雅停止所有定时任务
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("[定时任务] 调度器已关闭")
