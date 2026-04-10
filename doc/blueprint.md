# PitchCopyTrade — Blueprint
> Обновлено: 2026-04-10
> Статус: canonical current contract for MVP clean-up

## 1. Политика документа

Этот файл описывает только:
- текущее состояние продукта;
- целевой контракт ближайшего цикла;
- правила, обязательные для следующих изменений.

Исторические блоки, закрытые фазы и старые решения сюда не переносятся. Их архивом считается git history.

## 2. Текущее состояние

### 2.1 Поверхности продукта

В проекте есть пять рабочих контуров:
- `public web` на `/catalog`, `/catalog/strategies/{slug}`, `/checkout/{product_ref}`;
- `miniapp web` на `/app/*`;
- `staff admin` на `/admin/*`;
- `staff author` на `/author/*`;
- `bot` и `worker` как отдельные runtime-сервисы.

### 2.2 Технологический контур

- backend: `FastAPI` + `Jinja2`;
- bot: `aiogram`;
- worker: polling loop;
- storage modes:
  - `db` как основной product-critical режим;
  - `file` как вторичный local preview / compatibility smoke режим.

### 2.3 Важные факты для текущего цикла

- основной runtime priority для product-critical сценариев = `APP_DATA_MODE=db`;
- `file`-mode остается вторичным compatibility/preview/smoke режимом;
- локальный запуск без Docker возможен, но не заменяет production-like проверку на PostgreSQL schema path;
- для старта `api` обязательны `APP_SECRET_KEY` и `INTERNAL_API_SECRET`;
- `file`-mode читает состояние из `storage/runtime/*`, а не напрямую из `storage/seed/*`;
- `storage/runtime/*` считается изменяемым runtime-слоем и перед воспроизводимыми проверками должен сбрасываться;
- Mini App first screen contract = `/app/catalog`, help contract = `/app/help`;
- author/public/subscriber contour перешел на message-centric модель `messages`;
- quote provider подключается backend-адаптером и не должен блокировать SSR;
- внутри docs больше нельзя писать "все закрыто" без сверки с [doc/review.md](/Users/alexey/site/PitchCopyTrade/doc/review.md).

## 3. Цель текущего цикла

Текущий цикл не про расширение сущностей. Он про чистку MVP subscriber contour:
- сделать Mini App понятным и быстрым;
- перенести первый экран на витрину стратегий;
- вынести помощь в отдельный `/help` сценарий;
- усилить описание стратегий как продающий и объясняющий экран;
- подключить real-time market data по тикерам;
- убрать основные product/runtime сбои вокруг подписки, оплаты и навигации.

После последнего review критичный открытый scope не должен трактоваться как новый продуктовый redesign. Это короткий stabilization pass: Telegram HTML newline handling, invited-user status cleanup, preview links и мелкие checkout-copy/context исправления.

## 4. Canonical subscriber contract

### 4.1 Стартовый сценарий Mini App

Основной вход клиента:
1. пользователь открывает Mini App из Telegram;
2. Mini App подтверждает профиль по Telegram;
3. первым экраном открывается витрина стратегий на `/app/catalog`;
4. помощь открывается отдельным экраном `/app/help`;
5. дальнейшая навигация остается внутри одного webview.

Не является целевым поведением:
- старт с `/app/status` как основного entry point;
- повторный онбординг на первом экране;
- bot-команды, которые создают новый message-thread вместо перехода в существующий in-app сценарий;
- помощь в виде еще одного текстового bot message без перехода в UI.

### 4.2 Навигация в одной вкладке / одном webview

Canonical rule:
- Mini App должен ощущаться как одно приложение, а не как набор внешних ссылок.

Это означает:
- из бота открывается один основной web_app entry;
- далее пользователь ходит по внутренним маршрутам приложения;
- `/help` и витрина открываются внутри того же webview;
- повторные bot-команды не должны быть обязательным способом навигации;
- если нужен возврат, используется browser/webview history внутри приложения, а не новое сообщение в чате.

### 4.3 Mini App menu contract

Постоянное верхнее меню Mini App должно быть небольшим и предсказуемым.

Primary tabs:
- `Каталог`
- `Подписки`
- `История`

Правила:
- эти три пункта присутствуют всегда на subscriber-facing Mini App surfaces;
- один из них всегда является активным;
- `Статус`, `Помощь`, `Оплаты`, `Напоминания` не должны жить в primary menu;
- они могут оставаться secondary screens или локальными page actions.
- бизнесово неготовые пункты не удаляются из кода насовсем;
- до отдельного product go-ahead они должны быть спрятаны в шаблонах через комментарии или equivalent dormant markup, чтобы worker не терял будущие точки возврата.

Контекстный пункт:
- `К стратегии` не является постоянным primary-tab;
- он показывается только в strategy-detail контексте;
- на checkout и других transaction/detail screens переход к стратегии должен быть локальным page action, а не постоянным пунктом меню.
- если checkout открыт из продукта, локальный CTA назад к `К стратегии` должен оставаться видимым и вести на связанный strategy detail route.

Маршрутизация активного состояния:
- `/app/catalog` -> активен `Каталог`
- `/app/strategies/{slug}` -> активен `К стратегии`, при этом `Каталог`, `Подписки`, `История` остаются видимыми
- `/app/checkout/{product_ref}` -> активен ближайший product-flow контекст без появления отдельного active-tab; возврат к стратегии остается локальным CTA
- `/app/subscriptions` и `/app/subscriptions/{id}` -> активны `Подписки`
- `/app/timeline` и `/app/messages/{id}` -> активна `История`
- `/app/payments*` -> не добавляют новый primary-tab; относятся к lifecycle `Подписки`

Preview contract:
- preview routes обязаны рендериться без дополнительных сущностей вроде `product`, если их не требует сам экран;
- navigation partial не должен падать, если текущий screen context не содержит `product`.

### 4.4 Temporary legal-doc visibility contract

До отдельного business sign-off user-facing legal/checkout contract intentionally сокращен.

Текущий временный режим:
- в клиентском checkout и связанных public/Mini App surfaces показывается только `Дисклеймер`;
- остальные документы (`offer`, `privacy`, `payment consent` и т.п.) пока не удаляются из проекта как сущности;
- они должны быть временно спрятаны из пользовательского UI, предпочтительно через комментарии / dormant markup, а не через destructive removal.

Это означает:
- legal data model и backend support можно сохранять;
- user-facing copy, buttons и checkbox-список не должны обещать документы, которые бизнес пока не готов открыть;
- скрытые документы нельзя silently pre-check-ить или auto-submit-ить как уже принятые;
- набор реально принимаемых consent-ов должен совпадать с набором документов, которые пользователь реально видит и подтверждает;
- возврат полного document pack позже должен идти отдельным documented pass, а не случайным partial unhide.

## 5. Canonical contract для витрины и страницы стратегии

### 5.1 Главная страница Mini App

Главная страница Mini App = витрина стратегий.

Она должна отвечать на три вопроса еще до первого scroll:
- какие стратегии доступны;
- чем они различаются;
- куда нажать, чтобы увидеть детали и тарифы.

Первый экран витрины должен содержать:
- ясный заголовок без техничного онбординга;
- компактный trust/context layer:
  - автор;
  - риск;
  - горизонт;
  - минимальный капитал;
  - доступные тарифы или стартовая цена;
- один основной CTA на карточке;
- вторичный CTA только если он не конкурирует с главным действием.

### 5.2 Страница стратегии

Текущий дизайн strategy detail упрощен. Для текущего цикла canonical contract такой:

1. Hero block:
- название стратегии;
- автор;
- риск;
- минимальный капитал;
- основной CTA на подписку;
- secondary CTA только на `Тарифы`.

2. Market snapshot block:
- опциональный quote-strip;
- это supporting context, а не главный продающий экран.

3. Short description block:
- короткое объяснение идеи стратегии;
- текущий UI label = `Короткое описание`.

4. Description / mechanics block:
- раскрытие механики простым языком;
- текущий UI label = `Описание`.

5. Tariffs block:
- список тарифов и CTA на checkout;
- это обязательный коммерческий блок текущего дизайна.

6. Legal visibility:
- на пользовательском экране сейчас visible only `Дисклеймер`;
- остальные legal documents не считаются обязательными для текущего дизайна, пока не будет отдельного business-ready решения.

Для текущего pass-а не являются обязательными на самой strategy detail:
- отдельный `FAQ` section;
- отдельный `market scope` section;
- отдельный `risk` section;
- отдельные audience-блоки `кому подходит / кому не подходит`.
- отдельный user-facing pack из нескольких legal documents.

Если эти блоки возвращаются позже, это должен быть отдельный documented design change, а не случайный partial rollback шаблона.

### 5.3 Материалы-референсы

`Straddle.pdf` и приложенные Figma-screen'ы считаются reference materials, а не эталоном.

Из них допустимо брать:
- четкую структуру "идея -> механизм -> риск -> сценарии";
- сильный one-thesis hero;
- ясную визуальную иерархию;
- ощущение продукта, а не набора форм.

Нельзя слепо переносить:
- слайдовый формат презентации;
- длинные серые текстовые простыни;
- дублирующиеся CTA;
- QR-only платежный сценарий как основной mobile flow;
- макет как есть без адаптации к Mini App и browser preview.

### 5.4 Контентный контракт для strategy detail

Для текущего дизайна минимальный содержательный набор такой:
- `hero_summary` или fallback `short_description`
- `holding_period_note`
- `risk_rule`
- `thesis`
- `mechanics`

Поддерживаемые, но не обязательные в текущем рендере поля:
- `market_scope`
- `entry_logic`
- `instrument_examples`
- `who_is_it_for`
- `who_is_it_not_for`
- `faq_items`

Правило текущего цикла:
- tests и product contract должны проверять только те narrative blocks, которые реально считаются canonical для текущего дизайна;
- если UI intentionally упрощен, тесты обязаны быть пересобраны под этот contract, а не держать старые названия секций.

## 6. Visual identity contract

Текущий ручной pass ввел новый visual mark `D / DESK`.

Для следующего implementation pass нужно соблюдать правило:
- если `D / DESK` принимается как новый UI brand mark, он должен быть нормализован во всех top-level shells;
- нельзя оставлять mixed branding вида `D / DESK` в `base.html`, но `PC / PitchCopyTrade` в `staff_base.html`, `login.html` и preview surfaces.

При этом:
- visual brand slots можно менять независимо от внутренних технических имен;
- юридические/system identifiers не должны переименовываться стихийно вместе с декоративным brand mark.

## 7. Straddle как reference-стратегия

Тема `Straddle` задает полезный пример для PitchCopyTrade:
- стратегия продается не тикером, а механизмом заработка;
- ключевая ценность формулируется как доступ к рыночному сценарию;
- ограничение риска должно быть объяснено отдельно от обещания доходности.

Для карточки/деталей стратегии этого типа целевой narrative:
1. когда стратегия уместна;
2. на чем именно она пытается заработать;
3. чем ограничен риск;
4. как инвестор получает идеи и какие действия от него ожидаются.

В MVP это должно быть изложено на русском, короткими блоками, без презентационного мусора и без ощущения "PDF вставили в web".

## 8. Real-time market data contract

### 8.1 Источник

Canonical source для real-time quote data:
- provider origin задается через `INSTRUMENT_QUOTE_PROVIDER_BASE_URL`;
- в `.env` должен передаваться только origin, например `https://meta.pbull.kz` или internal-network `http://meta-api-1:8000`;
- code-owned endpoint path: `/api/marketData/forceDataSymbol`;
- итоговый request: `{origin}/api/marketData/forceDataSymbol?symbol={ticker}`.

Пример структуры подтвержден файлом `NVTK.json`.

### 8.2 Нормализованный backend contract

Backend не должен прокидывать ответ поставщика в шаблон как есть.

Нужен нормализованный слой с полями уровня продукта:
- `symbol`;
- `display_name`;
- `last_price`;
- `currency`;
- `change_abs`;
- `change_pct`;
- `open_price`;
- `high_price`;
- `low_price`;
- `prev_close_price`;
- `volume`;
- `updated_at`.

### 8.3 Правила интеграции

- источником тикера считается локальный `Instrument.ticker`;
- provider-adapter живет на backend, не в шаблонах;
- сетевой сбой или пустой ответ не должен валить страницу стратегии или форму рекомендации;
- UI должен уметь показать controlled fallback:
  - нет данных;
  - данные устарели;
  - источник временно недоступен;
- нужен короткий cache TTL, чтобы не бить внешний API на каждый рендер страницы.

## 9. Надежность checkout и подписок

### 9.1 Canonical expectation

Нажатие `Создать заявку на оплату` должно:
- одинаково работать в desktop browser, mobile browser и Telegram Mini App;
- либо создавать `payment + subscription` и отдавать ожидаемый следующий экран;
- либо возвращать controlled business error без `500`.

### 9.2 Недопустимые состояния

Недопустимы:
- кнопка не делает ничего на desktop, но работает на mobile;
- `Internal Server Error` при оформлении подписки;
- созданный `payment` без ожидаемого subscriber-facing follow-up;
- "успех" без фактически созданной подписки;
- raw JSON parse error после staff login redirect.

## 10. Локальный preview contract для исследования

Для локальной работы без Docker основной product-critical режим = `db`.

`file` остается быстрым вспомогательным режимом для preview/smoke и верстки, но не является главным критерием готовности.

Локальный контур должен поддерживать:
- публичные GET/POST;
- browser preview public views;
- browser preview Mini App views через demo subscriber link;
- быстрый reset runtime данных.

Для Mini App важно различать:
- `browser preview` для верстки и быстрого редактирования;
- `real Telegram WebApp check` для финальной валидации initData, webview-поведения и deeplink-сценариев.

## 11. Что не входит в текущий цикл

В текущий цикл не входят:
- новый большой staff redesign;
- расширение CRM-like сущностей;
- новая авторизация для subscriber вне Telegram как primary path;
- рефакторинг ради рефакторинга без влияния на MVP subscriber flow.
