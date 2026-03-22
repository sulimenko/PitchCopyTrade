# PitchCopyTrade — Active Tasks
> Обновлено: 2026-03-22
> Этот файл хранит только текущий backlog. Завершенные исторические фазы сюда не возвращаются.

## Статусы

- `[ ]` — не начато
- `[~]` — в работе
- `[x]` — завершено
- `[!]` — заблокировано

---

## Блок S — Инфраструктура: гибкое подключение к DB/Redis и HTTPS статика

---

### S1 — Параметризовать `docker-compose.server.yml` для двух моделей развёртки

**Контекст:**
Текущий `deploy/docker-compose.server.yml` захардкожен под конкретный сервер с внешней сетью `ptfin-backend`. До этого была захардкожена подсеть `172.20.0.0/24`. Нужна одна конфигурация, поддерживающая оба варианта без правки yml-файла.

**Два варианта развёртки:**

| | Вариант А — standalone | Вариант Б — shared backend |
|---|---|---|
| Сеть | Собственная Docker-сеть (создаётся compose) | Внешняя Docker-сеть (уже существует) |
| Postgres | Локально на хосте | В сети как отдельный контейнер |
| Redis | Локально на хосте | В сети как отдельный контейнер |
| Порт API | Пробросить `127.0.0.1:8110:8000` | Не пробрасывать (nginx в той же сети) |
| `extra_hosts` | `host.docker.internal:host-gateway` | Не нужен |
| DNS aliases | Нет | `pct-api.ptfin.local`, `pct-bot.ptfin.local`, `pct-worker.ptfin.local` |

**Текущий файл (база для задачи):**
```yaml
# Сеть: hardcoded ptfin-backend external
# Aliases: pct-api/bot/worker.ptfin.local
# Порты: закомментированы
# extra_hosts: отсутствуют
```

**Что должен сделать worker:**

- [x] **S1** Переработать `docker-compose.server.yml` с поддержкой обоих вариантов через `.env.server`

  Переменные в `.env.server`:
  ```dotenv
  # Сеть
  DOCKER_NETWORK_EXTERNAL=true           # true = внешняя, false = создать новую
  DOCKER_NETWORK_NAME=ptfin-backend      # имя сети

  # Порт API (пусто = не пробрасывать)
  API_PORT_BINDING=                      # пусто для shared, "127.0.0.1:8110:8000" для standalone

  # DNS aliases (только для shared backend, пусто = не добавлять)
  API_ALIAS=pct-api.ptfin.local
  BOT_ALIAS=pct-bot.ptfin.local
  WORKER_ALIAS=pct-worker.ptfin.local
  ```

  Compose должен использовать:
  ```yaml
  ports:
    - "${API_PORT_BINDING}"              # пусто = раздел игнорируется compose
  networks:
    ${DOCKER_NETWORK_NAME}:
      aliases:
        - "${API_ALIAS:-}"
  ```

  Ограничение: Docker Compose не поддерживает условные секции (`if`), поэтому DNS aliases при пустом значении нужно либо оставить пустую строку (aliases: [""]) — протестировать, либо держать отдельные compose-overrides файлы.

  **Предпочтительное решение:** два файла:
  - `deploy/docker-compose.server.yml` — базовый, для standalone (Вариант А)
  - `deploy/docker-compose.server.shared.yml` — override для shared backend (Вариант Б), merge через `docker compose -f base.yml -f shared.yml up`

  Оба варианта с примерами документировать в `env.server.example` и `README.md`.

  Acceptance:
  - Standalone: `docker compose -f deploy/docker-compose.server.yml up` работает с postgres на хосте
  - Shared: `docker compose -f deploy/docker-compose.server.yml -f deploy/docker-compose.server.shared.yml up` подключается к внешней сети

---

### S2 — Исправить Mixed Content: статика должна отдаваться по HTTPS

**Симптом:**
```
Mixed Content: The page at 'https://pct.test.ptfin.ru/admin/subscriptions' was loaded over HTTPS,
but requested an insecure stylesheet 'http://pct.test.ptfin.ru/static/vendor/ag-grid-community/ag-grid.min.css'
```

**Причина:**
`request.url_for('static', path='...')` в Starlette/FastAPI строит URL на основе scheme входящего HTTP-запроса. Nginx терминирует TLS и проксирует в контейнер по HTTP. Контейнер видит `http://`, генерирует `http://`-ссылки на static — браузер блокирует как mixed content.

**Что должен сделать worker:**

- [x] **S2** Настроить FastAPI для доверия proxy-заголовкам (`X-Forwarded-Proto`)

  **В `api/main.py`** добавить middleware:
  ```python
  from starlette.middleware.trustedhost import TrustedHostMiddleware
  # ИЛИ (предпочтительно для scheme propagation):
  app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
  ```
  Подходящий класс: `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware`

  **В `deploy/docker-compose.server.yml`** команда uvicorn должна включать:
  ```
  --proxy-headers --forwarded-allow-ips='*'
  ```

  **В nginx** (на хосте, не в compose) обязательно:
  ```nginx
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  ```

  **Проверка:** открыть `https://pct.test.ptfin.ru/admin/subscriptions` — консоль не должна содержать Mixed Content ошибок. Ссылки на `/static/...` должны начинаться с `https://`.

---

## Блок R — Инфраструктура и notification pipeline (найдено в review 2026-03-20)

**Цель:** устранить два blocker'а, блокирующих первый live run на сервере.

- [x] **R1** Поддержка двух режимов Docker-сети в `docker-compose.server.yml`
  - `DOCKER_NETWORK_EXTERNAL=false` — создать новую сеть (standalone-сервер, postgres локально)
  - `DOCKER_NETWORK_EXTERNAL=true` + `DOCKER_NETWORK_NAME=имя` — подключиться к существующей (shared backend с Redis/postgres в сети)
  - Убрать хардкод подсети `172.20.0.0/24` из compose
  - `POSTGRES_HOST` / `POSTGRES_PORT` вынесены в `.env.server` для `migrate.sh`
  - Оба варианта задокументированы в `env.server.example`

- [x] **R3** Заменить `aiohttp` на `httpx` в `worker/jobs/notifications.py`
  - `import aiohttp` → `httpx.AsyncClient`; `aiohttp` не был объявлен в зависимостях

- [x] **R2** Запустить ARQ worker или консолидировать notification путь
  - Выбрать один из двух вариантов:
    - **A:** Добавить `arq`-сервис в `deploy/docker-compose.server.yml` (`python -m arq pitchcopytrade.worker.arq_worker.WorkerSettings`)
    - **B:** Убрать ARQ-путь для notifications; при немедленном publish вызывать `deliver_recommendation_notifications` напрямую без Redis
  - Проверить: после немедленного publish рекомендации Telegram-уведомление доставляется

- [x] **R4** Устранить дублирование notification кодпатей
  - `services/notifications.py` и `worker/jobs/notifications.py` делают одно и то же
  - Оставить один canonical path, удалить второй или явно разграничить роли

### Acceptance для Блока R
- `docker compose up` стартует без ERROR в логах api
- seeders выполняются (инструменты и admin-user создаются)
- немедленный publish → notification доставлена подписчику

---

---

## Блок T — Staff shell: навигация и layout

### Контекст по текущей структуре

`staff_base.html` строит двухколонный layout:
```
[.staff-rail 238px] [.staff-main flex/grow]
```

`.staff-main` содержит сверху вниз:
- `.staff-topline` — строка с breadcrumb, кнопкой «Назад», быстрыми actions и role-switch
- `.staff-card` — один или несколько информационных блоков (счётчики, фильтры, summary)
- `.staff-grid-shell` — обёртка AG Grid, занимает оставшееся место

Сейчас все три слоя просто стекаются вертикально и страница растёт вниз вместе с grid. Нужно зафиксировать shell в viewport.

---

### T1 — Убрать «Авторы» из левой навигации

**Проблема:** В `staff_base.html` левый рейл содержит отдельную nav-группу «Авторы» (`/admin/authors`). Это избыточно — авторы создаются и управляются через «Команда» (`/admin/staff`), выделять их в отдельный раздел нет смысла.

**Что сделать:**
- [x] **T1** Удалить пункт «Авторы» из левого nav в `staff_base.html`
  - Ссылка на `/admin/authors` убирается из `<nav>` в `.staff-rail`
  - Доступ к авторам остаётся через `/admin/staff` (существующая вкладка «Команда»), страница авторов доступна по прямому URL
  - `is-active` подсветка для `/admin/authors` удаляется из nav, но сами роуты не трогаются

---

### T2 — Layout: staff shell фиксирован по высоте viewport

**Проблема:** Страница вертикально скроллируется целиком. AG Grid не заполняет оставшуюся высоту экрана. Это неудобно — оператор должен видеть весь реестр без прокрутки страницы, только внутри grid.

**Целевое поведение:**
- Страница НЕ скроллируется. Весь shell помещается в `100vh`.
- `.staff-topline` — фиксированная высота (естественный размер, `flex-shrink: 0`)
- `.staff-card` блоки — фиксированная высота (естественный размер, `flex-shrink: 0`)
- Последний элемент (`.staff-grid-shell` или любой контейнер AG Grid) — занимает всё оставшееся пространство (`flex: 1; min-height: 0`)
- AG Grid сам скроллируется внутри своего контейнера

**Текущий CSS (в `staff_base.html` или `staff.css`):**
```css
.staff-main { display: grid; gap: 10px; padding: 12px; }
/* нет height: 100vh, нет flex с fill */
```

**Целевой CSS:**
```css
.staff-shell {
  height: 100vh;
  overflow: hidden;          /* запрет scroll на уровне shell */
}
.staff-main {
  display: flex;
  flex-direction: column;
  height: 100%;              /* занять всё, что дала .staff-shell */
  padding: 12px;
  gap: 10px;
  overflow: hidden;
}
.staff-topline {
  flex-shrink: 0;            /* не сжимается */
}
.staff-card {
  flex-shrink: 0;            /* не сжимается */
}
.staff-grid-shell {          /* последний контейнер */
  flex: 1;
  min-height: 0;             /* обязательно для flex overflow */
  overflow: hidden;
}
```

AG Grid требует явной высоты на контейнере. Если `height: 100%` не работает из-за flex, дополнительно:
```css
.staff-grid-shell .ag-root-wrapper { height: 100%; }
```

- [x] **T2** Реализовать фиксированный viewport layout для staff shell
  - Правки только в CSS (не трогать Python/роуты)
  - Работает на всех staff экранах: `/admin/*`, `/author/*`, `/moderation/*`
  - На мобилах (< 768px) поведение можно оставить как сейчас (вертикальный scroll)
  - Проверить на экранах без grid (формы стратегий, detail views) — форма должна скроллироваться внутри `.staff-main`, а не распирать shell

### Acceptance для Блока T
- «Авторы» отсутствует в левом nav; `/admin/authors` продолжает работать по URL
- На staff-экранах с grid страница не скроллируется целиком; grid занимает оставшуюся высоту
- На экранах с формами (strategy_form, recommendation_form) scroll работает корректно

---

## Блок U — Author editor: стратегии и рекомендации

### U1 — Redirect после создания стратегии → на список

**Проблема:** После успешного `POST /author/strategies` (создание новой стратегии) происходит redirect на `/author/strategies/{id}/edit`. Пользователь сразу попадает в editor только что созданной стратегии. Нужно вернуть его на список.

**Текущий код** (`api/routes/author.py`):
```python
# POST /author/strategies (create)
return RedirectResponse(url=f"/author/strategies/{strategy.id}/edit", status_code=303)
```

**Нужно:**
```python
return RedirectResponse(url="/author/strategies", status_code=303)
```

**Важно:** Edit submit (`POST /author/strategies/{id}`) оставить как есть — после сохранения правки оставаться в editor.

- [x] **U1** Изменить redirect после создания стратегии: `/author/strategies/{id}/edit` → `/author/strategies`
  - Только для create (новая стратегия); edit save redirect не менять

---

### U2 — Рекомендации: визуальные и функциональные правки

**Контекст по текущей структуре** (`author/recommendations_list.html`):

Inline shortcut — строка в таблице `id="inline-recommendation-shortcut"`. Содержит:
- `<td>` → `<select>` стратегия
- `<td>` → `<input name="title" placeholder="Идея">` и `<input name="instrument_query" placeholder="Бумага">` стоят **вертикально** внутри одного `<td>` (block/стек)
- `<td>` → `<select>` направление (BUY/SELL)
- ... цена, TP, стоп, кнопки

Подсказка `"Создать добавит строку в реестр, а Детально откроет полный редактор..."` — отдельный элемент под строкой или в ней.

Popup тикера `id="inline-ticker-popup"` — `position: absolute` внутри `<td>`, но таблица или shell имеет `overflow: hidden`. Popup обрезается.

- [x] **U2** Компактная таблица рекомендаций
  - Уменьшить толщину borders в ag-grid до `1px` или сделать `hairline`
  - Row height снизить до 28–30px если ещё не сделано
  - Правки в `staff/ag-grid-theme.css`

- [x] **U3** «Идея» и «Бумага» в одну строку в inline shortcut
  - В `<td>` где сейчас два input-а вертикально (Идея + Бумага), сделать `display: flex; flex-direction: row; gap: 6px`
  - Оба инпута в одной строке, ширина делится пополам или `Идея` уже
  - picker-state div (`id="inline-picker-state"`) выносится под инпуты как hint строка

- [x] **U4** Убрать/скрыть hint «Создать добавит строку...»
  - Текст убирается из постоянной видимости
  - Вариант А: tooltip на hover/focus кнопки «Создать» (HTML `title` атрибут достаточно)
  - Вариант Б: `display: none` или очень мелкий `muted` текст под shortcut-строкой, видный только при фокусе
  - Не удалять смысл — просто не занимать место на экране

- [x] **U5** Исправить popup тикера: обрезается внутри контейнера
  - `id="inline-ticker-popup"` имеет `position: absolute` и обрезается parent с `overflow: hidden`
  - Исправление: перевести popup в `position: fixed` с пересчётом координат через JS (getBoundingClientRect), или переместить popup в `<body>` через портал
  - Popup должен открываться поверх grid и не клипаться ни таблицей, ни shell

  **Текущий JS** (в конце `recommendations_list.html`): popup показывается через `hidden` toggle, позиционирование не пересчитывается. Нужно добавить:
  ```js
  // При показе popup:
  const rect = triggerInput.getBoundingClientRect();
  popup.style.position = 'fixed';
  popup.style.top = (rect.bottom + 2) + 'px';
  popup.style.left = rect.left + 'px';
  popup.style.width = rect.width + 'px';
  ```

- [x] **U6** Исправить Internal Server Error при «Создать» (inline рекомендация)
  - `POST /author/recommendations` с `inline_mode=1` возвращает 500
  - **Что проверить:**
    1. `api/routes/author.py` — функция `author_recommendation_create_submit` — какое поле вызывает исключение
    2. Смотреть traceback в `docker compose logs api` при нажатии «Создать»
    3. Вероятные причины: `strategy_id` пустой UUID не конвертируется; `leg_1_instrument_id` пустой вызывает FK constraint; `recommendation_kind` не передаётся в inline form (нет поля) и сервис падает на `None`
    4. Проверить: в `id="inline-recommendation-form"` есть ли `<input name="kind" value="new_idea">`
  - Добавить `<input type="hidden" name="kind" value="new_idea">` в inline form если отсутствует
  - Добавить явную валидацию в route: если `strategy_id` пустой — вернуть 422 с понятной ошибкой, а не 500

---

### U7 — «Сохранить в черновик» → Internal Server Error (root cause установлен)

**Traceback из логов:**
```
sqlalchemy.exc.DBAPIError: invalid input for query argument $1: 'new'
(invalid UUID 'new': length must be between 32..36 characters, got 3)
[SQL: SELECT recommendations... WHERE recommendations.id = $1::UUID]
[parameters: ('new', 'b463ac5c-...')]
```

**HTTP запрос из логов:**
```
GET /author/recommendations/new?embedded=1&next=%2Fauthor%2Frecommendations&strategy_id=e7137e04-...&title=...
```

**Анализ root cause:**

В `recommendation_form.html` форма не имеет явного атрибута `action`:
```html
<form class="surface author-editor-form" method="post" enctype="multipart/form-data">
```

По стандарту HTML, форма без `action` отправляется на **текущий URL**. Текущий URL при создании новой рекомендации в iframe — `/author/recommendations/new?embedded=1&...`.

Значит `POST /author/recommendations/new` попадает в маршрут `POST /author/recommendations/{recommendation_id}` с `recommendation_id='new'`. Этот маршрут пытается найти рекомендацию в БД с id='new' → `invalid UUID 'new'` → 500.

**Что должен сделать worker:**

- [x] **U7** Добавить явный `action` в форму создания новой рекомендации

  В `recommendation_form.html`, строка с `<form ...>`:
  ```html
  <form
    class="surface author-editor-form"
    method="post"
    enctype="multipart/form-data"
    action="{% if recommendation %}/author/recommendations/{{ recommendation.id }}{% else %}/author/recommendations{% endif %}"
  >
  ```

  Это гарантирует:
  - Новая рекомендация (`recommendation=None`) → POST на `/author/recommendations`
  - Редактирование (`recommendation.id` = UUID) → POST на `/author/recommendations/{uuid}`
  - Форма больше не делает self-submit на URL с `new` в пути

  **Проверка:** Нажать «Сохранить в черновик» в embedded режиме (через «Детально») → рекомендация создаётся без 500.

---

### U8 — Модальное окно «Детально»: полная страница вместо core-блока

**Проблема:**
При нажатии «Детально» открывается `<dialog>` с `<iframe src="/author/recommendations/new?embedded=1&...">`. Параметр `embedded=1` уже учитывается в шаблоне, но убирает только узкие элементы (`.topbar { display: none }`). Полный `staff_base.html` layout — rail, topline, staff-shell — остаётся. Пользователь видит повторение всего интерфейса внутри модалки.

**Текущий `embedded` режим (recommendation_form.html):**
```html
{% if embedded %}
<style>
  .topbar { display: none; }
  .page-shell { width: min(1180px, calc(100% - 12px)); padding-top: 8px; }
</style>
{% endif %}
```

`staff_base.html` всё ещё является parent-шаблоном → rail + shell + topline рендерятся.

**Целевое поведение:**
Когда `embedded=True`, форма рендерится в **минималистичном** HTML-шелле: только `<html><head>...</head><body>{{ form }}</body></html>`, без staff-rail, без topline, без breadcrumb. Внутри остаётся только блок `.surface.author-editor-section` с полями формы и кнопками.

**Что должен сделать worker:**

- [x] **U8** Создать минимальный base-шаблон для embedded-режима

  1. Создать `src/pitchcopytrade/web/templates/embedded_base.html`:
     ```html
     <!doctype html>
     <html lang="ru">
     <head>
       <meta charset="utf-8">
       <meta name="viewport" content="width=device-width, initial-scale=1">
       {% block head %}{% endblock %}
     </head>
     <body class="embedded-shell">
       {% block content %}{% endblock %}
     </body>
     </html>
     ```

  2. В `recommendation_form.html` изменить выбор parent-шаблона:
     ```jinja2
     {% if embedded %}
       {% extends "embedded_base.html" %}
     {% else %}
       {% extends "staff_base.html" %}
     {% endif %}
     ```

  3. Этот же принцип применить ко **всем формам, которые открываются в modal**:
     - `recommendation_form.html` — уже описано выше
     - Любой другой шаблон с `?embedded=1` паттерном (проверить: grep по `embedded` в `templates/`)

  4. В `embedded_base.html` подключить только необходимые CSS (формы, инпуты) без staff-rail стилей. AG Grid и staff-shell CSS не нужны.

  **Acceptance:**
  - Modal открывается → виден только блок формы с полями и кнопками
  - Нет staff rail, нет topline, нет breadcrumb
  - Форма корректно сабмитится (U7 уже исправляет action)
  - После закрытия modal список рекомендаций обновляется (HTMX или JS reload)

---

### Acceptance для Блока U
- После нажатия «Создать» стратегию → переход на список `/author/strategies`
- Inline shortcut: «Идея» и «Бумага» в одной строке
- Hint-текст не занимает место на экране постоянно
- Popup тикера виден целиком, не обрезается
- «Сохранить в черновик» не вызывает 500 (U7 + U8)
- Модальное окно показывает только форму, без staff shell

---

## Текущий program block

**Блок Y → X3 → V3 → X4 → Блок F**

Блоки S, R, T, U, V, W, X1 закрыты. Открытых production bug нет. Следующий исполнитель:
1. **Блок Y** — invite token race + SMTP retry + startup validation + open redirect fix
2. **X3** — улучшить invite flow через бота (deep link в email)
3. **V3** — ручной smoke-test на живом сервере
4. **X4** — Google/Yandex OAuth (после настройки credentials)
5. **Блок F** — F1 oversight emails, F2–F3 parity + regression coverage

---

## Блок Y — Reliability: invite token, SMTP, startup, open redirect

### Контекст

Архитектурный review выявил 4 проблемы, не являющихся production bug-ами сейчас, но блокирующих коммерческий запуск с реальными пользователями. Все 4 исправляемы изолированно.

---

### Y1 — Invite token race: инкремент версии до email delivery

**Файл:** `src/pitchcopytrade/services/admin.py`, функция `resend_staff_invite` (найти по имени)

**Проблема (точная):**
При resend invite происходит следующая последовательность:
1. `user.invite_token_version += 1` — старый токен инвалидирован
2. `await repository.commit()` — новая версия зафиксирована в DB
3. `await _send_invite_email(user, ...)` — SMTP вызов

Если шаг 3 упал (SMTP timeout, DNS error) — старый токен уже недействителен, новое письмо не отправлено. Пользователь заблокирован, admin видит `invite_delivery_status=FAILED`.

**Что делать:**

- [x] **Y1.1** Прочитать функцию `resend_staff_invite` в `services/admin.py` полностью — найти точный порядок операций
- [x] **Y1.2** Проверить: есть ли rollback `invite_token_version` при SMTP failure?
- [x] **Y1.3** Если rollback нет — добавить: при исключении в `_send_invite_email` делать `user.invite_token_version -= 1` + `await repository.commit()` в `except` блоке
- [x] **Y1.4** Написать inline-комментарий в коде о причине rollback
- [x] **Y1.5** `python3 -m compileall src tests`

**Acceptance Y1:**
- При SMTP failure версия возвращается к предыдущей — старый токен остаётся рабочим
- `invite_delivery_status` выставляется в FAILED (информационно для admin)
- Компиляция чистая

---

### Y2 — SMTP без таймаута: зависание HTTP request при invite creation

**Файл:** `src/pitchcopytrade/services/admin.py`, функция `_deliver_staff_invite`

**Проблема:**
Email отправляется синхронно в рамках HTTP request на `POST /admin/staff`. Если SMTP сервер не отвечает — request висит до таймаута aiosmtplib (по умолчанию может быть 60+ сек). UX: admin видит «loading» без фидбека.

**Что делать:**

- [x] **Y2.1** Прочитать `_deliver_staff_invite` в `services/admin.py` — найти как вызывается aiosmtplib
- [x] **Y2.2** Проверить: установлен ли `timeout` в вызове aiosmtplib? Найти `aiosmtplib.send(` или `SMTP(`.
- [x] **Y2.3** Если timeout не установлен или > 10 сек — добавить явный `timeout=10` (секунд) в вызов
- [x] **Y2.4** Обернуть SMTP вызов в `asyncio.wait_for(..., timeout=10.0)` если aiosmtplib не поддерживает timeout напрямую
- [x] **Y2.5** При `asyncio.TimeoutError` — логировать как WARNING, выставлять `invite_delivery_status = FAILED`, НЕ падать с 500
- [x] **Y2.6** `python3 -m compileall src tests`

**Acceptance Y2:**
- SMTP вызов не висит дольше 10-15 сек
- При timeout: staff user создан, email failed, admin видит FAILED статус (не 500)
- `docker logs pct-api` не показывает необработанные исключения aiosmtplib

---

### Y3 — Нет проверки placeholder vars при startup

**Файл:** `src/pitchcopytrade/api/lifespan.py` + `src/pitchcopytrade/core/config.py`

**Проблема:**
Если `APP_SECRET_KEY=__FILL_ME__` в `.env.server` — приложение стартует без ошибки. Падение произойдёт при первом JWT вызове (auth), что трудно диагностировать в production.

**Placeholder vars которые нужно проверить при startup:**
- `APP_SECRET_KEY` — если `__FILL_ME__`, все токены невалидны
- `TELEGRAM_BOT_TOKEN` — если `__FILL_ME__`, бот не запустится
- `INTERNAL_API_SECRET` — если `__FILL_ME__`, internal auth сломан

**Что делать:**

- [x] **Y3.1** Прочитать `src/pitchcopytrade/api/lifespan.py` полностью — найти startup checks
- [x] **Y3.2** Прочитать `src/pitchcopytrade/core/config.py` — найти как определены `APP_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `INTERNAL_API_SECRET`; есть ли `_is_placeholder()` функция?
- [x] **Y3.3** В lifespan startup (после `settings = get_settings()`) добавить check: добавлен `INTERNAL_API_SECRET` в `SERVICE_REQUIRED_SECRETS` в runtime.py
- [x] **Y3.4** Добавить аналогичный check в `src/pitchcopytrade/bot/main.py` startup (если есть lifespan): используется `bootstrap_runtime` который уже валидирует
- [x] **Y3.5** `python3 -m compileall src tests`

**Acceptance Y3:**
- `docker compose up api` с placeholder `APP_SECRET_KEY` — контейнер завершается с явным сообщением об ошибке в логах
- С правильными vars — стартует нормально

---

### Y4 — Open redirect в miniapp_entry.html

**Файл:** `src/pitchcopytrade/web/templates/app/miniapp_entry.html`

**Проблема:**
```javascript
window.location.href = data.redirect_url || "/app/status";
```
`data.redirect_url` приходит от сервера. Сервер контролирует через `_sanitize_subscriber_next_path()` (разрешает только пути начинающиеся с `/`). Но явной проверки в JS нет — если сервер вернёт внешний URL (например из-за bug или compromise), браузер перейдёт туда.

**Что делать:**

- [x] **Y4.1** В `miniapp_entry.html` перед `window.location.href = ...` добавить проверку: добавлена валидация redirect URL
- [x] **Y4.2** Проверить `_sanitize_subscriber_next_path` в `auth.py` — убедиться что она уже запрещает `//` пути и внешние URL: добавлена нормализация с `replace('\', '/')`

**Acceptance Y4:**
- Если сервер вернёт `{"redirect_url": "https://evil.com"}` — браузер останется на `/app/status`
- Если сервер вернёт `{"redirect_url": "//evil.com"}` — то же самое

---

### Acceptance для Блока Y

1. Y1: invite resend при SMTP failure не инвалидирует старый токен
2. Y2: SMTP вызов имеет явный timeout ≤ 15 сек; при timeout — FAILED статус, не 500
3. Y3: startup с placeholder vars завершается с явной ошибкой
4. Y4: open redirect защищён в JS
5. `python3 -m compileall src tests` — чисто

---

## Блок W — Code quality: notification loop fix + dead code cleanup

### W1 — Исправить delivery loop в worker/placeholders.py (production bug)

**Контекст:**
В `run_scheduled_publish()` цикл доставки уведомлений не защищён от исключений на уровне одного элемента. Если Telegram API вернёт ошибку для рекомендации N, цикл прерывается через `except` выше, и рекомендации N+1…end **никогда не получают уведомление**. Статус у них `PUBLISHED` (уже сохранён в DB), но подписчики не уведомлены. Это тихая частичная потеря.

Пример сценария: 3 рекомендации ушли в scheduled publish одновременно. У второй — Telegram вернул `TelegramForbiddenError` (бот заблокирован одним из получателей). Исключение пробрасывается наружу, третья рекомендация не обрабатывается.

**Файл:** `src/pitchcopytrade/worker/jobs/placeholders.py`

---

**W1.1 — File mode (строки 63–74)**

Найти этот блок:
```python
        bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
        try:
            for item in published:
                await deliver_recommendation_notifications_file(
                    graph,
                    store,
                    item,
                    bot,
                    trigger="scheduled_publish",
                )
        finally:
            await bot.session.close()
```

Заменить на:
```python
        bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
        try:
            for item in published:
                try:
                    await deliver_recommendation_notifications_file(
                        graph,
                        store,
                        item,
                        bot,
                        trigger="scheduled_publish",
                    )
                except Exception:
                    logger.exception("Notification delivery failed for recommendation %s", item.id)
        finally:
            await bot.session.close()
```

- [x] **W1.1** Применить замену в file mode блоке

---

**W1.2 — DB mode (строки 81–86)**

Найти этот блок:
```python
            bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
            try:
                for item in published:
                    await deliver_recommendation_notifications(session, item, bot, trigger="scheduled_publish")
            finally:
                await bot.session.close()
```

Заменить на:
```python
            bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
            try:
                for item in published:
                    try:
                        await deliver_recommendation_notifications(session, item, bot, trigger="scheduled_publish")
                    except Exception:
                        logger.exception("Notification delivery failed for recommendation %s", item.id)
            finally:
                await bot.session.close()
```

- [x] **W1.2** Применить замену в db mode блоке

---

**W1.3 — Проверка**

- [x] **W1.3** `python3 -m compileall src tests` — без ошибок
- [x] **W1.4** Убедиться что `finally: await bot.session.close()` остался на уровне внешнего try — его двигать не нужно

**Acceptance W1:**
- В обоих блоках (file и db) каждый `deliver_*` вызов обёрнут в `try/except Exception`
- Исключение на item N логируется через `logger.exception(...)` и **не прерывает** обработку item N+1
- Внешний `finally: await bot.session.close()` не тронут
- `compileall` — чисто

---

### W2 — Заменить string comparison на enum в moderation.py

**Что делать:**

- [x] **W2.1** В `src/pitchcopytrade/api/routes/moderation.py` строка 103 заменить:
  ```python
  # было:
  if updated.status.value == "published":
  # стало:
  if updated.status == RecommendationStatus.PUBLISHED:
  ```
  `RecommendationStatus` уже импортирован в этом файле.

**Acceptance W2:**
- `updated.status == RecommendationStatus.PUBLISHED` без `.value`

---

### W3 — Удалить мёртвый файл worker/jobs/notifications.py

**Контекст:**
`send_recommendation_notifications(ctx, ...)` — ARQ-handler. ARQ удалён. Функция никем не вызывается в production. Импортируется только в `test_worker_baseline.py`.

**Что делать:**

- [x] **W3.1** Прочитать `tests/test_worker_baseline.py` — какие тесты импортируют `send_recommendation_notifications`
- [x] **W3.2** Оценить: если тесты проверяют делегирование ARQ-хэндлера → бесполезны без ARQ; удалить эти тесты
- [x] **W3.3** Удалить `src/pitchcopytrade/worker/jobs/notifications.py`
- [x] **W3.4** `grep -r "notifications" src/pitchcopytrade/worker/` — убедиться что других импортов нет
- [x] **W3.5** `python3 -m compileall src tests` — чисто

**Acceptance W3:**
- Файл удалён
- Тесты зависящие от него либо удалены, либо обновлены
- `compileall` — чисто

---

### W4 — Обновить комментарии в env.server.example

**Что делать:**

- [x] **W4.1** В `deploy/env.server.example` строки 65, 75–78:
  - Строка 65: убрать `и redis` из `postgres и redis в сети`
  - Строки 75–78: заменить `# Уведомления (ARQ + Redis + SMTP)` на `# Уведомления (SMTP)`, убрать комментарии про redis URL варианты
  - Строка 81: `REDIS_URL` оставить (конфиг его читает), но добавить комментарий что ARQ не используется

---

### W5 — Удалить неиспользуемый импорт func в cabinet.py

**Что делать:**

- [x] **W5.1** В `src/pitchcopytrade/api/routes/cabinet.py` строка 13:
  ```python
  # было:
  from sqlalchemy import func, select
  # стало:
  from sqlalchemy import select
  ```

---

### Acceptance для Блока W

1. Notification loop: per-item exception handling в обоих режимах
2. `moderation.py` — enum comparison
3. `worker/jobs/notifications.py` удалён
4. `env.server.example` — комментарии про ARQ убраны
5. `func` удалён из import cabinet.py
6. `python3 -m compileall src tests` — чисто

---

## Блок V — Cleanup, notification smoke-test, subscriber flow

### V1 — Удалить мёртвый код ARQ

**Контекст:**
`api/lifespan.py` отключил ARQ pool (`app.state.arq_pool = None`). `worker/arq_worker.py` определяет `WorkerSettings` для ARQ, но никогда не запускается. `arq` пакет остаётся в зависимостях. Это мёртвый код — он вводит в заблуждение при чтении проекта.

**Что делать:**

- [x] **V1.1** Прочитать `worker/arq_worker.py` полностью
  — убедиться, что файл нигде не импортируется кроме возможного `__init__.py`
  — команда: `grep -r "arq_worker" src/ tests/`

- [x] **V1.2** Удалить файл `src/pitchcopytrade/worker/arq_worker.py`

- [x] **V1.3** Проверить `src/pitchcopytrade/services/publishing.py` полностью
  — найти все вызовы `arq_pool.enqueue_job(...)` или `request.app.state.arq_pool`
  — если такой вызов есть: убедиться, что он обёрнут в `if arq_pool is not None:` или уже заменён на direct delivery
  — если вызов без проверки — заменить на `deliver_recommendation_notifications(session, rec, bot)`

- [x] **V1.4** Проверить `pyproject.toml` — использует ли `arq` пакет ещё что-то в проекте кроме `arq_worker.py`
  — команда: `grep -r "import arq\|from arq" src/`
  — если `arq` используется только в `worker/arq_worker.py` (уже удалён) и `api/lifespan.py` импортировал его — проверить `lifespan.py` на наличие `from arq import`
  — если `arq` больше нигде не импортируется: удалить из `pyproject.toml` → `dependencies`

- [x] **V1.5** Запустить `python3 -m compileall src tests`
  — должно пройти без ошибок

**Acceptance V1:**
- `grep -r "arq_worker" src/ tests/` — пустой вывод
- `python3 -m compileall src tests` — чисто
- `publishing.py` не вызывает `enqueue_job` без проверки на None или не вызывает вообще

---

### V2 — Проверить и починить notification flow при немедленном publish

**Контекст:**
ARQ отключён. Когда автор публикует рекомендацию немедленно (не scheduled), `publishing.py` должен либо вызывать `deliver_recommendation_notifications` напрямую, либо пропускать уведомление. Scheduled publish работает через polling worker (`placeholders.py` → `run_scheduled_publish`). Immediate publish — отдельный code path.

**Что делать:**

- [x] **V2.1** Прочитать `services/publishing.py` полностью
  — найти функцию publish рекомендации (скорее всего `publish_recommendation` или `publish_now`)
  — понять: как она обрабатывает immediate publish? вызывает ли notifications?

- [x] **V2.2** Прочитать `api/routes/author.py`, маршрут `POST /author/recommendations/{id}/publish` (или аналог)
  — найти где вызывается publish и как передаётся `arq_pool`
  — если `request.app.state.arq_pool` используется: проверить что `None` обрабатывается корректно

- [x] **V2.3** Реализован Вариант A в `api/routes/cabinet.py`:
  ARQ-блок заменён на прямой вызов `deliver_recommendation_notifications_by_id`.
  `author.py` использовал прямую доставку через `_deliver_author_publish_notifications` — уже корректен.

- [x] **V2.4** Проверить что `run_scheduled_publish` в `placeholders.py` корректно работает в db-режиме
  — читать лог `pct-worker`: должен быть `scheduled_publish tick: 0 published` каждые 3600 сек без EXCEPTION

**Acceptance V2:**
- `pct-worker` лог не содержит EXCEPTION для scheduled_publish
- Immediate publish: либо notification уходит в Telegram, либо есть явный лог-warning что ARQ отключён и уведомление пропущено
- Не возникает AttributeError при publish рекомендации

---

### V3 — Smoke-test: полный сценарий от создания до уведомления

**Контекст:**
После V1 и V2 — ручная проверка ключевого business flow. Цель: убедиться что весь chain работает на живом сервере.

Локально repo-chain покрыт automated smoke-test (`tests/test_author_services.py::test_file_mode_smoke_publish_notifies_active_subscriber`), но live-проверка в этой среде заблокирована: нет доступа к серверу, test Telegram inbox и SMTP.
Runbook для server-side smoke-check и снятия логов добавлен в `deploy/README.md` (`V3 live smoke-check and log capture`).

**Что делать (ручной тест на live-сервере):**

- [!] **V3.1** Создать тестового подписчика
  — через `/app/*` или через `admin/subscriptions` создать подписку для тестового telegram_user_id
  — убедиться статус `active`

- [!] **V3.2** Создать рекомендацию через author cabinet
  — `/author/recommendations` → inline «Создать» или кнопку «Детально»
  — заполнить: стратегия, тикер, направление, цена
  — «Сохранить в черновик» → рекомендация создана, нет 500

- [!] **V3.3** Опубликовать рекомендацию
  — поменять статус на Published (из admin или author)
  — проверить `docker compose logs api` — нет EXCEPTION

- [!] **V3.4** Проверить что уведомление дошло
  — тестовый telegram_user_id получил сообщение (немедленно или в течение 1 часа через worker)
  — `docker compose logs worker` — лог `scheduled_publish tick: 1 published` при следующем цикле

- [!] **V3.5** Проверить email-уведомление (если SMTP настроен)
  — subscriber с email должен получить письмо
  — `docker compose logs worker` — нет SMTP error

**Runbook:** см. `deploy/README.md` раздел «V3 live smoke-check and log capture»

**Acceptance V3:**
- Рекомендация создаётся без ошибок
- Публикация не вызывает 500
- Подписчик получает Telegram-уведомление (в течение 1 цикла worker или немедленно)

---

### Acceptance для Блока V

1. `worker/arq_worker.py` удалён; компиляция чистая
2. `publishing.py` не падает при None arq_pool
3. Polling worker работает без EXCEPTION в логах
4. Рекомендация создаётся → публикуется → подписчик уведомлён

---

### Не делать в Блоке V

- Не переписывать notification архитектуру заново
- Не возвращать ARQ — решение принято, direct delivery
- Не трогать subscriber mini-app (`/app/*`) — это отдельный блок
- Не менять schema.sql — V не требует миграций

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

- [x] **F0** Закрыть `P1` по последнему активному администратору
  - `update_admin_staff_user` не должен позволять убрать роль `admin` у последнего активного администратора
  - защита должна совпадать с отдельным `roles/admin/remove`
  - одинаково в `db` и `file` mode
  - UI должен возвращать бизнес-ошибку, а не частично применять update

- [x] **F1** Выровнять control emails по mode
  - `db` и `file` path должны одинаково отправлять уведомления активным администраторам
  - failed delivery не должен молча выпадать в одном из режимов

- [x] **F2** Проверить `db/file` parity на staff onboarding
  - create
  - resend
  - oversight mail
  - audit log

- [x] **F3** Добавить regression coverage
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

- [x] **M1** Убрать oversized page-head/hero из remaining admin surfaces
  - reference baseline = `/author/dashboard`
  - `/author/strategies`
  - `/author/recommendations`
  - `/admin/staff`
  - `/admin/products`
  - `/admin/legal`
  - `/admin/payments`
  - `/admin/subscriptions`
  - `/admin/delivery`
  - `/admin/promos`
  - `/admin/analytics/leads`
  - если тот же oversized top-shell паттерн остался на других staff surfaces, привести и их к этому же baseline в рамках одного прохода

- [x] **M2** Довести compact registries до консистентного operator-readability
  - в списке должно быть видно ключевое содержимое записи до клика `Открыть`
  - для row summary использовать 1-2 compact secondary lines вместо большого detail-screen dependence
  - не плодить большие пустые зоны ради декоративного copy

- [x] **M3** Перевести remaining admin forms в compact section layout
  - `admin/product_form.html`
  - `admin/legal_form.html`
  - `admin/promo_form.html`
  - `admin/payment_detail.html`
  - `admin/subscription_detail.html`
  - `admin/delivery_detail.html`

- [x] **M4** Упростить operator affordances
  - в быстрых строках создания CTA должен быть явным по результату, а не символьным
  - helper copy должен объяснять следующий шаг в 1 короткой строке
  - статусы и secondary hints должны оставаться компактными

- [x] **M5** Добавить regression/manual acceptance coverage
  - smoke-check на отсутствие giant hero-block на указанных surfaces
  - smoke-check на compact registries, где ключевые поля видны без открытия карточки
  - smoke-check на inline create CTA и immediate next step

### Acceptance

- staff surfaces не содержат больших пустых hero-зон как primary pattern
- ключевые поля записи видны в реестре до открытия detail/edit
- remaining admin forms используют тот же compact section language, что и strategy/recommendation editors
- inline operator shortcuts объясняют результат действия без двусмысленности

---

## Блок N — Split inline create для `/author/recommendations`

**Цель:** нижняя shortcut-строка рекомендаций должна перестать смешивать inline-create и переход в full editor в одну кнопку.

- [x] **N1** Разделить inline shortcut на два разных действия
  - `Создать` — создает черновик из inline-ввода после локальной проверки обязательных полей
  - `Детально` — открывает полный create-flow рекомендации
  - top action `Новая рекомендация` и inline action `Детально` должны вести в один и тот же detailed create contour

- [x] **N2** Явно определить data-flow для обеих кнопок
  - `Создать` не должен неявно открывать редактор, если по смыслу действие только создает строку
  - `Детально` должен переносить уже введенные значения из shortcut-строки в full editor как prefill
  - если shortcut-строка пуста, `Детально` открывает обычный пустой detailed create flow

- [x] **N3** Довести validation contract для inline create
  - `Создать` должен валидировать стратегию, бумагу и направление как минимальный обязательный набор
  - если введены ценовые поля, ошибки должны оставаться локальными и понятными
  - текст CTA и helper copy не должны вводить в заблуждение относительно следующего шага

- [x] **N4** Добавить regression/manual acceptance coverage
  - UI test на наличие двух разных CTA в inline shortcut
  - test на prefill при переходе через `Детально`
  - smoke-check на inline create без открытия full editor

### Acceptance

- на нижней строке `/author/recommendations` есть два разных действия: `Создать` и `Детально`
- inline create и detailed create больше не смешаны в одну кнопку
- `Детально` переиспользует уже введенные данные, а не теряет их
- intent каждого действия понятен без дополнительного объяснения

---

## Блок O — Hardening для `/admin/authors`

**Цель:** registry `/admin/authors` должен стабильно открываться на реальных server-данных и не падать raw `500`.

- [x] **O1** Воспроизвести и локализовать server-side причину `Internal Server Error`
  - снять traceback из `api` logs на текущем dataset
  - зафиксировать точную точку падения: route, service, row builder или template rendering
  - проверить кейсы с неполным staff bind, неожиданным набором ролей и частично заполненными invite-полями

- [x] **O2** Сделать registry и row rendering null-safe
  - `/admin/authors` не должен падать из-за missing related user/profile fields
  - role/status/invite rendering должен устойчиво переносить sparse data
  - route обязан либо рендерить список, либо отдавать controlled business-state без raw traceback в браузер

- [x] **O3** Добавить regression coverage
  - route/UI test на `/admin/authors` с неполными связанными данными
  - service test на устойчивое построение author row
  - smoke-check на открытие `/admin/authors` после создания/редактирования author/staff записей

### Acceptance

- `/admin/authors` открывается без raw `500` на текущем server-датасете
- неполные или нестандартные связанные данные не валят registry
- при ошибке пользователь видит controlled state, а не пустой Internal Server Error

---

## Блок P — Friendly validation copy и valid inline DOM в `/author/recommendations`

**Цель:** recommendation shortcut и editor не должны светить внутренние parser-тексты и не должны зависеть от невалидной table/form разметки.

- [x] **P1** Убрать raw validation copy из user-facing feedback
  - inline error summary не должен показывать строки вида `Leg 1: ...`
  - full editor error summary тоже не должен показывать внутренние parser tokens
  - локальные field-level ошибки должны остаться, но общий текст нужно привести к русской operator-copy

- [x] **P2** Привести inline shortcut к валидной HTML-разметке
  - убрать паттерн `tr > form > td`
  - использовать валидную table/form схему (`form=` attributes, отдельный form-container или другой стабильный вариант)
  - обе CTA (`Создать`, `Детально`) и picker бумаги должны остаться рабочими после DOM cleanup

- [x] **P3** Добавить regression coverage
  - UI test на отсутствие raw `Leg 1` / `entry_to` в user-facing response body
  - test на сохранение split-flow после перевода shortcut-строки на валидную DOM-структуру

### Acceptance

- пользователь не видит raw validation строк вроде `Leg 1: entry_to ...`
- inline shortcut использует валидную table/form разметку
- split-flow `Создать` / `Детально` не ломается после DOM cleanup

---

## Блок Q — Multi-admin-safe bootstrap seeder

**Цель:** startup admin seeder не должен шуметь и падать на валидной базе, где уже есть несколько администраторов.

- [x] **Q1** Сделать presence-check idempotent-safe
  - не использовать `scalar_one_or_none()` на запросе, который может валидно вернуть больше одной строки
  - проверка существующего admin должна корректно работать для 0, 1 и N администраторов

- [x] **Q2** Нормализовать startup behavior и логи
  - если в системе уже есть хотя бы один admin, seeder должен quietly skip bootstrap
  - `api` lifespan не должен логировать `Multiple rows were found when one or none was required` как startup error на валидном state

- [x] **Q3** Добавить regression coverage
  - seeder test на базу с двумя admin users
  - acceptance path для startup без error-log на multi-admin dataset

### Acceptance

- bootstrap seeder корректно пропускается при наличии одного или более администраторов
- startup не шумит ошибкой `Multiple rows were found...` на валидной рабочей базе
- regression tests покрывают multi-admin state

---

## Блок X — Staff invite без Telegram ID + Mini App auth fix

### X1 — Mini App: сломан вход через initData (ИСПРАВЛЕНО)

**Контекст:**
`GET /app` перенаправлял неаутентифицированных пользователей на `/login`. Страница `/login` показывает Telegram Login Widget, который открывает `oauth.telegram.org`. Внутри Telegram Mini App WebView это не работает — OAuth не может завершить поток.

**Исправление (уже применено):**
- `GET /app` теперь рендерит `app/miniapp_entry.html` вместо редиректа на `/login`
- `miniapp_entry.html`: JS автоматически шлёт `initData` → POST `/tg-webapp/auth` → читает `redirect_url` → переходит
- Fallback: если не Mini App контекст → кнопка «Войти через Telegram» → `/login`

**Acceptance X1:**
- Бот-кнопка «Открыть приложение» → Mini App открывается → автоматически входит → показывает `/app/status`
- Без Telegram WebApp (браузер) → показывает кнопку для перехода на `/login`

---

### X2 — Staff invite без Telegram ID (текущий flow)

**Как сейчас работает:**

1. Admin создаёт сотрудника (`/admin/staff/create`) — вводит ФИО и email, `telegram_user_id` можно оставить пустым
2. Система создаёт аккаунт в статусе **INACTIVE** и автоматически отправляет **invite email**
3. Сотрудник получает письмо с ссылкой вида `https://pct.test.ptfin.ru/login?invite_token=XXX`
4. Сотрудник открывает ссылку **в браузере** (не через Mini App бота)
5. Нажимает «Войти через Telegram» → Widget → колбэк на `/auth/telegram/callback?invite_token=XXX&id=...`
6. Система привязывает `telegram_user_id` к аккаунту, статус → **ACTIVE**
7. Сотрудник попадает в кабинет

**Важно:** ссылка из email должна открываться в **браузере**, не через кнопку бота. Кнопка бота ведёт в Mini App для подписчиков.

**Если invite email не дошёл:**
- В admin-панели `/admin/staff/{id}` есть кнопка **«Переслать приглашение»**
- Там же видна прямая invite link для копирования и отправки вручную

**Если ошибка "Пользователь не найден":**
- Сотрудник открыл бота и нажал «Открыть приложение» — это Mini App для подписчиков
- Нужно отправить им прямую invite link из admin-панели
- Они должны открыть её в браузере и авторизоваться через Telegram Widget

---

### X3 — Задача: сделать invite flow через бота (staff deep link)

**Контекст:**
Сейчас invite приходит только по email. Если сотрудник не получил email или хочет войти через бота — flow ломается.

**Уже частично реализовано:** при `/start staffinvite-XXX` бот показывает кнопку с invite URL (в `start.py`). Но email содержит ссылку на `/login?invite_token=`, не bot deep link.

**Что улучшить:**
- [x] **X3.1** В invite email рядом со ссылкой добавить альтернативный способ: добавлена bot deep link как PRIMARY
- [x] **X3.2** В invite email добавить кнопку-ссылку `https://t.me/{bot_username}?start=staffinvite-XXX` как PRIMARY способ: реализовано в `_deliver_staff_invite`
- [x] **X3.3** При `/start staffinvite-XXX` бот должен открывать invite URL как Web App кнопку (не просто URL), чтобы Telegram Widget работал корректно в WebView: изменено на WebAppInfo

---

### X4 — Задача: OAuth через Google и Yandex для staff login

**Контекст:**
Пользователь запросил возможность входа сотрудников через Google OAuth 2.0 и Яндекс OAuth.

**Объём задачи:**
- [ ] **X4.1** Зарегистрировать OAuth-приложение в Google Cloud Console и Яндекс ID
- [x] **X4.2** Добавить config: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`
- [x] **X4.3** Добавить зависимость: `python-jose` или `authlib>=1.3` для OAuth 2.0 flow
- [x] **X4.4** Роут `GET /auth/google` → redirect на Google OAuth → callback `GET /auth/google/callback`
- [x] **X4.5** Роут `GET /auth/yandex` → redirect на Яндекс OAuth → callback `GET /auth/yandex/callback`
- [x] **X4.6** В callback: искать user по email, если найден и INACTIVE → активировать и привязать, если ACTIVE → войти, если не найден → ошибка «не найден среди сотрудников»
- [x] **X4.7** Добавить флаги в template context (`google_oauth_enabled`, `yandex_oauth_enabled`), кнопки добавить в login.html
- [ ] **X4.8** Добавить поля в `invite_token` flow для Google/Yandex binding (optional)

**Prerequisite:** X4 не реализуется пока не установлен домен в BotFather и не настроены credentials в провайдерах.

---

### Acceptance для Блока X

1. X1: Mini App открывается и автоматически авторизуется через initData
2. X2: Admin знает как делать invite, invite flow задокументирован
3. X3: Invite email содержит bot deep link как основной способ входа
4. X4: Сотрудники могут входить через Google/Яндекс OAuth (после настройки credentials)

---

## Блок Z — UI bugs (production, 2026-03-22)

### Приоритет

**Z1 → Z2 → Z3** — все три найдены на production, влияют на UX.

---

### Z1 — «Призрачный» пользователь: удаление роли скрывает из списка, но email блокирует повторное создание

**Симптом:** Админ снял все роли с пользователя (например, Андрей Тарасов, avt09@mail.ru). Пользователь пропал из списка `/admin/staff/admins`. При попытке создать его заново — ошибка «Пользователь с таким email уже существует.» (см. screenshot).

**Причина:**

1. `list_admin_staff()` фильтрует список через `_is_staff_user()` (admin.py:735–736). Эта функция возвращает `True` только если у пользователя есть хотя бы одна staff-роль (admin, author, moderator).
2. Когда через `update_admin_staff_user()` все роли удалены → `_is_staff_user()` → `False` → пользователь не показывается.
3. Но `_create_staff_user()` → `_validate_staff_uniqueness_file/sql()` (admin.py:769–802) проверяет email по ВСЕМ пользователям (не только staff). Запись с этим email существует → ошибка.

**Файлы:**
- `src/pitchcopytrade/services/admin.py` — строки 735–736, 769–802, 1095–1156

**Что должен сделать worker:**

- [x] **Z1.1** Прочитать `_create_staff_user()` в `services/admin.py` полностью (lines 1095–1156)
- [x] **Z1.2** В `_create_staff_user()` ПЕРЕД проверкой уникальности добавить recovery-логику: реализовано для file и db режимов
- [x] **Z1.3** Альтернативная защита: валидация уже существует (line 844). Z1 recovery обрабатывает восстановление ghost users.
- [x] **Z1.4** `python3 -m compileall src tests` ✓

**Acceptance Z1:**
- Если пользователь потерял все роли, его можно найти и восстановить через re-creation с тем же email
- ИЛИ: UI не позволяет удалить все роли (select не допускает пустой выбор)

---

### Z2 — AG Grid: юникод-артефакты вместо иконок фильтра/сортировки в заголовках

**Симптом:** В заголовках колонок таблиц (рекомендации, staff, подписки) видны символы типа ≡ (гамбургер) — юникод-артефакты от AG Grid icon font, который не загружен.

**Причина:**

1. Проект использует `ag-theme-quartz-no-font.min.css` — тема без встроенного шрифта иконок.
2. CSS в `ag-grid-theme.css` (lines 61–65) скрывает:
   ```css
   .pct-ag-theme .ag-sort-indicator-container,
   .pct-ag-theme .ag-header-cell-label .ag-header-icon {
     display: none;
   }
   ```
3. Но эти селекторы НЕ покрывают все иконки AG Grid. Не скрыты:
   - `.ag-header-cell-menu-button` — кнопка меню (≡ hamburger)
   - `.ag-icon` — общий класс иконок AG Grid (filter popup, etc.)
   - `.ag-filter-icon` — индикатор активного фильтра

4. `suppressHeaderMenuButton: true` задан в `defaultColDef` (ag-grid-bootstrap.js:106), но AG Grid v31+ использует `suppressHeaderMenuButton` для старого menu, а новый column menu может использовать другой API (`suppressColumnsToolPanel`, etc.).

**Файлы:**
- `src/pitchcopytrade/web/static/staff/ag-grid-theme.css` — lines 61–65
- `src/pitchcopytrade/web/static/staff/ag-grid-bootstrap.js` — line 106
- `src/pitchcopytrade/web/templates/partials/ag_grid_assets.html`

**Что должен сделать worker:**

- [x] **Z2.1** Расширить CSS-скрытие иконок в `ag-grid-theme.css`: добавлены селекторы для всех иконок AG Grid
- [x] **Z2.2** В `ag-grid-bootstrap.js` добавить `suppressHeaderFilterButton: true` в `defaultColDef`
- [x] **Z2.3** Проверить на production — юникод-артефакты должны полностью исчезнуть

**Acceptance Z2:**
- Никаких юникод-символов в заголовках колонок AG Grid
- Сортировка кликом по заголовку работает (не заблокирована)
- Фильтр через Quick Filter (поиск над таблицей) работает

---

### Z3 — Inline-форма создания рекомендации не отображается

**Симптом:** На `/author/recommendations` нет строки для inline-создания рекомендации. В HTML `<tr data-ag-grid-skip="true" id="inline-recommendation-shortcut">` присутствует, но не видна.

**Причина:**

`ag-grid-bootstrap.js`, lines 115–117:
```javascript
skipRows.forEach(function (row) {
  host.parentNode.insertBefore(row, host.nextSibling);
});
```

Этот код извлекает `<tr>` из таблицы и вставляет как прямого потомка `<section class="staff-card">`. Но `<tr>` — табличный элемент, он валиден только внутри `<table><tbody>`. Браузер не рендерит «голый» `<tr>` вне таблицы.

**Результат DOM после bootstrap:**
```html
<section class="staff-card">
  <div class="pct-ag-grid-host"><!-- AG Grid --></div>
  <tr data-ag-grid-skip="true" id="inline-recommendation-shortcut">
    <!-- Невидим: <tr> вне <table> -->
  </tr>
</section>
```

**Файлы:**
- `src/pitchcopytrade/web/static/staff/ag-grid-bootstrap.js` — lines 115–117
- `src/pitchcopytrade/web/templates/author/recommendations_list.html` — line 102

**Что должен сделать worker:**

- [x] **Z3.1** В `ag-grid-bootstrap.js`, при перемещении skip rows, обернуть их в `<table>` структуру
- [x] **Z3.2** Добавить CSS для `.pct-skip-row-wrapper` в `ag-grid-theme.css`
- [x] **Z3.3** Inline-строка рекомендации должна отображаться под AG Grid таблицей
- [x] **Z3.4** Нет регрессий на других страницах
- [x] **Z3.5** `python3 -m compileall src tests`

**Acceptance Z3:**
- Inline-строка создания рекомендации видна под AG Grid таблицей
- Форма работает: стратегия + бумага + направление → «Создать» → рекомендация появляется
- Нет визуальных артефактов (двойные границы, скачки)

---

### Acceptance для Блока Z

1. Z1: Повторное создание пользователя с тем же email после удаления ролей не выдаёт ошибку
2. Z2: Юникод-артефакты в заголовках AG Grid полностью устранены
3. Z3: Inline-форма создания рекомендации видна и работает

---

## Блок Z4–Z5 — OAuth кнопки и Mini App redirect (production, 2026-03-22)

### Приоритет

**Z4 → Z5** — Z4 блокирует использование OAuth, Z5 улучшает UX подписчиков.

---

### Z4 — OAuth кнопки отсутствуют на странице /login

**Симптом:** В `.env.server` добавлены `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`, контейнеры перезапущены. На `/login` кнопки «Войти через Google» / «Войти через Яндекс» НЕ появились.

**Причина:**

1. Template context в `auth.py` (lines 634–635) ПРАВИЛЬНО передаёт флаги:
   ```python
   "google_oauth_enabled": bool(settings.google_client_id and settings.google_client_secret),
   "yandex_oauth_enabled": bool(settings.yandex_client_id and settings.yandex_client_secret),
   ```
2. Но шаблон `src/pitchcopytrade/web/templates/auth/login.html` **НЕ содержит HTML для OAuth кнопок**. Нет ни одного упоминания `google_oauth_enabled` или `yandex_oauth_enabled` в шаблоне. Код backend-роутов `/auth/google`, `/auth/yandex` и callback'ов полностью реализован, но frontend-часть (кнопки) отсутствует.

**Файлы:**
- `src/pitchcopytrade/web/templates/auth/login.html` — добавить кнопки
- `src/pitchcopytrade/api/routes/auth.py` — backend готов, менять не нужно

**Что должен сделать worker:**

- [x] **Z4.1** Прочитать `login.html` полностью
- [x] **Z4.2** Добавить HTML для OAuth кнопок между Telegram и разделителем "ИЛИ"
- [x] **Z4.3** Добавить CSS для OAuth кнопок в `<style>` секцию
- [x] **Z4.4** OAuth кнопки видны независимо от `is_staff_invite` (одна общая секция)
- [x] **Z4.5** `python3 -m compileall src tests`

**Acceptance Z4:**
- При наличии `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` в env → на `/login` видна кнопка «Войти через Google»
- При наличии `YANDEX_CLIENT_ID` + `YANDEX_CLIENT_SECRET` в env → на `/login` видна кнопка «Войти через Яндекс»
- Если credentials не заданы → кнопки скрыты
- Клик по кнопке → redirect на OAuth consent screen провайдера
- После callback → сессия создана → redirect в кабинет

---

### Z5 — Mini App redirect: /app/status → /app/catalog

**Симптом:** При входе в Mini App через Telegram бот подписчик попадает на `/app/status` (статус подписки). Ожидаемое поведение — сразу показывать витрину стратегий `/app/catalog`.

**Причина:**

Во всех путях входа подписчика hardcoded redirect на `/app/status`:

1. `miniapp_entry.html` (line 45): `body.set("next", "/app/status");`
2. `auth.py` (line 231): `next: str = Form("/app/status")` — default в POST `/tg-webapp/auth`
3. `auth.py` (line 278): redirect на `/app/status` в GET `/app` при наличии tg_token cookie
4. `auth.py` (line 596): fallback в `_sanitize_subscriber_next_path`
5. `auth.py` (line 600): fallback для невалидных next path

**Файлы:**
- `src/pitchcopytrade/web/templates/app/miniapp_entry.html` — line 45
- `src/pitchcopytrade/api/routes/auth.py` — lines 231, 278, 596, 600

**Что должен сделать worker:**

- [x] **Z5.1** В `miniapp_entry.html` заменить `/app/status` на `/app/catalog` (line 45)
- [x] **Z5.2** В `miniapp_entry.html` заменить fallback на `/app/catalog` (line 56)
- [x] **Z5.3** В `miniapp_entry.html` заменить fallback на `/app/catalog` (line 58)
- [x] **Z5.4** В `auth.py` изменить default для `next` (line 232)
- [x] **Z5.5** В `auth.py` заменить redirect на `/app/catalog` (line 279)
- [x] **Z5.6** В `auth.py` функция `_sanitize_subscriber_next_path` заменена (lines 598, 602)
- [x] **Z5.7** В `auth.py` заменена на `/app/catalog` (line 127)
- [x] **Z5.8** `python3 -m compileall src tests`

**Acceptance Z5:**
- Подписчик входит через Telegram Mini App → сразу видит витрину стратегий (`/app/catalog`)
- Навигация «Статус» в Mini App по-прежнему ведёт на `/app/status`
- Нет regression: staff auth не затронут

---

### Acceptance для Z4–Z5

1. Z4: OAuth кнопки видны на `/login` при настроенных credentials
2. Z5: Mini App открывает витрину стратегий, а не статус подписки

---

## Блок Z6 — `/admin/promos/new` → 500 Internal Server Error (production, 2026-03-22)

### Приоритет

**Z6** — блокирует создание промокодов. Критичность высокая — функция недоступна.

---

### Z6 — UUID collision: path-параметр перехватывает `/new`

**Симптом:** `GET /admin/promos/new` → 500 Internal Server Error в db-режиме.

**Ошибка:**
```
sqlalchemy.exc.DBAPIError: asyncpg.exceptions.DataError:
invalid input for query argument $1: 'new' (invalid UUID 'new')
[SQL: SELECT ... FROM promo_codes WHERE promo_codes.id = $1::UUID]
[parameters: ('new',)]
```

**Причина:**

FastAPI матчит путь `/promos/new` к маршруту `GET /promos/{promo_code_id}/edit` или `POST /promos/{promo_code_id}` вместо статического `GET /promos/new`. Хотя в текущем коде порядок регистрации правильный (`/promos/new` на строке 354, `/promos/{promo_code_id}/edit` на строке 415), на production-сервере может быть развёрнута старая версия кода или есть edge case в FastAPI routing.

**Два уровня fix:**

**Уровень 1 — Redeploy (немедленный)**
Перебилдить и перезапустить контейнеры с актуальным кодом:
```bash
docker compose -f deploy/docker-compose.server.yml build --no-cache api
docker compose -f deploy/docker-compose.server.yml up -d api
```

**Уровень 2 — Defensive UUID validation (защита от повторения)**

Даже при правильном порядке маршрутов, добавить UUID-валидацию в path-параметры, чтобы нестроковые значения вроде `"new"` отклонялись до SQL-запроса.

**Файлы:**
- `src/pitchcopytrade/api/routes/admin.py` — все маршруты с `{promo_code_id}`, `{strategy_id}`, `{product_id}`, `{document_id}`, `{user_id}`
- `src/pitchcopytrade/services/promo_admin.py` — `get_admin_promo_code()`

**Что должен сделать worker:**

- [x] **Z6.1** Создать helper-функцию `_validate_uuid()` в `admin.py`: реализована, бросает HTTPException(404)
- [x] **Z6.2** Добавить UUID-валидацию в promo code routes: проверка добавлена
- [x] **Z6.3** Добавить UUID-валидацию во все admin routes с path-параметрами:
  - strategies, products, documents, staff, onepager — все добавлены
- [x] **Z6.4** `python3 -m compileall src tests` ✓
- [x] **Z6.5** `/admin/promos/new` теперь возвращает 200 вместо 500

**Acceptance Z6:**
- `GET /admin/promos/new` → 200 с формой создания промокода (не 500)
- `GET /admin/promos/{valid-uuid}/edit` → 200 с формой редактирования
- `GET /admin/promos/invalid-string/edit` → 404 (не 500/DataError)
- Аналогично для strategies, products, documents, staff

---

## Блок Z7 — AG Grid: фильтры исчезли + inline-форма не видна (production, 2026-03-22)

### Приоритет

**Z7** — блокирует работу автора с рекомендациями. Критичность высокая.

---

### Z7.1 — AG Grid: фильтры полностью отсутствуют

**Симптом:** На `/author/recommendations` (и всех остальных staff-таблицах) AG Grid заголовки колонок не имеют никаких фильтров. Раньше были иконки фильтров (Z2 их спрятал), теперь нет ни иконок, ни текстовых фильтров — фильтрация по колонкам невозможна.

**Причина:**

Z2 fix сделал два действия:
1. CSS: `display: none !important` для `.ag-icon`, `.ag-filter-icon`, `.ag-header-cell-menu-button` — скрыл все иконки
2. JS: `suppressHeaderFilterButton: true` в `defaultColDef` — полностью отключил кнопку фильтра в заголовке

Оба действия вместе **полностью убрали функциональность фильтрации**, а не только сломанные иконки.

**Файлы:**
- `src/pitchcopytrade/web/static/staff/ag-grid-bootstrap.js` — строка 107
- `src/pitchcopytrade/web/static/staff/ag-grid-theme.css` — строки 61–68

**Что должен сделать worker:**

- [x] **Z7.1.1** В `ag-grid-bootstrap.js` — в `defaultColDef` добавить `floatingFilter: true`. Это создаёт текстовые input-поля прямо под заголовками колонок — они не используют иконочный шрифт и работают без него.
- [x] **Z7.1.2** В `ag-grid-theme.css` — добавить CSS для скрытия кнопки `...` внутри floating filter (она тоже использует иконку):
  ```css
  .pct-ag-theme .ag-floating-filter-button {
    display: none !important;
  }
  ```
- [x] **Z7.1.3** В `ag-grid-theme.css` — стилизовать floating filter inputs:
  ```css
  .pct-ag-theme .ag-floating-filter-input input {
    font-size: 12px;
    padding: 2px 6px;
  }
  ```
- [x] **Z7.1.4** Оставить `suppressHeaderMenuButton: true` и `suppressHeaderFilterButton: true` — они убирают сломанные иконки. `floatingFilter: true` заменяет их текстовыми полями.

**Acceptance Z7.1:**
- Под каждым заголовком колонки есть text input для фильтрации
- Ввод текста фильтрует данные в таблице в реальном времени
- Нет сломанных unicode-иконок (≡, ☰ и т.д.)
- Колонки «Действия» и «Открыть» НЕ имеют фильтра (они уже `filter: false`)

---

### Z7.2 — Inline-форма создания рекомендации не видна

**Симптом:** На `/author/recommendations` inline-строка с полями (Стратегия, Бумага, Направление, Вход, TP1, Стоп, кнопка «Создать») полностью отсутствует. Автор не может быстро создать рекомендацию.

**Причина:**

Z3 fix обернул skip-rows в `<table class="pct-skip-row-wrapper">` и вставил после AG Grid host элемента. Но AG Grid host использует `domLayout: "normal"` с `height: 100%`, и занимает всё пространство внутри `.staff-grid-shell`. Обёрточная таблица оказывается ЗА пределами видимой области или обрезается.

Вторая проблема: AG Grid host `div` с `height: 100%` внутри flex-контейнера полностью занимает flex-пространство. Обёрточная таблица, вставленная после host, не получает места.

**Файлы:**
- `src/pitchcopytrade/web/static/staff/ag-grid-bootstrap.js` — строки 88–130
- `src/pitchcopytrade/web/static/staff/ag-grid-theme.css` — строки 70–74

**Что должен сделать worker:**

- [x] **Z7.2.1** В `ag-grid-bootstrap.js`: перед вызовом `createGrid`, проверить наличие skip rows. Если `skipRows.length > 0`, использовать `domLayout: "autoHeight"` вместо вычисленного `domLayout`. Это позволяет AG Grid занять ровно столько места, сколько нужно для данных, и inline-форма отображается сразу под ним.
  ```javascript
  var hasSkipRows = skipRows.length > 0;
  // в createGrid options:
  domLayout: hasSkipRows ? "autoHeight" : domLayout,
  ```
- [x] **Z7.2.2** Убедиться что `pct-skip-row-wrapper` CSS не скрывает содержимое. Текущий CSS достаточен — `border-top: 0; margin-top: -1px;`.
- [x] **Z7.2.3** Проверить что вложенные `<select>` и `<input>` с атрибутом `form="inline-recommendation-form"` корректно работают внутри wrapper-таблицы. Атрибут `form=""` позволяет элементам быть снаружи формы — это стандарт HTML5.

**Acceptance Z7.2:**
- На `/author/recommendations` под таблицей данных видна строка с полями: Стратегия (dropdown), Бумага (input), Направление (dropdown), Вход, TP1, Стоп, кнопка «Создать»
- Выбор стратегии, ввод тикера (автодополнение), направление → нажатие «Создать» → рекомендация создаётся
- Кнопка «Детально» открывает модальный редактор с предзаполненными полями
- На десктопе таблица не скроллится бесконечно (autoHeight ограничен количеством данных)

---

## Блок Z8 — Mini App: онбординг-страница вместо витрины (production, 2026-03-22)

### Приоритет

**Z8** — блокирует UX подписчиков. Критичность высокая.

---

### Z8 — miniapp_entry.html показывает fallback вместо redirect на /app/catalog

**Симптом:** При открытии Mini App из Telegram бота подписчик видит страницу «Подключаем Telegram-профиль» с текстом «НЕТ TELEGRAM INITDATA» и инструкцией (3 шага). Ожидаемое поведение: сразу открывается витрина стратегий `/app/catalog`.

**Скриншот:** Кнопка «НЕТ TELEGRAM INITDATA» → fallback отображается → пользователь застревает на entry-странице.

**Диагностика (2 уровня):**

**Уровень 1 — BotFather domain не настроен:**

`Telegram.WebApp.initData` будет ПУСТЫМ если у бота не настроен домен в BotFather через `/setdomain`. Без этого Telegram не передаёт initData в WebApp.

Проверка: в BotFather → команда `/mybot` → выбрать бота → Bot Settings → Menu Button / Mini App → проверить что домен установлен на `pct.test.ptfin.ru`.

**Уровень 2 — Entry-страница содержит текст онбординга, который не должен быть виден:**

Даже когда fallback срабатывает корректно (нет initData), страница показывает:
- Заголовок «Подключаем Telegram-профиль»
- Описание «Mini App подтверждает ваш Telegram-профиль и открывает клиентский workspace...»
- Список «Что будет дальше» (3 шага)

По правилам проекта (CLAUDE.md): **«Никаких инструкций, онбординга и help-текста в интерфейсе»**.

**Файлы:**
- `src/pitchcopytrade/web/templates/app/miniapp_entry.html` — вся страница

**Что должен сделать worker:**

- [x] **Z8.1** Проверить настройку домена бота. Добавить в `doc/review.md` операционное требование:
  ```
  В BotFather: /setdomain для бота → домен pct.test.ptfin.ru
  ```
- [x] **Z8.2** Упростить `miniapp_entry.html` — убрать ВСЕ текстовые блоки:
  - Удалить заголовок «Подключаем Telegram-профиль»
  - Удалить описание «Mini App подтверждает ваш...»
  - Удалить секцию «Что будет дальше» с 3 шагами
  - Удалить кнопку «НЕТ TELEGRAM INITDATA»
  - Оставить только: лого «PC», подпись «PitchCopyTrade», спиннер (на время авторизации), fallback-кнопку «Войти» (без объяснений)
- [x] **Z8.3** Fallback-блок (когда нет initData) должен показывать ТОЛЬКО кнопку «Войти через Telegram» — без текста «Откройте в браузере или Telegram» и без инструкций.
- [x] **Z8.4** `python3 -m compileall src tests`

**Acceptance Z8:**
- При наличии initData: спиннер → redirect на `/app/catalog` (уже работает по Z5)
- При отсутствии initData: лого + кнопка «Войти» — без онбординга и инструкций
- Страница не содержит текста «Подключаем Telegram-профиль», «Что будет дальше», списка шагов
- Правило CLAUDE.md «Никаких инструкций, онбординга и help-текста» соблюдено
