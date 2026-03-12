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
- admin subscription registry
- payment review -> confirm -> subscription activation
- automatic `T-Bank` pending payment sync via worker
- `T-Bank` callback endpoint for provider-driven payment confirmation
- legal docs admin UI
- author workspace
- recommendation CRUD
- structured legs editor
- author publish workflow hardening
- preview
- moderation queue
- moderation history baseline
- moderation `file-mode` parity
- public catalog
- checkout `stub/manual`
- ACL delivery
- Telegram-first subscriber baseline
- Telegram subscriber surface:
  - only `/start` and `/help` remain as bot commands
  - Mini App is the main client interface
  - no separate client login/password
  - Telegram verification page remains only as fallback for protected web pages
- scheduled publish baseline
- delivery notifications baseline
- delivery admin UI with retry history
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
  - `T-Bank pending payment -> worker sync -> subscriber activation`
- first server prototype deployed on target host with:
  - host nginx
  - dockerized `api + bot + worker`
  - test domain `pct.test.ptfin.ru`
  - canonical nginx upstream `127.0.0.1:8110`

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
- file mode уже поддержан не только на уровне config/runtime, но и в ключевом test contour;
- repository layer уже введен частично, но `notifications` и часть publishing paths еще не переведены на него полностью;
- `author` и `subscriber ACL/feed` уже могут идти через file repositories;
- `public checkout`, `staff auth` и `admin confirm path` уже проверены в `file` mode;
- `notifications` и часть publishing/delivery UX еще не имеют полной file-repository parity;
- local filesystem storage backend уже является canonical path для file-mode attachments и legal docs;
- `docker-compose.yml` теперь держит `postgres` и `minio` только как optional profiles:
  - `local-db`
  - `local-minio`
- часть metadata и compose assumptions все еще ориентированы на bucket/object-key path.
- legal docs уже не только рендерятся из локальных markdown source files, но и управляются через admin editing flow.

Это значит:
- текущая реализация пригодна для продолжения продуктовой разработки;
- локальный test-launch contour уже можно честно запускать без PostgreSQL и без MinIO;
- следующий этап нужен не для первого запуска, а для parity/hardening и server operations.

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
- запускает `/start`
- открывает Mini App
- внутри Mini App работает с каталогом, оплатой, статусом и лентой
- оформляет подписку без отдельного клиентского входа
- после активации получает рекомендации по ACL

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
- subscriber bot surface physically reduced to:
  - `/start`
  - `/help`
- legacy subscriber command handlers removed from codebase
- catalog, status, оплаты, подписки, помощь и лента перемещены в единый Mini App workspace
- `/app/status` remains as web fallback landing page after Telegram verification
- redirect from `/app/*` to `/verify/telegram` when Telegram auth cookie is missing
- Mini App automatic auth bridge through verified Telegram `initData`
- `/miniapp` is the canonical bootstrap entry for subscriber auth inside Telegram
- `/app/catalog`, `/app/subscriptions`, `/app/payments`, `/app/help`, `/app/feed` form the canonical subscriber workspace
- Mini App checkout is now linked to the current Telegram identity instead of a detached web checkout record
- provider-aware checkout:
  - `stub_manual` fallback
  - `tbank` SBP adapter
  - automatic `T-Bank` state sync for pending payments
  - `T-Bank` notify endpoint on `/payments/tbank/notify`
- Mini App workspace reuses Telegram auth cookie and shows subscriber overview with quick actions
- каждая страница Mini App может тихо переподтвердить Telegram WebApp `initData` и обновить subscriber session без отдельного входа
- Mini App self-service now includes:
  - детальные страницы подписки и оплаты
  - отмену `pending` заявки внутри Mini App
  - отмену подписки из карточки подписки
  - переключение автопродления внутри Mini App
  - русские статусы для подписок и оплат
  - обновление статуса оплаты
  - повторную оплату для `failed / expired / cancelled`
  - продление подписки из карточки подписки
  - промокод внутри retry и renewal flow
  - result messaging по текущему состоянию оплаты
  - историю статусов оплаты
  - историю продлений по продукту
  - worker-driven reminders по pending оплате и скорому окончанию подписки
  - центр напоминаний внутри Mini App
  - настройки напоминаний по оплатам и подпискам
  - единая лента событий подписчика по оплатам и продлениям
- ручные скидки для mutable `pending` `stub_manual` платежей на стороне admin
- worker lifecycle now applies:
  - автоматический перевод `pending` платежей в `expired`
  - автоматическую отмену связанных `pending` подписок
  - автоматический перевод истекших `active/trial` подписок в `expired`

## Ближайшая цель
Первый server prototype уже поднят. Ближайшая цель теперь не запуск, а переход к product-complete state:
1. довести real SBP lifecycle до production-ready состояния;
2. закончить remaining file-mode parity и ops hardening;
3. усилить support tooling и observability;
4. довести production payment/delivery reliability;
5. закрыть оставшиеся analytics/promotions gaps.

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
  - `Telegram /start -> Mini App open`
  - `Mini App checkout -> pending payment`
  - `POST /admin/payments/{id}/confirm -> 303`
  - `Mini App feed/status -> visible recommendation after activation`

## Правило следующих этапов
Новые задачи теперь должны выполняться так:
- менять код крупными блоками, а не добавлять очередной слой совместимости;
- не сохранять legacy subscriber flows, если принят новый canonical contour;
- после каждого завершенного блока делать `review -> tests -> docs sync`;
- docs должны описывать именно текущий canonical path, а не transitional backward-compatible mix.

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
   - `Telegram /start`
   - открыть `Mini App`
   - оформить подписку внутри `Mini App`
   - `admin confirm payment`
   - проверить `Mini App` статус и ленту
7. После review обновить description files:
   - `README.md`
   - `doc/blueprint.md`
   - `doc/task.md`
   - `doc/review.md`

Operational rule:
- не редактировать `storage/seed/*` вручную во время обычного smoke-test;
- все runtime-изменения должны жить только в `storage/runtime/*`;
- один и тот же bot token нельзя одновременно держать в polling на двух машинах.
- если `BASE_URL` работает по `http`, bot скрывает `Mini App` кнопку; Telegram WebApp доступен только на `https`.

## Следующий этап развития
Task list для test-launch можно считать закрытым. Следующий этап теперь такой:
1. Реальный платежный контур:
   - заменить `stub/manual` на реальный SBP provider
   - рекомендованный target: `T-Bank`
   - сохранить manual fallback для оператора
2. Remaining persistence and ops hardening:
   - full file-mode parity for remaining contours
   - compose cleanup `[done]`
   - storage backup/restore discipline
3. Support and observability hardening:
   - worker retries and observability baseline
   - delivery support tooling and audit visibility
4. Product analytics and monetization:
  - promo/discount lifecycle `[done baseline]`
  - done: admin promo registry, checkout apply path, redemption counters, manual discounts, richer Mini App promo UX, expiry/cancel flows
  - lead source analytics `[partial]`
  - baseline already done: normalized checkout attribution and admin lead source report
  - moderation analytics/SLA UX `[partial]`
  - baseline already done: queue filters, overdue SLA and resolution latency
5. Telegram UX depth:
   - более глубокая настройка центра напоминаний и типов уведомлений
   - расширение WebApp bridge на более сложные subscriber сценарии
   - расширенная история уведомлений и действий подписчика

## Что осталось до выполнения первоначальной задачи
Из исходной постановки уже закрыто:
- витрина стратегий
- выбор стратегии
- Telegram-first subscriber flow
- author cabinet baseline
- ACL delivery
- multi-author contour
- admin baseline

Еще не закрыто до business-complete state:
- реальная оплата по СБП в рублях;
- production payment/delivery reliability и support tooling.

## Рекомендуемый порядок задач
Чтобы дойти до следующего полноценного этапа без расползания scope, делать так:
1. remaining file-mode parity
2. callback rollout hardening on target host
3. lead source / promo / analytics hardening

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
   - открыть `Mini App`
   - оформить подписку внутри `Mini App`
9. Вернуться в admin web:
   - открыть payment queue
   - подтвердить pending payment
10. Снова в Telegram:
   - открыть `Mini App`
   - убедиться, что статус и рекомендации стали видны

## Запуск на выделенном сервере
Текущий рекомендованный серверный путь для test-version:
- `file mode`
- `docker compose`
- системный `nginx` сервера как reverse proxy
- polling bot, без webhook

Целевой DNS:
- `pct.test.ptfin.ru`

### 1. Подготовка сервера
Предположение:
- CentOS Linux 8
- Docker Engine и Docker Compose plugin уже установлены
- DNS `pct.test.ptfin.ru` уже указывает на IP сервера
- открыт входящий `80/tcp`
- текущий test bot больше нигде не запущен в polling

### 2. Разложить проект
```bash
mkdir -p /var/www
cd /var/www
git clone <REPO_URL> pct
cd /var/www/pct
```

### 3. Secret-файл
На сервере используйте отдельный secret file:
- `/var/www/pct/.env.server`

Шаблон уже лежит в проекте:
- [deploy/env.server.example](/Users/alexey/site/PitchCopyTrade/deploy/env.server.example)

Создание:
```bash
cd /var/www/pct
cp deploy/env.server.example .env.server
```

Минимум, что нужно заполнить:
- `APP_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- при необходимости `BASE_URL` и `ADMIN_BASE_URL`

Важно:
- `.env.server` не коммитится;
- локальный `.env` и серверный `.env.server` не смешивать.

### 4. Структура проекта на сервере
После `git clone` все должно жить прямо в `/var/www/pct`:
- код проекта
- [deploy/docker-compose.server.yml](/Users/alexey/site/PitchCopyTrade/deploy/docker-compose.server.yml)
- [deploy/nginx/pct.test.ptfin.ru.conf](/Users/alexey/site/PitchCopyTrade/deploy/nginx/pct.test.ptfin.ru.conf)
- `.env.server`
- `storage/seed`
- `storage/runtime`

### 5. Подготовить storage
```bash
mkdir -p /var/www/pct/storage/runtime/json
mkdir -p /var/www/pct/storage/runtime/blob
```
`storage/seed/*` уже приходит из git. Ничего отдельно копировать не нужно.

### 6. Готовые deploy-файлы
В проект уже добавлены:
- [deploy/docker-compose.server.yml](/Users/alexey/site/PitchCopyTrade/deploy/docker-compose.server.yml)
- [deploy/nginx/pct.test.ptfin.ru.conf](/Users/alexey/site/PitchCopyTrade/deploy/nginx/pct.test.ptfin.ru.conf)
- [deploy/env.server.example](/Users/alexey/site/PitchCopyTrade/deploy/env.server.example)
- [deploy/README.md](/Users/alexey/site/PitchCopyTrade/deploy/README.md)
- [guide.pdf](/Users/alexey/site/PitchCopyTrade/doc/guide.pdf)

Это и есть canonical server bundle для текущей test-version.

### 7. Установить nginx config на сервер
```bash
cd /var/www/pct
cp deploy/nginx/pct.test.ptfin.ru.conf /etc/nginx/conf.d/pct.test.ptfin.ru.conf
nginx -t
systemctl reload nginx
```

### 8. Поднять контейнеры
```bash
cd /var/www/pct
docker compose -f deploy/docker-compose.server.yml build
docker compose -f deploy/docker-compose.server.yml up -d
```

Важно:
- системный `nginx` должен проксировать именно на `http://127.0.0.1:8110`;
- старый upstream `127.0.0.1:8000` для текущего deploy bundle больше невалиден;
- после изменения зависимостей контейнеры нужно пересобрать, не только перезапустить.

### 9. Проверить контейнеры и логи
```bash
cd /var/www/pct
docker compose -f deploy/docker-compose.server.yml ps
docker compose -f deploy/docker-compose.server.yml logs --tail=100 api
docker compose -f deploy/docker-compose.server.yml logs --tail=100 bot
docker compose -f deploy/docker-compose.server.yml logs --tail=100 worker
```

### 10. Smoke-check API и сайта
```bash
curl -I http://127.0.0.1:8110/catalog
curl -I http://pct.test.ptfin.ru/catalog
curl -I http://pct.test.ptfin.ru/login
```

Если на CentOS 8 контейнеры не могут писать в `storage`, проверьте SELinux:
```bash
getenforce
ls -laZ /var/www/pct/storage
```
В compose уже выставлены bind mounts с `:Z`.

### 11. Финальная ручная проверка
Проверить:
- `http://pct.test.ptfin.ru/catalog`
- `http://pct.test.ptfin.ru/login`
- login `admin1 / admin-demo-pass`
- login `author1 / author-demo-pass`
- в Telegram у `@Avt09_Bot` выполнить:
  - `/start`
  - открыть `Mini App`
  - оформить подписку внутри `Mini App`
- в admin web подтвердить payment
- снова открыть `Mini App` и проверить статус/ленту

### 12. Обновление сервера
```bash
cd /var/www/pct
git pull
docker compose -f deploy/docker-compose.server.yml build
docker compose -f deploy/docker-compose.server.yml up -d
```

### 13. Полный cold start runtime
Seed не трогать. Чистится только runtime:
```bash
rm -rf /var/www/pct/storage/runtime
mkdir -p /var/www/pct/storage/runtime/json
mkdir -p /var/www/pct/storage/runtime/blob
cd /var/www/pct
docker compose -f deploy/docker-compose.server.yml restart api bot worker
```
