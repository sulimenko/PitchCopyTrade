# PitchCopyTrade — Blueprint
> Обновлено: 2026-03-20
> Статус: canonical current contract

## 1. Политика документа

Этот файл не хранит историю фаз.

Он должен описывать только:
- текущий продуктовый контракт;
- согласованный target для следующего крупного блока;
- правила, которые обязательны для всех следующих изменений.

Если решение уже устарело, спорная развилка закрыта или completed phase больше не влияет на следующие шаги, ее нужно удалять из этого файла, а не копить как архив.

## 2. Границы продукта

В продукт входят:
- staff web для `admin`
- staff web для `author`
- staff surface для `moderation`
- subscriber flow через Telegram bot + Mini App
- локальный storage под `APP_STORAGE_ROOT`

Не входят в текущий canonical contract:
- MinIO и любой object storage
- отдельная subscriber web-registration
- password-first staff auth как основной path
- исторические UI patterns, если для них уже выбран новый canonical слой

## 3. Роли и доступ

### 3.1 Роли

- `admin`
- `author`
- `moderation`
- `subscriber`

### 3.2 Staff user

Staff user — это один `User`.

Если у пользователя есть роли `admin + author`, это:
- один аккаунт;
- один staff session;
- одно переключение active mode;
- не два разных логина.

### 3.3 Права

`admin`:
- создает staff users;
- создает автора;
- создает стратегию за любого автора;
- управляет платежами, подписками, документами, delivery, moderation и staff settings.

`author`:
- работает только со своими стратегиями;
- создает и редактирует только свои рекомендации;
- не управляет своими author-permissions.

`admin` в admin-mode:
- не создает рекомендации.

Если `admin` хочет работать как автор:
- он переключается в `author` mode;
- видит только свои author entities.

## 4. Staff auth и onboarding

### 4.1 Current contract

- основной вход staff — через Telegram Login Widget;
- password login остается только как demo/local fallback;
- новый staff user создается как `invited`;
- доступ в staff UI появляется только после подтвержденного bind через Telegram.

### 4.2 Canonical onboarding

Основной путь:
1. admin вводит `display_name + email + roles`;
2. система создает `invited` staff user;
3. система отправляет email invite;
4. сотрудник открывает invite;
5. сотрудник завершает bind через Telegram;
6. user получает `active`.

### 4.3 Статусы staff user

Для продукта и UI canonical vocabulary:
- `invited`
- `active`
- `inactive`

`inactive` нужен вместо отдельного `blocked` языка в product layer, чтобы не расходиться с будущим SuiteCRM contour.

### 4.4 Приглашения

Invite contract:
- invite links абсолютные, от `BASE_URL`;
- resend инвалидирует старые invite links;
- это должно быть реализовано не только на уровне UI, а на уровне token/bind contract;
- failed invite delivery не отменяет создание staff user;
- failed delivery создает log entry;
- failed delivery отправляет email всем активным администраторам для контроля;
- создание нового `admin` и нового `author` также отправляет контрольное письмо всем администраторам.
- поведение по control emails должно совпадать в `db` и `file` mode.

### 4.5 `telegram_user_id`

`telegram_user_id`:
- не primary UX field;
- может существовать как advanced field;
- после bind может редактироваться администратором;
- при ручной смене сохраняется сразу, без forced re-invite.

### 4.6 Hardening rules

Bind по invite обязан:
- до commit проверять, не привязан ли этот `telegram_user_id` к другому staff user;
- завершаться контролируемой бизнес-ошибкой, а не DB `500`;
- одинаково корректно работать в `db` и `file` mode.

Invite token обязан:
- иметь механизм отзыва старых токенов после resend;
- не оставаться валидным просто до `exp`, если уже был выпущен новый invite.

## 5. Staff UI shell

Canonical staff shell:
- узкая левая вертикальная навигация;
- верхняя строка:
  - `Назад`
  - breadcrumb
  - быстрые действия
  - переключение роли
- основной рабочий контент почти всегда grid;
- row edit открывается в right drawer;
- сложные формы остаются modal или fullscreen modal.

Навигация:
- `back` = browser history fallback -> parent route.

Приоритет:
- desktop-first;
- mobile fallback допустим, но не primary target для `admin` и `moderation`.

## 6. Grid layer

### 6.1 Canonical choice

Для `admin`, `author` и `moderation` canonical table layer = `AG Grid Community`.

Primary staff registries не должны оставаться на handcrafted HTML tables как final contract.

### 6.2 Scope

На `AG Grid` переводятся все staff list/registry/queue screens:
- `/admin/staff`
- `/admin/authors`
- `/admin/strategies`
- `/admin/products`
- `/admin/promos`
- `/admin/payments`
- `/admin/subscriptions`
- `/admin/legal`
- `/admin/delivery`
- `/admin/analytics/*` там, где есть табличный слой
- `/author/strategies`
- `/author/recommendations`
- watchlist в `/author/dashboard`
- `/moderation/queue`

### 6.3 Design contract

Staff grid не должен выглядеть как public UI.

Требования:
- компактная тема;
- маленькие кнопки;
- маленькие row/header heights;
- слабые границы;
- минимум теней;
- минимум декоративных поверхностей;
- максимум плотности и читаемости.

Это professional operator UI, а не маркетинговая поверхность.

### 6.4 Interaction contract

Grid должен поддерживать:
- sorting;
- filtering;
- quick filter;
- keyboard navigation;
- pinned action column;
- row menu;
- inline edit для простых полей;
- right drawer для сложных полей и multi-step actions.

Для `admin/staff` и `admin/authors` canonical CRUD contract дополнительно требует:
- редактирование existing rows, а не только create/action forms;
- правку `display_name`, `email`, `telegram_user_id`, ролей и статусных actions;
- отсутствие второго параллельного handcrafted registry как fallback.
- status column не может быть только информативной; для `staff user` нужен рабочий action flow `active/inactive`.
- row edit не может обходить governance-ограничения отдельных actions; любые изменения ролей и статуса обязаны уважать правило последнего активного администратора.

## 7. Unified CRUD pattern

### 7.1 Simple entities

Для простых сущностей primary pattern:
- grid row
- inline edit простых полей
- drawer для расширенного редактирования

Сюда относятся:
- staff users
- authors
- strategies
- products
- promos

### 7.2 Operational entities

Для operational entities primary pattern:
- grid row
- read-only detail drawer
- только разрешенные row actions

Сюда относятся:
- payments
- subscriptions
- delivery
- moderation items

### 7.3 Complex content entities

Для сложных контентных сущностей:
- grid как primary list layer;
- full edit через modal / fullscreen modal.

Сюда относятся:
- recommendations
- legal document versions
- one pager / long-form content

## 8. Mutability rules

### 8.1 Staff user

До bind:
- можно менять `display_name`
- `email`
- роли
- `telegram_user_id`

После bind:
- можно менять `display_name`
- `email`
- роли
- `telegram_user_id`
- нельзя редактировать статус свободным inline-изменением; статус меняется только через явные actions.

Governance rule:
- нельзя снять роль `admin` у последнего активного администратора ни через отдельный row action, ни через drawer edit, ни через bulk update path.

### 8.1.2 Staff status actions

Для `staff user` должен существовать явный operator flow:
- `Активировать`
- `Деактивировать`

`inactive` не может оставаться только badge в grid без action path.

### 8.1.1 Staff status vocabulary

Product/UI vocabulary:
- `invited`
- `active`
- `inactive`

`blocked` не должен оставаться в canonical staff contract.

### 8.2 Author

Editable:
- `display_name`
- `email`
- roles
- `telegram_user_id`
- `requires_moderation`
- `active/inactive`

### 8.3 Strategy

Editable:
- только `draft`

Read-only:
- `published`
- `archived`

### 8.4 Recommendation

Editable:
- `draft`
- `review`

Read-only:
- `approved`
- `scheduled`
- `published`
- `closed`
- `cancelled`
- `archived`

### 8.5 Payment

Editable/actionable:
- `created`
- `pending`

Read-only:
- `paid`
- `failed`
- `expired`
- `cancelled`
- `refunded`

### 8.6 Subscription

Grid shows all rows.

Editable free-form fields — нет.

Допустимы только actions:
- `Открыть`
- `Отключить автопродление`
- `Отменить`

Read-only:
- terminal states и все завершенные исторические записи.

### 8.7 Legal

Editable:
- draft version

Read-only:
- active version

Изменение active doc идет только через новую версию и `activate`.

### 8.8 Moderation

`/moderation/queue` идет в тот же grid language.

Pattern:
- queue в `AG Grid`
- detail в right drawer
- approve/rework/reject как row actions

## 9. Runtime consistency

Обязательные правила текущего блока:
- `db` и `file` mode должны одинаково поддерживать agreed onboarding/governance contract;
- control emails администраторам не должны зависеть от выбранного storage mode;
- review всегда проверяет не только UI, но и parity между `db` и `file` path.
- row actions:
  - `approve`
  - `rework`
  - `reject`
- published/archived entries read-only

## 9. Recommendations editor

Grid layer и editor coexist.

Canonical contract:
- список рекомендаций живет в grid;
- create/edit сложной рекомендации открывается в modal/fullscreen modal;
- быстрый inline add остается в рекомендациях как operator shortcut;
- первая бумага обязательна;
- дополнительные бумаги добавляются динамически.

## 10. Watchlist

Watchlist автора:
- живет в grid language;
- поддерживает search/filter/sort;
- поддерживает добавление;
- поддерживает удаление;
- не редактирует сам инструмент как справочник.

## 11. Русский язык интерфейса

Весь staff и subscriber UI должен использовать русский язык:
- статусы;
- labels;
- action names;
- breadcrumbs;
- drawer titles;
- modal titles;
- empty states;
- errors;
- help-copy.

Английские enum/value имена допустимы только в коде и БД.

## 12. Local-only storage

Canonical storage contract:
- только локальная файловая система;
- attachments и legal files только локально;
- никаких `MINIO_*`;
- никаких fallback branches под object storage.

## 13. Правило на будущее

Если новый canonical contour уже согласован:
- код меняется крупными блоками;
- без поддержки старых UI patterns;
- без сохранения устаревших вариантов “на всякий случай”;
- docs должны отражать только текущее canonical решение и активный backlog.
