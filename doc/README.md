# PitchCopyTrade — Local Work Guide

Этот файл отвечает только за локальную работу с проектом:

- как читать документы;
- как запускать сервисы локально;
- как работать с backlog;
- как прогонять тесты и preview-сценарии.

За product contract отвечает [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md).  
За backlog отвечает [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md).  
За review gate отвечает [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md).  
За server deploy и clean DB reset отвечает [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md).

Если входите в новый implementation pass как worker, сначала прочитайте стратегический блок `P25` в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md).

## Текущий Snapshot

Проверенный runtime snapshot на `2026-04-03` такой:

- Mini App auth и checkout в `db`-mode проходят;
- новые подписчики создаются и получают подписки/consents;
- страницы подписок в Mini App рендерятся без `500`;
- publish path и subscriber delivery работают;
- staff/admin Telegram invite onboarding в основном контуре восстановлен;
- local `BASE_URL` / `ADMIN_BASE_URL` и raw `uvicorn` contract синхронизированы на `http://127.0.0.1:8000`;
- operator-facing runtime log source = `storage/api.log`.

Текущие открытые follow-up после последнего design/runtime pass-а:

- checkout UI показывает только `Дисклеймер`, но hidden legal docs нельзя silently auto-submit-ить как уже принятые, см. `P44` в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md);
- после сокращения Mini App menu checkout/product-flow surface должен сохранить локальный CTA `К стратегии`, см. `P45` в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md).

## Правила работы

- перед реализацией читайте [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- для нового worker-pass сначала сверяйтесь с архитектурной стратегией `P25` в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- если задача затрагивает UX или data contract, сначала сверяйтесь с [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- после завершения задачи обновляйте статус в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- не переходите к следующему блоку backlog, пока текущий не зафиксирован в задаче и review
- пишите минимально необходимый код, без лишних абстракций
- весь пользовательский UI-текст держите на русском языке
- не добавляйте help/onboarding текст в интерфейс, если это не требуется задачей

## Короткий снимок проекта

Сервисы:

- API: `./.venv/bin/python -m uvicorn pitchcopytrade.main:app --reload --host 127.0.0.1 --port 8000`
- Bot: `./.venv/bin/python -m pitchcopytrade.bot.main`
- Worker: `./.venv/bin/python -m pitchcopytrade.worker.main`

Storage modes:

- `db` — основной рабочий режим текущего цикла
- `file` — вторичный compatibility/smoke режим, читающий `storage/runtime/*`

Важные env-факты:

- canonical runtime env file = `.env`
- template для локальной конфигурации = `.env.example`
- `api` не стартует без `INTERNAL_API_SECRET`
- `db`-mode является приоритетным runtime path для текущей разработки
- `file`-mode можно использовать для быстрой верстки, preview и compatibility smoke, но не как основной критерий готовности product-flow
- `db`-mode сейчас не означает полный business seed: после clean reset автоматически поднимаются только schema, `instruments` и bootstrap `admin`; полный dataset пока требует отдельного importer/seed pass
- для operator RCA используйте прежде всего `storage/api.log`
- если запускаете raw `uvicorn` локально без proxy/hosts-entry, `BASE_URL` и `ADMIN_BASE_URL` должны совпадать с реальным reachable origin `http://127.0.0.1:8000`

## Подготовка окружения

```bash
cd /Users/alexey/site/PitchCopyTrade

if [ ! -x ./.venv/bin/python ]; then
  python3.12 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -e ".[dev]"
fi
```

## Локальный запуск без Docker

### Основной режим: `db`

Используйте `APP_DATA_MODE=db`, если проверяете реальные продуктовые сценарии.

Важно:

- текущий цикл считает `db` основным рабочим контуром;
- `file` остается полезным для быстрого UI smoke и preview, но не заменяет проверку на PostgreSQL path.

Детальный reset/startup сценарий вынесен в [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md).

### Быстрый fallback режим: `file`

Перед воспроизводимой проверкой очистите runtime:

```bash
cd /Users/alexey/site/PitchCopyTrade
bash scripts/clean_storage.sh --apply --fresh-runtime
```

Запуск API:

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_ENV=development
export APP_HOST=127.0.0.1
export APP_PORT=8000
export BASE_URL=http://127.0.0.1:8000
export ADMIN_BASE_URL=http://127.0.0.1:8000/admin
export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret
export TELEGRAM_USE_WEBHOOK=false
export TELEGRAM_BOT_USERNAME=local_preview_bot

./.venv/bin/python -m uvicorn pitchcopytrade.main:app --reload --host 127.0.0.1 --port 8000
```

Запуск worker при необходимости:

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_ENV=development
export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret

./.venv/bin/python -m pitchcopytrade.worker.main
```

Запуск bot только если есть реальный Telegram token:

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_ENV=development
export BASE_URL=https://<your-https-host>
export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret
export TELEGRAM_USE_WEBHOOK=false
export TELEGRAM_BOT_TOKEN=<real-token>
export TELEGRAM_BOT_USERNAME=<real-bot-username>

./.venv/bin/python -m pitchcopytrade.bot.main
```

### Когда использовать `file`

Переходите в `APP_DATA_MODE=file`, если хотите:

- быстро смотреть верстку
- воспроизводить compatibility path
- делать preview/smoke без полной зависимости от PostgreSQL данных

Важно:

- `file` больше не считается главным режимом приемки product-flow;
- если задача работает только в `file`, но не работает в `db`, она не считается закрытой;
- `db`-mode пока не дает полный business seed автоматически, это только primary runtime path для schema/startup verification;
- детальный db-mode runbook и текущие ограничения описаны в [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md).

Сам сценарий reset/migrate намеренно вынесен в [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md), чтобы не дублировать server/db runbook здесь.

## Preview и локальный доступ

### Preview mode

Для локальной верстки без Telegram token и auth cookies:

```bash
export APP_PREVIEW_ENABLED=true
```

Основные preview URL:

- `http://127.0.0.1:8000/preview`
- `http://127.0.0.1:8000/preview/app/catalog`
- `http://127.0.0.1:8000/preview/app/status`
- `http://127.0.0.1:8000/preview/app/help`
- `http://127.0.0.1:8000/preview/admin/dashboard`
- `http://127.0.0.1:8000/preview/author/dashboard`

### Dev bootstrap

Для одного локального входа без Telegram/OAuth:

- `http://127.0.0.1:8000/dev/bootstrap`

Что делает bootstrap:

- создает или поднимает local staff account с ролями `admin`, `author`, `moderator`
- ставит staff/session cookies и Telegram fallback cookie
- открывает нужную surface сразу в браузере
- работает только в `development`, `test`, `local`

Bootstrap-аккаунт:

- email: `dev-superuser@pitchcopytrade.local`
- password: `local-dev-password`
- Telegram ID: `999000099`

Доступные режимы:

- `admin` -> `/admin/dashboard`
- `author` -> `/author/dashboard`
- `moderator` -> `/moderation/queue`
- `catalog` -> `/app/catalog`

## Что открывать в браузере

Public:

- `http://127.0.0.1:8000/catalog`
- `http://127.0.0.1:8000/catalog/strategies/momentum-ru`
- `http://127.0.0.1:8000/checkout/momentum-ru-month`
- `http://127.0.0.1:8000/legal/doc-disclaimer`

Важно:

- `http://127.0.0.1:8000/checkout/momentum-ru-month` теперь canonical public checkout URL в `APP_DATA_MODE=db`;
- `product-1` остается file-mode seeded example и не является универсальным локальным URL.

Mini App:

- `http://127.0.0.1:8000/app`
- `http://127.0.0.1:8000/app/catalog`
- `http://127.0.0.1:8000/app/help`
- `http://127.0.0.1:8000/app/status`

Staff:

- `http://127.0.0.1:8000/login`
- `http://127.0.0.1:8000/admin/dashboard`
- `http://127.0.0.1:8000/author/dashboard`
- `http://127.0.0.1:8000/author/messages`
- `http://127.0.0.1:8000/author/messages/new`
- `http://127.0.0.1:8000/moderation/queue`

Author surface:

- `/author/messages` — основная message-centric рабочая поверхность автора: history table + unified composer
- `/author/messages/new` — тот же composer, открытый в явном create-flow
- `/author/messages/<id>/edit` — edit-flow того же composer для существующего сообщения

## Тесты и проверки

Полный suite:

```bash
./.venv/bin/python -m pytest -q
```

Точечные прогоны:

```bash
./.venv/bin/python -m pytest tests/test_health.py -q
./.venv/bin/python -m pytest tests/test_health.py::test_metadata_route_returns_runtime_metadata -q
./.venv/bin/python -m pytest -v
```

Синтаксическая проверка:

```bash
./.venv/bin/python -m compileall src tests
```

Reproducible file-mode smoke:

```bash
source scripts/local_file_profile.sh
bash scripts/local_file_smoke.sh
```

## Где искать дальше

- product/UX/data decisions: [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- backlog и implementation phases: [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- review findings и merge gate: [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)
- db-mode reset, schema, server smoke, SMTP, bot transport: [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md)
