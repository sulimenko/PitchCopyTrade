# PitchCopyTrade — Active Tasks
> Обновлено: 2026-03-26
> Этот файл хранит только текущий backlog нового цикла MVP clean-up.

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
- [x] **A2** Переписать `doc/task.md` только под текущий backlog
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

- [ ] **D1** Пересобрать hero каталога Mini App
  - меньше онбординга;
  - больше карточек стратегии;
  - быстрее переход к выбору.

- [ ] **D2** Пересобрать карточку стратегии
  - автор;
  - value proposition;
  - риск;
  - горизонт;
  - минимальный капитал;
  - главный CTA;
  - без перегруза вторичными действиями.

- [ ] **D3** Пересобрать `strategy_detail` под структурный narrative
  - hero;
  - thesis;
  - mechanics;
  - risk;
  - tariffs;
  - FAQ/documents.

- [ ] **D4** Подготовить content contract для strategy detail
  - решить, что живет в structured fields;
  - что временно допустимо держать в `full_description`;
  - как это редактируется staff/author контуром.

- [ ] **D5** Использовать `Straddle.pdf` как один из reference-материалов
  - взять сильные части narrative;
  - не копировать презентационный стиль как есть.

- [ ] **D6** Проверить mobile-first behavior для Mini App
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

- [ ] **E1** Сделать backend adapter для `meta.pbull.kz`
- [ ] **E2** Нормализовать provider response в продуктовый JSON contract
- [ ] **E3** Подключить quote data в те view/flows, где она реально нужна
  - карточка стратегии;
  - detail стратегии;
  - author recommendation editor;
  - инструментальный picker.
- [ ] **E4** Добавить cache TTL и fallback behavior
- [ ] **E5** Решить расхождение между `storage/seed/json/instruments.json` и дрейфующим `storage/runtime/json/instruments.json`

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

- [ ] **F1** Разобрать desktop/mobile расхождение для `Создать заявку на оплату`
  - воспроизведение;
  - network trace;
  - response body;
  - session/cookie context;
  - различие browser vs Telegram WebView.

- [ ] **F2** Разобрать `Internal Server Error` при создании подписки из Mini App
  - проверить путь `payment -> subscription -> commit -> response`;
  - отловить controlled business errors;
  - убрать raw `500`.

- [ ] **F3** Разобрать transient JSON parse error после login redirect на `/admin/dashboard`
  - capture response headers/body;
  - capture browser console;
  - понять, был ли это truncated response, bad fetch, cached partial payload или auth/session race.

- [ ] **F4** Перевести navigation contract на one-webview behavior
  - без лишних bot message hops;
  - без ощущения "каждый экран — новая закладка".

- [ ] **F5** Переделать bot `/help`
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

- [ ] **G1** Собрать список canonical preview URL для дизайна и верстки
- [ ] **G2** Собрать список canonical real-device сценариев для Telegram
- [ ] **G3** Зафиксировать минимум smoke-check для каждой surface:
  - public;
  - miniapp;
  - admin;
  - author.

Acceptance:
- у следующего исполнителя есть короткий набор URL и сценариев для ручной проверки;
- локальный browser preview и реальный Telegram check описаны раздельно.
