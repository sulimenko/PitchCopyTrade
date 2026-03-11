# PitchCopyTrade Task Pack

Дата: 2026-03-11  
Режим: current implementation status + migration roadmap to local storage and file mode

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

### 14. Recommendation lifecycle baseline `[done]`
- moderation queue
- moderation history baseline
- scheduled publish baseline
- delivery notifications baseline

## 2. Что исследование признало transitional

### 15. Remote storage as primary model `[refactor]`
Текущее состояние:
- attachment flow ориентирован на `MinIO`
- `docker-compose.yml` поднимает `minio`
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
- admin/legal editing flow for writing local markdown sources
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
  - `Telegram /confirm_buy`
  - `payment pending`
  - `admin confirm`
  - `subscriber /feed` sees recommendation after activation

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

### 29. Fast-track order `[todo]`
Делать строго так:
1. local storage adapter
2. runtime switch `APP_DATA_MODE`
3. file repositories for minimal scope
4. seed data for file mode
5. local attachment serving
6. run `api + bot + worker` in file mode
7. connect test bot and run Telegram smoke-test
8. open local staff web and author cabinet

### 30. Fast-track acceptance `[todo]`
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
- command baseline
- reply keyboard baseline
- Mini App entry baseline

Не сделано:
- full WebApp auth bridge
- richer interactive checkout/status UX

### 32. Legal admin UI `[todo]`
- document CRUD
- version publish UI
- active version management

### 33. Promo/discount lifecycle `[todo]`
- promo UI
- manual discounts
- expiry/cancel flows

### 34. Delivery admin UX `[todo]`
- notification queue
- retry/dedup
- metrics

### 35. Moderation analytics/SLA `[todo]`
- filters
- timelines
- resolution metrics

### 36. Lead source analytics `[todo]`
- normalized attribution
- reporting

### 37. Worker hardening `[todo]`
- retries
- observability
- broader lifecycle jobs

## 8. Следующий этап после test-launch

### 38. Deployment hardening `[partial]`
Сделано:
- canonical server deploy path documented
- dedicated docker server compose committed in repo
- host `nginx` reverse proxy config committed in repo
- committed deploy bundle inside repo:
  - `deploy/docker-compose.server.yml`
  - `deploy/nginx/pct.test.ptfin.ru.conf`
  - `deploy/env.server.example`
  - `deploy/README.md`
- canonical server root `/var/www/pct`
- secret runtime file `.env.server`
- update/restart procedure documented

Сделать:
- real server validation on target host
- optional TLS step when test domain is ready

Acceptance:
- test version можно поднимать на одной выделенной машине без ручного старта процессов

### 39. Compose cleanup `[todo]`
- убрать `MinIO-first` dependency from `api` and `worker` in `file` mode
- separate dev-only compose assumptions from real server path
- keep PostgreSQL and MinIO as optional profiles, not mandatory runtime blocks

Acceptance:
- file-mode compose path не требует MinIO по умолчанию

### 40. Full file-mode parity `[todo]`
- moderation decisions
- notifications persistence edges
- publishing edge cases
- remaining auth/session fallback paths

Acceptance:
- all critical test-version contours behave одинаково в `db` и `file`

### 41. Legal admin UI `[todo]`
- local markdown editor
- version activation
- active document management

Acceptance:
- legal docs можно править без ручного редактирования файлов на сервере

### 42. Telegram UX phase `[todo]`
- WebApp auth bridge
- richer menu/status flow
- subscriber self-service UX
- conditional WebApp button behavior for `http` vs `https` environments

Acceptance:
- subscriber flow меньше зависит от command-only interaction

### 43. Release and review discipline `[todo]`
- clean runtime checklist
- technical review checklist
- product smoke checklist
- docs sync checklist

Acceptance:
- каждый новый этап проходит одинаковый `clean -> review -> docs -> deploy` контур

## 7. Правила, которые нельзя ломать
- subscriber path остается `Telegram-first`
- `admin`, `author`, `moderator` остаются отдельным staff contour
- pending payment не дает доступ
- entitlement rules одинаковы в web и bot
- новые шаги не должны усиливать remote storage dependency
- новые шаги не должны делать БД обязательной для базового локального тестирования
