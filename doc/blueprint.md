# PitchCopyTrade — MVP Architecture Blueprint
> Version: 0.2.0 — MVP baseline
> Updated: 2026-03-18
> Status: **APPROVED for implementation**

---

## 1. Scope of MVP

MVP covers:
- Author Cabinet (web, Telegram auth) — create and publish recommendations
- Admin Cabinet (web) — create authors, publish One Pager, basic metrics
- CopyTradeBot (Telegram) — deliver recommendations to subscribers
- Instruments stub — 10 MOEX tickers, expandable via future API
- Subscriber Mini App (Telegram WebApp) — view strategies, tariffs, subscribe, pay

Out of scope for MVP:
- Moderator role enforcement (DB field exists, `requires_moderation = False` by default)
- External payment API (Tinkoff/T-Bank) — stub manual confirmation only
- Complex promo/trial/discount logic
- File attachments (MinIO not used in MVP routes, infrastructure stays)
- Compliance legal documents flow (tables exist, no UI)

---

## 2. Terminology

| Term in UI (RU)     | Term in code (EN)         | Notes |
|---------------------|---------------------------|-------|
| Рекомендация / Сделка | `Recommendation`        | Same entity. A recommendation can contain 1+ legs (trades on specific instruments). Most commonly 1 leg. |
| Нога сделки         | `RecommendationLeg`       | One instrument + side + price/target/stop |
| Стратегия           | `Strategy`                | Container grouping recommendations by author |
| Подписчик           | Subscriber / `User` with active `Subscription` | |
| Автор               | `AuthorProfile` linked to `User` | |
| Тикер               | `Instrument.ticker`       | E.g. SBER, GAZP |

---

## 3. System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐ │
│  │   api    │   │   bot    │   │  worker  │   │  postgres   │ │
│  │ FastAPI  │   │ aiogram3 │   │ asyncio  │   │  pg16-alpine│ │
│  │ port 8000│   │ webhook  │   │ bg jobs  │   │             │ │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └─────────────┘ │
│       │              │              │                           │
│       └──────────────┴──────────────┘                          │
│                  internal network                               │
│                                                                 │
│  ┌──────────┐                                                   │
│  │  minio   │  (infrastructure ready, not used in MVP routes)  │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘

External actors:
  Telegram API ←→ Bot (webhook on HTTPS, dedicated IP)
  Author Browser ←→ API (Author Cabinet web UI)
  Admin Browser ←→ API (Admin Cabinet web UI)
  Subscriber Telegram ←→ Bot + Mini App (WebApp inside Telegram)
```

---

## 4. Roles

| Role    | Access method       | How created              | Moderator enforcement |
|---------|--------------------|--------------------------|-----------------------|
| admin   | Web cabinet        | Seeded at deploy         | —                     |
| author  | Web cabinet (Telegram auth) | Admin creates in ЛК | `requires_moderation=False` in MVP |
| subscriber | Telegram bot + Mini App | Self-registration | — |

Moderator role: DB enum exists, no UI/enforcement in MVP.

---

## 5. Author Authentication Flow

Author cabinet is **web-only**. Auth via **Telegram Login Widget**.

```
1. Admin creates author in Admin Cabinet
   → fills: display_name, email (optional), telegram_user_id (optional)
   → system creates User + AuthorProfile + Role(author)
   → sends invite link to email and/or Telegram

2. Author opens web cabinet URL
   → clicks "Войти через Telegram"
   → Telegram Login Widget redirects with signed payload
   → API verifies HMAC-SHA256(bot_token, payload)
   → creates server session (JWT cookie, HttpOnly, Secure)
   → author lands in cabinet
```

No password. No Telegram bot interaction for author login. Author works exclusively via web browser.

---

## 6. Recommendation Creation UI

Two modes coexist on the same page:

### 6.1 Quick Inline (default)
- Table row with empty cells: `[Тикер ▼] [BUY|SELL] [Цена] [Цель] [Стоп] [+]`
- Clicking `Тикер` cell opens **Ticker Picker Popup** (see §8)
- Tab/Enter navigates between cells, Enter on last cell saves
- Row appears optimistically, saved async in background
- Other fields (title, thesis, horizon) auto-filled as null/empty

### 6.2 Full Popup (optional)
- Triggered by "Новая рекомендация" button above table
- Modal overlay with full form:
  - Strategy selector (dropdown)
  - Kind: new_idea / update / close / cancel
  - Title, Summary (optional)
  - Legs: repeatable block (Ticker + Side + Price + Target + Stop + Note)
  - Scheduled date (optional)
- Submit → creates recommendation with all legs

### 6.3 Table state on load
- Table is **empty on fresh load** — no placeholder rows, no seed data, no sample text
- Empty state: minimal text "Нет рекомендаций" + inline add row
- No onboarding tooltips, no instructions, no welcome modals

---

## 7. Ticker Picker

Triggered from any Ticker cell (inline or popup form).

```
┌─────────────────────────────────┐
│ 🔍 Поиск тикера...              │
├─────────────────────────────────┤
│ ★ SBER  Сбербанк       ▲+1.2%  │
│ ★ GAZP  Газпром        ▼-0.5%  │
│ ★ LKOH  ЛУКОЙЛ         ▲+0.8%  │
│   GMKN  Норильский никель       │
│   YNDX  Яндекс          ▲+2.1%  │
│   ...                           │
├─────────────────────────────────┤
│ [Отмена]                        │
└─────────────────────────────────┘
```

- Data source: `instruments_stub.json` (10 MOEX stocks, see §9)
- User's recent picks saved to `localStorage` and shown starred
- Future: search API endpoint returns additional tickers
- Real-time price: stub field `last_price` in JSON for now (will be replaced by live API)
- Filter by typing — client-side search on ticker + name

---

## 8. Recommendation Publishing & Notification

```
Author clicks "Опубликовать" on a draft recommendation
    │
    ▼
API: recommendation.status → "published", published_at = now()
    │
    └──► arq_pool.enqueue_job("send_recommendation_notifications", recommendation_id)
         Returns immediately — UI not blocked
              │
              ▼
         ARQ Worker (Redis-backed, local Redis on server)
              │
              ├──► Internal HTTP POST to bot service (Docker internal network)
              │    POST http://bot:8080/internal/broadcast
              │    Body: { recommendation_id }
              │    Bot fetches subscribers → sends Telegram message to each
              │
              └──► SMTP send to each subscriber with confirmed email
                   Server: relay.ptfin.kz:465 SSL
                   From: pct@ptfin.ru
```

### Why this approach:
- **ARQ + Redis** (Redis already installed on server): job enqueued instantly at publish time, worker picks it up in < 1 second — zero polling delay
- **Single job handles both channels** (Telegram + Email): atomic, one retry policy, one log entry
- **Reliable**: if worker crashes, jobs survive in Redis and resume on restart
- **Internal HTTP API** to bot: bot is on same Docker network, always reachable
- **No DB polling**: cleaner than 30s timer loops, lower DB load
- Bot runs in **webhook mode** on dedicated server — see README for activation

---

## 9. Bot Notification Message Format

```
📊 Новая рекомендация — {strategy.title}

{recommendation.title or kind_label}
{leg.ticker} — {leg.side} @ {leg.entry_from or "рынок"}
🎯 Цель: {leg.tp1 or "—"}
🛡 Стоп: {leg.stop_loss or "—"}

{recommendation.summary or ""}

[Открыть в приложении →]
```

---

## 10. Telegram Mini App (Subscriber)

Entry point: bot sends button "Открыть приложение" which opens WebApp URL.

Pages:
1. **Главная** — list of active strategies
2. **Стратегия / One Pager** — HTML page with strategy description, author, stats
3. **Тарифы** — subscription products with prices
4. **Подписка** — checkout flow (stub manual payment)
5. **Мои подписки** — subscriber's active subscriptions

One Pager = HTML template rendered server-side (Jinja2), embedded in Mini App iframe or served as full WebApp page.

---

## 11. Admin Cabinet

Pages:
1. **Авторы** — list of authors, create author (display_name, email, telegram_user_id)
2. **One Pager** — publish/edit strategy One Pager (HTML content editor)
3. **Метрики** — aggregated subscriber counts per strategy (authors see only own strategy counts)
4. **Выплаты** — accruals list, initiate payout (manual stub)

---

## 12. Database Conventions

- All tables have UUID PK, `created_at`, `updated_at`
- `requires_moderation = False` on all AuthorProfiles in MVP
- `RecommendationStatus.draft` → `published` only (skip review/approved/scheduled for MVP)
- On fresh deploy: **no seed data except admin user** — tables start empty
- Instruments loaded from `instruments_stub.json` via startup migration seeder

---

## 13. Notification Architecture (ARQ + Redis)

No `notification_queue` DB table needed — ARQ handles queue state in Redis.

```
Redis (local on server, redis://localhost:6379/0)
└── ARQ job queue
    └── job: send_recommendation_notifications(recommendation_id)
        ├── retries: 3
        ├── retry_delay: 10s
        └── timeout: 60s
```

ARQ worker runs as separate process (or inside the `worker` Docker service).
Failed jobs viewable via `arq info redis://...` CLI command.

### Email settings
- Server: `relay.ptfin.kz`
- Port: `465` (SSL)
- From: `pct@ptfin.ru`
- Credentials: in `.env` only, never committed

---

## 14. Fresh Deploy / Full Reset

See README.md § "Full Reset Procedure" for step-by-step cleanup before new version deploy.
No legacy code, no legacy data. Clean slate on every major version.

---

## 15. Design Principles

- **No instructions in UI** — interface is self-evident. No onboarding text, no "how to use" tooltips, no welcome screens.
- **Empty = clean** — all tables start empty, no placeholder/sample rows.
- **Minimal required fields** — only ticker + side mandatory for a recommendation leg. All price fields nullable.
- **Russian UI** — all user-facing text in Russian.
- **Mobile-first web** — author cabinet usable on mobile browser.
