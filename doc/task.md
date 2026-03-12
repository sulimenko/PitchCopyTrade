# PitchCopyTrade Task Pack

Дата: 2026-03-12  
Режим: current implementation status + migration roadmap to local storage and file mode

Current review checkpoint:
- `2026-03-12`
- full regression suite: `165 passed`
- no critical findings
- current focus shifts from baseline delivery to product hardening and subscriber UX depth

Process rule:
- after each completed implementation step, run review first;
- only after review update all current description files:
  - [README.md](/Users/alexey/site/PitchCopyTrade/README.md)
  - [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
  - [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
  - [review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)

Статусы:
- `[done]`
- `[partial]`
- `[refactor]`
- `[todo]`

## 1. Что уже сделано

### 1. Foundation infrastructure `[done]`
- project skeleton
- `api`, `bot`, `worker`
- Docker baseline
- `.env.example`

### 2. Config and runtime `[done]`
- typed settings
- runtime bootstrap
- base logging
- fail-fast env

### 3. Database foundation `[done]`
- domain models
- enums
- constraints
- ORM relationships

### 4. Alembic foundation `[done]`
- Alembic env
- initial migration
- migration smoke path

### 5. FastAPI baseline `[done]`
- health
- ready
- meta
- lifespan

### 6. Bot baseline `[done]`
- aiogram app
- dispatcher
- `/start`

### 7. Worker baseline `[done]`
- worker loop
- job registry

### 8. Storage baseline `[done]`
- attachment storage wrapper exists
- upload/download/delete/stat contract exists

### 9. Auth foundation `[done]`
- password hashing
- session token
- role mapping

### 10. Compliance foundation `[done]`
- legal docs model
- consent-before-payment logic

### 11. Staff web baseline `[done]`
- auth UI for staff
- admin dashboard
- strategy CRUD
- subscription product CRUD
- payment review / confirm / activation

### 12. Author workspace baseline `[done]`
- author dashboard
- recommendation CRUD
- own-strategy scoping
- preview
- structured legs
- attachments

### 13. Subscriber commerce baseline `[done]`
- public catalog
- strategy detail
- checkout `stub/manual`
- Telegram subscriber baseline
- Telegram-auth fallback for `/app/*`
- ACL delivery in web and bot

### 13.1 Telegram-only subscriber reset `[done]`
- subscriber bot commands reduced to `/start` and `/help`
- Mini App became the main client surface for catalog, status, payments and feed
- subscriber-facing web pages removed `Вход` and legacy `/web` guidance
- checkout no longer asks client for manual timezone or lead source
- Mini App context is preserved across catalog, strategy and checkout pages

### 14. Recommendation lifecycle baseline `[done]`
- moderation queue
- moderation history baseline
- scheduled publish baseline
- delivery notifications baseline

## 2. Что исследование признало transitional

### 15. Remote storage as primary model `[refactor]`
Текущее состояние:
- attachment flow ориентирован на `MinIO`
- `docker-compose.yml` больше не делает `minio` обязательным runtime service
- metadata по-прежнему bucket/object oriented

Новая цель:
- primary storage = локальная файловая система
- `MinIO` максимум optional compatibility backend

### 16. DB-only runtime `[refactor]`
Текущее состояние:
- `db` mode по-прежнему поддержан
- `file` mode уже работает для test contour
- remaining проблема не в отсутствии file mode, а в неполной parity

Новая цель:
- `db` mode через `PostgreSQL`
- `file` mode без БД для тестирования

### 17. Current web fallback surfaces `[partial]`
Сделано:
- subscriber web fallback уже зависит от Telegram-auth path

Нужно:
- не углублять fallback как primary path
- перевести его на storage/file-mode parity

## 3. Новый обязательный migration track

### 18. Local filesystem storage foundation `[done]`
Сделано:
- общий storage contract
- `LocalFilesystemStorage`
- `APP_STORAGE_ROOT`
- default runtime blob root `storage/runtime/blob`
- local storage tests
- attachment download path understands `storage_provider=local_fs`
- author/document flows already use local filesystem path in file mode

Acceptance:
- attachments можно сохранять и читать без `MinIO`
- local path становится canonical metadata source

### 19. Runtime switch for persistence `[done]`
Сделано:
- введен `APP_DATA_MODE=db|file`
- введен `APP_STORAGE_ROOT`
- runtime metadata now exposes data mode and storage root
- `file` mode не требует `DATABASE_URL`, `ALEMBIC_DATABASE_URL` и `MINIO_ROOT_PASSWORD` на уровне config/runtime
- DB engine создается только в `db` mode

Acceptance:
- приложение стартует в двух режимах без правки application code

### 20. Repository abstraction `[partial]`
Сделано:
- repository package introduced
- `SqlAlchemyAuthorRepository`
- `SqlAlchemyAccessRepository`
- `FileAuthorRepository`
- `FileAccessRepository`
- `FilePublicRepository`
- `FileAuthRepository`
- `FileDataStore`
- `FileDatasetGraph`
- repository deps for FastAPI
- author service layer detached from direct `AsyncSession` usage
- ACL/feed service layer detached from direct `AsyncSession` usage
- `author`, `ACL/feed`, `public`, `auth` and verified admin smoke paths now switch to file repositories in `APP_DATA_MODE=file`

Сделать:
- вынести critical persistence operations в repositories
- подготовить dual implementation:
  - DB repositories
  - file repositories

Минимальный scope:
- users / roles
- authors
- strategies
- products
- legal docs / consents
- payments / subscriptions
- recommendations / legs / attachments

Acceptance:
- service layer не зависит напрямую от `AsyncSession`

### 21. File repositories for demo path `[partial]`
Сделано:
- JSON-backed file datasets under `storage/runtime/json` with bootstrap from `storage/seed/json`
- file repositories for minimal demo scope:
  - users
  - roles
  - authors
  - strategies
  - products
  - legal docs
  - payments
  - subscriptions
  - recommendations
  - recommendation legs
  - recommendation attachments
- hydration graph into ORM-like domain objects
- author create/edit persistence can now save recommendations, legs and attachments without DB
- ACL/feed can now read user entitlements and recommendations without DB
- committed demo seed datasets in `storage/seed/json`
- committed demo blob attachment in `storage/seed/blob`
- `staff auth`, `admin dashboard` and `author dashboard` verified in `file` mode
- `Telegram checkout -> admin confirm -> Telegram feed` verified in `file` mode on fresh temp storage root

Сделать:
- safe write hardening and concurrent-write strategy
- expand file repo coverage to moderation flows
- add seed/bootstrap generator and real file-mode execution path for complete local demo

Acceptance:
- можно пройти demo flow без PostgreSQL

### 22. Local attachment and legal files `[partial]`
Сделано:
- local attachment backend exists
- local attachment download branch exists
- author uploads по умолчанию в `storage/runtime/blob`
- subscriber downloads из `storage/runtime/blob`
- legal documents now support `source_path`
- public legal page renders markdown from local storage path
- seed legal markdown files committed under `storage/seed/blob/legal`

Сделать:
- убрать transitional dependency from remaining MinIO-only paths

Acceptance:
- `MinIO` не нужен для локального smoke-test

### 23. File-mode seed data `[done]`
Сделано:
- seeded staff accounts
- seeded subscriber account
- seeded strategies
- seeded products for `strategy / author / bundle`
- seeded legal docs
- seeded payment/subscription demo records
- seeded recommendations for feed demo
- seeded local attachment blob
- runtime bootstrap copies seed into local ignored runtime tree

Acceptance:
- локальный запуск больше не требует ручного наполнения через БД для demo read-path
- file repositories имеют committed demo dataset в репозитории
- локальные изменения тестировщика уходят в ignored runtime tree, а не в tracked seed

### 24. File-mode payment/subscription demo `[done]`
Сделано:
- file-backed checkout artifacts
- manual payment confirm path
- activation path
- verified path:
  - `Telegram /start -> Mini App`
  - `Mini App checkout`
  - `payment pending`
  - `admin confirm`
  - `subscriber /app/feed` sees recommendation after activation

Acceptance:
- subscriber flow можно проверить локально end-to-end

### 24.1 File-mode process startup `[done]`
Сделано:
- `api` cold-start smoke in `APP_DATA_MODE=file`
- `bot` cold-start smoke in `APP_DATA_MODE=file`
- real Telegram API smoke for test bot `Avt09_Bot`
- `worker` cold-start smoke in `APP_DATA_MODE=file`
- public catalog/legal flow works without PostgreSQL
- bot shop handlers work with file repository path
- worker scheduled publish runner has file-mode branch
- seeded author login and author dashboard work in file mode
- verified e2e on fresh temp storage root:
  - `admin` login -> dashboard
  - `author` login -> dashboard
  - `Telegram checkout -> confirm -> feed`

Acceptance:
- `api + bot + worker` можно поднимать без PostgreSQL и без MinIO
- локальный smoke path опирается на committed seed + ignored runtime tree
- test bot token from `.env` подтвержден реальным `getMe` check

## 4. Что уже реализовано и должно сохраниться в refactor

### 25. Telegram-first subscriber model `[partial]`
Сделано:
- subscriber path moved to Telegram-first baseline
- no subscriber password-first requirement
- Telegram-auth fallback exists

Нужно сохранить:
- primary identity = `telegram_user_id`
- minimum necessary data policy

### 26. Staff auth and workspaces `[partial]`
Сделано:
- admin/author/moderator web auth
- admin dashboard
- author workspace
- moderation queue

Нужно сохранить:
- staff flows должны работать и в `db`, и в `file` mode

### 27. ACL and payment lifecycle `[partial]`
Сделано:
- checkout -> payment pending -> confirm -> subscription activation
- ACL gating in web and bot

Нужно сохранить:
- одинаковое поведение в `db` и `file` mode

### 28. Recommendation lifecycle `[partial]`
Сделано:
- recommendation CRUD
- moderation
- publish/schedule
- notifications baseline

Нужно сохранить:
- scheduled publish
- attachment rendering
- scope and ACL guarantees

## 5. Самый быстрый путь к локальному тестированию

### 29. Fast-track order `[done]`
Делать строго так:
1. local storage adapter
2. runtime switch `APP_DATA_MODE`
3. file repositories for minimal scope
4. seed data for file mode
5. local attachment serving
6. run `api + bot + worker` in file mode
7. connect test bot and run Telegram smoke-test
8. open local staff web and author cabinet

### 30. Fast-track acceptance `[done]`
Считать быстрый путь завершенным, когда:
- сайт открывается локально;
- admin login работает локально;
- author login работает локально;
- test bot отвечает и показывает каталог;
- можно оформить `stub/manual` checkout;
- можно подтвердить платеж и увидеть доступ к feed;
- все это проходит без PostgreSQL и без `MinIO`.

## 6. После этого остаются продуктовые задачи

### 31. Telegram UX depth `[partial]`
Сделано:
- Telegram-only command surface:
  - `/start`
  - `/help`
- reply keyboard reduced to Mini App + help
- Mini App entry baseline
- deployed `https` host now allows Telegram `Mini App` button in real bot flow
- subscriber navigation moved into Mini App sections:
  - каталог
  - подписки
  - оплаты
  - лента
  - помощь
- web fallback now redirects to `/verify/telegram` instead of raw unauthorized response
- timezone is auto-detected from client/browser
- lead source attribution is automatic

Не сделано:
- full WebApp auth bridge
- richer in-app actions beyond current Mini App pages

### 32. Legal admin UI `[done]`
- document CRUD
- version publish UI
- active version management

### 33. Promo/discount lifecycle `[done baseline]`
Сделано:
- admin promo registry
- promo create/edit UI
- checkout promo apply path
- payment-linked redemption counters
- manual discounts
- richer Telegram promo UX inside retry/renew flows
- expiry/cancel flows

Acceptance:
- admin can apply a manual discount before confirming a mutable payment
- subscriber can reuse or replace a promo code inside Mini App retry/renew flows
- expired payments and subscriptions transition without manual DB edits

### 34. Delivery admin UX `[done]`
- notification queue
- retry/dedup
- delivery audit visibility
- metrics still remain as hardening, not as baseline blocker

### 35. Moderation analytics/SLA `[partial]`
Сделано:
- queue filters by query and status
- overdue review visibility
- approve/rework/reject counters
- resolution latency metric on queue and detail

Сделать:
- richer timeline slicing
- moderator workload breakdown
- export/reporting

### 36. Lead source analytics `[partial]`
Сделано:
- normalized lead source attribution on checkout
- file/db compatible source lookup and creation
- admin lead source analytics report

Сделать:
- richer campaign breakdown
- time-range filtering
- conversion slices by source

### 37. Worker hardening `[partial]`
Сделано:
- per-job fault tolerance in worker loop
- per-job duration logging
- notification retries baseline

Сделать:
- broader lifecycle jobs
- stronger metrics/export path

## 8. Следующий этап после test-launch

### 38. Deployment hardening `[done]`
Сделано:
- canonical server deploy path documented
- dedicated docker server compose committed in repo
- host `nginx` reverse proxy config committed in repo
- committed deploy bundle inside repo:
  - `deploy/docker-compose.server.yml`
  - `deploy/nginx/pct.test.ptfin.ru.conf`
  - `deploy/env.server.example`
  - `deploy/README.md`
  - `doc/guide.pdf`
- canonical server root `/var/www/pct`
- secret runtime file `.env.server`
- update/restart procedure documented

Сделано:
- first server prototype validated on target host
- `admin` login validated on deployed host
- Telegram bot polling validated on deployed host
- `https` enabled for `pct.test.ptfin.ru`

Acceptance:
- test version можно поднимать на одной выделенной машине без ручного старта процессов

### 39. Compose cleanup `[done]`
- `postgres` and `minio` live behind optional compose profiles
- `api` and `worker` no longer hard depend on MinIO in file mode
- real server path is separated from dev-only assumptions

Acceptance:
- file-mode compose path не требует MinIO по умолчанию

### 40. Full file-mode parity `[partial]`
- notifications persistence edges
- publishing edge cases
- remaining auth/session fallback paths

Acceptance:
- all critical test-version contours behave одинаково в `db` и `file`

### 41. Legal admin UI hardening `[done]`
- local markdown editor
- version activation
- active document management

Acceptance:
- legal docs можно править без ручного редактирования файлов на сервере

### 42. Telegram UX phase `[done]`
Сделано:
- conditional WebApp button behavior for `http` vs `https` environments
- subscriber bot surface reduced to `/start` and `/help`
- legacy subscriber bot handlers physically removed from the codebase
- Telegram verification page for web fallback
- safe local `next` redirect in `/tg-auth`
- `/app/status` as web fallback landing page after Telegram verification
- Mini App automatic auth bridge through `/tg-webapp/auth`
- `/miniapp` became the canonical Telegram bootstrap entry
- canonical subscriber workspace now lives at:
  - `/app/catalog`
  - `/app/status`
  - `/app/subscriptions`
  - `/app/payments`
  - `/app/feed`
  - `/app/help`
- Mini App catalog/workspace shows subscriber overview when Telegram auth cookie already exists
- Mini App checkout now uses Telegram-linked identity and accepted legal docs
- public site and Mini App subscriber routes are split into separate canonical surfaces without `surface=miniapp` compatibility mode

Acceptance:
- subscriber flow больше не зависит от legacy bot command interaction
- Mini App is the canonical subscriber UI instead of a web/catalog overlay

### 43. Mini App self-service detail/actions `[done]`
Сделано:
- subscriber payment detail page
- subscriber subscription detail page
- `pending` payment cancellation from Mini App
- autorenew toggle from Mini App
- Russian status labels for payment and subscription lifecycle

Acceptance:
- subscriber can inspect payment/subscription state without staff help
- subscriber can cancel a pending payment request from Mini App
- subscriber can manage autorenew inside Mini App
- Mini App does not expose raw English enum values for payment/subscription lifecycle

### 44. Mini App payment recovery and renewal `[done]`
Сделано:
- payment refresh action for provider-driven `pending` payments
- payment retry flow for `failed / expired / cancelled`
- subscription renewal flow from Mini App
- redirect from retry/renew into the newly created payment detail page

Acceptance:
- subscriber can recover an unfinished payment scenario without staff help
- subscriber can start renewal from the current subscription card
- recovery flow stays inside Mini App and remains Telegram-linked

### 45. Mini App payment messaging/history and reminders `[done]`
Сделано:
- payment result messaging inside payment detail page
- provider state history rendering inside payment detail page
- renewal history rendering inside subscription detail page
- worker-driven subscriber reminders:
  - pending payment reminder
  - expiring subscription reminder
- reminder dedup through audit events

Acceptance:
- subscriber sees a clear next step on payment detail page
- subscriber can inspect payment history and renewal history inside Mini App
- worker reminders do not repeat endlessly on each tick for the same payment/subscription
### 46. Reminder center, notification preferences and timeline `[done]`
Сделано:
- страница центра напоминаний в Mini App
- настройки напоминаний подписчика по оплатам и подпискам
- единая страница событий по оплатам и подпискам
- отправка напоминаний теперь учитывает сохраненные настройки подписчика

Acceptance:
- subscriber can review reminder history inside Mini App
- subscriber can enable/disable reminder categories without staff help
- Mini App exposes a unified event timeline for payments and subscriptions
### 47. Full WebApp auth bridge and richer Mini App actions `[done]`
Сделано:
- полный WebApp auth bridge для всех Mini App страниц
- action cards на статус-экране
- inline действия в списках оплат и подписок
- промокод в retry/renew flows
- отмена подписки из subscriber card
- staff-side manual discount для `pending` `stub_manual` платежей
- worker expiry/cancel lifecycle для платежей и подписок

Acceptance:
- subscriber can open any Mini App page and stay inside Telegram-backed auth contour
- subscriber can restore failed payment flow, renew access and stop a subscription without leaving Mini App
- mutable payment discounts do not require direct DB edits
- due payment/subscription lifecycle changes happen automatically in worker
### 48. Release and review discipline `[todo]`
- clean runtime checklist
- technical review checklist
- product smoke checklist
- docs sync checklist

Acceptance:
- каждый новый этап проходит одинаковый `clean -> review -> docs -> deploy` контур

## 9. Что делать дальше до business-complete state

### 49. HTTPS enablement `[done]`
- certificate issued for `pct.test.ptfin.ru`
- deployed `BASE_URL` switched to `https`
- Telegram WebApp prerequisites validated on deployed host

Acceptance:
- deployed host serves app over `https`
- bot can safely expose `Mini App` button

### 50. Real SBP payments `[partial]`
Сделано:
- provider-aware checkout service
- `T-Bank` SBP adapter foundation
- `stub/manual` kept as operator fallback
- provider payment id is persisted in checkout records
- worker `payment_expiry_sync` polls pending `T-Bank` payments through `GetState`
- confirmed provider state auto-activates linked subscriptions
- terminal failed provider state auto-cancels pending subscriptions
- sync writes `worker.payment_state_sync` audit events
- runtime dependency `httpx` moved to main project dependencies because live payment code imports it outside test-only scope
- `T-Bank` callback endpoint exists at `/payments/tbank/notify`
- callback token is validated before payment state update
- callback path writes `payment.webhook_sync` audit events

Сделать:
- production credential rollout on target host
- callback rollout hardening on target host

Acceptance:
- user can pay in RUB via real SBP flow
- payment confirmation does not rely only on manual admin action

### 51. Admin subscription registry `[done]`
- full list of subscriptions
- start/end dates
- payment status
- search by user / strategy / author
- access scope visibility

Acceptance:
- admin can answer who is subscribed to what and until when

### 52. Author publish UX hardening `[done]`
- better multi-leg recommendation editor
- attachment replace/delete flow
- clearer draft/review/publish path

Acceptance:
- author can publish complex recommendation sets without manual operator help

### 53. Legal and compliance operations `[done]`
- legal docs admin UI
- version activation
- consent visibility in admin surfaces

Acceptance:
- legal lifecycle no longer requires manual file edits in runtime operations

### 54. Delivery operations `[done]`
- notification queue
- retry / dedup visibility
- delivery audit visibility for support

Acceptance:
- support/admin can understand whether recommendation delivery succeeded

### 52. Final persistence hardening `[todo]`
- finish remaining file-mode parity
- compose cleanup `[done]`
- backup/restore workflow for `storage/`

Acceptance:
- deployed prototype can be operated and recovered predictably

## 7. Правила, которые нельзя ломать
- subscriber path остается `Telegram-first`
- `admin`, `author`, `moderator` остаются отдельным staff contour
- pending payment не дает доступ
- entitlement rules одинаковы в web и bot
- новые шаги не должны усиливать remote storage dependency
- новые шаги не должны делать БД обязательной для базового локального тестирования
### Server deploy note
- host nginx canonical upstream must be `127.0.0.1:8110`
