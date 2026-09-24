# Runs the sweep in demo mode by default; pass a .env for live mode.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

COPY fixtures ./fixtures

ENV PATH="/app/.venv/bin:$PATH" DEMO_MODE=true DRY_RUN=false EMAIL_RECIPIENTS=team@example.com \
    DB_PATH=/data/state.sqlite OUTBOX_DIR=/data/outbox
VOLUME ["/data"]

ENTRYPOINT ["notice-monitor"]
