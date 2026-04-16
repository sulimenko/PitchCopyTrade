# PitchCopyTrade — Active Tasks
> Обновлено: 2026-04-16

Закрытые задачи этого цикла. Архив закрытых блоков — в `doc/changelog.md`.
Активных задач в текущем цикле не осталось.

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

- [x] Убрать transient free-text fallback и перевести composer на submit-time instrument import
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
  - tests на local lookup / provider import / duplicate import / validation
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
  - если provider ничего не нашёл, пользователь получает controlled validation error;
  - добавлены тесты на:
    - local instrument path;
    - provider import path;
    - duplicate import path;
    - validation path для несуществующего точного `symbol`.

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
