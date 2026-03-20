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
