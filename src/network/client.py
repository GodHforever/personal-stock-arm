"""网络请求客户端：封装 httpx.AsyncClient，提供自动超时、重试和结构化异常。"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from src.config import ConfigManager
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

# 指数退避基础间隔（秒）
_BACKOFF_BASE: float = 1.0
# 指数退避倍数
_BACKOFF_MULTIPLIER: float = 2.0


class NetworkClient:
    """统一 HTTP 客户端，封装 httpx.AsyncClient。

    提供自动超时、指数退避重试、代理支持和结构化异常。
    所有数据源适配器应通过此客户端发起网络请求。

    使用方式::

        async with NetworkClient("tushare") as client:
            response = await client.get("https://api.example.com/data")
    """

    def __init__(self, source_name: str) -> None:
        """初始化网络客户端。

        Args:
            source_name: 数据源名称，用于日志和异常信息中标识来源
        """
        self.source_name = source_name
        self._client: httpx.AsyncClient | None = None

    def _build_client(self) -> httpx.AsyncClient:
        """根据配置构建 httpx.AsyncClient 实例。"""
        config = ConfigManager.get_config()
        data_cfg = config.data
        net_cfg = config.net

        timeout = httpx.Timeout(
            connect=float(data_cfg.connect_timeout),
            read=float(data_cfg.read_timeout),
            write=float(data_cfg.read_timeout),
            pool=float(data_cfg.read_timeout),
        )

        proxy = net_cfg.proxy if net_cfg.proxy else None

        return httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy,
            verify=net_cfg.ssl_verify,
        )

    async def __aenter__(self) -> NetworkClient:
        """进入异步上下文管理器，创建底层 HTTP 客户端。"""
        self._client = self._build_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """退出异步上下文管理器，关闭底层 HTTP 客户端。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """确保客户端已初始化。"""
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """发起 GET 请求，自动重试。

        Args:
            url: 请求 URL
            **kwargs: 传递给 httpx.AsyncClient.get 的额外参数

        Returns:
            httpx.Response 对象

        Raises:
            DataSourceError: 所有重试失败后抛出
        """
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """发起 POST 请求，自动重试。

        Args:
            url: 请求 URL
            **kwargs: 传递给 httpx.AsyncClient.post 的额外参数

        Returns:
            httpx.Response 对象

        Raises:
            DataSourceError: 所有重试失败后抛出
        """
        return await self._request("POST", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """发起 HTTP 请求，带指数退避重试。

        Args:
            method: HTTP 方法（GET / POST）
            url: 请求 URL
            **kwargs: 传递给 httpx 的额外参数

        Returns:
            httpx.Response 对象

        Raises:
            DataSourceError: 所有重试失败后抛出
        """
        max_retries = ConfigManager.get_config().data.max_retries
        client = self._ensure_client()
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                last_error = exc
                error_type = "超时"
                error_msg = f"请求超时: {exc}"
                suggestion = "请检查网络连接或增大超时配置"
            except httpx.ConnectError as exc:
                last_error = exc
                error_type = "连接失败"
                error_msg = f"无法连接到服务器: {exc}"
                suggestion = "请检查网络连接或代理配置"
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                error_type = f"HTTP {status_code}"
                error_msg = f"服务器返回错误状态码: {status_code}"
                # 4xx 客户端错误不重试
                if 400 <= status_code < 500:
                    raise DataSourceError(
                        step="请求发送",
                        source=self.source_name,
                        url=url,
                        error_type=error_type,
                        error_msg=error_msg,
                        suggestion="请检查请求参数是否正确",
                    ) from exc
                suggestion = "服务端错误，请稍后重试"
            except httpx.HTTPError as exc:
                last_error = exc
                error_type = "网络错误"
                error_msg = f"请求异常: {exc}"
                suggestion = "请检查网络连接"

            # 还有重试机会时等待
            if attempt < max_retries:
                delay = _BACKOFF_BASE * (_BACKOFF_MULTIPLIER ** attempt)
                logger.warning(
                    "[%s] %s %s 第 %d 次请求失败（%s），%.1f 秒后重试",
                    self.source_name,
                    method,
                    url,
                    attempt + 1,
                    error_type,
                    delay,
                )
                await asyncio.sleep(delay)

        # 所有重试耗尽
        logger.error(
            "[%s] %s %s 请求失败，已重试 %d 次",
            self.source_name,
            method,
            url,
            max_retries,
        )
        raise DataSourceError(
            step="请求发送",
            source=self.source_name,
            url=url,
            error_type=error_type,  # type: ignore[possibly-undefined]
            error_msg=error_msg,  # type: ignore[possibly-undefined]
            suggestion=suggestion,  # type: ignore[possibly-undefined]
        ) from last_error
