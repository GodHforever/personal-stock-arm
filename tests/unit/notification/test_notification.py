"""推送通知模块单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import ConfigManager
from src.config.models import AppConfig, PushConfig
from src.notification.base import (
    BaseNotifier,
    NotificationLevel,
    NotificationMessage,
    SendResult,
)
from src.notification.email import EmailNotifier
from src.notification.feishu import FeishuNotifier
from src.notification.manager import (
    _CONSECUTIVE_FAILURE_THRESHOLD,
    NotificationManager,
)
from src.notification.webhook import WebhookNotifier
from src.notification.wechat import WeChatNotifier

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config() -> None:
    """每个测试前后重置 ConfigManager。"""
    ConfigManager.reset()
    yield  # type: ignore[misc]
    ConfigManager.reset()


@pytest.fixture()
def wechat_config() -> AppConfig:
    """配置了企业微信的配置。"""
    return ConfigManager.initialize(
        push=PushConfig(wechat_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"),
    )


@pytest.fixture()
def feishu_config() -> AppConfig:
    """配置了飞书的配置。"""
    return ConfigManager.initialize(
        push=PushConfig(feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test"),
    )


@pytest.fixture()
def email_config() -> AppConfig:
    """配置了邮件的配置。"""
    return ConfigManager.initialize(
        push=PushConfig(
            email_smtp_host="smtp.example.com",
            email_smtp_port=465,
            email_sender="sender@example.com",
            email_password="password123",
            email_receivers="user1@example.com,user2@example.com",
        ),
    )


@pytest.fixture()
def webhook_config() -> AppConfig:
    """配置了自定义 Webhook 的配置。"""
    return ConfigManager.initialize(
        push=PushConfig(custom_webhook_urls="https://hook1.example.com,https://hook2.example.com"),
    )


@pytest.fixture()
def sample_message() -> NotificationMessage:
    """示例通知消息。"""
    return NotificationMessage(
        title="测试通知",
        content="这是一条测试消息内容",
        level=NotificationLevel.INFO,
    )


@pytest.fixture()
def urgent_message() -> NotificationMessage:
    """紧急通知消息。"""
    return NotificationMessage(
        title="紧急警报",
        content="指数大幅下跌",
        level=NotificationLevel.URGENT,
    )


@pytest.fixture()
def catchup_message() -> NotificationMessage:
    """catch-up 模式消息。"""
    return NotificationMessage(
        title="补漏通知",
        content="补漏消息内容",
        is_catchup=True,
    )


def _ok_response() -> httpx.Response:
    """创建成功的 HTTP 响应。"""
    return httpx.Response(
        200,
        json={"errcode": 0, "errmsg": "ok"},
        request=httpx.Request("POST", "https://example.com"),
    )


def _error_response(status_code: int = 500) -> httpx.Response:
    """创建失败的 HTTP 响应。"""
    return httpx.Response(
        status_code,
        text="Internal Server Error",
        request=httpx.Request("POST", "https://example.com"),
    )


# ---------------------------------------------------------------------------
# NotificationMessage 模型测试
# ---------------------------------------------------------------------------


class TestNotificationMessage:
    """NotificationMessage 模型测试。"""

    def test_default_values(self) -> None:
        msg = NotificationMessage(title="标题", content="内容")
        assert msg.level == NotificationLevel.INFO
        assert msg.is_catchup is False

    def test_custom_level(self) -> None:
        msg = NotificationMessage(
            title="标题", content="内容", level=NotificationLevel.URGENT
        )
        assert msg.level == NotificationLevel.URGENT


class TestSendResult:
    """SendResult 模型测试。"""

    def test_success_result(self) -> None:
        now = datetime.now(tz=UTC)
        result = SendResult(success=True, channel="测试渠道", timestamp=now)
        assert result.success is True
        assert result.error is None

    def test_failure_result(self) -> None:
        now = datetime.now(tz=UTC)
        result = SendResult(
            success=False, channel="测试渠道", error="连接超时", timestamp=now
        )
        assert result.success is False
        assert result.error == "连接超时"


# ---------------------------------------------------------------------------
# BaseNotifier 抽象基类测试
# ---------------------------------------------------------------------------


class TestBaseNotifier:
    """BaseNotifier 抽象基类测试。"""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseNotifier()  # type: ignore[abstract]

    def test_truncate_short_text(self) -> None:
        """短文本不截断。"""

        class DummyNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "测试"

            @property
            def max_message_length(self) -> int:
                return 100

            async def send(self, message: NotificationMessage) -> SendResult:
                return SendResult(success=True, channel="测试", timestamp=datetime.now(tz=UTC))

            def format_message(self, title: str, content: str) -> str:
                return f"{title}: {content}"

            async def is_configured(self) -> bool:
                return True

        notifier = DummyNotifier()
        assert notifier._truncate("短文本") == "短文本"

    def test_truncate_long_text(self) -> None:
        """长文本被截断并添加省略号。"""

        class DummyNotifier(BaseNotifier):
            @property
            def channel_name(self) -> str:
                return "测试"

            @property
            def max_message_length(self) -> int:
                return 10

            async def send(self, message: NotificationMessage) -> SendResult:
                return SendResult(success=True, channel="测试", timestamp=datetime.now(tz=UTC))

            def format_message(self, title: str, content: str) -> str:
                return f"{title}: {content}"

            async def is_configured(self) -> bool:
                return True

        notifier = DummyNotifier()
        result = notifier._truncate("这是一段非常长的文本内容用于测试截断功能")
        assert len(result) == 10
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# WeChatNotifier 测试
# ---------------------------------------------------------------------------


class TestWeChatNotifier:
    """企业微信通知器测试。"""

    async def test_not_configured(self) -> None:
        ConfigManager.initialize()
        notifier = WeChatNotifier()
        assert await notifier.is_configured() is False

    async def test_is_configured(self, wechat_config: AppConfig) -> None:
        notifier = WeChatNotifier()
        assert await notifier.is_configured() is True

    async def test_channel_name(self) -> None:
        notifier = WeChatNotifier()
        assert notifier.channel_name == "企业微信"

    async def test_send_not_configured(self, sample_message: NotificationMessage) -> None:
        ConfigManager.initialize()
        notifier = WeChatNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False
        assert "未配置" in (result.error or "")

    @patch("src.notification.wechat.httpx.AsyncClient")
    async def test_send_success(
        self,
        mock_client_cls: MagicMock,
        wechat_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.return_value = _ok_response()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        notifier = WeChatNotifier()
        result = await notifier.send(sample_message)
        assert result.success is True
        assert result.channel == "企业微信"

    @patch("src.notification.wechat.httpx.AsyncClient")
    async def test_send_failure(
        self,
        mock_client_cls: MagicMock,
        wechat_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("连接失败")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        notifier = WeChatNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False
        assert "连接失败" in (result.error or "")

    def test_format_message(self) -> None:
        notifier = WeChatNotifier()
        result = notifier.format_message("标题", "内容")
        assert "## 标题" in result
        assert "内容" in result


# ---------------------------------------------------------------------------
# FeishuNotifier 测试
# ---------------------------------------------------------------------------


class TestFeishuNotifier:
    """飞书通知器测试。"""

    async def test_not_configured(self) -> None:
        ConfigManager.initialize()
        notifier = FeishuNotifier()
        assert await notifier.is_configured() is False

    async def test_is_configured(self, feishu_config: AppConfig) -> None:
        notifier = FeishuNotifier()
        assert await notifier.is_configured() is True

    async def test_channel_name(self) -> None:
        notifier = FeishuNotifier()
        assert notifier.channel_name == "飞书"

    @patch("src.notification.feishu.httpx.AsyncClient")
    async def test_send_success(
        self,
        mock_client_cls: MagicMock,
        feishu_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.return_value = _ok_response()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        notifier = FeishuNotifier()
        result = await notifier.send(sample_message)
        assert result.success is True
        assert result.channel == "飞书"

    async def test_send_not_configured(self, sample_message: NotificationMessage) -> None:
        ConfigManager.initialize()
        notifier = FeishuNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False

    def test_format_message(self) -> None:
        notifier = FeishuNotifier()
        result = notifier.format_message("标题", "内容")
        assert "标题" in result
        assert "内容" in result


# ---------------------------------------------------------------------------
# EmailNotifier 测试
# ---------------------------------------------------------------------------


class TestEmailNotifier:
    """邮件通知器测试。"""

    async def test_not_configured(self) -> None:
        ConfigManager.initialize()
        notifier = EmailNotifier()
        assert await notifier.is_configured() is False

    async def test_is_configured(self, email_config: AppConfig) -> None:
        notifier = EmailNotifier()
        assert await notifier.is_configured() is True

    async def test_channel_name(self) -> None:
        notifier = EmailNotifier()
        assert notifier.channel_name == "邮件"

    @patch("src.notification.email.asyncio.to_thread", new_callable=AsyncMock)
    async def test_send_success(
        self,
        mock_to_thread: AsyncMock,
        email_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_to_thread.return_value = None
        notifier = EmailNotifier()
        result = await notifier.send(sample_message)
        assert result.success is True
        assert result.channel == "邮件"
        mock_to_thread.assert_called_once()

    @patch("src.notification.email.asyncio.to_thread", new_callable=AsyncMock)
    async def test_send_failure(
        self,
        mock_to_thread: AsyncMock,
        email_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_to_thread.side_effect = Exception("SMTP 连接失败")
        notifier = EmailNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False
        assert "SMTP 连接失败" in (result.error or "")

    async def test_send_not_configured(self, sample_message: NotificationMessage) -> None:
        ConfigManager.initialize()
        notifier = EmailNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False
        assert "配置不完整" in (result.error or "")

    def test_format_message_html(self) -> None:
        notifier = EmailNotifier()
        result = notifier.format_message("标题", "第一行\n第二行")
        assert "<h2>标题</h2>" in result
        assert "<br>" in result


# ---------------------------------------------------------------------------
# WebhookNotifier 测试
# ---------------------------------------------------------------------------


class TestWebhookNotifier:
    """自定义 Webhook 通知器测试。"""

    async def test_not_configured(self) -> None:
        ConfigManager.initialize()
        notifier = WebhookNotifier()
        assert await notifier.is_configured() is False

    async def test_is_configured(self, webhook_config: AppConfig) -> None:
        notifier = WebhookNotifier()
        assert await notifier.is_configured() is True

    async def test_channel_name(self) -> None:
        notifier = WebhookNotifier()
        assert notifier.channel_name == "自定义Webhook"

    @patch("src.notification.webhook.httpx.AsyncClient")
    async def test_send_success(
        self,
        mock_client_cls: MagicMock,
        webhook_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.return_value = _ok_response()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        notifier = WebhookNotifier()
        result = await notifier.send(sample_message)
        assert result.success is True
        # 应该对两个 URL 分别发送
        assert mock_client.post.call_count == 2

    @patch("src.notification.webhook.httpx.AsyncClient")
    async def test_send_partial_failure(
        self,
        mock_client_cls: MagicMock,
        webhook_config: AppConfig,
        sample_message: NotificationMessage,
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.side_effect = [_ok_response(), httpx.ConnectError("失败")]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        notifier = WebhookNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False

    async def test_send_not_configured(self, sample_message: NotificationMessage) -> None:
        ConfigManager.initialize()
        notifier = WebhookNotifier()
        result = await notifier.send(sample_message)
        assert result.success is False

    def test_format_message(self) -> None:
        notifier = WebhookNotifier()
        result = notifier.format_message("标题", "内容")
        assert "标题" in result
        assert "内容" in result


# ---------------------------------------------------------------------------
# NotificationManager 测试
# ---------------------------------------------------------------------------


class TestNotificationManager:
    """通知管理器测试。"""

    def test_register(self) -> None:
        ConfigManager.initialize()
        manager = NotificationManager()
        notifier = WeChatNotifier()
        manager.register(notifier)
        assert len(manager.notifiers) == 1
        assert manager.notifiers[0].channel_name == "企业微信"

    def test_should_send_normal(self) -> None:
        manager = NotificationManager()
        assert manager.should_send(is_catchup=False) is True

    def test_should_send_catchup(self) -> None:
        manager = NotificationManager()
        assert manager.should_send(is_catchup=True) is False

    def test_is_silent_period_during_silent(self) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        # 23:00 应该在免打扰时段
        night = datetime(2024, 1, 1, 23, 0, tzinfo=UTC)
        assert manager.is_silent_period(now=night) is True

    def test_is_silent_period_during_active(self) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        # 12:00 不在免打扰时段
        noon = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        assert manager.is_silent_period(now=noon) is False

    def test_is_silent_period_at_boundary_start(self) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        # 22:00 正好是免打扰开始
        boundary = datetime(2024, 1, 1, 22, 0, tzinfo=UTC)
        assert manager.is_silent_period(now=boundary) is True

    def test_is_silent_period_at_boundary_end(self) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        # 08:00 正好是免打扰结束
        boundary = datetime(2024, 1, 1, 8, 0, tzinfo=UTC)
        assert manager.is_silent_period(now=boundary) is False

    def test_is_silent_period_early_morning(self) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        # 03:00 凌晨在免打扰时段
        early = datetime(2024, 1, 1, 3, 0, tzinfo=UTC)
        assert manager.is_silent_period(now=early) is True

    async def test_send_all_catchup_skipped(
        self,
        catchup_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize()
        manager = NotificationManager()
        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "测试"
        manager.register(mock_notifier)

        results = await manager.send_all(catchup_message)
        assert results == []
        mock_notifier.send.assert_not_called()

    async def test_send_all_silent_period_skipped(
        self,
        sample_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="00:00", silent_end="23:59"),
        )
        manager = NotificationManager()
        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "测试"
        mock_notifier.is_configured = AsyncMock(return_value=True)
        manager.register(mock_notifier)

        results = await manager.send_all(sample_message)
        assert results == []

    async def test_send_all_urgent_bypasses_silent(
        self,
        urgent_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="00:00", silent_end="23:59"),
        )
        manager = NotificationManager()
        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "测试"
        mock_notifier.is_configured = AsyncMock(return_value=True)
        mock_notifier.send = AsyncMock(
            return_value=SendResult(success=True, channel="测试", timestamp=datetime.now(tz=UTC))
        )
        manager.register(mock_notifier)

        results = await manager.send_all(urgent_message)
        assert len(results) == 1
        assert results[0].success is True

    @patch("src.notification.manager._RETRY_DELAY", 0.01)
    async def test_send_all_with_retry(
        self,
        sample_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        now = datetime.now(tz=UTC)

        # 第一次失败，第二次成功
        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "测试渠道"
        mock_notifier.is_configured = AsyncMock(return_value=True)
        mock_notifier.send = AsyncMock(
            side_effect=[
                SendResult(success=False, channel="测试渠道", error="超时", timestamp=now),
                SendResult(success=True, channel="测试渠道", timestamp=now),
            ]
        )
        manager.register(mock_notifier)

        # 设置非免打扰时间
        with patch.object(manager, "is_silent_period", return_value=False):
            results = await manager.send_all(sample_message)

        assert len(results) == 1
        assert results[0].success is True
        assert mock_notifier.send.call_count == 2

    @patch("src.notification.manager._RETRY_DELAY", 0.01)
    async def test_consecutive_failure_warning(
        self,
        sample_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()
        now = datetime.now(tz=UTC)

        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "测试渠道"
        mock_notifier.is_configured = AsyncMock(return_value=True)
        # 始终失败
        mock_notifier.send = AsyncMock(
            return_value=SendResult(success=False, channel="测试渠道", error="持续失败", timestamp=now)
        )
        manager.register(mock_notifier)

        with patch.object(manager, "is_silent_period", return_value=False):
            for _ in range(_CONSECUTIVE_FAILURE_THRESHOLD):
                await manager.send_all(sample_message)

        assert manager._consecutive_failures["测试渠道"] >= _CONSECUTIVE_FAILURE_THRESHOLD

    async def test_event_push_daily_limit(
        self,
        sample_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize(
            push=PushConfig(
                silent_start="22:00",
                silent_end="08:00",
                event_push_daily_limit=2,
            ),
        )
        manager = NotificationManager()
        now = datetime.now(tz=UTC)

        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "测试渠道"
        mock_notifier.is_configured = AsyncMock(return_value=True)
        mock_notifier.send = AsyncMock(
            return_value=SendResult(success=True, channel="测试渠道", timestamp=now)
        )
        manager.register(mock_notifier)

        with patch.object(manager, "is_silent_period", return_value=False):
            # 前两次发送应成功
            results1 = await manager.send_all(sample_message, is_event=True)
            assert len(results1) == 1
            results2 = await manager.send_all(sample_message, is_event=True)
            assert len(results2) == 1
            # 第三次应被限额拦截
            results3 = await manager.send_all(sample_message, is_event=True)
            assert results3 == []

    async def test_unconfigured_channel_skipped(
        self,
        sample_message: NotificationMessage,
    ) -> None:
        ConfigManager.initialize(
            push=PushConfig(silent_start="22:00", silent_end="08:00"),
        )
        manager = NotificationManager()

        mock_notifier = AsyncMock(spec=BaseNotifier)
        mock_notifier.channel_name = "未配置渠道"
        mock_notifier.is_configured = AsyncMock(return_value=False)
        manager.register(mock_notifier)

        with patch.object(manager, "is_silent_period", return_value=False):
            results = await manager.send_all(sample_message)

        assert results == []
        mock_notifier.send.assert_not_called()


# ---------------------------------------------------------------------------
# PushConfig 测试
# ---------------------------------------------------------------------------


class TestPushConfig:
    """推送配置测试。"""

    def test_default_values(self) -> None:
        config = PushConfig()
        assert config.schedule_time == "18:00"
        assert config.silent_start == "22:00"
        assert config.silent_end == "08:00"
        assert config.event_push_daily_limit == 10

    def test_invalid_daily_limit(self) -> None:
        with pytest.raises(ValueError, match="不能为负数"):
            PushConfig(event_push_daily_limit=-1)

    def test_email_fields(self) -> None:
        config = PushConfig(
            email_smtp_host="smtp.test.com",
            email_smtp_port=587,
            email_sender="test@test.com",
            email_password="pass",
            email_receivers="a@b.com,c@d.com",
        )
        assert config.email_smtp_host == "smtp.test.com"
        assert config.email_smtp_port == 587
