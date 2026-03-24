# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-24
> Этот файл хранит только текущие findings и gate на следующий merge.

---

## Общий вывод

Блоки S, R, T, U, V, W, X1, Y, X3, X4, Z (Z1–Z8), **TAB** полностью закрыты. Инфраструктура двухрежимная. ARQ/Redis удалены. Notification pipeline унифицирован. Staff shell viewport-фиксирован. Author editor без ошибок. Mini App auth исправлен, redirect на витрину, онбординг убран. Inline-форма восстановлена (autoHeight). **AG Grid полностью заменен на Tabulator 6** (14 шаблонов переписаны, bundle 1.4 MB → ~150 KB, 0 console errors). UUID-валидация всех admin path-параметров. Invite flow с bot deep link. OAuth 2.0 (Google/Яндекс) с кнопками на /login. Ghost user recovery. Oversight emails.

**Production bug-ов нет.** Merge не блокирован.

---

## Инвентарь проекта (снапшот 2026-03-22)

### Сервисы
| Сервис | Entry point | Статус |
|--------|-------------|--------|
| API | `api/main.py` — FastAPI, HTMX, Mini App | ✅ работает |
| Bot | `bot/main.py` — aiogram 3, polling + webhook | ✅ работает |
| Worker | `worker/main.py` — polling loop, 4 jobs | ✅ работает |

### Worker jobs (4 активных)
| Job | Файл | Интервал |
|-----|------|----------|
| `scheduled_publish` | `placeholders.py` | 3600 сек |
| `payment_expiry_sync` | `placeholders.py` | 3600 сек |
| `subscription_expiry` | `placeholders.py` | 3600 сек |
| `reminder_jobs` | `placeholders.py` | 3600 сек |

### Хранение
- **`file`** (default/demo): JSON в `storage/runtime/json/`, blobs в `storage/runtime/blob/`
- **`db`**: PostgreSQL через SQLAlchemy 2 async + asyncpg; схема `deploy/schema.sql`

### Маршруты
| Префикс | Назначение |
|---------|-----------|
| `/admin/*` | Административный кабинет (staff) |
| `/cabinet/*` | Кабинет автора (HTMX, legacy path) |
| `/author/*` | Кабинет автора (новый path) |
| `/moderation/*` | Очередь модерации |
| `/app/*` | Telegram Mini App (подписчики) |
| `/api/*` | JSON API |
| `/auth/*` | Аутентификация (Telegram Widget, OAuth 2.0) |
| `/` | Публичный каталог, checkout |

### Аутентификация (4 способа)
| Способ | Роуты | Назначение |
|--------|-------|-----------|
| Telegram Login Widget | `/auth/telegram/callback` | Staff: привязка Telegram ID |
| Telegram Mini App initData | `POST /tg-webapp/auth` | Подписчики: вход из бота |
| Google OAuth 2.0 | `/auth/google` → `/auth/google/callback` | Staff: вход по email |
| Яндекс OAuth 2.0 | `/auth/yandex` → `/auth/yandex/callback` | Staff: вход по email |

### Зависимости (pyproject.toml)
```
fastapi, uvicorn[standard], aiogram, sqlalchemy, greenlet,
asyncpg, jinja2, pydantic-settings, python-multipart,
email-validator, httpx, aiosmtplib, authlib
```
`arq` и `redis` удалены (Блок V1).

---

## Закрытые блоки

### Блок S — Инфраструктура ✅
- `docker-compose.server.yml` параметризован: `DOCKER_NETWORK_EXTERNAL`, `DOCKER_NETWORK_NAME`, `API_PORT_BINDING`
- Standalone и shared-backend варианты без правки yml
- `deploy/migrate.sh` использует `PGPASSWORD` + `-h/-p`
- uvicorn: `--proxy-headers --forwarded-allow-ips='*'` для HTTPS static URLs

### Блок R — Notification pipeline ✅
- ARQ pool отключён (`app.state.arq_pool = None`)
- Immediate publish: прямой вызов `deliver_recommendation_notifications_by_id()` в route handlers
- Scheduled publish: polling worker → `run_scheduled_publish()` → `deliver_recommendation_notifications()`
- File и db режимы покрыты отдельными путями

### Блок T — Staff shell ✅
- `height: 100vh; overflow: hidden` — viewport-фиксирован
- AG Grid в `flex: 1; min-height: 0` заполняет оставшееся пространство

### Блок U — Author editor ✅
- U7: явный `action` на форме рекомендации
- U8: `embedded_base.html` — modal без staff rail
- U6: inline create без 500

### Блок V — ARQ cleanup ✅
- `worker/arq_worker.py` удалён
- `arq`, `redis` удалены из `pyproject.toml`
- `cabinet.py` publish: прямая доставка через `deliver_recommendation_notifications_by_id`

### Блок W — Code quality ✅
- W1: per-item exception handling в notification loops (`placeholders.py`)
- W2: enum comparison в `moderation.py`
- W3: `worker/jobs/notifications.py` удалён
- W4/W5: cleanup

### Блок X1 — Mini App auth ✅
- `GET /app` без аутентификации рендерит `app/miniapp_entry.html`
- JS: `Telegram.WebApp.initData` → POST `/tg-webapp/auth` → `redirect_url` → navigate
- Fallback: кнопка «Войти» для браузерного контекста

### Блок Y — Security & reliability fixes ✅
- **Y1**: Invite token race condition — rollback `invite_token_version` при SMTP failure
- **Y2**: SMTP timeout — `asyncio.wait_for(..., timeout=10.0)`
- **Y3**: Startup placeholder validation — `bootstrap_runtime()` → `validate_runtime_settings()`
- **Y4**: Open redirect — `_sanitize_subscriber_next_path()`

### Блок X3 — Staff invite via bot deep link ✅
- Invite email: `https://t.me/{bot}?start=staffinvite-XXX` как PRIMARY способ
- Бот `/start staffinvite-XXX` → WebApp с invite URL

### Блок X4 — Google/Yandex OAuth 2.0 ✅
- Config: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`
- `authlib>=1.3` в зависимостях
- Routes + callbacks + CSRF state cookie
- Кнопки в login.html с условным отображением

### Блок Z — UI bugs + production fixes ✅
- **Z1**: Ghost user recovery — обновление бесролевого user вместо ошибки уникальности
- **Z2**: AG Grid иконки — CSS скрывает сломанные icon-font элементы
- **Z3**: Inline form — skip rows в `<table><tbody>` wrapper
- **Z4**: OAuth кнопки в `login.html`
- **Z5**: Mini App redirect `/app/status` → `/app/catalog`
- **Z6**: UUID-валидация — `_validate_uuid()` helper во всех admin path-параметрах (promos, strategies, products, documents, staff, one-pager) → 404 вместо 500/DataError
- **Z7.1**: AG Grid floating filters — `floatingFilter: true` в defaultColDef, CSS скрывает `ag-floating-filter-button`
- **Z7.2**: Inline-форма видимость — `domLayout: "autoHeight"` при наличии skip rows
- **Z8**: Mini App entry — убран весь онбординг-текст, оставлены лого + спиннер + кнопка «Войти»
- **Z9.1**: Promo form action — явный `action` в promo_form, strategy_form, product_form, legal_form (create → `/admin/{entity}`, edit → `/admin/{entity}/{id}`)
- **Z9.2**: Inline-форма видимость — промежуточный fix (заменён Z10)
- **Z10**: Inline-форма вынесена из `<table>` — отдельный `<div>` с CSS Grid после `.staff-grid-shell`. Skip row механизм удалён из JS. `overflow: hidden` восстановлен.

### Блок TAB — AG Grid → Tabulator 6 миграция ✅
- **TAB.1**: Tabulator 6.3.0 vendor (JS + CSS), AG Grid полностью удален
- **TAB.2**: `tabulator-bootstrap.js` — единый API `PCTTabulator.create()`
- **TAB.3**: `tabulator-theme.css` — кастомная тема (badge styles встроены)
- **TAB.4**: `tabulator_assets.html` partial, включен в `staff_base.html`
- **TAB.5**: 14 route handlers + `_grid_serializers.py` (14 функций сериализации)
- **TAB.6**: Все 14 шаблонов переписаны: `<table>` → `<div id="grid-host">` + JSON инициализация
  - admin: strategies, authors, staff, products, subscriptions, payments, legal, promos, delivery, lead_analytics, metrics
  - author: strategies, recommendations
  - moderation: queue
- **TAB.7**: Tests обновлены (ag-grid references → tabulator), 0 ссылок на AG Grid в коде
- **TAB-FIX**: Все 14 сериализаторов исправлены — правильные имена атрибутов моделей, `_enum_str()` helper для enum safety, dict `.get()` для staff/author rows
- Bundle: 1.4 MB (AG Grid) → ~150 KB (Tabulator)
- Console errors `postProcessThemeChange` полностью устранены

### Блок P2 — Production UX fixes ✅
- **P2.1**: Фильтр по роли — `onchange="this.form.submit()"` на `<select>` в staff_list и authors_list
- **P2.2**: Дублирующие кнопки в топбаре убраны — остались только контекстные (Новая стратегия, Новый продукт, etc.)
- **P2.3**: Dashboard автора — карточки рекомендаций расширены: дата, тикер, направление (↑/↓), цены (вход, TP, стоп)
- **P2.4**: Фильтр по дате в `/author/recommendations` — поля `date_from`, `date_to` + серверная фильтрация
- **P2.5**: Inline-форма рекомендации — лейблы, выделенный фон, кнопки «Создать» (primary) / «Детально» (ghost)

### Fixes ✅
- **MissingGreenlet fix**: `_attach_legs` перемещён до `repository.flush()`
- **F1 — Oversight emails**: `_send_admin_oversight_email()` при staff onboarding

---

## Открытые findings

### F2 — db/file parity verification `[ ]` — не блокирует MVP

### F3 — Regression coverage `[ ]` — не блокирует MVP

---

## Операционные требования

- **BotFather domain**: `/setdomain` → `pct.test.ptfin.ru` для бота. Без этого `Telegram.WebApp.initData` будет пустым и Mini App покажет fallback.
- **OAuth credentials**: Зарегистрировать приложения в Google Cloud Console и Яндекс ID. Redirect URIs: `https://{DOMAIN}/auth/google/callback`, `https://{DOMAIN}/auth/yandex/callback`.
- **Redeploy**: После каждого merge — rebuild контейнеров:
  ```bash
  docker compose -f deploy/docker-compose.server.yml build --no-cache api
  docker compose -f deploy/docker-compose.server.yml up -d
  ```

---

## Gate на следующий merge

**Все блоки закрыты: S, R, T, U, V, W, X1, Y, X3, X4, Z (Z1–Z10), TAB, P2.**

**Production bug-ов нет.** Merge не блокирован.

F2–F3 — не блокируют MVP.

---

## Worker target

Следующий исполнитель (в порядке приоритета):
1. **V3** — ручной smoke-test на сервере: redeploy → проверить все 14 admin-страниц
2. **Блок F** — F2 parity audit, F3 regression coverage
