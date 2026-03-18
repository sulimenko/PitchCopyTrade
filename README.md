# PitchCopyTrade

Telegram-first платформа для продажи подписок на инвестиционные стратегии и доставки торговых рекомендаций подписчикам.

Три роли: **Администратор** управляет авторами и платежами через веб-кабинет. **Автор** публикует рекомендации через веб-кабинет с авторизацией через Telegram. **Подписчик** работает через Telegram-бот и Mini App — без отдельного пароля.

Три сервиса в Docker: **api** (FastAPI, веб-кабинеты), **bot** (aiogram 3, Telegram), **worker** (ARQ, фоновые задачи и уведомления). PostgreSQL и Redis — установлены на хосте сервера, не в Docker.

---

## Запуск на сервере

### Требования

- CentOS 8 / Ubuntu 22+ с Docker Engine и Docker Compose plugin
- Системный nginx
- PostgreSQL 12+ установлен на хосте (`yum install postgresql-server` / `apt install postgresql`)
- Redis установлен на хосте (`yum install redis` / `apt install redis`)
- DNS-запись домена указывает на IP сервера
- Открыты входящие порты `80/tcp` и `443/tcp`
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

### Шаг 2. Подготовить PostgreSQL

PostgreSQL установлен на хосте. Создать пользователя и базу данных:

```bash
sudo -u postgres psql << 'EOF'
CREATE USER pct WITH PASSWORD 'сильный_пароль_здесь';
CREATE DATABASE pct OWNER pct ENCODING 'UTF8';
EOF
```

Проверить:

```bash
sudo -u postgres psql -c "\l" | grep pct
```

---

### Шаг 3. Создать конфигурационный файл

```bash
cp deploy/env.server.example .env.server
```

Открыть `.env.server` и заполнить обязательные поля:

```dotenv
APP_SECRET_KEY=           # длинная случайная строка, минимум 32 символа
BASE_URL=                 # https://ваш-домен.ru
ADMIN_BASE_URL=           # https://ваш-домен.ru/admin

TELEGRAM_BOT_TOKEN=       # токен от @BotFather
TELEGRAM_BOT_USERNAME=    # username бота без @
TELEGRAM_USE_WEBHOOK=true
TELEGRAM_WEBHOOK_SECRET=  # любая случайная строка

POSTGRES_USER=pct
POSTGRES_DB=pct
POSTGRES_PASSWORD=        # пароль из Шага 2

# Контейнеры подключаются к хостовому postgres через host.docker.internal
DATABASE_URL=postgresql+asyncpg://pct:ПАРОЛЬ@host.docker.internal:5432/pct

# migrate.sh запускает alembic с --network host, поэтому здесь localhost
ALEMBIC_DATABASE_URL=postgresql+asyncpg://pct:ПАРОЛЬ@localhost:5432/pct

INTERNAL_API_SECRET=      # случайная строка для внутренних вызовов bot→api
REDIS_URL=redis://localhost:6379/0

SMTP_PASSWORD=            # пароль SMTP
ADMIN_TELEGRAM_ID=        # Telegram user_id первого администратора
ADMIN_EMAIL=              # email первого администратора
```

> **Важно.** `.env.server` не коммитить в git. Токен бота не держать одновременно в polling на двух машинах.

---

### Шаг 4. Установить nginx-конфиг

```bash
cp deploy/nginx/pct.test.ptfin.ru.conf /etc/nginx/conf.d/ваш-домен.conf
```

Открыть скопированный файл и заменить `pct.test.ptfin.ru` на ваш домен.

Для HTTPS получить сертификат:

```bash
certbot --nginx -d ваш-домен.ru
```

Проверить и применить конфиг:

```bash
nginx -t && systemctl reload nginx
```

nginx проксирует входящий трафик на `127.0.0.1:8110` — там слушает контейнер api.
Webhook Telegram принимается по пути `/webhook/` → пробрасывается в контейнер api.

---

### Шаг 5. Собрать Docker-образы

```bash
cd /var/www/pct
docker compose -f deploy/docker-compose.server.yml build
```

Образы: `deploy-api`, `deploy-bot`, `deploy-worker`.

---

### Шаг 6. Создать таблицы в базе данных

```bash
bash deploy/migrate.sh
```

Скрипт читает `.env.server` и применяет все Alembic-миграции через Docker с `--network host`.

Ожидаемый вывод:

```
Запуск: alembic upgrade head
Running upgrade  -> 20260310_0001, Initial foundation schema.
Running upgrade 20260310_0001 -> 20260318_0002, Add notification_log table.

Готово.
```

Проверить таблицы:

```bash
sudo -u postgres psql pct -c "\dt"
```

Должно быть 19 таблиц, включая `notification_log`.

---

### Шаг 7. Запустить контейнеры

```bash
docker compose -f deploy/docker-compose.server.yml up -d
```

Запускаются три контейнера: `pct-api`, `pct-bot`, `pct-worker`.

---

### Шаг 8. Проверить запуск

```bash
# статус контейнеров
docker compose -f deploy/docker-compose.server.yml ps

# логи
docker compose -f deploy/docker-compose.server.yml logs --tail=50 api
docker compose -f deploy/docker-compose.server.yml logs --tail=50 bot
docker compose -f deploy/docker-compose.server.yml logs --tail=50 worker

# health-check
curl -s http://127.0.0.1:8110/health
```

---

### Шаг 9. Первый вход

Открыть в браузере `https://ваш-домен.ru/login`.

При первом старте в db-режиме API создаёт администратора из `ADMIN_TELEGRAM_ID` и `ADMIN_EMAIL` (если заданы в `.env.server`). После входа откроется `/admin/dashboard`.

**Что сделать сразу после входа:**
1. Перейти в раздел **Авторы** → создать первого автора (имя + Telegram User ID).
2. Передать автору адрес кабинета — он входит через Telegram Login Widget.
3. В Telegram открыть бота → `/start` → проверить, что кнопка Mini App появляется.

---

## База данных

### Схема

2 миграции Alembic создают полную схему:

| Миграция | Содержание |
|----------|-----------|
| `20260310_0001` | Начальная схема: 18 таблиц, 11 enum-типов |
| `20260318_0002` | Таблица `notification_log` + enum `notification_channel` |

**Таблицы:**

| Таблица | Назначение |
|---------|-----------|
| `users` | Все пользователи (admin, author, subscriber) |
| `user_roles` | Связь пользователей с ролями (M2M) |
| `roles` | Справочник ролей: admin, author, moderator |
| `author_profiles` | Профили авторов стратегий |
| `lead_sources` | Источники привлечения подписчиков |
| `instruments` | Торговые инструменты (тикеры ММВБ) |
| `strategies` | Стратегии авторов |
| `subscription_products` | Тарифы подписки (период, цена) |
| `subscriptions` | Подписки пользователей |
| `payments` | Платёжные заявки и история оплат |
| `promo_codes` | Промокоды и скидки |
| `recommendations` | Рекомендации (draft → published → closed) |
| `recommendation_legs` | Ноги рекомендации: тикер, сторона, цены |
| `recommendation_attachments` | Вложения к рекомендациям |
| `legal_documents` | Юридические документы |
| `user_consents` | Факты принятия документов пользователями |
| `bundles` | Пакеты стратегий |
| `bundle_members` | Состав пакетов (M2M) |
| `audit_events` | Лог действий в системе |
| `notification_log` | Лог отправленных уведомлений |

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

### Проверить состояние БД

```bash
# список таблиц
sudo -u postgres psql pct -c "\dt"

# версия применённых миграций
sudo -u postgres psql pct -c "SELECT version_num FROM alembic_version;"

# кол-во инструментов (должно быть 10 после первого старта API)
sudo -u postgres psql pct -c "SELECT COUNT(*) FROM instruments;"

# пользователи и роли
sudo -u postgres psql pct -c "
SELECT u.email, u.telegram_user_id, r.slug AS role
FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r ON r.id = ur.role_id;"
```

---

### Полный сброс БД и runtime-хранилища

Удаляет все таблицы, все runtime JSON-файлы и blob-файлы. Seed-данные (`storage/seed/`) не трогает.

```bash
# остановить контейнеры
docker compose -f deploy/docker-compose.server.yml stop

# сброс: DROP SCHEMA → чистые JSON/blob → alembic upgrade head
bash deploy/migrate.sh --reset

# запустить снова
docker compose -f deploy/docker-compose.server.yml start
```

---

### Откат миграции

```bash
bash deploy/migrate.sh downgrade -1
bash deploy/migrate.sh downgrade 20260310_0001
bash deploy/migrate.sh history
```

---

### Резервное копирование БД

```bash
# создать дамп
sudo -u postgres pg_dump pct > backup_$(date +%Y%m%d_%H%M).sql

# восстановить из дампа
sudo -u postgres psql pct < backup_20260318_1400.sql
```

---

## Обновление сервера

```bash
cd /var/www/pct
git pull
docker compose -f deploy/docker-compose.server.yml build
bash deploy/migrate.sh
docker compose -f deploy/docker-compose.server.yml up -d
```

---

## Очистка Docker

Удалить неиспользуемые образы (после каждого rebuild накапливаются `<none>`-образы):

```bash
docker image prune -f
```

Полная очистка всего неиспользуемого (образы + контейнеры + тома):

```bash
docker system prune -f
```

Добавить в cron для автоматической еженедельной очистки:

```bash
echo "0 3 * * 0 root docker image prune -f" > /etc/cron.d/docker-cleanup
```

---

## Полезные команды

```bash
# статус всех сервисов
docker compose -f deploy/docker-compose.server.yml ps

# логи в реальном времени
docker compose -f deploy/docker-compose.server.yml logs -f api

# перезапустить один сервис
docker compose -f deploy/docker-compose.server.yml restart api

# зайти внутрь контейнера
docker exec -it pct-api bash
```

---

## Устранение проблем

**Контейнер не может подключиться к postgres:**

```bash
# проверить, что postgres слушает
ss -tlnp | grep 5432

# проверить, что host.docker.internal резолвится внутри контейнера
docker exec pct-api ping -c1 host.docker.internal
```

`extra_hosts: host.docker.internal:host-gateway` прописан в `docker-compose.server.yml` — на Linux это обязательно.

**Контейнер не может писать в `storage/` на CentOS:**

```bash
ls -laZ /var/www/pct/storage
# bind mounts в docker-compose используют :Z — SELinux должен пропустить
```

**Mini App не открывается в Telegram:**

Telegram WebApp работает только на HTTPS. При `BASE_URL=http://...` кнопка Mini App скрыта. Нужен TLS-сертификат (certbot + nginx).

**Бот не реагирует на команды:**

```bash
docker compose -f deploy/docker-compose.server.yml logs --tail=100 bot
```

Убедиться, что токен корректный и бот не запущен в polling на другой машине.

---

## Документация

| Файл | Содержание |
|------|-----------|
| `doc/guide.pdf` | Подробная инструкция для администратора, автора и подписчика |
| `doc/blueprint.md` | Архитектура MVP: компоненты, роли, потоки данных |
| `deploy/env.server.example` | Шаблон конфигурации сервера |
| `deploy/migrate.sh` | Скрипт миграций и полного сброса |
| `deploy/docker-compose.server.yml` | Docker Compose для production |
| `deploy/nginx/` | Конфиг nginx для reverse proxy |
