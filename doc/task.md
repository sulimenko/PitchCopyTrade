# PitchCopyTrade Task Pack

Дата: 2026-03-11  
Режим: actual status + refactor roadmap after Telegram-first decision

Статусы:
- `[done]`
- `[partial]`
- `[refactor]`
- `[todo]`

## 1. Уже сделано

### 1. Foundation infrastructure `[done]`
- project skeleton
- Docker baseline
- `api`, `bot`, `worker`
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
- env
- initial migration
- migration smoke path

### 5. FastAPI baseline `[done]`
- health
- ready
- meta
- lifespan

### 6. Bot baseline `[done]`
- aiogram app
- `/start`
- dispatcher

### 7. Worker baseline `[done]`
- worker loop
- placeholder jobs

### 8. MinIO adapter `[done]`
- storage wrapper
- upload/download/delete/stat

### 9. Auth foundation `[done]`
- password hashing
- session token
- role mapping

### 10. Compliance foundation `[done]`
- legal docs model
- consents
- consent-before-payment logic

### 11. Admin baseline `[done]`
- auth UI for staff
- admin dashboard
- strategy CRUD
- subscription product CRUD
- payment review / confirm / activation

### 11.1 Author workspace baseline `[done]`
- author dashboard
- author recommendation CRUD
- author-scoped strategy selection
- create/edit recommendation flow

### 12. Public commerce baseline `[done]`
- public catalog
- strategy detail
- product selection
- checkout stub/manual
- web fallback checkout without subscriber password

### 13. Access delivery baseline `[done]`
- ACL service
- web feed
- bot `/feed`
- bot `/catalog`
- bot `/buy`
- bot `/confirm_buy`
- bot `/web`
- Telegram-auth-only fallback cookie for `/app/*`

## 2. Сделано, но теперь требует refactor

### 14. Subscriber auth model `[partial]`
Что уже сделано:
- password capture removed from web fallback checkout
- Telegram subscriber profile creation on `/start`
- bot-generated Telegram-auth web link
- `/app/*` fallback no longer uses ordinary staff session auth

Что еще нужно:
- заменить link-based fallback на Telegram WebApp / Mini App contour
- удержать единый UX between bot and fallback web

### 15. Subscriber checkout channel `[partial]`
Что уже сделано:
- Telegram checkout baseline via bot commands
- web checkout moved to fallback role

Что еще нужно:
- richer Telegram UX
- explicit status/subscription flows in bot
- consent UX in Telegram

### 16. PostgreSQL runtime assumptions `[refactor]`
Что нужно:
- основной режим: внешний PostgreSQL через `.env`
- optional режим: docker-based PostgreSQL
- ни один из режимов не должен считаться единственно допустимым

Что уже сделано:
- `docker compose` больше не делает postgres hard dependency для app services
- docker postgres вынесен в optional profile `local-db`

## 3. Частично сделано

### 17. Legal admin surface `[partial]`
Сделано:
- models
- logic
- checkout gate

Не сделано:
- legal docs UI
- version publish UI

### 18. Lead source attribution `[partial]`
Сделано:
- field captured
- payload stored

Не сделано:
- normalized persistence
- reporting

### 19. Telegram subscriber path `[partial]`
Сделано:
- `/feed`
- ACL gate

Не сделано:
- onboarding
- account linking
- subscriptions/status commands
- Telegram-first checkout

## 4. Следующие обязательные шаги

### 20. Завершить subscriber contour под Telegram-first `[todo]`
Сделать:
- canonical subscriber identity = `telegram_user_id`
- минимальный профиль по умолчанию
- optional collection of extra fields only by need or consent

Acceptance:
- subscriber не обязан заводить local password account
- password-based subscriber auth больше не считается основным сценарием

### 21. Довести основной checkout в Telegram `[todo]`
Сделать:
- product selection inside Telegram
- consent collection inside Telegram
- payment creation flow inside Telegram
- status feedback in Telegram

Acceptance:
- subscriber может пройти основной путь без перехода в обязательный web checkout

### 22. Довести Telegram-auth web fallback `[todo]`
Сделать:
- Telegram WebApp / Mini App или более нативный equivalent Telegram-auth layer
- улучшить subscriber web fallback UX
- не сломать текущий Telegram-only auth contract

Acceptance:
- subscriber web access, если он остается, не требует отдельного local password login

### 23. Поддержать оба режима PostgreSQL `[todo]`
Сделать:
- основной DSN mode через `.env`
- optional docker DB profile
- docs/run instructions для обоих режимов

Acceptance:
- проект запускается с внешней БД без обязательного локального postgres-контейнера

### 24. Author recommendation workspace `[partial]`
Сделано:
- author shell
- recommendation CRUD
- own-strategy scoping
- base status/kind editing
- structured legs editor
- attachment upload

Не сделано:
- richer workspace UX from prototype
- preview
- validation depth
- attachment delete/replace UX

### 25. Recommendation publish flow `[partial]`
Сделано:
- publish/schedule baseline
- `new/update/close/cancel`
- status timestamps in author editor

Не сделано:
- history/timeline
- worker-based scheduled publish
- moderation-aware transitions

### 26. Moderation queue `[todo]`
Сделать:
- moderator queue
- optional moderation rules
- approve/reject/rework

### 27. Attachments through MinIO `[partial]`
Сделано:
- author upload
- validation
- MinIO persistence baseline

Не сделано:
- subscriber access path
- attach/delete UX

### 28. Instruments and leg UX `[partial]`
Сделано:
- structured leg editor
- validation logic baseline

Не сделано:
- instruments management
- richer multi-leg UX

### 29. Commerce completion `[todo]`
Сделать:
- promo codes
- manual discount UI
- expiry and cancel flows
- real worker jobs

### 30. Account and linkage lifecycle `[todo]`
Сделать:
- Telegram account linking
- subscriber status/profile
- optional extra-contact capture only when needed

### 31. Audit and analytics `[todo]`
Сделать:
- legal and payment admin surface
- lead source analytics
- audit views

## 5. Правила, которые нельзя ломать
- не возвращаться к file-first persistence
- не считать subscriber password-login canonical path
- не собирать лишние пользовательские данные без необходимости
- не выдавать access по `pending` subscription
- не разводить web ACL и bot ACL по разным правилам
- не делать postgres container обязательным для всех режимов запуска

## 6. Definition of done
Проект завершен, когда:
- subscriber контур стал Telegram-first;
- web fallback использует только Telegram auth;
- admin/author контур complete;
- recommendation workspace и publish flow работают;
- legal/payment/subscription/access/delivery связаны end-to-end;
- внешний PostgreSQL через `.env` поддерживается как основной режим.
