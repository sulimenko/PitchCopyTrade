# PitchCopyTrade Blueprint

Дата: 2026-03-11  
Статус: actual implementation baseline + updated target architecture

## 1. Назначение
Этот документ фиксирует:
- что уже реализовано в проекте;
- что теперь считается целевой схемой после изменения subscriber model;
- что из текущей реализации стало transitional и должно быть переделано;
- что нужно довести до полного завершения проекта.

## 2. Главный продуктовый сдвиг
Клиентский контур больше не считается `web-first`.

Новая целевая модель:
- основное взаимодействие подписчика идет через `Telegram`;
- все основные сервисы для клиента должны жить в Telegram-боте;
- web для клиента допустим только как:
  - публичная витрина;
  - legal pages;
  - optional fallback surface;
- если клиенту нужен авторизованный web-доступ, авторизация должна идти только через `Telegram auth`, а не через отдельный email/password login;
- данные клиента должны собираться по принципу minimum necessary data.

## 3. Зафиксированные решения
- Язык: `русский`
- Стек:
  - `FastAPI`
  - `aiogram 3`
  - `SQLAlchemy 2`
  - `Alembic`
  - `PostgreSQL`
  - `MinIO`
  - `Jinja2`
  - `HTMX`
- Платежи в первой версии: `stub/manual`
- Следующий провайдер: `Т-Банк`
- Типы подписок:
  - `strategy`
  - `author`
  - `bundle`
- Роли web-кабинета:
  - `admin`
  - `author`
  - `moderator`
- Subscriber identity:
  - primary id: `telegram_user_id`
  - минимальный профиль по умолчанию:
    - `telegram_user_id`
    - `username`
    - `first_name`
    - `last_name`
- `email` и `phone`:
  - не обязательны;
  - собираются только по желанию пользователя или по явной необходимости сценария.

## 4. Runtime и deployment model

### Основной режим
Основной режим подключения к БД:
- внешний `PostgreSQL`, уже установленный в системе;
- DSN приходит через `.env`.

### Допустимый второй режим
Допустим и должен поддерживаться:
- optional docker-based PostgreSQL для локального dev/demo режима.

### Правило
Система должна запускаться разными способами:
- с внешним DSN;
- с docker-based DB;
- без переписывания application code.

То есть `postgres` не должен считаться жестко обязательным docker-сервисом для каждого запуска.

## 5. Что уже реально реализовано

### 5.1 Infrastructure foundation
Есть:
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- typed runtime config
- `api`, `bot`, `worker`
- health/readiness/meta endpoints

### 5.2 Data foundation
Есть:
- ORM foundation
- Alembic initial migration
- доменные модели:
  - users / roles / author_profiles
  - strategies / bundles / subscription_products
  - payments / subscriptions / promo_codes
  - recommendations / legs / attachments
  - legal_documents / user_consents
  - lead_sources
  - audit_events

### 5.3 Auth/admin foundation
Есть:
- web login/logout для `admin/author/moderator`
- password hashing
- session cookie auth
- admin guard
- author guard

### 5.4 Admin commercial contour
Есть:
- admin dashboard
- strategy CRUD
- subscription product CRUD
- payment queue
- payment review
- confirm payment -> activate subscription

### 5.5 Author workspace baseline
Есть:
- `/author/dashboard`
- `/author/recommendations`
- create/edit recommendation flow
- author-scoped strategy selection
- author sees only own recommendation set
- statuses and kinds editable on baseline level
- structured legs editor
- attachment upload through MinIO
- scheduled/published/closed/cancelled state timestamps
- preview route with subscriber-facing template

### 5.6 Moderation baseline
Есть:
- `/moderation/queue`
- moderation detail page
- approve / rework / reject actions
- moderation audit event write
- moderator login redirect

### 5.7 Public storefront baseline
Есть:
- `/catalog`
- `/catalog/strategies/{slug}`
- web fallback checkout flow

### 5.8 Telegram-first subscriber baseline
Есть:
- `/start` creates or updates minimal Telegram subscriber profile
- bot `/catalog`
- bot `/buy <product_slug>`
- bot `/confirm_buy <product_slug>`
- bot `/web` for Telegram-authenticated web fallback link
- dedicated Telegram fallback cookie issued by `/tg-auth`

### 5.9 Access delivery baseline
Есть:
- ACL service
- `/app/feed`
- recommendation detail with ACL gate
- bot `/feed` with active/trial gate
- `/app/*` fallback now depends on Telegram-issued access, not on staff web session
- attachment download path under ACL
- richer recommendation rendering for legs and attachments

## 6. Что в текущем коде считается transitional и подлежит переделке

### 6.1 Subscriber web login/password
Этот конфликт на baseline-уровне снят:
- web checkout больше не требует subscriber password;
- bot уже выдает Telegram-authenticated web fallback link.

Но до продуктового завершения еще нужно:
- заменить link-based fallback на более нативный Telegram WebApp / Mini App contour;
- улучшить Telegram UX beyond command baseline.

### 6.2 Web checkout как primary path
Сейчас web checkout уже переведен в fallback-режим.

Главный путь:
- Telegram bot checkout commands.

Дальше нужно:
- richer Telegram UX;
- более нативный consent flow;
- optional Telegram WebApp replacement for web fallback.

### 6.3 Web subscriber area
Сейчас есть `/app/feed`.

Новая интерпретация:
- это secondary fallback surface;
- если он остается, то должен открываться только через Telegram-authenticated access;
- он не должен быть основной точкой взаимодействия подписчика.

## 7. Целевая subscriber architecture

### Primary surface: Telegram
Подписчик должен в Telegram:
- открыть витрину;
- выбрать стратегию или пакет;
- увидеть legal/copy/условия;
- оформить checkout;
- получить статус оплаты;
- видеть доступные рекомендации;
- управлять подписками и своим статусом.

### Optional surface: web fallback
Допустимо оставить:
- public landing/catalog/legal;
- Telegram-authenticated fallback pages;
- Telegram WebApp / Mini App как recommended web surface.

Рекомендованный подход:
- `Telegram WebApp / Mini App`

## 8. Canonical auth model

### Subscriber
- primary auth: `Telegram identity`
- не требовать пароль;
- не требовать email/password для базового доступа к сервису;
- хранить минимальный профиль;
- собирать дополнительные данные только при необходимости.

### Admin / Author / Moderator
- остаются в web-кабинете;
- auth по `login/password`;
- отдельный контур от subscriber auth.

## 9. Canonical checkout model

### Subscriber checkout target
Основной целевой checkout:
- запускается в Telegram;
- собирает consents в Telegram;
- создает payment/subscription;
- не заставляет пользователя заводить отдельный web-account password.

### Data minimality
По умолчанию не требовать:
- email
- phone
- full profile form

Собирать только если:
- пользователь сам захотел оставить;
- это реально нужно для конкретного сценария;
- есть отдельное правовое или операционное основание.

## 10. Canonical access model
- entitlement строится на `active` / `trial` subscription;
- `pending` не дает delivery access;
- `strategy / author / bundle` entitlements должны разрешаться единообразно;
- web fallback и bot не должны иметь разные правила доступа.

## 11. Что обязательно еще реализовать до завершения проекта

### 11.1 Telegram-first subscriber refactor
Нужно сделать:
- довести subscriber model без password-first path до конца;
- Telegram-first checkout beyond command baseline;
- Telegram-first consent UX;
- Telegram-first status pages;
- Telegram-first recommendation feed;
- Telegram account linking / bootstrapping без ручной админской магии.

### 11.2 Telegram-auth web fallback
Нужно сделать:
- сохранить Telegram-authenticated web access как единственный fallback auth path;
- заменить link-based fallback на более нативный WebApp / Mini App contour;
- удержать единый ACL contract между bot и fallback web.

### 11.3 Author recommendation workspace
Baseline уже есть:
- author shell;
- recommendation CRUD;
- base status/kind editing;
- structured legs;
- attachment upload.

Нужно доделать:
- richer prototype-based workspace;
- drafts UX;
- preview polish;
- validation depth;
- attach/delete UX.

### 11.4 Moderation
Baseline уже есть:
- moderation queue;
- approve/reject/rework flow.

Нужно доделать:
- optional moderation per author;
- filters, SLA and history UX;
- moderation analytics.

### 11.5 Publish flow
Baseline уже есть:
- publish/schedule transitions;
- `new/update/close/cancel` types;
- status timestamps.

Нужно доделать:
- history/timeline;
- worker-based scheduled publish execution;
- moderator-aware transitions.

### 11.6 Attachments
Baseline уже есть:
- upload screenshot/PDF;
- attachment validation;
- MinIO persistence from author editor.

Нужно доделать:
- subscriber rendering/download path polish;
- deletion/replacement UX;
- attachment policy hardening.

### 11.7 Commerce completion
Нужно сделать:
- promo codes;
- manual discounts;
- trial UX;
- expiry/cancel flows;
- worker jobs instead of placeholders.

### 11.8 Legal admin surface
Нужно сделать:
- legal docs UI;
- versioning UI;
- active set management.

### 11.9 Lead source normalization
Нужно сделать:
- real linkage to `lead_sources`;
- reporting;
- attribution consistency.

### 11.10 Ops and hardening
Нужно сделать:
- DB mode support for external DSN and optional docker DB;
- deployment notes;
- seed/bootstrap scripts;
- broader integration tests.

## 12. Что считать полным завершением проекта
Проект считается завершенным, когда:
- subscriber контур стал реально Telegram-first;
- web fallback для subscriber использует только Telegram auth;
- admin/author web contour устойчив и complete;
- автор может создавать и публиковать рекомендации через рабочий кабинет;
- moderation и publish flows работают;
- delivery в bot/web идет по реальным публикациям;
- legal, payments, subscriptions, entitlements и delivery связаны end-to-end;
- запуск поддерживает внешний PostgreSQL через `.env` как основной режим.

## 13. Текущий status summary
- foundation: реализован
- admin коммерческий baseline: реализован
- author workspace baseline: реализован
- publish/legs/attachments baseline: реализован
- preview/moderation/rendering baseline: реализован
- ACL delivery baseline: реализован
- Telegram-first bot baseline: реализован
- subscriber password removed from web fallback checkout
- Telegram-auth-only web fallback baseline: реализован
- optional docker postgres profile and external DSN mode: зафиксированы
- главный следующий шаг: lifecycle polish, worker-based scheduling и Telegram UX depth
