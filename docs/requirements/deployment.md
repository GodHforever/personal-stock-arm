# Deployment Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Target Platforms

**Supported**: Windows, macOS, Linux

**Running Modes**: Local / Cloud (VPS) / Docker

| Platform | Method | Command/Action | Use Case |
|----------|--------|---------------|----------|
| Windows | Executable | Double-click `stock-arm.exe` | End user, no Python needed |
| Windows | Python | `python main.py --webui` | Development |
| macOS | Executable | `stock-arm.app` or CLI | End user |
| macOS | Python | `python main.py --webui` | Development |
| Linux | Python | `python main.py --webui` | Local use |
| Linux (VPS) | Daemon | `python main.py --daemon` or systemd | Cloud 7×24 deployment |
| All platforms | Docker | `docker-compose up` | Isolated environment |

---

## 2. Executable Packaging

### Build Tools
- **Primary**: PyInstaller (proven ecosystem, cross-platform)
- **Alternative**: Nuitka (if PyInstaller encounters issues)

### Build Process
```
build/
├── build_windows.py    # Windows build script
├── build_macos.py      # macOS build script
├── stock-arm.spec      # PyInstaller spec file
└── assets/             # Icons, splash screens
```

### Build Requirements
- Frontend pre-built to static files, embedded in the executable
- Single-file executable (PyInstaller `--onefile`)
- Startup behavior identical to `python main.py --webui` (launch server + open browser)
- Major version updates require validation of packaging artifacts on both platforms

---

## 3. One-Click Startup

### First Run (`python main.py`)
```
1. Detect Python version ≥ 3.11 → error if not met
2. Check/install dependencies (pip install -r requirements.txt)
3. Initialize SQLite database (run Alembic migrations)
4. Launch config wizard if .env not found:
   - Prompt for LLM API key (required)
   - Prompt for data source tokens (optional)
   - Prompt for notification channel config (optional)
   - Save to .env
5. Start FastAPI server + TaskScheduler
6. Open browser to http://localhost:<PORT> (local mode only)
```

### Config Files
- `.env` or `config.yaml` — user configuration
- `.env.example` — template with comments explaining each setting
- Environment variables override file-based config

---

## 4. Cloud Deployment (VPS)

### Overview

Cloud mode enables 7×24 unattended operation on a personal VPS. Compared to local mode, it adds:

| Requirement | Reason | Solution |
|-------------|--------|----------|
| Authentication | VPS exposed to public network | Username + password login page |
| HTTPS | Encrypt credentials and data in transit | Configurable SSL cert path, or reverse proxy (Nginx/Caddy) |
| Daemon process | Must survive SSH disconnect | systemd service file + `--daemon` flag |
| Health monitoring | User not at terminal | `/api/v1/health` endpoint + status page |
| Data backup | VPS may fail, need recovery | Configurable scheduled backup to specified path |
| Bind address | External access needed | Default `0.0.0.0` |

### Daemon Mode

```bash
# Option 1: built-in daemon
python main.py --daemon

# Option 2: systemd (recommended for production)
sudo cp deploy/stock-arm.service /etc/systemd/system/
sudo systemctl enable stock-arm
sudo systemctl start stock-arm
```

### systemd Service File (`deploy/stock-arm.service`)
```ini
[Unit]
Description=Stock-ARM Financial Analysis Service
After=network.target

[Service]
Type=simple
User=<username>
WorkingDirectory=/path/to/personal-stock-arm
ExecStart=/usr/bin/python3 main.py --daemon
Restart=on-failure
RestartSec=10
EnvironmentFile=/path/to/personal-stock-arm/.env

[Install]
WantedBy=multi-user.target
```

### Cloud Configuration
```env
STOCK_ARM_RUNTIME_ENV=cloud
STOCK_ARM_AUTH_ENABLED=true
STOCK_ARM_AUTH_USERNAME=admin
STOCK_ARM_AUTH_PASSWORD=<strong-password>
STOCK_ARM_SSL_CERT_PATH=              # Optional, leave empty for HTTP
STOCK_ARM_SSL_KEY_PATH=               # Optional
STOCK_ARM_BACKUP_ENABLED=false        # Optional scheduled backup
STOCK_ARM_BACKUP_PATH=/backup/stock-arm/
STOCK_ARM_BACKUP_CRON=0 3 * * *       # Daily 3:00 AM backup
```

---

## 5. Task Scheduler

### Architecture

The project uses a unified **TaskScheduler** (based on APScheduler) that adapts behavior based on runtime mode.

```
┌─────────────────────────────────────────────┐
│              TaskScheduler                   │
│                                             │
│  Registered Tasks:                           │
│    daily_analysis    Daily 18:00             │
│    daily_macro       Daily 18:30             │
│    daily_briefing    Daily 19:00             │
│    earnings_scan     Earnings season 20:00   │
│    monthly_report    1st of month 09:00      │
│    data_cleanup      1st of month 03:00      │
│                                             │
│  Adapts to runtime mode:                     │
│    cloud/docker → continuous scheduling      │
│    local        → catch-up + live scheduling │
└─────────────────────────────────────────────┘
```

### Cloud/Docker Mode Scheduling

```
Service start → Scheduler runs continuously → Triggers at cron time → Execute → Push
                       ↑
                  7×24, no catch-up needed
```

### Local Mode Scheduling

```
User starts program
  │
  ├── 1. Read last_run_time from database
  │     ├── Today's tasks not yet executed → Auto-run due tasks
  │     └── Today's tasks already done → Skip
  │
  ├── 2. Register remaining tasks for today
  │     └── Will trigger if program is still running at scheduled time
  │
  ├── 3. Web UI shows "Catch-up" entry
  │     └── User can manually select date range to backfill
  │     └── Backfill results stored and displayed in Web only, NOT pushed
  │
  └── 4. User closes program
        └── Record last_run_time, scheduler stops
```

### Push Behavior Differences

| Scenario | Cloud | Local |
|----------|-------|-------|
| Daily scheduled push | Auto-push at scheduled time | Push on startup if today not yet pushed |
| Event alerts | Real-time push | Only during runtime |
| Monthly report | Auto-generate and push monthly | Check on startup if this month's report exists |
| Backfill data | N/A (never missed) | Display in Web only, **never push** |

### Scheduler Configuration

```env
STOCK_ARM_SCHEDULER_ENABLED=true
STOCK_ARM_SCHEDULE_DAILY_ANALYSIS=18:00
STOCK_ARM_SCHEDULE_DAILY_MACRO=18:30
STOCK_ARM_SCHEDULE_DAILY_BRIEFING=19:00
STOCK_ARM_SCHEDULE_EARNINGS_SCAN=20:00
STOCK_ARM_SCHEDULE_MONTHLY_REPORT=09:00
STOCK_ARM_TRADING_DAY_CHECK=true       # Skip non-trading days
STOCK_ARM_DATA_RETENTION_DAYS=90       # Auto-cleanup data older than N days
STOCK_ARM_CLEANUP_CRON=0 3 1 * *       # Cleanup schedule (1st of month, 3:00 AM)
```

---

## 6. Docker Environment

### Role
Docker serves two purposes in this project:
1. **Development environment unification** — consistent env across team members/machines
2. **Optional deployment method** — for users who prefer containerized deployment (behaves like cloud mode for scheduling)

### Container Architecture
```
docker-compose.yml (unified dev/deploy)
  └── app (single container)
        ├── Python backend (FastAPI + TaskScheduler)
        ├── Frontend static files (served by FastAPI StaticFiles)
        └── Volumes:
              ├── ./data:/app/data       # SQLite persistence
              ├── ./config:/app/config   # User config persistence
              ├── ./logs:/app/logs       # Log persistence
              └── ./src:/app/src         # Dev mode: source mount + hot reload
```

### Dockerfile Requirements
- Single `Dockerfile`, multi-stage build:
  - Stage 1: `node:20-alpine` — build frontend to static files
  - Stage 2: `python:3.11.9-slim` — install Python deps + copy frontend build + run
- Base image: pinned version tag (never `latest`)
- Frontend compiled to static files, served by FastAPI (no separate Nginx container)
- `.env` injected via `env_file`, never baked into image

### Development Override
`docker-compose.override.yml`:
- Mount source code for hot reload
- `uvicorn --reload` for backend
- Vite dev server for frontend (if needed)

---

## 7. Environment Detection & Auto-Configuration

### Detection Flow
```
On startup:

1. DETECT RUNTIME MODE
   ├── RUNTIME_ENV=cloud → Cloud mode
   ├── Check /.dockerenv or /proc/1/cgroup → Docker mode
   └── Otherwise → Local mode

   Cloud mode behavior:
     - Data dir: ./data
     - Log: file + stdout
     - No browser launch
     - Bind: 0.0.0.0
     - Auth: enabled (if configured)
     - Scheduler: continuous

   Docker mode behavior:
     - Data dir: /app/data
     - Log: file + stdout
     - No browser launch
     - Bind: 0.0.0.0
     - Scheduler: continuous

   Local mode behavior:
     - Data dir: ./data
     - Log: file only
     - Auto-open browser
     - Bind: 127.0.0.1
     - Scheduler: catch-up + live

2. DETECT LOCAL DOCKER (local mode only)
   ├── docker --version → Docker installed?
   ├── docker compose version → Compose available?
   ├── Check for existing project containers/images
   │     ├── Found → Suggest: "docker-compose up is available"
   │     └── Not found → Continue local mode
   ├── Check Docker config completeness:
   │     ├── Missing .env → Generate from .env.example, prompt user
   │     ├── Missing data/ volume dir → Auto-create
   │     └── Stale image → Suggest: "docker-compose pull"
   └── Print Docker environment status summary

3. DETECT PYTHON ENVIRONMENT (local mode)
   ├── Python version < 3.11 → Error with version requirement
   └── Missing dependencies → Prompt install command or suggest Docker

4. DETECT NETWORK (all modes)
   ├── Probe key data sources (AkShare, Tushare endpoints)
   ├── Probe LLM API endpoint
   └── Unreachable → WARNING log + mark unavailable (don't block startup)
```

### Environment Variables
```env
STOCK_ARM_RUNTIME_ENV=auto       # auto | cloud | docker | local
STOCK_ARM_DATA_DIR=              # Override data directory
STOCK_ARM_LOG_TO_STDOUT=false    # true in cloud/Docker mode
STOCK_ARM_BIND_HOST=127.0.0.1   # 0.0.0.0 in cloud/Docker mode
STOCK_ARM_PORT=8000              # Server port
```
