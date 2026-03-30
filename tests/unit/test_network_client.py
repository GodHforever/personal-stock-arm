"""网络请求模块单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.config import ConfigManager
from src.config.models import AppConfig, DataConfig, NetworkConfig
from src.network.client import _BACKOFF_BASE, _BACKOFF_MULTIPLIER, NetworkClient
from src.network.errors import DataSourceError

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _ok_response(text: str = "ok") -> httpx.Response:
    """创建带 request 属性的成功响应（raise_for_status 需要）。"""
    return httpx.Response(
        200,
        text=text,
        request=httpx.Request("GET", "https://example.com"),
    )


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
def default_config() -> AppConfig:
    """使用默认超时和重试配置初始化 ConfigManager。"""
    return ConfigManager.initialize()


@pytest.fixture()
def fast_config() -> AppConfig:
    """使用快速超时（用于加速测试）的配置。"""
    return ConfigManager.initialize(
        data=DataConfig(connect_timeout=1, read_timeout=2, max_retries=2),
    )


@pytest.fixture()
def proxy_config() -> AppConfig:
    """带代理配置。"""
    return ConfigManager.initialize(
        net=NetworkConfig(proxy="http://proxy.example.com:8080"),
    )


@pytest.fixture()
def no_retry_config() -> AppConfig:
    """不重试的配置（max_retries=0）。"""
    return ConfigManager.initialize(
        data=DataConfig(max_retries=0),
    )


# ---------------------------------------------------------------------------
# DataSourceError 测试
# ---------------------------------------------------------------------------


class TestDataSourceError:
    """DataSourceError 结构化异常测试。"""

    def test_fields_stored_correctly(self) -> None:
        """AC-1: 异常包含所有结构化字段。"""
        err = DataSourceError(
            step="请求发送",
            source="tushare",
            url="https://api.tushare.pro",
            error_type="超时",
            error_msg="连接超时",
            suggestion="请检查网络",
        )
        assert err.step == "请求发送"
        assert err.source == "tushare"
        assert err.url == "https://api.tushare.pro"
        assert err.error_type == "超时"
        assert err.error_msg == "连接超时"
        assert err.suggestion == "请检查网络"

    def test_to_dict(self) -> None:
        """AC-2: to_dict() 返回包含所有字段的字典。"""
        err = DataSourceError(
            step="响应解析",
            source="akshare",
            url="https://akshare.example.com",
            error_type="HTTP 500",
            error_msg="服务器内部错误",
            suggestion="请稍后重试",
        )
        result = err.to_dict()
        assert isinstance(result, dict)
        assert result == {
            "step": "响应解析",
            "source": "akshare",
            "url": "https://akshare.example.com",
            "error_type": "HTTP 500",
            "error_msg": "服务器内部错误",
            "suggestion": "请稍后重试",
        }

    def test_str_chinese_readable(self) -> None:
        """AC-3: __str__() 返回中文可读描述。"""
        err = DataSourceError(
            step="请求发送",
            source="tushare",
            url="https://api.tushare.pro",
            error_type="超时",
            error_msg="连接超时 5s",
            suggestion="请检查网络连接",
        )
        text = str(err)
        assert "tushare" in text
        assert "请求发送" in text
        assert "超时" in text
        assert "连接超时 5s" in text
        assert "建议" in text
        assert "请检查网络连接" in text

    def test_is_exception(self) -> None:
        """DataSourceError 是 Exception 的子类。"""
        err = DataSourceError(
            step="测试",
            source="test",
            url="http://test",
            error_type="测试",
            error_msg="测试",
            suggestion="测试",
        )
        assert isinstance(err, Exception)

    def test_to_dict_keys_complete(self) -> None:
        """to_dict() 返回的字典包含全部 6 个字段。"""
        err = DataSourceError(
            step="s", source="src", url="u",
            error_type="t", error_msg="m", suggestion="sg",
        )
        expected_keys = {"step", "source", "url", "error_type", "error_msg", "suggestion"}
        assert set(err.to_dict().keys()) == expected_keys


# ---------------------------------------------------------------------------
# NetworkClient 测试
# ---------------------------------------------------------------------------


class TestNetworkClientInit:
    """NetworkClient 初始化和配置测试。"""

    def test_source_name_stored(self, default_config: AppConfig) -> None:
        """AC-4: NetworkClient 保存数据源名称。"""
        client = NetworkClient("tushare")
        assert client.source_name == "tushare"

    def test_build_client_timeout(self, default_config: AppConfig) -> None:
        """AC-6: 超时从 DataConfig 读取。"""
        client = NetworkClient("test")
        httpx_client = client._build_client()
        assert httpx_client.timeout.connect == 5.0
        assert httpx_client.timeout.read == 30.0

    def test_build_client_custom_timeout(self, fast_config: AppConfig) -> None:
        """AC-6: 自定义超时配置生效。"""
        client = NetworkClient("test")
        httpx_client = client._build_client()
        assert httpx_client.timeout.connect == 1.0
        assert httpx_client.timeout.read == 2.0

    def test_build_client_no_proxy(self, default_config: AppConfig) -> None:
        """AC-8: 无代理配置时不设置代理。"""
        client = NetworkClient("test")
        httpx_client = client._build_client()
        assert httpx_client._transport.__class__.__name__ == "AsyncHTTPTransport"


class TestNetworkClientContextManager:
    """NetworkClient 异步上下文管理器测试。"""

    @pytest.mark.asyncio()
    async def test_context_manager(self, default_config: AppConfig) -> None:
        """AC-10: 支持 async with 使用。"""
        async with NetworkClient("test") as client:
            assert client._client is not None

    @pytest.mark.asyncio()
    async def test_context_manager_cleanup(self, default_config: AppConfig) -> None:
        """AC-10: 退出上下文后客户端被关闭。"""
        client = NetworkClient("test")
        async with client:
            assert client._client is not None
        assert client._client is None


class TestNetworkClientGet:
    """NetworkClient.get() 方法测试。"""

    @pytest.mark.asyncio()
    async def test_get_success(self, default_config: AppConfig) -> None:
        """AC-5: GET 请求成功返回 Response。"""
        mock_response = _ok_response('{"data": "ok"}')

        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = AsyncMock(return_value=mock_response)
            response = await client.get("https://api.example.com/data")
            assert response.status_code == 200
            assert response.text == '{"data": "ok"}'

    @pytest.mark.asyncio()
    async def test_get_with_params(self, default_config: AppConfig) -> None:
        """AC-5: GET 请求透传额外参数。"""
        mock_response = _ok_response()
        mock_request = AsyncMock(return_value=mock_response)

        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = mock_request
            await client.get("https://api.example.com", params={"key": "val"})
            mock_request.assert_called_once_with(
                "GET", "https://api.example.com", params={"key": "val"},
            )


class TestNetworkClientPost:
    """NetworkClient.post() 方法测试。"""

    @pytest.mark.asyncio()
    async def test_post_success(self, default_config: AppConfig) -> None:
        """AC-5: POST 请求成功返回 Response。"""
        mock_response = _ok_response('{"result": "created"}')

        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = AsyncMock(return_value=mock_response)
            response = await client.post(
                "https://api.example.com/data",
                json={"code": "000001"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio()
    async def test_post_with_json(self, default_config: AppConfig) -> None:
        """AC-5: POST 请求透传 JSON 数据。"""
        mock_response = _ok_response()
        mock_request = AsyncMock(return_value=mock_response)

        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = mock_request
            await client.post("https://api.example.com", json={"a": 1})
            mock_request.assert_called_once_with(
                "POST", "https://api.example.com", json={"a": 1},
            )


class TestNetworkClientRetry:
    """重试和指数退避测试。"""

    @pytest.mark.asyncio()
    async def test_retry_on_timeout(self, default_config: AppConfig) -> None:
        """AC-7: 超时时自动重试。"""
        mock_response = _ok_response()

        async with NetworkClient("test") as client:
            assert client._client is not None
            mock_request = AsyncMock(
                side_effect=[
                    httpx.ReadTimeout("读取超时"),
                    httpx.ReadTimeout("读取超时"),
                    mock_response,
                ],
            )
            client._client.request = mock_request
            with patch("src.network.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                response = await client.get("https://api.example.com")

            assert response.status_code == 200
            assert mock_request.call_count == 3
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)

    @pytest.mark.asyncio()
    async def test_retry_on_connect_error(self, default_config: AppConfig) -> None:
        """AC-7: 连接错误时自动重试。"""
        mock_response = _ok_response()

        async with NetworkClient("test") as client:
            assert client._client is not None
            mock_request = AsyncMock(
                side_effect=[
                    httpx.ConnectError("连接被拒绝"),
                    mock_response,
                ],
            )
            client._client.request = mock_request
            with patch("src.network.client.asyncio.sleep", new_callable=AsyncMock):
                response = await client.get("https://api.example.com")

            assert response.status_code == 200
            assert mock_request.call_count == 2

    @pytest.mark.asyncio()
    async def test_retry_on_server_error(self, default_config: AppConfig) -> None:
        """AC-7/AC-9: 5xx 服务端错误时重试。"""
        error_response = httpx.Response(
            500, text="Internal Server Error",
            request=httpx.Request("GET", "https://api.example.com"),
        )
        ok_response = _ok_response()

        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = AsyncMock(
                side_effect=[
                    httpx.HTTPStatusError(
                        "500", request=error_response.request, response=error_response,
                    ),
                    ok_response,
                ],
            )
            with patch("src.network.client.asyncio.sleep", new_callable=AsyncMock):
                response = await client.get("https://api.example.com")

            assert response.status_code == 200

    @pytest.mark.asyncio()
    async def test_no_retry_on_client_error(self, default_config: AppConfig) -> None:
        """AC-9: 4xx 客户端错误不重试，立即抛出 DataSourceError。"""
        error_response = httpx.Response(
            404, text="Not Found",
            request=httpx.Request("GET", "https://api.example.com"),
        )

        async with NetworkClient("test") as client:
            assert client._client is not None
            mock_request = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=error_response.request, response=error_response,
                ),
            )
            client._client.request = mock_request
            with pytest.raises(DataSourceError) as exc_info:
                await client.get("https://api.example.com")

            assert "HTTP 404" in exc_info.value.error_type
            assert mock_request.call_count == 1

    @pytest.mark.asyncio()
    async def test_exponential_backoff_delays(self, default_config: AppConfig) -> None:
        """AC-7: 验证指数退避间隔为 1s, 2s, 4s。"""
        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = AsyncMock(
                side_effect=httpx.ReadTimeout("超时"),
            )
            with patch("src.network.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
                    pytest.raises(DataSourceError):
                await client.get("https://api.example.com")

            assert mock_sleep.call_count == 3
            calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert calls == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio()
    async def test_all_retries_exhausted(self, default_config: AppConfig) -> None:
        """AC-9: 所有重试耗尽后抛出 DataSourceError。"""
        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = AsyncMock(
                side_effect=httpx.ConnectError("连接被拒绝"),
            )
            with patch("src.network.client.asyncio.sleep", new_callable=AsyncMock), \
                    pytest.raises(DataSourceError) as exc_info:
                await client.get("https://api.example.com")

            err = exc_info.value
            assert err.source == "test"
            assert err.error_type == "连接失败"
            assert "api.example.com" in err.url

    @pytest.mark.asyncio()
    async def test_no_retry_when_max_retries_zero(self, no_retry_config: AppConfig) -> None:
        """AC-7: max_retries=0 时不重试。"""
        async with NetworkClient("test") as client:
            assert client._client is not None
            mock_request = AsyncMock(
                side_effect=httpx.ReadTimeout("超时"),
            )
            client._client.request = mock_request
            with pytest.raises(DataSourceError):
                await client.get("https://api.example.com")

            assert mock_request.call_count == 1


class TestNetworkClientErrorConversion:
    """异常转换测试。"""

    @pytest.mark.asyncio()
    async def test_timeout_converts_to_datasource_error(self, no_retry_config: AppConfig) -> None:
        """AC-9: 超时异常转换为 DataSourceError。"""
        async with NetworkClient("tushare") as client:
            assert client._client is not None
            client._client.request = AsyncMock(
                side_effect=httpx.ReadTimeout("读取超时"),
            )
            with pytest.raises(DataSourceError) as exc_info:
                await client.get("https://api.tushare.pro")

            err = exc_info.value
            assert err.source == "tushare"
            assert err.error_type == "超时"
            assert "tushare.pro" in err.url

    @pytest.mark.asyncio()
    async def test_connect_error_converts_to_datasource_error(
        self, no_retry_config: AppConfig,
    ) -> None:
        """AC-9: 连接错误转换为 DataSourceError。"""
        async with NetworkClient("akshare") as client:
            assert client._client is not None
            client._client.request = AsyncMock(
                side_effect=httpx.ConnectError("连接被拒绝"),
            )
            with pytest.raises(DataSourceError) as exc_info:
                await client.get("https://akshare.example.com")

            err = exc_info.value
            assert err.source == "akshare"
            assert err.error_type == "连接失败"

    @pytest.mark.asyncio()
    async def test_http_error_converts_to_datasource_error(
        self, no_retry_config: AppConfig,
    ) -> None:
        """AC-9: 通用 HTTP 错误转换为 DataSourceError。"""
        async with NetworkClient("test") as client:
            assert client._client is not None
            client._client.request = AsyncMock(
                side_effect=httpx.HTTPError("未知错误"),
            )
            with pytest.raises(DataSourceError) as exc_info:
                await client.get("https://api.example.com")

            err = exc_info.value
            assert err.error_type == "网络错误"


class TestNetworkClientBackoffConstants:
    """退避常量验证。"""

    def test_backoff_base(self) -> None:
        """退避基础间隔为 1 秒。"""
        assert _BACKOFF_BASE == 1.0

    def test_backoff_multiplier(self) -> None:
        """退避倍数为 2。"""
        assert _BACKOFF_MULTIPLIER == 2.0
