# PitchCopyTrade — Review Gate
> Обновлено: 2026-04-11

Текущий gate и открытые findings. Закрытые — в `doc/changelog.md`.

## Gate: GREEN (с оговорками)

- 336 тестов проходят (20.6s)
- Mini App auth работает в production
- Message-centric author UI, composer, preview, delivery — функциональны
- Checkout, подписки, уведомления — работают
- XSS, SQL injection, auth bypass — не обнаружено

## Открытые findings

| ID | Severity | Описание | Задача |
|---|---|---|---|
| SEC-1 | HIGH | Open redirect через `requested_next` | T-001 |
| SEC-2 | MEDIUM | File upload без magic bytes validation | T-002 |
| SEC-3 | MEDIUM | Нет CSRF-токенов (приемлемо для MVP) | backlog |
| DB-1 | HIGH | 26 FK-колонок без индексов | T-003 |
| DB-2 | HIGH | Messages table без FK constraints | T-004 |
| DB-3 | MEDIUM | Двойной запрос в `get_public_product_by_slug` | T-005 |
| DB-4 | MEDIUM | Python-фильтрация в `list_user_reminder_events` | T-006 |
| AUTH-1 | LOW | Signature hash validation cleanup | T-007 |

## Что подтверждено

- Auth: Telegram Mini App + staff invite — production OK
- Delivery: Telegram-first + email fallback — работает
- Checkout: stub_manual + free product — работает
- Race condition в `upsert_telegram_subscriber` — исправлен
- Duplicate subscription — защита добавлена

## Заключения по блокам

_(пока нет завершённых блоков в новом формате)_
