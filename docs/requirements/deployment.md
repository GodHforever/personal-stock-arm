# Deployment Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Target Platforms

**Supported**: Windows, macOS, Android (via PWA)

| Platform | Method | Command/Action | Use Case |
|----------|--------|---------------|----------|
| Windows | Executable | Double-click `stock-arm.exe` | End user, no Python needed |
| Windows | Python | `python main.py --webui` | Development |
| macOS | Executable | `stock-arm.app` or CLI | End user |
| macOS | Python | `python main.py --webui` | Development |
| Windows/macOS | Docker | `docker-compose up` | Isolated environment |
| Android | PWA | Browser → "Add to Home Screen" | Mobile access |

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
5. Start FastAPI server
6. Open browser to http://localhost:<PORT>
```

### Config Files
- `.env` or `config.yaml` — user configuration
- `.env.example` — template with comments explaining each setting
- Environment variables override file-based config

---

## 4. Docker Environment

### Role
Docker serves two purposes in this project:
1. **Development environment unification** — consistent env across team members/machines
2. **Optional deployment method** — for users who prefer containerized deployment

### Container Architecture
```
docker-compose.yml (unified dev/deploy)
  └── app (single container)
        ├── Python backend (FastAPI + scheduler)
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

## 5. Environment Detection & Auto-Configuration

### Detection Flow
```
On startup:

1. DETECT RUNTIME MODE
   ├── Check /.dockerenv or /proc/1/cgroup → Docker mode
   └── Otherwise → Local mode

   Docker mode behavior:
     - Data dir: /app/data
     - Log: file + stdout (for docker logs)
     - No browser launch
     - Bind: 0.0.0.0

   Local mode behavior:
     - Data dir: ./data
     - Log: file only
     - Auto-open browser
     - Bind: 127.0.0.1

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
STOCK_ARM_RUNTIME_ENV=auto       # auto | docker | local
STOCK_ARM_DATA_DIR=              # Override data directory
STOCK_ARM_LOG_TO_STDOUT=false    # true in Docker mode
STOCK_ARM_BIND_HOST=127.0.0.1   # 0.0.0.0 in Docker mode
STOCK_ARM_PORT=8000              # Server port
```
