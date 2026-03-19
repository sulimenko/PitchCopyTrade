# PitchCopyTrade

Telegram-first платформа для подписок на авторские стратегии и доставки торговых рекомендаций.

## Документы

- [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md) — серверный запуск
- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md) — канонический продуктовый и UI-контракт
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md) — только активный backlog
- [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md) — текущий review gate
- [doc/guide.html](/Users/alexey/site/PitchCopyTrade/doc/guide.html)
- [doc/guide.pdf](/Users/alexey/site/PitchCopyTrade/doc/guide.pdf)

## Текущий продуктовый контур

- `subscriber` работает через Telegram bot + Mini App
- `admin` работает через staff web
- `author` работает через staff web
- `moderation` остается staff operator surface

Сервисы:
- `api` — FastAPI
- `bot` — aiogram
- `worker` — фоновые задачи и уведомления

Runtime:
- storage только локальный под `APP_STORAGE_ROOT`
- PostgreSQL и Redis на сервере
- staff auth primary path: Telegram Login Widget
- password login — только local/demo fallback

## Текущие роли

- `admin`
  - создает `author`
  - создает стратегии за любого автора
  - управляет staff, платежами, подписками, документами и delivery
- `author`
  - работает только со своими стратегиями и рекомендациями
- `subscriber`
  - только Telegram / Mini App

Если один пользователь имеет роли `admin + author`, это один `User`. Он переключает режим работы внутри staff UI.

## Текущий governance contract

- новый `admin` и `author` создаются из продукта, без SQL
- обязательные поля создания staff user: `display_name + email`
- `telegram_user_id` не должен быть primary полем onboarding
- новый staff user создается в статусе `invited`
- staff user становится `active` только после invite/bind через Telegram
- invite links строятся как абсолютные URL от `BASE_URL`

Текущий gap:
- invite email не отправляется автоматически
- администратору приходится вручную копировать invite link
- staff UI еще не переведен на единый compact grid layer

## UI priorities

- `public` и Mini App: дизайн и product feel первичны
- `admin`, `author`, `moderation`: usability первична, дизайн вторичен

Для staff UI канонический следующий контракт:
- компактный layout
- мелкие контролы
- минимум карточек и декоративных блоков
- левая навигация
- breadcrumb
- кнопка назад
- единый `AG Grid Community` layer
- редактирование через right drawer
- сложные формы через modal / fullscreen modal

## Язык интерфейса

Весь текст, который видит пользователь или сотрудник в интерфейсе, должен быть на русском:
- статусы
- labels
- hints
- actions
- table headers
- empty states

Внутренние enum/value имена в коде могут оставаться английскими, но UI-копия должна быть русской.

## Текущий review focus

Следующий крупный блок не про новые сущности, а про чистку staff UX:

1. единый compact staff shell
2. `AG Grid Community` для всех list/registry/queue screens
3. unified CRUD pattern для `admin` и `author`
4. mutability rules по статусам
5. быстрый onboarding staff через email invite + Telegram bind

Подробно:
- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)

## Быстрый запуск

Локальный и серверный runbook вынесен в:
- [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md)

Tester/operator guide:
- [doc/guide.html](/Users/alexey/site/PitchCopyTrade/doc/guide.html)
- [doc/guide.pdf](/Users/alexey/site/PitchCopyTrade/doc/guide.pdf)

## Основные env-поля

```dotenv
APP_SECRET_KEY=
BASE_URL=
ADMIN_BASE_URL=

APP_DATA_MODE=db
APP_STORAGE_ROOT=/data/storage

TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
TELEGRAM_USE_WEBHOOK=true
TELEGRAM_WEBHOOK_SECRET=

DATABASE_URL=
REDIS_URL=

SMTP_HOST=
SMTP_PORT=
SMTP_SSL=true
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_FROM_NAME=

ADMIN_EMAIL=
ADMIN_TELEGRAM_ID=
```

## Что считать каноническим сейчас

- нет MinIO и `MINIO_*`
- нет object-storage fallback
- нет второго author contour
- нет subscriber web-auth вне Telegram
- нет разрастания docs историческими фазами

Документы должны поддерживаться так:
- `README` — короткий overview
- `blueprint` — только текущий canonical contract
- `task` — только активные блоки работ
- `review` — только текущие gates и findings

Старые completed фазы не накапливать как историю. Когда блок завершен и больше не влияет на текущие решения, его нужно вычищать из `task.md` и оставлять только в коде и git history.
