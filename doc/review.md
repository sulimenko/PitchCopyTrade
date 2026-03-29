# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-29
> Этот файл хранит только актуальные findings и merge gate после перехода проекта на `messages` и unified author composer.

## Общий вывод

Последний implementation pass существенно продвинул проект:

- `recommendations` заменены на `messages`
- author UI стал message-centric
- unified composer, preview и history table уже есть
- локальный regression gate сейчас зеленый: `./.venv/bin/python -m pytest -q` -> `233 passed`

Но merge нельзя считать полностью чистым: post-implementation review все еще держит открытыми несколько реальных product regressions в author edit flow.

## Подтвержденные факты

- основной author surface теперь находится на `/author/messages`
- composer действительно собирает одно сообщение из text/documents/structured секций
- preview перед submit реализован
- локальный test suite проходит полностью
- clean db schema и startup path существуют
- минимальный public checkout dataset в PostgreSQL теперь seed-ится автоматически

## Findings

### [P1] Structured deal edit round-trip ломает повторное сохранение уже созданного сообщения

Проблема:
- `_build_structured_deal()` сохраняет `deal.instrument` как человекочитаемое имя инструмента, а `deal.instrument_id` как реальный ID;
- `recommendation_form_values()` при заполнении edit form сначала берет `deal.instrument`, а только потом `deal.instrument_id`;
- в результате скрытое поле `structured_instrument_id` получает значение вроде `Sberbank` вместо `instrument-1`.

Следствие:
- повторное открытие и сохранение structured message без ручного повторного выбора инструмента может падать на backend validation;
- edit round-trip нового canonical payload сейчас не является стабильным.

Файлы:
- `src/pitchcopytrade/services/author.py`

### [P1] Document-only edit/preview path не учитывает уже прикрепленные документы

Проблема:
- `hasDocumentFiles()` в author composer считает только новые файлы из `<input type="file">`;
- уже существующие `composer.documents` в client-side type detection не участвуют;
- preview gate считает такую форму пустой, а hidden `message_type` может быть переопределен в `mixed`.

Следствие:
- существующее document-only сообщение нельзя надежно открыть и пересохранить без повторной загрузки файла;
- document-only edit flow остается неполноценным несмотря на зеленый test suite.

Файлы:
- `src/pitchcopytrade/web/templates/author/message_form.html`

### [P2] Author history table подписана как `Каналы`, но показывает `deliver`

Проблема:
- в таблице сообщений колонка называется `Каналы`;
- в ячейке рендерится `message.deliver`, а не `message.channel`.

Следствие:
- оператор видит audience routing под меткой transport channels;
- это создает UX ambiguity и затрудняет ручную проверку delivery contract.

Файлы:
- `src/pitchcopytrade/web/templates/author/message_form.html`

### [P2] DB-mode документация нельзя трактовать как “полный business seed готов”

Проблема:
- `deploy/migrate.sh --reset` и startup path в `APP_DATA_MODE=db` по-прежнему auto-seed-ят только `instruments` и bootstrap `admin`;
- importer для полного business dataset в PostgreSQL не появился.

Следствие:
- `db`-mode подходит для schema/startup verification, но не как полноценный replacement file-mode dataset для ручного QA;
- документация должна это подчеркивать явно, иначе инженер ожидает больше, чем реально умеет репозиторий.

Файлы:
- `deploy/README.md`
- `src/pitchcopytrade/api/lifespan.py`
- `src/pitchcopytrade/db/seeders/*`

## Открытые задачи

### P4 — Dropdown / dialog / русские статусы

- [x] P4.1: Staff dialog через event delegation
- [x] P4.2: Dropdown mutual exclusion (toggle listener)
- [x] P4.3: Статусы рекомендаций на английском → **вынесено в P6**
- [x] P4.4: Все статусы во всех grid-ах на английском → **вынесено в P6**

### P5 — Composer: 3-колоночный layout `[x]`

- [x] P5.1: 3-колоночный grid (`1fr 1fr 1fr`, mobile breakpoint 900px)
- [x] P5.2: Заголовки + кнопки (Отправить / Купить / Продать)
- [x] P5.3: Навигация-лента (3 anchor-табы)
- [x] P5.4: Cleanup (sticky, eyebrow, общий submit убраны)

### P6 — `_label()` подключён во всех сериализаторах `[x]`

Все 14 вызовов `_badge()` с переменными обёрнуты в `_label()`. Словарь `_STATUS_LABELS` расширен на 16 ключей (risk, payment, message kind/type). Компиляция чистая.

### P7 — Компактный composer + единая кнопка + inline autocomplete + toggle + TP/SL `[x]`

- P7.1: UI слишком крупный — уменьшить все padding/gap/radius/font-size
- P7.2: Кнопка submit — одна общая «Отправить сообщение» вместо 3+2 кнопок в блоках
- P7.3: Instrument picker + direction toggle + TP/SL + валидация:
  - **Удалить modal dialog** → inline autocomplete popup (3-5 вариантов под полем)
  - **Удалить select Buy/Sell** → toggle-кнопки «Купить» (зелёный) / «Продать» (красный)
  - **Добавить поля TP и SL** (необязательные)
  - **Валидация блока 3:** если хоть одно поле заполнено → обязательны: инструмент + цена + кол-во; если всё пустое → блок неактивен
- P7.4: Цены инструментов — `INSTRUMENT_QUOTE_PROVIDER_ENABLED=true` в `.env` + WARNING лог если недоступен (без fallback)

**Root cause цен:** `config.py:213` — `provider_enabled: bool = default=False`. Fix: `INSTRUMENT_QUOTE_PROVIDER_ENABLED=true`.

**Цены при выборе инструмента:** запроса в консоли нет потому что цены грузятся ОДИН РАЗ при рендере страницы (`build_instrument_payloads()` → `get_instrument_quote()`). JS массив `instrument_items` уже содержит `quote_last_price_text`. При клике на autocomplete item цена берётся из массива. Если провайдер выключен — все цены = "—".

### P8 — Radio toggle, inline layout блока 3, удаление заголовка, диагностика quote provider `[x]`

- [x] P8.1: Radio toggle `<input id> + <label for>` pattern
- [x] P8.2: Toggle на ОТДЕЛЬНОЙ строке
- [x] P8.3: Labels inline
- [x] P8.4: Заголовок удалён
- [x] P8.5: History «Превью»
- [x] P8.6: Логи quote provider

### P9 — Равномерная ширина полей блока 3 + таблица на Tabulator JSON mode `[x]`

- [x] P9.1: Поля блока 3 — `flex: 1 1 0`, удалены `deal-field--fixed`/`deal-field--grow` ✅
- [x] P9.2: Таблица → Tabulator JSON mode ✅
- **Проблема:** Toggle «Купить | Продать» НЕ растягивается на 100% строки → см. P10

### P10 — Toggle «Купить/Продать» на 100% ширины строки `[x]`

- [x] P10.1: `.side-toggle { width: 100% }`, удалить `min-width: 140px`, `flex-shrink: 0`, `align-self`
- [x] P10.2: `.side-toggle-label { flex: 1; text-align: center; padding: 8px 12px }` — каждая кнопка 50%
- [x] P10.3: Удалить `.deal-row .side-toggle { align-self: flex-start }`
- [x] P10.4: Удалить `min-width: 140px` из media queries

**Подробные инструкции:** `doc/task.md` → Блок P10

### P11 — Bugfix: NameError при POST /author/messages → 500 `[x]`

- [x] P11.1: `_render_recommendation_create_error()` строка 914 — `selected_instrument_id` и `selected_instrument` не определены в scope функции. Заменить на `form.get(...)`. Проверить все аналогичные helper-функции на тот же баг.

**Подробные инструкции:** `doc/task.md` → Блок P11

### P12 — Tabulator: огромная серая область пустой таблицы `[x]`

- [x] P12.1: Удалить `min-height: 400px` из `.author-history-grid-wrap` и `#author-history-grid`
- [x] P12.2: Tabulator init — убрать фиксированную `height`, использовать `maxHeight: "400px"`
- [x] P12.3: CSS — прозрачный фон placeholder, компактный padding (≤80px вместо 400px)
- [x] P12.4: Компактные шрифты заголовков и ячеек

**Подробные инструкции:** `doc/task.md` → Блок P12

### P13 — Composer как overlay-панель внутри `.staff-main` `[x]`

- [x] P13.1: Вырезать форму из `message_form.html` → новый `_composer_dock.html`. Обернуть в `<div class="composer-dock">` с header + body
- [x] P13.2: CSS — `position: absolute; bottom:0` внутри `.staff-main` (НЕ fixed). `max-height: calc(100% - 60px)`. `.staff-main { position: relative }`
- [x] P13.3: JS toggle collapse/expand + localStorage. На `/author/messages` — раскрыт, на остальных — свёрнут
- [x] P13.4: Подключить dock на ВСЕХ author-страницах. `{% block composer_dock %}` ВНУТРИ `<main>`. Backend: `_get_composer_context()` helper
- [x] P13.5: Header: «Новое сообщение» (синий) или «Редактирование #ID» (оранжевый) + pill статус

**Подробные инструкции:** `doc/task.md` → Блок P13

### P14 — Кнопка «+ Новое» для возврата из режима редактирования `[x]`

- [x] P14.1: В header dock при `_composer_recommendation` → добавить `<a href="/author/messages">+ Новое</a>` для сброса формы на создание нового сообщения

**Подробные инструкции:** `doc/task.md` → Блок P14

### P15 — Поддержка LOG_FILE для записи логов в файл `[x]`

- [x] P15.1: Добавить `LOG_FILE` в `EnvName`, `Settings` (`log_file: str | None`), `LoggingSettings` (`file_path: str | None`)
- [x] P15.2: В `configure_logging()` — добавить `FileHandler` если `settings.file_path` задан. Тот же формат что и stdout.

**Подробные инструкции:** `doc/task.md` → Блок P15

### P16 — Fix `_normalize_provider_payload` для реального формата meta.pbull.kz `[x]`

- [x] P16.1: Добавить `_nested_float()` и `_nested_text()` — helpers для извлечения данных из вложенных dict по dot-path
- [x] P16.2: Переписать `_normalize_provider_payload()` — извлекать `last_price` из `trade.price`, `change` из `prev-daily-bar.close`, `updated_at` из `trade.time`
- [x] P16.3: безопасный доступ и тестовые mock-и доделаны в P19

**Подробные инструкции:** `doc/task.md` → Блок P16

### P19 — Fix: тесты не соответствуют реальному формату API `[x]`

- [x] P19.1: Строка 230 — безопасный доступ: `unwrapped[ticker]` если есть, иначе `unwrapped` (fallback)
- [x] P19.2: Mock-и в тестах обернуть под ключ тикера: `{"NVTK": {...}}`, `{"GAZP": {...}}`

**Подробные инструкции:** `doc/task.md` → Блок P19

### P17 — Автоподстановка цены при выборе инструмента `[x]`

- [x] P17.1: В click handler autocomplete — если `structured_price` пустое и `item.last_price != null`, подставить цену + вызвать `syncAmount()`

**Подробные инструкции:** `doc/task.md` → Блок P17

### P18 — Stub-заглушка: автоактивация подписки без оплаты `[x]`

- [x] P18.1: `_create_checkout_records()` — при `stub_manual` сразу ставить `Payment=PAID`, `Subscription=ACTIVE` (auto-confirm)
- [x] P18.2: Бесплатный продукт (`price_rub=0` или 100% промокод) → `Subscription=ACTIVE` без Payment. `CheckoutResult.payment` → `Optional`
- [x] P18.3: Routes — корректная обработка auto-confirm и free в checkout success page

**Подробные инструкции:** `doc/task.md` → Блок P18

### P20 — Bugfix: MissingGreenlet при checkout (expired product после commit) `[x]`

- [x] P20.1: В `_create_checkout_records`, `_create_free_checkout_records`, `_create_tbank_checkout_records` — добавить `await repository.refresh(product)` после commit
- [x] P20.2: В route handlers — сохранить `product_title = product.title` ДО try-блока, использовать в except-блоках
- [x] P20.3: Проверить шаблоны checkout_success на обращения к expired product attributes

**Подробные инструкции:** `doc/task.md` → Блок P20

## Gate на следующий implementation pass

Следующий merge считается полностью чистым только после:

1. фикса structured deal edit round-trip через единый `instrument_id` contract;
2. фикса preview/type detection для existing document-only messages;
3. синхронизации history table: либо показывать `channel`, либо честно переименовать колонку под `deliver`;
4. явного решения по полному business seed для `APP_DATA_MODE=db`:
   или реализовать importer, или оставить это открытым контрактом и не маркировать блок как завершенный.

## Что считать готовностью текущего pass

Текущий pass можно считать пригодным для дальнейшей разработки, если:

- авторский message-centric UI уже используется как основной surface;
- локальный test suite остается зеленым;
- документация не обещает больше, чем реально сделано;
- follow-up fixes из review занесены в backlog и review gate.
