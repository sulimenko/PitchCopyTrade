# Server Deploy

Этот каталог хранит только те server-артефакты, которые реально есть в репозитории:
- `.env.example`
- `deploy/docker-compose.server.yml`
- `deploy/nginx/pct.test.ptfin.ru.conf`
- `deploy/migrate.sh`

Старого local-dev `docker-compose.yml` больше нет.
Также в репозитории нет `deploy/docker-compose.server.shared.yml`, поэтому shared-override сценарии из старых описаний больше не считаются актуальным контрактом.

## Layout

- `/var/www/pct`
  - root проекта
- `/var/www/pct/.env`
  - секреты сервера
- `/var/www/pct/storage/seed`
  - seed data
- `/var/www/pct/storage/runtime`
  - runtime files

## Fast path

1. `cd /var/www`
2. `git clone <REPO_URL> pct`
3. `cd /var/www/pct`
4. `cp .env.example .env`
5. заполнить `.env`
6. подготовить PostgreSQL, Redis и внешнюю Docker-сеть `ptfin-backend`, которые ожидает текущий `deploy/docker-compose.server.yml`
7. установить nginx config из `deploy/nginx/`, если используете host nginx
8. `docker compose -f deploy/docker-compose.server.yml build`
9. `docker compose -f deploy/docker-compose.server.yml up -d`

## Important

- перед использованием server-артефактов сверяйте их между собой: compose, nginx и `.env` в репозитории не покрывают альтернативные режимы за пределами текущего файла `deploy/docker-compose.server.yml`
- nginx или другой reverse proxy обязан передавать:
  - `X-Forwarded-Proto`
  - `X-Forwarded-For`
- Telegram Login Widget требует корректный `BASE_URL` и `@BotFather /setdomain`
- для staff onboarding по email должны быть заполнены `SMTP_*` поля в `.env`
- если `SMTP_PASSWORD` пустой или начинается с `__FILL_ME__`, invite email не отправится
- staff redesign, current review gate и local preview/runbook описаны в:
  - [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
  - [review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)
  - [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)

## SMTP quick check

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
3. Создать тестового `author` или `admin` из staff UI.
4. Проверить:
   - письмо сотруднику;
   - контрольное письмо действующим администраторам;
   - badge `отправлено` или `ошибка отправки` в реестре.
5. Если письмо не ушло, смотреть:
   - `docker compose -f deploy/docker-compose.server.yml logs --tail=200 api`

## V3 live smoke-check and log capture

Этот runbook нужен для live-части `V3` из `doc/task.md`: создать подписчика, создать и опубликовать рекомендацию, затем снять логи по цепочке доставки.

### 1. Выбрать compose command

- `export COMPOSE_SERVER="docker compose -f deploy/docker-compose.server.yml"`

### 2. Подготовить директорию для артефактов

1. `cd /var/www/pct`
2. `export V3_LOG_DIR="/var/www/pct/tmp/v3-smoke-$(date -u +%Y%m%dT%H%M%SZ)"`
3. `mkdir -p "$V3_LOG_DIR"`
4. `$COMPOSE_SERVER ps > "$V3_LOG_DIR/compose-ps.txt"`
5. `$COMPOSE_SERVER logs --tail=200 api worker > "$V3_LOG_DIR/preflight.log"`

### 3. Включить live-follow лог в отдельной сессии

Запустить до начала smoke-сценария и оставить открытым:

```bash
$COMPOSE_SERVER logs --since=1m -f api worker | tee "$V3_LOG_DIR/live-follow.log"
```

Если отдельно проверяется transport до Telegram API, параллельно можно смотреть:

```bash
$COMPOSE_SERVER logs --since=1m -f bot | tee "$V3_LOG_DIR/bot-follow.log"
```

### 4. Выполнить live V3 сценарий

1. Создать тестового подписчика и активную подписку.
2. Создать recommendation через `/author/recommendations`.
3. Опубликовать recommendation.
4. Если проверяется scheduled path, дождаться worker tick или принудительно дождаться ближайшего цикла.
5. Если SMTP настроен и проверяется email часть, повторить сценарий с подписчиком, у которого есть email.

### 5. Снять итоговые логи после сценария

```bash
$COMPOSE_SERVER logs --since=30m api > "$V3_LOG_DIR/api.log"
$COMPOSE_SERVER logs --since=30m worker > "$V3_LOG_DIR/worker.log"
$COMPOSE_SERVER logs --since=30m bot > "$V3_LOG_DIR/bot.log"
```

Собрать короткую выжимку по ключевым маркерам:

```bash
rg -n "scheduled_publish|notification|Immediate notification delivery failed|Failed to deliver recommendation notification|SMTP|Traceback|ERROR|EXCEPTION" \
  "$V3_LOG_DIR"/api.log "$V3_LOG_DIR"/worker.log "$V3_LOG_DIR"/bot.log \
  > "$V3_LOG_DIR/highlights.txt" || true
```

При необходимости упаковать всё в один архив:

```bash
tar -czf "$V3_LOG_DIR.tar.gz" -C "$(dirname "$V3_LOG_DIR")" "$(basename "$V3_LOG_DIR")"
```

### 6. Что считать нормой

- immediate publish:
  - в `api.log` нет `Traceback` и нет `Immediate notification delivery failed`
  - нет строк `Failed to deliver recommendation notification` для нужного `chat_id`
- scheduled publish:
  - в `worker.log` есть `scheduled_publish tick:`
  - нет `EXCEPTION`/`Traceback` во время публикации и доставки
- email часть:
  - нет SMTP errors в том процессе, который инициировал доставку

### 7. Что приложить по итогам smoke-проверки

- путь к каталогу `$V3_LOG_DIR`
- `compose-ps.txt`
- `highlights.txt`
- указание, какой path проверялся:
  - immediate publish через `api`
  - scheduled publish через `worker`
  - email smoke при наличии SMTP
  - transport smoke через `bot`, если была проблема связи с Telegram

## Telegram bot troubleshooting

Если `bot` падает на `api.telegram.org:443`, это transport/runtime проблема, а не product-flow ошибка.

Проверить по порядку:
1. системное время на хосте;
2. DNS-резолвинг именно из контейнера `bot`;
3. исходящий `443` до `api.telegram.org` именно из контейнера;
4. CA/cert trust внутри образа;
5. логи `bot` после старта и после автоматического retry.

Runbook:
- `docker compose -f deploy/docker-compose.server.yml logs --tail=200 bot`
- `docker compose -f deploy/docker-compose.server.yml exec bot getent hosts api.telegram.org`
- `docker compose -f deploy/docker-compose.server.yml exec bot curl -I https://api.telegram.org`
- `docker compose -f deploy/docker-compose.server.yml exec bot date -u`
- `docker compose -f deploy/docker-compose.server.yml exec bot python -m pitchcopytrade.bot.main --smoke-check`
- убедиться, что после временного network/TLS сбоя в логах появляются retry/backoff сообщения, а затем `Telegram smoke check ok` и запуск polling

Post-deploy smoke-check:
1. `docker compose -f deploy/docker-compose.server.yml up -d bot`
2. `docker compose -f deploy/docker-compose.server.yml logs --tail=200 -f bot`
3. проверить, что bot доходит до `getMe` и затем до polling без ручного `restart`
4. дополнительно выполнить:
   - `docker compose -f deploy/docker-compose.server.yml exec bot python -m pitchcopytrade.bot.main --smoke-check`
5. если во время старта есть временный DNS/TLS timeout, bot должен продолжить retry сам; ручной redeploy всего стека не нужен

Требование к коду:
- единичный network/TLS сбой не должен завершать bot-contour навсегда;
- bot обязан сам восстанавливать polling через retry/backoff.
