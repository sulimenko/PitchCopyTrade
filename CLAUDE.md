# PitchCopyTrade

Python/FastAPI сервис. Документация в `doc/`:

- `doc/blueprint.md` — архитектурные правила, контракты, product contracts
- `doc/task.md` — активные задачи (блоки для worker)
- `doc/review.md` — текущий review gate и открытые findings
- `doc/changelog.md` — архив закрытых задач и заключений (не загружается автоматически)

---

## Роли

**Architect — этот чат (senior-модель: claude-opus/sonnet max)**

- пишет и обновляет `doc/*`
- формирует блоки задач в `task.md`
- проводит review после каждого блока
- **не пишет код, не выполняет задачи**

**Worker — более простая модель (claude-haiku/sonnet medium)**

- получает блок задач из `task.md`
- выполняет код строго по описанию
- не добавляет задачи, не меняет блок
- сигнализирует завершение → architect проводит review

---

## Правила task.md

- Задачи группируются в **блоки**: один блок = одна итерация worker → review
- ID: `T-NNN`, сквозная нумерация, никогда не сбрасывается
- Статусы: `[ ]` не начато / `[~]` в работе / `[x]` завершено / `[!]` заблокировано
- Каждая задача описана подробно: файлы, поведение до/после, ограничения, критерии
- После review — заключение в `review.md`; проблемы из review → новые T-NNN в следующем блоке

**Архивирование** (`doc/changelog.md`):

- >30 задач `[x]`/`[!]` в файле, или файл >400 строк, или крупный цикл завершён
- Переносятся все `[x]`/`[!]` старше последнего завершённого блока
- Архивная строка: `T-NNN | название | [x] | дата | краткий итог` — одна строка, без кода
- В `task.md` остаются только `[ ]`, `[~]` и правила

---

## Правила review

- Review проводится после каждого блока задач по checklist `doc/review.md`
- Заключение добавляется в конец раздела «Заключения по блокам» в `review.md`
- Формат: `### Заключение: Блок N — название`, затем статус (passed / passed with notes / failed), проблемы, задачи
- При архивировании — соответствующие заключения переносятся в `changelog.md`

---

## Порядок закрытия блока

1. Worker выполняет задачи → сигнализирует завершение
2. Architect читает изменённые файлы
3. Проверяет по checklist `doc/review.md`
4. Пишет заключение в `review.md`
5. При `passed`: обновляет `doc/*` если появились новые устойчивые правила
6. При `failed`: создаёт новый блок с задачами на исправление

---

## Ключевые архитектурные правила

Детали в `doc/blueprint.md`. Обязательный минимум:

**Слои:**

- `api/routes/` — HTTP-роуты, form handling, template rendering; не хранит state
- `api/deps/` — DI: auth, DB sessions, permissions
- `services/` — бизнес-логика: checkout, notifications, instruments, author workflow
- `repositories/` — SQLAlchemy queries, eager loading, data access
- `db/models/` — ORM-модели, enums, relationships
- `auth/` — Telegram WebApp validation, tokens, session management
- `bot/` — aiogram handlers, webhook/polling
- `web/templates/` — Jinja2 templates (HTMX, no JS framework)

**Notification delivery:**

- ARQ job queue (Redis). Publish → enqueue → worker sends Telegram + Email
- Telegram-first, per-recipient email fallback
- SMTP: aiosmtplib, relay.ptfin.kz:465 (SSL)

**Auth:**

- Subscriber: Telegram WebApp initData (HMAC-SHA256)
- Staff/Author: Telegram Login Widget → cookie session
- Staff invite: deep link → `/login?invite_token=...`

**Runtime:**

- Primary: `APP_DATA_MODE=db` (PostgreSQL)
- Secondary: `APP_DATA_MODE=file` (smoke/preview only)
- Bot: polling in dev, webhook in prod
- Quote provider: `INSTRUMENT_QUOTE_PROVIDER_BASE_URL` → backend adapter, не блокирует SSR

**Общее:**

- Russian UI everywhere. Нет onboarding text, нет help tooltips
- Никогда не делай auto-commit. Пользователь коммитит сам
- Не добавляй docstrings, комментарии или type annotations к коду, который не менял
- После любого значимого изменения: обновить `doc/*`

**Стек:**

Python 3.12, FastAPI, aiogram 3, SQLAlchemy 2 async, Alembic, asyncpg, Jinja2 + HTMX, PostgreSQL 16, Redis (ARQ), aiosmtplib.

**Routes:**

- `/catalog/*`, `/checkout/*` — Public web
- `/app/*` — Telegram Mini App
- `/admin/*` — Admin Cabinet
- `/author/*`, `/cabinet/*` — Author Cabinet
- `/api/*` — JSON API
- `/auth/*` — Authentication
- `/webhook/bot` — Telegram webhook
