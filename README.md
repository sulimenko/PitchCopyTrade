# PitchCopyTrade

Telegram-first платформа для продажи подписок на инвестиционные стратегии и доставки торговых рекомендаций подписчикам.

Три роли: **Администратор** управляет авторами и платежами через веб-кабинет. **Автор** публикует рекомендации через веб-кабинет с авторизацией через Telegram. **Подписчик** работает через Telegram-бот и Mini App — без отдельного пароля.

Три сервиса в Docker: **api** (FastAPI, веб-кабинеты), **bot** (aiogram 3, Telegram), **worker** (ARQ, фоновые задачи и уведомления).

---

## Запуск на сервере

### Требования

- CentOS 8 / Ubuntu 22+ с Docker Engine и Docker Compose plugin
- Системный nginx
- DNS-запись домена указывает на IP сервера
- Открыт входящий порт `80/tcp` (и `443/tcp` при HTTPS)
- Telegram-бот создан через [@BotFather](https://t.me/BotFather), токен получен

---

### Шаг 1. Клонировать репозиторий

```bash
mkdir -p /var/www
cd /var/www
git clone <REPO_URL> pct
cd /var/www/pct
```

---

### Шаг 2. Создать конфигурационный файл

```bash
cp deploy/env.server.example .env.server
```

Открыть `.env.server` и заполнить обязательные поля:

```dotenv
APP_SECRET_KEY=           # длинная случайная строка, минимум 32 символа
BASE_URL=                 # https://ваш-домен.ru  (или http:// если без TLS)
ADMIN_BASE_URL=           # https://ваш-домен.ru/admin

TELEGRAM_BOT_TOKEN=       # токен от @BotFather
TELEGRAM_BOT_USERNAME=    # username бота без @
```

Остальные поля оставить как есть — дефолты рабочие для файлового режима.

> **Важно.** `.env.server` не коммитить. Токен бота не держать одновременно в polling на двух машинах.

---

### Шаг 3. Подготовить хранилище

```bash
mkdir -p /var/www/pct/storage/runtime/json
mkdir -p /var/www/pct/storage/runtime/blob
```

`storage/seed/` приходит из репозитория — трогать не нужно. При первом старте API автоматически скопирует seed-данные в `storage/runtime/`.

---

### Шаг 4. Установить nginx-конфиг

Скопировать готовый конфиг из репозитория:

```bash
cp deploy/nginx/pct.test.ptfin.ru.conf /etc/nginx/conf.d/ваш-домен.conf
```

Открыть скопированный файл и заменить `pct.test.ptfin.ru` на ваш домен.

Проверить и перезагрузить nginx:

```bash
nginx -t
systemctl reload nginx
```

nginx проксирует входящий трафик на `127.0.0.1:8110` — именно там слушает контейнер api.

---

### Шаг 5. Собрать и запустить контейнеры

```bash
cd /var/www/pct
docker compose -f deploy/docker-compose.server.yml build
docker compose -f deploy/docker-compose.server.yml up -d
```

Запускаются четыре контейнера: `pct-postgres`, `pct-api`, `pct-bot`, `pct-worker`.
`api` и остальные сервисы стартуют только после того, как postgres пройдёт healthcheck.

---

### Шаг 6. Проверить запуск

```bash
# статус контейнеров
docker compose -f deploy/docker-compose.server.yml ps

# логи (последние 50 строк каждого сервиса)
docker compose -f deploy/docker-compose.server.yml logs --tail=50 api
docker compose -f deploy/docker-compose.server.yml logs --tail=50 bot
docker compose -f deploy/docker-compose.server.yml logs --tail=50 worker
```

Проверить доступность через curl:

```bash
curl -I http://127.0.0.1:8110/health
curl -I http://ваш-домен.ru/login
```

---

### Шаг 7. Первый вход

Открыть в браузере `http://ваш-домен.ru/login`.

При первом запуске система автоматически создаёт администратора из seed-данных. Логин и пароль задаются переменными окружения `ADMIN_EMAIL` и `ADMIN_PASSWORD` в `.env.server` (если не заданы — используются дефолты из demo seed: `admin1` / `admin-demo-pass`).

После входа откроется `/admin/dashboard`.

**Что сделать сразу после входа:**
1. Перейти в раздел **Авторы** → создать первого автора (имя + Telegram User ID).
2. Передать автору адрес кабинета — он входит через Telegram Login Widget.
3. В Telegram открыть бота → `/start` → проверить, что кнопка Mini App появляется.

---

## Режим PostgreSQL

По умолчанию проект работает в файловом режиме (`APP_DATA_MODE=file`) — без PostgreSQL. Это подходит для быстрого старта и демо. Для production рекомендуется переключиться на PostgreSQL (`APP_DATA_MODE=db`).

### Что меняется в `.env.server`

```dotenv
APP_DATA_MODE=db

POSTGRES_DB=pitchcopytrade
POSTGRES_USER=pitchcopytrade
POSTGRES_PASSWORD=сильный_пароль

# host = postgres (имя сервиса в docker-compose)
DATABASE_URL=postgresql+asyncpg://pitchcopytrade:сильный_пароль@postgres:5432/pitchcopytrade

# host = localhost (при запуске alembic с хоста сервера, порт проброшен)
ALEMBIC_DATABASE_URL=postgresql+asyncpg://pitchcopytrade:сильный_пароль@localhost:5432/pitchcopytrade
```

> `POSTGRES_PASSWORD`, `DATABASE_URL` и `ALEMBIC_DATABASE_URL` должны содержать одинаковый пароль.

---

### Схема базы данных

2 миграции Alembic создают полную схему:

| Миграция | Дата | Содержание |
|----------|------|-----------|
| `20260310_0001` | 2026-03-10 | Начальная схема: 18 таблиц, 11 enum-типов |
| `20260318_0002` | 2026-03-18 | Таблица `notification_log` + enum `notification_channel` |

**Таблицы после применения миграций:**

| Таблица | Назначение |
|---------|-----------|
| `users` | Все пользователи системы (admin, author, subscriber) |
| `user_roles` | Связь пользователя с ролями (M2M) |
| `roles` | Справочник ролей: `admin`, `author`, `moderator` |
| `author_profiles` | Профили авторов стратегий |
| `lead_sources` | Источники привлечения подписчиков |
| `instruments` | Торговые инструменты (тикеры ММВБ) |
| `strategies` | Стратегии авторов |
| `subscription_products` | Тарифы подписки (период, цена) |
| `subscriptions` | Подписки пользователей на продукты |
| `payments` | Платёжные заявки и история оплат |
| `recommendations` | Рекомендации (черновик → опубликовано → закрыто) |
| `recommendation_legs` | Ноги рекомендации: тикер, сторона, цены |
| `recommendation_attachments` | Вложения к рекомендациям |
| `legal_documents` | Юридические документы (оферта, политика и т.д.) |
| `legal_acceptances` | Факты принятия документов пользователями |
| `promo_codes` | Промокоды и скидки |
| `notification_preferences` | Настройки уведомлений подписчика |
| `notification_log` | Лог отправленных уведомлений (Telegram / Email) |

**Enum-типы PostgreSQL:**

```
role_slug               — admin | author | moderator
user_status             — invited | active | blocked
strategy_status         — draft | published | archived
risk_level              — low | medium | high
billing_period          — month | quarter | year
payment_provider        — stub_manual | tbank
payment_status          — created | pending | paid | failed | expired | cancelled | refunded
subscription_status     — pending | trial | active | expired | cancelled | blocked
recommendation_kind     — new_idea | update | close | cancel
recommendation_status   — draft | review | approved | scheduled | published | closed | cancelled | archived
trade_side              — buy | sell
legal_document_type     — disclaimer | offer | privacy_policy | payment_consent
notification_channel    — telegram | email
```

---

### Применить миграции

Миграции запускаются один раз после первого старта postgres. Есть два способа.

**Способ 1 — изнутри контейнера api (рекомендуется):**

```bash
# убедиться, что postgres и api запущены
docker compose -f deploy/docker-compose.server.yml ps

# зайти в контейнер api и применить миграции
docker exec -it pct-api bash -c "PYTHONPATH=src alembic upgrade head"
```

**Способ 2 — с хоста сервера (если установлен Python):**

```bash
cd /var/www/pct
source .venv/bin/activate   # или активировать нужное окружение

# ALEMBIC_DATABASE_URL использует localhost (порт 5432 проброшен)
PYTHONPATH=src alembic upgrade head
```

Вывод при успешном применении:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 20260310_0001, Initial foundation schema.
INFO  [alembic.runtime.migration] Running upgrade 20260310_0001 -> 20260318_0002, Add notification_log table.
```

---

### Seed-данные при старте в db-режиме

При первом старте API автоматически запускает два seeder-а:

1. **Инструменты** — загружает 10 тикеров ММВБ из `doc/instruments_stub.json` (upsert по тикеру, не трогает существующие записи).
2. **Администратор** — создаёт пользователя с ролью `admin` из переменных окружения `ADMIN_TELEGRAM_ID` и `ADMIN_EMAIL` (пропускает, если уже создан).

Если `ADMIN_EMAIL` не задан — администратор не создаётся автоматически. Нужно создать вручную через psql или заполнить переменную.

---

### Проверить состояние БД

```bash
# подключиться к psql внутри контейнера
docker exec -it pct-postgres psql -U pitchcopytrade -d pitchcopytrade

# список таблиц
\dt

# версия миграций Alembic
SELECT version_num, is_current FROM alembic_version;

# кол-во инструментов (должно быть 10)
SELECT COUNT(*) FROM instruments;

# текущие пользователи
SELECT u.email, u.telegram_user_id, r.slug AS role
FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r ON r.id = ur.role_id;

# выйти из psql
\q
```

---

### Откат миграции

```bash
# откатить последнюю миграцию
docker exec -it pct-api bash -c "PYTHONPATH=src alembic downgrade -1"

# откатить до конкретной ревизии
docker exec -it pct-api bash -c "PYTHONPATH=src alembic downgrade 20260310_0001"

# посмотреть историю
docker exec -it pct-api bash -c "PYTHONPATH=src alembic history"
```

---

### Резервное копирование БД

```bash
# создать дамп
docker exec pct-postgres pg_dump -U pitchcopytrade pitchcopytrade > backup_$(date +%Y%m%d).sql

# восстановить из дампа
docker exec -i pct-postgres psql -U pitchcopytrade -d pitchcopytrade < backup_20260318.sql
```

---

## Обновление сервера

```bash
cd /var/www/pct
git pull
docker compose -f deploy/docker-compose.server.yml build
docker compose -f deploy/docker-compose.server.yml up -d
```

---

## Полный сброс runtime (без потери seed)

Очищает только runtime-данные. Seed-данные и код не затрагиваются.

```bash
docker compose -f deploy/docker-compose.server.yml stop

rm -rf /var/www/pct/storage/runtime
mkdir -p /var/www/pct/storage/runtime/json
mkdir -p /var/www/pct/storage/runtime/blob

docker compose -f deploy/docker-compose.server.yml start
```

---

## Полезные команды

```bash
# остановить все сервисы
docker compose -f deploy/docker-compose.server.yml stop

# перезапустить один сервис
docker compose -f deploy/docker-compose.server.yml restart api

# следить за логами в реальном времени
docker compose -f deploy/docker-compose.server.yml logs -f api

# зайти внутрь контейнера
docker exec -it pct-api bash
```

---

## Устранение проблем

**Контейнер не может писать в `storage/` на CentOS:**

```bash
getenforce
ls -laZ /var/www/pct/storage
# в docker-compose уже выставлены bind mounts с :Z — SELinux должен пропустить
```

**Mini App не открывается в Telegram:**

Telegram WebApp работает только на HTTPS. При `BASE_URL=http://...` кнопка Mini App в боте скрыта. Для включения Mini App нужен TLS-сертификат (certbot + nginx).

**Бот не реагирует на команды:**

Убедиться, что контейнер `pct-bot` запущен и в логах нет ошибок подключения:

```bash
docker compose -f deploy/docker-compose.server.yml logs --tail=100 bot
```

Проверить, что токен бота в `.env.server` корректный и бот не запущен на другой машине в polling-режиме.

---

## Документация

| Файл | Содержание |
|------|-----------|
| `doc/guide.pdf` | Подробная инструкция для администратора, автора и подписчика |
| `doc/blueprint.md` | Архитектура MVP: компоненты, роли, потоки данных |
| `doc/task.md` | Список реализованных фаз и задач |
| `deploy/env.server.example` | Шаблон конфигурации сервера |
| `deploy/docker-compose.server.yml` | Docker Compose для production |
| `deploy/nginx/` | Конфиг nginx для reverse proxy |
