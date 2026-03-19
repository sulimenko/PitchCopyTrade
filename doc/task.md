# PitchCopyTrade — Active Tasks
> Обновлено: 2026-03-20
> Этот файл хранит только текущий backlog. Завершенные исторические фазы сюда не возвращаются.

## Статусы

- `[ ]` — не начато
- `[~]` — в работе
- `[x]` — завершено
- `[!]` — заблокировано

## Текущий program block

Следующий крупный блок состоит из трех частей:
1. compact staff shell
2. `AG Grid Community` как единый CRUD layer
3. быстрый onboarding staff через email invite + Telegram bind

---

## Блок A — Compact staff shell

**Цель:** убрать public-like visual language из staff кабинетов и сделать operator-first shell.

- [ ] **A1** Сделать отдельный staff base layout
  - не использовать текущий общий `base.html` как final visual language для staff
  - выделить compact shell для `admin`, `author`, `moderation`
  - public/subscriber design не должен протекать в staff UI

- [ ] **A2** Внедрить left rail
  - узкая вертикальная навигация
  - группы разделов:
    - dashboard
    - staff
    - authors
    - strategies
    - recommendations
    - products
    - payments
    - subscriptions
    - legal
    - delivery
    - promos
    - analytics
    - moderation

- [ ] **A3** Внедрить верхнюю navigation line
  - `Назад`
  - breadcrumb
  - быстрые действия текущего экрана
  - переключение роли

- [ ] **A4** Правило `Назад`
  - browser history fallback
  - если history невалидна, fallback на parent route

- [ ] **A5** Уменьшить визуальный шум
  - убрать большие hero blocks как primary pattern
  - убрать крупные action buttons как основную навигацию
  - сделать staff controls компактными

### Acceptance

- staff UI визуально отделен от public/subscriber UI
- основные переходы видны в left rail и breadcrumb
- на staff экранах есть понятный `back` contract
- admin/author/mode switch не теряются в большом topbar noise

---

## Блок B — AG Grid Community

**Цель:** все staff list/registry/queue surfaces переводятся на единый `AG Grid Community`.

- [ ] **B1** Подключить `AG Grid Community` локально
  - без CDN как canonical path
  - shared JS/CSS слой внутри проекта
  - один reusable bootstrap для Jinja templates

- [ ] **B2** Сделать compact staff grid theme
  - row height `28-32px`
  - header height `30-34px`
  - слабые borders
  - минимальные paddings
  - мелкие controls
  - нейтральный фон
  - минимум карточности

- [ ] **B3** Перевести admin surfaces
  - `/admin/staff`
  - `/admin/authors`
  - `/admin/strategies`
  - `/admin/products`
  - `/admin/promos`
  - `/admin/payments`
  - `/admin/subscriptions`
  - `/admin/legal`
  - `/admin/delivery`
  - табличные части `/admin/analytics/*`

- [ ] **B4** Перевести author surfaces
  - `/author/strategies`
  - `/author/recommendations`
  - watchlist в `/author/dashboard`

- [ ] **B5** Перевести moderation surface
  - `/moderation/queue`
  - detail как right drawer
  - approve/rework/reject как row actions

- [ ] **B6** Сделать один CRUD language
  - grid row
  - inline edit простых полей
  - right drawer для расширенного редактирования
  - row menu для actions
  - modal/fullscreen modal для сложных форм

- [ ] **B7** Сохранить recommendation editor contract
  - grid остается primary list layer
  - full recommendation edit остается modal/fullscreen modal
  - быстрый inline add остается operator shortcut

### Acceptance

- `workspace-table` перестает быть primary pattern
- все list/registry/queue screens работают через `AG Grid Community`
- admin, author и moderation используют один visual/interaction language
- grid выглядит как professional operator tool, а не как public marketing UI

---

## Блок C — Unified mutability rules

**Цель:** все grids и drawers obey explicit editability rules по статусам.

- [ ] **C1** Staff users
  - до bind editable: `display_name`, `email`, `roles`, `telegram_user_id`
  - после bind editable: `display_name`, `email`, `roles`, `telegram_user_id`
  - статус меняется только через явные actions
  - vocabulary: `invited`, `active`, `inactive`

- [ ] **C2** Authors
  - editable:
    - `display_name`
    - `email`
    - `roles`
    - `telegram_user_id`
    - `requires_moderation`
    - `active/inactive`

- [ ] **C3** Strategies
  - editable только `draft`
  - `published`, `archived` read-only

- [ ] **C4** Recommendations
  - editable только `draft`, `review`
  - `approved`, `scheduled`, `published`, `closed`, `cancelled`, `archived` read-only

- [ ] **C5** Payments
  - editable/actionable только `created`, `pending`
  - `paid`, `failed`, `expired`, `cancelled`, `refunded` read-only
  - row actions minimum:
    - `Открыть`
    - `Подтвердить`
    - `Применить скидку`

- [ ] **C6** Subscriptions
  - free-form row edit не допускается
  - row actions minimum:
    - `Открыть`
    - `Отключить автопродление`
    - `Отменить`
  - terminal states read-only

- [ ] **C7** Legal
  - draft editable
  - active version read-only
  - смена active документа только через новую версию и `activate`

- [ ] **C8** Watchlist
  - добавить сортировку/фильтрацию
  - добавить удаление
  - не редактировать instrument master-data из watchlist

### Acceptance

- пользователь не может редактировать terminal rows
- доступные actions совпадают со статусом сущности
- drawer и row menu не показывают недопустимые операции

---

## Блок D — Staff onboarding

**Цель:** убрать ручную пересылку invite URL и сделать onboarding новым `admin/author` быстрым и естественным.

- [ ] **D1** Упростить create flow
  - primary fields:
    - `display_name`
    - `email`
    - `roles`
  - `telegram_user_id` увести в advanced field

- [ ] **D2** Автоматически отправлять invite email
  - новый `admin`
  - новый `author`
  - письмо с CTA:
    - `Открыть приглашение`
    - `Войти через Telegram`

- [ ] **D3** Делать admin oversight mail
  - при каждом создании `admin`
  - при каждом создании `author`
  - при failure отправки invite
  - отправлять уведомление всем активным администраторам

- [ ] **D4** Хранить invite delivery state
  - `sent`
  - `failed`
  - `resent`
  - `last_sent_at`
  - `last_error`
  - log entry для каждой отправки

- [ ] **D5** Добавить registry actions
  - `Отправить повторно`
  - `Скопировать ссылку`
  - `Открыть Telegram invite`

- [ ] **D6** Инвалидировать старые invite links при resend
  - старый invite token больше не работает
  - новый становится canonical

- [ ] **D7** Упростить invite state на `/login`
  - отдельное состояние staff invite
  - минимум текста
  - одна primary CTA
  - без необходимости понимать `invite_token`

### Acceptance

- администратор не пересылает invite вручную как основной сценарий
- новый `admin/author` получает письмо автоматически
- resend работает из registry
- failed delivery видна в UI и в log
- старые invite links невалидны после resend

---

## Блок E — Русский язык интерфейса

**Цель:** весь видимый UI перевести на русский и убрать английские статусы/подписи из staff и subscriber layers.

- [ ] **E1** Локализовать staff shell
- [ ] **E2** Локализовать grid headers
- [ ] **E3** Локализовать row actions и drawer labels
- [ ] **E4** Локализовать статусы и badge text
- [ ] **E5** Локализовать moderation, payments, subscriptions, legal и analytics surfaces

### Acceptance

- пользователь не видит англоязычных labels и статусов в интерфейсе
- английский остается только в коде/enum values

---

## Worker handoff

### Основные файлы-кандидаты

- `src/pitchcopytrade/web/templates/base.html`
- `src/pitchcopytrade/web/templates/partials/staff_mode_switch.html`
- `src/pitchcopytrade/web/templates/admin/*`
- `src/pitchcopytrade/web/templates/author/*`
- `src/pitchcopytrade/web/templates/moderation/*`
- `src/pitchcopytrade/api/routes/admin.py`
- `src/pitchcopytrade/api/routes/author.py`
- `src/pitchcopytrade/api/routes/moderation.py`
- `src/pitchcopytrade/services/admin.py`
- `src/pitchcopytrade/services/author.py`
- `src/pitchcopytrade/auth/*`
- новый shared слой для `AG Grid Community`

### Не делать

- не сохранять старые handcrafted tables как параллельный UI
- не поддерживать старый большой public-like shell для staff
- не оставлять onboarding через ручную пересылку URL как canonical path
- не добавлять второй CRUD language рядом с grid

### Порядок

1. staff shell
2. `AG Grid Community`
3. mutability gates
4. onboarding + invite delivery
5. localization pass
6. docs sync
