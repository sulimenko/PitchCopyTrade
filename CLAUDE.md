# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Правила работы (обязательно)

- Читай `doc/task.md` перед каждой задачей
- После выполнения задачи сразу помечай `[x]` в `task.md`
- Не переходи к следующей задаче без пометки
- Переходи к следующей фазе автоматически — без подтверждения пользователя
- Если задача требует решения — задай один вопрос, не пиши код до ответа
- Пиши минимально необходимый код, без over-engineering
- Весь пользовательский текст в UI — только на русском языке
- Никаких инструкций, онбординга и help-текста в интерфейсе

## Ключевые документы

- `doc/blueprint.md` — архитектура MVP (читать перед любой реализацией)
- `doc/task.md` — фазы и задачи (отмечать прогресс `[x]`)
- `doc/review.md` — чеклист ревью (проверять после каждой фазы)
- `doc/instruments_stub.json` — 10 бумаг ММВБ (seed data)

## Project Overview

**PitchCopyTrade** is a Telegram-first subscription marketplace for selling investment strategy subscriptions and delivering trading recommendations. It has three cooperating services: a FastAPI web app, an aiogram 3 Telegram bot, and an asyncio background worker.

## Commands

### Setup
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running services locally
```bash
# API (with live reload)
PYTHONPATH=src uvicorn pitchcopytrade.api.main:app --host 0.0.0.0 --port 8000 --reload

# Telegram bot (polling mode)
PYTHONPATH=src python -m pitchcopytrade.bot.main

# Background worker
PYTHONPATH=src python -m pitchcopytrade.worker.main
```

### Docker (local dev)
```bash
docker compose up
```

### Tests
```bash
pytest                                          # all tests
pytest tests/test_health.py                    # single file
pytest tests/test_health.py::test_function_name  # single test
pytest -v                                       # verbose
```

Tests run with `asyncio_mode = "auto"` (configured in `pyproject.toml`). Most tests use file mode — no external services required.

### Lint / syntax check
```bash
python3 -m compileall src tests
```

### Database migrations
```bash
alembic upgrade head       # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
```

## Architecture

### Dual-mode storage
The app supports two storage backends controlled by `APP_DATA_MODE`:
- **`file`** (default/demo): JSON files in `storage/runtime/json/`, blobs in `storage/runtime/blob/`. No database needed. Seed data lives in `storage/seed/` and is copied to `runtime/` on cold start.
- **`db`**: PostgreSQL via SQLAlchemy 2 async + asyncpg.

The `repositories/` layer abstracts this — switching mode swaps the repository implementation, not the service logic.

### Three cooperating services
| Service | Entry point | Purpose |
|---------|-------------|---------|
| **API** | `api/main.py` | FastAPI: web UI, Mini App, staff dashboards, REST |
| **Bot** | `bot/main.py` | Telegram bot: `/start`, Mini App bridge, deep links |
| **Worker** | `worker/main.py` | Async jobs: payment sync, subscription lifecycle, notifications |

### Key layers
- `core/` — config (`AppSettings`), logging, runtime bootstrap
- `db/` — SQLAlchemy models (db mode only)
- `repositories/` — data access with file and db implementations
- `services/` — domain logic: admin, author, subscriber, payments, notifications
- `api/router.py` — route definitions delegating to services
- `bot/dispatcher.py` — aiogram handler registration
- `worker/runner.py` — scheduled job loop
- `payments/` — stub manual and T-Bank (Tinkoff) SBP integrations
- `auth/` — Telegram `initData` verification + role-based access

### Telegram Mini App flow
Subscribers enter via `/start` in the bot → open a Mini App (web UI inside Telegram WebView). Authentication uses verified Telegram `initData`. Staff access the same web UI via a browser with a separate auth path.

### Payment providers
Controlled by `SBP_PROVIDER`:
- `stub_manual` (default): no external calls, manually confirmed in admin
- `tbank`: T-Bank SBP real payments

### Key environment variables
```
APP_DATA_MODE=file|db
APP_STORAGE_ROOT=storage
DATABASE_URL=postgresql+asyncpg://...
TELEGRAM_BOT_TOKEN=...
SBP_PROVIDER=stub_manual|tbank
BASE_TIMEZONE=Europe/Moscow
TRIAL_ENABLED=true|false
PROMO_ENABLED=true|false
AUTORENEW_ENABLED=true|false
```

## Deployment

Production runs on CentOS 8 + Docker + host Nginx. Nginx proxies to `127.0.0.1:8110` (the API container). Bot uses polling (no webhook). File mode is used in production with local `storage/` mounts.

```bash
docker compose -f deploy/docker-compose.server.yml build
docker compose -f deploy/docker-compose.server.yml up -d
```
