# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-29
> Этот файл хранит только актуальные findings и merge gate после перехода проекта на `messages` и unified author composer.

## Общий вывод

Последний implementation pass существенно продвинул проект:

- `recommendations` заменены на `messages`
- author UI стал message-centric
- unified composer, preview и history table уже есть
- локальный regression gate сейчас зеленый: `./.venv/bin/python -m pytest -q` -> `248 passed`

Открытых findings в этом gate нет.

## Подтвержденные факты

- основной author surface теперь находится на `/author/messages`
- composer действительно собирает одно сообщение из text/documents/structured секций
- preview перед submit реализован
- локальный test suite проходит полностью
- clean db schema и startup path существуют
- минимальный public checkout dataset в PostgreSQL теперь seed-ится автоматически

## Findings

Open findings: none.

## Resolved In This Pass

### [P1] Structured deal edit round-trip ломает повторное сохранение уже созданного сообщения

Resolved:
- `recommendation_form_values()` теперь предпочитает `deal.instrument_id`, а не human-readable `deal.instrument`
- structured edit form больше не подставляет display name в скрытое ID-поле

### [P1] Document-only edit/preview path не учитывает уже прикрепленные документы

Resolved:
- edit form и composer теперь сохраняют уже прикрепленные документы как часть canonical state;
- добавлен regression test на document-only edit flow с existing attachment payload

### [P2] Author history table подписана как `Каналы`, но показывает `deliver`

Resolved:
- колонка в composer history table переименована в `Доставка`
- подпись больше не смешивает audience routing с transport channels

### [P2] DB-mode документация нельзя трактовать как “полный business seed готов”

Resolved:
- `doc/README.md` и `deploy/README.md` теперь явно говорят, что `APP_DATA_MODE=db` пока не означает full business seed
- документация разделяет primary runtime path и полный importer/seed pipeline

### [P1] Переключение в author mode блокируется на live quote provider path

Resolved:
- author SSR больше не блокирует переход на live quote provider;
- initial render использует cached/stale/empty payloads и затем делает async quote hydrate after first paint;
- provider URL contract должен дальше жить как `origin in env + path in code`; internal-network сценарий должен использовать `INSTRUMENT_QUOTE_PROVIDER_BASE_URL=http://meta-api-1:8000`, а не полный endpoint path в `.env`;
- добавлены regression tests на `POST /auth/mode` + real author dashboard render.

### [P1] Author publish path валится до delivery, потому что validation идет раньше server-side `published`

Resolved:
- `_apply_publish_state()` теперь вызывается до `_validate_message_contract()` в create/update publish paths;
- `published` назначается сервером, а не ожидается от формы;
- publish path доходит до delivery trace, и regression tests это покрывают.

### [P1] DB runtime `0 recipients` теперь диагностируется и покрыт end-to-end checkout/publish regression tests

Resolved:
- recipient selection logs now distinguish `no active subscriptions`, `active subscriptions without telegram_user_id`, and `active subscriptions exist but do not match message audience`;
- `tests/test_notifications_service.py` covers the negative diagnostic branches;
- `tests/test_acl_delivery_services.py` covers the Telegram-bound checkout -> active subscription -> publish happy path with `recipient_count > 0`;
- the earlier `0 recipients` trace is now a diagnosable contract, not a silent failure.

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

### P21 — Убрать промежуточный блок профиля из каталога Mini App `[x]`

- [x] P21.1: Блок профиля/pills/статус убран из каталога, описание унифицировано

**Подробные инструкции:** `doc/task.md` → Блок P21

### P22 — Каталог: 1-колоночный layout + blue-dominant дизайн карточек `[x]`

- [x] P22.1: Grid `1fr` вместо `repeat(2,...)`, media-query удалён
- [x] P22.2: Метаданные — крупные синие блоки (`background: var(--accent-bg, #1a2a5e)`, белый текст)

**Подробные инструкции:** `doc/task.md` → Блок P22

## Gate на следующий implementation pass

Следующий merge считается полностью чистым только после:

1. ~~фикса structured deal edit round-trip~~ → **resolved** (P1)
2. ~~фикса preview/type detection для existing document-only messages~~ → **resolved** (P1)
3. ~~синхронизации history table: channel vs deliver~~ → **resolved** (P2)
4. ~~db seed contract~~ → **resolved** (P2, documented as-is)

Все ранее заблокированные gate items закрыты. Текущий gate: **green**.

## Что считать готовностью текущего pass

Текущий pass можно считать пригодным для дальнейшей разработки, если:

- авторский message-centric UI уже используется как основной surface;
- локальный test suite остается зеленым;
- документация не обещает больше, чем реально сделано;
- follow-up fixes из review занесены в backlog и review gate.
