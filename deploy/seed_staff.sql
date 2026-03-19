-- =============================================================================
-- deploy/seed_staff.sql — ручной seed staff-пользователей
--
-- Что делает:
--   1. Создает/обновляет admin-пользователя
--   2. Создает/обновляет test author-пользователя
--   3. Назначает роли admin/author
--   4. Для автора создает AuthorProfile
--   5. Предзаполняет watchlist автора всеми активными инструментами
--
-- Применение:
--   PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f deploy/seed_staff.sql
--
-- Важно:
--   - admin/login на сервере идет через Telegram Login Widget
--   - для этого у staff-пользователя должен быть корректный telegram_user_id
--   - test author ниже создан как заготовка; при необходимости поменяйте email / telegram_user_id / username / display_name
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Роли
-- -----------------------------------------------------------------------------

INSERT INTO roles (
    id,
    slug,
    title,
    created_at,
    updated_at
)
VALUES
    ('10000000-0000-4000-8000-000000000001'::uuid, 'admin',  'Администратор', now(), now()),
    ('10000000-0000-4000-8000-000000000002'::uuid, 'author', 'Автор',         now(), now())
ON CONFLICT (slug) DO UPDATE
SET
    title = EXCLUDED.title,
    updated_at = now();

-- -----------------------------------------------------------------------------
-- Admin: Алексей Сулименко
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    v_user_id uuid;
    v_role_id uuid;
BEGIN
    SELECT id INTO v_role_id FROM roles WHERE slug = 'admin';

    SELECT id
    INTO v_user_id
    FROM users
    WHERE email = 'sulimenkoas@gmail.com'
       OR telegram_user_id = 368288031
    ORDER BY updated_at DESC
    LIMIT 1;

    IF v_user_id IS NULL THEN
        v_user_id := '20000000-0000-4000-8000-000000000001'::uuid;

        INSERT INTO users (
            id,
            email,
            telegram_user_id,
            username,
            full_name,
            password_hash,
            status,
            timezone,
            lead_source_id,
            created_at,
            updated_at
        )
        VALUES (
            v_user_id,
            'sulimenkoas@gmail.com',
            368288031,
            'Sulimenko',
            'Сулименко Алексей',
            NULL,
            'active',
            'Asia/Almaty',
            NULL,
            now(),
            now()
        );
    ELSE
        UPDATE users
        SET
            email = 'sulimenkoas@gmail.com',
            telegram_user_id = 368288031,
            username = 'Sulimenko',
            full_name = 'Сулименко Алексей',
            status = 'active',
            updated_at = now()
        WHERE id = v_user_id;
    END IF;

    INSERT INTO user_roles (user_id, role_id)
    VALUES (v_user_id, v_role_id)
    ON CONFLICT DO NOTHING;
END
$$;

-- -----------------------------------------------------------------------------
-- Test author: заготовка для первого автора
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    v_user_id uuid;
    v_role_id uuid;
    v_author_id uuid;
BEGIN
    SELECT id INTO v_role_id FROM roles WHERE slug = 'author';

    SELECT id
    INTO v_user_id
    FROM users
    WHERE email = 'author-test@ptfin.ru'
       OR telegram_user_id = 999000001
    ORDER BY updated_at DESC
    LIMIT 1;

    IF v_user_id IS NULL THEN
        v_user_id := '20000000-0000-4000-8000-000000000002'::uuid;

        INSERT INTO users (
            id,
            email,
            telegram_user_id,
            username,
            full_name,
            password_hash,
            status,
            timezone,
            lead_source_id,
            created_at,
            updated_at
        )
        VALUES (
            v_user_id,
            'author-test@ptfin.ru',
            999000001,
            'author_test',
            'Тестовый Автор',
            NULL,
            'active',
            'Asia/Almaty',
            NULL,
            now(),
            now()
        );
    ELSE
        UPDATE users
        SET
            email = 'author-test@ptfin.ru',
            telegram_user_id = 999000001,
            username = 'author_test',
            full_name = 'Тестовый Автор',
            status = 'active',
            updated_at = now()
        WHERE id = v_user_id;
    END IF;

    INSERT INTO user_roles (user_id, role_id)
    VALUES (v_user_id, v_role_id)
    ON CONFLICT DO NOTHING;

    SELECT id
    INTO v_author_id
    FROM author_profiles
    WHERE user_id = v_user_id
    LIMIT 1;

    IF v_author_id IS NULL THEN
        v_author_id := '30000000-0000-4000-8000-000000000001'::uuid;

        INSERT INTO author_profiles (
            id,
            user_id,
            display_name,
            slug,
            bio,
            requires_moderation,
            is_active,
            created_at,
            updated_at
        )
        VALUES (
            v_author_id,
            v_user_id,
            'Тестовый Автор',
            'test-author',
            NULL,
            FALSE,
            TRUE,
            now(),
            now()
        );
    ELSE
        UPDATE author_profiles
        SET
            display_name = 'Тестовый Автор',
            slug = 'test-author',
            is_active = TRUE,
            updated_at = now()
        WHERE id = v_author_id;
    END IF;

    INSERT INTO author_watchlist_instruments (author_id, instrument_id)
    SELECT v_author_id, i.id
    FROM instruments i
    WHERE i.is_active = TRUE
    ON CONFLICT DO NOTHING;
END
$$;

COMMIT;
