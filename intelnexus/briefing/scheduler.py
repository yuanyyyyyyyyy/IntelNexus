"""
AI简报定时调度器
===============
管理定时任务，触发简报生成和推送
"""

from typing import Dict, List, Optional
from datetime import datetime
import threading

from intelnexus.briefing.config import get_all_categories, BRIEFING_CONFIG
from intelnexus.briefing.collector import AIBriefingCollector
from intelnexus.briefing.analyzer import AIBriefingAnalyzer
from intelnexus.briefing.notifier import AIBriefingNotifier
from intelnexus.briefing.templates import render_markdown_briefing, render_email_html, markdown_to_html_sections
from intelnexus.config.subscriptions import get_active_subscribers, update_last_sent
from intelnexus.core.logger import get_logger
logger = get_logger(__name__)


class AIBriefingScheduler:
    """AI简报定时调度器"""
    
    def __init__(
        self,
        email_config: Dict = None,
        wecom_webhook: str = None,
        dingtalk_webhook: str = None,
        llm=None
    ):
        """
        初始化调度器
        
        Args:
            email_config: SMTP邮件配置
            wecom_webhook: 企业微信Webhook URL
            dingtalk_webhook: 钉钉Webhook URL
            llm: LLM模型实例
        """
        self.collector = AIBriefingCollector()
        self.analyzer = AIBriefingAnalyzer(llm=llm)
        self.notifier = AIBriefingNotifier(
            email_config=email_config,
            wecom_webhook=wecom_webhook,
            dingtalk_webhook=dingtalk_webhook
        )
        
        self.scheduler = None
        self._running = False
        self._executing = set()
        self._executing_lock = threading.Lock()
    
    def start(self):
        """启动调度器"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            
            self.scheduler = BackgroundScheduler()
            self._load_all_schedules()
            self.scheduler.start()
            self._running = True
            logger.info("Scheduler started")
        except ImportError:
            logger.warning("APScheduler not installed. Running in manual mode only.")
            self._running = True
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
        self._running = False
        logger.info("Scheduler stopped")
    
    def _load_all_schedules(self):
        """加载所有订阅者的定时任务"""
        if not self.scheduler:
            return
        
        subscribers = get_active_subscribers()
        
        for subscriber in subscribers:
            self._add_subscriber_job(subscriber)
    
    def _add_subscriber_job(self, subscriber: Dict):
        """为单个订阅者添加定时任务"""
        if not self.scheduler:
            return
        
        schedule = subscriber.get("schedule", {})
        time_str = schedule.get("time", "08:00")
        days = schedule.get("days", ["mon", "tue", "wed", "thu", "fri"])
        
        # 解析时间
        try:
            hour, minute = map(int, time_str.split(":"))
        except Exception:
            hour, minute = 8, 0
        
        # 映射星期
        day_map = {
            "mon": "mon", "tue": "tue", "wed": "wed",
            "thu": "thu", "fri": "fri", "sat": "sat", "sun": "sun"
        }
        
        job_id = f"briefing_{subscriber['id']}"
        
        # 移除已存在的任务
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            self.scheduler.remove_job(job_id)
        
        from apscheduler.triggers.cron import CronTrigger

        # 时区：使用订阅者配置的 timezone（修复：原实现存而不读，时区选择形同虚设）
        tz_name = schedule.get("timezone") or None
        try:
            trigger = CronTrigger(
                day_of_week=",".join([day_map.get(d, d) for d in days]),
                hour=hour,
                minute=minute,
                timezone=tz_name,
            )
        except Exception:
            logger.warning(f"Invalid timezone {tz_name!r}, falling back to system default")
            trigger = CronTrigger(
                day_of_week=",".join([day_map.get(d, d) for d in days]),
                hour=hour,
                minute=minute,
            )
        
        self.scheduler.add_job(
            func=self._execute_briefing,
            trigger=trigger,
            args=[subscriber["id"]],
            id=job_id,
            name=f"Briefing for {subscriber.get('name', subscriber['id'])}",
            replace_existing=True
        )
        
        logger.info(f"Added schedule for {subscriber.get('name', subscriber['id'])}: {time_str} on {days}")
    
    def _execute_briefing(self, subscriber_id: str):
        """执行简报生成和推送"""
        with self._executing_lock:
            if subscriber_id in self._executing:
                logger.warning(f"Briefing for {subscriber_id} already running, skipping")
                return
            self._executing.add(subscriber_id)
        try:
            try:
                from intelnexus.config.subscriptions import get_subscriber
                
                subscriber = get_subscriber(subscriber_id)
                if not subscriber:
                    logger.warning(f"Subscriber {subscriber_id} not found")
                    return
                
                logger.info(f"Executing briefing for {subscriber.get('name', subscriber_id)}")
                
                # 1. 获取订阅者关注的类别
                all_cats = get_all_categories()
                categories = subscriber.get("categories", list(all_cats.keys()))
                
                # 2. 采集数据
                collected_data = {}
                for category in categories:
                    if category in all_cats:
                        collected_data[category] = self.collector.collect_for_category(category)
                
                # 3. 生成简报
                organization_name = BRIEFING_CONFIG["organization"]["name"]
                briefing_md = self.analyzer.generate_briefing(collected_data, organization_name)
                
                # 4. 保存简报到历史
                try:
                    from intelnexus.config.briefing_history import get_briefing_history
                    get_briefing_history().save_briefing(
                        markdown_content=briefing_md,
                        organization_name=organization_name,
                        categories=list(collected_data.keys()),
                        subscribers_count=1
                    )
                except Exception as e:
                    logger.error(f"Error saving briefing to history: {e}")
                
                # 5. 生成HTML版本（用于邮件）
                briefing_html = None
                try:
                    from intelnexus.briefing.analyzer import format_briefing_date
                    org_cfg = dict(BRIEFING_CONFIG["organization"])
                    generated_date = format_briefing_date()
                    sections = markdown_to_html_sections(briefing_md)
                    briefing_html = render_email_html(
                        generated_date=generated_date,
                        organization=org_cfg,
                        **sections
                    )
                except Exception as e:
                    logger.error(f"Error generating HTML: {e}")
                
                # 6. 推送简报
                # 邮件配置热生效：每次执行前刷新（修复：调度器的 notifier 在应用启动时
                # 构造一次，用户之后在 UI 保存的 SMTP 配置需重启才能被定时任务用到）
                try:
                    from intelnexus.config.email_settings import get_active_email_config
                    fresh_email_cfg = get_active_email_config()
                    if fresh_email_cfg is not None:
                        self.notifier.email_config = fresh_email_cfg
                except Exception as e:
                    logger.warning(f"Refresh email config failed, keeping previous: {e}")
                results = self.notifier.notify(subscriber, briefing_md, briefing_html)
                # 落盘推送结果（分析面板的推送成功率数据源；失败不影响主流程）
                try:
                    from intelnexus.config.push_log import record_push_result
                    record_push_result(f"scheduled_{subscriber_id}", subscriber_id, results)
                except Exception:
                    pass
                
                # 7. 更新最后发送时间（仅在至少一个渠道成功时）
                if any(results.values()):
                    update_last_sent(subscriber_id)
                
                logger.info(f"Briefing executed for {subscriber.get('name', subscriber_id)}: {results}")
                
            except Exception as e:
                logger.error(f"Error executing briefing: {e}")
        finally:
            with self._executing_lock:
                self._executing.discard(subscriber_id)
    
    def trigger_now(self, subscriber_id: str):
        """手动触发某个订阅者的简报"""
        self._execute_briefing(subscriber_id)
    
    def trigger_all_now(self):
        """手动触发所有订阅者的简报"""
        subscribers = get_active_subscribers()
        for subscriber in subscribers:
            self._execute_briefing(subscriber["id"])
    
    def get_job_status(self) -> List[Dict]:
        """获取所有任务的状态"""
        if not self.scheduler:
            return []
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return jobs
    
    def update_subscriber_schedule(self, subscriber_id: str):
        """更新订阅者的定时任务"""
        if not self.scheduler:
            return
        
        from intelnexus.config.subscriptions import get_subscriber
        
        subscriber = get_subscriber(subscriber_id)
        if subscriber:
            self._add_subscriber_job(subscriber)
    
    def remove_subscriber_schedule(self, subscriber_id: str):
        """删除订阅者的定时任务"""
        if not self.scheduler:
            return
        
        job_id = f"briefing_{subscriber_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed schedule for {subscriber_id}")
        except Exception:
            pass
