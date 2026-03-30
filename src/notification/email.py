"""Email SMTP 通知渠道。"""

from __future__ import annotations

import asyncio
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import ConfigManager
from src.log import get_logger
from src.notification.base import BaseNotifier, NotificationMessage, SendResult

logger = get_logger(__name__)

# Email 正文最大长度（HTML）
_MAX_LENGTH = 100000
_TIMEOUT = 30


class EmailNotifier(BaseNotifier):
    """Email SMTP 通知器。

    通过 SMTP 发送 HTML 格式邮件，使用 asyncio.to_thread 包装同步 smtplib。
    """

    @property
    def channel_name(self) -> str:
        return "邮件"

    @property
    def max_message_length(self) -> int:
        return _MAX_LENGTH

    async def is_configured(self) -> bool:
        """检查是否配置了 SMTP 信息和收件人。"""
        config = ConfigManager.get_config()
        push = config.push
        return bool(
            push.email_smtp_host
            and push.email_sender
            and push.email_password.get_secret_value()
            and push.email_receivers
        )

    def format_message(self, title: str, content: str) -> str:
        """格式化为 HTML 邮件正文。"""
        # 将换行转为 <br>，简单的纯文本转 HTML
        html_content = content.replace("\n", "<br>\n")
        html = (
            f"<html><body>"
            f"<h2>{title}</h2>"
            f"<div>{html_content}</div>"
            f"</body></html>"
        )
        return self._truncate(html)

    def _send_sync(self, subject: str, html_body: str, receivers: list[str]) -> None:
        """同步发送邮件（在线程池中调用）。"""
        config = ConfigManager.get_config()
        push = config.push

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = push.email_sender
        msg["To"] = ", ".join(receivers)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        port = push.email_smtp_port
        host = push.email_smtp_host
        password = push.email_password.get_secret_value()

        # 根据端口选择 SSL 或 STARTTLS
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=_TIMEOUT) as server:
                server.login(push.email_sender, password)
                server.sendmail(push.email_sender, receivers, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=_TIMEOUT) as server:
                server.starttls()
                server.login(push.email_sender, password)
                server.sendmail(push.email_sender, receivers, msg.as_string())

    async def send(self, message: NotificationMessage) -> SendResult:
        """通过 SMTP 发送邮件。"""
        config = ConfigManager.get_config()
        push = config.push

        if not await self.is_configured():
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="邮件 SMTP 配置不完整",
                timestamp=datetime.now(tz=UTC),
            )

        receivers = [r.strip() for r in push.email_receivers.split(",") if r.strip()]
        if not receivers:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="未配置收件人",
                timestamp=datetime.now(tz=UTC),
            )

        html_body = self.format_message(message.title, message.content)

        try:
            await asyncio.to_thread(self._send_sync, message.title, html_body, receivers)
            logger.info("[%s] 邮件发送成功: %s -> %s", self.channel_name, message.title, receivers)
            return SendResult(
                success=True,
                channel=self.channel_name,
                timestamp=datetime.now(tz=UTC),
            )
        except Exception as exc:
            error_msg = f"邮件发送失败: {exc}"
            logger.error("[%s] %s", self.channel_name, error_msg)
            return SendResult(
                success=False,
                channel=self.channel_name,
                error=error_msg,
                timestamp=datetime.now(tz=UTC),
            )
