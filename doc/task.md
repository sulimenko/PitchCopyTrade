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
4. закрытие staff CRUD gaps и parity между `db`/`file`

---

## Блок A — Compact staff shell

**Цель:** убрать public-like visual language из staff кабинетов и сделать operator-first shell.

- [x] **A1** Сделать отдельный staff base layout
  - не использовать текущий общий `base.html` как final visual language для staff
  - выделить compact shell для `admin`, `author`, `moderation`
  - public/subscriber design не должен протекать в staff UI

- [x] **A2** Внедрить left rail
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

- [x] **A3** Внедрить верхнюю navigation line
  - `Назад`
  - breadcrumb
  - быстрые действия текущего экрана
  - переключение роли

- [x] **A4** Правило `Назад`
  - browser history fallback
  - если history невалидна, fallback на parent route

- [x] **A5** Уменьшить визуальный шум
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

- [x] **B1** Подключить `AG Grid Community` локально
  - без CDN как canonical path
  - shared JS/CSS слой внутри проекта
  - один reusable bootstrap для Jinja templates
  - удалить handcrafted HTML tables как primary registry layer на staff screens

- [x] **B2** Сделать compact staff grid theme
  - row height `28-32px`
  - header height `30-34px`
  - слабые borders
  - минимальные paddings
  - мелкие controls
  - нейтральный фон
  - минимум карточности

- [x] **B3** Перевести admin surfaces
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

- [x] **B4** Перевести author surfaces
  - `/author/strategies`
  - `/author/recommendations`
  - watchlist в `/author/dashboard`

- [x] **B5** Перевести moderation surface
  - `/moderation/queue`
  - detail как right drawer
  - approve/rework/reject как row actions

- [x] **B6** Сделать один CRUD language
  - grid row
  - inline edit простых полей
  - right drawer для расширенного редактирования
  - row menu для actions
  - modal/fullscreen modal для сложных форм
  - для `admin/staff` и `admin/authors` обязательно покрыть existing row edit, а не только create/actions

- [x] **B8** Закрыть existing row edit для `admin/staff`
  - `display_name`
  - `email`
  - `telegram_user_id`
  - роли
  - invite actions
  - edit path должен быть доступен из grid, а не через скрытый side flow

- [x] **B9** Закрыть existing row edit для `admin/authors`
  - `display_name`
  - `email`
  - `telegram_user_id`
  - `requires_moderation`
  - `active/inactive`

- [x] **B7** Сохранить recommendation editor contract
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

- [x] **C1** Staff users
  - до bind editable: `display_name`, `email`, `roles`, `telegram_user_id`
  - после bind editable: `display_name`, `email`, `roles`, `telegram_user_id`
  - статус меняется только через явные actions
  - vocabulary: `invited`, `active`, `inactive`

- [x] **C1.1** Реализовать явный action flow `active/inactive`
  - status column не должна быть только информативной
  - должны существовать действия `Активировать` и `Деактивировать`
  - row menu / drawer не должны показывать невозможные переходы

- [x] **C2** Authors
  - editable:
    - `display_name`
    - `email`
    - `roles`
    - `telegram_user_id`
    - `requires_moderation`
    - `active/inactive`

- [x] **C3** Strategies
  - editable только `draft`
  - `published`, `archived` read-only

- [x] **C4** Recommendations
  - editable только `draft`, `review`
  - `approved`, `scheduled`, `published`, `closed`, `cancelled`, `archived` read-only

- [x] **C5** Payments
  - editable/actionable только `created`, `pending`
  - `paid`, `failed`, `expired`, `cancelled`, `refunded` read-only
  - row actions minimum:
    - `Открыть`
    - `Подтвердить`
    - `Применить скидку`

- [x] **C6** Subscriptions
  - free-form row edit не допускается
  - row actions minimum:
    - `Открыть`
    - `Отключить автопродление`
    - `Отменить`
  - terminal states read-only

- [x] **C7** Legal
  - draft editable
  - active version read-only
  - смена active документа только через новую версию и `activate`

- [x] **C8** Watchlist
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

- [x] **D1** Упростить create flow
  - primary fields:
    - `display_name`
    - `email`
    - `roles`
  - `telegram_user_id` увести в advanced field

- [x] **D2** Автоматически отправлять invite email
  - новый `admin`
  - новый `author`
  - письмо с CTA:
    - `Открыть приглашение`
    - `Войти через Telegram`

- [x] **D3** Делать admin oversight mail
  - при каждом создании `admin`
  - при каждом создании `author`
  - при failure отправки invite
  - отправлять уведомление всем активным администраторам
  - одинаково в `db` и `file` mode

- [x] **D4** Хранить invite delivery state
  - `sent`
  - `failed`
  - `resent`
  - `last_sent_at`
  - `last_error`
  - log entry для каждой отправки

- [x] **D5** Добавить registry actions
  - `Отправить повторно`
  - `Скопировать ссылку`
  - `Открыть Telegram invite`

- [x] **D6** Инвалидировать старые invite links при resend
  - старый invite token больше не работает
  - новый становится canonical
  - token contract должен иметь механизм revoke/version, а не только новый `iat`

- [x] **D7** Упростить invite state на `/login`
  - отдельное состояние staff invite
  - минимум текста
  - одна primary CTA
  - без необходимости понимать `invite_token`

- [x] **D8** Защитить bind от collision по `telegram_user_id`
  - до commit проверять, не привязан ли Telegram account к другому staff user
  - в `db` mode не допускать DB `500`
  - в `file` mode не допускать двойного владения одним Telegram ID
  - отдавать явную бизнес-ошибку в UI

### Acceptance

- администратор не пересылает invite вручную как основной сценарий
- новый `admin/author` получает письмо автоматически
- resend работает из registry
- failed delivery видна в UI и в log
- старые invite links невалидны после resend

---

## Блок E — Русский язык интерфейса

**Цель:** весь видимый UI перевести на русский и убрать английские статусы/подписи из staff и subscriber layers.

- [x] **E1** Локализовать staff shell
- [x] **E2** Локализовать grid headers
- [x] **E3** Локализовать row actions и drawer labels
- [x] **E4** Локализовать статусы и badge text
- [x] **E5** Локализовать moderation, payments, subscriptions, legal и analytics surfaces

### Acceptance

- пользователь не видит англоязычных labels и статусов в интерфейсе
- английский остается только в коде/enum values

---

## Блок F — Runtime parity и governance polish

**Цель:** `db` и `file` mode должны одинаково соблюдать текущий onboarding/governance contract.

- [ ] **F0** Закрыть `P1` по последнему активному администратору
  - `update_admin_staff_user` не должен позволять убрать роль `admin` у последнего активного администратора
  - защита должна совпадать с отдельным `roles/admin/remove`
  - одинаково в `db` и `file` mode
  - UI должен возвращать бизнес-ошибку, а не частично применять update

- [ ] **F1** Выровнять control emails по mode
  - `db` и `file` path должны одинаково отправлять уведомления активным администраторам
  - failed delivery не должен молча выпадать в одном из режимов

- [ ] **F2** Проверить `db/file` parity на staff onboarding
  - create
  - resend
  - oversight mail
  - audit log

- [ ] **F3** Добавить regression coverage
  - existing row edit
  - status actions `active/inactive`
  - oversight emails в `file` mode
  - запрет снятия `admin` у последнего активного администратора через `/admin/staff/{id}/edit`

### Acceptance

- `db` и `file` mode ведут себя одинаково для staff onboarding/control path
- existing staff rows реально редактируются из реестра
- `active/inactive` работает как action flow, а не только как badge
- drawer edit не может обойти governance path последнего активного администратора

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
5. runtime parity и governance polish
6. localization pass
7. docs sync

### First step для worker

1. Сначала исправить `update_admin_staff_user` в `src/pitchcopytrade/services/admin.py`, чтобы role edit использовал тот же governance contract, что и revoke-flow.
2. Затем добавить route-level regression test на попытку снять `admin` через `/admin/staff/{id}/edit`.
3. После этого прогнать целевой набор:
   - `tests/test_admin_ui.py`
   - `tests/test_auth.py`
   - `tests/test_db_models.py`
   - `tests/test_file_repositories.py`

---

## Блок G — Author editor compact redesign

**Цель:** убрать oversized editor screens и привести strategy/recommendation forms к compact operator-first layout.

- [x] **G1** Ужать header recommendation editor
  - убрать giant hero-block
  - оставить короткий title + one-line helper
  - actions держать в одной компактной строке

- [x] **G2** Ужать strategy editor до того же visual language
  - те же вертикальные ритмы
  - те же размеры инпутов
  - те же border/padding tokens

- [x] **G3** Перевести формы на compact field tokens
  - input/select height `32-36px`
  - явная рамка `1px`
  - меньшие gap между полями
  - textarea с небольшой стартовой высотой

- [x] **G4** Разбить recommendation editor на компактные секции
  - `Основное`
  - `Бумаги`
  - `Вложения`
  - `Действия`
  - без огромных пустых зон и декоративных блоков

- [x] **G5** Упростить copy в editor
  - убрать длинные объяснения, которые не несут операционной ценности
  - оставить короткие contextual hints

### Acceptance

- recommendation и strategy editor визуально соответствуют compact staff shell
- верхний экран не тратит высоту на giant titles и лишний copy
- оператор видит структуру формы с первого экрана

---

## Блок H — Recommendation data flow и validation

**Цель:** inline add, full editor и validation должны работать как один консистентный contour.

- [x] **H1** Сделать один data contract для inline add и detail editor
  - inline add сохраняет нормализованный `instrument_id`, а не только текст тикера
  - detail editor открывается с уже выбранной бумагой
  - при переходе не теряется `ticker`

- [x] **H2** Убрать свободный text-only ticker flow
  - paper selection только через controlled picker / autocomplete
  - выбор бумаги должен создавать валидную связку `instrument_id + ticker label`

- [x] **H3** Починить `+` flow
  - при нажатии `+` открывается detail уже для валидного draft
  - если бумага не выбрана валидно, UI не должен создавать видимость заполненной рекомендации

- [x] **H4** Сделать field-level validation для первой бумаги
  - общий alert можно оставить
  - но поле `Инструмент` должно подсвечиваться локально
  - текст ошибки для оператора:
    - `Выберите инструмент из списка`
    - а не только общий `Leg 1...`

- [x] **H5** Уточнить semantics первой бумаги
  - первая бумага обязательна
  - без валидного инструмента и направления рекомендация не может считаться собранной

- [x] **H6** Добавить regression coverage
  - inline add -> detail editor сохраняет бумагу
  - `instrument_id` не теряется
  - `Leg 1` ошибка возникает только при реально невалидной первой бумаге

### Acceptance

- inline add и full editor используют один и тот же объект бумаги
- выбранный в grid ticker подтягивается в detail editor
- ошибка `Leg 1` больше не возникает при валидном выборе бумаги
- ошибки показываются рядом с проблемным полем, а не только глобально

### Worker pack — Author editor

#### UI/UX fixes

- [x] Ужать header recommendation editor
- [x] Ужать strategy editor до того же visual language
- [x] Перевести формы на compact field tokens
- [x] Разбить recommendation editor на компактные секции
- [x] Упростить copy в editor

#### Data flow fixes

- [x] Сделать один data contract для inline add и detail editor
- [x] Убрать свободный text-only ticker flow
- [x] Починить `+` flow

#### Validation fixes

- [x] Сделать field-level validation для первой бумаги
- [x] Уточнить semantics первой бумаги
- [x] Добавить regression coverage

#### Acceptance criteria

- [x] inline add и full editor используют один и тот же объект бумаги
- [x] выбранный в grid ticker подтягивается в detail editor
- [x] ошибка `Leg 1` больше не возникает при валидном выборе бумаги
- [x] ошибки показываются рядом с проблемным полем, а не только глобально

---

## Блок I — Governance parity для `admin/authors`

**Цель:** edit flow автора не должен обходить ту же governance-защиту, что уже действует в `admin/staff`.

- [x] **I1** Распространить защиту последнего активного администратора на `update_admin_author`
  - drawer edit в `/admin/authors`
  - `file` mode
  - `db` mode
  - замена ролей через author edit не может снимать `admin` у последнего активного администратора

- [x] **I2** Унифицировать ошибки и UX
  - если admin снимается у самого себя через author edit, сообщение должно совпадать с staff edit
  - если admin снимается у другого последнего активного администратора, сообщение тоже должно совпадать с governance contract

- [x] **I3** Добавить regression coverage
  - service-level test для `update_admin_author`
  - route/UI test для `/admin/authors/{id}/edit`
  - behavior должен быть одинаковым в `db` и `file` mode

### Acceptance

- через `/admin/authors/{id}/edit` нельзя снять `admin` у последнего активного администратора
- behavior совпадает с `/admin/staff/{id}/edit`
- regression tests покрывают сценарий и не допускают повторного drift

---

## Блок J — Telegram bot transport resilience

**Цель:** bot не должен требовать ручного redeploy после временной сетевой/TLS ошибки при доступе к `api.telegram.org`.

- [x] **J1** Сделать resilient startup/polling loop
  - `TelegramNetworkError`, DNS, timeout и TLS handshake failures не должны завершать процесс навсегда
  - polling должен перезапускаться с backoff
  - лог должен явно показывать, что это transport/network failure, а не ошибка токена или бизнес-логики

- [x] **J2** Развести retry и fatal errors
  - временные network/TLS ошибки считаются retryable
  - truly fatal config errors остаются явными
  - при retry не должно быть бесконечного noisy traceback без контекста

- [x] **J3** Добавить deploy runbook для Telegram connectivity
  - проверить DNS из контейнера
  - проверить исходящий `443` до `api.telegram.org`
  - проверить системное время
  - проверить CA/cert trust внутри образа
  - проверить, что проблема воспроизводится именно из контейнера

- [x] **J4** Добавить post-deploy smoke-check
  - bot после старта должен дойти до `getMe/polling` без ручного перезапуска
  - при временном сетевом сбое восстановление должно происходить автоматически

### Acceptance

- единичный сбой сети до `api.telegram.org:443` не убивает bot-contour
- bot восстанавливает polling без ручного `docker compose up -d`
- deploy docs содержат явный troubleshooting path для Telegram connectivity

---

## Блок K — Staff invite fallback и unclipped action menus

**Цель:** onboarding staff не должен зависеть от единственного Telegram widget path, а operator menus не должны ломаться из-за scroll/container clipping.

- [x] **K1** Добавить fallback path на staff invite page
  - invite screen не должен держаться только на Telegram Login Widget
  - если widget не инициализировался, UI обязан показать рабочий следующий шаг
  - preferred fallback: deep-link в Telegram bot с invite context

- [x] **K2** Добавить явный fallback UX на `/login?invite_token=...`
  - детектировать, что widget не появился/не загрузился
  - показать понятное сообщение без технического шума
  - дать действия:
    - `Открыть Telegram`
    - `Скопировать приглашение`
    - `Запросить новое приглашение`

- [x] **K3** Убрать raw invite URL из primary grid cell в `/admin/staff`
  - длинный tokenized link не должен раздувать строку
  - в таблице оставить compact presentation:
    - badge статуса
    - дата/время отправки
    - короткие operator actions
  - invite link оставить только в row menu / drawer / copy action

- [x] **K4** Убрать clipping row menu в staff registries
  - `Действия` не должны резаться `.staff-grid-shell`
  - row menu перевести в viewport-level popover / dialog / portal
  - минимально допустимо: отдельный unclipped popup layer, а не absolute panel внутри scroll container

- [x] **K5** Добавить regression/manual acceptance coverage
  - mobile Safari / narrow viewport smoke-check для invite page
  - row menu открывается целиком в конце строки и у нижнего края таблицы
  - staff row не раздувается из-за invite link

### Acceptance

- пользователь по invite не застревает на сером placeholder без следующего шага
- `/admin/staff` остается компактным даже для длинных invite tokens
- action menus не клипуются grid-shell контейнером

---

## Блок L — Остаточная русификация author editor

**Цель:** после compact redesign и data-flow фиксов в author editor не должны оставаться видимые raw enum values и англоязычные статусы.

- [x] **L1** Локализовать readonly/status copy в author editor templates
  - `author/recommendation_form.html`
  - `author/strategy_form.html`
  - не показывать пользователю `draft`, `review` и другие raw enum values в help text, pill и readonly note

- [x] **L2** Локализовать user-facing ошибки редактирования
  - `services/author.py`
  - ошибки вида `Редактировать можно только draft-стратегии`
  - ошибки вида `Редактировать можно только рекомендации в статусах draft или review`
  - в UI и backend feedback должны использоваться русские статусы

- [x] **L3** Добавить regression coverage
  - template/UI test на отсутствие raw `draft/review` в author editor
  - test на русские user-facing ошибки для strategy/recommendation edit guards

### Acceptance

- в author editor не видно raw enum values вроде `draft`, `review`, `published`
- readonly notes, status pills и ошибки показывают только русскую копию
- author editor не ломает текущий compact layout и data flow

---

## Блок M — Remaining staff density pass

**Цель:** довести compact operator-first density до остальных staff surfaces, где еще остались большие hero-блоки, пустые зоны и слабая видимость ключевых данных до открытия карточки.

- [ ] **M1** Убрать oversized page-head/hero из remaining admin surfaces
  - `/admin/dashboard`
  - `/admin/products`
  - `/admin/payments`
  - `/admin/subscriptions`
  - `/admin/promos`
  - `/admin/analytics/*`
  - `/admin/delivery`
  - `/moderation/detail`
  - `/author/dashboard`

- [ ] **M2** Довести compact registries до консистентного operator-readability
  - в списке должно быть видно ключевое содержимое записи до клика `Открыть`
  - для row summary использовать 1-2 compact secondary lines вместо большого detail-screen dependence
  - не плодить большие пустые зоны ради декоративного copy

- [ ] **M3** Перевести remaining admin forms в compact section layout
  - `admin/product_form.html`
  - `admin/legal_form.html`
  - `admin/promo_form.html`
  - `admin/payment_detail.html`
  - `admin/subscription_detail.html`
  - `admin/delivery_detail.html`

- [ ] **M4** Упростить operator affordances
  - в быстрых строках создания CTA должен быть явным по результату, а не символьным
  - helper copy должен объяснять следующий шаг в 1 короткой строке
  - статусы и secondary hints должны оставаться компактными

- [ ] **M5** Добавить regression/manual acceptance coverage
  - smoke-check на отсутствие giant hero-block на указанных surfaces
  - smoke-check на compact registries, где ключевые поля видны без открытия карточки
  - smoke-check на inline create CTA и immediate next step

### Acceptance

- staff surfaces не содержат больших пустых hero-зон как primary pattern
- ключевые поля записи видны в реестре до открытия detail/edit
- remaining admin forms используют тот же compact section language, что и strategy/recommendation editors
- inline operator shortcuts объясняют результат действия без двусмысленности
