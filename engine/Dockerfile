# fele engine: API + CLI. Data is mounted at runtime, never baked into the image.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 \
    STL_DATA_DIR=/grid FELE_DATA_DIR=/data PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

RUN useradd --create-home fele && mkdir -p /data && chown fele /data
USER fele
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["fele", "serve", "--host", "0.0.0.0", "--no-reload"]
