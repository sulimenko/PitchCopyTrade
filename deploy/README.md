# Server Deploy

Канонический server deploy path для текущего продукта:
- код в `/var/www/pct`
- Docker для `api`, `bot`, `worker`
- host `nginx`
- host PostgreSQL
- host Redis
- HTTPS-only domain
- основной server mode: `APP_DATA_MODE=db`

## Layout

- `/var/www/pct`
  - root проекта
- `/var/www/pct/.env.server`
  - секреты сервера
- `/var/www/pct/storage/seed`
  - seed data
- `/var/www/pct/storage/runtime`
  - runtime files

## Fast path

1. `cd /var/www`
2. `git clone <REPO_URL> pct`
3. `cd /var/www/pct`
4. `cp deploy/env.server.example .env.server`
5. заполнить `.env.server`
6. подготовить PostgreSQL и Redis на хосте
7. установить nginx config из `deploy/nginx/`
8. `docker compose -f deploy/docker-compose.server.yml build`
9. `docker compose -f deploy/docker-compose.server.yml up -d`

## Important

- host `nginx` должен проксировать на `http://127.0.0.1:8110`
- Telegram Login Widget требует корректный `BASE_URL` и `@BotFather /setdomain`
- для staff onboarding по email должны быть заполнены `SMTP_*` поля в `.env.server`
- если `SMTP_PASSWORD` пустой или начинается с `__FILL_ME__`, invite email не отправится
- `guide.pdf` и `guide.html` описывают текущий операторский flow:
  - [guide.html](/Users/alexey/site/PitchCopyTrade/doc/guide.html)
  - [guide.pdf](/Users/alexey/site/PitchCopyTrade/doc/guide.pdf)
- staff redesign и onboarding redesign описаны в:
  - [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
  - [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)

## SMTP quick check

1. Заполнить в `.env.server`:
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
