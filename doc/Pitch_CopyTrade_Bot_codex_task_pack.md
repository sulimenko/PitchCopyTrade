# Pitch CopyTrade Bot Codex Task Pack

Дата: 2026-03-10
Режим: implementation baseline after requirements lock

## Цель
Собрать foundation и затем MVP `PitchCopyTrade` на стеке:
- `FastAPI`
- `aiogram 3`
- `SQLAlchemy 2`
- `Alembic`
- `PostgreSQL`
- `MinIO`
- `Jinja2 + HTMX`
- `Docker Compose`

## Обязательные ограничения
- Python 3.12.
- Только русский язык UI и bot copy.
- Основное хранилище - `PostgreSQL`.
- Файлы - во втором контейнере `MinIO`.
- Платежи пока только `stub/manual`.
- Источник лида должен учитываться с первого релиза.
- Роли только `admin`, `author`, `moderator`.
- Автор не видит PII клиентов, только агрегированное количество подписчиков.

## Согласованные доменные требования
- subscription types:
  - `strategy`
  - `author`
  - `bundle`
- recommendation kinds:
  - `new_idea`
  - `update`
  - `close`
  - `cancel`
- moderation:
  - опциональна;
  - зависит от прав автора.
- extra commerce:
  - trial;
  - promo code;
  - manual discount;
  - auto-renew flag.

## Порядок реализации

### 1. Foundation infrastructure
Сделать:
- `pyproject.toml`
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `src/` package skeleton
- `api`, `bot`, `worker` entrypoints
- config через `.env`

Acceptance criteria:
- структура проекта соответствует новому стеку;
- Docker Compose описывает `api`, `bot`, `worker`, `postgres`, `minio`;
- нет старых предположений про file-first persistence.

### 2. Config and runtime
Сделать:
- `Pydantic Settings` для env;
- settings для DB, MinIO, bot, security, payments;
- base logging;
- fail-fast на обязательных переменных.

Acceptance criteria:
- конфиг типизирован;
- секреты не хардкодятся;
- один источник правды для env names.

### 3. Database foundation
Сделать:
- SQLAlchemy Base;
- domain enums;
- модели:
  - users
  - roles
  - user_roles
  - author_profiles
  - instruments
  - strategies
  - bundles
  - bundle_members
  - subscription_products
  - lead_sources
  - promo_codes
  - payments
  - subscriptions
  - recommendations
  - recommendation_legs
  - recommendation_attachments
  - legal_documents
  - user_consents
  - audit_events

Acceptance criteria:
- схема покрывает согласованные типы подписок и публикаций;
- роли и moderation моделируются через данные, а не hardcoded ifs;
- attachment metadata живет в БД, а не в локальных JSON.

### 4. Alembic foundation
Сделать:
- `alembic.ini`
- `alembic/env.py`
- initial migration

Acceptance criteria:
- миграция описывает foundation schema;
- schema не создается "магически" через `create_all` в runtime.

### 5. FastAPI baseline
Сделать:
- `GET /health`
- `GET /ready`
- metadata route
- router assembly
- startup/shutdown hooks

Acceptance criteria:
- API контейнер имеет понятную точку входа;
- health endpoint не зависит от UI.

### 6. Bot baseline
Сделать:
- aiogram entrypoint;
- `/start` placeholder;
- базовый dispatcher;
- config wiring.

Acceptance criteria:
- bot process отделен от API process;
- нет смешения bot handlers и web handlers.

### 7. Worker baseline
Сделать:
- отдельный worker entrypoint;
- каркас для jobs:
  - scheduled publish;
  - payment expiry sync;
  - subscription expiry;
  - reminder jobs.

Acceptance criteria:
- worker изолирован;
- будущие cron-like задачи не зашиваются в API или bot контейнер.

### 8. MinIO storage adapter
Сделать:
- storage client wrapper;
- upload/download/delete interface;
- bucket bootstrap;
- config for bucket names.

Acceptance criteria:
- объектное хранилище абстрагировано от доменного слоя;
- recommendation attachments готовы к переводу в MinIO без локального файлового слоя.

### 9. Auth foundation
Сделать:
- password hashing utilities;
- session/token strategy для web login;
- базовую модель user-role mapping.

Acceptance criteria:
- только `admin`, `author`, `moderator`;
- авторские логины отделены от клиентских Telegram identities.

### 10. Compliance foundation
Сделать:
- модель legal documents;
- модель consent acceptance;
- связку consent before payment.

Acceptance criteria:
- legal drafts можно хранить и версионировать;
- у платежного потока есть место для обязательного согласия.

## UX контракт кабинета автора
Визуальный ориентир: `doc/author_cabinet_prototype/index.html`.

### Обязательно реализовать
- `left rail` со стратегиями, drafts и quick actions;
- `central workspace canvas` как главный слой работы;
- `right inspector` с validation, preview и publish actions;
- режимы `workspace`, `pipeline`, `analytics`, `calendar`, `history` внутри одного shell;
- `draft-first` и `autosave-first` поведение;
- multi-leg editor для нескольких сделок в одной рекомендации;
- desktop table и mobile cards/list fallback;
- агрегированную аудиторию без показа PII клиентов автору.

### Нельзя делать
- прямой клон trading terminal;
- перегруженный экран с графиками без editorial hierarchy;
- одну длинную форму без rails, pipeline и preview split;
- разнос `pipeline`, `calendar` и `history` в чужие страницы без общего draft context;
- bury validation или Telegram preview глубоко внутри формы.

### Acceptance criteria
- draft открывается из rail в 1 клик;
- draft state сохраняется при смене режимов;
- validation виден до publish action;
- preview находится в том же рабочем контексте, что и редактор;
- pipeline и calendar используют те же сущности публикаций, а не отдельные модели;
- mobile не роняет multi-leg идею в нечитаемую таблицу.

## Что должно пойти следующим этапом после foundation
- auth UI;
- admin dashboard;
- strategy catalog CRUD;
- products and subscription pricing;
- payments stub flow;
- entitlements;
- recommendation composer;
- bot showcase and subscriptions.

## Явные запреты
- не возвращаться к JSON-файлам как primary store;
- не складывать вложения рядом с кодом;
- не кодировать роли через строковые константы по всему проекту;
- не смешивать synchronous DB hacks с async app без явной границы;
- не хардкодить локальные секреты в compose или python code;
- не копировать торговый терминал как author UX без адаптации к publishing workflow.

## Definition of done для текущего шага
Текущий шаг считается выполненным, если:
- документы обновлены под новый стек;
- каркас проекта создан;
- foundation schema описана моделями и миграцией;
- есть Docker baseline;
- есть рабочие entrypoints `api`, `bot`, `worker`;
- `.env` подготовлен под `PostgreSQL + MinIO + stub/manual`.
