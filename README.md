# BB-Translation

Pipeline dịch tài liệu ngành bánh (EN → VI), giữ nguyên layout gốc. Xem chi tiết yêu cầu tại
[docs/PRD.md](docs/PRD.md) và thiết kế kỹ thuật tại [docs/Architecture.md](docs/Architecture.md).

## Chạy dự án

```bash
cp .env.example .env
# Điền API key vào .env

docker compose -f docker/docker-compose.yml up -d

# Kèm OCR (MinerU)
docker compose -f docker/docker-compose.yml --profile ocr up -d
```

Truy cập: http://localhost:8000

## Phát triển local (không Docker)

```bash
uv sync
uv run uvicorn src.api.main:app --reload
```

## Trạng thái

Xem [docs/CHANGELOG.md](docs/CHANGELOG.md) để biết tiến độ từng increment.
