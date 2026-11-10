FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先拷依赖声明，让依赖层在改代码时命中缓存
COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

# 演示环境连 MySQL，所以要带上 pymysql 驱动
RUN pip install --upgrade pip && pip install -e ".[mysql]"

EXPOSE 8000

# 迁移失败就别启动：带着半套 schema 起服务，错误会以 500 的形式散落在业务里
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
