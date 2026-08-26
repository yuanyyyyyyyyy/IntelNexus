"""
AI简报定时调度器
===============
管理定时任务，触发简报生成和推送
"""

from typing import Dict, List, Optional
from datetime import datetime
import threading

from intelnexus.briefing.config import BRIEFING_CONFIG
from intelnexus.briefing.collector import AIBriefingCollector
from intelnexus.briefing.analyzer import AIBriefingAnalyzer
from intelnexus.briefing.notifier import AIBriefingNotifier
from intelnexus.briefing.pipeline import run_briefing_pipeline
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
        # 模型解析：启动时确定（见 start()），未显式传入时先置 None；
        # 解析结果与降级原因记录在 self.llm_status，供状态横幅展示，
        # 避免旧实现静默走无 LLM 降级文案而管理员不可感知。
        self.analyzer = AIBriefingAnalyzer(llm=llm)
        self._explicit_llm = llm
        self.llm_status = {"ok": bool(llm), "model": "", "reason": ""}
        self.notifier = AIBriefingNotifier(
            email_config=email_config,
            wecom_webhook=wecom_webhook,
            dingtalk_webhook=dingtalk_webhook
        )
        
        self.scheduler = None
        self._running = False
        self._executing = set()
        self._executing_lock = threading.Lock()

    def _resolve_llm(self) -> dict:
        """解析定时链路可用的 LLM；成功则注入 analyzer 并返回状态。

        结果同步到 scheduler_registry（供 UI 状态横幅读取）。解析失败
        时状态必须可见——不允许静默以降级模板文案推送给订阅者。
        """
        from intelnexus.briefing.scheduler_model import resolve_scheduler_llm, make_status
        from intelnexus.briefing import scheduler_registry

        llm, name, reason = resolve_scheduler_llm()
        if llm is not None:
            self.analyzer._llm = llm
            logger.info(f"Scheduler LLM resolved: {name}")
            scheduler_registry.set_model_status(name, degraded=False)
        else:
            logger.warning(f"Scheduler LLM unavailable: {reason}")
            scheduler_registry.set_model_status(None, degraded=True, reason=reason)
        return make_status(llm is not None, name, reason)


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

        # 模型在启动时确定性解析一次；失败不阻塞调度器启动
        # （Ollama 可能稍后才就绪，执行前会重试），但状态必须可见。
        if not self._explicit_llm and not self.analyzer._llm:
            try:
                self.llm_status = self._resolve_llm()
            except Exception as e:
                self.llm_status = {"ok": False, "model": "", "reason": f"模型解析异常: {e}"}
    
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
            replace_existing=True,
            # 错过触发点（关机/睡眠/进程重启）后的补推窗口：默认≈0 会静默丢期。
            # 宽限 1 小时 + 合并错过的多次触发为一次，保证「每天一期」的承诺。
            misfire_grace_time=3600,
            coalesce=True,
        )
        
        logger.info(f"Added schedule for {subscriber.get('name', subscriber['id'])}: {time_str} on {days}")
    
    def _execute_briefing(self, subscriber_id: str):
        """执行简报生成和推送（复用统一 pipeline，与手动生成同链路）"""
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

                # LLM 保障：启动时解析失败（如 Ollama 未就绪）则执行前重试一次，
                # 成功即自动从降级模式恢复；仍失败保持降级并已上报注册表。
                if not self._explicit_llm and not self.analyzer._llm:
                    try:
                        self.llm_status = self._resolve_llm()
                    except Exception as e:
                        logger.warning(f"Scheduler LLM retry failed: {e}")

                # 统一链路：采集 → 生成 → 保存(含HTML/条目数据) → 推送。
                # 模型实例由调度器解析注入；推送关闭，订阅者单独推送（见下）。
                result = run_briefing_pipeline(
                    model=None,
                    categories=subscriber.get("categories") or None,
                    push_enabled=False,
                    llm_instance=self.analyzer._llm,
                    collector=self.collector,
                )
                briefing_md = result["md"]
                briefing_html = result.get("html")
                filename = None

                # 定时简报在历史索引中标注来源与真实触达人数
                try:
                    from intelnexus.config.briefing_history import get_briefing_history
                    history_mgr = get_briefing_history()
                    entries = history_mgr.get_briefings(limit=1)
                    if entries and entries[0].get("created_at", "")[:16] == datetime.now().isoformat()[:16]:
                        filename = entries[0]["filename"]
                        history_mgr.update_entry(filename, {
                            "subscribers_count": 1,
                            "source": "scheduled",
                            "subscriber_id": subscriber_id,
                        })
                except Exception as e:
                    logger.warning(f"Annotate scheduled briefing entry failed: {e}")

                # 推送该订阅者（沿用 notifier 的兴趣过滤 + 参与度重排 + 渠道分发）
                self._refresh_email_config()
                results = self.notifier.notify(subscriber, briefing_md, briefing_html)
                # 落盘推送结果（分析面板的推送成功率数据源；失败不影响主流程）；
                # 同时失效运行指标缓存，保证推送计数立即可见（跨会话最多 15s TTL 自愈）
                try:
                    from intelnexus.config.push_log import record_push_result
                    record_push_result(filename or f"scheduled_{subscriber_id}", subscriber_id, results)
                    from intelnexus.ui.status_metrics import invalidate_status_metrics
                    invalidate_status_metrics()
                except Exception:
                    pass

                # 更新最后发送时间（仅在至少一个渠道成功时）
                if any(results.values()):
                    update_last_sent(subscriber_id)

                logger.info(f"Briefing executed for {subscriber.get('name', subscriber_id)}: {results}")

            except Exception as e:
                logger.error(f"Error executing briefing: {e}")
        finally:
            with self._executing_lock:
                self._executing.discard(subscriber_id)

    def _refresh_email_config(self):
        """邮件配置热生效：每次推送前刷新（用户 UI 保存的 SMTP 立即可用）"""
        try:
            from intelnexus.config.email_settings import get_active_email_config
            fresh_email_cfg = get_active_email_config()
            if fresh_email_cfg is not None:
                self.notifier.email_config = fresh_email_cfg
        except Exception as e:
            logger.warning(f"Refresh email config failed, keeping previous: {e}")
    
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
