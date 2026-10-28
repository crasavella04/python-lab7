# syntax=docker/dockerfile:1

# ---------- builder: зависимости ставятся в отдельный venv ----------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- builder-dev: + pytest, httpx, ruff ----------
FROM builder AS builder-dev
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

# ---------- общая база для финальных образов ----------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
# непривилегированный пользователь без пароля и shell-входа
RUN groupadd --system app && useradd --system --gid app --uid 10001 --no-create-home app
WORKDIR /app

# ---------- test: образ для запуска тестов (docker compose run tests) ----------
FROM base AS test
COPY --from=builder-dev /opt/venv /opt/venv
COPY --chown=app:app . .
USER app
CMD ["pytest", "-v"]

# ---------- runtime: продовый образ (последний этап = цель по умолчанию) ----------
FROM base AS runtime
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
