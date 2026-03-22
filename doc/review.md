# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-22
> Этот файл хранит только текущие findings и gate на следующий merge.

---

## Общий вывод

Блоки S, R, T, U, V, W, X1, Y, X3, X4 полностью закрыты. Инфраструктура двухрежимная. ARQ/Redis удалены. Notification pipeline унифицирован. Staff shell viewport-фиксирован. Author editor без ошибок. Mini App auth исправлен. Inline-форма создания рекомендации восстановлена. Invite flow с bot deep link. OAuth 2.0 (Google/Яндекс) реализован. Oversight emails реализованы.

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
- `GET /app` без аутентификации теперь рендерит `app/miniapp_entry.html`
- JS: `Telegram.WebApp.initData` → POST `/tg-webapp/auth` → `redirect_url` → navigate
- Fallback: кнопка «Войти» для браузерного контекста
- AG Grid bootstrap: `data-ag-grid-skip` строки вставляются после grid-контейнера (inline-форма восстановлена)
- AG Grid theme CSS: sort/filter иконки скрыты (no-font theme без юникод-артефактов)

### Блок Y — Security & reliability fixes ✅
- **Y1**: Invite token race condition — rollback `invite_token_version` при SMTP failure в `resend_staff_invite` (admin.py:1431–1443)
- **Y2**: SMTP timeout — `asyncio.wait_for(..., timeout=10.0)` в `_send_email_message`; при timeout → `FAILED` статус, не 500
- **Y3**: Startup placeholder validation — `bootstrap_runtime()` → `validate_runtime_settings()` проверяет `APP_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `INTERNAL_API_SECRET` через `_is_placeholder()`
- **Y4**: Open redirect — `_sanitize_subscriber_next_path()` нормализует backslash, запрещает `//` пути и внешние URL

### Блок X3 — Staff invite via bot deep link ✅
- Invite email содержит `https://t.me/{bot}?start=staffinvite-XXX` как PRIMARY способ входа
- Web-ссылка как альтернативный fallback
- Бот `/start staffinvite-XXX` открывает WebApp с invite URL

### Блок X4 — Google/Yandex OAuth 2.0 ✅ (код готов, credentials не настроены)
- Config: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET` (все optional, default None)
- `authlib>=1.3` в зависимостях
- Routes: `GET /auth/google` → consent → `GET /auth/google/callback`; аналогично для Яндекс
- Callback: поиск user по email → если найден → session cookie → redirect; если не найден → ошибка
- CSRF: state cookie с TTL 600 сек
- Кнопки в login.html скрыты если credentials не заданы (`google_oauth_enabled`, `yandex_oauth_enabled`)
- **X4.1 не закрыт**: нужна регистрация OAuth-приложений в Google Cloud Console и Яндекс ID

### Fixes ✅
- **MissingGreenlet fix**: `_attach_legs` перемещён до `repository.flush()` в `create_author_recommendation`
- **F1 — Oversight emails**: `_send_admin_oversight_email()` реализован — при staff onboarding все активные админы получают email о новом сотруднике

---

## Открытые findings (по приоритету)

### X4.1 — Регистрация OAuth credentials `[ ]` — INFO

**Действие:** Заказчик должен зарегистрировать OAuth-приложение:
- Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID
- Яндекс ID → https://oauth.yandex.ru/ → Создать приложение
- Redirect URIs: `https://{DOMAIN}/auth/google/callback`, `https://{DOMAIN}/auth/yandex/callback`
- Записать client_id + client_secret в `.env`

### F2 — db/file parity verification `[ ]` — не блокирует MVP

Базовые пути одинаковые. Риск drift при будущих изменениях. Нужен явный audit обоих путей.

### F3 — Regression coverage F1–F2 `[ ]` — не блокирует MVP

Тесты на: oversight emails в file mode, governance через edit path.

---

## Gate на следующий merge

**Блоки S, R, T, U, V, W, X1, Y, X3, X4** — закрыты. Merge **не блокирован**.

Открытых production bug-ов нет.

X4.1 (OAuth credentials) — операционная задача заказчика, не блокирует merge.
F2–F3 — не блокируют MVP.

V3 (smoke-test) — ручная проверка на сервере. Не блокирует merge.

---

## Worker target

Следующий исполнитель (в порядке приоритета):
1. **V3** — ручной smoke-test: создать подписчика → рекомендацию → опубликовать → уведомление
2. **Блок F** — F2 parity audit, F3 regression coverage
3. **X4.1** — регистрация OAuth credentials (заказчик)
