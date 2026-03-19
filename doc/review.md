# PitchCopyTrade — Чеклист код-ревью
> Версия: 0.2.0
> Обновлено: 2026-03-19
> Использовать на каждом PR перед merge

---

## P0 — Блокеры (исправить до любого merge)

### Безопасность
- [x] Нет интерполяции строк в SQL — только SQLAlchemy bound params
- [x] HMAC-SHA256 Telegram проверяется на каждом auth callback (`auth_date` < 5 мин)
- [x] Подпись `initData` Telegram Mini App проверяется перед доверием identity
- [x] Домен Telegram Login Widget задан через `@BotFather /setdomain` и совпадает с host из `BASE_URL`
- [x] `X-Internal-Token` проверяется на `/internal/broadcast` — жёсткая блокировка без него
- [x] JWT: HttpOnly + Secure + SameSite=Strict, срок ≤ 24ч
- [x] Никаких секретов (токенов, паролей, ключей) в коммитах и логах
- [x] Автор читает/пишет только свои стратегии и рекомендации (ACL по `author_profile.id`)
- [x] Маршруты `/admin/*` защищены `require_role("admin")`
- [x] Подписчик не может зайти в кабинет автора или администратора

### Целостность данных
- [x] `RecommendationLeg.instrument_id` получается по ticker — нет orphan-ног
- [x] Переходы `Recommendation.status` только по разрешённому пути: draft → published → closed/cancelled
- [x] `Payment.final_amount_rub` вычисляется на сервере, не принимается от клиента
- [x] `Subscription` создаётся только после `paid` или ручного подтверждения админом

### Уведомления
- [x] Постановка ARQ-задания — **fire-and-forget**: публикация не блокируется если worker упал
- [x] Ошибки broadcast логируются, не проглатываются тихо
- [x] ARQ `enqueue_job` вызывается атомарно с обновлением статуса рекомендации

---

## P1 — Высокий приоритет

### Роли и ACL
- [x] 3 роли в БД: admin, author, moderator (moderator не используется в MVP)
- [x] `requires_moderation=False` на всех AuthorProfile MVP — никакой маршрут не проверяет статус модерации
- [x] Автор создаётся только админом — нет пути саморегистрации
- [x] Уникальность `telegram_user_id` на уровне БД и приложения

### Логика рекомендаций
- [x] Обязательные поля: только `ticker` + `side` при inline-создании
- [x] Все ценовые поля (`entry_from`, `tp1`, `stop_loss`) nullable — пустое = NULL, не 0
- [x] `RecommendationKind` по умолчанию `new_idea` при быстром inline-создании
- [x] `published_at` — серверное UTC время, не клиентское
- [x] Дублированная публикация предотвращена (статус должен быть `draft` для публикации)

### Инструменты
- [x] Инструменты засеяны из `storage/seed/json/instruments.json` при старте (upsert по ticker)
- [x] `GET /api/instruments` возвращает только `is_active=True`
- [x] Поиск тикера нечувствителен к регистру
- [x] Поля `last_price` и `change_pct` присутствуют в ответе (stub-значения OK)

### UI / Шаблоны
- [x] Нигде нет онбординг-текста, инструкций, блоков подсказок
- [x] Пустые таблицы показывают минимальный empty state («Нет рекомендаций»), не placeholder-строки
- [x] Popup тикера закрывается по Esc и клику на backdrop
- [x] Inline-строка сбрасывается после успешного сохранения
- [x] HTMX-ответы используют правильные `HX-Trigger` или swap targets — нет полных перезагрузок страницы
- [x] Весь пользовательский текст на русском

### База данных
- [x] Новая Alembic-миграция для каждого изменения схемы
- [x] Миграция обратима (`downgrade` реализован)
- [x] Нет `CREATE TABLE` в коде приложения — только через миграции
- [x] `Base.metadata` включает все модели до запуска `env.py`
- [x] Все PostgreSQL enum-поля используют `.value` (`active`, `pending`, `admin`), а не uppercase names (`ACTIVE`, `PENDING`, `ADMIN`)

---

## P2 — Стандартное качество

### Стиль кода
- [x] Нет неиспользуемых импортов
- [x] Нет закомментированных блоков кода
- [x] Нет `print()` — только `logging`
- [x] Функции до 50 строк (разбить большие)
- [x] Нет magic strings — использовать enum из `db/models/enums.py`

### Дизайн API
- [x] JSON API эндпоинты под префиксом `/api/`
- [x] HTMX partial эндпоинты под `/cabinet/` или `/admin/`
- [x] Ошибки возвращают правильные HTTP коды (400/401/403/404/422/500)
- [x] Тело 422 содержит field-level ошибки валидации

### Конфигурация
- [x] Все новые config-значения добавлены в `core/config.py` с типами и дефолтами
- [x] Новые env-переменные задокументированы в README
- [x] Нет захардкоженных URL, портов, секретов
- [x] В проекте не осталось `MINIO_*` env variables и MinIO-specific config sections

### Тесты
- [x] Каждый новый маршрут имеет хотя бы один тест
- [x] Тест ACL: неавторизованный доступ возвращает 401/403
- [x] Happy path тест: корректные данные возвращают ожидаемый ответ
- [x] После удаления MinIO есть regression-test, что storage contract остался только local-files-only

---

## P3 — Проверка product drift

Проверяем что реализация не отходит от утверждённого blueprint:

- [x] Кабинет автора — только веб, никаких bot-команд для авторов
- [x] Флоу подписчика — только Telegram bot + Mini App, без отдельной веб-регистрации
- [x] One Pager — HTML в `Strategy.full_description`, рендерится на сервере
- [x] Подтверждение платежа — ручное (действие админа), без автоматических вызовов платёжного API
- [x] Роль Модератора: enum есть, UI нет, проверок нет, `requires_moderation=False`
- [x] В продукте не осталось MinIO-инфраструктуры, MinIO-библиотеки и legacy storage fallback
- [x] Режим бота: `TELEGRAM_USE_WEBHOOK=true` в production, `false` в local dev
- [x] Инструменты: только из `storage/seed/json/instruments.json` — никаких live market API вызовов в MVP
- [x] Для каждого автора есть персональный watchlist, который предзаполняется активными инструментами и расширяется inline из author dashboard

---

## Подпись ревьюера

| Область | Ревьюер | Дата | Результат |
|---------|---------|------|-----------|
| P0 Безопасность | Claude | 2026-03-18 | Pass (исправлен timing attack в X-Internal-Token) |
| P0 Целостность данных | Claude | 2026-03-18 | Pass |
| P0 Уведомления | Claude | 2026-03-18 | Pass |
| P1 ACL/Роли | Claude | 2026-03-18 | Pass |
| P1 Рекомендации | Claude | 2026-03-18 | Pass |
| P1 UI/Шаблоны | Claude | 2026-03-18 | Pass |
| P2 Качество кода | Claude | 2026-03-18 | Pass |
| P3 Product Drift | Claude | 2026-03-18 | Pass |

PR может быть merged только когда все P0 и P1 — Pass.

---

## Замечания ревью

### Исправлено в ходе ревью

**[P0] timing attack в `bot/main.py`**
`bot/main.py:29` использовал `token != secret` для проверки `X-Internal-Token`.
Заменено на `hmac.compare_digest(token, secret)`.
Все остальные проверки HMAC в кодовой базе уже используют `compare_digest` корректно.

### Следующий обязательный cleanup

**[P1] Чистая миграция storage и БД**
- перед `deploy/migrate.sh --reset` запускать `scripts/clean_storage.sh --apply --fresh-runtime`;
- не переносить старые blob/json layout-и вручную;
- считать `storage/seed/*` и `storage/runtime/*` единственным поддерживаемым storage tree.
