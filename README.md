# PitchCopyTrade

Telegram-first платформа для продажи подписок на стратегии и доставки инвестиционных рекомендаций.

## Стек
- FastAPI
- aiogram 3
- PostgreSQL
- SQLAlchemy 2
- Alembic
- MinIO
- Jinja2
- HTMX
- Docker Compose

## Runtime modes
- Основной режим: внешний PostgreSQL через `.env`
- Допустимый dev/demo режим: `docker compose --profile local-db up`
- MinIO остается объектным хранилищем вложений

## Telegram bots
- Активный test bot:
  - username: `Avt09_Bot`
  - token хранится в [`.env`](/Users/alexey/site/PitchCopyTrade/.env)
- Main bot уже добавлен в [`.env`](/Users/alexey/site/PitchCopyTrade/.env), но закомментирован до переключения

## Что уже работает
- foundation infrastructure, config, ORM, Alembic, MinIO
- staff auth для `admin / author / moderator`
- admin dashboard
- strategy CRUD
- subscription product CRUD
- author workspace
- author recommendation CRUD
- public catalog
- checkout `stub/manual`
- payment review -> confirm -> subscription activation
- ACL delivery
- Telegram-first subscriber baseline:
  - `/start`
  - `/catalog`
  - `/buy <product_slug>`
  - `/confirm_buy <product_slug>`
  - `/feed`
  - `/web`
- Telegram-auth-only web fallback для subscriber feed

## User cases

### Admin
Что делает:
- входит в staff web через `login/password`
- управляет стратегиями
- заводит subscription products типа `strategy / author / bundle`
- просматривает платежи
- подтверждает manual payment
- активирует подписки без работы напрямую в БД

Что получает:
- единый операционный контур
- контроль над каталогом и коммерцией
- прозрачный payment/subscription lifecycle

### Автор стратегии
Что делает сейчас:
- входит в staff web через `login/password`
- попадает в `/author/dashboard`
- видит свои стратегии и последние публикации
- создает и редактирует рекомендации только по своим стратегиям
- управляет типом публикации и статусом идеи

Что получит после следующих шагов:
- draft / preview / publish flow depth
- structured multi-leg editor
- загрузку вложений через MinIO
- moderation flow по правилам автора

Польза:
- уже есть рабочий контур создания публикаций
- дальше добавится полный publish pipeline и delivery richness

### Обычный user / subscriber
Что делает сейчас:
- приходит из рекламы или рекомендации
- может открыть публичный каталог на сайте
- основной путь проходит через Telegram bot
- может выбрать продукт в Telegram
- может создать manual checkout request
- после активации получает доступ к рекомендациям в Telegram
- при необходимости открывает web fallback только через Telegram-issued link

Что получает:
- максимально простой вход без отдельного пароля
- минимум обязательных данных
- один основной канал взаимодействия: Telegram
- единые права доступа в bot и web fallback

### Moderator
Что делает сейчас:
- входит в staff web через `login/password`
- имеет staff workspace placeholder

Что получит после следующих шагов:
- moderation queue
- approve / reject / rework flow
- контроль качества публикаций по авторам

## Что осталось сделать
- author workspace
- recommendation CRUD
- moderation queue
- Telegram-first consent UX
- richer bot UX с кнопками и Mini App / WebApp
- attachments end-to-end через MinIO
- promo/discount and lifecycle UI
- legal docs admin UI
- lead source normalization and analytics
- real worker jobs

## Документы
- [blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)
- [review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md)
