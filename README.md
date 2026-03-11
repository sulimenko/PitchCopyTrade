# PitchCopyTrade

Telegram-first платформа для продажи подписок на стратегии и доставки инвестиционных рекомендаций.

## Текущее состояние
Сейчас кодовая база уже имеет рабочий baseline на:
- `FastAPI`
- `aiogram 3`
- `PostgreSQL`
- `SQLAlchemy 2`
- `Alembic`
- `MinIO`
- `Jinja2`
- `HTMX`
- `Docker Compose`

Реализовано:
- staff auth для `admin / author / moderator`
- admin dashboard
- strategy CRUD
- subscription product CRUD
- payment review -> confirm -> subscription activation
- author workspace
- recommendation CRUD
- structured legs editor
- preview
- moderation queue
- moderation history baseline
- public catalog
- checkout `stub/manual`
- ACL delivery
- Telegram-first subscriber baseline
- scheduled publish baseline
- delivery notifications baseline
- local filesystem storage backend baseline with runtime root `storage/runtime/blob`
- `api + bot + worker` can start in `APP_DATA_MODE=file` without PostgreSQL and without MinIO
- runtime switch:
  - `APP_DATA_MODE=db|file`
  - `APP_STORAGE_ROOT=storage`
- repository layer baseline for:
  - author workspace persistence
  - subscriber ACL/feed persistence
- file repositories baseline for demo datasets:
  - users
  - roles
  - authors
  - strategies
  - products
  - legal docs
  - payments
  - subscriptions
  - recommendations
  - legs
  - attachments
- real demo seed pack under [storage/seed/json](/Users/alexey/site/PitchCopyTrade/storage/seed/json)
- demo attachment blob under [storage/seed/blob/recommendations/rec-1/file.pdf](/Users/alexey/site/PitchCopyTrade/storage/seed/blob/recommendations/rec-1/file.pdf)
- legal markdown source files under [storage/seed/blob/legal](/Users/alexey/site/PitchCopyTrade/storage/seed/blob/legal)
- verified local file-mode e2e:
  - staff login for `admin` and `author`
  - `admin dashboard`
  - `author dashboard`
  - `Telegram checkout -> admin confirm -> subscriber feed`

## Архитектурный сдвиг
Новая целевая схема:
- отказаться от удаленного object storage как основной модели;
- хранить документы и вложения на локальной файловой системе;
- использовать единый корень `storage/`;
- поддержать запуск без БД для локального тестирования.

Целевые runtime modes:
- `db`:
  - `PostgreSQL` хранит операционные данные;
  - локальная файловая система хранит документы и вложения;
- `file`:
  - если нет доступа к локальной БД, проект работает на файловых репозиториях;
  - структурированные данные хранятся в `JSON`;
  - бинарные файлы хранятся в `blob`;
  - append-heavy и аналитические наборы можно складывать в `Parquet`.

Рекомендованная структура:
- `storage/seed/blob/`
- `storage/seed/json/`
- `storage/runtime/blob/`
- `storage/runtime/json/`
- `storage/parquet/`

## Что показывает исследование
Текущий код пока еще не соответствует новой целевой схеме полностью.

Жесткие зависимости, которые сейчас есть:
- file mode уже поддержан на уровне config/runtime, но service/repository layer все еще в основном DB-first;
- repository layer уже введен частично, но `admin`, `public`, `moderation`, `payments` и `notifications` еще не переведены на него полностью;
- `author` и `subscriber ACL/feed` уже могут идти через file repositories;
- `public checkout`, `staff auth` и `admin confirm path` уже проверены в `file` mode;
- `moderation`, `notifications` и часть publishing/delivery UX еще не имеют полной file-repository parity;
- local filesystem storage backend уже добавлен, но primary attachment flow все еще по умолчанию ориентирован на `MinIO`;
- `docker-compose.yml` все еще поднимает `minio` как штатный сервис;
- attachment flow и metadata пока ориентированы на bucket/object-key path.
- legal docs уже могут рендериться из локальных markdown source files, но admin editing flow для них еще не реализован.

Это значит:
- текущая реализация пригодна для продолжения продуктовой разработки;
- но для быстрого локального тестирования без БД и без удаленного storage нужен отдельный refactor persistence layer.

## User cases

### Admin
Что делает сейчас:
- входит в staff web через `login/password`
- управляет стратегиями
- управляет продуктами подписки
- проверяет manual payments
- подтверждает оплату и активирует подписки

Что получит после storage/file-mode refactor:
- локальный запуск админки без обязательной БД
- простую тестовую среду для проверки каталогов, платежных сценариев и legal flow

### Author
Что делает сейчас:
- входит в staff web через `login/password`
- работает в author workspace
- создает и редактирует рекомендации по своим стратегиям
- управляет статусами идей
- задает structured legs
- загружает вложения
- отправляет публикации в moderation/publish flow

Что получит после storage/file-mode refactor:
- локальное хранение вложений без `MinIO`
- локальный author demo flow без обязательного PostgreSQL

### Subscriber / user
Что делает сейчас:
- основной путь проходит через Telegram bot
- видит каталог
- оформляет `stub/manual` checkout
- после активации получает feed по ACL
- при необходимости использует web fallback через Telegram-auth path

Что получит после storage/file-mode refactor:
- локальный end-to-end demo без БД
- более быстрый smoke-test Telegram сценариев на одной машине

### Moderator
Что делает сейчас:
- входит в staff web через `login/password`
- работает в moderation queue
- видит preview и timeline baseline
- принимает решение `approve / rework / reject`

Что получит после storage/file-mode refactor:
- локальную очередь moderation без обязательной инфраструктуры БД и object storage

## Telegram bots
- test bot:
  - username: `Avt09_Bot`
  - token хранится в [`.env`](/Users/alexey/site/PitchCopyTrade/.env)
- main bot:
  - username: `Avt09Bot`
  - token хранится в [`.env`](/Users/alexey/site/PitchCopyTrade/.env) закомментированным

Telegram smoke baseline:
- `getMe` для test bot подтвержден
- Telegram username resolved as `avt09_bot`
- webhook state is empty
- pending updates at check time: `0`

## Ближайшая цель
Быстрый путь к тестированию сейчас такой:
1. внедрить local filesystem storage backend;
2. ввести `db|file` runtime mode;
3. сделать file repositories для минимального demo-контура;
4. добавить local seed data;
5. поднять `api + bot + worker` локально с test bot.

## Demo seed data
В проект уже добавлен локальный demo pack для `file` mode:
- [storage/seed/json/roles.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/roles.json)
- [storage/seed/json/users.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/users.json)
- [storage/seed/json/authors.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/authors.json)
- [storage/seed/json/strategies.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/strategies.json)
- [storage/seed/json/products.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/products.json)
- [storage/seed/json/legal_documents.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/legal_documents.json)
- [storage/seed/json/payments.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/payments.json)
- [storage/seed/json/subscriptions.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/subscriptions.json)
- [storage/seed/json/recommendations.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/recommendations.json)
- [storage/seed/json/recommendation_legs.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/recommendation_legs.json)
- [storage/seed/json/recommendation_attachments.json](/Users/alexey/site/PitchCopyTrade/storage/seed/json/recommendation_attachments.json)

При первом file-mode запуске runtime копируется из `storage/seed/*` в локальный `storage/runtime/*`. `storage/runtime/` не должен коммититься.
`APP_STORAGE_ROOT` должен указывать на корень, где вместе лежат `seed/` и `runtime/`.
Attachments и legal docs теперь local-first:
- recommendation attachments canonical provider = `local_fs`
- legal documents имеют `source_path` и читаются из `storage/runtime/blob` с bootstrap из `storage/seed/blob`
- `MinIO` остается transitional fallback

Demo staff credentials for local file-mode:
- `admin1 / admin-demo-pass`
- `author1 / author-demo-pass`
- `moderator1 / moderator-demo-pass`

Если меняется committed seed, локальный `storage/runtime/*` нужно пересоздать, чтобы получить новый cold start baseline.

## File mode smoke
Проверенный smoke path без PostgreSQL и без MinIO:
- `api`: каталог, legal page, staff login
- `bot`: runtime bootstrap и dispatcher assembly
- `worker`: `run_worker_once()` в `file mode`
- verified e2e on fresh temp storage root with copied seed:
  - `POST /login admin1 -> 303 /admin/dashboard`
  - `GET /admin/dashboard -> 200`
  - `POST /login author1 -> 303 /author/dashboard`
  - `GET /author/dashboard -> 200`
  - `Telegram /confirm_buy momentum-ru-month -> pending payment`
  - `POST /admin/payments/{id}/confirm -> 303`
  - `Telegram /feed -> visible recommendation after activation`

## Документы
- [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- [review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)

## Clean -> Review цикл
Рекомендуемый цикл перед каждым новым этапом и перед каждым demo/release прогоном:
1. Остановить локальные процессы `api`, `bot`, `worker`.
2. Если нужен cold start file-mode, удалить только локальный runtime:
   - `rm -rf storage/runtime`
3. Активировать окружение:
   - `source .venv/bin/activate`
4. Убедиться, что `.env` соответствует текущему сценарию:
   - `APP_DATA_MODE=file` для локального demo без БД
   - `APP_STORAGE_ROOT` указывает на корень, где лежат `seed/` и `runtime/`
   - активен только один bot token для текущего запуска
5. Прогнать технический smoke:
   - `python3 -m compileall src tests`
   - `./.venv/bin/pytest`
6. Прогнать ручной product smoke:
   - login `admin1 -> /admin/dashboard`
   - login `author1 -> /author/dashboard`
   - `Telegram /catalog`
   - `Telegram /confirm_buy momentum-ru-month`
   - `admin confirm payment`
   - `Telegram /feed`
7. После review обновить description files:
   - `README.md`
   - `doc/blueprint.md`
   - `doc/task.md`
   - `doc/review.md`

Operational rule:
- не редактировать `storage/seed/*` вручную во время обычного smoke-test;
- все runtime-изменения должны жить только в `storage/runtime/*`;
- один и тот же bot token нельзя одновременно держать в polling на двух машинах.

## Следующий этап развития
Task list для test-launch можно считать закрытым. Следующий этап теперь такой:
1. deployment hardening:
   - production-ready `systemd` units
   - `nginx` reverse proxy
   - file-mode friendly deploy scripts
2. compose cleanup:
   - убрать `MinIO-first` assumptions из runtime compose path
   - оставить `MinIO` только как optional compatibility profile
3. full file-mode parity:
   - moderation
   - notifications
   - publishing edge cases
4. legal admin UI:
   - local markdown editing
   - version activation
5. Telegram UX phase:
   - WebApp auth bridge
   - richer checkout/status UX
6. observability and operations:
   - log rotation
   - backup strategy for `storage/`
   - worker retry visibility

## Локальный запуск
Текущий рекомендованный путь для test-version: `file mode`, без PostgreSQL и без MinIO.

1. Подготовить окружение:
```bash
cd /Users/alexey/site/PitchCopyTrade
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```
2. Заполнить `.env` минимум так:
```dotenv
APP_ENV=development
APP_SECRET_KEY=change_me_to_long_random_value
APP_DATA_MODE=file
APP_STORAGE_ROOT=/Users/alexey/site/PitchCopyTrade/storage
BASE_URL=http://localhost:8000
ADMIN_BASE_URL=http://localhost:8000/admin
TELEGRAM_BOT_TOKEN=8620317929:AAGMpa6bsXETfFZ3TQAh-kxel9it5H4T85g
TELEGRAM_BOT_USERNAME=Avt09_Bot
TELEGRAM_USE_WEBHOOK=false
```
3. Если нужен чистый старт file-mode:
```bash
rm -rf storage/runtime
mkdir -p storage/runtime/json storage/runtime/blob
```
4. Запустить API:
```bash
source .venv/bin/activate
PYTHONPATH=src uvicorn pitchcopytrade.api.main:app --host 0.0.0.0 --port 8000 --reload
```
5. В отдельном терминале запустить bot:
```bash
source .venv/bin/activate
PYTHONPATH=src python -m pitchcopytrade.bot.main
```
6. В третьем терминале запустить worker:
```bash
source .venv/bin/activate
PYTHONPATH=src python -m pitchcopytrade.worker.main
```
7. Проверить web:
   - открыть `http://localhost:8000/catalog`
   - открыть `http://localhost:8000/login`
   - `admin1 / admin-demo-pass`
   - `author1 / author-demo-pass`
8. Проверить Telegram:
   - открыть `@Avt09_Bot`
   - выполнить `/start`
   - выполнить `/catalog`
   - выполнить `/confirm_buy momentum-ru-month`
9. Вернуться в admin web:
   - открыть payment queue
   - подтвердить pending payment
10. Снова в Telegram:
   - выполнить `/feed`
   - убедиться, что рекомендация стала видна

## Запуск на выделенном сервере
Текущий рекомендованный серверный путь для test-version:
- `file mode`
- `nginx + uvicorn`
- `systemd` для `api`, `bot`, `worker`
- polling bot, без webhook

Целевой DNS:
- `pct.test.pbull.kz`

### 1. Подготовка сервера
Предположение:
- Ubuntu 24.04 или совместимый Linux
- DNS `pct.test.pbull.kz` уже указывает на IP сервера
- открыты порты `80` и `443`

Установить пакеты:
```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip nginx certbot python3-certbot-nginx git
```

### 2. Разложить проект
```bash
sudo mkdir -p /opt/pitchcopytrade
sudo chown $USER:$USER /opt/pitchcopytrade
cd /opt/pitchcopytrade
git clone <repo_url> app
cd app
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

### 3. Настроить `.env`
Минимальный server config:
```dotenv
APP_ENV=staging
APP_SECRET_KEY=change_me_to_long_random_value
APP_DATA_MODE=file
APP_STORAGE_ROOT=/opt/pitchcopytrade/app/storage
BASE_URL=https://pct.test.pbull.kz
ADMIN_BASE_URL=https://pct.test.pbull.kz/admin
TELEGRAM_BOT_TOKEN=8620317929:AAGMpa6bsXETfFZ3TQAh-kxel9it5H4T85g
TELEGRAM_BOT_USERNAME=Avt09_Bot
TELEGRAM_USE_WEBHOOK=false
LOG_LEVEL=INFO
LOG_JSON=false
```

Важно:
- не запускать этот же test bot одновременно локально и на сервере;
- для server smoke использовать только один polling process на один token.

### 4. Подготовить storage
```bash
mkdir -p /opt/pitchcopytrade/app/storage/runtime/json
mkdir -p /opt/pitchcopytrade/app/storage/runtime/blob
```
`storage/seed/*` уже лежит в репозитории. При первом file-mode доступе runtime будет bootstrap'иться из seed.

### 5. Проверить проект вручную
```bash
cd /opt/pitchcopytrade/app
source .venv/bin/activate
python3 -m compileall src tests
./.venv/bin/pytest
```

### 6. Создать systemd unit для API
Файл `/etc/systemd/system/pitchcopytrade-api.service`:
```ini
[Unit]
Description=PitchCopyTrade API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pitchcopytrade/app
Environment=PYTHONPATH=/opt/pitchcopytrade/app/src
ExecStart=/opt/pitchcopytrade/app/.venv/bin/uvicorn pitchcopytrade.api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 7. Создать systemd unit для bot
Файл `/etc/systemd/system/pitchcopytrade-bot.service`:
```ini
[Unit]
Description=PitchCopyTrade Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pitchcopytrade/app
Environment=PYTHONPATH=/opt/pitchcopytrade/app/src
ExecStart=/opt/pitchcopytrade/app/.venv/bin/python -m pitchcopytrade.bot.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 8. Создать systemd unit для worker
Файл `/etc/systemd/system/pitchcopytrade-worker.service`:
```ini
[Unit]
Description=PitchCopyTrade Worker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pitchcopytrade/app
Environment=PYTHONPATH=/opt/pitchcopytrade/app/src
ExecStart=/opt/pitchcopytrade/app/.venv/bin/python -m pitchcopytrade.worker.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 9. Включить сервисы
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pitchcopytrade-api
sudo systemctl enable --now pitchcopytrade-bot
sudo systemctl enable --now pitchcopytrade-worker
sudo systemctl status pitchcopytrade-api
sudo systemctl status pitchcopytrade-bot
sudo systemctl status pitchcopytrade-worker
```

### 10. Настроить nginx для `pct.test.pbull.kz`
Файл `/etc/nginx/sites-available/pct.test.pbull.kz`:
```nginx
server {
    listen 80;
    server_name pct.test.pbull.kz;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включить конфиг:
```bash
sudo ln -s /etc/nginx/sites-available/pct.test.pbull.kz /etc/nginx/sites-enabled/pct.test.pbull.kz
sudo nginx -t
sudo systemctl reload nginx
```

### 11. Выпустить TLS сертификат
```bash
sudo certbot --nginx -d pct.test.pbull.kz
```

### 12. Финальная проверка
Проверить:
- `https://pct.test.pbull.kz/catalog`
- `https://pct.test.pbull.kz/login`
- login `admin1 / admin-demo-pass`
- login `author1 / author-demo-pass`
- в Telegram у `@Avt09_Bot` выполнить:
  - `/catalog`
  - `/confirm_buy momentum-ru-month`
  - `/feed`
- в admin web подтвердить payment
- снова выполнить `/feed`

### 13. Обновление сервера
```bash
cd /opt/pitchcopytrade/app
git pull
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m compileall src tests
./.venv/bin/pytest
sudo systemctl restart pitchcopytrade-api
sudo systemctl restart pitchcopytrade-bot
sudo systemctl restart pitchcopytrade-worker
```
