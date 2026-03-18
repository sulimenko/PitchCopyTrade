# PitchCopyTrade — Code Review Checklist
> Version: 0.2.0
> Updated: 2026-03-18
> Use this checklist on every PR before merge

---

## P0 — Blockers (must fix before any merge)

### Security
- [ ] No raw SQL string interpolation — use SQLAlchemy bound params only
- [ ] Telegram HMAC-SHA256 verified on every auth callback (`auth_date` < 5 min)
- [ ] Telegram Mini App `initData` signature verified before trusting user identity
- [ ] `X-Internal-Token` verified on `/internal/broadcast` — hard-block without it
- [ ] JWT: HttpOnly + Secure + SameSite=Strict, expiry ≤ 24h
- [ ] No secret values (tokens, passwords, keys) committed or logged
- [ ] Author can only read/write their own strategies and recommendations (ACL by `author_profile.id`)
- [ ] Admin routes protected by `require_role("admin")`
- [ ] Subscriber cannot access author cabinet or admin cabinet

### Data Integrity
- [ ] `RecommendationLeg.instrument_id` resolved from ticker — no orphan legs
- [ ] `Recommendation.status` transitions only follow allowed path: draft → published → closed/cancelled
- [ ] `Payment.final_amount_rub` computed server-side, never trusted from client
- [ ] `Subscription` created only after payment reaches `paid` status (or manual confirm by admin)

### Notifications
- [ ] Internal broadcast call is **fire-and-forget** — publication not blocked if bot is down
- [ ] Broadcast errors logged, not swallowed silently
- [ ] `notification_queue` entries created atomically with recommendation publish (same DB transaction)

---

## P1 — High Priority

### Role & ACL
- [ ] 3 roles in DB: admin, author, (moderator kept but unused)
- [ ] `requires_moderation=False` on all MVP AuthorProfiles — no route checks moderation status
- [ ] Author created by admin only — no self-registration path
- [ ] `telegram_user_id` uniqueness enforced at DB level + application level

### Recommendation Logic
- [ ] Minimal required fields enforced: `ticker` + `side` only on inline create
- [ ] All price fields (`entry_from`, `tp1`, `stop_loss`) nullable — blank = NULL, not 0
- [ ] `RecommendationKind` defaults to `new_idea` on quick inline create
- [ ] `published_at` set to server UTC time, never client time
- [ ] Duplicate publish prevented (idempotency check: status must be `draft` to publish)

### Instruments
- [ ] Instruments seeded from `doc/instruments_stub.json` on startup (upsert by ticker)
- [ ] `GET /api/instruments` returns only `is_active=True` instruments
- [ ] Ticker picker search is case-insensitive
- [ ] `last_price` and `change_pct` fields present in response (stub values OK in MVP)

### UI / Templates
- [ ] No onboarding text, no instruction blocks, no "how to use" tooltips anywhere
- [ ] Empty tables show minimal empty state ("Нет рекомендаций"), not placeholder rows
- [ ] Ticker picker popup closes on Esc and on backdrop click
- [ ] Inline row resets after successful save (fields cleared)
- [ ] HTMX responses return correct `HX-Trigger` or swap targets — no full page reloads on actions
- [ ] All user-facing text in Russian

### Database
- [ ] New Alembic migration for `notification_queue` table exists
- [ ] Migration is reversible (`downgrade` implemented)
- [ ] No raw `CREATE TABLE` in application code — migrations only
- [ ] `Base.metadata` includes all models before `env.py` runs

---

## P2 — Standard Quality

### Code Style
- [ ] No unused imports
- [ ] No commented-out code blocks
- [ ] No `print()` — use `logging` module
- [ ] Functions under 50 lines (split larger ones)
- [ ] No magic strings — use enums from `db/models/enums.py`

### API Design
- [ ] JSON API endpoints under `/api/` prefix
- [ ] HTMX partial endpoints under `/cabinet/` or `/admin/` prefix
- [ ] Error responses return appropriate HTTP status codes (400/401/403/404/422/500)
- [ ] 422 body includes field-level validation errors for form submissions

### Configuration
- [ ] All new config values added to `core/config.py` with type annotations and defaults
- [ ] New env vars documented in `.env.example` (if file exists) or README
- [ ] No hardcoded URLs, ports, or secrets

### Tests
- [ ] New route has at least one test
- [ ] ACL test: unauthorized access returns 401/403
- [ ] Happy path test: valid input returns expected response

---

## P3 — Product Drift Checks

These check that implementation doesn't drift from approved blueprint:

- [ ] Author cabinet is web-only, no Telegram bot commands for authors
- [ ] Subscriber flow is Telegram bot + Mini App only, no separate web registration
- [ ] One Pager is HTML stored in `Strategy.full_description`, rendered server-side
- [ ] Payment confirmation is manual (admin action) — no automatic payment API calls
- [ ] Moderator role: enum exists, no UI, no enforcement, `requires_moderation=False`
- [ ] MinIO: infrastructure up, but no upload routes in MVP
- [ ] Bot mode: `USE_WEBHOOK=true` in production, `USE_WEBHOOK=false` in local dev
- [ ] Instruments sourced from `instruments_stub.json` only — no live market API calls in MVP

---

## Reviewer Sign-off

| Check Area       | Reviewer | Date | Result |
|-----------------|----------|------|--------|
| P0 Security      |          |      | Pass / Fail |
| P0 Data Integrity|          |      | Pass / Fail |
| P0 Notifications |          |      | Pass / Fail |
| P1 ACL/Roles     |          |      | Pass / Fail |
| P1 Recommendations|         |      | Pass / Fail |
| P1 UI/Templates  |          |      | Pass / Fail |
| P2 Code Quality  |          |      | Pass / Fail |
| P3 Product Drift |          |      | Pass / Fail |

PR can merge only when all P0 and P1 items pass.
