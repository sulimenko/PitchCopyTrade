-- P26: миграция дубликатов пользователей на реального пользователя с telegram_user_id
-- Реальный пользователь:
--   a1f35a46-252b-4b94-84c5-5a8b59465301 (telegram_user_id=368288031)
-- Дубликаты (telegram_user_id IS NULL):
--   bee0cd23-af1c-4781-9d55-ef947e560904
--   e9ff7dba-5a7d-4253-bfbf-1d64b932e7a7
--   05c3b691-5674-43d4-85d9-d99d08ec8331

BEGIN;

UPDATE subscriptions
SET user_id = 'a1f35a46-252b-4b94-84c5-5a8b59465301'
WHERE user_id IN (
  'bee0cd23-af1c-4781-9d55-ef947e560904',
  'e9ff7dba-5a7d-4253-bfbf-1d64b932e7a7',
  '05c3b691-5674-43d4-85d9-d99d08ec8331'
);

UPDATE payments
SET user_id = 'a1f35a46-252b-4b94-84c5-5a8b59465301'
WHERE user_id IN (
  'bee0cd23-af1c-4781-9d55-ef947e560904',
  'e9ff7dba-5a7d-4253-bfbf-1d64b932e7a7',
  '05c3b691-5674-43d4-85d9-d99d08ec8331'
);

UPDATE user_consents
SET user_id = 'a1f35a46-252b-4b94-84c5-5a8b59465301'
WHERE user_id IN (
  'bee0cd23-af1c-4781-9d55-ef947e560904',
  'e9ff7dba-5a7d-4253-bfbf-1d64b932e7a7',
  '05c3b691-5674-43d4-85d9-d99d08ec8331'
);

DELETE FROM users
WHERE id IN (
  'bee0cd23-af1c-4781-9d55-ef947e560904',
  'e9ff7dba-5a7d-4253-bfbf-1d64b932e7a7',
  '05c3b691-5674-43d4-85d9-d99d08ec8331'
);

SELECT s.id AS subscription_id, s.status, u.telegram_user_id, u.email, sp.slug
FROM subscriptions s
JOIN users u ON s.user_id = u.id
JOIN subscription_products sp ON s.product_id = sp.id
WHERE s.status IN ('active', 'trial');

COMMIT;
