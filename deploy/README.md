# Server Deploy

Canonical server deploy path for the current test version:
- clone project into `/var/www/pct`
- use root secret file `.env.server`
- use [docker-compose.server.yml](/Users/alexey/site/PitchCopyTrade/deploy/docker-compose.server.yml)
- use host nginx config [nginx/pct.test.ptfin.ru.conf](/Users/alexey/site/PitchCopyTrade/deploy/nginx/pct.test.ptfin.ru.conf)
- use HTTPS-only tester guide [guide.pdf](/Users/alexey/site/PitchCopyTrade/doc/guide.pdf)
- run in `APP_DATA_MODE=file`

## Layout
- `/var/www/pct`
  - project root from `git clone`
- `/var/www/pct/.env.server`
  - server secrets, not committed
- `/var/www/pct/storage/seed`
  - committed seed copied from repository
- `/var/www/pct/storage/runtime`
  - mutable runtime state

## Quick Start
1. `cd /var/www`
2. `git clone <REPO_URL> pct`
3. `cd /var/www/pct`
4. `cp deploy/env.server.example .env.server`
5. fill `.env.server`
6. `mkdir -p storage/runtime/json storage/runtime/blob`
7. `cp deploy/nginx/pct.test.ptfin.ru.conf /etc/nginx/conf.d/pct.test.ptfin.ru.conf`
8. `nginx -t && systemctl reload nginx`
9. `docker compose -f deploy/docker-compose.server.yml build`
10. `docker compose -f deploy/docker-compose.server.yml up -d`
