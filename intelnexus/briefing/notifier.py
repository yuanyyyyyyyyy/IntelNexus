"""
AI简报推送通知器
===============
将生成的简报推送到订阅者的指定渠道（邮件、企业微信、钉钉）
"""

import smtplib
import ssl
import hashlib
import hmac
import base64
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
import requests
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


# 关注点 → 简报板块映射（用于按订阅者 interests 过滤推送内容）
# 细化映射粒度：每个interest映射到更具体的子板块
_TOPIC_TO_SECTION = {
    "ai_gov_usage": "AI 领域动态",
    "ai_china_narrative": "AI 领域动态",
    "ai_legislation": "政策法规动态",  # 修正：映射到政策法规动态
    "ai_data_leak": "网络安全动态",
    "cyber_vuln": "网络安全动态",
    "cyber_attack": "网络安全动态",
}
# 漏洞预警板块随网络安全动态一起被 interests 控制
_SECTION_TO_TOPICS = {}
for _tid, _sec in _TOPIC_TO_SECTION.items():
    _SECTION_TO_TOPICS.setdefault(_sec, []).append(_tid)
_SECTION_TO_TOPICS["近日新增安全漏洞预警"] = ["cyber_vuln", "cyber_attack"]
# 政策法规动态现在也受interests控制
_SECTION_TO_TOPICS["政策法规动态"] = ["ai_legislation"]


def filter_briefing_by_interests(briefing_content: str, interests: list) -> str:
    """按订阅者 interests 裁剪简报 Markdown。

    interests 为空（或缺失）表示接收全部板块。否则只保留与 interests
    命中板块相关的内容，未命中的板块折叠为「已省略」提示，通用板块
    （TOP3 / 增量速览 / 趋势研判 / 重要链接）始终保留。
    """
    if not interests:
        return briefing_content

    # 解析为 {区块标题: 内容}（按 ## 一级标题切分）
    sections: Dict[str, str] = {}
    order: list = []
    current = None
    buf = []
    for line in briefing_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = stripped[3:].strip()
            order.append(current)
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()

    # interests 命中的板块集合
    wanted_sections = set()
    for tid in interests:
        sec = _TOPIC_TO_SECTION.get(tid)
        if sec:
            wanted_sections.add(sec)
        if tid in ("cyber_vuln", "cyber_attack"):
            wanted_sections.add("近日新增安全漏洞预警")

    out = []
    for sec in order:
        if sec in wanted_sections or sec not in _SECTION_TO_TOPICS:
            # 通用板块或命中板块：原样保留
            out.append(f"## {sec}")
            out.append(sections.get(sec, ""))
        else:
            out.append(f"## {sec}")
            out.append("> 根据你的订阅偏好（关注点过滤），本板块已省略。")
        out.append("")
    return "\n".join(out).strip()


class AIBriefingNotifier:
    """AI简报推送通知器"""
    
    def __init__(self, email_config: Dict = None, wecom_webhook: str = None, dingtalk_webhook: str = None):
        """
        初始化通知器
        
        Args:
            email_config: SMTP邮件配置
            wecom_webhook: 企业微信Webhook URL
            dingtalk_webhook: 钉钉Webhook URL
        """
        self.email_config = email_config or {}
        self.wecom_webhook = wecom_webhook
        self.dingtalk_webhook = dingtalk_webhook
    
    def notify(self, subscriber: Dict, briefing_content: str, briefing_html: str = None) -> Dict[str, bool]:
        """
        推送简报到订阅者的所有启用渠道
        
        Args:
            subscriber: 订阅者信息
            briefing_content: Markdown格式的简报内容
            briefing_html: HTML格式的简报内容（可选，用于邮件）
        
        Returns:
            Dict[str, bool]: 各渠道的发送结果
        """
        results = {}
        channels = subscriber.get("channels", {})

        # 按订阅者关注点（interests / categories）裁剪简报，实现个性化降噪
        interests = subscriber.get("interests") or subscriber.get("categories", [])
        send_content = briefing_content
        send_html = briefing_html
        if interests:
            send_content = filter_briefing_by_interests(briefing_content, interests)
            # 基于裁剪后内容重新生成 HTML，避免 Markdown 与 HTML 不一致
            try:
                from intelnexus.briefing.templates import render_email_html, markdown_to_html_sections
                from datetime import datetime
                sections = markdown_to_html_sections(send_content)
                send_html = render_email_html(
                    generated_date=datetime.now().strftime("%Y年%m月%d日"),
                    organization={},
                    **sections
                )
            except Exception as e:
                logger.warning(f"Could not regenerate HTML after interest filtering: {e}")
                send_html = None
        
        # 基于参与度进一步个性化（第二阶段新增）
        subscriber_id = subscriber.get("id", "")
        if subscriber_id:
            try:
                from intelnexus.briefing.personalization import filter_briefing_by_engagement
                send_content = filter_briefing_by_engagement(send_content, subscriber_id)
            except Exception as e:
                logger.warning(f"基于参与度过滤失败: {e}")
        
        # 邮件推送
        if channels.get("email", {}).get("enabled", False):
            email = channels["email"].get("address", subscriber.get("email", ""))
            if email:
                results["email"] = self.send_email(
                    email=email,
                    subject=f"AI 与网络安全每日情报简报 - {subscriber.get('name', '')}",
                    content=send_content,
                    html_content=send_html
                )
        
        # 企业微信推送
        if channels.get("wecom", {}).get("enabled", False):
            webhook = channels["wecom"].get("webhook", "")
            if webhook:
                results["wecom"] = self.send_wecom(webhook, send_content)
        
        # 钉钉推送
        if channels.get("dingtalk", {}).get("enabled", False):
            webhook = channels["dingtalk"].get("webhook", "")
            secret = channels["dingtalk"].get("secret", "")
            if webhook:
                results["dingtalk"] = self.send_dingtalk(webhook, send_content, secret=secret)
        
        return results
    
    def send_email(self, email: str, subject: str, content: str, html_content: str = None) -> bool:
        """
        通过邮件发送简报（带重试）
        
        Args:
            email: 收件人邮箱
            subject: 邮件主题
            content: 纯文本内容
            html_content: HTML内容（可选）
        
        Returns:
            bool: 是否发送成功
        """
        if not self.email_config:
            logger.warning("Email config not set")
            return False
        return self._retry(self._send_email_once, email, subject, content, html_content)
    
    def _send_email_once(self, email: str, subject: str, content: str, html_content: str = None) -> bool:
        """单次邮件发送（供 _retry 调用）"""
        smtp_server = self.email_config.get("smtp_server", "")
        smtp_port = self.email_config.get("smtp_port", 587)
        use_tls = self.email_config.get("use_tls", True)
        username = self.email_config.get("username", "")
        password = self.email_config.get("password", "")
        from_name = self.email_config.get("from_name", "AI简报系统")
        
        if not smtp_server or not username or not password:
            logger.warning("Email SMTP config incomplete")
            return False
        
        if not use_tls:
            logger.warning(
                "SMTP use_tls=False：凭证与邮件内容将以明文传输，存在被窃听/中间人攻击风险，"
                "建议设置 SMTP_USE_TLS=true（或 UI 中勾选'使用TLS'）"
            )
        
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{from_name} <{username}>"
        msg["To"] = email
        msg["Subject"] = subject
        
        text_part = MIMEText(content, "plain", "utf-8")
        msg.attach(text_part)
        
        if html_content:
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                # 校验服务端证书，抵御中间人攻击
                server.starttls(context=ssl.create_default_context())
            server.login(username, password)
            server.send_message(msg)
        
        logger.info(f"Email sent to {email}")
        return True
    
    def send_wecom(self, webhook_url: str, content: str) -> bool:
        """
        通过企业微信Webhook发送简报（带重试）
        
        Args:
            webhook_url: 企业微信Webhook URL
            content: Markdown格式的内容
        
        Returns:
            bool: 是否发送成功
        """
        return self._retry(self._send_wecom_once, webhook_url, content)
    
    def _send_wecom_once(self, webhook_url: str, content: str) -> bool:
        """单次企业微信发送（供 _retry 调用）"""
        truncated_content = self._truncate_for_platform(content, "wecom", 4000)
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": truncated_content
            }
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("errcode") == 0:
                logger.info("Wecom message sent successfully")
                return True
            else:
                logger.error(f"Wecom error: {result}")
                return False
        else:
            logger.error(f"Wecom HTTP error: {response.status_code}")
            return False
    
    def send_dingtalk(self, webhook_url: str, content: str, title: str = "AI简报", secret: str = None) -> bool:
        """
        通过钉钉Webhook发送简报（带重试）
        
        Args:
            webhook_url: 钉钉Webhook URL
            content: Markdown格式的内容
            title: 消息标题
            secret: 签名密钥（可选）
        
        Returns:
            bool: 是否发送成功
        """
        return self._retry(self._send_dingtalk_once, webhook_url, content, title, secret)
    
    def _send_dingtalk_once(self, webhook_url: str, content: str, title: str = "AI简报", secret: str = None) -> bool:
        """单次钉钉发送（供 _retry 调用）"""
        truncated_content = self._truncate_for_platform(content, "dingtalk", 4500)
        
        if secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": truncated_content
            }
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("errcode") == 0:
                logger.info("Dingtalk message sent successfully")
                return True
            else:
                logger.error(f"Dingtalk error: {result}")
                return False
        else:
            logger.error(f"Dingtalk HTTP error: {response.status_code}")
            return False
    
    def _retry(self, func, *args, max_retries=3, **kwargs):
        """带重试的执行包装器（仅重试瞬态错误）"""
        last_error = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (requests.ConnectionError, requests.Timeout, IOError, OSError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                    time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                return False
        logger.error(f"All {max_retries} retries failed: {last_error}")
        return False
    
    def _truncate_for_platform(self, content: str, platform: str, max_length: int) -> str:
        """
        根据平台限制截断内容
        
        Args:
            content: 原始内容
            platform: 平台名称
            max_length: 最大长度
        
        Returns:
            str: 截断后的内容
        """
        if len(content) <= max_length:
            return content
        
        truncated = content[:max_length - 50]
        
        # 找到最近的换行符截断
        last_newline = truncated.rfind("\n")
        if last_newline > max_length - 100:
            truncated = truncated[:last_newline]
        
        truncated += "\n\n...(内容已截断，完整内容请查看邮件)"
        return truncated
    
    def test_connection(self, channel: str = "all") -> Dict[str, bool]:
        """
        测试各渠道连接
        
        Args:
            channel: 要测试的渠道（all/email/wecom/dingtalk）
        
        Returns:
            Dict[str, bool]: 各渠道的测试结果
        """
        results = {}
        
        if channel in ["all", "email"]:
            results["email"] = self._test_email_connection()
        
        if channel in ["all", "wecom"]:
            results["wecom"] = self._test_wecom_connection()
        
        if channel in ["all", "dingtalk"]:
            results["dingtalk"] = self._test_dingtalk_connection()
        
        return results
    
    def _test_email_connection(self) -> bool:
        """测试邮件连接"""
        if not self.email_config:
            return False
        
        try:
            smtp_server = self.email_config.get("smtp_server", "")
            smtp_port = self.email_config.get("smtp_port", 587)
            use_tls = self.email_config.get("use_tls", True)
            username = self.email_config.get("username", "")
            password = self.email_config.get("password", "")
            
            if not smtp_server or not username or not password:
                return False
            
            if not use_tls:
                logger.warning(
                    "SMTP use_tls=False：凭证将以明文传输，存在安全风险，"
                    "建议设置 SMTP_USE_TLS=true（或 UI 中勾选'使用TLS'）"
                )
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                server.login(username, password)
            
            return True
        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return False
    
    def _test_wecom_connection(self) -> bool:
        """测试企业微信连接"""
        if not self.wecom_webhook:
            return False
        
        try:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": "AI简报系统连接测试"
                }
            }
            response = requests.post(self.wecom_webhook, json=payload, timeout=10)
            return response.status_code == 200 and response.json().get("errcode") == 0
        except Exception as e:
            logger.error(f"Wecom connection test failed: {e}")
            return False
    
    def _test_dingtalk_connection(self) -> bool:
        """测试钉钉连接"""
        if not self.dingtalk_webhook:
            return False
        
        try:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": "AI简报系统连接测试"
                }
            }
            response = requests.post(self.dingtalk_webhook, json=payload, timeout=10)
            return response.status_code == 200 and response.json().get("errcode") == 0
        except Exception as e:
            logger.error(f"Dingtalk connection test failed: {e}")
            return False
