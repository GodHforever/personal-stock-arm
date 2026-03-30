"""FastAPI 后端 API 路由单元测试。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.api.v1 import analysis as analysis_module
from src.api.v1 import watchlists as watchlists_module
from src.api.v1.schemas import ErrorCodes


@pytest.fixture
def app():
    """创建测试用 FastAPI 应用。"""
    return create_app()


@pytest.fixture
async def client(app):
    """创建异步测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_stores():
    """每个测试前重置内存存储。"""
    watchlists_module._reset_store()
    analysis_module._reset_store()
    yield
    watchlists_module._reset_store()
    analysis_module._reset_store()


# ============================================================
# 健康检查
# ============================================================


class TestHealth:
    """健康检查路由测试。"""

    async def test_health_check_成功(self, client: AsyncClient) -> None:
        """AC-4: GET /api/v1/health 返回健康状态。"""
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["message"] == "ok"
        assert body["data"]["status"] == "healthy"
        assert "timestamp" in body["data"]
        assert body["data"]["version"] == "0.1.0"


# ============================================================
# 统一响应和错误码
# ============================================================


class TestSchemas:
    """统一响应模型和错误码测试。"""

    def test_api_response_默认值(self) -> None:
        """AC-1: ApiResponse 默认 code=0, data=None, message='ok'。"""
        from src.api.v1.schemas import ApiResponse

        resp = ApiResponse()
        assert resp.code == 0
        assert resp.data is None
        assert resp.message == "ok"

    def test_api_response_带数据(self) -> None:
        """AC-1: ApiResponse 支持泛型数据。"""
        from src.api.v1.schemas import ApiResponse

        resp = ApiResponse(data={"key": "value"})
        assert resp.data == {"key": "value"}

    def test_paginated_data_默认值(self) -> None:
        """AC-2: PaginatedData 默认值正确。"""
        from src.api.v1.schemas import PaginatedData

        page = PaginatedData()
        assert page.items == []
        assert page.total == 0
        assert page.page == 1
        assert page.page_size == 20
        assert page.total_pages == 0

    def test_error_codes_范围(self) -> None:
        """AC-3: ErrorCodes 涵盖 1xxx/2xxx/3xxx/4xxx。"""
        assert ErrorCodes.INVALID_PARAM == 1001
        assert ErrorCodes.MISSING_FIELD == 1002
        assert ErrorCodes.NOT_FOUND == 1003
        assert ErrorCodes.DATA_SOURCE_TIMEOUT == 2001
        assert ErrorCodes.DATA_SOURCE_UNAVAILABLE == 2002
        assert ErrorCodes.DATA_FORMAT_ERROR == 2003
        assert ErrorCodes.LLM_TIMEOUT == 3001
        assert ErrorCodes.LLM_RATE_LIMITED == 3002
        assert ErrorCodes.LLM_INVALID_RESPONSE == 3003
        assert ErrorCodes.DATABASE_ERROR == 4001
        assert ErrorCodes.CONFIG_ERROR == 4002
        assert ErrorCodes.INTERNAL_ERROR == 4003


# ============================================================
# 自选股管理
# ============================================================


class TestWatchlists:
    """自选股路由测试。"""

    async def test_列表_空(self, client: AsyncClient) -> None:
        """AC-5: 初始状态返回空列表。"""
        resp = await client.get("/api/v1/watchlists")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == []

    async def test_创建分组(self, client: AsyncClient) -> None:
        """AC-5: POST 创建分组返回 201。"""
        resp = await client.post(
            "/api/v1/watchlists",
            json={"name": "核心持仓", "description": "长期持有"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["name"] == "核心持仓"
        assert body["data"]["id"] == 1

    async def test_创建后列表非空(self, client: AsyncClient) -> None:
        """AC-5: 创建后列表包含该分组。"""
        await client.post("/api/v1/watchlists", json={"name": "测试组"})
        resp = await client.get("/api/v1/watchlists")
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "测试组"

    async def test_获取分组详情(self, client: AsyncClient) -> None:
        """AC-6: GET /{id} 返回分组详情。"""
        await client.post("/api/v1/watchlists", json={"name": "详情测试"})
        resp = await client.get("/api/v1/watchlists/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["name"] == "详情测试"
        assert body["data"]["stocks"] == []

    async def test_获取不存在的分组(self, client: AsyncClient) -> None:
        """AC-6: 不存在的分组返回 NOT_FOUND 错误码。"""
        resp = await client.get("/api/v1/watchlists/999")
        body = resp.json()
        assert body["code"] == ErrorCodes.NOT_FOUND

    async def test_删除分组(self, client: AsyncClient) -> None:
        """AC-6: DELETE /{id} 删除分组。"""
        await client.post("/api/v1/watchlists", json={"name": "待删除"})
        resp = await client.delete("/api/v1/watchlists/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

        # 确认已删除
        resp2 = await client.get("/api/v1/watchlists")
        assert resp2.json()["data"] == []

    async def test_删除不存在的分组(self, client: AsyncClient) -> None:
        """AC-6: 删除不存在的分组返回 NOT_FOUND。"""
        resp = await client.delete("/api/v1/watchlists/999")
        body = resp.json()
        assert body["code"] == ErrorCodes.NOT_FOUND

    async def test_添加股票(self, client: AsyncClient) -> None:
        """AC-7: POST /{id}/stocks 添加股票。"""
        await client.post("/api/v1/watchlists", json={"name": "股票测试"})
        resp = await client.post(
            "/api/v1/watchlists/1/stocks",
            json={"code": "600519"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "600519" in body["data"]["stocks"]

    async def test_添加重复股票不重复(self, client: AsyncClient) -> None:
        """AC-7: 重复添加同一股票不会出现重复。"""
        await client.post("/api/v1/watchlists", json={"name": "去重测试"})
        await client.post("/api/v1/watchlists/1/stocks", json={"code": "600519"})
        await client.post("/api/v1/watchlists/1/stocks", json={"code": "600519"})
        resp = await client.get("/api/v1/watchlists/1")
        assert resp.json()["data"]["stocks"].count("600519") == 1

    async def test_移除股票(self, client: AsyncClient) -> None:
        """AC-7: DELETE /{id}/stocks/{code} 移除股票。"""
        await client.post("/api/v1/watchlists", json={"name": "移除测试"})
        await client.post("/api/v1/watchlists/1/stocks", json={"code": "600519"})
        resp = await client.delete("/api/v1/watchlists/1/stocks/600519")
        assert resp.status_code == 200
        body = resp.json()
        assert "600519" not in body["data"]["stocks"]

    async def test_向不存在分组添加股票(self, client: AsyncClient) -> None:
        """AC-7: 向不存在的分组添加股票返回 NOT_FOUND。"""
        resp = await client.post(
            "/api/v1/watchlists/999/stocks",
            json={"code": "600519"},
        )
        assert resp.json()["code"] == ErrorCodes.NOT_FOUND


# ============================================================
# 分析任务
# ============================================================


class TestAnalysis:
    """分析路由测试。"""

    async def test_触发分析任务(self, client: AsyncClient) -> None:
        """AC-8: POST /analysis/run 返回 task_id。"""
        resp = await client.post(
            "/api/v1/analysis/run",
            json={"watchlist_id": 1},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["code"] == 0
        assert "task_id" in body["data"]
        assert len(body["data"]["task_id"]) > 0

    async def test_查询任务状态(self, client: AsyncClient) -> None:
        """AC-9: GET /analysis/tasks/{task_id} 返回任务状态。"""
        create_resp = await client.post(
            "/api/v1/analysis/run",
            json={"watchlist_id": 1},
        )
        task_id = create_resp.json()["data"]["task_id"]

        resp = await client.get(f"/api/v1/analysis/tasks/{task_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["task_id"] == task_id
        assert body["data"]["status"] == "pending"

    async def test_查询不存在的任务(self, client: AsyncClient) -> None:
        """AC-9: 查询不存在的任务返回 NOT_FOUND。"""
        resp = await client.get("/api/v1/analysis/tasks/nonexistent")
        body = resp.json()
        assert body["code"] == ErrorCodes.NOT_FOUND

    async def test_分析结果_空列表(self, client: AsyncClient) -> None:
        """AC-10: GET /analysis/results 初始返回空分页数据。"""
        resp = await client.get("/api/v1/analysis/results")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0
        assert body["data"]["page"] == 1

    async def test_分析结果_分页参数(self, client: AsyncClient) -> None:
        """AC-10: 分页参数正确传递。"""
        resp = await client.get("/api/v1/analysis/results?page=2&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10


# ============================================================
# 宏观数据
# ============================================================


class TestMacro:
    """宏观数据路由测试。"""

    async def test_获取宏观数据(self, client: AsyncClient) -> None:
        """AC-11: GET /macro 返回宏观数据。"""
        resp = await client.get("/api/v1/macro")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "indicators" in body["data"]
        assert "summary" in body["data"]


# ============================================================
# 简报/财报/研报
# ============================================================


class TestBriefings:
    """简报路由测试。"""

    async def test_获取国际简报(self, client: AsyncClient) -> None:
        """AC-12: GET /briefings 返回列表。"""
        resp = await client.get("/api/v1/briefings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    async def test_获取财报摘要(self, client: AsyncClient) -> None:
        """AC-13: GET /earnings 返回列表。"""
        resp = await client.get("/api/v1/earnings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    async def test_获取研报摘要(self, client: AsyncClient) -> None:
        """AC-14: GET /reports 返回列表。"""
        resp = await client.get("/api/v1/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)


# ============================================================
# 全局异常处理器
# ============================================================


class TestExceptionHandlers:
    """全局异常处理器测试。"""

    async def test_data_source_error_处理(self, app, client: AsyncClient) -> None:
        """AC-15: DataSourceError 转换为统一错误响应。"""
        from src.network.errors import DataSourceError

        @app.get("/api/v1/_test/data-error")
        async def _trigger_data_error():
            raise DataSourceError(
                step="请求发送",
                source="test",
                url="http://test.com",
                error_type="超时",
                error_msg="连接超时",
                suggestion="稍后重试",
            )

        resp = await client.get("/api/v1/_test/data-error")
        assert resp.status_code == 502
        body = resp.json()
        assert body["code"] == ErrorCodes.DATA_SOURCE_TIMEOUT

    async def test_config_load_error_处理(self, app, client: AsyncClient) -> None:
        """AC-15: ConfigLoadError 转换为统一错误响应。"""
        from src.config.manager import ConfigLoadError

        @app.get("/api/v1/_test/config-error")
        async def _trigger_config_error():
            raise ConfigLoadError("测试配置错误")

        resp = await client.get("/api/v1/_test/config-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == ErrorCodes.CONFIG_ERROR

    async def test_value_error_处理(self, app, client: AsyncClient) -> None:
        """AC-15: ValueError 转换为客户端错误。"""

        @app.get("/api/v1/_test/value-error")
        async def _trigger_value_error():
            raise ValueError("参数无效")

        resp = await client.get("/api/v1/_test/value-error")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == ErrorCodes.INVALID_PARAM

    async def test_未预期异常_处理(self, app, client: AsyncClient) -> None:
        """AC-15: 未预期异常转换为内部错误，隐藏细节。"""

        @app.get("/api/v1/_test/unexpected")
        async def _trigger_unexpected():
            raise RuntimeError("内部错误细节")

        resp = await client.get("/api/v1/_test/unexpected")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == ErrorCodes.INTERNAL_ERROR
        assert "内部错误细节" not in body["message"]


# ============================================================
# 应用工厂
# ============================================================


class TestCreateApp:
    """应用工厂测试。"""

    def test_create_app_返回FastAPI实例(self) -> None:
        """AC-16: create_app() 返回 FastAPI 实例。"""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_包含v1路由(self) -> None:
        """AC-16: 应用包含 /api/v1 前缀的路由。"""
        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/health" in routes


from fastapi import FastAPI
