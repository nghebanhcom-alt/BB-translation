FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    calibre \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY web/ ./web/
COPY fonts/ ./fonts/

RUN mkdir -p /data/uploads /data/processing /data/outputs /data/glossary

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
