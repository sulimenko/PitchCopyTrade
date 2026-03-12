# PitchCopyTrade Blueprint

Дата: 2026-03-12  
Статус: research-based current state + target migration architecture

## 1. Назначение
Этот документ фиксирует:
- что уже реально реализовано в проекте;
- какие ограничения найдены в текущей persistence architecture;
- к какой схеме теперь нужно прийти;
- какой migration path нужен, чтобы быстро получить локальный тестовый контур.

## 1.1 Обязательный delivery process
Для каждого завершенного implementation step действует правило:
- сначала выполнить review результата;
- затем обновить все актуальные description files проекта.
- если пользователь дал общее разрешение на последовательное выполнение задач, следующий согласованный step запускать без ожидания дополнительного подтверждения, пока не будет достигнут естественный blocker.
- все следующие задачи выполнять крупными блоками без сохранения backward compatibility, если новый canonical contour уже согласован.
- legacy layers, shim-ы и временные переходные пути нужно удалять, а не поддерживать бесконечно.

Актуальные description files:
- [README.md](/Users/alexey/site/PitchCopyTrade/README.md)
- [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- [review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)

## 2. Продуктовый контур

### 2.1 Subscriber model
Canonical subscriber model остается:
- `Telegram-first`;
- основной канал взаимодействия: `Telegram bot`;
- bot command surface intentionally reduced to `/start` and `/help`;
- legacy subscriber bot handlers and command-only flows must be removed, not preserved behind compatibility shims;
- вся клиентская навигация должна жить внутри `Mini App`;
- web для подписчика допустим только как:
  - публичная витрина;
  - legal pages;
  - Telegram-authenticated fallback;
  - `Telegram WebApp / Mini App` на `https`-стенде.

### 2.2 Staff model
`admin`, `author`, `moderator` остаются в web-контуре:
- вход через `login/password`;
- отдельный auth contour от subscriber.

## 3. Что уже реально есть в коде

### 3.1 Infrastructure baseline
Есть:
- `api`, `bot`, `worker`
- typed config
- health/ready/meta endpoints
- Docker baseline
- `.env.example`
- runtime switch baseline:
  - `APP_DATA_MODE=db|file`
  - `APP_STORAGE_ROOT=storage`
- repository layer baseline for selected contours
- cold-start file-mode smoke path for `api + bot + worker`

### 3.2 Domain baseline
Есть:
- users / roles / author_profiles
- strategies / bundles / subscription_products
- payments / subscriptions / promo_codes
- recommendations / legs / attachments
- legal_documents / user_consents
- lead_sources
- audit_events

### 3.3 Staff surfaces
Есть:
- staff auth
- admin dashboard
- strategy CRUD
- product CRUD
- payment queue and confirm flow
- admin subscription registry
- legal docs admin UI
- delivery admin UI with retry history
- author workspace
- author publish workflow hardening
- recommendation CRUD
- preview
- moderation queue
- moderation history baseline
- moderation routes and actions now work in `db` and `file` modes

### 3.4 Subscriber surfaces
Есть:
- public catalog
- web fallback checkout baseline
- Telegram bot commands:
  - `/start`
  - `/help`
- Mini App sections:
  - каталог
  - мои подписки
  - лента
  - оплаты
  - помощь
- Telegram verification page for web fallback
- redirect from protected `/app/*` surfaces to Telegram verification flow
- safe local `next` redirect support in `/tg-auth`
- `/app/status` as subscriber landing page in web fallback
- Mini App automatic auth bridge via verified Telegram `initData`
- `/miniapp` is the canonical Telegram bootstrap entry
- `/app/catalog`, `/app/subscriptions`, `/app/payments`, `/app/help`, `/app/feed` form a single subscriber workspace
- Mini App workspace is subscriber-aware when Telegram fallback cookie already exists
- Mini App checkout binds payment/subscription creation to the current Telegram identity
- provider-aware checkout service with `tbank` SBP adapter and `stub_manual` fallback
- worker-based pending `T-Bank` payment sync with automatic subscription activation on confirmed provider state
- `T-Bank` callback endpoint for provider-driven payment updates
- Telegram-auth fallback cookie for `/app/*`
- ACL-gated web feed and bot feed
- validated test bot token smoke via Telegram API `getMe`
- `https` host can expose Mini App safely
- timezone should be auto-detected from Telegram WebApp / browser when available, fallback `Europe/Moscow`
- lead source should be derived automatically, not entered by client manually
- strategy base demo price is `499 руб`; period labels should render as `Месяц`, trial labels as `7 дней бесплатно`
- required checkout documents should render with full Russian names:
  - `Предупреждение о рисках`
  - `Публичная оферта`
  - `Политика конфиденциальности`
  - `Согласие на оплату`

### 3.5 Recommendation lifecycle baseline
Есть:
- structured legs
- attachments
- publish / schedule baseline
- worker-based scheduled publish baseline
- delivery notifications baseline
- local filesystem storage backend baseline with `APP_STORAGE_ROOT=storage`
- runtime writes target `storage/runtime/*`
- committed seed target `storage/seed/*`
- attachments local-first by canonical `local_fs`
- legal documents local-first via `source_path` under `storage/*/blob/legal`
- worker `payment_expiry_sync` now resolves pending `T-Bank` payments in both `db` and `file` modes

### 3.6 Repository layer baseline
Есть:
- `SqlAlchemyAuthorRepository`
- `SqlAlchemyAccessRepository`
- `FileAuthorRepository`
- `FileAccessRepository`
- `FilePublicRepository`
- `FileAuthRepository`
- `FileDataStore`
- `FileDatasetGraph`
- FastAPI deps for repository wiring
- author services no longer talk to `AsyncSession` directly
- ACL/feed services no longer talk to `AsyncSession` directly
- `author` and `ACL/feed` deps can switch to file repositories in `APP_DATA_MODE=file`
- real demo seed pack under `storage/seed/json`
- real demo blob attachment under `storage/seed/blob`

Пока еще не переведены:
- notifications
- publishing
- часть auth/session fallback paths outside verified smoke contour

## 4. Что показало исследование текущего состояния

### 4.1 Current DB coupling
Сейчас проект уже не является жестко `PostgreSQL-only`, но parity еще не полная:
- `file` mode допускает runtime без DB DSN;
- DB engine создается только при `APP_DATA_MODE=db`;
- ключевой test contour уже идет без БД;
- часть контуров все еще имеет `SQLAlchemy-first` ветки и требует дальнейшего выравнивания.

### 4.2 Current storage coupling
Сейчас storage layer уже частично выровнен под local-first, но transitional следы остались:
- storage adapter `MinioStorage` все еще существует;
- compose все еще включает `minio` как штатный сервис;
- часть metadata shape и deploy assumptions еще bucket/object-key oriented;
- при этом file-mode attachments и legal docs уже работают через local filesystem path.

Уточнение по текущему состоянию:
- local filesystem storage backend уже добавлен в код;
- его runtime root идет из `APP_STORAGE_ROOT` и по умолчанию использует `storage/runtime/blob`;
- route download уже поддерживает `storage_provider=local_fs`;
- author upload path уже переключен на local filesystem по умолчанию;
- legal rendering уже умеет читать local markdown source files по `source_path`.

### 4.3 Что это означает practically
На сегодня проект:
- можно развивать как продуктовый baseline;
- можно запускать с внешним PostgreSQL и текущим storage stack;
- можно быстро и честно тестировать test contour без БД;
- нельзя считать всю persistence migration завершенной, потому что parity еще не полная.

## 5. Новая целевая persistence architecture

### 5.1 Главный принцип
Удаленный storage больше не должен быть primary model.

Primary persistence target:
- документы, вложения и служебные файлы хранятся локально;
- runtime должен поддерживать работу без БД для тестирования;
- один и тот же product behavior должен быть доступен и в `db` mode, и в `file` mode.

### 5.2 Canonical storage root
Единый корень:
- `storage/`
- `APP_STORAGE_ROOT` должен указывать именно на этот корень, где вместе живут `seed/` и `runtime/`

Целевое разбиение:
- `storage/seed/blob/`
  - committed demo attachments
  - committed demo legal source files
- `storage/seed/json/`
  - committed demo datasets
  - baseline file-mode bootstrap data
- `storage/runtime/blob/`
  - вложения рекомендаций
  - изображения
  - PDF
  - локальные runtime binary payload
- `storage/runtime/json/`
  - file repositories для сущностей
  - локальный mutable state тестировщика
- `storage/parquet/`
  - audit exports
  - analytics datasets
  - delivery logs / aggregates
- `storage/runtime/`
  - временные файлы
  - локальные очереди
  - техничeские state-файлы

### 5.3 Blob vs structured data rule
Использование должно быть таким:
- бинарные payload и документы: `blob`
- операционные сущности и справочники: `json`
- append-heavy, аналитические и экспортные наборы: `parquet`

`Parquet` не обязателен для самого первого шага.
Для быстрого локального тестирования сначала достаточно:
- `blob`
- `json`

Дополнение:
- recommendation attachments должны читаться и писаться в local filesystem path;
- legal markdown source files должны жить в local filesystem path и быть доступны для public/legal rendering.

## 6. Canonical runtime modes

### 6.1 `db` mode
Используется когда локальная или внешняя БД доступна.

Правила:
- `PostgreSQL` хранит операционные сущности;
- вложения и документы все равно хранятся локально в `storage/runtime/blob`;
- `MinIO` не должен быть обязательным;
- DSN приходит через `.env`.

### 6.2 `file` mode
Используется для локального тестирования и demo без БД.

Правила:
- БД не требуется;
- config/runtime не требуют `DATABASE_URL` и `ALEMBIC_DATABASE_URL`;
- сущности читаются и пишутся через файловые repositories;
- attachments и legal files хранятся локально;
- поведение app/bot/worker остается максимально близким к `db` mode;
- режим должен позволить прогнать основной сценарий на одной машине.
- в репозитории уже должен лежать demo seed pack, чтобы mode был runnable без ручного наполнения;
- runtime state тестировщика не должен коммититься.

Текущее подтверждение:
- `api` стартует и отдает `catalog`, `legal`, `staff login`;
- `bot` стартует на уровне runtime bootstrap и dispatcher assembly;
- test bot token resolves against Telegram API and returns expected bot identity;
- `worker` выполняет `run_worker_once()` без PostgreSQL и без MinIO.
- на свежем temp storage-root с copied seed подтвержден e2e:
  - `admin` login -> dashboard;
  - `author` login -> dashboard;
  - `Telegram checkout -> payment pending`;
  - `admin confirm -> subscription activation`;
  - `Telegram feed -> visible recommendation`.
- первый server prototype тоже подтвержден:
  - host nginx on target server;
  - dockerized `api + bot + worker`;
  - `admin` login works on deployed host;
  - Telegram bot polling works on deployed host.

### 6.3 Demo seed baseline
Текущий baseline теперь включает:
- seeded `roles`, `users`, `authors`
- seeded `lead_sources`, `instruments`
- seeded `strategies`, `bundles`, `products`
- seeded `legal_documents`
- seeded `payments`, `subscriptions`, `user_consents`
- seeded `recommendations`, `recommendation_legs`, `recommendation_attachments`
- seeded local blob file for attachment download smoke-test

Это означает:
- file-mode уже имеет входной demo dataset;
- локальный smoke path может опираться не только на тестовые фабрики, но и на реальные файлы в `storage/seed/*`, которые bootstrapятся в `storage/runtime/*`.

## 7. Canonical file-mode scope
Минимальный file-mode scope, без которого режим бесполезен:
- staff users and roles
- authors
- strategies
- subscription products
- legal documents and consents
- subscribers by `telegram_user_id`
- payments
- subscriptions
- recommendations
- recommendation legs
- recommendation attachments
- lead sources baseline

Допустимая первая версия:
- без полной транзакционности уровня PostgreSQL;
- но без нарушения ACL, payment states и ownership scope.

## 8. Что нужно переиспользовать, а не выкидывать
Новая схема не отменяет уже сделанное.

Нужно сохранить:
- Telegram-first subscriber contour
- staff auth contour
- admin dashboard
- author workspace
- moderation queue
- payment/subscription lifecycle
- ACL logic
- scheduled publish flow
- notifications baseline

Нужно переделать только слой persistence и storage integration, а не продуктовую модель целиком.

## 9. Transitional areas

### 9.1 MinIO
С этого момента `MinIO` считается transitional.

Допустимо:
- временно сохранить adapter как secondary backend;
- использовать его только пока не внедрен local filesystem backend.

Недопустимо:
- углублять проект в `MinIO-only` path;
- считать `MinIO` canonical storage model.

### 9.2 Local filesystem backend
На текущем этапе уже существует baseline:
- общий storage contract;
- `LocalFilesystemStorage`;
- конфиг `APP_STORAGE_ROOT`;
- совместимость attachment download route с `local_fs`.

Но это еще не final state:
- author uploads по умолчанию уже переведены на local backend;
- legal docs уже вынесены в локальный storage flow;
- compose/runtime пока не очищены от MinIO-first assumptions.

### 9.3 DB-only repositories
С этого момента `DB-only` runtime считается transitional.

Допустимо:
- продолжать использовать `SQLAlchemy` path до завершения refactor.

Недопустимо:
- добавлять новую критическую функциональность только через DB path без плана file-mode parity.

## 10. Целевой storage contract

### 10.1 Attachment contract
Attachment model должен уметь хранить:
- logical owner entity
- local relative path
- content type
- size
- original filename
- checksum
- created_at

Bucket/object-key не должны считаться обязательными полями целевого дизайна.

### 10.2 Repository contract
Каждый важный доменный контур должен идти через repository abstraction:
- `db repository`
- `file repository`

Service layer не должен знать, где лежат данные:
- в PostgreSQL;
- в JSON files.

Текущее состояние:
- contract уже начал внедряться;
- author, access, public, auth и admin smoke contour уже имеют repository-based file-mode path;
- file repositories уже реализованы для минимального demo dataset scope:
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
- остальные контуры пока еще требуют миграции.

### 10.3 Runtime selection
Runtime switch уже введен:
- `APP_DATA_MODE=db`
- `APP_DATA_MODE=file`

Storage root уже введен:
- `APP_STORAGE_ROOT=storage`

Что еще нужно:
- довести полный service/repository wiring до parity во всех remaining contours;
- убрать старые deploy assumptions, которые тянут compose к `MinIO` even for file mode.

## 11. Критерии готовности новой схемы

### 11.1 Local storage done
Будет считаться готовым, когда:
- author uploads по умолчанию идут в локальную файловую систему;
- subscriber downloads идут из локальной файловой системы;
- legal docs хранятся локально;
- проект не требует `MinIO` для локального запуска.

### 11.2 File mode done
Test-launch baseline уже достигнут, но full parity будет считаться готовой, когда:
- можно поднять `api + bot + worker` без PostgreSQL;
- есть seed data для admin/author/catalog/product/demo recommendations;
- можно пройти Telegram subscriber flow до feed;
- можно открыть staff web и author workspace локально;
- checkout `stub/manual` и activation можно проверить без ручной правки файлов.

## 12. Быстрый путь к локальному тестированию
Чтобы максимально быстро прийти к живому тесту, migration надо делать в таком порядке:
1. local filesystem storage backend
2. runtime config for `db|file`
3. repository abstraction
4. file repositories для минимального demo scope
5. local seed/bootstrap data
6. run instructions for `api + bot + worker` in file mode
7. only after that deeper UX and analytics tasks

## 13. Что еще нужно реализовать после persistence refactor
- richer Telegram checkout UX
- deeper WebApp auth bridge beyond current verification link flow
- promo/discount lifecycle `[partial]`
- manual discounts and richer Telegram promo UX still remain
- delivery retry/metrics hardening
- moderation analytics/SLA UX `[partial]`
- queue filters, overdue SLA and resolution latency are already in place
- attachment lifecycle UX hardening
- lead source analytics `[partial]`
- normalized checkout attribution and admin source report already exist
- worker retries and observability

## 14. Архитектурное правило на ближайшие шаги
Новые изменения нужно оценивать так:
- ускоряют ли они переход к local storage и file mode;
- сохраняют ли Telegram-first subscriber model;
- не создают ли новый hard dependency на remote storage;
- не делают ли DB обязательной для базового локального тестирования.

## 15. Следующий этап после test-launch
Task list для запуска тестовой версии закрыт. Следующий этап уже не про foundation, а про operational hardening.

Приоритеты:
1. payment completion
  - keep `stub/manual` as operator fallback
  - harden callback rollout on deployed host
   - keep manual operator fallback
2. remaining persistence hardening
   - full file-mode parity for remaining contours
   - backup/restore discipline
3. operational reliability
   - worker retries baseline already added
   - deepen observability and support tooling
4. product analytics and monetization
   - promo/discount lifecycle `[partial]`
   - admin registry, checkout apply path and redemption counters are already in place
   - lead source analytics `[partial]`
   - normalized attribution and admin report are already in place
   - moderation analytics/SLA UX `[partial]`
   - queue filters and SLA latency metrics are already in place
5. Telegram customer experience
   - richer status/checkout self-service
   - broader Mini App surfaces
   - deeper verification and handoff UX

## 16. Canonical clean -> review -> deploy flow
Каждый следующий этап нужно вести по одной схеме:
1. clean runtime state
   - очищать только `storage/runtime/*`
   - не трогать committed `storage/seed/*`
2. run technical review
   - `compileall`
   - `pytest`
3. run product smoke
   - `admin login`
   - `author login`
   - `Telegram checkout -> confirm -> feed`
4. update description files
   - `README.md`
   - `doc/blueprint.md`
   - `doc/task.md`
   - `doc/review.md`
5. only after that move to local/server deploy

Deployment note:
- текущий production-like deploy path должен опираться не на dev `docker-compose`, а на отдельный server compose profile/file;
- server nginx config должен тоже поставляться из репозитория как готовый template;
- deploy bundle должен быть доступен сразу после `git clone`, без ручного сочинения compose/nginx/env templates на сервере;
- один bot token должен обслуживаться только одним polling instance одновременно.
- Telegram `Mini App` / `WebApp` кнопки допустимы только при `https` base URL; на `http`-стенде bot должен работать без них.
