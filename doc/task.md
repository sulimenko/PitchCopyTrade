# PitchCopyTrade — Active Tasks
> Обновлено: 2026-03-27
> Это единый backlog-файл проекта. Все активные задачи ведутся только здесь.

## Статусы

- `[ ]` — не начато
- `[~]` — в работе
- `[x]` — завершено
- `[!]` — заблокировано

Предыдущие циклы не переносятся в этот backlog. Их архив — только git history.

## Блок A — Документный reset и research entrypoint

### Контекст

Старые документы накопили:
- закрытые фазы;
- утверждения, которые больше не соответствуют коду;
- ложную картину "все уже закрыто".

Новый цикл должен стартовать с компактного набора канонических документов.

### Задачи

- [x] **A1** Переписать `doc/blueprint.md` только под текущий subscriber/Mini App цикл
- [x] **A2** Свести backlog в единый `doc/task.md`
- [x] **A3** Переписать `doc/review.md` как текущий gate, а не как архив done-блоков
- [x] **A4** Добавить `doc/README.md` как стартовую точку исследования и локальный runbook без Docker
- [x] **A5** Проверить и убрать из остальных docs и readme ссылочную зависимость на устаревшие guide/prototype-артефакты, если они больше не нужны в текущем цикле

Acceptance:
- в канонических документах больше нет старых фаз `S/R/T/U/V/W/X/Y/Z/TAB/...`;
- документы не утверждают, что production bugs отсутствуют;
- новый инженер может начать исследование только по `doc/README.md`, `doc/blueprint.md`, `doc/task.md`, `doc/review.md`.

## Блок B — Локальный запуск без Docker и browser preview

### Контекст

Для текущего цикла нужен быстрый локальный контур на macOS + Python 3.12.4 без Docker. Цель — смотреть реальные GET/POST и быстро править view.

Факты, которые уже подтверждены:
- `api` стартует в `APP_DATA_MODE=file`;
- для старта `api` обязателен `INTERNAL_API_SECRET`;
- `file`-runtime зависит от содержимого `storage/runtime/*`;
- `public checkout` в `file`-mode создает заявку и отдает `201 Created`;
- browser preview для `/app/*` возможен через demo subscriber + `tg-auth` link.

### Задачи

- [x] **B1** Зафиксировать no-docker runbook в `doc/README.md`
- [x] **B2** Зафиксировать способ сброса `storage/runtime/*` перед воспроизводимыми тестами
- [x] **B3** Зафиксировать browser-preview способ для Mini App через `tg-auth` demo link
- [x] **B4** Добавить first-class preview mode для Mini App и staff, чтобы не требовались ручные токены/cookies для локальной верстки
- [x] **B5** Добавить отдельный reproducible local script/profile для `file`-mode smoke-check'ов

Acceptance:
- локальный запуск `api` без Docker описан одной короткой последовательностью команд;
- отдельно описано, какие URL открывать для public, Mini App и help;
- отдельно описано, что browser preview не заменяет финальную проверку в Telegram WebApp.

## Блок C — Mini App navigation и information architecture

### Контекст

Текущий subscriber flow концептуально расползся:
- есть `/miniapp`, `/app`, `/app/status`, `/app/catalog`, `/app/help`;
- первый экран и help-поведение расходятся между роутами и bot-командами;
- пользовательский запрос: главный экран Mini App должен сразу показывать витрину стратегий, а help должен жить на `/help`.

### Задачи

- [x] **C1** Зафиксировать `catalog-first` contract для Mini App
  - `/app/catalog` становится canonical first screen;
  - `/app/status` остается secondary screen, а не входной hero-flow.

- [x] **C2** Привести entry points к одному контракту
  - `/app`;
  - `/miniapp`;
  - bot `start`;
  - bot `help`.

- [x] **C3** Сделать `/app/help` canonical help-screen
  - help открывается как экран приложения;
  - bot `/help` не должен ограничиваться текстовым сообщением `PitchCopyTrade`.

- [x] **C4** Убрать сценарии, где навигация плодит новые вкладки/message-launches
  - один webview;
  - внутренняя навигация внутри приложения;
  - без обязательного возврата в чат ради перехода на следующий экран.

- [x] **C5** Пересобрать miniapp-nav и entry copy под новый каталог-first сценарий

Acceptance:
- после auth пользователь попадает в каталог, а не в status/onboarding;
- help открывается как экран интерфейса, а не как бот-эхо;
- пользовательский flow читается как единое приложение.

## Блок D — Витрина и страница стратегии

### Контекст

Текущие `public/catalog.html` и `public/strategy_detail.html` уже существуют, но:
- не дают сильного first-screen value;
- не раскрывают механику стратегии;
- слабо отрабатывают риск/доверие/CTA;
- не используют потенциал референсов `Straddle.pdf` и Figma.

### Задачи

- [x] **D1** Пересобрать hero каталога Mini App
  - меньше онбординга;
  - больше карточек стратегии;
  - быстрее переход к выбору.

- [x] **D2** Пересобрать карточку стратегии
  - автор;
  - value proposition;
  - риск;
  - горизонт;
  - минимальный капитал;
  - главный CTA;
  - без перегруза вторичными действиями.

- [x] **D3** Пересобрать `strategy_detail` под структурный narrative
  - hero;
  - thesis;
  - mechanics;
  - risk;
  - tariffs;
  - FAQ/documents.

- [x] **D4** Подготовить content contract для strategy detail
  - решить, что живет в structured fields;
  - что временно допустимо держать в `full_description`;
  - как это редактируется staff/author контуром.

- [x] **D5** Использовать `Straddle.pdf` как один из reference-материалов
  - взять сильные части narrative;
  - не копировать презентационный стиль как есть.

- [x] **D6** Проверить mobile-first behavior для Mini App
  - 390x844 / 430x932;
  - один доминирующий CTA;
  - читаемая длина блоков;
  - без длинных серых "стен текста".

Acceptance:
- страницу стратегии можно читать без знания внутреннего устройства проекта;
- value, risk и commercial CTA понятны на первом экране;
- референсы из Figma и Straddle используются как input, а не как буквальный шаблон.

## Блок E — Real-time instrument data

### Контекст

Текущий `/api/instruments` отдает статический список локальных инструментов и не заполняет quote-поля.

Новый источник:
- `https://meta.pbull.kz/api/marketData/forceDataSymbol?symbol={ticker}`
- sample structure подтверждена `NVTK.json`.

### Задачи

- [x] **E1** Сделать backend adapter для `meta.pbull.kz`
- [x] **E2** Нормализовать provider response в продуктовый JSON contract
- [x] **E3** Подключить quote data в те view/flows, где она реально нужна
  - карточка стратегии;
  - detail стратегии;
  - author recommendation editor;
  - инструментальный picker.
- [x] **E4** Добавить cache TTL и fallback behavior
- [x] **E5** Решить расхождение между `storage/seed/json/instruments.json` и дрейфующим `storage/runtime/json/instruments.json`

Acceptance:
- по тикеру `NVTK` backend отдает предсказуемую нормализованную quote-модель;
- сетевые сбои не валят страницу;
- UI показывает controlled empty/stale state вместо raw ошибки.

## Блок F — Checkout и payment reliability

### Контекст

Есть несколько потенциальных production дефектов:
- кнопка `Создать заявку на оплату` в Mini App не всегда работает на desktop;
- после авторизации был transient JSON parse error на `/admin/dashboard`;
- при оформлении подписки в Mini App был `Internal Server Error`, подписка не появилась;
- каждый переход в Mini App создает новую "закладку";
- `/help` в боте присылает еще одно сообщение вместо перехода на help-screen.

### Задачи

- [x] **F1** Разобрать desktop/mobile расхождение для `Создать заявку на оплату`
  - воспроизведение;
  - network trace;
  - response body;
  - session/cookie context;
  - различие browser vs Telegram WebView.

- [x] **F2** Разобрать `Internal Server Error` при создании подписки из Mini App
  - проверить путь `payment -> subscription -> commit -> response`;
  - отловить controlled business errors;
  - убрать raw `500`.

- [x] **F3** Разобрать transient JSON parse error после login redirect на `/admin/dashboard`
  - capture response headers/body;
  - capture browser console;
  - понять, был ли это truncated response, bad fetch, cached partial payload или auth/session race.

- [x] **F4** Перевести navigation contract на one-webview behavior
  - без лишних bot message hops;
  - без ощущения "каждый экран — новая закладка".

- [x] **F5** Переделать bot `/help`
  - либо web_app/deeplink на `/app/help`;
  - либо явный UI entry в уже открытый контур.

Acceptance:
- checkout flow одинаково предсказуем на desktop и mobile;
- в Mini App нет raw `Internal Server Error`;
- help не дублирует бот-сообщения;
- навигация не распадается на множество отдельных entry points.

## Блок G — Browser/device validation

### Контекст

Mini App должен удобно редактироваться в обычном браузере, но финальная проверка все равно проходит в Telegram.

### Задачи

- [x] **G1** Собрать список canonical preview URL для дизайна и верстки
- [x] **G2** Собрать список canonical real-device сценариев для Telegram
- [x] **G3** Зафиксировать минимум smoke-check для каждой surface:
  - public;
  - miniapp;
  - admin;
  - author.

Acceptance:
- у следующего исполнителя есть короткий набор URL и сценариев для ручной проверки;
- локальный browser preview и реальный Telegram check описаны раздельно.

## Блок H — Env contract unification

### Контекст

Сейчас проект использует один канонический env-контракт:
- runtime приложения читает `.env`;
- deploy/migration артефакты должны читать тот же `.env`.

Из-за этого локальный запуск и миграции расходятся:
- `uvicorn pitchcopytrade.main:app` падает, если `.env` не заполнен;
- `deploy/migrate.sh` и `deploy/docker-compose.server.yml` должны читать тот же `.env`;
- в репозитории должен остаться один очевидный ответ, какой env-файл канонический.

### Задачи

- [x] **H1** Зафиксировать `.env` как единственный активный env-файл для runtime, migrate и server compose
- [x] **H2** Вернуть один tracked sample-файл с placeholder-значениями
- [x] **H3** Убрать активные зависимости от старого server-env контракта из deploy/docs/tests
- [x] **H4** Не добавлять fallback сразу на два env-файла
- [x] **H5** Обновить runbook и guardrail-тесты под новый контракт

Acceptance:
- `Settings()`, `deploy/migrate.sh` и `deploy/docker-compose.server.yml` используют один и тот же `.env`;
- в активных docs/readme/tests больше нет старого server-env контракта как обязательного runtime-пути;
- в репозитории есть один sample-файл с placeholder-значениями;
- нельзя получить ситуацию, когда приложение стартует, а миграции падают только из-за другого имени env-файла.

## Блок I — Local dev access bootstrap

### Контекст

Текущий локальный auth-контур неудобен для DB/dev-режима:
- staff UI требует staff session cookie;
- subscriber/Mini App использует отдельный Telegram fallback cookie;
- seeded admin в DB-режиме создается без пароля и только с ролью `admin`;
- локальный HTTP-запуск без HTTPS/Telegram не дает простого способа войти во все защищенные разделы;
- `preview` полезен для верстки, но не заменяет доступ к реальным protected flow.

### Задачи

- [x] **I1** Спроектировать dev-only способ локального входа без реального Telegram/OAuth
- [x] **I2** Реализовать local superuser bootstrap с ролями `admin + author + moderator`
- [x] **I3** Использовать текущую cookie/session модель, а не вводить отдельный production-like auth stack без необходимости
- [x] **I4** Обеспечить локальный доступ к защищенным staff-разделам и `/app/*`
- [x] **I5** Задокументировать способ переключения режимов `admin` / `author` / `moderator` и ограничения dev-bootstrap

Acceptance:
- локальный инженер может получить доступ к `/admin/*`, `/author/*`, `/moderation/*` и защищенным `/app/*` без реального Telegram WebApp или OAuth;
- решение включается только в dev/local-контуре и не создает backdoor для staging/production;
- доступ строится поверх уже существующих session/cookie механизмов проекта;
- `preview` и реальный protected-flow остаются двумя разными сценариями.

## Блок J — Server regression recovery и public-first navigation

### Контекст

Серверная проверка опровергла часть ранее закрытых UX/runtime-задач:
- Mini App на сервере визуально расползся в 2 колонки там, где нужен 1-column mobile-first layout;
- blue-dominant visual language ослаблен;
- повторные входы и переходы открывают новые вкладки / новые Mini App entry вместо одного webview;
- first server page должна быть `https://pct.test.ptfin.ru/catalog`, а остальные surface должны открываться переходом через нее;
- `Создать заявку на оплату` приводит к `Internal Server Error`;
- в admin legal registry остается dead `Просмотр` link, ведущий в `404`.

### Задачи

- [x] **J1** Воспроизвести server-side layout drift и вернуть Mini App/catalog к 1-column mobile-first layout на целевом device width
- [x] **J2** Вернуть более выраженную blue-dominant visual language для CTA, pills и навигационных элементов
- [x] **J3** Пересобрать public-first entry contract: каноническая первая страница сервера = `/catalog`
- [x] **J4** Починить one-webview navigation между bot entry, `/catalog`, Mini App и help без открытия новых вкладок
- [x] **J5** Разобрать и исправить `Internal Server Error` в checkout по кнопке `Создать заявку на оплату`
- [x] **J6** Убрать dead legal CTA: либо реализовать detail route, либо удалить/заменить ссылку `Просмотр`
- [x] **J7** Перепроверить эти сценарии на реальном сервере и в реальном Telegram device-flow, а не только в local preview

Acceptance:
- Mini App/catalog на целевом мобильном размере снова одноколоночный, а не двухколоночный;
- основные controls и CTA вернули blue-dominant характер вместо нейтрального/серого визуального дрейфа;
- повторные bot/help/catalog переходы не плодят новые Mini App вкладки;
- canonical server entry начинается с `/catalog`, а дальнейшие переходы предсказуемы и не ломают flow;
- checkout либо создает ожидаемый `payment + subscription`, либо возвращает controlled business error без `500`;
- legal registry больше не отправляет оператора в `404`.

## Блок K — Полный отказ от `recommendations` и переход на `messages`

### Решение принято

Этот блок больше не про `Форму 2` поверх старой схемы. Решение уже принято и не обсуждается:
- `recommendations`, `recommendation_legs`, `recommendation_attachments`, `recommendation_messages` удаляются из проекта полностью;
- `messages` становится единственной контентной сущностью проекта;
- старая `Форма 1` удаляется из проекта полностью;
- в проекте остается только новый message-based editor;
- никакой legacy compatibility, dual write, fallback schema и backfill-слоев делать не нужно;
- `deploy/schema.sql` и seed data пересобираются заново под новую схему;
- DB не должна содержать business-check, foreign key, unique и прочие прикладные ограничения; прикладная валидация живет только в backend;
- `BOOLEAN`-поля по возможности не использовать; вместо этого использовать `VARCHAR` и `VARCHAR[]`;
- названия полей должны быть полными словами без сокращений и как можно короче: одно слово лучше двух, два лучше трех;
- `documents` и `deals` как JSON-массивы должны иметь default `[]`, а `text` как JSON-объект должен иметь default `{}`.

### Что должен понять worker перед стартом

Текущий проект жестко завязан на `Recommendation` как на корневую сущность:
- author workspace создает, редактирует и публикует рекомендации;
- moderation queue читает `Recommendation.status`;
- subscriber feed и detail читают опубликованные рекомендации;
- Telegram notification и bot broadcast форматируют рекомендации;
- file mode хранит четыре отдельных recommendation datasets;
- admin/delivery/preview/test suite используют те же объекты.

Следствие:
- это не точечный refactor модели;
- это полный message-centric rewrite нескольких слоев проекта;
- безопасный путь выполнения для mini-worker — делать работу большими, но законченными итерациями.

### Целевая DB-схема

#### Таблица `messages`

Ниже final target. Если worker делает SQLAlchemy model, он должен повторять эту структуру по смыслу.

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,

    thread UUID,
    parent UUID,

    author UUID,
    user UUID,
    moderator UUID,

    strategy UUID,
    bundle UUID,

    deliver VARCHAR(32)[] DEFAULT ARRAY[]::VARCHAR(32)[],
    channel VARCHAR(32)[] DEFAULT ARRAY['telegram', 'miniapp']::VARCHAR(32)[],

    kind VARCHAR(32),
    type VARCHAR(32),
    status VARCHAR(32) DEFAULT 'draft',
    moderation VARCHAR(32) DEFAULT 'required',

    title VARCHAR(255),
    comment TEXT,

    schedule TIMESTAMPTZ,
    published TIMESTAMPTZ,
    archived TIMESTAMPTZ,

    documents JSONB DEFAULT '[]'::jsonb,
    text JSONB DEFAULT '{}'::jsonb,
    deals JSONB DEFAULT '[]'::jsonb,

    created TIMESTAMPTZ,
    updated TIMESTAMPTZ
);
```

#### Смысл полей

- `id`: идентификатор сообщения;
- `thread`: идентификатор корневой идеи/цепочки, нужен для `idea -> update -> close -> cancel`;
- `parent`: прямой родитель сообщения в треде;
- `author`: автор, от имени которого идет сообщение;
- `user`: пользователь staff-side, который создал/сохранил запись;
- `moderator`: пользователь, который провел модерацию;
- `strategy`: привязка к стратегии для доступа и фильтрации;
- `bundle`: привязка к bundle, если публикация bundle-oriented;
- `deliver`: массив маршрутов доставки, например `['strategy', 'author']`;
- `channel`: массив каналов публикации, например `['telegram', 'miniapp']`;
- `kind`: бизнес-тип сообщения;
- `type`: тип содержимого;
- `status`: lifecycle;
- `moderation`: режим модерации;
- `title`: заголовок карточки или публикации;
- `comment`: комментарий модератора или служебный комментарий;
- `schedule`: время отложенной публикации;
- `published`: фактическое время публикации;
- `archived`: время архивирования;
- `documents`: JSONB-массив документов;
- `text`: JSONB-объект текстового содержимого;
- `deals`: JSONB-массив сделок;
- `created`, `updated`: timestamps.

#### Backend enum-наборы

Worker не должен делать DB enum-типы. Достаточно backend enum-ов или констант.

- `kind`: `idea`, `update`, `close`, `cancel`, `note`
- `type`: `text`, `document`, `deal`, `mixed`
- `status`: `draft`, `review`, `approved`, `scheduled`, `published`, `archived`, `failed`
- `moderation`: `required`, `direct`
- `deliver`: `strategy`, `author`, `bundle`
- `channel`: `telegram`, `miniapp`, `web`

### JSONB-contract

#### `text`

`text` должен быть простым HTML-first объектом. Не использовать старую сложную markdown/entity-модель.

```json
{
  "format": "html",
  "title": "Опцион Call на MSFT",
  "body": "<p>Покупка <b>MSFT</b> на откате.</p><p>Цель 340, контроль риска обязателен.</p>",
  "plain": "Покупка MSFT на откате. Цель 340, контроль риска обязателен."
}
```

Почему так:
- Telegram умеет HTML parse mode нативно;
- HTML проще санитайзить на backend;
- тот же HTML проще использовать в web preview и Mini App;
- HTML проще, чем Telegram MarkdownV2, где слишком болезненный escaping;
- `plain` строится backend-ом из `body` и используется для fallback/search/logging.

#### `documents`

Хранить только metadata и ссылку на storage, но не файл.

```json
[
  {
    "id": "uuid",
    "name": "OnePager.pdf",
    "title": "One pager",
    "type": "application/pdf",
    "size": 183245,
    "storage": "local",
    "key": "messages/9d.../OnePager.pdf",
    "hash": "abc123..."
  }
]
```

#### `deals`

Минимальный вариант:

```json
[
  {
    "instrument": "uuid",
    "ticker": "MSFT",
    "side": "buy",
    "price": "320.00",
    "quantity": "200",
    "amount": "64000.00"
  }
]
```

Максимальный вариант:

```json
[
  {
    "instrument": "uuid",
    "ticker": "MSFT",
    "name": "Microsoft Corporation",
    "board": "NASDAQ",
    "currency": "USD",
    "lot": 1,
    "side": "buy",
    "price": "320.00",
    "quantity": "200",
    "amount": "64000.00",
    "from": "315.00",
    "to": "320.00",
    "stop": "300.00",
    "targets": ["330.00", "340.00", "355.00"],
    "period": "2-4 weeks",
    "note": "Покупка на коррекции",
    "status": "open",
    "opened": "2026-03-27T10:00:00Z",
    "closed": null,
    "result": {
      "price": null,
      "profit_amount": null,
      "profit_percent": null
    }
  }
]
```

### Backend validation rules

Так как DB не хранит прикладные ограничения, worker обязан реализовать backend validation layer.

Минимальные правила:
- `thread` обязателен для всех сообщений; для root-message backend ставит `thread = id`;
- `parent` обязателен для `kind = update|close|cancel`, если сообщение не root;
- если в `deliver` есть `strategy`, поле `strategy` обязательно;
- если в `deliver` есть `bundle`, поле `bundle` обязательно;
- если `type = text`, `text.body` обязателен;
- если `type = document`, `documents` должен быть непустым;
- если `type = deal`, `deals` должен быть непустым;
- если `type = mixed`, backend должен требовать хотя бы один непустой блок из `text.body`, `documents`, `deals`;
- если `status = scheduled`, `schedule` обязательно;
- если `status = published`, `published` обязательно;
- backend обязан санитайзить HTML в `text.body`;
- backend обязан генерировать `text.plain` из `text.body`.

### Scope по файлам

Worker не должен гадать, где менять код. Минимальный scope уже известен.

#### Схема и seed data

- `deploy/schema.sql`
- `deploy/README.md`
- `storage/seed/json/recommendations.json`
- `storage/seed/json/recommendation_legs.json`
- `storage/seed/json/recommendation_attachments.json`
- `storage/seed/json/recommendation_messages.json`
- новый dataset `storage/seed/json/messages.json`

#### Модели

- `src/pitchcopytrade/db/models/content.py`
- `src/pitchcopytrade/db/models/enums.py`
- `src/pitchcopytrade/db/models/__init__.py`
- `src/pitchcopytrade/db/models/accounts.py`
- `src/pitchcopytrade/db/models/catalog.py`
- `src/pitchcopytrade/db/models/notification_log.py`

#### File mode

- `src/pitchcopytrade/repositories/file_store.py`
- `src/pitchcopytrade/repositories/file_graph.py`

#### Репозитории и сервисы

- `src/pitchcopytrade/repositories/contracts.py`
- `src/pitchcopytrade/repositories/author.py`
- `src/pitchcopytrade/repositories/access.py`
- `src/pitchcopytrade/services/author.py`
- `src/pitchcopytrade/services/moderation.py`
- `src/pitchcopytrade/services/notifications.py`
- `src/pitchcopytrade/services/publishing.py`
- `src/pitchcopytrade/services/acl.py`
- `src/pitchcopytrade/services/delivery_admin.py`
- `src/pitchcopytrade/services/preview.py`
- `src/pitchcopytrade/services/subscriber.py`
- `src/pitchcopytrade/services/admin.py`

#### Routes, bot, worker

- `src/pitchcopytrade/api/routes/author.py`
- `src/pitchcopytrade/api/routes/moderation.py`
- `src/pitchcopytrade/api/routes/app.py`
- `src/pitchcopytrade/api/routes/preview.py`
- `src/pitchcopytrade/api/routes/cabinet.py`
- `src/pitchcopytrade/api/routes/_grid_serializers.py`
- `src/pitchcopytrade/bot/main.py`
- `src/pitchcopytrade/worker/jobs/placeholders.py`

#### Templates

- `src/pitchcopytrade/web/templates/author/recommendation_form.html`
- `src/pitchcopytrade/web/templates/author/recommendations_list.html`
- `src/pitchcopytrade/web/templates/author/dashboard.html`
- `src/pitchcopytrade/web/templates/moderation/detail.html`
- `src/pitchcopytrade/web/templates/app/feed.html`
- `src/pitchcopytrade/web/templates/app/recommendation_detail.html`
- `src/pitchcopytrade/web/templates/preview/author_dashboard.html`
- `src/pitchcopytrade/web/templates/cabinet/recommendations.html`
- `src/pitchcopytrade/web/templates/cabinet/recommendation_row.html`
- `src/pitchcopytrade/web/templates/admin/dashboard.html`
- `src/pitchcopytrade/web/templates/admin/delivery_detail.html`
- `src/pitchcopytrade/web/templates/staff_base.html`

#### Tests

- `tests/test_author_services.py`
- `tests/test_author_ui.py`
- `tests/test_moderation_ui.py`
- `tests/test_notifications_service.py`
- `tests/test_access_delivery.py`
- `tests/test_db_models.py`
- `tests/test_file_repositories.py`
- `tests/test_lifecycle.py`
- `tests/test_publishing_worker.py`
- `tests/test_messages.py`
- `tests/test_storage_local.py`
- `tests/test_worker_baseline.py`
- `tests/test_admin_ui.py`
- `tests/test_payment_sync.py`
- `tests/test_subscriber_reminders.py`

### План работы для worker по крупным итерациям

Итерации должны выполняться по порядку. Не надо смешивать все сразу.

- [x] **K1** Итерация A: переписать schema, SQLAlchemy models и file-mode storage под единую сущность `messages`
  - удалить recommendation-модели и child-таблицы;
  - завести `Message` model;
  - пересобрать `deploy/schema.sql`;
  - пересобрать file datasets и seed data;
  - перевести `notification_log` на `message_id`.
  Acceptance:
  - DB schema и file-mode dataset больше не содержат `recommendations*`;
  - `messages` есть и соответствует target schema;
  - `tests/test_db_models.py` и `tests/test_file_repositories.py` обновлены и проходят.

- [x] **K2** Итерация B: переписать repository и service layer на `messages`
  - удалить `Recommendation*` из contracts/repositories/services;
  - завести message-centric CRUD и validation;
  - реализовать backend rules для `type`, `deliver`, `status`, HTML sanitize, `thread`, `parent`.
  Acceptance:
  - author/moderation/access/publishing/notification services не импортируют `Recommendation*`;
  - `tests/test_author_services.py`, `tests/test_lifecycle.py`, `tests/test_publishing_worker.py` обновлены и проходят.

- [x] **K3** Итерация C: удалить Form 1 и перевести author/moderation UI на новый editor
  - оставить только message-based editor;
  - реализовать только новый flow с `text`, `document`, `deal`, `mixed`;
  - удалить UI-зависимости от `summary`, `thesis`, `market_context`, `legs`, `attachments`, `messages` как отдельных сущностей.
  Acceptance:
  - в author UI больше нет старой формы;
  - moderation detail читает `messages.text/documents/deals`;
  - `tests/test_author_ui.py` и `tests/test_moderation_ui.py` обновлены и проходят.

- [x] **K4** Итерация D: перевести subscriber feed, Mini App, Telegram и worker-delivery на `messages`
  - переписать app feed/detail;
  - переписать notification formatter;
  - переписать Telegram broadcast;
  - scheduler публикует `messages.status = scheduled`.
  Acceptance:
  - Mini App читает `Message`, а не `Recommendation`;
  - Telegram notification/broadcast формируется из `text/documents/deals`;
  - `tests/test_notifications_service.py`, `tests/test_access_delivery.py`, `tests/test_subscriber_reminders.py`, `tests/test_worker_baseline.py` обновлены и проходят.

- [x] **K5** Итерация E: зачистить legacy terminology, seed/docs/tests и довести проект до консистентного состояния
  - удалить остаточные импорты и названия `recommendation*`;
  - обновить docs, grids, dashboards и delivery pages;
  - удалить старые recommendation seed files;
  - при необходимости переименовать тесты/страницы в `messages`.
  Acceptance:
  - `rg -n "Recommendation|recommendation_" src tests storage deploy` не возвращает живой product code, кроме исторических комментариев, если они остались сознательно;
  - полный test suite проходит в целевой runtime;
  - schema, seeds, UI и services говорят на одном message-centric языке.

### Инструкции для mini-worker

Чтобы задача была посильной даже для `gpt-5.4-mini medium`, worker должен соблюдать следующие правила:
- не пытаться сохранить старую архитектуру;
- не делать dual write между `recommendations` и `messages`;
- не создавать временные compatibility adapters;
- не добавлять новые abstraction layers без необходимости;
- в каждой итерации сначала переписать model/schema, потом repository/service, потом routes/templates, потом tests;
- если слой полностью переписан, удалить старый код, а не оставлять рядом;
- если есть выбор между красивым промежуточным дизайном и прямым удалением legacy, выбирать прямое удаление legacy;
- каждый блок завершать тестами именно этого блока до перехода к следующему.

### Definition of done

- в проекте нет рабочей зависимости от `Recommendation`, `RecommendationLeg`, `RecommendationAttachment`, `RecommendationMessage`;
- в проекте нет старой `Формы 1`;
- `messages` является единственной content-сущностью проекта;
- Telegram, Mini App, author workspace, moderation и worker delivery читают одну и ту же модель;
- seed data и file mode соответствуют новой схеме;
- `deploy/schema.sql` соответствует новой схеме;
- validation живет на backend, а не в DB;
- JSONB contract используется ровно в трех полях: `documents`, `text`, `deals`.

### Готовые prompts для worker

Ниже 5 независимых prompts. Их нужно запускать по одному и строго по порядку: сначала `K1`, потом `K2` и так далее.

#### Prompt `K1`

```text
Ты делаешь только итерацию K1. Не трогай K2-K5, кроме минимально необходимой компиляционной адаптации.

Контекст:
- проект полностью отказывается от `recommendations`, `recommendation_legs`, `recommendation_attachments`, `recommendation_messages`;
- новая единственная content-сущность называется `messages`;
- никакой legacy compatibility, dual write, fallback schema и backfill не нужен;
- DB не должна содержать business-check, foreign key, unique и прочие прикладные ограничения;
- валидация будет жить на backend;
- Boolean-поля по возможности не использовать;
- JSONB поля: `documents` default `[]`, `text` default `{}`, `deals` default `[]`.

Твоя цель:
- переписать schema, SQLAlchemy models и file-mode storage под единую сущность `messages`.

Целевая DB-схема:
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    thread UUID,
    parent UUID,
    author UUID,
    user UUID,
    moderator UUID,
    strategy UUID,
    bundle UUID,
    deliver VARCHAR(32)[] DEFAULT ARRAY[]::VARCHAR(32)[],
    channel VARCHAR(32)[] DEFAULT ARRAY['telegram', 'miniapp']::VARCHAR(32)[],
    kind VARCHAR(32),
    type VARCHAR(32),
    status VARCHAR(32) DEFAULT 'draft',
    moderation VARCHAR(32) DEFAULT 'required',
    title VARCHAR(255),
    comment TEXT,
    schedule TIMESTAMPTZ,
    published TIMESTAMPTZ,
    archived TIMESTAMPTZ,
    documents JSONB DEFAULT '[]'::jsonb,
    text JSONB DEFAULT '{}'::jsonb,
    deals JSONB DEFAULT '[]'::jsonb,
    created TIMESTAMPTZ,
    updated TIMESTAMPTZ
);
```

Ownership / write scope:
- `deploy/schema.sql`
- `deploy/README.md`
- `src/pitchcopytrade/db/models/content.py`
- `src/pitchcopytrade/db/models/enums.py`
- `src/pitchcopytrade/db/models/__init__.py`
- `src/pitchcopytrade/db/models/accounts.py`
- `src/pitchcopytrade/db/models/catalog.py`
- `src/pitchcopytrade/db/models/notification_log.py`
- `src/pitchcopytrade/repositories/file_store.py`
- `src/pitchcopytrade/repositories/file_graph.py`
- `storage/seed/json/recommendations.json`
- `storage/seed/json/recommendation_legs.json`
- `storage/seed/json/recommendation_attachments.json`
- `storage/seed/json/recommendation_messages.json`
- новый `storage/seed/json/messages.json`
- `tests/test_db_models.py`
- `tests/test_file_repositories.py`

Что сделать:
1. Удалить recommendation-модели и child-таблицы из model layer.
2. Завести новую model `Message`.
3. Перевести `notification_log` с `recommendation_id` на `message_id`.
4. Пересобрать `deploy/schema.sql` под новую схему.
5. Пересобрать file-mode datasets: убрать 4 старых dataset, добавить `messages`.
6. Удалить старые recommendation seed files или перестать использовать их; завести новый `messages.json`.
7. Обновить model exports и file graph serialization/deserialization.

Важно:
- ты не один в кодовой базе, не откатывай чужие изменения;
- не делай временные compatibility wrappers;
- не пытайся сохранить `Recommendation*` рядом с `Message`;
- если где-то код ломается из-за новых импортов, разрешены только минимальные компиляционные правки вне scope, без логического завершения K2-K5.

Что не делать:
- не переписывать author services и routes глубоко;
- не делать новый UI;
- не трогать bot formatting и notification logic глубже, чем нужно для компиляции;
- не добавлять DB foreign keys или DB checks.

Проверка:
- обнови и прогоняй только релевантные тесты для K1;
- минимум: `tests/test_db_models.py`, `tests/test_file_repositories.py`.

Формат результата:
- кратко перечисли, что изменено;
- перечисли измененные файлы;
- отдельно укажи, какие тесты прогнал и их результат;
- отдельно укажи, что сознательно оставил на K2-K5.
```

#### Prompt `K2`

```text
Ты делаешь только итерацию K2. Не бери K1, K3, K4, K5, кроме минимально необходимой компиляционной адаптации.

Предположение:
- K1 уже завершен, модель `Message` и schema `messages` уже существуют;
- legacy `Recommendation*` больше не должны быть source of truth.

Контекст:
- проект полностью message-centric;
- backend validation важнее DB validation;
- никаких compatibility adapters и dual write делать нельзя.

Твоя цель:
- переписать repository и service layer на `messages`.

Backend contract:
- `kind`: `idea`, `update`, `close`, `cancel`, `note`
- `type`: `text`, `document`, `deal`, `mixed`
- `status`: `draft`, `review`, `approved`, `scheduled`, `published`, `archived`, `failed`
- `moderation`: `required`, `direct`
- `deliver`: `strategy`, `author`, `bundle`
- `channel`: `telegram`, `miniapp`, `web`

Validation rules:
- `thread` обязателен для всех сообщений; для root-message backend ставит `thread = id`;
- `parent` обязателен для `kind = update|close|cancel`, если сообщение не root;
- если в `deliver` есть `strategy`, поле `strategy` обязательно;
- если в `deliver` есть `bundle`, поле `bundle` обязательно;
- если `type = text`, `text.body` обязателен;
- если `type = document`, `documents` должен быть непустым;
- если `type = deal`, `deals` должен быть непустым;
- если `type = mixed`, требуется хотя бы один непустой блок из `text.body`, `documents`, `deals`;
- если `status = scheduled`, `schedule` обязателен;
- если `status = published`, `published` обязателен;
- backend должен санитайзить HTML в `text.body`;
- backend должен генерировать `text.plain` из `text.body`.

Ownership / write scope:
- `src/pitchcopytrade/repositories/contracts.py`
- `src/pitchcopytrade/repositories/author.py`
- `src/pitchcopytrade/repositories/access.py`
- `src/pitchcopytrade/services/author.py`
- `src/pitchcopytrade/services/moderation.py`
- `src/pitchcopytrade/services/notifications.py`
- `src/pitchcopytrade/services/publishing.py`
- `src/pitchcopytrade/services/acl.py`
- `src/pitchcopytrade/services/delivery_admin.py`
- `src/pitchcopytrade/services/preview.py`
- `src/pitchcopytrade/services/subscriber.py`
- `src/pitchcopytrade/services/admin.py`
- `tests/test_author_services.py`
- `tests/test_lifecycle.py`
- `tests/test_publishing_worker.py`

Что сделать:
1. Удалить imports и бизнес-логику на `Recommendation*` из repository/service layer.
2. Завести message-centric CRUD/select/query contracts.
3. Переписать author/moderation/access/publishing/notification services на `Message`.
4. Реализовать validation layer для `text/documents/deals`, `thread/parent`, `deliver/status`.
5. Перевести publishing scheduler на `messages.status = scheduled`.

Важно:
- ты не один в кодовой базе, не откатывай чужие изменения;
- не добавляй новые абстракции без необходимости;
- не делай UI-рефактор глубже, чем нужно для компиляции;
- можно делать минимальные сигнатурные адаптации в routes, если без этого сервисы не собираются, но полноценный route/UI rewrite оставь на K3-K4.

Что не делать:
- не переделывать author templates;
- не делать subscriber feed/detail;
- не переписывать bot/main.py глубже минимума;
- не трогать docs и общую терминологическую зачистку.

Проверка:
- минимум: `tests/test_author_services.py`, `tests/test_lifecycle.py`, `tests/test_publishing_worker.py`.

Формат результата:
- кратко перечисли service/repository изменения;
- перечисли измененные файлы;
- перечисли тесты и результат;
- опиши, какие слои сознательно оставлены на K3-K5.
```

#### Prompt `K3`

```text
Ты делаешь только итерацию K3. Не бери K1, K2, K4, K5, кроме минимально необходимой компиляционной адаптации.

Предположение:
- K1 и K2 уже завершены;
- `Message` уже является единственной content-сущностью backend;
- старая recommendation-архитектура больше не должна проявляться в UI.

Твоя цель:
- удалить старую Form 1 и перевести author/moderation UI на новый editor, который работает только с `messages`.

Content contract:
- editor поддерживает только новый flow;
- `type`: `text`, `document`, `deal`, `mixed`;
- `text` хранится как HTML-first JSONB объект;
- `documents` и `deals` работают через JSONB contract новой `messages`-модели.

Ownership / write scope:
- `src/pitchcopytrade/api/routes/author.py`
- `src/pitchcopytrade/api/routes/moderation.py`
- `src/pitchcopytrade/api/routes/_grid_serializers.py`
- `src/pitchcopytrade/web/templates/author/recommendation_form.html`
- `src/pitchcopytrade/web/templates/author/recommendations_list.html`
- `src/pitchcopytrade/web/templates/author/dashboard.html`
- `src/pitchcopytrade/web/templates/moderation/detail.html`
- `src/pitchcopytrade/web/templates/staff_base.html`
- `tests/test_author_ui.py`
- `tests/test_moderation_ui.py`

Что сделать:
1. Удалить из UI старую Form 1 полностью.
2. Оставить только message-based editor.
3. Убрать UI-зависимости от `summary`, `thesis`, `market_context`, `legs`, `attachments`, `messages` как отдельных сущностей.
4. Переделать author create/edit/list flow на `Message`.
5. Переделать moderation detail под `messages.text`, `messages.documents`, `messages.deals`.
6. Обновить grid/list labels и actions так, чтобы UI не ссылался на recommendation legacy-contract.

Важно:
- ты не один в кодовой базе, не откатывай чужие изменения;
- не возвращай Form 1 даже как hidden fallback;
- если нужен промежуточный UI, он все равно должен быть message-centric;
- можно оставить временно старые route paths `/author/messages/*` как alias, если переименование path сейчас слишком дорого, но данные и формы должны работать через `Message`.

Что не делать:
- не переписывать subscriber feed/detail;
- не переделывать Telegram broadcast и worker delivery;
- не делать глобальную зачистку docs/test naming глубже своего scope.

Проверка:
- минимум: `tests/test_author_ui.py`, `tests/test_moderation_ui.py`.

Формат результата:
- кратко перечисли UI и route изменения;
- перечисли измененные файлы;
- перечисли тесты и результат;
- отдельно укажи, что осталось на K4-K5.
```

#### Prompt `K4`

```text
Ты делаешь только итерацию K4. Не бери K1, K2, K3, K5, кроме минимально необходимой компиляционной адаптации.

Предположение:
- K1-K3 уже завершены;
- author/moderation UI уже работает через `messages`;
- теперь нужно перевести subscriber-facing и delivery-facing слои.

Твоя цель:
- перевести subscriber feed, Mini App, Telegram и worker-delivery на `messages`.

Content rendering rules:
- источник данных только `Message`;
- текст публикации формируется из `text.body` / `text.plain`;
- документы читаются из `documents`;
- сделки читаются из `deals`;
- scheduler публикует `messages.status = scheduled`;
- Telegram отправка должна использовать HTML parse mode-friendly content.

Ownership / write scope:
- `src/pitchcopytrade/api/routes/app.py`
- `src/pitchcopytrade/api/routes/preview.py`
- `src/pitchcopytrade/bot/main.py`
- `src/pitchcopytrade/worker/jobs/placeholders.py`
- `src/pitchcopytrade/services/notifications.py`
- `src/pitchcopytrade/services/acl.py`
- `src/pitchcopytrade/repositories/access.py`
- `src/pitchcopytrade/services/subscriber.py`
- `src/pitchcopytrade/web/templates/app/feed.html`
- `src/pitchcopytrade/web/templates/app/recommendation_detail.html`
- `src/pitchcopytrade/web/templates/preview/author_dashboard.html`
- `tests/test_notifications_service.py`
- `tests/test_access_delivery.py`
- `tests/test_subscriber_reminders.py`
- `tests/test_worker_baseline.py`

Что сделать:
1. Переписать subscriber feed/detail на `Message`.
2. Переписать access filtering под новую сущность и поля `deliver`, `strategy`, `bundle`, `author`.
3. Переписать Telegram notification formatter на `text/documents/deals`.
4. Переписать bot broadcast на `Message`.
5. Переписать worker-delivery и scheduled publish на `messages`.

Важно:
- ты не один в кодовой базе, не откатывай чужие изменения;
- не возвращай старое форматирование из `RecommendationLeg`;
- если нужно временно сохранить старый URL path, допустимо, но response/view model должна быть message-centric;
- не трогай author editor и moderation UI глубже необходимого.

Что не делать:
- не заниматься общей терминологической зачисткой и документацией;
- не переделывать seeds/schema, если только не нужен минимальный компиляционный фикс.

Проверка:
- минимум: `tests/test_notifications_service.py`, `tests/test_access_delivery.py`, `tests/test_subscriber_reminders.py`, `tests/test_worker_baseline.py`.

Формат результата:
- кратко перечисли subscriber/bot/worker изменения;
- перечисли измененные файлы;
- перечисли тесты и результат;
- отдельно укажи, что осталось на K5.
```

#### Prompt `K5`

```text
Ты делаешь только итерацию K5. Это финальная зачистка после K1-K4.

Предположение:
- K1-K4 уже завершены;
- проект уже функционально работает на `messages`;
- теперь нужно довести кодовую базу до консистентного состояния и убрать legacy terminology.

Твоя цель:
- зачистить legacy terminology, seed/docs/tests и довести проект до консистентного message-centric состояния.

Ownership / write scope:
- `deploy/README.md`
- `storage/seed/json/*`
- `src/pitchcopytrade/api/routes/_grid_serializers.py`
- `src/pitchcopytrade/services/admin.py`
- `src/pitchcopytrade/services/delivery_admin.py`
- `src/pitchcopytrade/web/templates/admin/dashboard.html`
- `src/pitchcopytrade/web/templates/admin/delivery_detail.html`
- `src/pitchcopytrade/web/templates/cabinet/recommendations.html`
- `src/pitchcopytrade/web/templates/cabinet/recommendation_row.html`
- `src/pitchcopytrade/web/templates/cabinet/strategies.html`
- `src/pitchcopytrade/web/templates/staff_base.html`
- `tests/test_messages.py`
- `tests/test_admin_ui.py`
- `tests/test_payment_sync.py`
- все остальные тесты/документы, где осталась живая product-терминология `Recommendation|recommendation_`

Что сделать:
1. Удалить остаточные импорты и product-usage названий `Recommendation|recommendation_`.
2. Удалить старые recommendation seed files, если они еще физически лежат в проекте и больше не используются.
3. Обновить docs, grids, dashboards, delivery pages и cabinet pages на message-centric terminology.
4. При необходимости переименовать тестовые файлы и test names так, чтобы suite больше не опирался на старую сущность.
5. Довести репозиторий до состояния, в котором search по `Recommendation|recommendation_` не находит живой product code.

Важно:
- ты не один в кодовой базе, не откатывай чужие изменения;
- если где-то старый термин сознательно оставлен только в историческом комментарии, это допустимо, но в живом code path его быть не должно;
- не надо заново переписывать уже рабочие K1-K4 слои без причины.

Проверка:
1. Прогон search:
   - `rg -n "Recommendation|recommendation_" src tests storage deploy`
2. Прогон полного релевантного suite или максимально широкого поднабора после рефактора.

Формат результата:
- кратко перечисли, что зачищено;
- перечисли измененные файлы;
- приведи результат `rg -n "Recommendation|recommendation_" src tests storage deploy`;
- перечисли тесты и результат;
- отдельно укажи остаточные риски, если они есть.
```

### L. Final Hardening Before Clean DB Reset

Цель блока:
- закрыть все подтвержденные финальным review регрессии после перехода на `messages`;
- после этого дать безопасный путь для чистой DB-миграции;
- затем заполнить новую схему seed-данными так, чтобы можно было гонять все типы тестов: file-mode, db-mode, UI, service, worker, delivery.

Статус блока:
- `L1-L3` в основном реализованы, но post-implementation review выявил follow-up фиксы в author composer/edit flow
- `L4` clean reset contract поддерживается на уровне schema/startup runbook
- `L5` не подтвержден как завершенный: полный business seed в `APP_DATA_MODE=db` по-прежнему не выполняется автоматически
- [x] Финальный regression gate пройден: `./.venv/bin/python -m pytest -q` -> `218 passed`

Follow-up after post-implementation review (`2026-03-28`):
1. Structured deal edit round-trip нужно довести до консистентного `instrument_id` contract.
2. Existing document-only messages должны корректно проходить preview/edit без обязательного re-upload файла.
3. History table должна показывать либо реальные `channel`, либо быть переименована под audience/deliver contract.

Порядок выполнения:
1. `L1` — admin/file-mode/operator UI regressions
2. `L2` — `deliver` contract enforcement
3. `L3` — final Form 2 payload normalization
4. `L4` — clean DB reset / migration contract
5. `L5` — seed dataset for db-mode
6. `L6` — final regression gate

#### L1. Admin File-Mode And Operator UI Regressions

Контекст:
- финальный review подтвердил, что admin CRUD в file-mode сломан из-за `_validate_uuid()`;
- author/staff registries потеряли invite links и часть operator actions;
- payments queue потерял reference, по которому оператор вручную сопоставляет платеж.

Что исправить:
- убрать file-mode breaking behavior из admin edit/action routes для сущностей, где canonical IDs строковые;
- восстановить рабочие edit/action сценарии для legal, strategies, products, promos, staff;
- вернуть в author/staff registries:
  - абсолютный `invite_link`;
  - copy/invite action;
  - resend invite action;
  - явные role/status actions там, где они нужны оператору;
- вернуть в payments queue видимый payment reference:
  - `stub_reference` для manual/stub платежей;
  - `external_id` или provider-derived reference для provider платежей.

Файлы в scope:
- `src/pitchcopytrade/api/routes/admin.py`
- `src/pitchcopytrade/api/routes/_grid_serializers.py`
- `src/pitchcopytrade/web/templates/admin/staff_list.html`
- `src/pitchcopytrade/web/templates/admin/payments_list.html`
- `src/pitchcopytrade/web/templates/admin/dashboard.html`
- `tests/test_admin_ui.py`

Критерии приемки:
- file-mode seeded IDs вроде `doc-offer`, `strategy-1`, `product-1`, `promo-1`, `staff-2` больше не дают 404 на валидных admin routes;
- admin registries снова позволяют оператору скопировать invite link и выполнить основные actions без ручного поиска URL;
- payments queue снова показывает идентификатор, достаточный для ручной сверки платежа;
- соответствующие admin UI тесты проходят без monkeypatch обходов бизнес-логики.

Минимальная проверка:
- `./.venv/bin/python -m pytest -q tests/test_admin_ui.py`

#### L2. Enforce `deliver` As The Source Of Truth

Контекст:
- `Message.deliver` уже есть в модели и schema;
- текущий access layer и notification fan-out его игнорируют и используют только `strategy/author/bundle`;
- это создает risk of oversharing и oversending.

Что исправить:
- сделать `deliver` единственным routing contract для чтения и доставки;
- visibility в Mini App / subscriber-facing read-path должна совпадать с declared audience;
- outbound Telegram delivery должна совпадать с declared audience;
- сохранить backend validation:
  - если `deliver` содержит `strategy`, `strategy` обязателен;
  - если `deliver` содержит `bundle`, `bundle` обязателен;
  - если `deliver` содержит `author`, сообщение должно матчиться по author subscription path.

Файлы в scope:
- `src/pitchcopytrade/repositories/access.py`
- `src/pitchcopytrade/services/notifications.py`
- `src/pitchcopytrade/services/subscriber.py`
- `src/pitchcopytrade/services/acl.py`
- `src/pitchcopytrade/repositories/contracts.py`
- `tests/test_access_delivery.py`
- `tests/test_notifications_service.py`
- `tests/test_subscriber_reminders.py`

Критерии приемки:
- `deliver=['author']` не открывает сообщение strategy-only audience;
- `deliver=['strategy']` не отправляет сообщение author-only audience;
- `deliver=['bundle']` работает только через bundle routing;
- mixed cases вроде `['strategy', 'author']` отрабатывают как union, а не как implicit all;
- нигде в read/delivery path нет fallback логики “если есть strategy_id, показываем strategy subscribers несмотря на deliver”.

Минимальная проверка:
- `./.venv/bin/python -m pytest -q tests/test_access_delivery.py tests/test_notifications_service.py tests/test_subscriber_reminders.py`

#### L3. Final Form 2 Payload Normalization

Контекст:
- проект формально перешел на `messages`, но `services/author.py` все еще несет legacy recommendation/legs/attachments shape;
- producer и consumer для `documents` и `deals` пока не зафиксированы в одном финальном contract.

Цель:
- довести Form 2 до реально единственного message-centric payload contract без legacy полей.

Что исправить:
- удалить из form/service contract поля и flow, связанные со старой recommendation-структурой:
  - `summary`
  - `thesis`
  - `market_context`
  - `requires_moderation`
  - `scheduled_for`
  - `legs`
  - `attachments`
  - `structured_*`
  - любые другие остаточные recommendation-era aliases;
- зафиксировать один production contract:
  - `text`: HTML-first JSONB object;
  - `documents`: JSONB array с agreed short-field structure;
  - `deals`: JSONB array с agreed short-field structure;
- выровнять producer/consumer по одинаковым ключам;
- выровнять author UI, moderation UI, app detail view и Telegram formatter под один и тот же payload.

Рекомендуемый финальный contract:
- `text`:
  - `format`
  - `title`
  - `body`
  - `plain`
- `documents[]`:
  - `id`
  - `name`
  - `title`
  - `type`
  - `size`
  - `storage`
  - `key`
  - `hash`
- `deals[]` минимум:
  - `instrument`
  - `ticker`
  - `side`
  - `price`
  - `quantity`
  - `amount`
- `deals[]` расширение:
  - `name`
  - `board`
  - `currency`
  - `lot`
  - `from`
  - `to`
  - `stop`
  - `targets`
  - `period`
  - `note`
  - `status`
  - `opened`
  - `closed`
  - `result`

Файлы в scope:
- `src/pitchcopytrade/services/author.py`
- `src/pitchcopytrade/api/routes/author.py`
- `src/pitchcopytrade/api/routes/moderation.py`
- `src/pitchcopytrade/api/routes/app.py`
- `src/pitchcopytrade/bot/main.py`
- `src/pitchcopytrade/web/templates/author/message_form.html`
- `src/pitchcopytrade/web/templates/moderation/detail.html`
- `src/pitchcopytrade/web/templates/app/message_detail.html`
- `tests/test_author_services.py`
- `tests/test_author_ui.py`
- `tests/test_moderation_ui.py`
- `tests/test_messages.py`

Критерии приемки:
- нет живого product-flow, который зависит от `summary/thesis/market_context/legs/attachments/structured_*`;
- `documents` producer и consumer используют один и тот же field set;
- `deals` producer и consumer используют один и тот же field set;
- Form 2 является единственным editor flow;
- Telegram formatter и Mini App detail не читают старые ключи вроде `instrument_id`, `entry_from`, `object_key`, `original_filename`.

Минимальная проверка:
- `./.venv/bin/python -m pytest -q tests/test_author_services.py tests/test_author_ui.py tests/test_moderation_ui.py tests/test_messages.py`

#### L4. Clean DB Reset And Migration Contract

Контекст:
- после закрытия L1-L3 пользователь хочет выполнить чистую миграцию новой DB;
- в проекте больше не нужен legacy recommendation schema path;
- `deploy/schema.sql` должен быть единственным truth для clean reset.

Что сделать:
- привести `deploy/schema.sql` в полное соответствие текущим ORM-моделям `messages`-системы;
- гарантировать, что clean reset создает только новую message-centric schema, без legacy `recommendation_*`;
- проверить, что после reset проект поднимается в `APP_DATA_MODE=db`;
- привести migration/reset runbook в репозитории к одному воспроизводимому сценарию;
- если нужны helper scripts для reset/verify, добавить их явно, но без dual schema support.

Файлы в scope:
- `deploy/schema.sql`
- `deploy/migrate.sh`
- `deploy/README.md`
- `src/pitchcopytrade/db/models/*.py`
- `tests/test_db_models.py`
- `tests/test_deploy_server_files.py`

Критерии приемки:
- clean DB reset не создает legacy recommendation tables;
- `messages` schema, notification_log, catalog/account/commerce tables согласованы с ORM;
- локальный db-mode startup после reset не падает на schema mismatch;
- репозиторий содержит один понятный сценарий: reset -> seed -> startup -> tests.

Операторский сценарий после завершения задачи:
1. обновить `.env` / `.env.server` на db-mode;
2. выполнить clean reset;
3. загрузить seed data;
4. запустить app и tests.

Минимальная проверка:
- `./.venv/bin/python -m pytest -q tests/test_db_models.py`

#### L5. DB Seed Dataset For Message-Centric Project

Контекст:
- после clean reset нужна новая seed-база, достаточная для UI/service/worker тестов;
- seed должен покрывать не только `messages`, но и все зависимые справочники и операционные сущности.

Что сделать:
- собрать полный db/file-consistent seed dataset под новую схему;
- seed должен позволять прогонять:
  - admin flows;
  - author flows;
  - moderation flows;
  - subscriber Mini App/feed/detail;
  - payment and subscription flows;
  - delivery and notification flows;
  - worker and scheduled publish flows.

Обязательное seed-покрытие:
- users:
  - admin
  - moderator
  - author
  - subscriber
  - invited staff user
- roles / author_profiles
- strategies
- bundles и bundle_members
- subscription_products
- lead_sources
- promo_codes
- legal_documents
- payments
- subscriptions
- messages:
  - `type=text`
  - `type=document`
  - `type=deal`
  - `type=mixed`
  - `kind=idea`
  - `kind=update`
  - `kind=close`
  - `deliver=['strategy']`
  - `deliver=['author']`
  - `deliver=['bundle']`
  - `deliver=['strategy', 'author']`
  - draft / review / approved / scheduled / published / archived examples
- notification_log sample rows where useful for admin delivery views

Файлы в scope:
- `storage/seed/json/messages.json`
- `storage/seed/json/users.json`
- `storage/seed/json/author_profiles.json`
- `storage/seed/json/strategies.json`
- `storage/seed/json/bundles.json`
- `storage/seed/json/bundle_members.json`
- `storage/seed/json/subscription_products.json`
- `storage/seed/json/subscriptions.json`
- `storage/seed/json/payments.json`
- `storage/seed/json/promo_codes.json`
- `storage/seed/json/legal_documents.json`
- `storage/seed/json/notification_log.json`
- `src/pitchcopytrade/repositories/file_graph.py`
- `src/pitchcopytrade/repositories/file_store.py`
- `tests/test_file_repositories.py`
- `tests/test_worker_baseline.py`

Критерии приемки:
- clean reset + seed дает воспроизводимое локальное db/file состояние;
- tests не требуют ad-hoc ручного наполнения БД;
- message-related screens и services получают реалистичные данные из seeds;
- file-mode и db-mode не расходятся по ключевым shape assumptions.

Минимальная проверка:
- `./.venv/bin/python -m pytest -q tests/test_file_repositories.py tests/test_worker_baseline.py`

#### L5.1 Worker Prompt — Full DB Business Seed Importer

```text
Ты делаешь отдельную задачу по доведению `L5`: в `APP_DATA_MODE=db` после clean reset должен подниматься не только schema, но и полный business seed dataset.

Почему задача нужна:
- сейчас `deploy/migrate.sh --reset` создает чистую schema;
- затем startup в `APP_DATA_MODE=db` вызывает только `_run_seeders()`;
- `_run_seeders()` сейчас auto-seed-ит только:
  - `instruments`
  - bootstrap `admin`
- это создает ложное ощущение, что `L5` уже закрыт, хотя полного business seed в PostgreSQL нет.

Цель задачи:
- реализовать один канонический db-mode seed path для полного business dataset;
- использовать существующие canonical seed JSON файлы из `storage/seed/json/*`;
- после `bash deploy/migrate.sh --reset` и первого старта `api` база должна содержать тот же практический набор бизнес-данных, на который рассчитывает file-mode.

Что считать готовым результатом:
- после clean reset и первого startup в `APP_DATA_MODE=db` в БД есть:
  - users
  - roles
  - authors
  - lead_sources
  - instruments
  - author_watchlist_instruments
  - strategies
  - bundles
  - bundle_members
  - products
  - promo_codes
  - legal_documents
  - payments
  - subscriptions
  - user_consents
  - messages
  - notification_log
  - audit_events
- seed выполняется идемпотентно;
- повторный startup не дублирует записи;
- проект не требует ручного SQL или ручного заполнения БД для нормального db-mode QA.

Канонический источник данных:
- брать только `storage/seed/json/*`;
- не создавать второй параллельный seed-source;
- не заводить отдельные hardcoded Python fixtures как источник правды вместо JSON datasets;
- если JSON shape уже не соответствует ORM или product-contract, исправлять именно canonical seed JSON и importer вместе.

Рекомендуемая архитектура решения:
1. Добавить отдельный seeder/importer, например:
   - `src/pitchcopytrade/db/seeders/business.py`
2. Вынести туда полную загрузку dataset-файлов из `settings.storage.seed_json_root`.
3. Вызывать его из `src/pitchcopytrade/api/lifespan.py::_run_seeders()`.
4. Сохранить `seed_admin()` как safety-net bootstrap:
   - он не должен ломать импорт полного dataset;
   - если admin уже приехал из `users.json`, bootstrap должен просто тихо ничего не делать.

Обязательный порядок импорта:
1. `roles`
2. `lead_sources`
3. `users`
4. `authors`
5. `instruments`
6. `author_watchlist_instruments`
7. `strategies`
8. `bundles`
9. `bundle_members`
10. `products`
11. `promo_codes`
12. `legal_documents`
13. `payments`
14. `subscriptions`
15. `user_consents`
16. `messages`
17. `notification_log`
18. `audit_events`

Почему именно так:
- `users` зависят от `roles` и `lead_sources`
- `authors` зависят от `users`
- `strategies` зависят от `authors`
- `bundle_members` зависят от `bundles` и `strategies`
- `products` зависят от `strategies` / `authors` / `bundles`
- `payments` зависят от `users`, `products`, `promo_codes`
- `subscriptions` зависят от `users`, `products`, `payments`, `lead_sources`
- `user_consents` зависят от `users`, `legal_documents`, `payments`
- `messages` зависят от `authors`, `users`, `strategies`, `bundles`
- `notification_log` зависит от `messages` и `users`

Требования к importer-у:
- importer должен быть идемпотентным;
- повторный запуск не должен плодить дубликаты;
- importer должен обновлять существующие записи по их canonical `id`, а не создавать новые;
- many-to-many и association-таблицы должны синхронизироваться по seed dataset, а не только append-иться;
- importer не должен silently skip dataset, если он существует и не пустой;
- importer должен логировать понятный summary:
  - какие datasets обработаны
  - сколько записей inserted/updated/skipped
  - на каком dataset произошла ошибка, если она есть

Семантика идемпотентности:
- для сущностей с явным `id`:
  - upsert по `id`
- для association-table сущностей без своего UUID в dataset:
  - считать canonical identity составным ключом:
    - `bundle_members`: `bundle_id + strategy_id`
    - `author_watchlist_instruments`: `author_id + instrument_id`
- для user roles:
  - `users.role_ids` из seed должны быть source of truth;
  - не достаточно просто append existing roles, нужно синхронизировать набор ролей пользователя с dataset.

Message-specific требования:
- `messages.json` уже canonical source of truth для новой модели `Message`;
- importer должен корректно загрузить:
  - `deliver`
  - `channel`
  - `text`
  - `documents`
  - `deals`
  - `schedule`
  - `published`
  - `archived`
- никакой legacy `recommendation_*` логики в importer-е быть не должно.

Storage/blob требования:
- `documents[].key` в `messages.json` ссылается на blob-storage;
- db seed нельзя считать завершенным, если в БД появились message rows, но связанные документы физически не доступны из storage path;
- используй существующий storage bootstrap contract;
- проверь, что clean reset + runtime storage bootstrap позволяют открыть seeded document blobs без ручного копирования.

Что нельзя делать:
- не создавать второй независимый набор db seed fixtures вне `storage/seed/json`
- не объявлять задачу закрытой только потому, что tests на schema зеленые
- не оставлять importer в состоянии “работает только на пустой БД без повторного запуска”
- не подменять полную задачу фиктивным doc-only обновлением
- не вводить dual source of truth между file-mode graph и db-mode seed logic

Что можно менять:
- `src/pitchcopytrade/api/lifespan.py`
- `src/pitchcopytrade/db/seeders/*`
- `src/pitchcopytrade/repositories/file_graph.py`, если нужен shared parsing helper
- `storage/seed/json/*`, если где-то canonical datasets надо синхронизировать с новой ORM/schema
- `deploy/README.md`
- `doc/README.md`
- тесты, связанные с seed и db startup

Рекомендуемый write scope:
- `src/pitchcopytrade/api/lifespan.py`
- `src/pitchcopytrade/db/seeders/business.py`
- `src/pitchcopytrade/db/seeders/instruments.py`
- `src/pitchcopytrade/db/seeders/admin.py`
- `src/pitchcopytrade/repositories/file_graph.py`
- `storage/seed/json/*.json`
- `tests/test_seeders.py`
- `tests/test_db_models.py`
- `tests/test_deploy_server_files.py`
- при необходимости: новый тест вроде `tests/test_db_seed_importer.py`
- `deploy/README.md`
- `doc/README.md`

Рекомендуемый порядок работы:
1. Зафиксировать importer contract и import order.
2. Реализовать load/parse layer для canonical seed JSON.
3. Реализовать dataset-by-dataset upsert в БД.
4. Подключить importer к `_run_seeders()`.
5. Добавить idempotency tests.
6. Добавить smoke test на “clean reset + startup => business data loaded”.
7. Обновить deploy/local docs.

Минимальные проверки:
1. `./.venv/bin/python -m pytest -q tests/test_seeders.py`
2. `./.venv/bin/python -m pytest -q tests/test_file_repositories.py tests/test_worker_baseline.py`
3. при наличии отдельного importer test:
   - `./.venv/bin/python -m pytest -q tests/test_db_seed_importer.py`

Acceptance criteria:
- `deploy/README.md` больше не вводит в заблуждение по статусу full db seed;
- после clean reset и первого startup db-mode в БД появляется полный business dataset;
- повторный startup не создает дубликаты;
- seeded `messages` с document payload имеют рабочие blob references;
- file-mode и db-mode опираются на один и тот же canonical seed dataset;
- worker report включает:
  - какие datasets реально импортируются
  - import order
  - как обеспечена идемпотентность
  - какие тесты добавлены и пройдены
```

#### L6. Full Regression Gate After Reset And Seed

Цель:
- после L1-L5 получить репозиторий, который можно полноценно проверять в db-mode и file-mode.

Что сделать:
- прогнать максимально широкий regression suite после clean reset и seed load;
- устранить оставшиеся mismatches в тестах, fixtures и runtime metadata;
- отдельно закрыть test isolation issue в `/metadata`, где `storage_root` протекает между тестами.

Файлы в scope:
- `tests/test_health.py`
- `tests/test_admin_ui.py`
- `tests/test_author_services.py`
- `tests/test_author_ui.py`
- `tests/test_moderation_ui.py`
- `tests/test_notifications_service.py`
- `tests/test_access_delivery.py`
- `tests/test_subscriber_reminders.py`
- `tests/test_worker_baseline.py`
- `tests/test_public_catalog_checkout.py`
- `tests/test_payment_sync.py`
- и другие test files, которые падают после L1-L5

Финальный regression gate:
1. `./.venv/bin/python -m pytest -q`
2. если suite слишком тяжелый для одной итерации, сначала:
   - `tests/test_admin_ui.py`
   - `tests/test_author_services.py`
   - `tests/test_author_ui.py`
   - `tests/test_moderation_ui.py`
   - `tests/test_notifications_service.py`
   - `tests/test_access_delivery.py`
   - `tests/test_public_catalog_checkout.py`
   - `tests/test_payment_sync.py`
   - `tests/test_health.py`
   - `tests/test_worker_baseline.py`

Критерии приемки:
- полный suite проходит или остается только заранее задокументированный узкий residual risk;
- db-mode после clean reset и seed пригоден для ручного UI smoke;
- можно безопасно делать все виды тестов без ручных SQL hotfix и без ручного создания данных.

### M. Screen-Driven Message Composer

Цель блока:
- полностью переделать текущую форму подачи сообщения под экран-референс;
- убрать зависимость от старой recommendation/leg формы;
- оставить один понятный author workflow, где одно итоговое сообщение собирается из 3 независимых секций.

Статус блока:
- unified composer и history-centric author screen реализованы
- preview перед отправкой реализован
- mobile/tablet split между history и compose реализован
- post-implementation review выявил 2 обязательных follow-up фикса:
  - structured deal edit round-trip
  - existing document-only edit/preview path
- требование “вынести стили в общий theme CSS” пока не подтверждено: текущая реализация все еще содержит локальные style-блоки в author templates

Основной UX-принцип:
- это не 3 разных режима отправки и не 3 отдельных submit-flow;
- это один composer, в котором одновременно доступны 3 необязательные секции:
  - неструктурированный текст;
  - документы и изображения;
  - структурированная рекомендация покупки/продажи инструмента;
- текущую форму можно переделать полностью;
- отдельная legacy Form 1 не нужна;
- итоговое сообщение собирается из заполненных секций в фиксированном порядке;
- кнопка отправки одна, расположена по центру;
- перед отправкой всегда открывается preview окна/панели.

Источник визуального направления:
- screen из файла `/Users/alexey/Downloads/photo_2026-03-27 13.36.07.jpeg`
- только 1 кнопка отправки сообщения по центру
- из всех 3-х частей собирается одно итоговое сообщение
- базовый стиль брать из текущей темы приложения, но реализовывать через общий theme CSS файл, без отдельной локальной “мини-темы” только для author screen.

Порядок сборки итогового сообщения:
1. Сначала идет неструктурированный текстовый блок.
2. Затем идет блок структурированных рекомендаций о покупке/продаже инструментов.
3. Документы и изображения прикрепляются к сообщению и отображаются после текстового и structured блока.

Layout requirements:
- desktop:
  - сверху показывается история сообщений в виде таблицы или явно табличного списка;
  - новая форма подачи находится снизу экрана;
  - composer имеет больший `z-index` и визуально накрывает нижнюю часть экрана;
  - таблица истории сообщений остается прокручиваемой в оставшемся viewport-height;
  - таблица должна иметь узкий, плотный дизайн без лишних крупных карточек;
- mobile/tablet:
  - layout не должен ломаться;
  - секции composer идут строго друг под другом:
    - неструктурированный текст
    - документы
    - структурированная рекомендация
  - таблица истории и форма подачи разнесены на 2 отдельных экрана/состояния;
  - на compose screen таблица не показывается;
- все 3 секции всегда видимы и доступны одновременно;
- пользователь не выбирает “один из трех режимов”.

Требования к истории сообщений:
- это таблица `messages`, а не карточечная gallery;
- строки компактные и пригодные для работы с большим количеством записей;
- поле с текстом должно быть сокращенным;
- полный текст должен открываться либо:
  - через `title`/tooltip при hover;
  - либо через row preview / drawer по клику;
- worker может выбрать любой из этих вариантов, но должен использовать один понятный и единый паттерн для всей таблицы.

Требования к instrument picker:
- input выбора инструмента должен открывать popup/dropdown со списком доступных инструментов;
- в каждой строке списка должны быть видны:
  - ticker
  - человекочитаемое название инструмента
  - `lp` / `lastprice`, если значение доступно
- picker должен поддерживать быстрый поиск по ticker и названию.

Validation proposal:
- сообщение можно отправить только если заполнена хотя бы одна из трех секций:
  - есть непустой текст;
  - есть хотя бы один документ/файл;
  - есть валидная structured recommendation;
- structured recommendation считается валидной, если заполнены:
  - инструмент
  - `buy` или `sell`
  - цена
  - количество
- сумма считается на клиенте для UX, но backend всегда пересчитывает ее сам;
- загрузка документов разрешена только для `jpg`, `jpeg`, `pdf`;
- preview не должен открываться для полностью пустой формы;
- backend должен финально валидировать assembled payload, даже если client-side validation пропустила ошибку.

Рекомендуемые решения по реализации:
- text хранить в HTML-first contract:
  - `format`
  - `body`
  - `plain`
- structured recommendation хранить в `deals[]`, минимум с:
  - `instrument`
  - `ticker`
  - `name`
  - `side`
  - `price`
  - `quantity`
  - `amount`
- documents хранить только в canonical new shape:
  - `id`
  - `name`
  - `title`
  - `type`
  - `size`
  - `storage`
  - `key`
  - `hash`
- preview лучше делать как modal/drawer над composer, а не как второй submit;
- для desktop таблицы рекомендован pattern:
  - compact table
  - truncated text cell
  - hover tooltip для короткого просмотра
  - row click открывает full preview/detail.

Подтвержденные решения owner-а:
1. На первом этапе одно сообщение поддерживает ровно одну structured recommendation, но `deals` в DB и payload сразу остается массивом `JSONB array` для будущего расширения до нескольких рекомендаций.
2. Документы и изображения всегда рендерятся в конце итогового сообщения.
3. Обязательный заголовок сообщения в UI не нужен.
4. На mobile/tablet history и compose делаются как отдельные экраны/состояния, а не как tabs внутри одного экрана.
5. Разрешена отправка сообщения, состоящего только из документов, даже без текста и без structured блока, если есть хотя бы один валидный файл.

Статус:
- [x] M1 выполнен
- [x] M2 выполнен
- [x] M3 выполнен
- [x] Проверка прошла: `./.venv/bin/python -m pytest -q tests/test_author_services.py tests/test_author_ui.py tests/test_moderation_ui.py tests/test_messages.py` -> `22 passed`

#### M1. Worker Prompt — New Author Message Composer

```text
Ты делаешь отдельную задачу по полной переделке author message composer под screen-driven UX.

Важное допущение:
- текущую форму можно переделать полностью;
- не нужно сохранять старый layout;
- система уже работает на сущности `Message`;
- весь composer должен писать только в `messages`, без legacy `recommendations`.

Цель:
- сделать новый author screen, в котором автор собирает одно итоговое сообщение из 3 независимых секций:
  1. неструктурированный текст;
  2. документы/изображения;
  3. структурированная рекомендация покупки/продажи инструмента;
- все 3 секции всегда доступны одновременно;
- они необязательны по отдельности;
- сообщение можно отправить, если заполнена хотя бы одна секция;
- отдельного выбора “режима” в UI быть не должно.

Базовый UX-контракт:
- вся работа ведется в одном экране;
- история всех сообщений показывается в виде таблицы или явно табличного списка;
- composer должен быть визуально разделен на 3 понятные секции в духе screen reference;
- на desktop:
  - история сообщений находится сверху;
  - composer находится снизу экрана;
  - composer имеет больший `z-index` и визуально перекрывает нижнюю часть history area;
  - history остается прокручиваемой в доступной высоте;
- на mobile/tablet:
  - history screen и compose screen разделены;
  - на compose screen секции идут вертикально друг под другом:
    - текст
    - документы
    - structured recommendation;
- использовать общий theme CSS приложения;
- текущий стиль приложения взять как baseline и развить его, а не заводить локальный CSS-остров только для author form.

Что именно должен уметь экран:

1. Неструктурированная секция
- большое поле текста;
- поддержка HTML-first payload;
- текст, если заполнен, всегда идет первым блоком итогового сообщения.

2. Документная секция
- загрузка только `jpg/jpeg` и `pdf`;
- список прикрепленных файлов;
- возможность удалить файл до preview;
- опциональная подпись/описание к документам через общий текстовый блок или отдельное краткое поле, если это упростит UX;
- документы прикрепляются к сообщению и отображаются после text и structured блока.

3. Structured recommendation секция
- обязательные поля:
  - выбран инструмент
  - цена
  - количество
  - действие `buy/sell`
- отображаемая сумма должна считаться автоматически на клиенте;
- сумма должна считаться автоматически на клиенте как `price * quantity`;
- backend не должен доверять client-side amount и обязан пересчитать сумму сам;
- structured section, если заполнена, всегда идет после неструктурированного текста.

Как собирается итоговый `Message`:
- submit всегда один;
- кнопка submit одна и расположена по центру;
- перед финальной отправкой всегда открывается preview;
- preview показывает итоговое assembled message в точном порядке:
  1. неструктурированный текст;
  2. structured recommendation;
  3. документы и изображения;
- после подтверждения preview создается или обновляется один `Message`;
- не должно быть отдельных submit-кнопок для text/document/deal частей.

Какой payload должен писаться:
- если заполнен текст, писать `text.body` и `text.plain`;
- если есть файлы, писать `documents[]` только в canonical new shape;
- если заполнена structured recommendation, писать ровно один элемент в `deals[]`;
- `deals[]` остается массивом и в контракте, и в БД, несмотря на то что на первом этапе UI поддерживает только одну structured recommendation;
- поле `type` можно выставлять как:
  - `text`, если заполнен только текст;
  - `document`, если заполнены только документы;
  - `deal`, если заполнен только structured block;
  - `mixed`, если одновременно заполнены 2 или 3 секции.

Structured deal minimum contract:
- `instrument`
- `ticker`
- `name`
- `side`
- `price`
- `quantity`
- `amount`

Допустимое расширение deal contract:
- `board`
- `currency`
- `lot`
- `from`
- `to`
- `stop`
- `targets`
- `period`
- `note`
- `status`
- `opened`
- `closed`
- `result`

Document contract:
- не использовать legacy attachment shape;
- `documents[]` должны писаться только в новом формате:
  - `id`
  - `name`
  - `title`
  - `type`
  - `size`
  - `storage`
  - `key`
  - `hash`

Text contract:
- хранить HTML-first payload:
  - `format`
  - `body`
  - `plain`
- backend обязан санитайзить HTML;
- backend обязан строить `plain` из `body`.

История сообщений:
- вместо старой recommendation-oriented presentation нужна единая таблица сообщений;
- таблица должна быть пригодна для реальной работы, не просто как декоративный список;
- в таблице минимум должны быть:
  - дата/время
  - тип сообщения
  - заголовок или превью
  - стратегия
  - статус
  - каналы доставки
  - действия
- действия минимум:
  - открыть
  - редактировать, если статус позволяет
  - preview
- если запись содержит документ, в строке должно быть видно, что документ есть;
- если запись содержит сделку, в строке должно быть видно краткое summary сделки.
- колонка с текстом должна быть короткой и обрезанной;
- полный текст нужно показывать через `title`/tooltip или через отдельный compact preview interaction;
- worker должен выбрать один способ и применить его последовательно.

Поведение формы:
- пользователь выбирает или открывает стратегию;
- все 3 секции всегда доступны;
- пользователь не выбирает режим;
- hidden/legacy form fields вроде `summary`, `thesis`, `market_context`, `leg_*` не должны оставаться частью рабочего UI-контракта;
- preview строится из реальных visible UI полей;
- instrument input должен раскрывать список доступных инструментов с ticker, названием и `lp`/`lastprice`, если цена доступна.

Validation rules:
- preview и submit запрещены для полностью пустой формы;
- structured block валиден, если есть:
  - `instrument`
  - `side`
  - `price`
  - `quantity`
- `amount` всегда пересчитывается backend-ом;
- document block валиден, если есть хотя бы один файл допустимого типа;
- допустимые файлы: JPG/JPEG/PDF;
- HTML должен проходить sanitize;
- если `deliver` содержит `strategy`, нужна стратегия;
- если `status = scheduled`, нужен `schedule`.

Дизайн-направление:
- ориентироваться на приложенный screen, а не на текущую реализацию;
- больше светлых поверхностей, мягких синих action-элементов и явного разделения блоков;
- не делать “серую админку по умолчанию”;
- submit-кнопка одна, центральная;
- worker сам придумывает отступы, плотность, визуальные акценты и оформление structured recommendation блока;
- история сообщений должна быть визуально центральным рабочим элементом, а не второстепенным блоком.

Что можно менять:
- текущий `author/message_form.html` можно переписать полностью;
- routes и form parsing можно упростить под новый UX;
- service layer можно чистить от legacy fields, если это нужно для новой формы;
- можно переименовать helper functions под `messages`, если это улучшает читаемость.

Что нельзя делать:
- не возвращать старый `leg_*` workflow как source of truth;
- не писать новые данные в старый attachment shape;
- не оставлять два конкурирующих form contract;
- не делать fallback “structured UI -> legacy leg parser”;
- не использовать client-calculated amount как truth.

Ownership / write scope:
- `src/pitchcopytrade/api/routes/author.py`
- `src/pitchcopytrade/services/author.py`
- `src/pitchcopytrade/web/templates/author/message_form.html`
- `src/pitchcopytrade/web/templates/author/messages_list.html`
- `src/pitchcopytrade/web/templates/author/dashboard.html`
- `src/pitchcopytrade/web/templates/app/message_detail.html`
- `src/pitchcopytrade/web/templates/moderation/detail.html`
- `src/pitchcopytrade/bot/main.py`
- `tests/test_author_services.py`
- `tests/test_author_ui.py`
- `tests/test_messages.py`

Рекомендуемый порядок работы:
1. Зафиксировать final assembled-message contract.
2. Упростить backend parsing под один общий submit и preview.
3. Переделать template/layout под desktop overlay и mobile split-screen behavior.
4. Обновить detail/history rendering под новый payload.
5. Добавить tests на text-only, documents-only, structured-only и mixed submit.

Минимальные тесты:
- text-only message create
- documents-only message create
- structured-only message create
- mixed message create from text + structured + documents
- structured section rejects preview/submit without instrument
- structured section rejects preview/submit without side
- structured section rejects preview/submit without price
- structured section rejects preview/submit without quantity
- backend recalculates amount even if client sent a different value
- author edit page correctly renders new-format documents
- author edit page correctly renders new-format deals
- instrument picker renders ticker + name + `lp`/`lastprice`, if available
- mobile layout keeps sections stacked and history separated from compose screen

Acceptance criteria:
- текущая форма полностью заменена новым unified composer;
- автор может отправить одно сообщение, собранное из любой комбинации 3 секций;
- structured section реально работает от visible UI полей, а не через hidden legacy `leg_*`;
- история сообщений ведется через таблицу сообщений;
- desktop layout соответствует screen-driven overlay behavior;
- mobile/tablet layout не ломается и разносит history и compose;
- preview обязателен перед отправкой;
- payload в `messages` соответствует canonical `text/documents/deals` contract;
- worker report включает список измененных файлов и тесты.
```

---

## Блок P5 — Composer: 3-колоночный layout по дизайну (2026-03-28)

### Контекст

Текущая реализация `message_form.html` — вертикальный layout: блоки 1 (текст), 2 (документы), 3 (structured deal) расположены **сверху вниз**. По утверждённому дизайну (см. image) они должны быть **слева направо в 3 колонки** на desktop. Сверху — таблица сообщений (history). Снизу — форма подачи из 3 равных блоков-карточек.

### Дизайн (из image)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Опубликовать рекомендацию]  [История рекомендаций]  [Опубл. сделку]  │  ← навигация / вкладки
├─────────────────────────────────────────────────────────────────────────┤
│                        ТАБЛИЦА СООБЩЕНИЙ (history)                     │
│  Все ранее созданные сообщения автора — компактная таблица              │
├─────────────────────┬─────────────────────┬─────────────────────────────┤
│  БЛОК 1: ТЕКСТ      │  БЛОК 2: OnePager   │  БЛОК 3: СДЕЛКА            │
│                     │                     │                             │
│  textarea (8 строк) │  preview image      │  «Наименование ц. бумаги»  │
│  свободный текст    │  «Рекомендация от   │  ┌────────┐  ┌────────┐    │
│  рекомендации       │   ДД.ММ.ГГ»         │  │ цена   │  │ кол-во │    │
│                     │                     │  └────────┘  └────────┘    │
│                     │  OnePager.jpg  [+]  │  ┌────────┐  ┌────────┐    │
│                     │                     │  │ цена   │  │ Сумма  │    │
│                     │  (file upload)      │  └────────┘  └────────┘    │
│                     │                     │                             │
│  [Отправить]        │  [Отправить]        │  [Купить]    [Продать]      │
└─────────────────────┴─────────────────────┴─────────────────────────────┘
```

### Приоритет

**P5.1 → P5.2 → P5.3 → P5.4**

---

### P5.1 — CSS: 3-колоночный layout composer блоков

**Текущее состояние:** `.author-editor-block` — vertical stack (`display: grid; gap: 14px`), каждый блок на всю ширину.

**Целевое состояние:** 3 блока в одну строку (desktop), стек на mobile.

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html` — секция `<style>`

**Что должен сделать worker:**

- [x] **P5.1.1** Обернуть 3 секции `.author-editor-block` в контейнер `.author-editor-blocks-row`:
  ```html
  <div class="author-editor-blocks-row">
    <section class="author-editor-block"> <!-- 1. text --> </section>
    <section class="author-editor-block"> <!-- 2. documents --> </section>
    <section class="author-editor-block"> <!-- 3. structured --> </section>
  </div>
  ```

- [x] **P5.1.2** CSS для 3-колоночного layout:
  ```css
  .author-editor-blocks-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 18px;
    margin-top: 18px;
  }
  .author-editor-blocks-row .author-editor-block {
    margin-top: 0;
    padding-top: 0;
    border-top: none;
    border: 1px solid rgba(12, 20, 46, 0.10);
    border-radius: 18px;
    padding: 18px;
    background: #fff;
  }
  @media (max-width: 1024px) {
    .author-editor-blocks-row {
      grid-template-columns: 1fr;
    }
  }
  ```

- [x] **P5.1.3** Убрать `position: sticky` и `box-shadow` у `.author-editor-composer` — composer больше не «плавает» внизу, а занимает нормальное место в потоке (history сверху, composer снизу, как на дизайне).

- [x] **P5.1.4** `python3 -m compileall src tests`

---

### P5.2 — Блоки: заголовки и кнопки действий по дизайну

**Дизайн каждого блока:**

Блок 1 (текст):
- Заголовок: «Опубликовать рекомендацию в Telegram Bot»
- Содержимое: textarea (свободный текст)
- Кнопка внизу: «Отправить» (primary)

Блок 2 (OnePager / документы):
- Заголовок: «Опубликовать OnePager как рекомендацию»
- Содержимое: preview изображения (если есть) + file upload + подпись
- Кнопка внизу: «Отправить» (primary)

Блок 3 (structured deal / сделка):
- Заголовок: «Опубликовать сделку по рекомендации в Telegram Bot»
- Содержимое: наименование ценной бумаги (instrument picker), цена, количество, сумма (auto-calc)
- Кнопки внизу: «Купить» (green, primary) + «Продать» (red, danger)

**Что должен сделать worker:**

- [x] **P5.2.1** Изменить eyebrow / h3 в каждом блоке:
  - Блок 1: eyebrow = удалить, h3 = «Опубликовать рекомендацию в Telegram Bot»
  - Блок 2: eyebrow = удалить, h3 = «Опубликовать OnePager как рекомендацию»
  - Блок 3: eyebrow = удалить, h3 = «Опубликовать сделку по рекомендации в Telegram Bot»

- [x] **P5.2.2** Каждый блок получает свою кнопку submit внизу:
  - Блок 1: `<button type="submit" name="publish_block" value="text" class="action author-block-submit">Отправить</button>`
  - Блок 2: `<button type="submit" name="publish_block" value="document" class="action author-block-submit">Отправить</button>`
  - Блок 3: две кнопки:
    - `<button type="submit" name="publish_block" value="deal_buy" class="action author-block-submit is-buy">Купить</button>`
    - `<button type="submit" name="publish_block" value="deal_sell" class="action author-block-submit is-sell">Продать</button>`

- [x] **P5.2.3** CSS для кнопок блоков:
  ```css
  .author-block-submit {
    width: 100%;
    justify-content: center;
    margin-top: auto; /* прижать к низу блока */
    border-radius: 12px;
    padding: 12px;
    font-weight: 700;
  }
  .author-block-submit.is-buy {
    background: #22c55e;
    color: #fff;
  }
  .author-block-submit.is-sell {
    background: #ef4444;
    color: #fff;
  }
  ```

- [x] **P5.2.4** Блок 3: поля structured deal — grid 2x2:
  ```css
  .author-editor-structured-grid {
    grid-template-columns: 1fr 1fr; /* вместо текущего 2.1fr 1fr 1fr 1fr */
  }
  ```
  Порядок: Наименование (full width), Цена + Количество (row), Цена + Сумма (row).

- [x] **P5.2.5** Блок 3: instrument picker — текстовое поле «Наименование ценной бумаги» (full width в блоке, без modal picker button), так как на дизайне это простое текстовое поле с label.

- [x] **P5.2.6** `python3 -m compileall src tests`

---

### P5.3 — Навигация / вкладки сверху

**Дизайн:** 3 кнопки-вкладки над таблицей:
- «Опубликовать рекомендацию в Telegram Bot»
- «История рекомендаций»
- «Опубликовать сделку по рекомендации в Telegram Bot»

**Поведение:** Кнопки — anchor-ссылки к соответствующим блокам (scroll to section). Не переключатели вкладок. Все 3 блока всегда видны.

**Что должен сделать worker:**

- [x] **P5.3.1** Добавить навигацию-ленту над history table:
  ```html
  <nav class="author-editor-nav">
    <a href="#block-text" class="author-nav-tab">Опубликовать рекомендацию в Telegram Bot</a>
    <a href="#block-history" class="author-nav-tab is-active">История рекомендаций</a>
    <a href="#block-deal" class="author-nav-tab">Опубликовать сделку по рекомендации в Telegram Bot</a>
  </nav>
  ```

- [x] **P5.3.2** CSS: `.author-editor-nav { display: flex; gap: 8px; padding: 12px 0; }` + `.author-nav-tab { padding: 10px 18px; border-radius: 12px; background: #e8ecf2; font-weight: 600; text-decoration: none; color: inherit; }` + `.author-nav-tab.is-active { background: var(--staff-primary); color: #fff; }`

- [x] **P5.3.3** Добавить `id="block-text"`, `id="block-documents"`, `id="block-deal"` на соответствующие секции + `id="block-history"` на history table.

- [x] **P5.3.4** `python3 -m compileall src tests`

---

### P5.4 — Убрать лишние элементы composer

**По дизайну отсутствуют:**
- Секция «publishing» (статус и расписание) — отдельная от 3 блоков
- Общая кнопка «Предпросмотр и отправка» — каждый блок имеет свою кнопку
- eyebrow «screen-driven message composer» — удалить developer-facing текст
- hero-секция с «Один экран для текста, документов и structured deal» — упростить
- Meta-grid (Стратегия, Класс, Статус, Заголовок) — переместить НАД 3-блоками как общие поля формы

**Что должен сделать worker:**

- [x] **P5.4.1** Убрать `position: sticky`, `box-shadow`, `z-index: 4` с `.author-editor-composer`
- [x] **P5.4.2** Упростить hero: убрать developer eyebrow и технические описания, оставить только заголовок страницы + pills
- [x] **P5.4.3** Meta-grid (Стратегия, Класс сообщения, Статус, Заголовок) — разместить над `.author-editor-blocks-row`
- [x] **P5.4.4** Удалить секцию «publishing» (scheduling) или свернуть в meta-grid
- [x] **P5.4.5** Удалить общую кнопку «Предпросмотр и отправка» — публикация через кнопки в каждом блоке
- [x] **P5.4.6** `python3 -m compileall src tests`

Статус:
- [x] P5 выполнен

---

### Acceptance P5 (общий)

1. Desktop: history table сверху, 3 блока-карточки в одну строку снизу
2. Каждый блок — независимая карточка с заголовком и своей кнопкой submit
3. Блок 1: textarea + «Отправить»
4. Блок 2: preview image + file upload + «Отправить»
5. Блок 3: instrument + цена + кол-во + сумма + «Купить» / «Продать»
6. Навигация-лента сверху (3 кнопки)
7. Mobile: блоки стакуются вертикально
8. Нет developer-facing eyebrow текстов
9. Meta-поля (стратегия, класс, статус) — общие, над блоками

---

## Блок P6 — Русские статусы: подключить `_label()` во всех сериализаторах (2026-03-28)

### Контекст

После review P4: функция `_label()` и словарь `_STATUS_LABELS` были созданы в `_grid_serializers.py` (строки 31-50), но применены только в 3 из 12 сериализаторов. В остальных 6 статусы по-прежнему выводятся на английском (DRAFT, ACTIVE, PUBLISHED, BUY и т.д.).

### Приоритет

Одна задача, один файл, 8 правок. Блокирует русскоязычный UI.

---

### P6.1 — Применить `_label()` в 6 сериализаторах + risk labels

**Файл:** `src/pitchcopytrade/api/routes/_grid_serializers.py`

**Правило:** каждый `_badge(status_val, ...)` и `_badge(risk_val, ...)` должен быть обёрнут: `_badge(_label(status_val), ...)`. Также side-метки BUY/SELL → Покупка/Продажа.

**Что должен сделать worker — точные замены:**

- [x] **P6.1.1** `serialize_strategies()` — строка 66-67:
  ```python
  # БЫЛО:
  "risk": _badge(risk_val, risk_class),
  "status": _badge(status_val, status_class),
  # СТАЛО:
  "risk": _badge(_label(risk_val), risk_class),
  "status": _badge(_label(status_val), status_class),
  ```

- [x] **P6.1.2** `serialize_subscriptions()` — строка 229:
  ```python
  # БЫЛО:
  "status": _badge(status_val, status_class),
  # СТАЛО:
  "status": _badge(_label(status_val), status_class),
  ```

- [x] **P6.1.3** `serialize_payments()` — строка 256:
  ```python
  # БЫЛО:
  "status": _badge(status_val, status_class),
  # СТАЛО:
  "status": _badge(_label(status_val), status_class),
  ```

- [x] **P6.1.4** `serialize_recommendations()` — строка 391:
  ```python
  # БЫЛО:
  "status": _badge(status_val, status_class),
  # СТАЛО:
  "status": _badge(_label(status_val), status_class),
  ```

- [x] **P6.1.5** `serialize_author_strategies()` — строки 410-411:
  ```python
  # БЫЛО:
  "risk": _badge(risk_val, risk_class),
  "status": _badge(status_val, status_class),
  # СТАЛО:
  "risk": _badge(_label(risk_val), risk_class),
  "status": _badge(_label(status_val), status_class),
  ```

- [x] **P6.1.6** `serialize_moderation_queue()` — строки 442, 444:
  ```python
  # БЫЛО:
  "kind": _badge(kind_val, kind_class),
  "status": _badge(status_val, status_class),
  # СТАЛО:
  "kind": _badge(_label(kind_val), kind_class),
  "status": _badge(_label(status_val), status_class),
  ```

- [x] **P6.1.7** Добавить в `_STATUS_LABELS` недостающие ключи (если отсутствуют):
  ```python
  "LOW": "Низкий", "MEDIUM": "Средний", "HIGH": "Высокий",        # risk levels
  "CONFIRMED": "Оплачен", "CREATED": "Создан",                      # payment statuses
  "IDEA": "Идея", "UPDATE": "Обновление", "CLOSE": "Закрытие",     # message kinds
  "CANCEL": "Отмена", "NOTE": "Заметка",
  "TEXT": "Текст", "DOCUMENT": "Документ", "MIXED": "Смешанный",   # message types
  "DEALS": "Сделки",
  ```

- [x] **P6.1.8** В `serialize_recommendations()` — строка 388, перевести message_type:
  ```python
  # БЫЛО:
  "type": _badge(message_type, message_type_class),
  # СТАЛО:
  "type": _badge(_label(message_type), message_type_class),
  ```

- [x] **P6.1.9** `python3 -m compileall src tests` — без ошибок

Статус:
- [x] P6 выполнен

---

### Проверка после выполнения

Worker должен запустить grep и убедиться что НЕ осталось `_badge(` вызовов с `_val` аргументом БЕЗ `_label()`:

```bash
grep -n '_badge(' src/pitchcopytrade/api/routes/_grid_serializers.py | grep -v '_label'
```

**Допустимые исключения** (hardcoded русский текст, не нужен `_label()`):
- `_badge("Активен" ...` — строки 200, 279, 304
- `_badge("Неактивен" ...` — строки 200, 304
- `_badge("Черновик" ...` — строка 279
- `_badge("Да" ...` / `_badge("Нет" ...`

Все остальные `_badge(some_var, ...)` ДОЛЖНЫ быть обёрнуты в `_label()`.

---

### Acceptance P6

1. `grep -n '_badge(' _grid_serializers.py | grep -v '_label' | grep -v '"Актив' | grep -v '"Неактив' | grep -v '"Черновик' | grep -v '"Да"' | grep -v '"Нет"' | grep -v '"Отправлено"' | grep -v '"Ошибка"'` → пустой результат
2. Все grid-ы показывают русские статусы: Черновик, Опубликовано, Активен, Приглашён, Оплачен, Низкий/Средний/Высокий
3. Направление сделки: Покупка / Продажа (не BUY / SELL)
4. `python3 -m compileall src tests` — без ошибок

---

## Блок P7 — Компактный composer + единая кнопка + fix instrument picker (2026-03-28)

### Контекст

Форма composer (message_form.html) работает, 3-колоночный layout на месте. Пользователь тестировал на production и выявил 3 проблемы:

1. **Слишком крупные элементы** — много пустого места, padding, отступы. Composer — рабочий инструмент, не лендинг. Нужна максимальная компактность.
2. **Кнопка «Отправить» должна быть ОДНА** на все 3 блока, а не по кнопке в каждом блоке. Текущие кнопки «Отправить» + «Купить»/«Продать» в каждом блоке — убрать. Одна общая кнопка submit под 3 блоками.
3. **Instrument picker не работает** — при клике на поле «Наименование ценной бумаги» фильтр в modal не фильтрует, выбор инструмента не происходит. Цены акций не отображаются.

### Приоритет

**P7.1 → P7.2 → P7.3** — все три обязательны.

---

### P7.1 — Компактный UI: уменьшить padding, отступы, шрифты

**Текущее состояние:** Элементы формы имеют:
- `padding: 26px 28px` (hero)
- `padding: 22px` (composer, history)
- `padding: 18px` (blocks)
- `padding: 14px 16px` (inputs)
- `border-radius: 16px` (inputs), `18px` (blocks), `22px` (summary card)
- `gap: 18px` (blocks-row), `14px` (inner grids)
- `rows="8"` textarea, `rows="3"` deal note

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html` — секция `<style>`

**Что должен сделать worker — точные изменения в CSS:**

- [x] **P7.1.1** Hero секция — компактнее:
  ```css
  .author-editor-hero { padding: 12px 16px; }
  .author-editor-hero h1 { font-size: 1.1rem; margin: 0; }
  .author-editor-hero p { font-size: 0.82rem; margin: 2px 0 0; }
  ```

- [x] **P7.1.2** History и Composer — компактнее:
  ```css
  .author-editor-history, .author-editor-composer { padding: 12px; }
  .author-editor-history { max-height: min(50vh, 500px); }
  ```

- [x] **P7.1.3** History table — компактнее:
  ```css
  .author-history-table th, .author-history-table td { padding: 6px 8px; }
  .author-history-table { font-size: 0.85rem; }
  ```

- [x] **P7.1.4** Blocks row и blocks — компактнее:
  ```css
  .author-editor-blocks-row { gap: 10px; margin-top: 10px; }
  .author-editor-block { padding: 12px; border-radius: 12px; gap: 8px; }
  ```

- [x] **P7.1.5** Inputs — компактнее:
  ```css
  .author-editor-field input,
  .author-editor-field select,
  .author-editor-field textarea {
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 0.9rem;
  }
  ```

- [x] **P7.1.6** Meta grid — компактнее:
  ```css
  .author-editor-meta-grid { gap: 8px; }
  .author-editor-structured-grid { gap: 8px; }
  ```

- [x] **P7.1.7** Section heads — компактнее:
  ```css
  .author-editor-section-head h2, .author-editor-section-head h3 { font-size: 0.95rem; margin: 0; }
  .author-editor-section-head p { font-size: 0.78rem; margin: 2px 0 0; }
  .eyebrow { font-size: 0.7rem; }
  ```

- [x] **P7.1.8** Textarea rows — уменьшить:
  - В HTML: `rows="8"` → `rows="4"` для текста сообщения
  - В HTML: `rows="4"` → `rows="2"` для подписи к документам
  - В HTML: `rows="3"` → `rows="2"` для примечания к сделке

- [x] **P7.1.9** Navigation tabs — компактнее:
  ```css
  .author-nav-tab { padding: 6px 12px; font-size: 0.82rem; border-radius: 8px; }
  .author-editor-nav { gap: 6px; padding: 8px 0; }
  ```

- [x] **P7.1.10** Field titles — компактнее:
  ```css
  .author-editor-field-title { font-size: 0.75rem; }
  .author-editor-field { gap: 4px; }
  ```

- [x] **P7.1.11** Pills — компактнее:
  ```css
  .pill { font-size: 0.72rem; padding: 3px 8px; }
  ```

---

### P7.2 — Одна кнопка submit на все 3 блока

**Текущее состояние:** Каждый блок имеет свою кнопку:
- Блок 1: `<button name="publish_block" value="text">Отправить</button>`
- Блок 2: `<button name="publish_block" value="document">Отправить</button>`
- Блок 3: `<button name="publish_block" value="deal_buy">Купить</button>` + `<button name="publish_block" value="deal_sell">Продать</button>`

**Целевое состояние:** Одна кнопка submit ПОСЛЕ `.author-editor-blocks-row`, перед footer:

```html
<section class="author-editor-submit-section">
  <button class="action author-editor-submit" type="submit">Отправить сообщение</button>
</section>
```

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

**Что должен сделать worker:**

- [x] **P7.2.1** УДАЛИТЬ из каждого блока кнопки submit:
  - Блок 1: удалить `<button type="submit" name="publish_block" value="text" ...>Отправить</button>`
  - Блок 2: удалить `<button type="submit" name="publish_block" value="document" ...>Отправить</button>`
  - Блок 3: удалить оба `<button type="submit" name="publish_block" ...>` (Купить и Продать)
  - Удалить контейнеры `.author-editor-structured-actions` если пустые

- [x] **P7.2.2** ПОСЛЕ закрывающего `</div>` для `.author-editor-blocks-row` и ПЕРЕД `.author-editor-footer` добавить:
  ```html
  <section class="author-editor-submit-section">
    <button class="action author-editor-submit" type="submit">Отправить сообщение</button>
  </section>
  ```

- [x] **P7.2.3** CSS для единой кнопки:
  ```css
  .author-editor-submit-section {
    display: flex;
    justify-content: center;
    margin-top: 12px;
  }
  .author-editor-submit {
    min-width: min(100%, 320px);
    justify-content: center;
    padding: 10px 24px;
    font-weight: 700;
    border-radius: 10px;
  }
  ```

- [x] **P7.2.4** Удалить CSS для `.author-block-submit`, `.is-buy`, `.is-sell` — они больше не нужны.

---

### P7.3 — Inline autocomplete инструмента (вместо modal dialog)

**Текущее состояние:** При клике на поле «Наименование ценной бумаги» JS вызывает `pickerModal.showModal()` — открывается отдельный `<dialog>` на весь экран с поиском. Это громоздко и ломается из-за focus loop (`focus` → `showModal()` → input теряет focus).

**Целевое состояние:** Inline autocomplete dropdown прямо под полем ввода. При наборе текста — появляется popup с 3-5 подходящими вариантами. По мере набора список сужается. Клик по варианту — заполняет поле.

**Эталон для реализации:** Тикер-попап работал в старом `recommendations_list.html` — `position: fixed` popup, JS фильтрация `instruments` массива, позиционирование через `getBoundingClientRect()`.

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

**Что должен сделать worker:**

- [x] **P7.3.1** УДАЛИТЬ `<dialog class="author-picker-modal" data-picker-modal>` целиком (строки 304-340). Modal больше не нужен.

- [x] **P7.3.2** УДАЛИТЬ JS код привязанный к modal:
  - Удалить: `instrumentInput.addEventListener("focus", openPicker)` и `instrumentInput.addEventListener("click", openPicker)` (строки 877-878)
  - Удалить: `closePickerButton` listener (строки 866-870)
  - Удалить: `pickerSearch.addEventListener("input", ...)` (строки 881-893)
  - Удалить: `pickerItems.forEach(...)` для click selection (строки 895-907)
  - Удалить переменные: `pickerModal`, `closePickerButton`, `pickerSearch`, `pickerItems`

- [x] **P7.3.3** ДОБАВИТЬ inline popup HTML прямо после input `data-instrument-input`:
  ```html
  <div class="author-editor-field author-editor-field--wide">
    <span class="author-editor-field-title">Наименование ценной бумаги</span>
    <div class="author-instrument-picker">
      <input
        type="text"
        name="structured_instrument_query"
        value="..."
        placeholder="Начните вводить ticker или название"
        autocomplete="off"
        data-instrument-input
      />
      <input type="hidden" name="structured_instrument_id" value="..." data-instrument-id />
    </div>
    <!-- Inline autocomplete popup -->
    <div id="instrument-autocomplete" class="instrument-autocomplete-popup" hidden></div>
  </div>
  ```

- [x] **P7.3.4** ДОБАВИТЬ JS для inline autocomplete (в `<script>` блок, вместо удалённого modal-кода):
  ```javascript
  // Inline instrument autocomplete
  var instrumentPopup = document.getElementById("instrument-autocomplete");
  // Массив instruments передаётся из Jinja2 template
  var instruments = {{ instrument_items | tojson }};

  function hideInstrumentPopup() {
    if (instrumentPopup) { instrumentPopup.hidden = true; instrumentPopup.innerHTML = ""; }
  }

  function positionInstrumentPopup() {
    if (!instrumentPopup || instrumentPopup.hidden || !instrumentInput) return;
    var rect = instrumentInput.getBoundingClientRect();
    instrumentPopup.style.position = "fixed";
    instrumentPopup.style.top = (rect.bottom + 2) + "px";
    instrumentPopup.style.left = rect.left + "px";
    instrumentPopup.style.width = rect.width + "px";
    instrumentPopup.style.zIndex = "100";
  }

  if (instrumentInput && instrumentPopup) {
    instrumentInput.addEventListener("input", function() {
      var query = instrumentInput.value.trim().toLowerCase();
      // Сброс hidden ID при ручном вводе
      if (instrumentIdInput) instrumentIdInput.value = "";
      if (hiddenTicker) hiddenTicker.value = "";
      if (hiddenName) hiddenName.value = "";

      if (!query || query.length < 1) { hideInstrumentPopup(); return; }

      var matches = instruments.filter(function(item) {
        return (item.ticker + " " + item.name).toLowerCase().includes(query);
      }).slice(0, 5); // максимум 5 вариантов

      if (!matches.length) { hideInstrumentPopup(); return; }

      instrumentPopup.innerHTML = "";
      matches.forEach(function(item) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "instrument-autocomplete-item";
        var priceText = item.quote_last_price_text || "—";
        btn.innerHTML = "<strong>" + item.ticker + "</strong> " + item.name +
          " <span class='muted'>" + priceText + "</span>";
        btn.addEventListener("click", function() {
          instrumentInput.value = item.ticker + " · " + item.name;
          if (instrumentIdInput) instrumentIdInput.value = item.id;
          if (hiddenTicker) hiddenTicker.value = item.ticker;
          if (hiddenName) hiddenName.value = item.name;
          hideInstrumentPopup();
          syncMessageType();
        });
        instrumentPopup.appendChild(btn);
      });
      instrumentPopup.hidden = false;
      positionInstrumentPopup();
    });

    // Закрыть при клике вне
    document.addEventListener("click", function(e) {
      if (e.target === instrumentInput || (instrumentPopup && instrumentPopup.contains(e.target))) return;
      hideInstrumentPopup();
    });
    document.addEventListener("keydown", function(e) {
      if (e.key === "Escape") hideInstrumentPopup();
    });
    window.addEventListener("scroll", positionInstrumentPopup, true);
    window.addEventListener("resize", positionInstrumentPopup);
  }
  ```

- [x] **P7.3.5** CSS для inline popup:
  ```css
  .instrument-autocomplete-popup {
    position: fixed;
    z-index: 100;
    background: #fff;
    border: 1px solid rgba(12, 20, 46, 0.12);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.10);
    max-height: 220px;
    overflow: auto;
    display: grid;
    gap: 0;
  }
  .instrument-autocomplete-popup[hidden] { display: none !important; }
  .instrument-autocomplete-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 6px 10px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .instrument-autocomplete-item:hover {
    background: rgba(12, 20, 46, 0.05);
  }
  ```

- [x] **P7.3.6** Удалить CSS для `.author-picker-modal`, `.author-picker-shell`, `.author-picker-list`, `.author-picker-item`, `.author-picker-item-price` — modal больше не нужен.

- [x] **P7.3.7** УДАЛИТЬ `<select name="structured_side">` (Buy/Sell). Заменить на **checkbox-toggle «Купить / Продать»**:
  ```html
  <!-- Вместо select Buy/Sell -->
  <div class="author-editor-field author-editor-field--wide">
    <span class="author-editor-field-title">Направление</span>
    <div class="side-toggle">
      <input type="hidden" name="structured_side" value="" data-structured-side />
      <button type="button" class="side-toggle-btn is-buy" data-side-btn="buy">Купить</button>
      <button type="button" class="side-toggle-btn is-sell" data-side-btn="sell">Продать</button>
    </div>
  </div>
  ```
  JS для toggle:
  ```javascript
  var sideBtns = document.querySelectorAll("[data-side-btn]");
  var sideHidden = document.querySelector("[data-structured-side]");
  sideBtns.forEach(function(btn) {
    btn.addEventListener("click", function() {
      var val = btn.dataset.sideBtn;
      // Если уже выбран — снять выбор (toggle off)
      if (sideHidden && sideHidden.value === val) {
        sideHidden.value = "";
        sideBtns.forEach(function(b) { b.classList.remove("active"); });
      } else {
        if (sideHidden) sideHidden.value = val;
        sideBtns.forEach(function(b) { b.classList.remove("active"); });
        btn.classList.add("active");
      }
      syncMessageType();
    });
  });
  // Restore on page load
  if (sideHidden && sideHidden.value) {
    var activeBtn = document.querySelector('[data-side-btn="' + sideHidden.value + '"]');
    if (activeBtn) activeBtn.classList.add("active");
  }
  ```
  CSS для toggle:
  ```css
  .side-toggle { display: flex; gap: 0; border-radius: 8px; overflow: hidden; border: 1px solid rgba(12,20,46,0.12); }
  .side-toggle-btn { flex: 1; padding: 8px 12px; border: none; background: #fff; font-weight: 600; font-size: 0.85rem; cursor: pointer; transition: background 0.15s, color 0.15s; }
  .side-toggle-btn.is-buy.active { background: #22c55e; color: #fff; }
  .side-toggle-btn.is-sell.active { background: #ef4444; color: #fff; }
  .side-toggle-btn:not(.active):hover { background: rgba(12,20,46,0.04); }
  ```

- [x] **P7.3.8** ДОБАВИТЬ поля TP (Take Profit) и SL (Stop Loss) — необязательные:
  ```html
  <label class="author-editor-field">
    <span class="author-editor-field-title">TP (необяз.)</span>
    <input type="text" name="structured_tp" value="{{ composer.structured_tp or '' }}" inputmode="decimal" placeholder="—" data-structured-tp />
  </label>
  <label class="author-editor-field">
    <span class="author-editor-field-title">SL (необяз.)</span>
    <input type="text" name="structured_sl" value="{{ composer.structured_sl or '' }}" inputmode="decimal" placeholder="—" data-structured-sl />
  </label>
  ```
  Разместить в `.author-editor-structured-grid` после Цена и Количество. Grid layout:
  ```
  [Инструмент                    ] (full width)
  [Цена] [Кол-во] [TP]    [SL]
  [Сумма (readonly)]
  [Купить | Продать] toggle
  [Примечание                    ] (full width)
  ```
  CSS grid: `grid-template-columns: repeat(4, minmax(0, 1fr));`

- [x] **P7.3.9** ВАЛИДАЦИЯ блока 3 (client-side, в JS):
  **Правило:** если хотя бы одно поле блока 3 заполнено (ticker выбран, цена, кол-во, TP, SL, направление, примечание) — считать блок **активным**. Активный блок требует минимум 3 обязательных значения:
  1. Инструмент выбран (`instrumentIdInput.value` не пустой)
  2. Цена указана (`structuredPrice.value` не пустая)
  3. Количество указано (`structuredQuantity.value` не пустое)

  Если блок активен но не хватает обязательных полей — подсветить недостающие (`.is-invalid` класс) и не дать submit.

  Если ВСЕ поля блока 3 пустые — блок неактивен, валидация не нужна, submit разрешён.

  ```javascript
  function isDealBlockActive() {
    return !!(
      (instrumentIdInput && instrumentIdInput.value.trim()) ||
      (structuredPrice && structuredPrice.value.trim()) ||
      (structuredQuantity && structuredQuantity.value.trim()) ||
      (sideHidden && sideHidden.value) ||
      (document.querySelector("[data-structured-tp]") && document.querySelector("[data-structured-tp]").value.trim()) ||
      (document.querySelector("[data-structured-sl]") && document.querySelector("[data-structured-sl]").value.trim()) ||
      (dealNote && dealNote.value.trim())
    );
  }

  function validateDealBlock() {
    if (!isDealBlockActive()) return true; // всё пустое — OK
    var errors = [];
    if (!instrumentIdInput || !instrumentIdInput.value.trim()) errors.push("instrument");
    if (!structuredPrice || !structuredPrice.value.trim()) errors.push("price");
    if (!structuredQuantity || !structuredQuantity.value.trim()) errors.push("quantity");
    // Подсветить ошибки
    if (instrumentInput) instrumentInput.classList.toggle("is-invalid", errors.includes("instrument"));
    if (structuredPrice) structuredPrice.classList.toggle("is-invalid", errors.includes("price"));
    if (structuredQuantity) structuredQuantity.classList.toggle("is-invalid", errors.includes("quantity"));
    return errors.length === 0;
  }

  // Вызвать при submit формы
  form.addEventListener("submit", function(e) {
    if (!validateDealBlock()) {
      e.preventDefault();
      // Можно показать alert или scroll к блоку 3
    }
  });
  ```

- [x] **P7.3.10** Если checkbox «Купить/Продать» не выбран и все поля пустые — НЕ считать блок активным. Направление (`structured_side`) — необязательное при пустом блоке, но если блок активен — рекомендуется (не блокирует submit).

- [x] **P7.3.11** `python3 -m compileall src tests` — без ошибок

**Acceptance P7.3:**
- При вводе текста в поле «Наименование» — popup с 3-5 вариантами прямо под полем
- По мере набора список сужается
- Клик по варианту → поле заполняется (ticker · name), hidden ID заполняется
- Escape / клик вне → popup закрывается
- НЕТ modal dialog для выбора инструмента
- НЕТ select Buy/Sell — вместо него toggle-кнопки «Купить» (зелёный) / «Продать» (красный)
- Повторный клик по активной кнопке — снимает выбор
- Поля TP и SL — необязательные, рядом с Ценой и Кол-вом
- Если хотя бы одно поле блока 3 заполнено — обязательны: инструмент + цена + кол-во
- Если все поля пустые — блок неактивен, валидации нет

---

### P7.4 — Цены инструментов: включить провайдер котировок

**Root cause:** В `config.py` (строка 213):
```python
instrument_quote_provider_enabled: bool = Field(default=False)
```
Провайдер котировок **выключен по умолчанию**. `get_instrument_quote()` при `provider_enabled=False` сразу возвращает `_empty_quote(status="disabled")` → цена = `"—"`.

**Provider URL:** `https://meta.pbull.kz/api/marketData/forceDataSymbol` (строка 215).

**Файлы:**
- `src/pitchcopytrade/core/config.py` — настройка
- `src/pitchcopytrade/services/instruments.py` — `get_instrument_quote()`, `_fetch_quote()`
- `deploy/.env` или `deploy/docker-compose.server.yml` — env переменные

**Что должен сделать worker:**

- [x] **P7.4.1** Проверить доступность провайдера с сервера:
  ```bash
  curl -s "https://meta.pbull.kz/api/marketData/forceDataSymbol?symbol=SBER" | head -c 500
  ```
  Если 200 OK и есть данные — провайдер работает.

- [x] **P7.4.2** Добавить в production `.env` (или `docker-compose.server.yml` → environment):
  ```
  INSTRUMENT_QUOTE_PROVIDER_ENABLED=true
  ```

- [x] **P7.4.3** Добавить WARNING лог в `build_instrument_payload()` и в `get_instrument_quote()`:
  ```python
  # В build_instrument_payload():
  async def build_instrument_payload(instrument) -> dict[str, object]:
      quote = await get_instrument_quote(instrument.ticker)
      if quote.status in ("empty", "disabled"):
          logger.warning("No quote for %s: status=%s", instrument.ticker, quote.status)
      ...
  ```
  Если `meta.pbull.kz` недоступен — логировать в консоль, **не добавлять других провайдеров**.

- [x] **P7.4.4** После включения — redeploy и проверить что цены отображаются в autocomplete popup.

**Acceptance P7.4:**
- Провайдер включен на production (`INSTRUMENT_QUOTE_PROVIDER_ENABLED=true`)
- При загрузке формы composer инструменты показывают цены (не `"—"`)
- WARNING в логах если провайдер недоступен

---

### Acceptance P7 (общий)

1. Форма визуально компактная — минимум padding, gap, radius
2. History table — плотная, font-size ≤ 0.85rem
3. Одна кнопка «Отправить сообщение» на всю форму (не по одной в каждом блоке)
4. Блок 3: toggle-кнопки «Купить» (зелёный) / «Продать» (красный) вместо select
5. Блок 3: поля TP и SL (необязательные)
6. Блок 3: если хоть одно поле заполнено → обязательны инструмент + цена + кол-во; если всё пустое → блок неактивен
7. Instrument picker — inline autocomplete popup, 3-5 вариантов, сужается при наборе
8. НЕТ modal dialog, НЕТ select Buy/Sell
9. Цены инструментов: если `meta.pbull.kz` недоступен — WARNING в логах, нет fallback
10. `python3 -m compileall src tests` — без ошибок

---

## Блок P8 — Компактность блока 3, checkbox toggle, удаление заголовка, inline labels (2026-03-28)

### Контекст

Пользователь протестировал текущую форму. Замечания:

1. **Side toggle** — текущие `<button>` работают, но правильнее `<input type="checkbox">` с кастомной стилизацией. «Купить» выбран по умолчанию, невыбранная сторона — тот же цвет но сильно прозрачная.
2. **Поле «Цена»** — должно быть на одной строке с инструментом (не на отдельной строке).
3. **«Количество» и «Сумма»** — на одной строке (кол-во слева, сумма справа).
4. **label + input** — `<span>` заголовок и `<input>` в одну строку (inline), а не друг под другом. Компактнее.
5. **Поле «Заголовок»** — УДАЛИТЬ. Заголовок генерируется автоматически из текста или сделки.
6. **History table** — колонка «Заголовок / превью» → только «Превью»: обрезанный текст + `title` для tooltip при hover.
7. **Цены** — при выборе инструмента нет запроса в консоли. **Объяснение:** цены загружаются ОДИН РАЗ при рендере страницы через `build_instrument_payloads()` → `get_instrument_quote()`. Запроса при клике нет потому что данные уже в JS массиве `instrument_items`. Если `INSTRUMENT_QUOTE_PROVIDER_ENABLED=false` — все цены = "—".

### Статус P8

- P8.1 radio toggle `<input id> + <label for>` — `[x]` DONE
- P8.2 toggle на отдельной строке — `[x]` DONE
- P8.3 inline labels — `[x]` DONE
- P8.4 удалить заголовок — `[x]` DONE
- P8.5 history «Превью» — `[x]` DONE

---

### P8.6 — Диагностика `INSTRUMENT_QUOTE_PROVIDER_ENABLED=true` — цены не подгружаются `[x]`

**Проблема:** Пользователь добавил `INSTRUMENT_QUOTE_PROVIDER_ENABLED=true` в `.env`, но все цены по-прежнему показывают «—». При выборе инструмента в autocomplete цена не отображается.

**Контекст:**
- Цены загружаются ОДИН РАЗ при рендере страницы: `build_instrument_payloads()` → `get_instrument_quote()` → HTTP к `meta.pbull.kz`
- JS массив `instrument_items` содержит `quote_last_price_text` для каждого инструмента
- Если провайдер выключен или запрос упал — все цены = `"—"`
- `get_settings()` кэшируется через `@lru_cache(maxsize=1)` — изменение `.env` требует ПЕРЕЗАПУСКА процесса
- В Docker: env vars задаются в `docker-compose.server.yml`, `.env` файл читается только при локальном запуске

**Файлы:**
- `src/pitchcopytrade/core/config.py` — settings + lru_cache
- `src/pitchcopytrade/services/instruments.py` — quote pipeline
- `src/pitchcopytrade/api/routes/author.py` — вызов `build_instrument_payloads()`

**Что должен сделать worker:**

- [x] **P8.6.1** В `get_instrument_quote()` (`src/pitchcopytrade/services/instruments.py`) — добавить детальный лог при запросе цены:
  ```python
  logger.info("Fetching quote for %s: provider_enabled=%s, url=%s",
              normalized_ticker, settings.provider_enabled, settings.provider_base_url)
  ```
  Добавить в самом начале функции, ДО проверки `provider_enabled`.

- [x] **P8.6.2** В `_fetch_quote()` — добавить логирование HTTP запроса и ответа:
  ```python
  logger.info("Quote HTTP request: GET %s?symbol=%s", url, ticker)
  # ... после response
  logger.info("Quote HTTP response: status=%s, body_length=%s", response.status_code, len(response.content))
  ```

- [x] **P8.6.3** В `build_instrument_payload()` — добавить лог финального результата:
  ```python
  logger.info("Instrument payload for %s: quote_status=%s, last_price=%s",
              instrument.ticker, quote.status, quote.last_price)
  ```

- [x] **P8.6.4** Добавить в route handler `author.py` (или где вызывается `build_instrument_payloads`) лог:
  ```python
  logger.info("Building instrument payloads for %d instruments, provider_enabled=%s",
              len(instruments), get_settings().instrument_quotes.provider_enabled)
  ```

- [x] **P8.6.5** `python3 -m compileall src tests` — без ошибок

**ВАЖНО для пользователя:** После деплоя этих логов — проверить вывод через `docker logs api` или `docker compose logs api`. Если видно `provider_enabled=False` — значит env var не доходит до контейнера. Если `provider_enabled=True` но status=empty — значит `meta.pbull.kz` недоступен из Docker.

---

### Acceptance P8 (обновлённый)

1. Toggle «Купить/Продать» — плоский HTML: `<input id> + <label for>`, БЕЗ `<label>` обёрток, БЕЗ `<span>` внутри
2. `input:checked + label` CSS селектор работает (зелёный/красный насыщенный фон)
3. Невыбранная сторона — прозрачная версия цвета (rgba 0.15)
4. Блок 3 — 5 строк: Инструмент+Цена / Toggle / Кол-во+Сумма / TP+SL / Примечание
5. Toggle на ОТДЕЛЬНОЙ строке, НЕ на одной строке с Кол-во и Суммой
8. Все labels в блоке 3 — inline (span слева, input справа)
9. Поле «Заголовок» удалено из meta-grid
10. History table: «Превью» — обрезанный текст + tooltip
11. Детальные логи для диагностики quote provider
12. `python3 -m compileall src tests` — без ошибок

---

## Блок P9 — Равномерная ширина полей + таблица на Tabulator JSON mode (2026-03-28)

### Контекст

Работаем ТОЛЬКО с файлом `src/pitchcopytrade/web/templates/author/message_form.html`.
Закомментированный HTML НЕ ТРОГАТЬ. Менять только активный (незакомментированный) код.

Пользователь подтвердил что текущая структура и расположение элементов правильные (5 строк в блоке 3, toggle отдельно, meta-grid 3 колонки). Осталось два замечания:

1. **Поля не занимают всё доступное пространство.** Если в строке 2 элемента — каждый должен занимать ровно 50% (минус gap). Если 1 элемент — 100%. Сейчас `deal-field--fixed` ограничивает ширину «Цена» до 110px, а label-текст перед input не даёт полям растянуться.
2. **Таблица истории** — переделать с HTML `<table>` на Tabulator.js в JSON mode: в HTML объявляется только `<div id>`, а структура колонок и данные задаются через JS/JSON.

### Приоритет

**P9.1 → P9.2** — оба в одном файле `message_form.html`.

---

### P9.1 — Все поля блока 3 (Сделка) занимают 100% доступной ширины `[x]`

**Проблема:** Поля в `.deal-row` не растягиваются на всю ширину контейнера. «Цена» ограничена 110px. Каждый `.deal-field` содержит `<span>` (label) + `<input>`, где span забирает место и input не растягивается.

**Правило:** В каждой `.deal-row`:
- Если 2 элемента → каждый ровно **50%** (минус gap 6px)
- Если 1 элемент → **100%**
- Исключение: строка с toggle — toggle auto-width, это ОК

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

**Что должен сделать worker:**

- [x] **P9.1.1** УДАЛИТЬ классы `deal-field--fixed` и `deal-field--grow` из HTML. Все `.deal-field` должны иметь одинаковый `flex: 1`. Не должно быть фиксированных ширин.

  Текущий HTML строки 1:
  ```html
  <div class="deal-row">
    <label class="author-editor-field deal-field deal-field--grow">
      <span>Наименование ценной бумаги</span>
      <div class="author-instrument-picker"><input .../></div>
      ...
    </label>
    <label class="author-editor-field deal-field deal-field--fixed">
      <span>Цена</span>
      <input .../>
    </label>
  </div>
  ```

  Целевой HTML строки 1:
  ```html
  <div class="deal-row">
    <label class="author-editor-field deal-field">
      <span class="author-editor-field-title">Наименование ценной бумаги</span>
      <div class="author-instrument-picker"><input .../></div>
      ...
    </label>
    <label class="author-editor-field deal-field">
      <span class="author-editor-field-title">Цена</span>
      <input .../>
    </label>
  </div>
  ```

  То же для строки «Примечание к сделке» — убрать `deal-field--grow`, оставить просто `deal-field`.

- [x] **P9.1.2** CSS: УДАЛИТЬ правила для `.deal-field--grow`, `.deal-field--fixed`, `.deal-field--fixed input`. Заменить на единый стиль:
  ```css
  .deal-field {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.82rem;
    flex: 1 1 0;       /* ← все поля равные */
    min-width: 0;       /* ← позволяет сжиматься */
  }
  ```

- [x] **P9.1.3** CSS: `.deal-row` должен гарантировать равномерное распределение:
  ```css
  .deal-row {
    display: flex;
    gap: 6px;
    align-items: stretch;
    width: 100%;
  }
  ```
  Уже почти так, но убедиться что нет `flex-wrap` на desktop (wrap ломает 50/50).

- [x] **P9.1.4** Внутри `.deal-field` — input/textarea должны занимать всё оставшееся пространство:
  ```css
  .deal-field input,
  .deal-field textarea,
  .deal-field select {
    flex: 1;
    min-width: 0;
    width: 100%;   /* ← fallback для textarea */
  }
  ```

- [x] **P9.1.5** Визуальный тест: открыть страницу и проверить:
  - Строка 1: «Наименование» и «Цена» — одинаковая ширина (50%/50%)
  - Строка 3: «Количество» и «Сумма» — одинаковая ширина (50%/50%)
  - Строка 4: «TP» и «SL» — одинаковая ширина (50%/50%)
  - Строка 5: «Примечание» — 100% ширины

---

### P9.2 — Таблица истории: переделать с HTML `<table>` на Tabulator JSON mode `[x]`

**Проблема:** Сейчас таблица истории — обычный HTML `<table>` с Jinja-циклом `{% for message in history %}`. Нужно заменить на Tabulator.js в JSON mode: в HTML только `<div>`, структура колонок и данные — через JS.

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

**Текущая реализация (строки ~57-104):**
```html
<div class="author-history-table-wrap">
  <table class="author-history-table">
    <thead>
      <tr>
        <th>Дата</th>
        <th>Тип</th>
        <th>Превью</th>
        <th>Стратегия</th>
        <th>Статус</th>
        <th>Каналы</th>
        <th>Действия</th>
      </tr>
    </thead>
    <tbody>
      {% for message in history %}...{% endfor %}
    </tbody>
  </table>
</div>
```

**Что должен сделать worker:**

- [x] **P9.2.1** Заменить `<table class="author-history-table">...</table>` на один `<div>`:
  ```html
  <div id="author-history-grid"></div>
  ```
  УДАЛИТЬ весь `<table>`, `<thead>`, `<tbody>`, `{% for message in history %}` loop.

- [x] **P9.2.2** Подготовить данные в JSON. В блоке `<script>` (в конце файла) добавить массив данных, сгенерированный Jinja:
  ```javascript
  const historyData = {{ history_json | tojson }};
  ```
  **ВАЖНО:** Нужен route handler, который сериализует `history` в JSON. Если `history_json` ещё не передаётся в шаблон — создать его в route handler. Формат каждого элемента:
  ```json
  {
    "date": "28.03.2026 14:30",
    "type": "IDEA",
    "preview": "Первые 60 символов текста...",
    "preview_full": "Полный текст для tooltip",
    "strategy": "Название стратегии",
    "status": "Черновик",
    "channels": "strategy",
    "edit_url": "/author/messages/{id}/edit"
  }
  ```

- [x] **P9.2.3** Инициализировать Tabulator в JS:
  ```javascript
  if (document.getElementById("author-history-grid")) {
    new Tabulator("#author-history-grid", {
      data: historyData,
      layout: "fitColumns",
      height: "400px",
      placeholder: "Пока сообщений нет.",
      columns: [
        { title: "Дата", field: "date", width: 140, sorter: "string" },
        { title: "Тип", field: "type", width: 80 },
        {
          title: "Превью", field: "preview", widthGrow: 3,
          tooltip: function(e, cell) { return cell.getRow().getData().preview_full; },
          cssClass: "author-history-message-preview"
        },
        { title: "Стратегия", field: "strategy", width: 140 },
        { title: "Статус", field: "status", width: 110 },
        { title: "Каналы", field: "channels", width: 100 },
        {
          title: "Действия", field: "edit_url", width: 100,
          formatter: function(cell) {
            var url = cell.getValue();
            return url ? '<a class="action ghost" href="' + url + '">Открыть</a>' : "";
          },
          headerSort: false
        }
      ]
    });
  }
  ```

- [x] **P9.2.4** Backend: В route handler (найти где рендерится `message_form.html`) — добавить сериализацию `history` в JSON формат для Tabulator. Создать переменную `history_json` и передать в шаблон:
  ```python
  history_json = []
  for msg in history:
      content = msg.text or {}
      preview_full = content.get("plain") or ""
      if not preview_full and content.get("body"):
          # strip HTML tags
          import re
          preview_full = re.sub(r"<[^>]+>", "", content["body"])
      if not preview_full:
          preview_full = msg.comment or "Без текста"

      history_json.append({
          "date": (msg.updated or msg.created).strftime("%d.%m.%Y %H:%M") if (msg.updated or msg.created) else "—",
          "type": (msg.type or "mixed").upper(),
          "preview": preview_full[:60] + ("..." if len(preview_full) > 60 else ""),
          "preview_full": preview_full,
          "strategy": msg.strategy.title if msg.strategy else "—",
          "status": label_message_status(msg.status),
          "channels": ", ".join(msg.deliver) if msg.deliver else "strategy",
          "edit_url": f"/author/messages/{msg.id}/edit",
      })
  ```
  Передать `history_json=history_json` в `TemplateResponse` context.

- [x] **P9.2.5** Убедиться что Tabulator.js CSS и JS подключены в базовом шаблоне (`staff_base.html`). Если уже используется на других страницах (admin) — должно быть подключено. Проверить:
  ```html
  <link href="/static/vendor/tabulator.min.css" rel="stylesheet">
  <script src="/static/vendor/tabulator.min.js"></script>
  ```

- [x] **P9.2.6** УДАЛИТЬ неиспользуемые CSS правила для `.author-history-table`, `.author-history-table th`, `.author-history-table td`, `.author-history-message-title`, `.author-history-message-preview`, `.author-history-message-meta`, `.author-history-empty` — они больше не нужны после перехода на Tabulator.

- [x] **P9.2.7** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P9 (общий)

1. Блок 3: строка с 2 полями — каждое поле ровно 50% ширины (минус gap)
2. Блок 3: строка с 1 полем — 100% ширины
3. НЕТ фиксированных ширин (`110px`, `140px`) у полей блока 3
4. Таблица истории — Tabulator.js, НЕ HTML `<table>`
5. Данные истории передаются как JSON из backend, рендерятся через JS
6. Колонки: Дата, Тип, Превью (tooltip с полным текстом), Стратегия, Статус, Каналы, Действия
7. Закомментированный HTML не изменён
8. `python3 -m compileall src tests` — без ошибок

---

## Блок P10 — Toggle «Купить/Продать» на 100% ширины строки (2026-03-28)

### Контекст

Worker выполнил P9. Поля блока 3 (Наименование+Цена, Количество+Сумма, TP+SL, Примечание) теперь занимают равные доли ширины. **НО** строка с toggle «Купить | Продать» осталась маленькой — toggle auto-width (~30% строки), остальное — пустое место.

Правило: **если элемент один в строке — он занимает 100% ширины**. Toggle — единственный элемент в своей `.deal-row`. Значит toggle должен растянуться на всю ширину, а кнопки «Купить» и «Продать» — каждая по 50%.

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

### P10.1 — Toggle на 100% ширины строки `[x]`

**Текущий CSS (проблема):**
```css
/* строка ~627 */
.side-toggle {
  display: flex;
  gap: 0;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid rgba(12, 20, 46, 0.12);
  align-self: stretch;
  flex-shrink: 0;
  min-width: 140px;        /* ← ограничивает, но НЕ растягивает */
}
/* строка ~438 */
.deal-row .side-toggle {
  align-self: flex-start;  /* ← мешает растяжению */
}
/* строка ~642 */
.side-toggle-label {
  padding: 4px 12px;       /* ← маленький padding, кнопки узкие */
}
```

**Что должен сделать worker:**

- [x] **P10.1.1** CSS `.side-toggle` — заменить текущее правило (строка ~627-636) на:
  ```css
  .side-toggle {
    display: flex;
    gap: 0;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid rgba(12, 20, 46, 0.12);
    width: 100%;
  }
  ```
  УДАЛИТЬ: `align-self: stretch`, `flex-shrink: 0`, `min-width: 140px`.

- [x] **P10.1.2** CSS `.side-toggle-label` — добавить `flex: 1` и `text-align: center`, увеличить padding. Заменить текущее правило (строка ~642-650) на:
  ```css
  .side-toggle-label {
    flex: 1;
    text-align: center;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 0.82rem;
    cursor: pointer;
    line-height: 1.4;
    transition: background 0.15s, color 0.15s;
    user-select: none;
  }
  ```

- [x] **P10.1.3** УДАЛИТЬ правило `.deal-row .side-toggle { align-self: flex-start; }` (строка ~438-440). Полностью удалить этот блок.

- [x] **P10.1.4** В `@media (max-width: 1080px)` — УДАЛИТЬ `.side-toggle { min-width: 140px; }` (строка ~692-694).

- [x] **P10.1.5** В `@media (max-width: 900px)` — проверить что `.side-toggle { width: 100% }` уже есть или наследуется от основного правила. Если есть `min-width: 0` — удалить, `width: 100%` из основного правила достаточно.

- [x] **P10.1.6** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P10

1. Toggle «Купить | Продать» — 100% ширины строки (`.deal-row`)
2. Каждая кнопка toggle — ровно 50% ширины (`flex: 1`)
3. Текст кнопок по центру (`text-align: center`)
4. Высота кнопок визуально совпадает с input-полями (`padding: 8px`)
5. Нет `min-width: 140px` нигде в файле
6. Нет `align-self: flex-start` для `.deal-row .side-toggle`
7. Закомментированный HTML не изменён
8. `python3 -m compileall src tests` — без ошибок

---

## Блок P11 — Bugfix: NameError при POST /author/messages → 500 (2026-03-28)

### Контекст

При отправке формы создания рекомендации (`POST /author/messages`) — **500 Internal Server Error**.

**Traceback (из консоли uvicorn):**
```
File "src/pitchcopytrade/api/routes/author.py", line 914, in _render_recommendation_create_error
    "structured_instrument_id": selected_instrument_id,
                                ^^^^^^^^^^^^^^^^^^^^^^
NameError: name 'selected_instrument_id' is not defined
```

**Root cause:** Функция `_render_recommendation_create_error()` (строка 873) использует переменные `selected_instrument_id` и `selected_instrument` (строки 914-917), но они НЕ переданы как параметры и НЕ определены в теле функции. Эти переменные существуют только в `recommendation_create_submit()` (строка 414-415) как локальные — они не видны в helper-функции.

**Файл:** `src/pitchcopytrade/api/routes/author.py`

### P11.1 — Исправить NameError `[x]`

**Проблемные строки (~914-917) в `_render_recommendation_create_error()`:**
```python
"structured_instrument_id": selected_instrument_id,           # ← NameError!
"structured_instrument_query": str(form.get("structured_instrument_query", "") or ""),
"structured_instrument_ticker": selected_instrument.ticker if selected_instrument is not None else "",  # ← NameError!
"structured_instrument_name": selected_instrument.name if selected_instrument is not None else "",      # ← NameError!
```

**Что должен сделать worker:**

- [x] **P11.1.1** Заменить строки 914-917: использовать данные из `form` вместо несуществующих переменных. Форма отправляет hidden fields `structured_instrument_id`, `structured_instrument_ticker`, `structured_instrument_name`:

  **Было (строки 914-917):**
  ```python
  "structured_instrument_id": selected_instrument_id,
  "structured_instrument_query": str(form.get("structured_instrument_query", "") or ""),
  "structured_instrument_ticker": selected_instrument.ticker if selected_instrument is not None else "",
  "structured_instrument_name": selected_instrument.name if selected_instrument is not None else "",
  ```

  **Стало:**
  ```python
  "structured_instrument_id": str(form.get("structured_instrument_id", "") or ""),
  "structured_instrument_query": str(form.get("structured_instrument_query", "") or ""),
  "structured_instrument_ticker": str(form.get("structured_instrument_ticker", "") or ""),
  "structured_instrument_name": str(form.get("structured_instrument_name", "") or ""),
  ```

- [x] **P11.1.2** Поиск аналогичных багов: выполнить `grep -n 'selected_instrument_id\|selected_instrument\b' src/pitchcopytrade/api/routes/author.py` и для КАЖДОГО вхождения проверить что переменная определена в scope текущей функции. Особенно проверить:
  - `_render_recommendation_update_error()` — если существует
  - Любые другие `_render_*_error()` helper-функции

- [x] **P11.1.3** Проверить что `structured_tp` и `structured_sl` тоже есть в dict `form_values` (строки 908-925). Если нет — добавить:
  ```python
  "structured_tp": str(form.get("structured_tp", "") or ""),
  "structured_sl": str(form.get("structured_sl", "") or ""),
  ```

- [x] **P11.1.4** `python3 -m compileall src tests` — без ошибок

- [x] **P11.1.5** Ручной тест: открыть форму, заполнить сделку (инструмент GAZP, цена 120, кол-во 100), НЕ выбирать стратегию → нажать «Отправить сообщение» → должна вернуться форма с ошибкой 422 «Выберите стратегию автора» и все поля сохранены. **НЕ должно быть 500.**

---

### Acceptance P11

1. `POST /author/messages` с невалидными данными → 422, НЕ 500
2. Форма перерисовывается с сохранением введённых данных (ticker, price, side, quantity, tp, sl, note)
3. Нет `NameError` в логах
4. Проверены ВСЕ helper-функции в `author.py` на аналогичные `NameError` с `selected_instrument*`
5. `python3 -m compileall src tests` — без ошибок

### Где хранятся логи

- **Локальный запуск (dev):** вывод uvicorn в терминал (stdout/stderr)
- **Docker:** `docker compose logs api` / `docker compose logs bot` / `docker compose logs worker`
- **Файл логов:** не настроен — весь output в stdout контейнера

---

## Блок P12 — Tabulator: убрать серый фон и огромную высоту пустой таблицы (2026-03-28)

### Контекст

После перехода на Tabulator (P9.2) пустая таблица истории отображается как огромный серый прямоугольник ~400px высотой с текстом «Пока сообщений нет.» по центру. Это выглядит сломанным. Проблема в `min-height: 400px` на обёртке и самом grid, плюс дефолтный серый фон Tabulator placeholder.

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

### P12.1 — Компактная пустая таблица `[x]`

**Текущий CSS (проблема):**
```css
/* строка ~388 */
.author-history-grid-wrap {
  min-height: 400px;
}
/* строка ~392 */
#author-history-grid {
  min-height: 400px;
}
```

Tabulator также рендерит `.tabulator-placeholder` div с серым фоном на всю `height`/`min-height`.

**Что должен сделать worker:**

- [x] **P12.1.1** УДАЛИТЬ `min-height: 400px` из CSS для `.author-history-grid-wrap` и `#author-history-grid`. Таблица должна быть компактной когда пустая. Заменить на:
  ```css
  .author-history-grid-wrap {
    overflow: auto;
  }
  ```
  Удалить правило `#author-history-grid { min-height: 400px; }` полностью.

- [x] **P12.1.2** В JS инициализации Tabulator — изменить `height`:
  ```javascript
  new Tabulator("#author-history-grid", {
    data: historyData,
    layout: "fitColumns",
    height: historyData.length > 0 ? "300px" : undefined,  // компактный если пуст
    maxHeight: "400px",                                      // максимальная высота
    placeholder: "Пока сообщений нет.",
    // ... columns
  });
  ```
  Или просто убрать `height: "400px"` и использовать `maxHeight: "400px"` — Tabulator автоматически подстроится.

- [x] **P12.1.3** CSS для placeholder Tabulator — убрать серый фон, сделать компактным:
  ```css
  #author-history-grid .tabulator-placeholder {
    padding: 24px 12px;
    background: transparent;
    color: var(--muted, #888);
    font-size: 0.85rem;
  }
  #author-history-grid .tabulator-placeholder span {
    color: inherit;
  }
  ```

- [x] **P12.1.4** Общая стилизация Tabulator для этой таблицы — опционально переопределить шрифт и размер:
  ```css
  #author-history-grid .tabulator-header .tabulator-col-title {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  #author-history-grid .tabulator-row .tabulator-cell {
    font-size: 0.82rem;
    padding: 4px 8px;
  }
  ```

- [x] **P12.1.5** Применить общую светлую тему Tabulator к истории автора через `pct-tabulator`, чтобы таблица наследовала оформление страницы, а не дефолтный серый вид.

- [x] **P12.1.6** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P12

1. Пустая таблица — компактная (≤ 80px), НЕ 400px серого пространства
2. Placeholder «Пока сообщений нет.» — на прозрачном/белом фоне, обычным шрифтом
3. Таблица с данными — растёт до `maxHeight: 400px`, потом скролл
4. Шрифт заголовков и ячеек — компактный (0.75rem / 0.82rem)
5. Закомментированный HTML не изменён
6. `python3 -m compileall src tests` — без ошибок

---

## Блок P13 — Composer как overlay-панель внутри `.staff-main` (2026-03-29)

### Контекст

Сейчас форма composer — часть `{% block content %}` в `message_form.html`. Таблица растёт → форма уезжает вниз. Composer привязан только к `/author/messages`.

**Новая архитектура: overlay внутри `.staff-main`**

Composer — это **overlay-панель**, которая:
- Живёт **внутри** `<main class="staff-main">` (не `position: fixed` от viewport, а `position: absolute` внутри main)
- Занимает **всю рабочую область** `.staff-main` (100% ширины и высоты main)
- **Не перекрывает sidebar** — она часть main, а не поверх всего
- **Разворачивается** при открытии (по default на `/author/messages`)
- **Сворачивается** в компактную полоску-header (~40px) для работы с таблицей
- Доступна на **любой** author-странице
- Чётко показывает: **«Новое сообщение»** или **«Ред. #ID · Черновик»**

**Визуальная схема:**
```
┌──────────┬─────────────────────────────────────────────────────────┐
│ sidebar  │ .staff-main (position: relative)                        │
│          │ ┌─────────────────────────────────────────────────────┐ │
│          │ │ .staff-topline (хлебные крошки, кнопки)             │ │
│          │ ├─────────────────────────────────────────────────────┤ │
│          │ │ .staff-content (таблица, дашборд — скроллируемый)   │ │
│          │ │   ...контент страницы...                            │ │
│          │ │                                                     │ │
│          │ ├─────────────────────────────────────────────────────┤ │
│          │ │ .composer-dock (position: absolute; bottom:0)       │ │
│          │ │ ┌─ header: [Новое сообщение]  [▼ свернуть] ──────┐ │ │
│          │ │ │ Стратегия [___]  Класс [___]  Статус [___]      │ │ │
│          │ │ │ ┌─Описание──┐ ┌─OnePager──┐ ┌─Сделка─────────┐ │ │ │
│          │ │ │ │           │ │           │ │ GAZP  120       │ │ │ │
│          │ │ │ │           │ │           │ │ [Купить|Продать]│ │ │ │
│          │ │ │ └───────────┘ └───────────┘ └────────────────┘ │ │ │
│          │ │ │         [Отправить сообщение]                   │ │ │
│          │ │ └────────────────────────────────────────────────┘ │ │
│          │ └─────────────────────────────────────────────────────┘ │
└──────────┴─────────────────────────────────────────────────────────┘
```

**Свёрнутое состояние:**
```
│          │ │ .staff-content (таблица — вся высота)               │ │
│          │ │   ...контент страницы...                            │ │
│          │ │                                                     │ │
│          │ ├─────────────────────────────────────────────────────┤ │
│          │ │ .composer-dock.is-collapsed                         │ │
│          │ │ ┌─ [Новое сообщение]  [▲ развернуть] ────────────┐ │ │
│          │ └─────────────────────────────────────────────────────┘ │
```

### Файлы

- `src/pitchcopytrade/web/templates/author/message_form.html` — вырезать форму, оставить таблицу
- `src/pitchcopytrade/web/templates/author/_composer_dock.html` — **НОВЫЙ**: partial с overlay-формой
- `src/pitchcopytrade/web/templates/staff_base.html` — добавить `position: relative` к `.staff-main`, подключить `{% block composer_dock %}`
- `src/pitchcopytrade/api/routes/author.py` — передавать composer context во все author-страницы

### Приоритет

**P13.1 → P13.2 → P13.3 → P13.4 → P13.5**

---

### P13.1 — Извлечь composer-форму в `_composer_dock.html` `[x]`

**Файл:** `src/pitchcopytrade/web/templates/author/message_form.html`

**Что должен сделать worker:**

- [x] **P13.1.1** Создать НОВЫЙ файл `src/pitchcopytrade/web/templates/author/_composer_dock.html`.

- [x] **P13.1.2** Из `message_form.html` **ВЫРЕЗАТЬ** (не копировать — именно удалить из исходного файла):
  - `<form class="surface author-editor-composer" ...>...</form>` (строки 72-276)
  - `<dialog class="author-preview-modal">...</dialog>` (строки 279-294)
  - Все `<style>` правила, относящиеся к форме (`.author-editor-composer`, `.author-editor-blocks-row`, `.author-editor-block`, `.author-editor-meta-grid`, `.deal-row`, `.deal-field`, `.side-toggle`, `.instrument-autocomplete-popup` и т.д.)
  - Весь `<script>` блок с JS формы (функции `syncAmount`, `syncMessageType`, `renderInstrumentPopup`, `validateDealBlock` и т.д.)

- [x] **P13.1.3** В `_composer_dock.html` — обернуть форму в dock-контейнер:
  ```html
  {# Composer dock — overlay panel inside .staff-main #}
  <div class="composer-dock {% if not composer_default_open %}is-collapsed{% endif %}"
       id="composer-dock"
       data-composer-dock>

    {# --- Header bar (всегда видна) --- #}
    <div class="composer-dock-header" data-composer-dock-toggle>
      <div class="composer-dock-title">
        {% if composer_recommendation %}
          <span class="composer-dock-mode is-edit">Редактирование</span>
          <span class="composer-dock-id">#{{ composer_recommendation.id[:8] }}…</span>
          <span class="pill">{{ label_message_status(composer_recommendation.status) }}</span>
        {% else %}
          <span class="composer-dock-mode is-new">Новое сообщение</span>
        {% endif %}
      </div>
      <button type="button" class="action ghost composer-dock-toggle-btn"
              data-composer-dock-toggle title="Свернуть / развернуть">
        <span class="composer-dock-arrow">▼</span>
      </button>
    </div>

    {# --- Body (скрывается при is-collapsed) --- #}
    <div class="composer-dock-body" data-composer-dock-body>
      <form
        class="composer-form"
        method="post"
        enctype="multipart/form-data"
        action="{% if composer_recommendation %}/author/messages/{{ composer_recommendation.id }}{% else %}/author/messages{% endif %}"
        data-author-form
      >
        {# ... вся начинка формы (hidden inputs, meta-grid, blocks-row, submit) ... #}
      </form>
    </div>
  </div>

  <style>
    {# ... CSS dock + CSS формы ... #}
  </style>

  <script>
    {# ... JS dock toggle + JS формы ... #}
  </script>
  ```

- [x] **P13.1.4** В `message_form.html` — после удаления формы, оставить ТОЛЬКО:
  ```html
  {% extends "staff_base.html" %}

  {% block content %}
  <section class="surface author-editor-hero">...</section>
  {% if error %}<section class="author-editor-error">...</section>{% endif %}
  <section class="surface author-editor-history" id="block-history">
    {# Tabulator grid #}
  </section>
  <style>{# CSS только для history/hero #}</style>
  <script>{# JS только для Tabulator init #}</script>
  {% endblock %}

  {% block composer_dock %}
    {% include "author/_composer_dock.html" %}
  {% endblock %}
  ```

---

### P13.2 — CSS для overlay dock внутри `.staff-main` `[x]`

**Что должен сделать worker:**

- [x] **P13.2.1** В `staff_base.html` — добавить `position: relative` к `.staff-main`:
  ```css
  .staff-main {
    /* уже есть: */
    min-width: 0;
    min-height: 0;
    height: 100%;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow: hidden;
    /* ДОБАВИТЬ: */
    position: relative;
  }
  ```

- [x] **P13.2.2** CSS dock в `_composer_dock.html`:
  ```css
  .composer-dock {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 20;
    background: var(--staff-surface, #fff);
    border-top: 1px solid var(--staff-line, #d7dee7);
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.06);
    display: flex;
    flex-direction: column;
    max-height: calc(100% - 60px);   /* не перекрывать topline (~60px) */
    border-radius: 12px 12px 0 0;
  }

  /* --- Свёрнутое состояние --- */
  .composer-dock.is-collapsed {
    max-height: none;       /* сбросить ограничение */
  }
  .composer-dock.is-collapsed .composer-dock-body {
    display: none;
  }

  /* --- Header (всегда видна) --- */
  .composer-dock-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 16px;
    cursor: pointer;
    user-select: none;
    flex-shrink: 0;
    border-bottom: 1px solid var(--staff-line, #d7dee7);
    background: var(--staff-surface-soft, #f7f9fb);
    border-radius: 12px 12px 0 0;
  }

  .composer-dock-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .composer-dock-mode.is-new {
    color: var(--staff-accent, #224a7a);
  }
  .composer-dock-mode.is-edit {
    color: #b45309;
  }
  .composer-dock-id {
    font-family: monospace;
    font-size: 0.75rem;
    color: var(--staff-muted);
  }

  /* --- Body (скроллируемый) --- */
  .composer-dock-body {
    overflow-y: auto;
    padding: 12px;
    flex: 1;
    min-height: 0;
  }

  /* --- Toggle arrow --- */
  .composer-dock-arrow {
    display: inline-block;
    transition: transform 0.2s;
  }
  .composer-dock.is-collapsed .composer-dock-arrow {
    transform: rotate(180deg);  /* ▼ → ▲ */
  }
  ```

- [x] **P13.2.3** `.staff-content` — НЕ добавлять `padding-bottom`. Вместо этого dock абсолютно позиционирован и ПЕРЕКРЫВАЕТ контент (это overlay). Контент скроллируется под ним. Когда dock свёрнут — контент почти полностью виден.

---

### P13.3 — JS для toggle dock + сохранение состояния `[x]`

**Что должен сделать worker:**

- [x] **P13.3.1** JS в `_composer_dock.html`:
  ```javascript
  (function() {
    var dock = document.getElementById("composer-dock");
    if (!dock) return;

    var STORAGE_KEY = "composer-dock-collapsed";
    var defaultOpen = dock.hasAttribute("data-composer-default-open");

    // Начальное состояние:
    // Если data-composer-default-open — всегда раскрыт при загрузке
    // Иначе — восстановить из localStorage (default = collapsed)
    if (!defaultOpen) {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored === null || stored === "1") {
        dock.classList.add("is-collapsed");
      }
    }

    // Toggle по клику на header
    dock.querySelector("[data-composer-dock-toggle]").addEventListener("click", function() {
      dock.classList.toggle("is-collapsed");
      localStorage.setItem(STORAGE_KEY, dock.classList.contains("is-collapsed") ? "1" : "0");
    });
  })();
  ```

- [x] **P13.3.2** В `message_form.html` (где `{% include %}` dock) — передать `composer_default_open=True`:
  ```html
  {% set composer_default_open = True %}
  {% include "author/_composer_dock.html" %}
  ```
  В Jinja partial — использовать `composer_default_open` для класса И data-attr:
  ```html
  <div class="composer-dock {% if not composer_default_open %}is-collapsed{% endif %}"
       {% if composer_default_open %}data-composer-default-open{% endif %}
       ...>
  ```

  На других страницах (dashboard, strategies) — `composer_default_open=False` (dock свёрнут).

---

### P13.4 — Подключить dock на всех author-страницах `[x]`

**Что должен сделать worker:**

- [x] **P13.4.1** В `staff_base.html` — блок `{% block composer_dock %}{% endblock %}` уже есть на строке 655. Переместить его **ВНУТРЬ** `<main class="staff-main">`, ПОСЛЕ `.staff-content`, ПЕРЕД `</main>`:
  ```html
  <main class="staff-main">
    <div class="staff-topline">...</div>
    <div class="staff-content">
      {% block content %}{% endblock %}
    </div>
    {% block composer_dock %}{% endblock %}  {# ← СЮДА, внутрь main #}
  </main>
  ```
  **УДАЛИТЬ** старый `{% block composer_dock %}` со строки 655 (вне main).

- [x] **P13.4.2** В каждом author-шаблоне добавить блок:
  - `message_form.html`:
    ```html
    {% block composer_dock %}
      {% set composer_default_open = True %}
      {% include "author/_composer_dock.html" %}
    {% endblock %}
    ```
  - `dashboard.html`:
    ```html
    {% block composer_dock %}
      {% set composer_default_open = False %}
      {% include "author/_composer_dock.html" %}
    {% endblock %}
    ```
  - `strategies_list.html` и `strategy_form.html` — аналогично с `False`.
  - `messages_list.html` — с `False` (список сообщений без формы; форма на message_form).

- [x] **P13.4.3** Backend: создать helper `_get_composer_context()` в `author.py`:
  ```python
  async def _get_composer_context(
      repository: AuthorRepository,
      author: AuthorProfile,
      recommendation=None,
      form_values: dict | None = None,
  ) -> dict:
      """Context для composer dock — вызывается на любой author-странице."""
      strategies = await list_author_strategies(repository, author)
      instruments = await list_active_instruments(repository)
      instrument_items = [build_instrument_payload(inst) for inst in instruments]
      return {
          "strategies": strategies,
          "instrument_items": instrument_items,
          "composer_recommendation": recommendation,
          "compose_form_values": form_values or {},
      }
  ```

- [x] **P13.4.4** Подключить `_get_composer_context()` в КАЖДЫЙ author route handler. Merge dict в template context:
  - `GET /author/dashboard` — `_get_composer_context(repo, author)` (новое сообщение)
  - `GET /author/strategies` — `_get_composer_context(repo, author)`
  - `GET /author/messages` — `_get_composer_context(repo, author)`
  - `GET /author/messages/new` — `_get_composer_context(repo, author)` (новое)
  - `GET /author/messages/{id}/edit` — `_get_composer_context(repo, author, recommendation=loaded_msg, form_values=msg_values)`
  - `POST /author/messages` (create) — `_get_composer_context(...)` при re-render с ошибкой
  - `POST /author/messages/{id}` (update) — аналогично

  **Важно:** Не загружать strategies/instruments дважды. Если route уже загрузил их — переиспользовать.

---

### P13.5 — Header dock: чёткое отображение режима `[x]`

**Что должен сделать worker:**

- [x] **P13.5.1** Header dock должен показывать:

  **Новое сообщение:**
  ```
  [●] Новое сообщение                                    [▼]
  ```
  `●` — синий кружок или иконка. Текст `Новое сообщение` — цвет `var(--staff-accent)`.

  **Редактирование:**
  ```
  [✎] Редактирование #3fc25027  [Черновик]               [▼]
  ```
  `✎` — оранжевый. ID — первые 8 символов UUID, monospace. Pill с текущим статусом.

- [x] **P13.5.2** При клике «Открыть» в таблице истории (ссылка `/author/messages/{id}/edit`) — страница перезагружается и dock открывается с данными этого сообщения. Это уже работает через route handler, но убедиться что `composer_recommendation` передаётся.

- [x] **P13.5.3** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P13

1. Composer — `position: absolute` overlay ВНУТРИ `<main class="staff-main">`, НЕ `position: fixed`
2. Dock занимает ширину `.staff-main` (не перекрывает sidebar)
3. `max-height: calc(100% - 60px)` — не перекрывает topline
4. Dock видна на всех author-страницах: dashboard, strategies, messages, message edit
5. На `/author/messages` — dock **раскрыт** по default
6. На других страницах — dock **свёрнут** по default (header-полоска ~40px)
7. Header чётко показывает: «Новое сообщение» (синий) или «Редактирование #ID» (оранжевый) + pill статус
8. Click по header → toggle collapse/expand
9. Состояние collapse/expand сохраняется в localStorage (кроме страниц с `data-composer-default-open`)
10. `message_form.html` содержит ТОЛЬКО таблицу + hero (форма полностью в `_composer_dock.html`)
11. Таблица истории скроллируется под dock-ом
12. `python3 -m compileall src tests` — без ошибок

---

## Блок P14 — Кнопка «+ Новое» в dock при редактировании (2026-03-29) [x]

### Контекст

Когда пользователь нажимает «Открыть» в таблице истории, страница перезагружается на `/author/messages/{id}/edit` и dock показывает «✎ Редактирование #ID». **Нет способа вернуться к созданию нового сообщения** без ручного перехода по URL.

**Файл:** `src/pitchcopytrade/web/templates/author/_composer_dock.html`

### P14.1 — Кнопка «+ Новое сообщение» в header dock `[x]`

**Что должен сделать worker:**

- [x] **P14.1.1** В header dock (`_composer_dock.html`), когда `_composer_recommendation` не None (режим редактирования) — добавить ссылку для сброса на новое сообщение:
  ```html
  <div class="composer-dock-title">
    {% if _composer_recommendation %}
      <span class="composer-dock-mode is-edit">✎ Редактирование</span>
      <span class="composer-dock-id">#{{ _composer_recommendation.id[:8] }}</span>
      {% if _composer_recommendation.status %}
      <span class="pill">{{ label_message_status(_composer_recommendation.status) }}</span>
      {% endif %}
      <a href="/author/messages" class="action ghost composer-dock-new" title="Создать новое сообщение">+ Новое</a>
    {% else %}
      <span class="composer-dock-mode is-new">● Новое сообщение</span>
    {% endif %}
  </div>
  ```

- [x] **P14.1.2** CSS для кнопки:
  ```css
  .composer-dock-new {
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 6px;
    background: var(--staff-accent-soft, #dbe8f8);
    color: var(--staff-accent, #224a7a);
    text-decoration: none;
    font-weight: 600;
    white-space: nowrap;
  }
  .composer-dock-new:hover {
    background: var(--staff-accent, #224a7a);
    color: #fff;
  }
  ```

- [x] **P14.1.3** Ссылка ведёт на `/author/messages` (НЕ `/author/messages/new`) — это страница со списком + dock с пустой формой (новое сообщение). При переходе dock сбрасывается в режим «Новое сообщение».

- [x] **P14.1.4** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P14

1. В режиме «Редактирование» — в header dock есть кнопка «+ Новое»
2. В режиме «Новое сообщение» — кнопки нет (и так новое)
3. Клик по «+ Новое» → переход на `/author/messages` → dock сбрасывается
4. Кнопка не ломает layout header-а (inline, компактная)

---

## Блок P15 — Поддержка LOG_FILE для записи логов в файл (2026-03-29) [x]

### Контекст

Пользователь добавил `LOG_FILE=api.log` в `.env`. Сейчас логирование идёт **только в stdout** (StreamHandler). Нужно добавить поддержку переменной `LOG_FILE` — если задана, логи пишутся дополнительно в файл.

**Файлы:**
- `src/pitchcopytrade/core/config.py`
- `src/pitchcopytrade/core/logging.py`

### P15.1 — Добавить `log_file` в Settings и LoggingSettings `[x]`

**Что должен сделать worker:**

- [x] **P15.1.1** В `config.py` добавить env-переменную:
  ```python
  # В class EnvName:
  LOG_FILE = "LOG_FILE"
  ```

- [x] **P15.1.2** В `class Settings` добавить поле:
  ```python
  log_file: str | None = Field(default=None, alias=EnvName.LOG_FILE)
  ```

- [x] **P15.1.3** В `class LoggingSettings` добавить поле:
  ```python
  file_path: str | None = None
  ```

- [x] **P15.1.4** В `Settings.logging` property добавить `file_path`:
  ```python
  @property
  def logging(self) -> LoggingSettings:
      return LoggingSettings(level=self.log_level, json_logs=self.log_json, file_path=self.log_file)
  ```

---

### P15.2 — FileHandler в `configure_logging()` `[x]`

**Что должен сделать worker:**

- [x] **P15.2.1** В `src/pitchcopytrade/core/logging.py` — если `settings.file_path` задан, добавить `FileHandler` с тем же форматом:
  ```python
  def configure_logging(settings: LoggingSettings) -> None:
      root_logger = logging.getLogger()
      level = getattr(logging, settings.level, logging.INFO)
      root_logger.setLevel(level)

      # Формат — один для всех handler-ов
      if settings.json_logs:
          formatter = JsonLogFormatter()
      else:
          formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

      root_logger.handlers.clear()

      # stdout handler (всегда)
      stdout_handler = logging.StreamHandler(sys.stdout)
      stdout_handler.setFormatter(formatter)
      root_logger.addHandler(stdout_handler)

      # file handler (опционально)
      if settings.file_path:
          file_handler = logging.FileHandler(settings.file_path, encoding="utf-8")
          file_handler.setFormatter(formatter)
          root_logger.addHandler(file_handler)
  ```

- [x] **P15.2.2** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P15

1. Без `LOG_FILE` в `.env` — поведение не меняется (только stdout)
2. С `LOG_FILE=api.log` — логи пишутся и в stdout, и в файл `api.log`
3. Формат одинаковый в обоих handler-ах (plain или JSON, в зависимости от `LOG_JSON`)
4. Файл создаётся автоматически при старте, дописывается (append mode)

---

## Блок P16 — Fix `_normalize_provider_payload` для реального формата meta.pbull.kz (2026-03-29) [x]

### Контекст

Провайдер `meta.pbull.kz/api/marketData/forceDataSymbol?symbol=GAZP` возвращает payload с **вложенной структурой**. Текущая функция `_normalize_provider_payload()` ищет только плоские ключи (`lastPrice`, `price`, `close`) и **не находит** данные из реального ответа.

Реальная структура (пример для GAZP):

```python
{
    "symbol": "GAZP",           # ← symbol работает ✓
    "short_name": "GAZP",
    "description": "Gazprom",
    "currency_id": "USD",       # ← валюта конвертированная, НЕ реальная
    "currency_code": "USD",     # ← то же
    "trade": {                  # ← ВЛОЖЕННЫЙ объект с последней сделкой
        "price": "137.32",      # ← LAST PRICE (RUB)
        "size": "10",
        "time": "1774778083",
        "data-update-time": "1774778083.815627"
    },
    "prev-daily-bar": {         # ← ВЛОЖЕННЫЙ: предыдущий дневной бар
        "close": "137.09",      # ← prev close (для расчёта change)
        "high": "137.57",
        "low": "136.55",
        "open": "137.5",
        "volume": "5431630"
    },
    "daily-bar": {              # ← ВЛОЖЕННЫЙ: текущий дневной бар
        "close": "137.32",
        "high": "137.45",
        "low": "136.66",
        "open": "136.66",
        "volume": "1378310"
    },
    "lp": 1.68214032,          # ← конвертированная цена в USD (НЕ использовать)
    "chp": 0.18,               # ← % изменения (тоже в USD контексте)
    "ch": 0.003,               # ← абс. изменение (в USD — НЕ использовать)
    "prev_close_price": 1.6790783200000001,  # ← USD
    ...
}
```

**Проблема:** Цены в RUB находятся в `trade.price` и `prev-daily-bar.close` / `daily-bar.close`. Плоские ключи `lp`, `ch`, `chp` — это конвертированные USD-значения, бесполезны для MOEX.

**Файл:** `src/pitchcopytrade/services/instruments.py`

### P16.1 — Вспомогательная функция `_extract_nested_float()` `[x]`

**Что должен сделать worker:**

- [x] **P16.1.1** Добавить helper для извлечения float из вложенного dict:
  ```python
  def _nested_float(data: dict, path: str) -> float | None:
      """Extract float from nested dict by dot-path, e.g. 'trade.price'."""
      keys = path.split(".")
      current = data
      for key in keys:
          if not isinstance(current, dict):
              return None
          current = current.get(key)
          if current is None:
              return None
      return _coerce_float(current)
  ```

- [x] **P16.1.2** Аналогичный helper для текстовых значений:
  ```python
  def _nested_text(data: dict, path: str) -> str:
      """Extract string from nested dict by dot-path, e.g. 'trade.time'."""
      keys = path.split(".")
      current = data
      for key in keys:
          if not isinstance(current, dict):
              return ""
          current = current.get(key)
          if current is None:
              return ""
      return str(current).strip()
  ```

---

### P16.2 — Переписать `_normalize_provider_payload()` `[x]`

**Что должен сделать worker:**

- [x] **P16.2.1** Заменить тело функции `_normalize_provider_payload()`. Логика поиска:

  **last_price** (приоритет — реальная цена в RUB из вложенных объектов):
  1. `trade.price` (последняя сделка — наилучший вариант)
  2. `daily-bar.close` (закрытие текущего дня)
  3. плоские fallback: `lastPrice`, `last_price`, `price`, `close`, `ltp`, `marketPrice`

  **prev_close** (для расчёта change):
  1. `prev-daily-bar.close`
  2. плоские fallback: `prev_close_price`, `previousClose`

  **change_abs** (расчёт):
  1. Если есть `last_price` и `prev_close` → `change_abs = last_price - prev_close`
  2. Иначе плоские fallback: `change`, `delta`, `priceChange`, `change_value`, `absChange`

  **change_pct** (расчёт):
  1. Если есть `last_price` и `prev_close` и `prev_close != 0` → `change_pct = (last_price - prev_close) / prev_close * 100`, округлить до 2 знаков
  2. Иначе плоские fallback: `changePercent`, `change_pct`, `change_percentage`, `percentChange`, `chp`

  **currency**:
  1. `currency_code`
  2. плоские fallback: `currency`, `curr`, `priceCurrency`

  **updated_at** (timestamp последней сделки):
  1. `trade.time`
  2. `trade.data-update-time`
  3. плоские fallback: `updatedAt`, `updated_at`, `time`, `timestamp`, `datetime`, `lastUpdate`

  **symbol** — без изменений (уже работает).

- [x] **P16.2.2** Полный код новой функции:
  ```python
  def _normalize_provider_payload(ticker: str, payload: object, *, source: str) -> InstrumentQuote | None:
      data = _first_text(_unwrap_payload(payload), ticker)
      if not isinstance(data, dict):
          return None

      # --- symbol (уже работает) ---
      symbol = _first_text(
          data, "symbol", "ticker", "secCode", "sec_code", "code", "short_name",
      )

      # --- last_price: предпочитаем вложенные RUB-цены ---
      last_price = (
          _nested_float(data, "trade.price")
          or _nested_float(data, "daily-bar.close")
          or _first_float(data, "lastPrice", "last_price", "price", "close", "ltp", "marketPrice")
      )

      # --- prev_close: для расчёта change ---
      prev_close = (
          _nested_float(data, "prev-daily-bar.close")
          or _first_float(data, "prev_close_price", "previousClose")
      )

      # --- change_abs ---
      if last_price is not None and prev_close is not None:
          change_abs = round(last_price - prev_close, 6)
      else:
          change_abs = _first_float(data, "change", "delta", "priceChange", "change_value", "absChange")

      # --- change_pct ---
      if last_price is not None and prev_close is not None and prev_close != 0:
          change_pct = round((last_price - prev_close) / prev_close * 100, 2)
      else:
          change_pct = _first_float(data, "changePercent", "change_pct", "change_percentage", "percentChange", "chp")

      # --- currency ---
      currency = _first_text(data, "currency_code", "currency", "curr", "priceCurrency", "currency_id")

      # --- updated_at ---
      updated_at = (
          _nested_text(data, "trade.time")
          or _nested_text(data, "trade.data-update-time")
          or _first_text(data, "updatedAt", "updated_at", "time", "timestamp", "datetime", "lastUpdate")
      )

      status = _first_text(data, "status", "state", "tradeStatus") or ("ok" if last_price is not None else "empty")

      if last_price is None and change_abs is None and change_pct is None and symbol == "" and len(data) == 0:
          return None

      return InstrumentQuote(
          ticker=ticker,
          source=source,
          status=status,
          last_price=last_price,
          change_pct=change_pct,
          change_abs=change_abs,
          currency=currency,
          updated_at=updated_at,
          provider_symbol=symbol or ticker,
          payload=data,
      )
  ```

- [x] **P16.2.3** Добавить debug-лог в начало функции для отладки:
  ```python
  def _normalize_provider_payload(ticker: str, payload: object, *, source: str) -> InstrumentQuote | None:
      data = _first_text(_unwrap_payload(payload), ticker)
      if not isinstance(data, dict):
          logger.warning("Provider payload for %s is not a dict: %s", ticker, type(data))
          return None
      logger.debug(
          "Normalizing provider payload for %s: keys=%s, has_trade=%s, has_daily_bar=%s",
          ticker,
          list(data.keys())[:10],
          "trade" in data,
          "daily-bar" in data,
      )
      # ... остальной код
  ```

- [x] **P16.2.4** `python3 -m compileall src tests` — без ошибок

---

### P16.3 — Убрать `_first_text` на первой строке парсинга `[x]`

**Что должен сделать worker:**

- [x] **P16.3.1** В текущем коде строка 231:
  ```python
  data = _first_text(_unwrap_payload(payload), ticker)
  ```
  Это **баг**: `_first_text(dict, str)` пытается сделать `dict.get("GAZP")` — вернёт `""` для любого dict payload. Функция задумана для поиска текстового значения по ключам, а здесь передаётся unwrapped dict.

  **Исправить на:**
  ```python
  data = _unwrap_payload(payload)
  ```
  Просто unwrap без `_first_text`. Переменная `data` должна быть dict, проверка `isinstance(data, dict)` на следующей строке уже есть.

---

### Acceptance P16

1. Для payload от `meta.pbull.kz` с вложенными `trade`, `daily-bar`, `prev-daily-bar` — корректно извлекается `last_price` из `trade.price` (137.32, не 1.68)
2. `change_abs` = `trade.price - prev-daily-bar.close` (0.23, не 0.003)
3. `change_pct` рассчитан из RUB-цен (~0.17%, не из USD chp)
4. `currency` = `"USD"` (из `currency_code`) — API так отдаёт, оставляем как есть
5. `updated_at` = timestamp из `trade.time`
6. Для payload другого формата (плоские ключи) — fallback работает как прежде
7. `_first_text(_unwrap_payload(...), ticker)` **заменён** на `_unwrap_payload(...)` — баг устранён
8. `python3 -m compileall src tests` — без ошибок

---

## Блок P19 — Fix: тесты не соответствуют реальному формату API meta.pbull.kz (2026-03-29)

### Контекст

API `meta.pbull.kz` оборачивает данные под ключом тикера: `{"GAZP": {"symbol": "GAZP", "trade": {...}, ...}}`. Строка 230 `data = _unwrap_payload(payload)[ticker]` — **корректна** для реального API (котировки приходят). Но **2 теста падают**, потому что mock-и передают данные БЕЗ обёртки тикером.

Дополнительно: `[ticker]` может вызвать `KeyError` если API вернёт ответ без ключа тикера (например, ошибку). Нужен безопасный доступ.

**Падающие тесты:**
- `test_get_instrument_quote_normalizes_provider_payload` — mock: `{"data": {"symbol": "NVTK", ...}}`
- `test_get_instrument_quote_prefers_nested_trade_fields` — mock: `{"symbol": "GAZP", "trade": {...}, ...}`

**Файлы:**
- `src/pitchcopytrade/services/instruments.py` — строка 230
- `tests/test_instruments_service.py` — строки 68-80, 101-122

### P19.1 — Безопасный доступ по тикеру в `_normalize_provider_payload` `[x]`

**Что должен сделать worker:**

- [x] **P19.1.1** Строка 230 — заменить `[ticker]` на безопасный `.get()` с fallback:

  **Текущий код:**
  ```python
  data = _unwrap_payload(payload)[ticker]
  ```

  **Заменить на:**
  ```python
  unwrapped = _unwrap_payload(payload)
  if isinstance(unwrapped, dict) and ticker in unwrapped and isinstance(unwrapped[ticker], dict):
      data = unwrapped[ticker]
  else:
      data = unwrapped
  ```

  **Логика:** если unwrapped dict содержит ключ = тикеру (реальный API: `{"GAZP": {...}}`) — берём вложенный dict. Иначе используем unwrapped как есть (для совместимости с другими форматами и тестами).

---

### P19.2 — Обновить тесты: mock-и должны соответствовать реальному формату API `[x]`

**Что должен сделать worker:**

- [x] **P19.2.1** Тест `test_get_instrument_quote_normalizes_provider_payload` (строки 68-80) — обернуть mock-данные под ключ тикера:

  **Текущий mock:**
  ```python
  _FakeAsyncClient(
      {
          "data": {
              "symbol": "NVTK",
              "lastPrice": "123.45",
              ...
          }
      }
  )
  ```

  **Заменить на:**
  ```python
  _FakeAsyncClient(
      {
          "NVTK": {
              "symbol": "NVTK",
              "lastPrice": "123.45",
              "changePercent": "1.25",
              "change": "1.53",
              "currency": "RUB",
              "updatedAt": "2026-03-26T10:00:00+00:00",
          }
      }
  )
  ```

- [x] **P19.2.2** Тест `test_get_instrument_quote_prefers_nested_trade_fields` (строки 101-122) — обернуть под ключ тикера:

  **Текущий mock:**
  ```python
  _FakeAsyncClient(
      {
          "symbol": "GAZP",
          "short_name": "GAZP",
          ...
      }
  )
  ```

  **Заменить на:**
  ```python
  _FakeAsyncClient(
      {
          "GAZP": {
              "symbol": "GAZP",
              "short_name": "GAZP",
              "description": "Gazprom",
              "trade": {
                  "price": "137.32",
                  "time": "1774778083",
              },
              "prev-daily-bar": {
                  "close": "137.09",
              },
              "daily-bar": {
                  "close": "137.32",
              },
              "currency_code": "RUB",
              "lp": 1.68214032,
              "chp": 0.18,
              "ch": 0.003,
              "prev_close_price": 1.6790783200000001,
          }
      }
  )
  ```

- [x] **P19.2.3** Запустить тесты: `python -m pytest tests/test_instruments_service.py -q` — все должны пройти.

- [x] **P19.2.4** Полный test suite: `python -m pytest -q` — 0 failures.

---

### Acceptance P19

1. Строка 230: безопасный доступ — если `unwrapped[ticker]` существует и является dict → используем его, иначе → `unwrapped` как есть
2. Mock-и в тестах обёрнуты под ключ тикера (`{"NVTK": {...}}`, `{"GAZP": {...}}`) — соответствуют реальному API
3. Реальный API продолжает работать (GAZP=137.45, LKOH=5640.5, etc.)
4. Полный test suite — 0 failures

---

## Блок P17 — Автоподстановка цены при выборе инструмента (2026-03-29)

### Контекст

При выборе инструмента в autocomplete popup (`structured_instrument_query`) заполняются ticker, name, id — но поле **«Цена»** (`structured_price`) остаётся пустым. Массив `instruments` (из backend `build_instrument_payloads()`) уже содержит `last_price` для каждого инструмента. Нужно автоматически подставлять цену при выборе.

**Файл:** `src/pitchcopytrade/web/templates/author/_composer_form.html`

### P17.1 — Автозаполнение цены при клике на инструмент `[x]`

**Что должен сделать worker:**

- [x] **P17.1.1** В click handler кнопки autocomplete (примерно строка 376-390 в `_composer_form.html`) — после установки ticker/name/id, добавить подстановку цены в `structured_price`:

  **Текущий код:**
  ```javascript
  button.addEventListener("click", function () {
    if (instrumentInput) instrumentInput.value = `${item.ticker || ""} · ${item.name || ""}`.trim();
    if (instrumentIdInput) instrumentIdInput.value = item.id || "";
    if (hiddenTicker) hiddenTicker.value = item.ticker || "";
    if (hiddenName) hiddenName.value = item.name || "";
    clearInstrumentPopup();
    syncAmount();
  });
  ```

  **Заменить на:**
  ```javascript
  button.addEventListener("click", function () {
    if (instrumentInput) instrumentInput.value = `${item.ticker || ""} · ${item.name || ""}`.trim();
    if (instrumentIdInput) instrumentIdInput.value = item.id || "";
    if (hiddenTicker) hiddenTicker.value = item.ticker || "";
    if (hiddenName) hiddenName.value = item.name || "";

    // Автоподстановка цены из котировки — только если поле пустое
    if (structuredPrice && !structuredPrice.value && item.last_price != null) {
      structuredPrice.value = item.last_price;
    }

    clearInstrumentPopup();
    syncAmount();
  });
  ```

  **Важно:** `structuredPrice` — это ссылка на `<input name="structured_price" data-structured-price>`, которая уже объявлена выше в JS-коде (проверить что переменная `structuredPrice` действительно ссылается на `document.querySelector('[data-structured-price]')` или аналогичный селектор). `syncAmount()` уже вызывается после — пересчитает сумму с новой ценой.

- [x] **P17.1.2** Убедиться что `item.last_price` доступен в JS. В backend `build_instrument_payload()` уже возвращает `last_price` в payload (строка 129 в `instruments.py`). Проверить что `_instrument_items | tojson` включает это поле.

- [x] **P17.1.3** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P17

1. При выборе инструмента из autocomplete — поле «Цена» заполняется текущей ценой из `last_price`
2. Если поле «Цена» уже содержит значение — цена НЕ перезаписывается
3. После подстановки цены — `syncAmount()` пересчитывает сумму (цена × количество)
4. Если у инструмента `last_price = null` (провайдер выключен/недоступен) — поле остаётся пустым
5. `python3 -m compileall src tests` — без ошибок

---

## Блок P18 — Stub-заглушка: автоактивация подписки без оплаты (2026-03-29)

### Контекст

Провайдер оплаты ещё не подключён (`SBP_PROVIDER=stub_manual`). Сейчас при checkout подписка создаётся со статусом `PENDING` и **навсегда зависает** — клиент не получает сообщения (рассылка только для `ACTIVE`/`TRIAL`).

Нужна **заглушка для MVP**: при `SBP_PROVIDER=stub_manual` платёж подтверждается автоматически, подписка сразу активируется. Отдельно — поддержка бесплатных продуктов (`price_rub=0`): подписка без создания Payment.

**Файл:** `src/pitchcopytrade/services/public.py`

### P18.1 — Auto-confirm для stub_manual: Payment=PAID, Subscription=ACTIVE сразу при создании `[x]`

**Что должен сделать worker:**

- [x] **P18.1.1** В функции `_create_checkout_records()` (строка ~553) — при создании Payment и Subscription сразу ставить подтверждённые статусы (эта функция вызывается **только** для `stub_manual`, TBank идёт через `_create_tbank_checkout_records`):

  **Текущий код (строки 567-614):**
  ```python
  payment = Payment(
      ...
      status=PaymentStatus.PENDING,
      ...
  )
  ...
  subscription = Subscription(
      ...
      status=SubscriptionStatus.PENDING,
      ...
  )
  ```

  **Заменить на:**
  ```python
  payment = Payment(
      user=user,
      product=product,
      promo_code=promo_code,
      provider=PaymentProvider.STUB_MANUAL,
      status=PaymentStatus.PAID,
      amount_rub=product.price_rub,
      discount_rub=pricing.discount_rub if pricing is not None else 0,
      final_amount_rub=pricing.final_amount_rub if pricing is not None else product.price_rub,
      currency="RUB",
      stub_reference=_build_stub_reference(product.slug),
      provider_payload={
          "flow": source,
          "lead_source_name": lead_source_name,
          "promo_code": promo_code.code if promo_code is not None else None,
          "auto_confirmed": True,
      },
      expires_at=timestamp + timedelta(hours=24),
      confirmed_at=timestamp,
  )
  ```

  И для Subscription:
  ```python
  sub_status = SubscriptionStatus.TRIAL if product.trial_days > 0 else SubscriptionStatus.ACTIVE

  subscription = Subscription(
      user=user,
      product=product,
      payment=payment,
      status=sub_status,
      lead_source=lead_source,
      autorenew_enabled=product.autorenew_allowed,
      is_trial=product.trial_days > 0,
      manual_discount_rub=0,
      applied_promo_code=promo_code,
      start_at=timestamp,
      end_at=timestamp + _billing_delta(product.billing_period),
  )
  ```

- [x] **P18.1.2** Добавить `import logging` и `logger = logging.getLogger(__name__)` в начало файла (если ещё нет). Добавить лог после commit:
  ```python
  logger.info(
      "Stub auto-confirm: payment=%s subscription=%s user=%s product=%s",
      payment.id, subscription.id, user.id, product.slug,
  )
  ```

---

### P18.2 — Бесплатный продукт: `price_rub == 0` → подписка без Payment `[x]`

**Что должен сделать worker:**

- [x] **P18.2.1** В начале `_create_checkout_records()` — добавить ветку для бесплатного продукта. Если `final_price == 0` (либо `product.price_rub == 0`, либо промокод дал 100% скидку) → создать Subscription со статусом `ACTIVE` без Payment:

  ```python
  async def _create_checkout_records(...) -> CheckoutResult:
      # --- Согласия (нужны в любом случае) ---
      consents = [
          record_user_consent(
              user=user, document=document, source=source,
              payment=None, accepted_at=timestamp, ip_address=ip_address,
          )
          for document in required_documents
      ]

      # --- Определяем итоговую цену ---
      pricing = apply_promo_to_amount(promo_code, amount_rub=product.price_rub) if promo_code is not None else None
      final_price = pricing.final_amount_rub if pricing is not None else product.price_rub

      # --- Бесплатный продукт: подписка без платежа ---
      if final_price == 0:
          subscription = Subscription(
              user=user, product=product, payment=None,
              status=SubscriptionStatus.ACTIVE,
              lead_source=lead_source,
              autorenew_enabled=False, is_trial=False,
              manual_discount_rub=0, applied_promo_code=promo_code,
              start_at=timestamp,
              end_at=timestamp + _billing_delta(product.billing_period),
          )
          repository.add(subscription)
          await repository.commit()
          await repository.refresh(subscription)
          logger.info("Free checkout: subscription=%s user=%s product=%s", subscription.id, user.id, product.slug)
          return CheckoutResult(
              user=user, payment=None, subscription=subscription,
              required_documents=required_documents, applied_promo_code=promo_code,
          )

      # --- Платный продукт (существующий код с auto-confirm из P18.1) ---
      ...
  ```

- [x] **P18.2.2** Проверить что `CheckoutResult.payment` допускает `None`. Текущий dataclass:
  ```python
  @dataclass(slots=True)
  class CheckoutResult:
      user: User
      payment: Payment  # ← сделать Optional
      ...
  ```
  **Исправить на:**
  ```python
  @dataclass(slots=True)
  class CheckoutResult:
      user: User
      payment: Payment | None
      subscription: Subscription
      required_documents: list[LegalDocument]
      applied_promo_code: PromoCode | None = None
      payment_url: str | None = None
      provider_payment_id: str | None = None
  ```

- [x] **P18.2.3** Проверить все места, где используется `CheckoutResult.payment` — убедиться что корректно обрабатывают `None`:
  - `routes/public.py` — после `create_stub_checkout()`
  - `routes/app.py` — после `create_telegram_stub_checkout()`
  - шаблоны checkout success — если отображают `payment.stub_reference` или `payment.id`, обернуть в `{% if result.payment %}`

---

### P18.3 — Маршруты checkout: корректная обработка auto-confirm и free `[x]`

**Что должен сделать worker:**

- [x] **P18.3.1** В `routes/public.py` POST `/checkout/{product_id}` — после успешного `create_stub_checkout()`:
  - Если `result.subscription.status` in (`ACTIVE`, `TRIAL`) → показать success page (подписка активна)
  - Если `PENDING` → показать «ожидание оплаты» (текущее поведение, для будущего TBank)

- [x] **P18.3.2** В `routes/app.py` POST `/app/checkout/{product_id}` — аналогичная логика.

- [x] **P18.3.3** `python3 -m compileall src tests` — без ошибок

---

### Acceptance P18

1. `SBP_PROVIDER=stub_manual` + `price_rub > 0` → при checkout Payment=PAID, Subscription=ACTIVE сразу (auto-confirm)
2. `price_rub == 0` (или промокод дал 100% скидку) → Subscription=ACTIVE без Payment
3. Клиент с ACTIVE подпиской **получает сообщения** через рассылку (`notifications.py` проверяет `ACTIVE`/`TRIAL`)
4. Лог фиксирует auto-confirm и free checkout
5. Checkout success page корректно отображается для обоих случаев
6. При подключении TBank (`SBP_PROVIDER=tbank`) — логика не затрагивается (auto-confirm только в `_create_checkout_records`, TBank идёт через `_create_tbank_checkout_records`)
7. `CheckoutResult.payment` допускает `None`; шаблоны и routes корректно обрабатывают это
8. `python3 -m compileall src tests` — без ошибок
