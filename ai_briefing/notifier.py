"""
AI简报推送通知器
===============
将生成的简报推送到订阅者的指定渠道（邮件、企业微信、钉钉）
"""

import smtplib
import hashlib
import hmac
import base64
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
import requests


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
        
        # 邮件推送
        if channels.get("email", {}).get("enabled", False):
            email = channels["email"].get("address", subscriber.get("email", ""))
            if email:
                results["email"] = self.send_email(
                    email=email,
                    subject=f"AI领域每日情报简报 - {subscriber.get('name', '')}",
                    content=briefing_content,
                    html_content=briefing_html
                )
        
        # 企业微信推送
        if channels.get("wecom", {}).get("enabled", False):
            webhook = channels["wecom"].get("webhook", "")
            if webhook:
                results["wecom"] = self.send_wecom(webhook, briefing_content)
        
        # 钉钉推送
        if channels.get("dingtalk", {}).get("enabled", False):
            webhook = channels["dingtalk"].get("webhook", "")
            secret = channels["dingtalk"].get("secret", "")
            if webhook:
                results["dingtalk"] = self.send_dingtalk(webhook, briefing_content, secret=secret)
        
        return results
    
    def send_email(self, email: str, subject: str, content: str, html_content: str = None) -> bool:
        """
        通过邮件发送简报
        
        Args:
            email: 收件人邮箱
            subject: 邮件主题
            content: 纯文本内容
            html_content: HTML内容（可选）
        
        Returns:
            bool: 是否发送成功
        """
        if not self.email_config:
            print("Email config not set")
            return False
        
        try:
            smtp_server = self.email_config.get("smtp_server", "")
            smtp_port = self.email_config.get("smtp_port", 587)
            use_tls = self.email_config.get("use_tls", True)
            username = self.email_config.get("username", "")
            password = self.email_config.get("password", "")
            from_name = self.email_config.get("from_name", "AI简报系统")
            
            if not smtp_server or not username or not password:
                print("Email SMTP config incomplete")
                return False
            
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{from_name} <{username}>"
            msg["To"] = email
            msg["Subject"] = subject
            
            # 添加纯文本版本
            text_part = MIMEText(content, "plain", "utf-8")
            msg.attach(text_part)
            
            # 添加HTML版本
            if html_content:
                html_part = MIMEText(html_content, "html", "utf-8")
                msg.attach(html_part)
            
            # 发送邮件
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(username, password)
                server.send_message(msg)
            
            print(f"Email sent to {email}")
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def send_wecom(self, webhook_url: str, content: str) -> bool:
        """
        通过企业微信Webhook发送简报
        
        Args:
            webhook_url: 企业微信Webhook URL
            content: Markdown格式的内容
        
        Returns:
            bool: 是否发送成功
        """
        try:
            # 企业微信消息长度限制为4096字节
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
                    print("Wecom message sent successfully")
                    return True
                else:
                    print(f"Wecom error: {result}")
                    return False
            else:
                print(f"Wecom HTTP error: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error sending wecom message: {e}")
            return False
    
    def send_dingtalk(self, webhook_url: str, content: str, title: str = "AI简报", secret: str = None) -> bool:
        """
        通过钉钉Webhook发送简报
        
        Args:
            webhook_url: 钉钉Webhook URL
            content: Markdown格式的内容
            title: 消息标题
            secret: 签名密钥（可选）
        
        Returns:
            bool: 是否发送成功
        """
        try:
            # 钉钉消息长度限制为5000字节
            truncated_content = self._truncate_for_platform(content, "dingtalk", 4500)
            
            # 如果有签名密钥，计算签名
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
                    print("Dingtalk message sent successfully")
                    return True
                else:
                    print(f"Dingtalk error: {result}")
                    return False
            else:
                print(f"Dingtalk HTTP error: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error sending dingtalk message: {e}")
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
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(username, password)
            
            return True
        except Exception as e:
            print(f"Email connection test failed: {e}")
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
            print(f"Wecom connection test failed: {e}")
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
            print(f"Dingtalk connection test failed: {e}")
            return False
