# PitchCopyTrade — Список задач MVP
> Версия: 0.2.0
> Обновлено: 2026-03-18
> Порядок выполнения: фазы последовательно; каждая фаза должна пройти acceptance criteria перед следующей

---

## Обозначения
- `[ ]` — не начато
- `[~]` — в процессе
- `[x]` — выполнено
- `[!]` — заблокировано / требует решения

---

## Фаза 0 — Фундамент (выполнено)

- [x] Структура проекта (pyproject.toml, src layout)
- [x] Docker Compose (api, bot, worker, postgres, minio)
- [x] Конфигурация через env (pydantic-settings, .env)
- [x] API health-эндпоинты (`/health`, `/ready`, `/meta`)
- [x] Заглушка бота (aiogram 3)
- [x] Заглушка worker
- [x] Начальная схема БД + Alembic миграция (18 таблиц)
- [x] MinIO storage adapter
- [x] Тестовый фреймворк (pytest-asyncio, httpx)

---

## Фаза 1 — Сброс и чистый старт

**Цель:** Сервис стартует без legacy-данных, без инструкций в UI, с чистой БД.

### Задачи
- [ ] **1.1** Добавить Alembic-миграцию для ARQ job queue в Redis
  - Таблица `notification_log` для аудита отправленных уведомлений (опционально)
  - Enum `NotificationChannel`: telegram, email

- [ ] **1.2** Seeder инструментов
  - Создать `src/pitchcopytrade/db/seeders/instruments.py`
  - Загружает из `doc/instruments_stub.json`
  - Upsert по ticker (пропускает если уже существует)
  - Вызывается из события старта API (только если таблица инструментов пустая)

- [ ] **1.3** Seeder admin-пользователя
  - Создать `src/pitchcopytrade/db/seeders/admin.py`
  - Читает `ADMIN_TELEGRAM_ID` и `ADMIN_EMAIL` из env
  - Создаёт User + Role(admin) если не существует
  - Вызывается из события старта API

- [ ] **1.4** Скрипт полного сброса
  - `scripts/reset.sh` — удаляет volumes, образы, приводит к чистому состоянию
  - Документировать в README в разделе «Полный сброс»

### Критерии приёмки
- `docker-compose up --build` на чистой машине → пустые таблицы (кроме instruments + admin)
- Никаких примеров данных, никаких placeholder-строк нигде

---

## Фаза 2 — Webhook бота и внутренний broadcast API

**Цель:** Бот работает в webhook-режиме на выделенном сервере; API умеет инициировать рассылку.

### Задачи
- [ ] **2.1** Активация webhook
  - Флаг `TELEGRAM_USE_WEBHOOK` уже есть в config
  - В `bot/main.py`: если `TELEGRAM_USE_WEBHOOK=true` → регистрировать webhook через `bot.set_webhook(url)`
  - Бот слушает порт `8080` внутренне (aiohttp webhook server)
  - Health-check эндпоинт: `GET /health`

- [ ] **2.2** Internal broadcast эндпоинт
  - В сервисе бота: `POST /internal/broadcast`
  - Авторизация: заголовок `X-Internal-Token` (секрет из env `INTERNAL_API_SECRET`)
  - Тело: `{ "recommendation_id": "<uuid>" }`
  - Обработчик: получает рекомендацию + ноги + стратегию из БД
  - Получает всех пользователей с `Subscription.status = active` для этой стратегии
  - Отправляет форматированное Telegram-сообщение каждому подписчику
  - Формат сообщения: см. blueprint.md §9

- [ ] **2.3** Обновление Docker Compose
  - Сервис бота: открыть порт 8080 внутренне
  - Добавить `INTERNAL_API_SECRET` в env
  - Описать правило reverse proxy для webhook-пути (nginx на хосте)

- [ ] **2.4** Документация webhook
  - README §«Настройка Telegram Webhook» — пошагово для выделенного сервера

### Критерии приёмки
- `curl -X POST http://localhost:8080/internal/broadcast -H "X-Internal-Token: ..." -d '{"recommendation_id":"..."}' ` отправляет сообщение тестовому подписчику
- Логи бота показывают регистрацию webhook при старте если `TELEGRAM_USE_WEBHOOK=true`

---

## Фаза 3 — Авторизация через Telegram для кабинета автора

**Цель:** Автор может войти в веб-кабинет через Telegram Login Widget.

### Задачи
- [ ] **3.1** Эндпоинт Telegram Login Widget
  - `GET /auth/telegram/callback` — принимает auth data от Telegram
  - Проверка HMAC-SHA256 подписи через `BOT_TOKEN`
  - Отклонять если `auth_date` старше 5 минут
  - Искать User по `telegram_user_id`; возвращать 401 если не найден
  - Создать подписанный JWT (HttpOnly, Secure, SameSite=Strict, 24ч)
  - Редирект на `/cabinet/`

- [ ] **3.2** Session middleware
  - `src/pitchcopytrade/api/middleware/auth.py`
  - Зависимость `get_current_user()`: декодирует JWT, загружает User из БД
  - Фабрика зависимостей `require_role(role_slug)`

- [ ] **3.3** Шаблон страницы входа
  - `src/pitchcopytrade/templates/auth/login.html`
  - Только кнопка Telegram Login Widget + логотип
  - Никаких инструкций, никаких форм логин/пароль

- [ ] **3.4** Маршруты авторизации
  - `GET /auth/login` → рендерит login.html
  - `GET /auth/telegram/callback` → проверка + редирект
  - `POST /auth/logout` → очистка cookie + редирект на /auth/login

### Критерии приёмки
- Автор с корректным `telegram_user_id` в БД может войти
- Пользователь не в БД получает страницу 401 (без саморегистрации)
- JWT проверяется на каждом защищённом маршруте

---

## Фаза 4 — Кабинет администратора

**Цель:** Администратор может создавать авторов и управлять базовыми настройками.

### Задачи
- [ ] **4.1** Шаблон layout кабинета администратора
  - `src/pitchcopytrade/templates/admin/layout.html`
  - Левый nav: Авторы | One Pager | Метрики | Выплаты
  - Никаких инструкций, никакого help-текста

- [ ] **4.2** Страница управления авторами
  - `GET /admin/authors` — список авторов (имя, telegram_id, email, активен)
  - `POST /admin/authors` — создание автора
    - Поля: `display_name` (обязательно), `email` (опц.), `telegram_user_id` (опц.)
    - Создаёт: User + AuthorProfile (slug авто) + user_roles(author)
    - Устанавливает `requires_moderation=False`
  - `POST /admin/authors/{id}/toggle` — включить/отключить автора

- [ ] **4.3** Редактор One Pager
  - `GET /admin/onepager/{strategy_id}` — редактировать One Pager
  - `POST /admin/onepager/{strategy_id}` — сохранить HTML-контент
  - Хранить в `Strategy.full_description` как HTML
  - Кнопка предпросмотра → `/s/{strategy_slug}` в новой вкладке

- [ ] **4.4** Страница метрик
  - `GET /admin/metrics`
  - Карточки: всего подписчиков, активных подписок, новых за неделю
  - Таблица: стратегия → кол-во подписчиков (агрегированно, без персональных данных)

- [ ] **4.5** Страница платежей (stub)
  - `GET /admin/payments` — список ожидающих ручных платежей
  - `POST /admin/payments/{id}/confirm` — подтвердить вручную → активировать подписку

### Критерии приёмки
- Администратор может создать автора; новый автор сразу может войти через Telegram
- Нет утечки персональных данных: администратор не видит имён подписчиков в метриках

---

## Фаза 5 — Инструменты и Popup выбора тикера

**Цель:** Popup тикера на основе instruments_stub.json с клиентским поиском.

### Задачи
- [ ] **5.1** API эндпоинт инструментов
  - `GET /api/instruments` — список активных инструментов
  - Ответ: `[{ ticker, name, last_price, change_pct, board, currency }]`
  - Из БД (засеяно из instruments_stub.json)
  - Будущее: параметр `?q=` для живого API

- [ ] **5.2** Компонент Popup тикера
  - `src/pitchcopytrade/templates/components/ticker_picker.html` (HTMX partial)
  - Поле ввода → `hx-get=/api/instruments?q=...` по keyup (debounce 300мс)
  - Таблица результатов: тикер | название | цена | изменение%
  - Клик по строке → заполняет родительское поле, закрывает popup
  - Недавние выборы → `localStorage` (ключ `pct_recent_tickers`)
  - Недавние отображаются со звёздочкой при пустом запросе

- [ ] **5.3** Подключить popup в inline-строку и полную форму (Фаза 7)

### Критерии приёмки
- Ввод «SB» → SBER первым в списке
- Клик по SBER → заполняет поле, popup закрывается
- Недавние выборы сохраняются между загрузками страницы

---

## Фаза 6 — Кабинет автора и управление стратегиями

**Цель:** Автор может создавать стратегии и управлять ими.

### Задачи
- [ ] **6.1** Layout кабинета автора
  - `src/pitchcopytrade/templates/cabinet/layout.html`
  - Левый nav: Стратегии | (будущее: Аналитика)
  - Шапка: display_name автора + кнопка «Выйти»
  - Никакого help-текста, никакого онбординга

- [ ] **6.2** Страница списка стратегий
  - `GET /cabinet/strategies` — список стратегий автора (название, статус, кол-во подписчиков)
  - Кнопка «Создать стратегию»
  - `POST /cabinet/strategies` — создать стратегию (название обязательно, slug авто)
  - `GET /cabinet/strategies/{id}` → страница рекомендаций этой стратегии

- [ ] **6.3** Редактирование стратегии
  - `GET /cabinet/strategies/{id}/edit` — изменить название, описание, уровень риска, min_capital_rub
  - `POST /cabinet/strategies/{id}/edit` — сохранить

### Критерии приёмки
- Автор видит только свои стратегии (ACL: `strategy.author_id = current_user.author_profile.id`)
- Slug уникален и URL-безопасен

---

## Фаза 7 — CRUD рекомендаций (Inline + Popup)

**Цель:** Автор может создавать, просматривать и публиковать рекомендации.

### Задачи
- [ ] **7.1** Страница таблицы рекомендаций
  - `GET /cabinet/strategies/{strategy_id}/recommendations`
  - Колонки: дата | тикер | сторона | цена | цель | стоп | статус | действия
  - Пустое состояние: только «Нет рекомендаций» + строка ввода внизу
  - Таблица полностью пустая на свежей БД

- [ ] **7.2** Inline-строка добавления
  - Последняя строка таблицы — пустая редактируемая строка
  - Поля: `[Тикер ▼]` `[BUY ▼]` `[Цена]` `[Цель]` `[Стоп]`
  - Клик «Тикер» → Popup тикера (Фаза 5)
  - BUY/SELL → toggle-кнопка
  - Цена/Цель/Стоп → числовые поля, nullable, без валидации пустых
  - Enter или `[+]` → POST создать рекомендацию + первую ногу
  - Новая строка появляется вверху таблицы, строка ввода сбрасывается

- [ ] **7.3** API создания рекомендации
  - `POST /cabinet/strategies/{strategy_id}/recommendations`
  - Тело: `{ ticker, side, price?, target?, stop? }`
  - Создаёт `Recommendation` (kind=new_idea, status=draft, requires_moderation=False)
  - Создаёт `RecommendationLeg` (instrument_id по ticker, side, entry_from=price, tp1=target, stop_loss=stop)
  - Возвращает HTMX partial с новой строкой таблицы

- [ ] **7.4** Полная форма (popup)
  - Кнопка «Новая рекомендация» → модальное окно
  - Поля: название (опц.), тип (radio), ноги (повторяемый блок), дата публикации (опц.)
  - Ссылка «Добавить ногу»
  - Закрытие по Esc или ×

- [ ] **7.5** Публикация
  - Кнопка «Опубликовать» на каждой черновой строке
  - `POST /cabinet/recommendations/{id}/publish`
  - Устанавливает status=published, published_at=now()
  - Ставит задание ARQ `send_recommendation_notifications` (async, не блокирует UI)
  - Возвращает HTMX swap — обновляет только ячейку статуса

- [ ] **7.6** Действия со строкой
  - «Закрыть» → status=closed, closed_at=now()
  - «Отменить» → status=cancelled, cancelled_at=now()
  - Удаления нет в MVP — только soft close/cancel

### Критерии приёмки
- Создание рекомендации с только тикер + сторона → сохраняется без ошибки
- Цена, цель, стоп nullable — пустые поля допустимы
- Публикация → ARQ job в очереди (видно в логах API)
- Строка таблицы обновляется на месте без перезагрузки страницы

---

## Фаза 8 — ARQ Worker: мгновенные уведомления через Redis

**Цель:** При публикации рекомендации Telegram и Email уведомления отправляются мгновенно.

### Задачи
- [ ] **8.1** ARQ worker entry point
  - `src/pitchcopytrade/worker/arq_worker.py`
  - `WorkerSettings` с functions, redis_settings, max_jobs, job_timeout
  - Redis URL из `settings.redis_url` (по умолчанию `redis://localhost:6379/0`)
  - Обновить `worker/main.py` для запуска ARQ вместо sleep-цикла

- [ ] **8.2** Функция задания уведомлений
  - `src/pitchcopytrade/worker/jobs/notifications.py`
  - `async def send_recommendation_notifications(ctx, recommendation_id: str)`
  - Получает рекомендацию + ноги + стратегию из БД
  - Для каждого подписчика с `Subscription.status = active`:
    - Если есть `telegram_user_id` → POST на `http://bot:8080/internal/broadcast`
    - Если есть `email` → отправить через aiosmtplib
  - Retry: 3 раза, задержка 10с, timeout 60с

- [ ] **8.3** Постановка задания при публикации
  - В обработчике `POST /cabinet/recommendations/{id}/publish`:
    ```python
    await arq_pool.enqueue_job("send_recommendation_notifications", str(rec.id))
    ```
  - `arq_pool` через FastAPI dependency (создаётся при старте, хранится в `app.state`)

- [ ] **8.4** Email шаблон
  - `src/pitchcopytrade/templates/email/recommendation.html` — Jinja2 HTML
  - `src/pitchcopytrade/templates/email/recommendation.txt` — plain text fallback
  - aiosmtplib отправляет multipart/alternative (HTML + text)
  - SMTP: `relay.ptfin.kz:465 SSL`, от `pct@ptfin.ru`

- [ ] **8.5** CMD для сервиса worker в docker-compose
  - `python -m arq pitchcopytrade.worker.arq_worker.WorkerSettings`
  - Worker подключается к Redis на хосте через `host.docker.internal`

### Критерии приёмки
- Публикация рекомендации → уведомления отправлены за < 2 сек
- Логи worker показывают мгновенный подхват задания (без 30с ожидания)
- Сбой SMTP → задание retry 3 раза, потом failed

---

## Фаза 9 — Telegram Mini App (подписчики)

**Цель:** Подписчик может просматривать стратегии, One Pager и оформить подписку.

### Задачи
- [ ] **9.1** Точка входа Mini App
  - Команда бота `/start` → кнопка «Открыть приложение» (WebApp)
  - WebApp URL: `{BASE_URL}/app/`

- [ ] **9.2** Страницы Mini App (Jinja2, HTMX, mobile)
  - `GET /app/` — список опубликованных стратегий
  - `GET /app/strategy/{slug}` — One Pager (HTML, полноэкранный)
  - `GET /app/tariffs` — продукты подписки с ценами
  - `GET /app/subscribe/{product_id}` — checkout (stub: инструкции по ручной оплате)
  - `GET /app/my` — активные подписки пользователя

- [ ] **9.3** Идентификация подписчика в Mini App
  - Mini App передаёт `initData` в заголовке
  - `GET /app/auth` — проверить подпись `initData`, создать/найти User, вернуть токен сессии
  - Все маршруты `/app/*` требуют валидной Mini App сессии

- [ ] **9.4** Checkout подписки (stub)
  - Показывает: «Переведите {amount} руб. по реквизитам: ... и нажмите "Я оплатил"»
  - `POST /app/subscribe/{product_id}/claim` → создаёт Payment(status=pending) + Subscription(status=pending)
  - Администратор подтверждает вручную в кабинете (Фаза 4.5)

### Критерии приёмки
- Подписчик открывает Mini App из бота, видит список стратегий, переходит на One Pager
- Claim подписки создаёт записи в БД, видимые в кабинете администратора

---

## Фаза 10 — Тесты и закалка

**Цель:** Основные флоу покрыты тестами. Регрессий нет.

### Задачи
- [ ] **10.1** Тесты авторизации
  - Проверка Telegram HMAC (корректный / просроченный / подделанный)
  - Защищённые маршруты возвращают 401 без сессии
  - Проверка ролей: автор не может зайти на `/admin/*`

- [ ] **10.2** Тесты рекомендаций
  - Создание с минимальными полями (только тикер + сторона)
  - Создание со всеми полями
  - Публикация → запись в ARQ очереди
  - ACL: автор А не может публиковать рекомендации автора Б

- [ ] **10.3** Тест broadcast
  - Internal broadcast эндпоинт с корректным/некорректным токеном
  - 401 на плохом токене, 200 на корректном

- [ ] **10.4** Тест Worker
  - Обработка ARQ задания: успех / retry при сбое

---

## Соглашения по реализации

### Именование маршрутов
- `/cabinet/` — кабинет автора (HTMX)
- `/admin/` — кабинет администратора (HTMX)
- `/app/` — Mini App подписчиков
- `/api/` — JSON API (инструменты и т.д.)
- `/auth/` — авторизация

### HTMX паттерны
- `hx-target` + `hx-swap="outerHTML"` для обновления строк таблицы
- `hx-boost` на nav-ссылках для SPA-ощущения
- Inline-строка: `hx-post` + `hx-swap="afterbegin"` на tbody

### Политика «без legacy»
- Перед каждой фазой: `git status` — никаких незакоммиченных файлов
- Перед деплоем: `scripts/reset.sh` для гарантии чистого состояния
- Никакого закомментированного кода, никаких TODO в production-путях
