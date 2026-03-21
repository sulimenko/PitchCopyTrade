# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-20
> Этот файл хранит только текущие findings и gate на следующий merge.

## Общий вывод

Кодовая база MVP стабильна. Алембик удалён, схема переведена на `deploy/schema.sql`. UX-блоки A–Q закрыты. Система поднята на новом сервере (`cloud-001`), все три сервиса (api, bot, worker) запускаются штатно. Обнаружены инфраструктурные и UX дефекты, требующие устранения.

---

## Критические findings (блокируют продакшн)

### R1 — pg_hba.conf не пускает Docker-контейнеры в postgres **[BLOCKER]**

**Симптом:**
```
ERROR | Instrument seeder failed: в pg_hba.conf нет записи для компьютера "172.21.0.4",
       пользователя "pct", базы "pct", SSL выкл.
```

**Причина:** Postgres на хосте слушает только `127.0.0.1/32`. Docker-контейнеры подключаются через `host.docker.internal`, но postgres видит source IP контейнера (`172.21.x.x` или `172.20.x.x` — зависит от конкретной docker-сети). Правила для этих подсетей в `pg_hba.conf` отсутствуют.

**Примечание:** `docker-compose.server.yml` объявляет `subnet: 172.20.0.0/24`, но контейнер получил `172.21.0.4` — Docker выбрал следующую свободную подсеть. Правило должно покрывать оба диапазона.

**Исправление:**
```bash
# Найти pg_hba.conf
sudo -u postgres psql -c "SHOW hba_file;"

# Добавить строку (пример для CentOS: /var/lib/pgsql/data/pg_hba.conf)
echo "host    pct    pct    172.0.0.0/8    md5" | sudo tee -a /var/lib/pgsql/data/pg_hba.conf

# Перечитать конфиг без перезапуска
sudo systemctl reload postgresql
```

**Последствия пока не исправлено:** seeders падают при каждом старте, инструменты и admin-пользователь не создаются, DB не инициализируется.

---

### R2 — ARQ-worker не запущен, notifications при немедленном publish не доставляются **[BLOCKER]**

**Причина:** В системе два worker-пути:

| Путь | Файл | Запущен? |
|------|------|---------|
| Polling loop (cron-like) | `worker/main.py` → `placeholders.py` | ✅ да (docker-compose) |
| ARQ queue worker | `worker/arq_worker.py` | ❌ нет |

`docker-compose.server.yml` запускает `python -m pitchcopytrade.worker.main` — это polling loop. ARQ-worker (`arq_worker.py`) не запускается.

**Что ломается:** Когда автор публикует рекомендацию немедленно (не scheduled), `services/publishing.py` вызывает:
```python
await arq_pool.enqueue_job("send_recommendation_notifications", recommendation_id=...)
```
Задача попадает в Redis, но обработчик не работает — notifications молча теряются.

**Что работает:** Scheduled-publish через polling worker доставляет notifications через `services/notifications.py` — этот путь исправен.

**Исправление:** Запустить ARQ worker как отдельный сервис (добавить в docker-compose) ИЛИ убрать дублирование кодпатей и обрабатывать все notifications через polling.

---

## Medium findings

### R3 — `aiohttp` импортируется, но не объявлен в зависимостях

**Файл:** `worker/jobs/notifications.py`, строка 93: `import aiohttp`

`aiohttp` отсутствует в `pyproject.toml`. В production-образе пакет может быть доступен как транзитивная зависимость `uvicorn[standard]`, но это ненадёжно. `httpx` уже объявлен явно и пригоден для того же.

**Исправление:** Заменить `aiohttp` на `httpx` в `worker/jobs/notifications.py`.

---

### R4 — Два параллельных кодпати для recommendation notifications

`services/notifications.py` → вызывается polling worker, broadcast через direct Telegram bot call.
`worker/jobs/notifications.py` → ARQ job, дополнительно отправляет email.

Оба делают одно: рассылку при publish. Canonical path должен быть один. Для MVP достаточно polling-пути (`services/notifications.py`); ARQ-job можно либо удалить, либо сделать основным и убрать дублирование.

---

## Housekeeping (не блокируют)

- **Alembic удалён** — `alembic.ini`, `alembic/` папка, зависимость в `pyproject.toml` отсутствуют. Схема переведена на `deploy/schema.sql`. ✅
- **Блоки F0–F3** (`task.md`) остаются открытыми — db/file parity для staff governance. Не блокируют первый запуск.
- **`db/session.py`** создаёт engine на уровне импорта — нормально для production, усложняет unit-tests. Не критично для MVP.
- **`worker/main.py`** спит 3600 секунд между циклами — для scheduled notifications достаточно, но задержка может быть до 1 часа от времени создания.

---

## Новые findings (2026-03-21)

### S2 — Mixed Content: статика генерирует HTTP-ссылки на HTTPS-сайте

`request.url_for('static', ...)` в Starlette использует scheme входящего запроса. За nginx-proxy контейнер видит HTTP → генерирует `http://`-ссылки → браузер блокирует. Задача S2 в `task.md`.

### U6 — Internal Server Error при «Создать» в рекомендациях

`POST /author/recommendations` с `inline_mode=1` возвращает 500. Вероятные причины: отсутствие `kind` в inline форме, пустой `strategy_id`, FK constraint на `instrument_id`. Задача U6 в `task.md`.

### U5 — Popup тикера обрезается внутри таблицы

`id="inline-ticker-popup"` с `position: absolute` внутри контейнера с `overflow: hidden`. Задача U5.

---

## Gate на следующий merge

1. Mixed Content устранён — статика отдаётся по HTTPS (S2)
2. `POST /author/recommendations` inline не возвращает 500 (U6)
3. Popup тикера виден целиком (U5)
4. Notifications при немедленном publish доставляются (R2)
5. Блоки F0–F3 закрыты

---

## Worker target

Следующий исполнитель должен брать как canonical source:
- `doc/blueprint.md` — архитектура MVP
- `doc/task.md` — backlog задач

Исторические completed phases не использовать как источник правды.
