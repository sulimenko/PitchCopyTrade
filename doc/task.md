# PitchCopyTrade — Active Tasks
> Обновлено: 2026-03-20
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

- [ ] **S1** Переработать `docker-compose.server.yml` с поддержкой обоих вариантов через `.env.server`

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

- [ ] **S2** Настроить FastAPI для доверия proxy-заголовкам (`X-Forwarded-Proto`)

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

- [ ] **R2** Запустить ARQ worker или консолидировать notification путь
  - Выбрать один из двух вариантов:
    - **A:** Добавить `arq`-сервис в `deploy/docker-compose.server.yml` (`python -m arq pitchcopytrade.worker.arq_worker.WorkerSettings`)
    - **B:** Убрать ARQ-путь для notifications; при немедленном publish вызывать `deliver_recommendation_notifications` напрямую без Redis
  - Проверить: после немедленного publish рекомендации Telegram-уведомление доставляется

- [ ] **R4** Устранить дублирование notification кодпатей
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
- [ ] **T1** Удалить пункт «Авторы» из левого nav в `staff_base.html`
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

- [ ] **T2** Реализовать фиксированный viewport layout для staff shell
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

- [ ] **U1** Изменить redirect после создания стратегии: `/author/strategies/{id}/edit` → `/author/strategies`
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

- [ ] **U2** Компактная таблица рекомендаций
  - Уменьшить толщину borders в ag-grid до `1px` или сделать `hairline`
  - Row height снизить до 28–30px если ещё не сделано
  - Правки в `staff/ag-grid-theme.css`

- [ ] **U3** «Идея» и «Бумага» в одну строку в inline shortcut
  - В `<td>` где сейчас два input-а вертикально (Идея + Бумага), сделать `display: flex; flex-direction: row; gap: 6px`
  - Оба инпута в одной строке, ширина делится пополам или `Идея` уже
  - picker-state div (`id="inline-picker-state"`) выносится под инпуты как hint строка

- [ ] **U4** Убрать/скрыть hint «Создать добавит строку...»
  - Текст убирается из постоянной видимости
  - Вариант А: tooltip на hover/focus кнопки «Создать» (HTML `title` атрибут достаточно)
  - Вариант Б: `display: none` или очень мелкий `muted` текст под shortcut-строкой, видный только при фокусе
  - Не удалять смысл — просто не занимать место на экране

- [ ] **U5** Исправить popup тикера: обрезается внутри контейнера
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

- [ ] **U6** Исправить Internal Server Error при «Создать» (inline рекомендация)
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

- [ ] **U7** Добавить явный `action` в форму создания новой рекомендации

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

- [ ] **U8** Создать минимальный base-шаблон для embedded-режима

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

Следующий крупный блок состоит из трех частей:
1. compact staff shell
2. `AG Grid Community` как единый CRUD layer
3. быстрый onboarding staff через email invite + Telegram bind
4. закрытие staff CRUD gaps и parity между `db`/`file`

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

- [ ] **F0** Закрыть `P1` по последнему активному администратору
  - `update_admin_staff_user` не должен позволять убрать роль `admin` у последнего активного администратора
  - защита должна совпадать с отдельным `roles/admin/remove`
  - одинаково в `db` и `file` mode
  - UI должен возвращать бизнес-ошибку, а не частично применять update

- [ ] **F1** Выровнять control emails по mode
  - `db` и `file` path должны одинаково отправлять уведомления активным администраторам
  - failed delivery не должен молча выпадать в одном из режимов

- [ ] **F2** Проверить `db/file` parity на staff onboarding
  - create
  - resend
  - oversight mail
  - audit log

- [ ] **F3** Добавить regression coverage
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
