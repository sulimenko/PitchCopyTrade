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
- `storage/blob/`
- `storage/json/`
- `storage/parquet/`
- `storage/runtime/`

## Что показывает исследование
Текущий код пока еще не соответствует новой целевой схеме полностью.

Жесткие зависимости, которые сейчас есть:
- config валидирует только `PostgreSQL` DSN;
- DB session создается сразу через `SQLAlchemy async engine`;
- attachment storage реализован через `MinIO`;
- `docker-compose.yml` все еще поднимает `minio` как штатный сервис;
- attachment flow и metadata пока ориентированы на bucket/object-key path.

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

## Ближайшая цель
Быстрый путь к тестированию сейчас такой:
1. внедрить local filesystem storage backend;
2. ввести `db|file` runtime mode;
3. сделать file repositories для минимального demo-контура;
4. добавить local seed data;
5. поднять `api + bot + worker` локально с test bot.

## Документы
- [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- [review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)
