# Stock-ARM 部署与使用指南

> 面向最终用户和运维人员的完整部署、配置与使用手册。

---

## 目录

- [第一部分：快速开始](#第一部分快速开始)
- [第二部分：详细部署指南](#第二部分详细部署指南)
  - [2.1 本地模式（Windows/macOS/Linux）](#21-本地模式windowsmacoslinux)
  - [2.2 云端部署（Linux VPS）](#22-云端部署linux-vps)
  - [2.3 Docker 部署](#23-docker-部署)
  - [2.4 可执行文件打包（Windows/macOS）](#24-可执行文件打包windowsmacos)
- [第三部分：配置详解](#第三部分配置详解)
- [第四部分：功能使用指南](#第四部分功能使用指南)
  - [4.1 自选股管理](#41-自选股管理)
  - [4.2 每日分析报告](#42-每日分析报告)
  - [4.3 宏观数据追踪](#43-宏观数据追踪)
  - [4.4 财报处理](#44-财报处理)
  - [4.5 国际金融简报](#45-国际金融简报)
  - [4.6 研报管理](#46-研报管理)
  - [4.7 推送通知](#47-推送通知)
- [第五部分：API 参考](#第五部分api-参考)
- [第六部分：运维与故障排除](#第六部分运维与故障排除)

---

## 第一部分：快速开始

### 系统要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 必需，推荐 3.11.9 |
| Node.js | 20+ | 仅开发前端时需要 |
| SQLite | 3.35+ | 通常随 Python 自带 |
| 操作系统 | Windows 10+ / macOS 12+ / Linux (glibc 2.31+) | 全平台支持 |

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/personal-stock-arm.git
cd personal-stock-arm

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动（自动打开浏览器）
python main.py --webui
```

### 首次运行配置向导

首次运行时，如果未检测到 `.env` 文件，程序会自动启动配置向导：

```
Stock-ARM 首次运行配置向导
=============================

[1/3] LLM 配置（必填）
  请输入 LLM API Key: ▌
  主模型 [deepseek-chat]: ▌
  快速模型 [glm-4-flash]: ▌

[2/3] 数据源配置（可选，回车跳过）
  Tushare Pro Token: ▌

[3/3] 推送通知配置（可选，回车跳过）
  企业微信 Webhook URL: ▌
  飞书 Webhook URL: ▌

配置已保存至 .env 文件。
```

你也可以手动从模板创建配置文件：

```bash
cp .env.example .env
# 然后用编辑器修改 .env 文件
```

启动流程概览：

```
1. 检测 Python 版本 >= 3.11，不满足则报错退出
2. 检查/安装依赖（pip install -r requirements.txt）
3. 初始化 SQLite 数据库（运行 Alembic 迁移）
4. 如果 .env 不存在，启动配置向导
5. 启动 FastAPI 服务 + 任务调度器
6. 自动打开浏览器访问 http://localhost:8000（仅本地模式）
```

---

## 第二部分：详细部署指南

### 2.1 本地模式（Windows/macOS/Linux）

#### Python 环境准备

推荐使用 pyenv 或 conda 管理 Python 版本，确保使用 Python 3.11+。

**使用 pyenv（Linux/macOS）：**

```bash
# 安装 pyenv
curl https://pyenv.run | bash

# 安装 Python 3.11.9
pyenv install 3.11.9
pyenv local 3.11.9

# 验证版本
python --version
# Python 3.11.9
```

**使用 conda（全平台）：**

```bash
# 创建虚拟环境
conda create -n stock-arm python=3.11 -y
conda activate stock-arm

# 验证版本
python --version
```

**使用 venv（全平台）：**

```bash
# 创建虚拟环境
python3.11 -m venv .venv

# 激活虚拟环境
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

#### 依赖安装

```bash
pip install -r requirements.txt
```

#### 数据库初始化

```bash
# 运行数据库迁移，自动创建 SQLite 数据库
alembic upgrade head
```

数据库文件默认位于 `./data/stock_arm.db`，使用 WAL 模式以支持并发读取。

#### 启动命令和参数

```bash
# 标准启动（启动 Web 服务 + 打开浏览器）
python main.py --webui

# 仅启动后端服务（不打开浏览器）
python main.py

# 指定端口
python main.py --webui --port 9000

# 调试模式（详细日志）
STOCK_ARM_LOG_LEVEL=DEBUG python main.py --webui
```

#### 自动打开浏览器行为

在本地模式下，`--webui` 参数会在服务启动后自动打开默认浏览器访问 `http://localhost:<PORT>`。如果端口被占用，程序会自动尝试下一个可用端口。

#### 调度器行为：启动时 catch-up + 实时调度

本地模式下，调度器采用"启动补偿 + 实时调度"策略：

```
用户启动程序
  │
  ├── 1. 读取数据库中的 last_run_time
  │     ├── 今日任务未执行 → 自动补跑到期任务
  │     └── 今日任务已完成 → 跳过
  │
  ├── 2. 注册今日剩余任务
  │     └── 如果程序仍在运行到调度时间，正常触发
  │
  ├── 3. Web UI 显示 "Catch-up" 入口
  │     └── 用户可选择日期范围进行补录
  │     └── 补录结果仅在 Web 中展示，不推送
  │
  └── 4. 用户关闭程序
        └── 记录 last_run_time，调度器停止
```

---

### 2.2 云端部署（Linux VPS）

#### 准备工作

```bash
# 1. 创建专用用户
sudo useradd -r -m -s /bin/bash stockarm
sudo su - stockarm

# 2. 安装 Python 3.11（以 Ubuntu 22.04 为例）
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

#### 部署步骤

```bash
# 1. 克隆代码到部署目录
sudo mkdir -p /opt/stock-arm
sudo chown stockarm:stockarm /opt/stock-arm
git clone https://github.com/your-repo/personal-stock-arm.git /opt/stock-arm
cd /opt/stock-arm

# 2. 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
alembic upgrade head

# 5. 创建必要目录
mkdir -p data config logs
```

#### 配置 .env（云端特有配置）

```bash
cp .env.example .env
```

编辑 `.env` 文件，重点配置以下云端特有项：

```env
# === 运行时模式 ===
STOCK_ARM_RUNTIME_ENV=cloud       # 强制云端模式
STOCK_ARM_BIND_HOST=0.0.0.0      # 允许外部访问
STOCK_ARM_PORT=8000               # 服务端口
STOCK_ARM_LOG_TO_STDOUT=true      # 日志同时输出到 stdout（方便 journalctl 查看）

# === 认证（云端必须启用）===
STOCK_ARM_AUTH_ENABLED=true       # 开启 Web UI 密码认证
STOCK_ARM_AUTH_USERNAME=admin     # 认证用户名
STOCK_ARM_AUTH_PASSWORD=YourStrongPassword123!  # 认证密码

# === SSL（可选，推荐使用反向代理）===
STOCK_ARM_SSL_CERT_PATH=         # 留空，由 Nginx/Caddy 处理
STOCK_ARM_SSL_KEY_PATH=

# === 数据备份 ===
STOCK_ARM_BACKUP_ENABLED=true    # 启用定时备份
STOCK_ARM_BACKUP_PATH=/backup/stock-arm/   # 备份目标目录
STOCK_ARM_BACKUP_CRON=0 3 * * *  # 每天凌晨 3 点备份

# === LLM（必填）===
STOCK_ARM_LLM_API_KEY=sk-xxx
STOCK_ARM_LLM_PRIMARY_MODEL=deepseek-chat
STOCK_ARM_LLM_FAST_MODEL=glm-4-flash
```

#### systemd 服务配置

```bash
# 复制服务文件
sudo cp deploy/stock-arm.service /etc/systemd/system/stock-arm.service
```

服务文件内容 (`deploy/stock-arm.service`)：

```ini
[Unit]
Description=Stock-ARM 金融分析服务
After=network.target

[Service]
Type=simple
User=stockarm
WorkingDirectory=/opt/stock-arm
ExecStart=/opt/stock-arm/.venv/bin/python main.py --daemon
Restart=on-failure
RestartSec=10
EnvironmentFile=/opt/stock-arm/.env

[Install]
WantedBy=multi-user.target
```

> 注意：如果你的安装路径或用户名不同，需要修改服务文件中的 `User`、`WorkingDirectory`、`ExecStart` 和 `EnvironmentFile` 路径。

#### 启动/停止/重启/查看日志

```bash
# 启用开机自启
sudo systemctl enable stock-arm

# 启动服务
sudo systemctl start stock-arm

# 查看服务状态
sudo systemctl status stock-arm

# 停止服务
sudo systemctl stop stock-arm

# 重启服务
sudo systemctl restart stock-arm

# 查看实时日志
sudo journalctl -u stock-arm -f

# 查看最近 100 行日志
sudo journalctl -u stock-arm -n 100

# 查看今天的日志
sudo journalctl -u stock-arm --since today
```

#### HTTPS 配置（反向代理）

推荐使用 Nginx 或 Caddy 作为反向代理，处理 HTTPS 证书。

**方案一：Caddy（推荐，自动 HTTPS）**

```bash
# 安装 Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

编辑 `/etc/caddy/Caddyfile`：

```
stock.yourdomain.com {
    reverse_proxy localhost:8000
}
```

```bash
sudo systemctl restart caddy
```

Caddy 会自动申请并续期 Let's Encrypt 证书。

**方案二：Nginx**

```bash
# 安装 Nginx 和 certbot
sudo apt install nginx certbot python3-certbot-nginx

# 申请 SSL 证书
sudo certbot --nginx -d stock.yourdomain.com
```

Nginx 配置文件 `/etc/nginx/sites-available/stock-arm`：

```nginx
server {
    listen 80;
    server_name stock.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name stock.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/stock.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/stock.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持（用于分析进度推送）
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/stock-arm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 数据备份策略

当启用了 `STOCK_ARM_BACKUP_ENABLED=true` 后，系统会按照 `STOCK_ARM_BACKUP_CRON` 定义的计划自动备份数据库。

你也可以手动备份：

```bash
# 手动备份 SQLite 数据库
cp /opt/stock-arm/data/stock_arm.db /backup/stock-arm/stock_arm_$(date +%Y%m%d_%H%M%S).db

# 设置 cron 定时备份（如未使用内置备份功能）
crontab -e
# 添加以下行（每天凌晨 3 点备份）:
# 0 3 * * * cp /opt/stock-arm/data/stock_arm.db /backup/stock-arm/stock_arm_$(date +\%Y\%m\%d).db
```

#### 调度器行为：7x24 持续调度

云端模式下，调度器持续运行，在预设的 cron 时间自动触发各项任务，无需 catch-up 机制。

---

### 2.3 Docker 部署

#### 前提条件

```bash
# 安装 Docker（以 Ubuntu 为例）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 验证 Docker 和 Docker Compose
docker --version
docker compose version
```

#### docker-compose.yml 说明

项目自带 `docker-compose.yml` 文件：

```yaml
services:
  app:
    build: .
    container_name: stock-arm
    env_file: .env
    ports:
      - "${STOCK_ARM_PORT:-8000}:8000"
    volumes:
      - ./data:/app/data       # SQLite 数据库持久化
      - ./config:/app/config   # 用户配置持久化
      - ./logs:/app/logs       # 日志持久化
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/api/v1/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
```

关键说明：
- **端口映射**：默认映射宿主机 8000 端口到容器 8000 端口，可通过 `.env` 的 `STOCK_ARM_PORT` 修改
- **数据持久化**：通过三个 volume 挂载确保数据、配置、日志不会随容器销毁而丢失
- **健康检查**：每 30 秒调用 `/api/v1/health` 端点检测服务健康状态
- **自动重启**：`unless-stopped` 策略确保服务异常退出后自动重启

#### 环境变量注入

```bash
# 从模板创建配置文件
cp .env.example .env

# 编辑配置（至少设置 LLM API Key）
vim .env
```

Docker 环境下会自动设置以下环境变量（无需手动配置）：

```env
STOCK_ARM_RUNTIME_ENV=docker
STOCK_ARM_BIND_HOST=0.0.0.0
STOCK_ARM_PORT=8000
STOCK_ARM_LOG_TO_STDOUT=true
```

#### 数据持久化

| 挂载路径 | 宿主机路径 | 容器内路径 | 内容 |
|---------|-----------|-----------|------|
| data | `./data` | `/app/data` | SQLite 数据库、分析结果 |
| config | `./config` | `/app/config` | 用户自定义配置 |
| logs | `./logs` | `/app/logs` | 应用日志 |

首次运行前确保宿主机目录存在：

```bash
mkdir -p data config logs
```

#### 启动/停止/更新命令

```bash
# 构建并启动（后台运行）
docker compose up -d --build

# 查看运行状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看最近 100 行日志
docker compose logs --tail 100

# 停止服务
docker compose down

# 更新到最新代码并重启
git pull
docker compose up -d --build

# 完全清理（包括数据卷，慎用！）
docker compose down -v
```

#### 开发模式

创建 `docker-compose.override.yml` 以启用源码挂载和热重载：

```yaml
services:
  app:
    volumes:
      - ./src:/app/src          # 源码挂载，支持热重载
    command: ["python", "-m", "uvicorn", "src.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    environment:
      - STOCK_ARM_LOG_LEVEL=DEBUG
```

```bash
# 开发模式启动
docker compose up --build
```

在开发模式下，修改 `src/` 目录下的代码会自动触发服务重载，无需重新构建镜像。

#### 调度器行为

Docker 模式下的调度器行为与云端模式相同：7x24 持续运行，在预设 cron 时间自动触发任务。

---

### 2.4 可执行文件打包（Windows/macOS）

#### PyInstaller 打包流程

```bash
# 安装 PyInstaller
pip install pyinstaller

# Windows 打包
python build/build_windows.py

# macOS 打包
python build/build_macos.py
```

#### 构建脚本位置

```
build/
├── build_windows.py    # Windows 构建脚本
├── build_macos.py      # macOS 构建脚本
├── stock-arm.spec      # PyInstaller 配置文件
└── assets/             # 图标、启动画面等资源
```

#### 打包要求

- 前端预先编译为静态文件，嵌入到可执行文件中
- 单文件可执行文件（PyInstaller `--onefile`）
- 启动行为与 `python main.py --webui` 一致（启动服务 + 打开浏览器）

#### 分发和安装说明

**Windows**：
1. 双击 `stock-arm.exe` 即可运行
2. 首次运行会在程序所在目录创建 `data/`、`config/`、`logs/` 目录
3. 首次运行自动弹出配置向导

**macOS**：
1. 打开 `stock-arm.app` 或在终端运行 CLI 版本
2. 首次运行可能需要在"系统偏好设置 > 安全性与隐私"中允许运行
3. 配置和数据目录与 Windows 相同

---

## 第三部分：配置详解

### .env 配置文件逐项说明

#### LLM 配置

```env
STOCK_ARM_LLM_API_KEY=sk-xxx           # 主 LLM API Key（必填）
STOCK_ARM_LLM_PRIMARY_MODEL=deepseek-chat  # 主模型，用于核心分析任务
STOCK_ARM_LLM_FAST_MODEL=glm-4-flash      # 快速模型，用于批量轻量任务（新闻分类、简要摘要等）
STOCK_ARM_LLM_DAILY_TOKEN_LIMIT=500000     # 每日 Token 预算，0 表示不限
```

支持的 LLM 提供商和模型：

| 提供商 | 模型示例 | 适用场景 |
|--------|---------|---------|
| OpenAI | gpt-4o, gpt-4o-mini | 综合分析 |
| Anthropic | claude-sonnet-4-20250514 | 深度推理 |
| DeepSeek | deepseek-chat, deepseek-reasoner | 高性价比 |
| 通义千问 (Qwen) | qwen-plus, qwen-max | 中文优化 |
| MiniMax | abab6.5s, abab7 | 中文长文本处理 |
| 智谱 AI (Zhipu) | glm-4-plus, glm-4-flash | 中文综合分析 |

#### 数据源配置

```env
STOCK_ARM_DATA_TUSHARE_TOKEN=           # Tushare Pro Token（可选，有免费额度限制）
STOCK_ARM_DATA_CONNECT_TIMEOUT=5        # 数据源连接超时（秒）
STOCK_ARM_DATA_READ_TIMEOUT=30          # 数据源读取超时（秒）
STOCK_ARM_DATA_MAX_RETRIES=3            # 数据拉取最大重试次数
```

A股数据源优先级链：

| 优先级 | 数据源 | 能力 | 需要 Token |
|--------|--------|------|-----------|
| 0 | efinance | 实时行情、K线、板块排行 | 否 |
| 0 | Tushare Pro | 行情、财务、宏观、分红 | 是 |
| 1 | AkShare | 行情、宏观指标、板块、资金流 | 否 |
| 2 | pytdx (TDX) | 实时行情、K线 | 否 |
| 3 | Baostock | 历史K线、基本面 | 否 |

#### 网络配置

```env
STOCK_ARM_NET_PROXY=                    # 代理地址，如 socks5://127.0.0.1:1080
```

#### 运行时配置

```env
STOCK_ARM_RUNTIME_ENV=auto              # auto | cloud | docker | local
                                        # auto: 自动检测运行环境
STOCK_ARM_DATA_DIR=                     # 数据目录覆盖（默认: ./data）
STOCK_ARM_LOG_LEVEL=INFO                # 日志级别: DEBUG | INFO | WARNING | ERROR
STOCK_ARM_LOG_TO_STDOUT=false           # 是否同时输出到 stdout（cloud/docker 自动开启）
STOCK_ARM_BIND_HOST=127.0.0.1          # 绑定地址（cloud/docker 自动切换为 0.0.0.0）
STOCK_ARM_PORT=8000                     # 服务端口
```

#### 调度器配置

```env
STOCK_ARM_SCHEDULER_ENABLED=true        # 是否启用调度器
STOCK_ARM_SCHEDULE_DAILY_ANALYSIS=18:00 # 每日个股分析时间
STOCK_ARM_SCHEDULE_DAILY_MACRO=18:30    # 每日宏观数据拉取时间
STOCK_ARM_SCHEDULE_DAILY_BRIEFING=19:00 # 每日国际金融简报时间
STOCK_ARM_SCHEDULE_EARNINGS_SCAN=20:00  # 财报季扫描时间
STOCK_ARM_SCHEDULE_MONTHLY_REPORT=09:00 # 月度报告生成时间
STOCK_ARM_TRADING_DAY_CHECK=true        # 非交易日跳过（推荐开启）
STOCK_ARM_DATA_RETENTION_DAYS=90        # 自动清理超过 N 天的旧数据
STOCK_ARM_CLEANUP_CRON=0 3 1 * *        # 清理计划（每月1日凌晨3点）
```

#### 云端模式配置

```env
# 仅当 RUNTIME_ENV=cloud 时生效
STOCK_ARM_AUTH_ENABLED=false            # 启用 Web UI 密码认证
STOCK_ARM_AUTH_USERNAME=admin           # 认证用户名
STOCK_ARM_AUTH_PASSWORD=                # 认证密码（启用认证时必填）
STOCK_ARM_SSL_CERT_PATH=               # SSL 证书路径（可选，推荐用反向代理）
STOCK_ARM_SSL_KEY_PATH=                # SSL 私钥路径
STOCK_ARM_BACKUP_ENABLED=false         # 定时数据库备份
STOCK_ARM_BACKUP_PATH=                 # 备份目标目录
STOCK_ARM_BACKUP_CRON=0 3 * * *        # 备份计划（cron 格式）
```

#### 推送通知配置

```env
# 企业微信
STOCK_ARM_WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# 飞书
STOCK_ARM_FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 邮件
STOCK_ARM_EMAIL_SMTP_HOST=smtp.example.com
STOCK_ARM_EMAIL_SMTP_PORT=465
STOCK_ARM_EMAIL_SENDER=user@example.com
STOCK_ARM_EMAIL_PASSWORD=xxx
STOCK_ARM_EMAIL_RECEIVERS=user1@example.com,user2@example.com

# 自定义 Webhook
STOCK_ARM_CUSTOM_WEBHOOK_URLS=https://hook1.example.com,https://hook2.example.com

# 推送时间
STOCK_ARM_PUSH_SCHEDULE_TIME=18:00     # 定时推送时间
STOCK_ARM_PUSH_SILENT_START=22:00      # 免打扰开始时间
STOCK_ARM_PUSH_SILENT_END=08:00        # 免打扰结束时间
STOCK_ARM_EVENT_PUSH_DAILY_LIMIT=10    # 每日事件推送上限（防刷屏）
```

### config.yaml 高级配置

`config.yaml` 用于更细粒度的配置，如 LLM 回退链、分析参数等：

```yaml
# config.yaml 示例
llm:
  primary: "deepseek-chat"         # 主模型
  fast: "glm-4-flash"             # 快速模型
  fallback_chain:                  # 回退链：主模型失败后依次尝试
    - "qwen-plus"
    - "gpt-4o-mini"
  temperature: 0.3                 # LLM 温度参数
  max_tokens: 4096                 # 最大输出 Token
  timeout: 60                      # 单次调用超时（秒）

analysis:
  earnings_scan_scope: "watchlist"  # watchlist | all
  earnings_auto_deep: false        # 是否自动触发深度分析
```

### 优先级链说明

配置值的加载遵循以下优先级（从高到低）：

```
环境变量 > .env 文件 > config.yaml > 代码默认值
```

例如：
- 在 `.env` 中设置了 `STOCK_ARM_PORT=9000`
- 在 `config.yaml` 中没有设置端口
- 代码默认端口为 `8000`
- 则最终使用端口 `9000`

如果在命令行中设置了环境变量：
```bash
STOCK_ARM_PORT=7000 python main.py --webui
```
则端口为 `7000`，覆盖 `.env` 中的值。

### 敏感信息保护

- 所有密钥、密码等敏感信息仅通过 `.env` 文件或环境变量传入
- `.env` 文件已在 `.gitignore` 中，不会被提交到版本控制
- 配置系统内部使用 Pydantic 的 `SecretStr` 类型处理密码字段，避免意外日志泄露
- 切勿在 `config.yaml` 中存放 API Key 或密码

---

## 第四部分：功能使用指南

### 4.1 自选股管理

#### 创建分组

支持创建多个自选股分组，如"长期持有"、"短线观察"、"板块追踪"等。

```bash
# 创建自选股分组
curl -X POST http://localhost:8000/api/v1/watchlists \
  -H "Content-Type: application/json" \
  -d '{
    "name": "长期持有",
    "description": "核心仓位，长期跟踪"
  }'

# 响应
{
  "code": 0,
  "data": {
    "id": 1,
    "name": "长期持有",
    "description": "核心仓位，长期跟踪",
    "created_at": "2026-03-30T10:00:00Z"
  },
  "message": "ok"
}
```

#### 删除分组

```bash
curl -X DELETE http://localhost:8000/api/v1/watchlists/1
```

#### 添加股票到分组

```bash
# 添加单只股票
curl -X POST http://localhost:8000/api/v1/watchlists/1/stocks \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "600519",
    "stock_name": "贵州茅台"
  }'

# 批量添加
curl -X POST http://localhost:8000/api/v1/watchlists/1/stocks/batch \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": [
      {"stock_code": "600519", "stock_name": "贵州茅台"},
      {"stock_code": "000858", "stock_name": "五粮液"},
      {"stock_code": "600036", "stock_name": "招商银行"}
    ]
  }'
```

#### 移除股票

```bash
curl -X DELETE http://localhost:8000/api/v1/watchlists/1/stocks/600519
```

#### 手动触发分析

```bash
# 触发指定分组的分析
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"watchlist_id": 1}'

# 响应（异步任务）
{
  "code": 0,
  "data": {
    "task_id": "abc-123"
  },
  "message": "Task started"
}

# 查询分析进度
curl http://localhost:8000/api/v1/analysis/tasks/abc-123

# 响应
{
  "code": 0,
  "data": {
    "status": "running",
    "progress": 45
  },
  "message": "ok"
}
```

#### 查看分析结果

```bash
# 查看某只股票最新分析结果
curl http://localhost:8000/api/v1/stocks/600519/analysis

# 查看指定日期的分析结果
curl http://localhost:8000/api/v1/stocks/600519/analysis?date=2026-03-28
```

---

### 4.2 每日分析报告

#### 自动分析流程

每日分析按以下维度对自选股逐一进行全面分析：

| 维度 | 内容 | 数据来源 |
|------|------|---------|
| 技术面 | 均线趋势、MACD、RSI、量价关系、支撑/阻力位 | DataFetcherManager（实时拉取，不存储） |
| 基本面 | PE/PB/ROE、最新财务数据摘要 | DataFetcherManager（实时拉取） |
| 新闻面 | 相关新闻、公告、研报摘要 | 新闻/舆情数据源（摘要后丢弃原文） |
| 资金面 | 主力资金流向、筹码分布（可选） | DataFetcherManager（实时拉取） |
| LLM 综合 | 多空研判、关键风险提示、操作建议 | LLM Provider |
| 变化追踪 | 与前一交易日的信号对比变化 | 数据库（历史分析结果） |

#### 分析结果结构

每只股票产出结构化分析结果：

```
StockAnalysisResult:
  - stock_code: str          # 股票代码
  - stock_name: str          # 股票名称
  - analysis_date: date      # 分析日期
  - technical_summary:       # 技术面摘要
      TechnicalSummary
  - fundamental_summary:     # 基本面摘要
      FundamentalSummary
  - news_summary:            # 新闻面摘要
      NewsSummary
  - capital_flow:            # 资金面摘要（可选）
      CapitalFlowSummary | None
  - llm_verdict:             # LLM 综合研判
      LLMVerdict
  - signal_changes:          # 信号变化列表
      list[SignalChange]
```

#### 信号变化追踪

系统自动对比前一交易日的分析结果，追踪以下信号变化：
- 技术指标信号变化（如 MACD 金叉/死叉）
- 资金流向变化
- LLM 研判方向变化
- 新出现的风险提示

#### 调度时间配置

```env
# 默认每交易日 18:00 自动触发
STOCK_ARM_SCHEDULE_DAILY_ANALYSIS=18:00
```

---

### 4.3 宏观数据追踪

#### 跟踪的核心指标

| 类别 | 指标 | 更新频率 | 数据来源 |
|------|------|---------|---------|
| 价格 | CPI、PPI | 每月 | AkShare / Tushare |
| 货币 | M1、M2、社会融资规模 | 每月 | AkShare |
| 利率 | LPR、Shibor、国债收益率（10Y/1Y） | 每日/每月 | AkShare |
| 市场 | 股权风险溢价（= 1/A股PE - 10Y国债） | 每日 | 计算值 |
| 市场 | 融资融券余额 | 每日 | AkShare |
| 市场 | 北向资金净流入 | 每日 | AkShare / efinance |
| 市场 | 沪深港通额度使用率 | 每日 | AkShare |
| 国际 | 美联储利率决议、非农就业、美国CPI | 事件驱动 | 财经日历 API |
| 大宗商品 | 原油（WTI/Brent）、黄金、铜 | 每日 | AkShare / yfinance |

#### 数据更新频率

- 日度指标：每个交易日收盘后拉取（默认 18:30）
- 月度指标：在数据发布日拉取（通常每月 10-15 日）
- 事件驱动指标：每日轮询财经日历，在事件日触发
- 所有指标均显示"最后更新时间"

#### LLM 宏观分析

系统拉取最新宏观数据后，会调用 LLM 进行综合分析，产出内容包括：
- 当前数据的市场含义
- 与预期值/前值的对比分析
- 对 A 股市场的潜在影响判断
- 需要关注的风险点

```bash
# 查看最新宏观数据
curl http://localhost:8000/api/v1/macro-data

# 手动触发宏观数据拉取
curl -X POST http://localhost:8000/api/v1/macro-data/refresh
```

---

### 4.4 财报处理

#### 财报季自动扫描

系统在财报季（4月/8月/10月）自动扫描新发布的财报：

- **4月**：年报 + 一季报（高频期）
- **8月**：半年报
- **10月**：三季报

#### 处理流程

```
1. 每日扫描新发布的财报
   数据来源：AkShare / 东方财富
   范围：自选股 或 全部A股（可配置）

2. LLM 生成财报摘要：
   - 核心业务构成及变化
   - 关键财务指标：营收、净利润、扣非净利润、毛利率、净利率、经营性现金流
   - 同比/环比变化趋势
   - 亮点与风险提示

3. 摘要存储为 Markdown 文件：
   data/earnings/<日期>/<股票代码>_summary.md

4. 用户标记"感兴趣"的报告：
   - 触发深度分析（细分业务、同业对比、估值）
   - 可按需转发原始文档到邮件/企业微信/飞书
   - 原始文档不在本地存储
```

#### LLM 摘要生成

```bash
# 查看财报摘要列表
curl http://localhost:8000/api/v1/earnings?date=2026-04-28

# 查看单只股票财报摘要
curl http://localhost:8000/api/v1/stocks/600519/earnings/latest
```

#### 手动触发深度分析

```bash
# 触发深度财报分析
curl -X POST http://localhost:8000/api/v1/earnings/600519/deep-analysis

# 转发原始文档（按需拉取，不本地存储）
curl -X POST http://localhost:8000/api/v1/earnings/600519/forward \
  -H "Content-Type: application/json" \
  -d '{"channel": "email"}'
```

#### 配置项

```env
STOCK_ARM_EARNINGS_SCAN_SCOPE=watchlist   # watchlist（仅自选股）| all（全A股）
STOCK_ARM_EARNINGS_AUTO_DEEP_ANALYSIS=false  # 是否自动触发深度分析（默认手动）
```

---

### 4.5 国际金融简报

#### 每日隔夜市场摘要

系统每日自动生成国际金融简报，内容涵盖：

**跟踪的海外指数：**
- 美股：道琼斯、标普500、纳斯达克
- 港股：恒生指数、恒生科技指数

**跟踪的事件类型：**
- 美联储/欧央行政策决议和讲话
- 地缘政治动态（中美关系、地区冲突）
- 大宗商品异动（原油、黄金急涨急跌）
- 全球重大经济事件日历

#### 简报输出格式

```markdown
# 国际金融简报 - 2026-03-30

## 隔夜市场概况
- 美股: [指数涨跌、关键个股、市场叙事]
- 港股: [指数涨跌、关键个股]

## 关键事件及 A 股影响
- 事件1: [描述] → A股潜在影响: [分析]
- 事件2: ...

## 未来 7 天重要事件
- 2026-03-31: <事件描述>
- 2026-04-02: <事件描述>
- ...
```

简报存储位置：`data/briefings/<日期>_international.md`

#### 事件影响分析

LLM 会对每个重大事件分析其对 A 股的潜在影响，包括：
- 受影响的板块和个股
- 影响方向（利好/利空/中性）
- 影响程度评估

#### 未来 7 天日程

系统自动整理未来 7 天全球重大经济事件日程，包括：
- 各国央行利率决议
- 重要经济数据发布（非农、CPI、PMI 等）
- 大型 IPO 或重要公司财报
- 重大政策会议

```bash
# 查看最新国际金融简报
curl http://localhost:8000/api/v1/briefings/latest

# 查看指定日期的简报
curl http://localhost:8000/api/v1/briefings/2026-03-30

# 手动触发简报生成
curl -X POST http://localhost:8000/api/v1/briefings/generate
```

---

### 4.6 研报管理

#### 研报筛选

支持按行业、个股、评级等维度筛选研报：

```bash
# 按股票筛选研报
curl "http://localhost:8000/api/v1/research-reports?stock_code=600519"

# 按行业筛选
curl "http://localhost:8000/api/v1/research-reports?industry=白酒"

# 按评级筛选
curl "http://localhost:8000/api/v1/research-reports?rating=Buy"

# 分页
curl "http://localhost:8000/api/v1/research-reports?page=1&page_size=20"
```

数据来源：
- 东方财富研报中心
- 券商 App API（如有）
- Longbridge 研报（港美股）

#### LLM 摘要

每份研报自动生成 LLM 摘要，包含以下信息：

```
ResearchReportSummary:
  - title: str              # 研报标题
  - broker: str             # 券商名称
  - analyst: str            # 分析师
  - publish_date: date      # 发布日期
  - target_stock: str       # 目标股票
  - rating: str             # 评级（买入/增持/持有/减持/卖出）
  - target_price: float     # 目标价（如有）
  - core_thesis: str        # 核心观点（1-2句摘要）
  - key_logic: list[str]    # 推理逻辑链
  - risk_factors: list[str] # 风险因素
  - previous_rating: str    # 此前评级（用于变化追踪）
```

仅存储 LLM 摘要，不存储原始研报文档。用户可按需转发原始文档到通知渠道。

#### 评级变化追踪

系统自动追踪同一股票在不同券商间的评级变化，例如：
- 某券商从"增持"上调至"买入"
- 多家券商集体下调评级

```bash
# 查看某只股票的评级变化历史
curl "http://localhost:8000/api/v1/stocks/600519/rating-changes"
```

---

### 4.7 推送通知

#### 支持的渠道

| 渠道 | 适用场景 | 格式支持 |
|------|---------|---------|
| 企业微信 Webhook | 企业内网用户 | Markdown |
| 飞书 Webhook | 飞书用户 | 富文本、卡片 |
| 邮件 (SMTP) | 详细报告投递 | HTML、附件 |
| 自定义 Webhook | 与任意系统集成 | JSON |

#### 配置方法

**企业微信：**
1. 在企业微信群中添加"群机器人"
2. 获取 Webhook URL
3. 设置环境变量：
```env
STOCK_ARM_WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key
```

**飞书：**
1. 在飞书群中添加"自定义机器人"
2. 获取 Webhook URL
3. 设置环境变量：
```env
STOCK_ARM_FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的hook
```

**邮件：**
```env
STOCK_ARM_EMAIL_SMTP_HOST=smtp.qq.com    # SMTP 服务器
STOCK_ARM_EMAIL_SMTP_PORT=465            # SMTP 端口（SSL）
STOCK_ARM_EMAIL_SENDER=your@qq.com       # 发件人邮箱
STOCK_ARM_EMAIL_PASSWORD=授权码           # SMTP 授权码（非登录密码）
STOCK_ARM_EMAIL_RECEIVERS=user1@example.com,user2@example.com  # 收件人列表
```

**自定义 Webhook：**
```env
STOCK_ARM_CUSTOM_WEBHOOK_URLS=https://hook1.example.com,https://hook2.example.com
```

#### 推送策略

**定时推送：**
- 默认每个交易日收盘后（18:00 北京时间）发送完整分析报告
- 内容包含：所有自选股分析 + 宏观数据摘要 + 国际金融简报
- 配置：`STOCK_ARM_PUSH_SCHEDULE_TIME=18:00`
- 交易日检查：`STOCK_ARM_TRADING_DAY_CHECK=true`（非交易日跳过）

**事件推送：**
- 触发条件：重大新闻、异常价格波动、财报发布
- 内容：简要提醒，包含关键信息
- 防刷屏：每日每渠道最多 10 条事件推送
- 配置：`STOCK_ARM_EVENT_PUSH_DAILY_LIMIT=10`

**免打扰时段：**
- 默认 22:00-08:00 不发送非紧急推送
- 紧急提醒（如指数跌幅超过 5%）可穿透免打扰
- 配置：
```env
STOCK_ARM_PUSH_SILENT_START=22:00
STOCK_ARM_PUSH_SILENT_END=08:00
```

**内容分级：**

| 级别 | 渠道 | 内容 |
|------|------|------|
| 摘要 | 企业微信/飞书 Bot | 关键信号，每只股票 1-2 句 |
| 标准 | Web UI | 完整分析结果 |
| 详细 | 邮件 | 完整报告含附件 |

#### 本地模式 catch-up 不推送规则

**重要**：本地模式下的 catch-up（补录）任务执行结果只在 Web UI 中展示，**绝不会触发推送通知**，以避免历史数据刷屏。

| 场景 | 云端/Docker (7x24) | 本地（按需启动） |
|------|--------------------|--------------------|
| 每日定时推送 | 在 cron 时间自动推送 | 启动时检查今日是否已推送，未推送则推送 |
| 事件提醒 | 实时推送 | 仅在程序运行期间推送 |
| 月度报告 | 自动生成并推送 | 启动时检查本月报告是否存在 |
| 补录数据 | 不适用（从不错过） | 仅存入 Web UI 展示，**不推送** |

---

## 第五部分：API 参考

### 统一响应格式

所有 API 端点返回统一的 JSON 格式：

**成功响应：**
```json
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}
```

**错误响应：**
```json
{
  "code": 2001,
  "data": null,
  "message": "AkShare 数据源超时: 连接 api.akshare.com 超时 (5s)"
}
```

### 错误码表

| 错误码范围 | 类别 | 示例 |
|-----------|------|------|
| 0 | 成功 | -- |
| 1xxx | 客户端错误 | 1001=参数无效, 1002=缺少必填字段, 1003=资源未找到 |
| 2xxx | 数据源错误 | 2001=数据源超时, 2002=数据源不可用, 2003=数据格式错误 |
| 3xxx | LLM 错误 | 3001=LLM 超时, 3002=LLM 频率限制, 3003=LLM 响应无效 |
| 4xxx | 系统错误 | 4001=数据库错误, 4002=配置错误, 4003=内部错误 |

### 完整路由列表

#### 系统

```bash
# 健康检查
curl http://localhost:8000/api/v1/health
# {"code": 0, "data": {"status": "healthy", "uptime": 3600}, "message": "ok"}
```

#### 自选股管理

```bash
# 获取所有自选股分组
curl http://localhost:8000/api/v1/watchlists

# 创建分组
curl -X POST http://localhost:8000/api/v1/watchlists \
  -H "Content-Type: application/json" \
  -d '{"name": "短线观察", "description": "短期操作标的"}'

# 获取分组详情
curl http://localhost:8000/api/v1/watchlists/1

# 更新分组
curl -X PUT http://localhost:8000/api/v1/watchlists/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "核心持仓", "description": "长期核心仓位"}'

# 删除分组
curl -X DELETE http://localhost:8000/api/v1/watchlists/1

# 获取分组中的股票列表
curl http://localhost:8000/api/v1/watchlists/1/stocks

# 添加股票到分组
curl -X POST http://localhost:8000/api/v1/watchlists/1/stocks \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "600519", "stock_name": "贵州茅台"}'

# 从分组移除股票
curl -X DELETE http://localhost:8000/api/v1/watchlists/1/stocks/600519
```

#### 分析

```bash
# 触发分析（异步）
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"watchlist_id": 1}'

# 查询分析任务状态
curl http://localhost:8000/api/v1/analysis/tasks/abc-123

# SSE 实时进度流
curl http://localhost:8000/api/v1/analysis/tasks/abc-123/stream

# 获取股票分析结果
curl http://localhost:8000/api/v1/stocks/600519/analysis

# 获取指定日期的分析结果
curl "http://localhost:8000/api/v1/stocks/600519/analysis?date=2026-03-28"
```

#### 宏观数据

```bash
# 获取最新宏观数据
curl http://localhost:8000/api/v1/macro-data

# 手动刷新宏观数据
curl -X POST http://localhost:8000/api/v1/macro-data/refresh
```

#### 财报

```bash
# 获取财报摘要列表
curl "http://localhost:8000/api/v1/earnings?date=2026-04-28"

# 获取某只股票最新财报摘要
curl http://localhost:8000/api/v1/stocks/600519/earnings/latest

# 触发深度分析
curl -X POST http://localhost:8000/api/v1/earnings/600519/deep-analysis

# 转发原始文档
curl -X POST http://localhost:8000/api/v1/earnings/600519/forward \
  -H "Content-Type: application/json" \
  -d '{"channel": "email"}'
```

#### 国际金融简报

```bash
# 获取最新简报
curl http://localhost:8000/api/v1/briefings/latest

# 获取指定日期简报
curl http://localhost:8000/api/v1/briefings/2026-03-30

# 手动触发简报生成
curl -X POST http://localhost:8000/api/v1/briefings/generate
```

#### 研报

```bash
# 查询研报（支持筛选和分页）
curl "http://localhost:8000/api/v1/research-reports?stock_code=600519&page=1&page_size=20"

# 获取股票评级变化
curl http://localhost:8000/api/v1/stocks/600519/rating-changes
```

### Swagger UI 访问

FastAPI 自动生成交互式 API 文档，访问：

```
http://localhost:8000/docs          # Swagger UI
http://localhost:8000/redoc         # ReDoc（备用文档界面）
```

在 Swagger UI 中可以直接测试所有 API 端点。

### 分页参数说明

所有列表接口支持统一的分页参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `page` | int | 1 | 页码，从 1 开始 |
| `page_size` | int | 20 | 每页条数，最大 100 |

分页响应格式：

```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  },
  "message": "ok"
}
```

---

## 第六部分：运维与故障排除

### 日志位置和级别

**日志文件位置：**

| 部署模式 | 日志路径 | 输出方式 |
|---------|---------|---------|
| 本地 | `./logs/stock-arm.log` | 仅文件 |
| 云端 | `./logs/stock-arm.log` | 文件 + stdout |
| Docker | `/app/logs/stock-arm.log`（挂载至 `./logs/`） | 文件 + stdout |

**日志级别配置：**

```env
STOCK_ARM_LOG_LEVEL=INFO    # DEBUG | INFO | WARNING | ERROR
```

- `DEBUG`：详细调试信息，包括 API 调用详情、LLM 输入输出
- `INFO`：常规运行信息（推荐生产使用）
- `WARNING`：潜在问题警告
- `ERROR`：错误信息

**查看日志：**

```bash
# 本地模式
tail -f logs/stock-arm.log

# 云端 systemd
sudo journalctl -u stock-arm -f

# Docker
docker compose logs -f
```

### 常见错误及解决方案

#### LLM 相关

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `3001: LLM 超时` | LLM API 响应慢或网络问题 | 检查网络连接；配置代理 `STOCK_ARM_NET_PROXY`；检查 LLM 服务商状态 |
| `3002: LLM 频率限制` | API 调用频率过高 | 降低并发分析数量；升级 API 套餐；等待限制重置 |
| `3003: LLM 响应无效` | LLM 返回了无法解析的内容 | 检查日志中的原始响应；更换模型；重试 |
| Token 预算耗尽 | 当日 Token 使用超过限制 | 调大 `STOCK_ARM_LLM_DAILY_TOKEN_LIMIT`；等待次日重置 |

#### 数据源相关

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `2001: 数据源超时` | 数据接口不可达 | 检查网络；配置代理；增大 `STOCK_ARM_DATA_CONNECT_TIMEOUT` |
| `2002: 数据源不可用` | 所有数据源均失败 | 检查各数据源服务状态；查看日志中的详细错误信息 |
| `2003: 数据格式错误` | 数据源返回格式发生变更 | 更新依赖 `pip install -U akshare`；提交 issue |
| Tushare 限频 | 免费额度受限 | 减少调用频率；升级 Tushare 会员；使用其他数据源 |

#### 系统相关

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `4001: 数据库错误` | SQLite 文件损坏或锁定 | 检查磁盘空间；确认无其他进程锁定数据库文件 |
| `4002: 配置错误` | .env 配置项格式错误 | 对照 `.env.example` 检查配置格式 |
| 端口被占用 | 其他服务使用了相同端口 | 修改 `STOCK_ARM_PORT` 或关闭占用端口的进程 |
| Python 版本不兼容 | Python < 3.11 | 升级 Python 到 3.11+；使用 pyenv 管理版本 |

### 数据备份与恢复

#### 备份

```bash
# 手动备份（推荐在服务停止或低负载时执行）
cp data/stock_arm.db data/stock_arm_backup_$(date +%Y%m%d).db

# 备份整个数据目录
tar -czf stock-arm-data-$(date +%Y%m%d).tar.gz data/

# 远程备份（scp 到另一台服务器）
scp data/stock_arm.db backup-server:/backup/stock-arm/
```

#### 恢复

```bash
# 停止服务
sudo systemctl stop stock-arm

# 恢复数据库
cp /backup/stock-arm/stock_arm_20260328.db data/stock_arm.db

# 启动服务
sudo systemctl start stock-arm
```

#### 自动备份（已内置）

启用内置备份功能后，系统会按照 cron 计划自动备份：

```env
STOCK_ARM_BACKUP_ENABLED=true
STOCK_ARM_BACKUP_PATH=/backup/stock-arm/
STOCK_ARM_BACKUP_CRON=0 3 * * *    # 每天凌晨 3 点
```

### 升级流程

```bash
# 1. 备份当前数据
cp data/stock_arm.db data/stock_arm_before_upgrade.db

# 2. 拉取最新代码
cd /opt/stock-arm
git pull origin main

# 3. 更新 Python 依赖
source .venv/bin/activate
pip install -r requirements.txt

# 4. 运行数据库迁移
alembic upgrade head

# 5. 重启服务
sudo systemctl restart stock-arm

# 6. 检查服务状态
sudo systemctl status stock-arm
curl http://localhost:8000/api/v1/health
```

**Docker 环境升级：**

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建并启动
docker compose up -d --build

# 3. 检查服务状态
docker compose ps
curl http://localhost:8000/api/v1/health
```

### 性能调优建议

#### 调度器优化

- 避免多个任务在同一时间点触发，错开调度时间（默认配置已错开 30 分钟）
- 自选股数量较多时（>50只），考虑增加分析间隔或分批执行
- 合理设置 `STOCK_ARM_DATA_RETENTION_DAYS` 避免数据库过大

#### LLM 调用优化

- 批量轻量任务使用快速模型（`glm-4-flash`），降低延迟和成本
- 设置合理的 Token 预算，避免意外超支
- 配置回退链，确保主模型不可用时自动降级

#### 数据库优化

- SQLite 默认使用 WAL 模式，支持并发读取
- 定期运行数据清理（系统每月自动执行）
- 数据库文件建议放在 SSD 上以获得更好的性能
- 如果数据库文件过大（>1GB），可手动执行 `VACUUM`：
```bash
sqlite3 data/stock_arm.db "VACUUM;"
```

#### 网络优化

- 数据源连接超时建议设置为 5-10 秒
- 如果需要访问海外数据源（yfinance 等），配置代理 `STOCK_ARM_NET_PROXY`
- 数据拉取失败时系统会自动重试（默认 3 次），无需手动干预
