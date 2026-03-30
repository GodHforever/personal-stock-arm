"""Stock-ARM 应用入口点。"""

from __future__ import annotations

import argparse
import asyncio
import sys


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Stock-ARM 金融分析工具")
    parser.add_argument("--daemon", action="store_true", help="以守护进程模式运行（云端部署）")
    parser.add_argument("--webui", action="store_true", help="启动 Web UI（本地模式，自动打开浏览器）")
    parser.add_argument("--port", type=int, default=None, help="服务端口覆盖")
    return parser.parse_args()


async def startup() -> None:
    """应用启动流程。"""
    # TODO: 各模块实现后按顺序初始化
    # 1. 加载配置 (ConfigManager)
    # 2. 初始化日志 (setup_logging)
    # 3. 初始化数据库 (Database)
    # 4. 启动调度器 (TaskScheduler)
    # 5. 启动 FastAPI 服务
    pass


async def shutdown() -> None:
    """应用关闭流程。"""
    # TODO: 各模块实现后按顺序清理
    # 1. 停止调度器
    # 2. 关闭数据库连接
    pass


def main() -> None:
    """主入口。"""
    args = parse_args()

    if sys.version_info < (3, 11):
        print("错误: Stock-ARM 需要 Python 3.11 或更高版本")
        sys.exit(1)

    asyncio.run(startup())


if __name__ == "__main__":
    main()
