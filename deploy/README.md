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
- `guide.pdf` и `guide.html` описывают текущий операторский flow:
  - [guide.html](/Users/alexey/site/PitchCopyTrade/doc/guide.html)
  - [guide.pdf](/Users/alexey/site/PitchCopyTrade/doc/guide.pdf)
- staff redesign и onboarding redesign описаны в:
  - [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
  - [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
