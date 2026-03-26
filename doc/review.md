# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-26
> Этот файл хранит только текущие findings, наблюдения и gate следующего implementation pass.

## Общий вывод

Следующий цикл merge нельзя считать "косметическим". Он блокируется не staff-рефакторингом, а subscriber/Mini App контуром:
- неправильный первый экран;
- слабая витрина и detail стратегии;
- неинтегрированные real-time данные;
- неразобранные дефекты checkout/help/navigation;
- отсутствие first-class local preview режима.

## Подтвержденные факты исследования

- `api` реально стартует локально без Docker в `APP_DATA_MODE=file`;
- для старта `api` обязательно нужен `INTERNAL_API_SECRET`;
- `public checkout` в `file`-mode создает заявку и возвращает `201 Created`;
- browser preview для `/app/*` возможен через demo subscriber и `/tg-auth?token=...`;
- `storage/runtime/*` — mutable runtime слой, который может расходиться с `storage/seed/*`;
- текущий `/api/instruments` не возвращает real-time quote data;
- `bot /help` сейчас не открывает help-screen приложения.

## Findings

### [P1] Mini App entry contract сейчас противоречив

Проблема:
- `public /miniapp` по-прежнему строится вокруг `next_path="/app/status"`;
- `POST /tg-webapp/auth` и `app/miniapp_entry.html` уже ведут в `/app/catalog`;
- в продуктовых требованиях пользователь ожидает catalogue-first.

Следствие:
- стартовый сценарий распадается на несколько конкурирующих entry points;
- документация и runtime расходятся;
- часть ошибок навигации может быть следствием именно этого расхождения.

Файлы для implementation pass:
- `src/pitchcopytrade/api/routes/public.py`
- `src/pitchcopytrade/api/routes/auth.py`
- `src/pitchcopytrade/web/templates/public/miniapp_bootstrap.html`
- `src/pitchcopytrade/web/templates/app/miniapp_entry.html`

### [P1] Help flow не соответствует продуктовой задаче

Проблема:
- `GET /app/help` уже существует;
- но `bot /help` в `src/pitchcopytrade/bot/handlers/start.py` отправляет то же сообщение `PitchCopyTrade`, что и `/start`;
- пользовательский сценарий `/help` в Telegram не приводит к help-screen приложения.

Следствие:
- help живет как дублирующий bot-message flow;
- это усиливает проблему "каждый переход создает новую закладку/новое сообщение";
- продуктовый контур Mini App выглядит незавершенным.

### [P1] Real-time instruments еще не интегрированы

Проблема:
- `src/pitchcopytrade/api/routes/instruments.py` отдает `last_price=None` и `change_pct=None`;
- `NVTK.json` показывает, что новый provider уже определен;
- текущие UI/author flows пока не получают нормализованные live quotes.

Следствие:
- стратегии и recommendation editor работают без актуального market context;
- локальный `/api/instruments?q=NVTK` не отражает целевой контракт;
- новая product value по инструментам еще не реализована.

### [P1] Checkout/payment defects не закрыты

Проблема:
- есть подтвержденные пользовательские сообщения о desktop/mobile расхождении на кнопке `Создать заявку на оплату`;
- есть сообщение про `Internal Server Error` при оформлении подписки;
- эти кейсы пока не воспроизведены и не сведены в controlled diagnostics.

Следствие:
- subscriber flow нельзя считать надежным;
- success/error contract checkout не стабилизирован;
- любые UI-изменения витрины без разбора payment path рискуют скрыть, а не решить core issue.

### [P2] Browser preview Mini App есть, но он не first-class

Проблема:
- miniapp screens в обычном браузере можно открыть только через технический путь с demo subscriber и `/tg-auth`;
- first-class preview mode для дизайна и редактирования нет;
- staff и miniapp preview пока не сведены в единый local-dev contract.

Следствие:
- каждый следующий исследователь будет заново изобретать способ открыть `/app/*` локально;
- скорость UI-итераций ниже, чем должна быть.

### [P2] Документация до этого цикла была недостоверной

Проблема:
- старые docs утверждали, что production bug-ов нет и все крупные блоки закрыты;
- при этом в пользовательском feedback уже есть действующие баги и незакрытые UX-проблемы;
- текущий код уже живет не в AG Grid narrative, а в другой конфигурации.

Следствие:
- предыдущие docs нельзя было использовать как source of truth;
- следующий implementation pass должен опираться только на новые канонические документы.

### [P2] File-mode runtime дрейфует от seed и может искажать результаты исследования

Проблема:
- `storage/seed/json/instruments.json` содержит расширенный список тикеров, включая `NVTK`;
- текущий `storage/runtime/json/instruments.json` может содержать уже урезанный набор;
- `file`-mode всегда читает runtime-слой первым.

Следствие:
- локальные проверки без reset runtime не воспроизводимы;
- отсутствие `NVTK` в `/api/instruments?q=NVTK` может быть следствием drift, а не кода поиска.

## Открытые вопросы и ограничения исследования

- `Straddle.pdf` является image-based PDF без доступного текстового слоя. В текущей среде удалось использовать его как визуальный reference, но не как полноценно машиночитаемый текстовый источник.
- transient JSON parse error на `/admin/dashboard` пока не воспроизведен локально и требует отдельного capture в браузере пользователя или на стенде.
- точная причина desktop-only отказа кнопки `Создать заявку на оплату` пока не локализована: нужен network trace и server log по одному и тому же сценарию.

## Gate на следующий implementation pass

Следующий merge считается блокированным, пока не закрыты следующие пункты:

1. зафиксирован и реализован единый `catalog-first` contract для Mini App;
2. `bot /help` приведен к help-screen приложения;
3. определен и реализован contract для strategy showcase/detail;
4. согласован adapter для `meta.pbull.kz` и нормализованный quote payload;
5. проведена диагностика checkout/payment дефектов;
6. зафиксирован reproducible local preview path без документной магии и догадок.

## Что считать готовностью этого research pass

Research pass считается завершенным, если:
- канонические docs очищены от истории;
- локальный no-docker runbook зафиксирован;
- backlog и review gate описывают только текущие задачи;
- следующий инженер может сразу перейти к implementation по subscriber contour, не разбирая старые фазы.
