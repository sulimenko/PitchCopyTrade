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
- `tests/test_recommendations.py`
- `tests/test_storage_local.py`
- `tests/test_worker_baseline.py`
- `tests/test_admin_ui.py`
- `tests/test_payment_sync.py`
- `tests/test_subscriber_reminders.py`

### План работы для worker по крупным итерациям

Итерации должны выполняться по порядку. Не надо смешивать все сразу.

- [ ] **K1** Итерация A: переписать schema, SQLAlchemy models и file-mode storage под единую сущность `messages`
  - удалить recommendation-модели и child-таблицы;
  - завести `Message` model;
  - пересобрать `deploy/schema.sql`;
  - пересобрать file datasets и seed data;
  - перевести `notification_log` на `message_id`.
  Acceptance:
  - DB schema и file-mode dataset больше не содержат `recommendations*`;
  - `messages` есть и соответствует target schema;
  - `tests/test_db_models.py` и `tests/test_file_repositories.py` обновлены и проходят.

- [ ] **K2** Итерация B: переписать repository и service layer на `messages`
  - удалить `Recommendation*` из contracts/repositories/services;
  - завести message-centric CRUD и validation;
  - реализовать backend rules для `type`, `deliver`, `status`, HTML sanitize, `thread`, `parent`.
  Acceptance:
  - author/moderation/access/publishing/notification services не импортируют `Recommendation*`;
  - `tests/test_author_services.py`, `tests/test_lifecycle.py`, `tests/test_publishing_worker.py` обновлены и проходят.

- [ ] **K3** Итерация C: удалить Form 1 и перевести author/moderation UI на новый editor
  - оставить только message-based editor;
  - реализовать только новый flow с `text`, `document`, `deal`, `mixed`;
  - удалить UI-зависимости от `summary`, `thesis`, `market_context`, `legs`, `attachments`, `messages` как отдельных сущностей.
  Acceptance:
  - в author UI больше нет старой формы;
  - moderation detail читает `messages.text/documents/deals`;
  - `tests/test_author_ui.py` и `tests/test_moderation_ui.py` обновлены и проходят.

- [ ] **K4** Итерация D: перевести subscriber feed, Mini App, Telegram и worker-delivery на `messages`
  - переписать app feed/detail;
  - переписать notification formatter;
  - переписать Telegram broadcast;
  - scheduler публикует `messages.status = scheduled`.
  Acceptance:
  - Mini App читает `Message`, а не `Recommendation`;
  - Telegram notification/broadcast формируется из `text/documents/deals`;
  - `tests/test_notifications_service.py`, `tests/test_access_delivery.py`, `tests/test_subscriber_reminders.py`, `tests/test_worker_baseline.py` обновлены и проходят.

- [ ] **K5** Итерация E: зачистить legacy terminology, seed/docs/tests и довести проект до консистентного состояния
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
- можно оставить временно старые route paths `/author/recommendations/*`, если переименование path сейчас слишком дорого, но данные и формы должны работать через `Message`.

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
- `tests/test_recommendations.py`
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
