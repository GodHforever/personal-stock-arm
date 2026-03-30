# Stage 1: 前端构建（Layer 5 时启用）
# FROM node:20-alpine AS frontend
# WORKDIR /app/web
# COPY web/package*.json ./
# RUN npm ci
# COPY web/ ./
# RUN npm run build

# Stage 2: Python 运行时
FROM python:3.11.9-slim AS runtime

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY src/ ./src/
COPY main.py ./
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 前端静态文件（Layer 5 时启用）
# COPY --from=frontend /app/web/dist ./web/dist

# 运行时配置
ENV STOCK_ARM_RUNTIME_ENV=docker
ENV STOCK_ARM_BIND_HOST=0.0.0.0
ENV STOCK_ARM_PORT=8000
ENV STOCK_ARM_LOG_TO_STDOUT=true

EXPOSE 8000

# 数据持久化挂载点
VOLUME ["/app/data", "/app/config", "/app/logs"]

CMD ["python", "main.py", "--daemon"]
