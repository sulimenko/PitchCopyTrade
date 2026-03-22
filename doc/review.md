# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-22
> Этот файл хранит только текущие findings и gate на следующий merge.

---

## Общий вывод

Блоки S, R, T, U, V, W, X1, Y, X3, X4, Z полностью закрыты. Инфраструктура двухрежимная. ARQ/Redis удалены. Notification pipeline унифицирован. Staff shell viewport-фиксирован. Author editor без ошибок. Mini App auth исправлен, redirect на витрину. Inline-форма создания рекомендации восстановлена. Invite flow с bot deep link. OAuth 2.0 (Google/Яндекс) реализован с кнопками на /login. Ghost user recovery реализован. AG Grid иконки скрыты. Oversight emails реализованы.

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
- W2: enum comparison в `moderation.py` (`.status == RecommendationStatus.PUBLISHED`)
- W3: `worker/jobs/notifications.py` удалён
- W4: комментарии "ARQ + Redis" в `env.server.example` убраны
- W5: unused `func` import в `cabinet.py` удалён

### Блок X1 — Mini App auth ✅
- `GET /app` без аутентификации рендерит `app/miniapp_entry.html`
- JS: `Telegram.WebApp.initData` → POST `/tg-webapp/auth` → `redirect_url` → navigate
- Fallback: кнопка «Войти» для браузерного контекста

### Блок Y — Security & reliability fixes ✅
- **Y1**: Invite token race condition — rollback `invite_token_version` при SMTP failure
- **Y2**: SMTP timeout — `asyncio.wait_for(..., timeout=10.0)`; при timeout → `FAILED` статус, не 500
- **Y3**: Startup placeholder validation — `bootstrap_runtime()` → `validate_runtime_settings()`
- **Y4**: Open redirect — `_sanitize_subscriber_next_path()` нормализует backslash, запрещает `//`

### Блок X3 — Staff invite via bot deep link ✅
- Invite email: `https://t.me/{bot}?start=staffinvite-XXX` как PRIMARY способ
- Web-ссылка как fallback
- Бот `/start staffinvite-XXX` → WebApp с invite URL

### Блок X4 — Google/Yandex OAuth 2.0 ✅
- Config: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`
- `authlib>=1.3` в зависимостях
- Routes: `/auth/google` → consent → callback; аналогично для Яндекс
- Callback: поиск user по email → session cookie → redirect
- CSRF: state cookie с TTL 600 сек
- **X4.1**: credentials настроены заказчиком в `.env.server`

### Блок Z — UI bugs ✅
- **Z1**: Ghost user recovery — `_create_staff_user()` при email collision с бесролевым user обновляет существующую запись вместо ошибки
- **Z2**: AG Grid иконки — CSS скрывает `.ag-header-cell-menu-button`, `.ag-icon`, `.ag-filter-icon` + `suppressHeaderFilterButton: true`
- **Z3**: Inline form — skip rows оборачиваются в `<table class="pct-skip-row-wrapper"><tbody>` при перемещении из AG Grid
- **Z4**: OAuth кнопки — добавлена секция `auth-login-section--oauth` в `login.html` с условным отображением по `google_oauth_enabled`/`yandex_oauth_enabled`
- **Z5**: Mini App redirect — default subscriber redirect изменён с `/app/status` на `/app/catalog` (витрина стратегий) в miniapp_entry.html и auth.py

### Fixes ✅
- **MissingGreenlet fix**: `_attach_legs` перемещён до `repository.flush()`
- **F1 — Oversight emails**: `_send_admin_oversight_email()` — при staff onboarding все активные админы уведомляются

---

## Открытые findings

### F2 — db/file parity verification `[ ]` — не блокирует MVP

Базовые пути одинаковые. Риск drift при будущих изменениях. Нужен явный audit обоих путей.

### F3 — Regression coverage `[ ]` — не блокирует MVP

Тесты на: oversight emails в file mode, governance через edit path.

---

## Gate на следующий merge

**Блоки S, R, T, U, V, W, X1, Y, X3, X4, Z** — закрыты. Merge **не блокирован**.

Открытых production bug-ов нет.

F2–F3 — не блокируют MVP.

V3 (smoke-test) — ручная проверка на сервере. Не блокирует merge.

---

## Worker target

Следующий исполнитель (в порядке приоритета):
1. **V3** — ручной smoke-test: создать подписчика → рекомендацию → опубликовать → уведомление
2. **Блок F** — F2 parity audit, F3 regression coverage
