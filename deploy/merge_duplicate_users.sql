-- Generic helper for future duplicate-user merges.
-- 1) Find users without telegram_user_id but with active subscriptions.
SELECT u.id, u.email, u.telegram_user_id, u.full_name, COUNT(s.id) AS sub_count
FROM users u
LEFT JOIN subscriptions s ON s.user_id = u.id
WHERE u.telegram_user_id IS NULL
  AND EXISTS (
    SELECT 1
    FROM subscriptions
    WHERE user_id = u.id
      AND status IN ('active', 'trial')
  )
GROUP BY u.id
ORDER BY u.created_at;

-- 2) Find the real user by email.
-- SELECT * FROM users WHERE email = 'xxx@yyy.com' AND telegram_user_id IS NOT NULL;

-- 3) Merge manually:
-- UPDATE subscriptions SET user_id = <real_id> WHERE user_id = <dup_id>;
-- UPDATE payments SET user_id = <real_id> WHERE user_id = <dup_id>;
-- UPDATE user_consents SET user_id = <real_id> WHERE user_id = <dup_id>;
-- DELETE FROM users WHERE id = <dup_id>;
