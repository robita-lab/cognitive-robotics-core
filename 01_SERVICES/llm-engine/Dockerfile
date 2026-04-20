FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml ./
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

COPY app ./app

FROM python:3.12-slim AS runtime

RUN groupadd --system --gid 1001 udito && \
    useradd --system --uid 1001 --gid udito --create-home udito

WORKDIR /app

COPY --from=builder --chown=udito:udito /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER udito

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
