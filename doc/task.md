# PitchCopyTrade — Active Tasks
> Обновлено: 2026-04-21

Закрытые задачи этого цикла. Архив закрытых блоков — в `doc/changelog.md`.
Активных задач в текущем цикле не осталось; финальный review-pass 2026-04-21 не открыл новых блоков.

## Правила

- ID: `T-NNN`, сквозная нумерация, не сбрасывается
- Статусы: `[ ]` не начато / `[~]` в работе / `[x]` завершено / `[!]` заблокировано
- Один блок = одна итерация worker → review
- Каждая задача: файлы, поведение до/после, критерии приёмки
- Runtime priority: `APP_DATA_MODE=db`

---

## Блок 1 — Security & DB cleanup

### T-001 Open redirect через `requested_next` [SEC, HIGH]

- [x] Валидировать `requested_next` в `_verify_redirect_url()` (`src/pitchcopytrade/api/routes/app.py`)
- Ограничить до внутренних путей, начинающихся с `/app/`
- Если путь не начинается с `/app/` → заменить на `/app/catalog`
- Убрать `safe='/'` из `quote()` — использовать `safe=''`

### T-002 File upload: magic bytes validation [SEC, MEDIUM]

- [x] В `normalize_attachment_uploads()` (`src/pitchcopytrade/services/author.py`)
- Добавить проверку file signature (magic bytes) помимо content-type header
- PDF: `%PDF` (первые 4 байта), JPEG: `\xff\xd8\xff` (первые 3 байта)
- Если magic bytes не совпадают — `ValueError("Файл не является допустимым PDF или JPG.")`

### T-003 FK-индексы в deploy/schema.sql [DB, HIGH]

- [x] Добавить `CREATE INDEX` на все FK-колонки в `deploy/schema.sql`
- Приоритетные: `payments.user_id`, `subscriptions.user_id`, `subscriptions.product_id`, `user_consents.user_id`
- Формат: `CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table}({column});`

### T-004 Messages table: FK constraints [DB, HIGH]

- [x] Добавить `REFERENCES` constraints в `deploy/schema.sql` для таблицы `messages`
- Колонки: `author` → `author_profiles(id)`, `user_id` → `users(id)`, `moderator_id` → `users(id)`, `strategy_id` → `strategies(id)`, `bundle_id` → `bundles(id)`

### T-005 Оптимизация `get_public_product_by_slug` [DB, MEDIUM]

- [x] В `src/pitchcopytrade/repositories/public.py` метод `get_public_product_by_slug`
- Убрать рекурсивный вызов `get_public_product_by_ref` после загрузки product
- Сделать один запрос с полным набором `selectinload`/`joinedload`

### T-006 `list_user_reminder_events`: SQL фильтрация [DB, MEDIUM]

- [x] В `src/pitchcopytrade/repositories/access.py` метод `list_user_reminder_events`
- Перенести фильтрацию `user_id` из Python в SQL WHERE clause
- Использовать JSON-оператор PostgreSQL: `.where(AuditEvent.payload["user_id"].astext == user_id)`

### T-007 Signature hash validation cleanup [AUTH, LOW]

- [x] В `src/pitchcopytrade/auth/telegram_webapp.py` функция `validate_telegram_webapp_init_data`
- Упростить: signature в основном пути, без signature как fallback
- Добавить тесты обоих путей

---

## Блок 2 — Production regressions: staff auth, author composer, bot delivery

### T-008 Yandex OAuth: убрать dead repository call и нормализовать error UX [AUTH, HIGH]

- [x] Исправить `src/pitchcopytrade/api/routes/auth.py` в `yandex_oauth_callback`
- До исправления:
  - callback вызывает `repository.save_user(user)`, которого нет в `SqlAlchemyAuthRepository`;
  - valid OAuth-поток падает с `AttributeError`;
  - пользователю показывается сырой backend exception `OAuth error: 'SqlAlchemyAuthRepository' object has no attribute 'save_user'`
- Что сделать:
  - заменить dead call на существующий persistence contract репозитория;
  - не добавлять в репозиторий искусственный `save_user()` только ради этой ветки;
  - использовать тот же update path, что уже применяется в Google callback и обычном staff login;
  - user-facing ошибка должна быть общей и безопасной, без имён Python-классов и traceback-фрагментов;
  - техническая причина должна оставаться только в логе.
- Файлы:
  - `src/pitchcopytrade/api/routes/auth.py`
  - `src/pitchcopytrade/repositories/auth.py`
  - `tests/*auth*`, `tests/*oauth*`
- Не делать:
  - не размазывать новый метод по всем репозиториям без необходимости;
  - не менять business semantics invite flow;
  - не скрывать ошибку полным silent redirect.
- Acceptance:
  - staff invite + Yandex OAuth с валидным email больше не падает с `AttributeError`;
  - статус staff user при необходимости становится `active`;
  - в UI нет текста вида `SqlAlchemyAuthRepository`;
  - добавлены тесты на успешный Yandex callback и на безопасный error message.

### T-009 Staff canonical redirect: после любого staff auth уходить на role dashboard, не на `/workspace` [STAFF, HIGH]

- [x] Убрать legacy `/workspace` как primary destination после успешного staff auth
- До исправления:
  - OAuth staff-пользователь после входа попадает в legacy shell `/workspace`;
  - это расходится с текущим staff contract и с уже существующим `_resolve_role_redirect(...)`;
  - у автора вместо нормальной рабочей поверхности показывается временный экран `Author workspace`.
- Что сделать:
  - для `password login`, `Google OAuth`, `Yandex OAuth`, `Telegram invite bind` использовать один и тот же canonical redirect contract;
  - после успешного входа:
    - `admin` -> `/admin/dashboard`
    - `author` -> `/author/dashboard`
    - `moderator` -> `/moderation/queue`
  - роль и cookies должны ставиться через один общий helper, без копипасты cookie logic;
  - `/workspace` оставить только как legacy compatibility route:
    - либо мгновенный redirect на canonical home;
    - либо debug-only shell, который больше не используется в auth flows.
- Файлы:
  - `src/pitchcopytrade/api/routes/auth.py`
  - при необходимости `src/pitchcopytrade/web/templates/auth/app_home.html`
  - tests на staff login / OAuth redirect
- Проверить отдельно:
  - `switch_staff_mode` не должен возвращать пользователя на legacy shell;
  - `invite_token_priority` не должен ломаться;
  - существующий admin/author dashboard routing не должен деградировать.
- Acceptance:
  - после успешного Google/Yandex/password/invite staff auth автор попадает на `/author/dashboard`;
  - `/workspace` не фигурирует в качестве primary redirect target ни в одном success path;
  - добавлены regression tests на redirect target.

### T-010 Structured message: если инструмента нет в `instruments`, импортировать его через `meta.pbull.kz` по точному `symbol` во время submit [AUTHOR, HIGH]

- [x] Backend exact-import path и submit/preview contract восстановлены для ручного точного ticker
- Актуальный business contract:
  - structured deal не должен публиковаться по "сырым" введённым символам без локальной записи в `instruments`;
  - если нужного инструмента нет в локальной таблице `instruments`, backend должен попытаться найти его через уже используемый quote provider endpoint `https://meta.pbull.kz/api/marketData/forceDataSymbol?symbol=...`;
  - этот endpoint ищет по полному совпадению `symbol`, а не по like-search;
  - import должен выполняться только для тех инструментов, которые автор реально использовал при создании structured message и нажал submit;
  - импортированный инструмент становится общим для всех авторов, потому что пишется в общую таблицу `instruments`.
- До исправления:
  - composer требует `selected_instrument` из локального списка инструментов;
  - если тикера нет в локальном каталоге, backend отвечает ошибкой `Для structured message нужны инструмент, цена и количество.`;
  - `_search_external_instruments_stub()` всегда возвращает пусто;
  - нет path "на submit не нашли local instrument -> exact lookup в provider -> upsert в `instruments` -> продолжили обычную валидацию".
- Фактическая текущая проблема после частичной реализации:
  - backend exact-import path уже существует, но author composer всё ещё блокирует submit/preview, если у пользователя нет локального `structured_instrument_id`;
  - в текущем UI новый symbol нельзя "выбрать", потому что autocomplete знает только локальные инструменты;
  - если автор руками вводит новый ticker, frontend считает structured block незавершённым и не даёт дойти до backend submit/import path;
  - в результате задача закрыта преждевременно: импорт на submit технически есть, но до него нельзя дойти из реального UI.
- Важное уточнение по логике:
  - исходная формулировка "по like из введённых символов" конфликтует с текущим provider contract;
  - при использовании только `forceDataSymbol?symbol=...` worker не должен пытаться строить внешний autocomplete по частичной строке;
  - в рамках этой задачи external search = exact lookup по итоговому значению input на submit;
  - если позже появится отдельный provider endpoint для like-search, это должна быть новая задача, а не скрытое расширение `T-010`.
- Что сделать:
  - на submit structured message обработать `structured_instrument_query`;
  - если `structured_instrument_id` уже передан и валиден локально:
    - поведение остаётся как сейчас;
  - если `structured_instrument_id` пустой, но `structured_instrument_query` заполнен:
    - нормализовать query как ticker/symbol;
    - попробовать найти локальную запись по `ticker`;
    - если локально не найдено, сделать backend-запрос в текущий provider endpoint по точному `symbol`;
    - если provider вернул корректный payload для этого `symbol`, создать или переиспользовать локальную запись `Instrument`;
    - после этого продолжить стандартную валидацию уже через локальный `structured_instrument_id`.
- Что дополнительно исправить в UI/preview contract:
  - structured block не должен требовать локальный `structured_instrument_id` как единственный признак "complete", если автор ввёл новый точный ticker вручную;
  - preview modal и pre-submit validation должны разрешать submit при условиях:
    - указан `structured_instrument_query`;
    - указаны цена и количество;
    - выбрана сторона buy/sell;
  - если query соответствует уже существующему локальному инструменту, UI может продолжать проставлять `structured_instrument_id` как сейчас;
  - если query не выбран из локального popup, submit всё равно должен уйти на backend, где exact lookup/import решит дальнейшую судьбу symbol;
  - placeholder/copy поля не должны обещать поиск по названию, если runtime contract поддерживает только точный ticker/symbol для нового инструмента.
- Правила import/upsert:
  - не создавать запись в `instruments` на каждый ввод символа;
  - import только при реальном submit structured message;
  - uniqueness = `ticker`, потому что текущая БД уже держит `UniqueConstraint("ticker")`;
  - перед insert всегда делать lookup по `ticker`, чтобы не плодить дубликаты;
  - если инструмент уже импортирован ранее, повторно не вставлять, а переиспользовать существующую запись;
  - импортированная запись должна создаваться как глобальная, доступная всем авторам.
- Какие поля брать из provider response для `Instrument`:
  - `ticker`:
    - приоритет `short_name`
    - fallback `symbol`
  - `name`:
    - приоритет `description`
    - fallback `original_name`
    - fallback `short_name`
  - `board`:
    - приоритет `listed_exchange`
    - fallback `source`
    - fallback `levelI.source`
  - `currency`:
    - приоритет `currency_code`
    - fallback `currency`
    - fallback `"USD"`/`"RUB"` не выдумывать, если в payload ничего нет;
    - если поля пустые, использовать безопасный runtime fallback, совместимый с моделью;
  - `instrument_type`:
    - так как в enum сейчас есть только `equity`, импортировать как `InstrumentType.EQUITY`;
  - `lot_size`:
    - в sample provider response поле не найдено;
    - чтобы insert не падал, зафиксировать controlled fallback `lot_size = 1`;
    - этот fallback должен быть явно прокомментирован в коде как временный provider compatibility rule;
  - `is_active = True`.
- Валидация structured message после изменения:
  - обязательные поля:
    - локальный `structured_instrument_id` или успешно импортированный instrument на submit;
    - цена;
    - количество;
    - buy/sell уже выбран always-on toggle;
  - простой текст в `structured_instrument_query` остаётся только входом для import attempt;
  - если exact lookup в provider ничего не вернул, нужна controlled validation error:
    - что инструмент не найден по точному тикеру;
    - что нужно указать корректный `symbol`.
- Потенциальные ошибки в логике, которые worker должен не пропустить:
  - нельзя оставлять в задаче обещание like-search, если текущий endpoint умеет только full match;
  - нельзя делать insert по keypress или blur;
  - нельзя импортировать без обязательных полей модели `Instrument`;
  - `lot_size` обязателен в ORM, а provider его не даёт в sample response, поэтому fallback должен быть зафиксирован явно;
  - uniqueness по `ticker` технически может конфликтовать между площадками, но до отдельного redesign это нужно принять как текущее ограничение, согласованное с БД.
- Файлы:
  - `src/pitchcopytrade/api/routes/author.py`
  - `src/pitchcopytrade/services/author.py`
  - `src/pitchcopytrade/services/instruments.py`
  - `src/pitchcopytrade/repositories/*`, если нужен явный upsert/import path
  - `src/pitchcopytrade/web/templates/author/_composer_form.html`
  - tests на local lookup / provider import / duplicate import / validation / preview-submit
- Не делать:
  - не строить внешний like-search поверх endpoint, который его не поддерживает;
  - не делать browser-to-meta прямой вызов;
  - не создавать transient structured deal без локальной записи в `instruments`;
  - не делать insert в `instruments` до фактического submit сообщения.
- Acceptance:
  - если инструмент есть локально, форма работает как сейчас;
  - если локально инструмента нет, backend на submit делает exact lookup по `symbol`;
  - при успешном lookup создаётся или переиспользуется запись в `instruments`;
  - запись содержит валидные для текущей модели поля, включая `lot_size`;
  - после import сообщение успешно создаётся и публикуется;
  - frontend preview/submit не блокирует автора только потому, что новый symbol ещё не имеет локального `structured_instrument_id`;
  - если provider ничего не нашёл, пользователь получает controlled validation error;
  - добавлены тесты на:
    - local instrument path;
    - provider import path;
    - duplicate import path;
    - validation path для несуществующего точного `symbol`;
    - UI/pre-submit path для ручного ввода нового точного ticker.

### T-011 Telegram attachments: отправлять реальный media/document payload, а не только имя файла в тексте [DELIVERY, HIGH]

- [x] Реализовать delivery contract для вложений в Telegram notifications
- До исправления:
  - author attachments сохраняются в storage, но notification path отправляет в Telegram только текст;
  - в рендере остаются лишь `📎 имя файла` или link placeholder;
  - screenshot/JPEG не отображается в боте как изображение;
  - PDF не отправляется как document.
- Что сделать:
  - выделить transport/helper для Telegram delivery message + attachments;
  - логика отправки:
    - сначала основной текст сообщения;
    - затем каждое вложение из `message.documents`;
    - `image/jpeg` -> `send_photo`
    - `application/pdf` -> `send_document`
  - payload брать по storage key / object key из storage backend, не требовать заранее публичный URL;
  - attachment send failure не должен теряться:
    - если хоть одно вложение не доставлено, Telegram delivery считать неуспешной;
    - существующий fallback email path должен отработать по текущему policy;
  - text-only сообщения не должны менять поведение;
  - если в проекте остаётся второй broadcast/send path, его нельзя оставлять текстовым дубликатом для той же предметной области: либо перевести на shared helper, либо явно вывести из активного runtime path.
- Файлы:
  - `src/pitchcopytrade/services/notifications.py`
  - `src/pitchcopytrade/services/message_rendering.py`
  - `src/pitchcopytrade/services/author.py`
  - при необходимости `src/pitchcopytrade/bot/main.py`
  - tests на notification transport
- Проверить:
  - JPEG из author composer приходит в Telegram как фото;
  - PDF приходит как документ;
  - mixed message (`text + deal + attachments`) не теряет текстовую часть;
  - logs не раздуваются сырой binary диагностикой.
- Acceptance:
  - screenshot/JPEG реально отображается в Telegram;
  - PDF доставляется как attachment;
  - при telegram media failure включается fallback email;
  - добавлены тесты/моки на успешную и частично неуспешную отправку.

### T-012 Bot catalog entry: сделать постоянную Telegram menu button для каталога [BOT, MEDIUM]

- [x] Убрать зависимость основного Mini App entry от scroll position chat history
- До исправления:
  - `Открыть каталог` живёт только как inline button в ответе на `/start`;
  - при потоке сигналов и новых сообщениях пользователь теряет быстрый вход в Mini App;
  - это расходится с идеей одного постоянного entry point в каталог.
- Что сделать:
  - на bot startup настроить Telegram `MenuButtonWebApp` с переходом в каталог;
  - inline `/start`-кнопку оставить как fallback и onboarding hint, но не как единственную точку входа;
  - если `BASE_URL` не HTTPS или Telegram API не позволяет поставить menu button:
    - не падать всем ботом;
    - писать короткий warning в лог;
  - help/start copy обновить так, чтобы они не обещали только старый inline-сценарий.
- Файлы:
  - `src/pitchcopytrade/bot/main.py`
  - `src/pitchcopytrade/bot/handlers/start.py`
  - при необходимости docs / tests
- Acceptance:
  - после старта бота у пользователя есть постоянная menu button на каталог;
  - `/start` всё ещё работает;
  - сбой установки menu button не валит polling/webhook runtime;
  - если локально нет HTTPS, поведение деградирует контролируемо.

---

## Блок 3 — OAuth hardening follow-up

### T-013 Google OAuth: убрать утечку сырого backend exception в login UI [AUTH, MEDIUM]

- [x] Синхронизировать Google OAuth error UX с уже исправленным Yandex flow
- До исправления:
  - в `src/pitchcopytrade/api/routes/auth.py` ветка `except` у `google_oauth_callback` рендерит в шаблон логина строку вида `OAuth error: {str(exc)[:100]}`;
  - пользователю показываются технические детали runtime, provider-ошибок или внутренних исключений;
  - это расходится с контрактом `T-008`, где user-facing ошибка должна быть общей и безопасной, а техническая причина оставаться только в логе.
- Что сделать:
  - в `google_oauth_callback` заменить сырой `error=f"OAuth error: {str(exc)[:100]}"` на безопасное человекочитаемое сообщение того же уровня, что уже используется в `yandex_oauth_callback`;
  - не скрывать сам факт ошибки: пользователь должен понять, что вход через Google не завершился;
  - сохранить `logger.exception("Google OAuth error")`, чтобы полная техническая причина осталась в логах;
  - не менять success path, state validation, redirect contract и cookie logic;
  - привести тексты Google и Yandex OAuth к одному UX-подходу:
    - безопасное сообщение в UI;
    - техническая детализация только в логах.
- Файлы:
  - `src/pitchcopytrade/api/routes/auth.py`
  - `tests/test_auth_ui.py`
  - при необходимости docs (`doc/review.md`)
- Не делать:
  - не добавлять новый repository API;
  - не менять redirect target после успешного входа;
  - не убирать `logger.exception`;
  - не делать silent redirect без сообщения об ошибке.
- Проверки:
  - вручную: сломанный Google OAuth flow не показывает `RuntimeError`, имя класса, traceback-фрагменты, provider response text;
  - regression: успешный Google OAuth flow по-прежнему уводит staff на canonical dashboard;
  - regression: Yandex OAuth поведение не меняется.
- Acceptance:
  - при ошибке Google OAuth login page показывает только безопасное сообщение без backend деталей;
  - в HTML нет `OAuth error:`, `RuntimeError`, имён repository-классов и фрагментов Python exception text;
  - success path Google OAuth остаётся рабочим;
  - добавлены tests на:
    - безопасный Google OAuth error message;
    - отсутствие утечки exception text;
    - сохранение canonical redirect на успешном callback.

---

## Блок 4 — Subscriber auth recovery from bot/start

### T-014 Subscriber Mini App entry: из бота нельзя открывать защищённый `/app/catalog` до Telegram bootstrap auth [SUBSCRIBER, HIGH]

- [x] Перевести bot/menu entry для клиента на bootstrap route, который умеет обменять `Telegram.WebApp.initData` на auth cookie до перехода в каталог
- Текущая проблема:
  - сейчас bot `/start` keyboard и Telegram menu button открывают `web_app` URL на `/app/catalog`;
  - `/app/catalog` — уже защищённый subscriber route и он ожидает существующий Telegram fallback cookie/session;
  - для нового клиента это даёт loop: пользователь открывает Mini App, cookie ещё нет, route уводит на recovery/verify surface, а кнопки дальше не завершают авторизацию;
  - по факту входной путь идёт мимо bootstrap-страницы, которая умеет отправить `initData` в `/tg-webapp/auth`.
- Что сделать:
  - primary bot/web_app entry для subscriber path должен открывать не защищённый `/app/catalog`, а canonical bootstrap route;
  - bootstrap route обязан:
    - если subscriber уже авторизован или Telegram cookie уже есть, сразу уводить на `/app/catalog`;
    - принимать открытие внутри Telegram WebApp;
    - читать `Telegram.WebApp.initData`;
    - POST-ить `init_data` в `/tg-webapp/auth`;
    - только после успешного server-side bind/cookie setup уводить на `/app/catalog`;
  - использовать уже существующий bootstrap route, если он покрывает этот contract;
  - если текущих bootstrap routes два (`/app` и `/miniapp`), выбрать один canonical subscriber entry и убрать двусмысленность в bot/start/menu flows;
  - `Каталог` остаётся целевым экраном после auth, но не должен быть первым URL из бота для нового пользователя без cookie.
  - важно: Telegram menu button и `/start` web_app link должны вести в один и тот же canonical bootstrap route; условие "если доступен каталог -> открыть каталог, иначе -> bootstrap" должно решаться внутри route, а не разными URL в кнопках.
- Файлы:
  - `src/pitchcopytrade/bot/handlers/start.py`
  - `src/pitchcopytrade/bot/main.py`
  - `src/pitchcopytrade/api/routes/auth.py`
  - `src/pitchcopytrade/api/routes/public.py`
  - `src/pitchcopytrade/web/templates/app/miniapp_entry.html`
  - tests: `tests/test_bot_baseline.py`, `tests/test_auth_ui.py`
- Важное уточнение по test contract:
  - текущие tests всё ещё ожидают старый URL `/app/catalog`;
  - при реальном закрытии задачи нужно обновить assertions в bot/auth tests, иначе regression suite будет закреплять старое поведение.
- Не делать:
  - не оставлять primary entry на `/app/catalog` для first-time subscriber auth;
  - не плодить несколько равноправных bootstrap URLs без явного canonical contract;
  - не завязывать решение на уже существующем cookie как обязательном условии старта.
- Проверить:
  - новый пользователь из Telegram бота проходит путь `/start -> web_app -> tg-webapp/auth -> /app/catalog`;
  - повторный пользователь с cookie всё ещё быстро попадает в каталог;
  - existing staff `/login` и invite flows не затрагиваются.
- Acceptance:
  - bot `/start` и menu button ведут в canonical bootstrap route;
  - если auth уже есть, bootstrap route сразу открывает `/app/catalog`;
  - если auth нет, bootstrap route запускает subscriber auth flow с `initData` или показывает recovery CTA;
  - после успешного bind пользователь попадает в `/app/catalog`;
  - добавлены regression tests на bot keyboard/menu button URL и на first-time subscriber bootstrap flow.

### T-015 Recovery CTA: вместо dead-end `Открыть бота` нужен явный deep-link на `/start payload`, а не попытка «отправить /start из сайта» [SUBSCRIBER, HIGH]

- [x] Исправить recovery UX для неавторизованных клиентов на `/verify/telegram` и fallback surfaces
- Ограничение Telegram, которое worker обязан учитывать:
  - обычная HTML-кнопка на сайте не может тихо отправить команду `/start` в Telegram-бота от имени пользователя;
  - сайт не может программно «нажать /start» в чате;
  - разрешённые варианты:
    - deep link `https://t.me/<bot_username>?start=<payload>` — пользователь открывает бота, а bot получает `/start <payload>`;
    - `web_app` button / menu button, если пользователь уже находится в Telegram и открывает Mini App;
    - внутри уже открытого WebApp возможны собственные client-side calls, но это не эквивалент команде `/start`.
- Текущая проблема:
  - recovery pages показывают generic CTA `Открыть бота`;
  - generic `https://t.me/<bot_username>` не гарантирует повторный `/start`, пользователь просто попадает в чат/историю и остаётся без следующего шага;
  - из-за этого кнопки на verify/entry surfaces выглядят «ни к чему не приводят».
- Что сделать:
  - заменить generic CTA `Открыть бота` на явный recovery/start CTA:
    - primary label = `Начать авторизацию в Telegram`;
    - URL должен быть deep link с payload, а не просто `https://t.me/<bot_username>`;
  - добавить обработку соответствующего `/start payload` в `handle_start`;
  - bot по этому payload должен отправлять пользователю понятный следующий шаг:
    - свежую `web_app` кнопку на canonical bootstrap route;
    - короткий текст без двусмысленности;
  - recovery surfaces (`/verify/telegram`, `app/miniapp_entry.html`, при необходимости `public/miniapp_bootstrap.html`) должны использовать этот же deep-link contract;
  - copy на recovery surfaces должна прямо объяснять: сначала открыть бота по кнопке, затем нажать кнопку запуска Mini App / авторизации.
- Файлы:
  - `src/pitchcopytrade/bot/handlers/start.py`
  - `src/pitchcopytrade/web/templates/public/telegram_verify.html`
  - `src/pitchcopytrade/web/templates/app/miniapp_entry.html`
  - `src/pitchcopytrade/web/templates/public/miniapp_bootstrap.html`
  - tests: `tests/test_bot_baseline.py`, `tests/test_auth_ui.py`
- Важное уточнение по test contract:
  - `tests/test_auth_ui.py` сейчас ещё ожидает generic `Открыть бота` на verify surface;
  - при закрытии задачи test suite должен быть переведён на новый deep-link/start-payload contract.
- Не делать:
  - не обещать literal «кнопку, отправляющую /start из сайта»;
  - не оставлять generic `https://t.me/<bot_username>` как единственный recovery CTA;
  - не строить recovery UX вокруг того, что пользователь сам догадается вручную ввести `/start`.
- Важное UX-решение:
  - Telegram menu button нельзя надёжно делать условной по browser auth state;
  - если нужен универсальный label, лучше использовать нейтральное `Открыть Mini App` или `Начать`, а условный recovery CTA показывать уже на HTML recovery surfaces;
  - worker не должен пытаться делать menu button «если не авторизован → Start, иначе → Каталог» без отдельного per-user bot state contract.
- Acceptance:
  - неавторизованный клиент на `/verify/telegram` и bootstrap fallback видит primary CTA `Начать авторизацию в Telegram` на deep link `/start <payload>`, а не просто `Открыть бота`;
  - bot обрабатывает этот payload и присылает понятную кнопку для запуска авторизации;
  - recovery путь больше не зависит от ручного ввода `/start`;
  - добавлены tests на deep-link generation и на `/start payload` handler.
