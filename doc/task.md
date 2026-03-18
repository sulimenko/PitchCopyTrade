# PitchCopyTrade — MVP Implementation Task Pack
> Version: 0.2.0
> Updated: 2026-03-18
> Process: implement phases sequentially; each phase must pass its acceptance criteria before next begins

---

## Status Legend
- `[ ]` — pending
- `[~]` — in progress
- `[x]` — completed
- `[!]` — blocked / needs decision

---

## Phase 0 — Foundation (completed)
> Foundation was established in initial commit. Do not modify unless Phase regression.

- [x] Project packaging (pyproject.toml, src layout)
- [x] Docker Compose baseline (api, bot, worker, postgres, minio)
- [x] Env-based config (pydantic-settings, .env)
- [x] API health endpoints (`/health`, `/ready`, `/meta`)
- [x] Bot stub entry point (aiogram 3)
- [x] Worker stub entry point
- [x] Initial DB schema + Alembic migration (18 tables)
- [x] MinIO storage adapter skeleton
- [x] Test framework (pytest-asyncio, httpx)

---

## Phase 1 — Reset & Clean Slate

**Goal:** Service starts with zero legacy data, no instructions in UI, clean database.

### Tasks
- [ ] **1.1** Add `notification_queue` table to Alembic migration (new revision)
  - Fields: id, recommendation_id, channel, recipient_user_id, status, attempts, last_error, scheduled_at, sent_at, created_at
  - Add `NotificationStatus` enum: pending, sent, failed, skipped
  - Add `NotificationChannel` enum: telegram, email

- [ ] **1.2** Add instruments seeder
  - Create `src/pitchcopytrade/db/seeders/instruments.py`
  - Load from `doc/instruments_stub.json`
  - Upsert on ticker (skip if already exists)
  - Call seeder from API startup event (only if instruments table is empty)

- [ ] **1.3** Add admin user seeder
  - Create `src/pitchcopytrade/db/seeders/admin.py`
  - Reads `ADMIN_TELEGRAM_ID` and `ADMIN_EMAIL` from env
  - Creates User + Role(admin) if not exists
  - Call from API startup event

- [ ] **1.4** Create full reset script
  - `scripts/reset.sh` — drops volumes, removes images, restores clean state
  - Document in README.md § "Full Reset Procedure"

### Acceptance Criteria
- `docker-compose up --build` on clean machine produces empty tables (except instruments + admin user)
- No sample data, no placeholder rows anywhere

---

## Phase 2 — Bot Webhook & Internal Broadcast API

**Goal:** Bot runs in webhook mode on dedicated server; API can trigger broadcasts.

### Tasks
- [ ] **2.1** Webhook activation
  - Add `USE_WEBHOOK` env flag (already in config)
  - In `bot/main.py`: if `USE_WEBHOOK=true`, register webhook via `bot.set_webhook(url)`
  - Expose bot on port `8080` internally (aiohttp webhook server)
  - Add health check endpoint on bot: `GET /health`

- [ ] **2.2** Internal broadcast endpoint
  - In bot service: `POST /internal/broadcast`
  - Auth: `X-Internal-Token` header (shared secret from env `INTERNAL_API_SECRET`)
  - Payload: `{ "recommendation_id": "<uuid>" }`
  - Handler: fetch recommendation + legs + strategy from DB
  - Fetch all users with `Subscription.status = active` for this strategy
  - Send formatted Telegram message to each subscriber
  - Message format: see blueprint.md §9

- [ ] **2.3** Docker Compose updates
  - Bot service: expose port 8080 internally
  - Add `INTERNAL_API_SECRET` to env
  - Add reverse proxy rule (nginx or Caddy) for Telegram webhook path

- [ ] **2.4** Webhook setup docs
  - README.md § "Telegram Webhook Setup" — step-by-step for dedicated server

### Acceptance Criteria
- `curl -X POST http://localhost:8080/internal/broadcast -H "X-Internal-Token: ..." -d '{"recommendation_id":"..."}' ` sends message to test subscriber
- Bot logs show webhook registration on startup when `USE_WEBHOOK=true`

---

## Phase 3 — Telegram Auth for Author Web Cabinet

**Goal:** Author can authenticate in web cabinet using Telegram Login Widget.

### Tasks
- [ ] **3.1** Telegram Login Widget endpoint
  - `GET /auth/telegram/callback` — receives Telegram auth data
  - Verify HMAC-SHA256 signature using `BOT_TOKEN`
  - Reject if `auth_date` older than 5 minutes
  - Look up User by `telegram_user_id`; return 401 if not found (must be pre-created by admin)
  - Create signed JWT (HttpOnly, Secure, SameSite=Strict, 24h expiry)
  - Redirect to `/cabinet/`

- [ ] **3.2** Session middleware
  - `src/pitchcopytrade/api/middleware/auth.py`
  - `get_current_user()` dependency: decode JWT, fetch User from DB
  - `require_role(role_slug)` dependency factory

- [ ] **3.3** Login page template
  - `src/pitchcopytrade/templates/auth/login.html`
  - Telegram Login Widget button
  - No username/password form
  - No instructions — just the Telegram button and logo

- [ ] **3.4** Auth routes
  - `GET /auth/login` → renders login.html
  - `GET /auth/telegram/callback` → verify + redirect
  - `POST /auth/logout` → clear cookie + redirect to /auth/login

### Acceptance Criteria
- Author with valid `telegram_user_id` in DB can log in
- User not in DB gets 401 page (no registration self-service)
- JWT verified on every protected route

---

## Phase 4 — Admin Cabinet

**Goal:** Admin can create authors and manage basic settings.

### Tasks
- [ ] **4.1** Admin cabinet layout template
  - `src/pitchcopytrade/templates/admin/layout.html`
  - Left nav: Авторы | One Pager | Метрики | Выплаты
  - No instructions, no help text anywhere

- [ ] **4.2** Authors management page
  - `GET /admin/authors` — list of authors (name, telegram_id, email, active)
  - `POST /admin/authors` — create author
    - Form fields: `display_name` (required), `email` (optional), `telegram_user_id` (optional)
    - Creates: User + AuthorProfile (slug auto-generated from display_name) + user_roles(author)
    - Sets `requires_moderation=False`
  - `POST /admin/authors/{id}/toggle` — activate/deactivate

- [ ] **4.3** One Pager editor
  - `GET /admin/onepager/{strategy_id}` — edit One Pager
  - `POST /admin/onepager/{strategy_id}` — save HTML content
  - Store in `Strategy.full_description` as HTML
  - Preview button opens `/s/{strategy_slug}` in new tab

- [ ] **4.4** Metrics page
  - `GET /admin/metrics`
  - Cards: total subscribers, active subscriptions, new this week
  - Table: strategy → subscriber count (aggregated, no individual names)

- [ ] **4.5** Payments page (stub)
  - `GET /admin/payments` — list of pending manual payments
  - `POST /admin/payments/{id}/confirm` — manually confirm payment → activates subscription

### Acceptance Criteria
- Admin can create author; new author can immediately log in via Telegram
- No PII leak: admin cannot see individual subscriber identities in metrics

---

## Phase 5 — Instruments & Ticker Picker

**Goal:** Ticker picker popup backed by instruments_stub.json with client-side search.

### Tasks
- [ ] **5.1** Instruments API endpoint
  - `GET /api/instruments` — returns list of active instruments
  - Response: `[{ ticker, name, last_price, change_pct, board, currency }]`
  - Served from DB (seeded from instruments_stub.json)
  - Future: add `?q=` search param for live API proxy

- [ ] **5.2** Ticker picker component
  - `src/pitchcopytrade/templates/components/ticker_picker.html` (HTMX partial)
  - Input field triggers `hx-get=/api/instruments?q=...` on keyup (debounce 300ms)
  - Results table: ticker | name | last_price | change_pct
  - Click row → fills parent input, closes popup
  - Recent picks stored in `localStorage` under key `pct_recent_tickers`
  - Recent picks shown starred at top when no search query

- [ ] **5.3** Include ticker picker in recommendation inline row and popup form

### Acceptance Criteria
- Typing "SB" in ticker field shows SBER at top
- Clicking SBER fills the ticker field and closes popup
- Recent picks persist across page reloads

---

## Phase 6 — Author Cabinet & Strategy Management

**Goal:** Author can create strategies and manage them.

### Tasks
- [ ] **6.1** Author cabinet layout
  - `src/pitchcopytrade/templates/cabinet/layout.html`
  - Left nav: Стратегии | (future: Аналитика)
  - Header: author display_name + "Выйти" button
  - No help text, no onboarding

- [ ] **6.2** Strategies list page
  - `GET /cabinet/strategies` — list author's strategies (title, status, subscriber count)
  - "Создать стратегию" button
  - `POST /cabinet/strategies` — create strategy (title required, slug auto-generated)
  - `GET /cabinet/strategies/{id}` — opens recommendations page for this strategy

- [ ] **6.3** Strategy edit
  - `GET /cabinet/strategies/{id}/edit` — edit title, short_description, risk_level, min_capital_rub
  - `POST /cabinet/strategies/{id}/edit` — save

### Acceptance Criteria
- Author sees only their own strategies (ACL enforced by `strategy.author_id = current_user.author_profile.id`)
- Strategy slug is unique and URL-safe

---

## Phase 7 — Recommendation CRUD (Inline + Popup)

**Goal:** Author can create, view, and publish recommendations with minimal required fields.

### Tasks
- [ ] **7.1** Recommendations table page
  - `GET /cabinet/strategies/{strategy_id}/recommendations`
  - Table columns: дата | тикер | сторона | цена | цель | стоп | статус | действия
  - Empty state: no rows, no placeholder text, just empty table + inline add row at bottom
  - Table starts fully empty on fresh DB

- [ ] **7.2** Inline add row
  - Last row in table is always an empty editable row
  - Fields: `[Тикер ▼]` `[BUY ▼]` `[Цена]` `[Цель]` `[Стоп]`
  - Clicking Тикер → opens Ticker Picker Popup (Phase 5)
  - BUY/SELL → toggle button or small dropdown
  - Price/Target/Stop → number inputs, nullable, no validation if empty
  - Enter or click `[+]` → POST to create recommendation + first leg
  - New row appears at top of table, inline row resets

- [ ] **7.3** Recommendation creation API
  - `POST /cabinet/strategies/{strategy_id}/recommendations`
  - Body: `{ ticker, side, price?, target?, stop? }`
  - Creates `Recommendation` (kind=new_idea, status=draft, requires_moderation=False)
  - Creates `RecommendationLeg` (instrument_id from ticker, side, entry_from=price, tp1=target, stop_loss=stop)
  - Returns HTMX partial with new table row (hx-swap: afterbegin on tbody)

- [ ] **7.4** Full popup form
  - "Новая рекомендация" button above table → opens modal
  - Modal fields:
    - Название (optional text)
    - Тип: new_idea / update / close / cancel (radio)
    - Legs (repeatable): Тикер + Сторона + Цена + Цель + Стоп + Заметка
    - "Добавить ногу" link
    - Запланировать на (optional datetime)
  - Submit → same POST endpoint, richer body
  - Close button (Esc or ×)

- [ ] **7.5** Publish action
  - Each draft row has "Опубликовать" button
  - `POST /cabinet/recommendations/{id}/publish`
  - Sets status=published, published_at=now()
  - Calls internal broadcast (Phase 2.2) async — do not block UI response
  - Enqueues email notification in notification_queue
  - Returns HTMX swap updating just that row's status cell

- [ ] **7.6** Row actions
  - "Закрыть" (close) → status=closed, closed_at=now()
  - "Отменить" (cancel) → status=cancelled, cancelled_at=now()
  - No delete in MVP — soft close/cancel only

### Acceptance Criteria
- Author creates recommendation with only ticker + side — saves without error
- Price, target, stop are nullable — blank fields allowed
- Published recommendation triggers internal broadcast call (verified in API logs)
- Table row updates in-place after publish (no full page reload)

---

## Phase 8 — ARQ Worker: Immediate Notifications via Redis

**Goal:** On recommendation publish, both Telegram and Email notifications sent immediately via ARQ job queue backed by local Redis.

### Why ARQ
- Redis already installed locally on the server (`redis://localhost:6379`)
- ARQ is async-native (asyncio), no polling delay — job picked up in < 1 second
- Jobs survive worker restart (stored in Redis until processed)
- Built-in retry with configurable backoff

### Tasks
- [ ] **8.1** Add ARQ worker entry point
  - `src/pitchcopytrade/worker/arq_worker.py`
  - Define `WorkerSettings` with `functions`, `redis_settings`, `max_jobs`, `job_timeout`
  - Redis URL from `settings.redis_url` (default: `redis://localhost:6379/0`)
  - Update `worker/main.py` to launch ARQ worker instead of sleep loop

- [ ] **8.2** Define notification job function
  - `src/pitchcopytrade/worker/jobs/notifications.py`
  - `async def send_recommendation_notifications(ctx, recommendation_id: str)`
  - Fetch recommendation + legs + strategy from DB
  - Fetch all subscribers with `Subscription.status = active` for this strategy
  - For each subscriber:
    - If `telegram_user_id` set → POST to `http://bot:8080/internal/broadcast`
    - If `email` set → send via SMTP (aiosmtplib)
  - Retries: 3, retry delay: 10s, timeout: 60s

- [ ] **8.3** Enqueue job at publish time
  - In `POST /cabinet/recommendations/{id}/publish` handler:
    ```python
    await arq_pool.enqueue_job("send_recommendation_notifications", str(rec.id))
    ```
  - `arq_pool` injected via FastAPI dependency (created at startup, stored on `app.state`)
  - Publish endpoint returns immediately after enqueue — no waiting for notifications

- [ ] **8.4** Email template
  - `src/pitchcopytrade/templates/email/recommendation.html` — Jinja2 HTML
  - `src/pitchcopytrade/templates/email/recommendation.txt` — plain text fallback
  - aiosmtplib sends multipart/alternative (HTML + text)
  - SMTP settings: `relay.ptfin.kz:465 SSL`, from `pct@ptfin.ru` (from env)

- [ ] **8.5** ARQ dependency in docker-compose
  - Worker service CMD: `python -m arq pitchcopytrade.worker.arq_worker.WorkerSettings`
  - Worker connects to Redis on host network (if Redis is on host OS, use `host.docker.internal` or host IP)
  - OR: add Redis as Docker service if preferred later

### Acceptance Criteria
- Published recommendation → notifications sent within 2 seconds
- Worker log shows job picked up immediately (no 30s wait)
- Failed SMTP → job retried 3 times, then marked failed in ARQ
- `arq info redis://localhost:6379/0` shows job history

---

## Phase 9 — Telegram Mini App (Subscriber)

**Goal:** Subscriber can browse strategies, view One Pager, and initiate subscription.

### Tasks
- [ ] **9.1** Mini App entry point
  - Bot `/start` command → sends "Открыть приложение" inline keyboard button (WebApp)
  - WebApp URL: `{BASE_URL}/app/`

- [ ] **9.2** Mini App pages (Jinja2, HTMX, mobile-optimised)
  - `GET /app/` — list of published strategies (title, author, subscriber count)
  - `GET /app/strategy/{slug}` — One Pager (HTML, full screen)
  - `GET /app/tariffs` — subscription products with prices
  - `GET /app/subscribe/{product_id}` — subscription checkout (stub: shows manual payment instructions)
  - `GET /app/my` — subscriber's active subscriptions

- [ ] **9.3** Subscriber identification in Mini App
  - Telegram Mini App passes `initData` in header / JS
  - `GET /app/auth` — verify `initData` signature, create/get User, return session token
  - All `/app/*` routes require valid Mini App session

- [ ] **9.4** Subscription checkout (stub)
  - Shows: "Переведите {amount} руб. по реквизитам: ... и нажмите 'Я оплатил'"
  - `POST /app/subscribe/{product_id}/claim` → creates Payment(status=pending) + Subscription(status=pending)
  - Admin confirms manually in ЛК администратора (Phase 4.5)

### Acceptance Criteria
- Subscriber can open Mini App from bot, see strategies list, tap through to One Pager
- Subscription claim creates records in DB visible in admin payments page

---

## Phase 10 — Hardening & Tests

**Goal:** Core flows covered by tests. No regressions.

### Tasks
- [ ] **10.1** Auth tests
  - Telegram HMAC verification (valid / expired / tampered)
  - Protected routes return 401 without valid session
  - Role checks: author cannot access `/admin/*`

- [ ] **10.2** Recommendation tests
  - Create recommendation with minimal fields (ticker + side only)
  - Create recommendation with all fields
  - Publish triggers notification_queue entry
  - ACL: author A cannot publish author B's recommendations

- [ ] **10.3** Broadcast mock test
  - Internal broadcast endpoint called with valid/invalid token
  - 401 on bad token, 200 on valid

- [ ] **10.4** Worker test
  - Email queue processing: pending → sent
  - Retry logic on failure

---

## Implementation Notes

### Naming Conventions
- Routes: `/cabinet/` for author, `/admin/` for admin, `/app/` for Mini App, `/api/` for JSON endpoints, `/auth/` for auth
- Templates: `templates/{section}/{name}.html`
- Services: `src/pitchcopytrade/services/{domain}.py`

### HTMX Patterns
- Use `hx-target` + `hx-swap="outerHTML"` for row updates
- Use `hx-boost` on nav links for SPA-like feel without JS framework
- Inline add row: `hx-post` + `hx-swap="afterbegin"` on tbody

### No Legacy Policy
- Before each phase: run `git status` — no uncommitted files from previous attempts
- Before deploy: run `scripts/reset.sh` to guarantee clean state
- No commented-out code, no TODO left in production paths
