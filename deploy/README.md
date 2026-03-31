# Server Deploy And Clean DB Reset

Этот файл отвечает только за server/db контур:

- server deploy артефакты
- clean reset PostgreSQL schema
- db-mode startup после reset
- SMTP smoke-check
- live log capture
- bot transport troubleshooting

Локальный runbook и contributor workflow вынесены в [doc/README.md](/Users/alexey/site/PitchCopyTrade/doc/README.md).  
Product contract, backlog и review gate вынесены в:

- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)

## Текущий Production Snapshot

Проверенный server/runtime snapshot на `2026-03-31`:

- Mini App auth и checkout работают в `db`-mode;
- новые подписчики создаются, consents/subscriptions записываются;
- Mini App subscription pages больше не падают на render path;
- subscriber publish delivery работает;
- `storage/api.log` считается canonical operator-facing log sink;
- основной staff/admin Telegram invite onboarding path восстановлен.

Открытый follow-up после этого pass-а:

- metadata merge для existing subscriber -> staff/admin еще требует нормализации; см. `P40` в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md) и актуальный gate в [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md).

## Актуальные deploy-артефакты

В репозитории реально поддерживаются:

- `.env.example`
- `deploy/docker-compose.server.yml`
- `deploy/nginx/pct.test.ptfin.ru.conf`
- `deploy/migrate.sh`
- `deploy/schema.sql`

Корневого local-dev `docker-compose.yml` больше нет.  
Также в репозитории нет `deploy/docker-compose.server.shared.yml`, поэтому shared-override сценарии из старых описаний больше не считаются актуальным контрактом.

## Server layout

- `/var/www/pct`
  - root проекта
- `/var/www/pct/.env`
  - runtime env сервера
- `/var/www/pct/storage/seed`
  - seed data
- `/var/www/pct/storage/runtime`
  - runtime files

## Fast path: server deploy

1. `cd /var/www`
2. `git clone <REPO_URL> pct`
3. `cd /var/www/pct`
4. `cp .env.example .env`
5. заполнить `.env`
6. подготовить PostgreSQL, Redis и внешнюю Docker-сеть `ptfin-backend`, которые ожидает текущий `deploy/docker-compose.server.yml`
7. установить nginx config из `deploy/nginx/`, если используете host nginx
8. `docker compose -f deploy/docker-compose.server.yml build`
9. `docker compose -f deploy/docker-compose.server.yml up -d`

## Clean DB Reset Contract

Единый воспроизводимый db-mode сценарий:

1. `cp .env.example .env`
2. заполнить `.env` для PostgreSQL
3. `bash deploy/migrate.sh --reset`
4. убедиться, что seed data лежат в `storage/seed`
5. поднять приложение в `APP_DATA_MODE=db`
6. прогнать smoke/regression suite

Важно:

- `deploy/schema.sql` является единственным источником правды для clean reset
- legacy `recommendation_*` schema path не поддерживается
- `deploy/migrate.sh` читает `.env`
- storage reset выполняется отдельно внутри `deploy/migrate.sh --reset`

### Что сейчас реально seed-ится в `APP_DATA_MODE=db`

Текущее поведение проекта такое:

1. `bash deploy/migrate.sh --reset`
   - создает schema из `deploy/schema.sql`
   - не загружает автоматически весь business dataset из `storage/seed/json`
2. при первом старте `api` в `APP_DATA_MODE=db`
   - startup вызывает `src/pitchcopytrade/api/lifespan.py::_run_seeders()`
   - автоматически загружаются только:
     - `instruments` из `storage/seed/json/instruments.json`
     - bootstrap `admin`, если в `.env` заданы `ADMIN_TELEGRAM_ID` или `ADMIN_EMAIL`

Это значит:

- `messages.json`, `users.json`, `strategies.json`, `products.json`, `subscriptions.json` и прочие file-mode datasets сейчас не импортируются в PostgreSQL автоматически;
- `db`-mode здесь следует читать как primary schema/startup runtime, а не как “полный business seed готов”;
- для полного business seed в db-mode нужен отдельный importer или явный seed pipeline;
- post-implementation review от `2026-03-28` подтверждает, что этот статус все еще актуален;
- текущая follow-up работа по полному db seed описана в [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md) в блоке `L5`.

Практический сценарий на сегодня:

1. подготовить `.env` с `APP_DATA_MODE=db`
2. выполнить `bash deploy/migrate.sh --reset`
3. поднять `api`
4. дождаться auto-seed инструментов и bootstrap admin
5. если нужен полный dataset для manual QA, нельзя считать `file` заменой основного runtime: нужно закрыть/import `L5` и получить полный business seed именно в PostgreSQL; до этого момента `db` не должен трактоваться как уже полноценно seeded business environment

## Команды миграции

```bash
bash deploy/migrate.sh
bash deploy/migrate.sh --reset
```

Что делает `--reset`:

1. дропает `public` schema
2. пересоздает `public`
3. очищает `storage`
4. заново применяет `deploy/schema.sql`

## Важные замечания

- перед использованием server-артефактов сверяйте compose, nginx и `.env` между собой
- nginx или другой reverse proxy обязан передавать:
  - `X-Forwarded-Proto`
  - `X-Forwarded-For`
- Telegram Login Widget требует корректный `BASE_URL` и настройку `@BotFather /setdomain`
- для staff onboarding по email должны быть заполнены `SMTP_*` поля в `.env`
- если `SMTP_PASSWORD` пустой или начинается с `__FILL_ME__`, invite email не отправится

## SMTP Quick Check

1. Заполнить в `.env`:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_SSL`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `SMTP_FROM`
   - `SMTP_FROM_NAME`
2. Перезапустить `api`:
   - `docker compose -f deploy/docker-compose.server.yml up -d --build api`
3. Создать тестового `author` или `admin` из staff UI
4. Проверить:
   - письмо сотруднику
   - контрольное письмо действующим администраторам
   - badge `отправлено` или `ошибка отправки` в реестре
5. Если письмо не ушло:
   - `docker compose -f deploy/docker-compose.server.yml logs --tail=200 api`

## Live Smoke And Log Capture

Этот runbook нужен для live server-проверки публикации и доставки.

Операционный контракт:

- основным источником RCA считайте `storage/api.log`;
- `docker compose logs` используйте как secondary stream только если нужно быстро увидеть container stdout/stderr;
- при triage новых production дефектов сначала фиксируйте `journey_id` и затем ищите его в `storage/api.log`.

### 1. Compose command

- `export COMPOSE_SERVER="docker compose -f deploy/docker-compose.server.yml"`

### 2. Директория артефактов

1. `cd /var/www/pct`
2. `export V3_LOG_DIR="/var/www/pct/tmp/v3-smoke-$(date -u +%Y%m%dT%H%M%SZ)"`
3. `mkdir -p "$V3_LOG_DIR"`
4. `$COMPOSE_SERVER ps > "$V3_LOG_DIR/compose-ps.txt"`
5. `$COMPOSE_SERVER logs --tail=200 api worker > "$V3_LOG_DIR/preflight.log"`

### 3. Live follow

```bash
$COMPOSE_SERVER logs --since=1m -f api worker | tee "$V3_LOG_DIR/live-follow.log"
```

Если отдельно проверяется transport до Telegram API:

```bash
$COMPOSE_SERVER logs --since=1m -f bot | tee "$V3_LOG_DIR/bot-follow.log"
```

### 4. Сценарий

1. Создать тестового подписчика и активную подписку
2. Создать сообщение через author surface
3. Опубликовать сообщение
4. Для scheduled path дождаться worker tick
5. Для email path повторить сценарий с пользователем, у которого есть email

### 5. Итоговые логи

```bash
$COMPOSE_SERVER logs --since=30m api > "$V3_LOG_DIR/api.log"
$COMPOSE_SERVER logs --since=30m worker > "$V3_LOG_DIR/worker.log"
$COMPOSE_SERVER logs --since=30m bot > "$V3_LOG_DIR/bot.log"
```

Короткая выжимка:

```bash
rg -n "scheduled_publish|notification|Immediate notification delivery failed|Failed to deliver message notification|SMTP|Traceback|ERROR|EXCEPTION" \
  "$V3_LOG_DIR"/api.log "$V3_LOG_DIR"/worker.log "$V3_LOG_DIR"/bot.log \
  > "$V3_LOG_DIR/highlights.txt" || true
```

### 6. Что считать нормой

- immediate publish:
  - в `api.log` нет `Traceback`
  - нет `Immediate notification delivery failed`
- scheduled publish:
  - в `worker.log` есть `scheduled_publish tick:`
  - нет `EXCEPTION`/`Traceback` во время публикации и доставки
- email часть:
  - нет SMTP errors в процессе, который инициировал доставку

## Telegram Bot Troubleshooting

Если `bot` падает на `api.telegram.org:443`, это transport/runtime проблема, а не product-flow ошибка.

Проверять по порядку:

1. системное время на хосте
2. DNS-резолвинг из контейнера `bot`
3. исходящий `443` из контейнера
4. CA/cert trust внутри образа
5. логи `bot` после старта и retry

Runbook:

- `docker compose -f deploy/docker-compose.server.yml logs --tail=200 bot`
- `docker compose -f deploy/docker-compose.server.yml exec bot getent hosts api.telegram.org`
- `docker compose -f deploy/docker-compose.server.yml exec bot curl -I https://api.telegram.org`
- `docker compose -f deploy/docker-compose.server.yml exec bot date -u`
- `docker compose -f deploy/docker-compose.server.yml exec bot python -m pitchcopytrade.bot.main --smoke-check`

Требование к коду:

- единичный network/TLS сбой не должен завершать bot-contour навсегда
- bot обязан восстанавливать polling через retry/backoff
