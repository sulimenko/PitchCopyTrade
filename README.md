# PitchCopyTrade

Telegram-first marketplace для подписок на инвестиционные стратегии и доставки торговых сообщений.

## Что находится в репозитории

Проект состоит из трех сервисов:

| Сервис | Entry point | Назначение |
| --- | --- | --- |
| API | `src/pitchcopytrade/api/main.py` | FastAPI, public web, Mini App, staff UI |
| Bot | `src/pitchcopytrade/bot/main.py` | Telegram bridge, `/start`, deep links, Mini App launch |
| Worker | `src/pitchcopytrade/worker/main.py` | background jobs, lifecycle, notifications, scheduled publish |

Поддерживаются два storage-режима:

- `APP_DATA_MODE=file` — локальный/demo режим на `storage/runtime/*`
- `APP_DATA_MODE=db` — PostgreSQL через SQLAlchemy async

Платежные провайдеры:

- `stub_manual`
- `tbank`

## Как читать документацию

Каждый документ отвечает только за свою зону:

- [doc/README.md](/Users/alexey/site/PitchCopyTrade/doc/README.md) — правила работы с проектом, локальный runbook, команды запуска, тесты
- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md) — продуктовый, UX и data contract
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md) — единый активный backlog
- [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md) — review findings и merge gate
- [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md) — server deploy, clean DB reset, server smoke-check

## Быстрый старт

Если задача локальная:

- поднимайте проект по [doc/README.md](/Users/alexey/site/PitchCopyTrade/doc/README.md)
- для быстрой разработки используйте `APP_DATA_MODE=file`
- для clean DB reset и db-mode сценариев переходите в [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md)

Если задача продуктовая или UX:

- сначала читайте [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)

Если задача implementation/research:

- начинайте с [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- после изменений сверяйтесь с [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)
