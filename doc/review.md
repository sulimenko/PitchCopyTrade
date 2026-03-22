# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-22
> Этот файл хранит только текущие findings и gate на следующий merge.

## Общий вывод

Блоки S, R, T, U, V, W полностью закрыты. ARQ/Redis удалены из зависимостей и кода. Notification pipeline унифицирован на прямую доставку с per-item exception handling. Инфраструктура поддерживает два варианта развёртки. Staff shell viewport-фиксирован. Author editor работает без 500.

Открытых production bug нет. Следующий приоритет: V3 (ручной smoke-test) → Блок F (governance parity).

---

## Инвентарь проекта (снапшот 2026-03-22)

### Сервисы
| Сервис | Entry point | Статус |
|--------|-------------|--------|
| API | `api/main.py` — FastAPI, HTMX, Mini App | ✅ работает |
| Bot | `bot/main.py` — aiogram 3, polling/webhook | ✅ работает |
| Worker | `worker/main.py` — polling loop, 4 jobs | ✅ работает |

### Worker jobs (4 активных)
| Job | Файл | Интервал |
|-----|------|----------|
| `scheduled_publish` | `placeholders.py` | 3600 сек |
| `payment_expiry_sync` | `placeholders.py` | 3600 сек |
| `subscription_expiry` | `placeholders.py` | 3600 сек |
| `reminder_jobs` | `placeholders.py` | 3600 сек |

### Режимы хранения
- **`file`** (default/demo): JSON в `storage/runtime/json/`, blobs в `storage/runtime/blob/`
- **`db`**: PostgreSQL через SQLAlchemy 2 async + asyncpg; схема в `deploy/schema.sql`

### Маршруты (100+ endpoints)
| Префикс | Назначение |
|---------|-----------|
| `/admin/*` | Административный кабинет (staff) |
| `/cabinet/*` | Кабинет автора (HTMX, legacy path) |
| `/author/*` | Кабинет автора (новый path, FileRepo + SqlAlchemy) |
| `/moderation/*` | Очередь модерации |
| `/app/*` | Telegram Mini App |
| `/api/*` | JSON API (instruments, health, ready, meta) |
| `/auth/*` | Аутентификация (Telegram Widget, WebApp, staff) |
| `/` | Публичный каталог, checkout |

### Тестовое покрытие
| Модуль | Тестов |
|--------|--------|
| test_admin_ui.py | 50 |
| test_auth_ui.py | 27 |
| test_author_ui.py | 23 |
| test_access_delivery.py | 19 |
| test_public_catalog_checkout.py | 13 |
| test_author_services.py | 11 |
| test_worker_baseline.py | 9 |
| test_bot_baseline.py | 9 |
| прочие (17 файлов) | ~137 |
| **Итого** | **~298** |

### Зависимости (pyproject.toml)
```
fastapi, uvicorn[standard], aiogram, sqlalchemy, greenlet,
asyncpg, jinja2, pydantic-settings, python-multipart,
email-validator, httpx, aiosmtplib
```
`arq` и `redis` удалены (Блок V1).

---

## Закрытые блоки (подтверждено в коде)

### Блок S — Инфраструктура ✅

**S1 — Docker-compose двухрежимный:**
- `deploy/docker-compose.server.yml` параметризирован через `DOCKER_NETWORK_EXTERNAL`, `DOCKER_NETWORK_NAME`, `API_PORT_BINDING`
- Standalone (Вариант А): postgres/redis на хосте через `host.docker.internal`
- Shared backend (Вариант Б): внешняя сеть, DNS aliases, без проброса портов
- `x-pct-service` YAML anchor убирает дублирование
- `deploy/env.server.example` описывает оба варианта
- `deploy/migrate.sh` использует `PGPASSWORD` + `-h/-p`; `POSTGRES_HOST/PORT` из `.env.server`

**S2 — HTTPS Mixed Content:**
- Uvicorn запускается с `--proxy-headers --forwarded-allow-ips='*'`
- FastAPI читает `X-Forwarded-Proto` → static URL генерируются с `https://`

---

### Блок R — Notification pipeline ✅

- ARQ pool **отключён** в `api/lifespan.py` (`app.state.arq_pool = None`)
- `services/notifications.py` — canonical path: `deliver_recommendation_notifications_by_id()` + `deliver_recommendation_notifications()`
- Immediate publish (cabinet, author, moderation): прямой вызов `deliver_*` в route handler
- Scheduled publish: polling worker через `run_scheduled_publish()` → `deliver_recommendation_notifications()`
- Оба режима хранения (file/db) покрыты отдельными функциями
- `aiohttp` удалён, используется `httpx`

**V1 cleanup:**
- `worker/arq_worker.py` удалён
- `arq` и `redis` удалены из `pyproject.toml`
- `cabinet.py` publish: ARQ-блок заменён на `deliver_recommendation_notifications_by_id`

---

### Блок T — Staff shell ✅

- «Авторы» убраны из nav; управление через «Команда»
- `.staff-shell { height: 100vh; overflow: hidden }` — viewport-фиксированный layout
- `.staff-grid-shell { flex: 1; min-height: 0 }` — AG Grid заполняет оставшееся пространство

---

### Блок U — Author editor ✅

- **U1**: После создания стратегии redirect на `/author/strategies` (список)
- **U2**: Compact table: borders hairline, row height 28–30px
- **U3**: «Идея» и «Бумага» в одной строке inline shortcut
- **U5**: Ticker popup в `position: fixed`, не клипается shell
- **U6**: `POST /author/recommendations` не возвращает 500; `kind=new_idea` добавлен
- **U7**: `recommendation_form.html` имеет явный `action` — нет self-submit на `/new`
- **U8**: `embedded_base.html` создан; dynamic extends `{% extends "embedded_base.html" if embedded else "staff_base.html" %}`

---

## Закрытые findings (Блок W)

### Блок W — Code quality cleanup ✅

**W1 — Notification loop per-item exception handling** ✅
`worker/jobs/placeholders.py` — оба цикла (file mode строки 66–75, db mode строки 87–90) теперь обёрнуты в `try/except Exception: logger.exception(...)`. Ошибка Telegram для одной рекомендации не прерывает доставку остальных.

**W2 — Enum comparison в moderation.py** ✅
`moderation.py:104` — `updated.status == RecommendationStatus.PUBLISHED` (было `updated.status.value == "published"`).

**W3 — Удалён мёртвый `worker/jobs/notifications.py`** ✅
ARQ-handler удалён. Связанные тесты удалены из `test_worker_baseline.py`. `compileall` чистый.

**W4 — env.server.example** ✅
Комментарии "ARQ + Redis" заменены. `REDIS_URL` остаётся (нужен как поле конфига), с пояснением что ARQ не используется.

**W5 — Unused import `func` в cabinet.py** ✅
`from sqlalchemy import func, select` → `from sqlalchemy import select`.

---

## Открытые findings

### F0 — Governance: последний активный администратор `[ ]` — не блокирует MVP

`update_admin_staff_user` должен запрещать снятие роли `admin` у последнего активного администратора через edit-path (governance contract уже реализован для `roles/admin/remove`).

### F1 — Control emails: db/file parity `[ ]`

`db` и `file` path должны одинаково отправлять уведомления администраторам при staff onboarding.

### F2 — db/file parity verification `[ ]`

Проверить coverage: create, resend, oversight mail, audit log — одинаково в обоих режимах.

### F3 — Regression coverage F0–F2 `[ ]`

Тесты на: governance защита через edit, `active/inactive` flow, oversight emails в file mode.

---

## Gate на следующий merge

Блоки S, R, T, U, V, W — закрыты. Следующий merge **не блокирован**.

Открытых production bug нет.

Блок F — не является production blocker для MVP. Закрыть до первого коммерческого запуска (реальные деньги).

V3 (smoke-test) — ручная проверка на живом сервере. Не блокирует merge.

---

## Worker target

Следующий исполнитель:
- Canonical source: `doc/blueprint.md`, `doc/task.md`
- **V3** — ручной smoke-test на живом сервере (создать подписчика → рекомендацию → опубликовать → проверить Telegram-уведомление)
- После V3: **Блок F** (F0 — governance parity через staff edit)
