# PitchCopyTrade — Active Tasks
> Обновлено: 2026-04-11

Активные задачи. Закрытые блоки — в `doc/changelog.md`.

## Правила

- ID: `T-NNN`, сквозная нумерация, не сбрасывается
- Статусы: `[ ]` не начато / `[~]` в работе / `[x]` завершено / `[!]` заблокировано
- Один блок = одна итерация worker → review
- Каждая задача: файлы, поведение до/после, критерии приёмки
- Runtime priority: `APP_DATA_MODE=db`

---

## Блок 1 — Security & DB cleanup

### T-001 Open redirect через `requested_next` [SEC, HIGH]

- [ ] Валидировать `requested_next` в `_verify_redirect_url()` (`src/pitchcopytrade/api/routes/app.py`)
- Ограничить до внутренних путей, начинающихся с `/app/`
- Если путь не начинается с `/app/` → заменить на `/app/catalog`
- Убрать `safe='/'` из `quote()` — использовать `safe=''`

### T-002 File upload: magic bytes validation [SEC, MEDIUM]

- [ ] В `normalize_attachment_uploads()` (`src/pitchcopytrade/services/author.py`)
- Добавить проверку file signature (magic bytes) помимо content-type header
- PDF: `%PDF` (первые 4 байта), JPEG: `\xff\xd8\xff` (первые 3 байта)
- Если magic bytes не совпадают — `ValueError("Файл не является допустимым PDF или JPG.")`

### T-003 FK-индексы в deploy/schema.sql [DB, HIGH]

- [ ] Добавить `CREATE INDEX` на все FK-колонки в `deploy/schema.sql`
- Приоритетные: `payments.user_id`, `subscriptions.user_id`, `subscriptions.product_id`, `user_consents.user_id`
- Формат: `CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table}({column});`

### T-004 Messages table: FK constraints [DB, HIGH]

- [ ] Добавить `REFERENCES` constraints в `deploy/schema.sql` для таблицы `messages`
- Колонки: `author` → `author_profiles(id)`, `user_id` → `users(id)`, `moderator_id` → `users(id)`, `strategy_id` → `strategies(id)`, `bundle_id` → `bundles(id)`

### T-005 Оптимизация `get_public_product_by_slug` [DB, MEDIUM]

- [ ] В `src/pitchcopytrade/repositories/public.py` метод `get_public_product_by_slug`
- Убрать рекурсивный вызов `get_public_product_by_ref` после загрузки product
- Сделать один запрос с полным набором `selectinload`/`joinedload`

### T-006 `list_user_reminder_events`: SQL фильтрация [DB, MEDIUM]

- [ ] В `src/pitchcopytrade/repositories/access.py` метод `list_user_reminder_events`
- Перенести фильтрацию `user_id` из Python в SQL WHERE clause
- Использовать JSON-оператор PostgreSQL: `.where(AuditEvent.payload["user_id"].astext == user_id)`

### T-007 Signature hash validation cleanup [AUTH, LOW]

- [ ] В `src/pitchcopytrade/auth/telegram_webapp.py` функция `validate_telegram_webapp_init_data`
- Упростить: signature в основном пути, без signature как fallback
- Добавить тесты обоих путей
