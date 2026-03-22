# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-22
> Этот файл хранит только текущие findings и gate на следующий merge.

---

## Общий вывод

Блоки S, R, T, U, V, W, X1 полностью закрыты. Инфраструктура двухрежимная. ARQ/Redis удалены. Notification pipeline унифицирован. Staff shell viewport-фиксирован. Author editor без ошибок. Mini App auth исправлен. Inline-форма создания рекомендации восстановлена через fix AG Grid bootstrap.

**Production bug-ов нет.** Два открытых finding не блокируют MVP: F1 (control emails) и invite token race condition.

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
| `/auth/*` | Аутентификация |
| `/` | Публичный каталог, checkout |

### Зависимости (pyproject.toml)
```
fastapi, uvicorn[standard], aiogram, sqlalchemy, greenlet,
asyncpg, jinja2, pydantic-settings, python-multipart,
email-validator, httpx, aiosmtplib
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

### Fixes этой сессии ✅
- **MissingGreenlet fix**: `_attach_legs` перемещён до `repository.flush()` в `create_author_recommendation` — рекомендации создаются корректно

---

## Открытые findings (по приоритету)

### Y1 — Invite token race condition при resend `[ ]` — WARNING

**Файл:** `src/pitchcopytrade/services/admin.py`, функция resend_staff_invite
**Проблема:** `invite_token_version` инкрементируется ДО отправки email. Если SMTP упал — старый токен инвалидирован, новый не доставлен. Пользователь заблокирован до следующего ручного resend.
**Контекст:** UI в `/admin/staff/{id}` показывает статус доставки и кнопку «Переслать». Admin может исправить вручную, но это friction.
**Severity:** WARNING — не падает, но UX плохой при SMTP проблемах.

---

### Y2 — Нет SMTP retry при отправке invite `[ ]` — WARNING

**Файл:** `src/pitchcopytrade/services/admin.py`, `_deliver_staff_invite()`
**Проблема:** Email отправляется в одну попытку синхронно (в рамках HTTP request). Нет retry, нет async queue. При SMTP timeout — request висит 30+ сек, user создан, email не доставлен.
**Severity:** WARNING для production с реальными пользователями.

---

### Y3 — Нет валидации `__FILL_ME__` vars при startup `[ ]` — INFO

**Файл:** `src/pitchcopytrade/core/config.py`
**Проблема:** Если `APP_SECRET_KEY=__FILL_ME__` остаётся в `.env`, приложение стартует без ошибки. Падение произойдёт только при первом вызове JWT-функции (auth, tokens).
**Рекомендация:** В lifespan добавить check на placeholder values для критических vars.

---

### Y4 — Open redirect в miniapp_entry.html `[ ]` — INFO

**Файл:** `src/pitchcopytrade/web/templates/app/miniapp_entry.html`, строка ~54
**Код:** `window.location.href = data.redirect_url || "/app/status"`
**Проблема:** `redirect_url` приходит от сервера `/tg-webapp/auth`. Если сервер вернёт абсолютный URL на внешний домен — браузер перейдёт туда. Сейчас сервер контролирует URL через `_sanitize_subscriber_next_path()`, но explicit validation в JS отсутствует.
**Fix:** `if (!data.redirect_url || !data.redirect_url.startsWith('/')) { ... }` перед навигацией.

---

### F0 — Governance: последний активный администратор ✅ (закрыто в коде)

Подтверждено при review: `update_admin_staff_user()` вызывает `_validate_admin_role_update_file/sql()` (admin.py:874) — governance contract реализован через edit-path. Пометить как закрытое.

---

### F1 — Control emails при staff onboarding `[ ]` — не блокирует MVP

`_deliver_staff_invite()` отправляет письмо только самому сотруднику. Blueprint требует также уведомлять активных администраторов ("oversight email"). Не реализовано. Допустимо до первого коммерческого запуска.

---

### F2 — db/file parity verification `[ ]` — не блокирует MVP

Базовые пути одинаковые. Риск drift при будущих изменениях. Нужен явный audit обоих путей.

---

### F3 — Regression coverage F1–F2 `[ ]` — не блокирует MVP

Тесты на: oversight emails в file mode, governance через edit path.

---

## Gate на следующий merge

**Блоки S, R, T, U, V, W, X1** — закрыты. Merge **не блокирован**.

Открытых production bug-ов нет.

Y1–Y3 — рекомендуется закрыть до коммерческого запуска.
F1–F3 — не блокируют MVP.

V3 (smoke-test) — ручная проверка на сервере. Не блокирует merge.

---

## Worker target

Следующий исполнитель (в порядке приоритета):
1. **Блок Y** — fix invite token race (Y1–Y3), open redirect (Y4) — см. doc/task.md
2. **Блок X3** — улучшить invite flow через бота (bot deep link в email)
3. **V3** — ручной smoke-test: создать подписчика → рекомендацию → опубликовать → уведомление
4. **Блок X4** — Google/Yandex OAuth (после настройки credentials у заказчика)
5. **Блок F** — F1 oversight emails, F2–F3 parity + coverage
