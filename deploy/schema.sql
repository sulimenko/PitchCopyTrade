-- =============================================================================
-- PitchCopyTrade — полная схема базы данных
-- Применить: psql -U pct -d pct -f deploy/schema.sql
--         или через скрипт: bash deploy/migrate.sh
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Enum-типы
-- -----------------------------------------------------------------------------

CREATE TYPE role_slug AS ENUM ('admin', 'author', 'moderator');
CREATE TYPE user_status AS ENUM ('invited', 'active', 'inactive');
CREATE TYPE invite_delivery_status AS ENUM ('sent', 'failed', 'resent');
CREATE TYPE lead_source_type AS ENUM ('ads', 'blogger', 'organic', 'direct', 'referral');
CREATE TYPE strategy_status AS ENUM ('draft', 'published', 'archived');
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high');
CREATE TYPE product_type AS ENUM ('strategy', 'author', 'bundle');
CREATE TYPE billing_period AS ENUM ('month', 'quarter', 'year');
CREATE TYPE payment_provider AS ENUM ('stub_manual', 'tbank');
CREATE TYPE payment_status AS ENUM ('created', 'pending', 'paid', 'failed', 'expired', 'cancelled', 'refunded');
CREATE TYPE subscription_status AS ENUM ('pending', 'trial', 'active', 'expired', 'cancelled', 'blocked');
CREATE TYPE legal_document_type AS ENUM ('disclaimer', 'offer', 'privacy_policy', 'payment_consent');
CREATE TYPE instrument_type AS ENUM ('equity');
CREATE TYPE notification_channel AS ENUM ('telegram', 'email');

-- -----------------------------------------------------------------------------
-- Таблицы
-- -----------------------------------------------------------------------------

CREATE TABLE lead_sources (
    id          UUID PRIMARY KEY,
    source_type lead_source_type NOT NULL,
    name        VARCHAR(120) NOT NULL,
    ref_code    VARCHAR(120),
    utm_source  VARCHAR(120),
    utm_medium  VARCHAR(120),
    utm_campaign VARCHAR(120),
    utm_content VARCHAR(120),
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_lead_sources_ref_code UNIQUE (ref_code)
);
CREATE INDEX ix_lead_sources_source_type ON lead_sources (source_type);

CREATE TABLE users (
    id               UUID PRIMARY KEY,
    email            VARCHAR(320),
    telegram_user_id BIGINT,
    username         VARCHAR(64),
    full_name        VARCHAR(255),
    password_hash    VARCHAR(255),
    status           user_status NOT NULL,
    invite_token_version INTEGER NOT NULL DEFAULT 1,
    invite_delivery_status invite_delivery_status,
    invite_delivery_error TEXT,
    invite_delivery_updated_at TIMESTAMPTZ,
    timezone         VARCHAR(64) NOT NULL,
    lead_source_id   UUID REFERENCES lead_sources (id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_users_email             UNIQUE (email),
    CONSTRAINT uq_users_telegram_user_id  UNIQUE (telegram_user_id)
);

CREATE TABLE roles (
    id         UUID PRIMARY KEY,
    slug       role_slug NOT NULL,
    title      VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_roles_slug UNIQUE (slug)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_id)
);

CREATE TABLE author_profiles (
    id                  UUID PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    display_name        VARCHAR(255) NOT NULL,
    slug                VARCHAR(120) NOT NULL,
    bio                 TEXT,
    requires_moderation BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_author_profiles_slug    UNIQUE (slug),
    CONSTRAINT uq_author_profiles_user_id UNIQUE (user_id)
);

CREATE TABLE instruments (
    id              UUID PRIMARY KEY,
    ticker          VARCHAR(32) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    board           VARCHAR(32) NOT NULL,
    lot_size        INTEGER NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    instrument_type instrument_type NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_instruments_ticker UNIQUE (ticker)
);

CREATE TABLE author_watchlist_instruments (
    author_id     UUID NOT NULL REFERENCES author_profiles (id) ON DELETE CASCADE,
    instrument_id UUID NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    CONSTRAINT pk_author_watchlist_instruments PRIMARY KEY (author_id, instrument_id)
);

CREATE TABLE strategies (
    id                UUID PRIMARY KEY,
    author_id         UUID NOT NULL REFERENCES author_profiles (id) ON DELETE CASCADE,
    slug              VARCHAR(120) NOT NULL,
    title             VARCHAR(255) NOT NULL,
    short_description VARCHAR(500) NOT NULL,
    full_description  TEXT,
    risk_level        risk_level NOT NULL,
    status            strategy_status NOT NULL,
    min_capital_rub   INTEGER,
    is_public         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_strategies_slug UNIQUE (slug)
);

CREATE TABLE bundles (
    id          UUID PRIMARY KEY,
    slug        VARCHAR(120) NOT NULL,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    is_public   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_bundles_slug UNIQUE (slug)
);

CREATE TABLE bundle_members (
    bundle_id   UUID NOT NULL REFERENCES bundles (id) ON DELETE CASCADE,
    strategy_id UUID NOT NULL REFERENCES strategies (id) ON DELETE CASCADE,
    CONSTRAINT pk_bundle_members PRIMARY KEY (bundle_id, strategy_id)
);

CREATE TABLE subscription_products (
    id               UUID PRIMARY KEY,
    product_type     product_type NOT NULL,
    slug             VARCHAR(120) NOT NULL,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    strategy_id      UUID REFERENCES strategies (id) ON DELETE SET NULL,
    author_id        UUID REFERENCES author_profiles (id) ON DELETE SET NULL,
    bundle_id        UUID REFERENCES bundles (id) ON DELETE SET NULL,
    billing_period   billing_period NOT NULL,
    price_rub        INTEGER NOT NULL,
    trial_days       INTEGER NOT NULL DEFAULT 0,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    autorenew_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_subscription_products_slug UNIQUE (slug),
    CONSTRAINT ck_subscription_products_price_rub_non_negative
        CHECK (price_rub >= 0),
    CONSTRAINT ck_subscription_products_trial_days_non_negative
        CHECK (trial_days >= 0),
    CONSTRAINT ck_subscription_products_target_matches_product_type CHECK (
        (product_type = 'strategy' AND strategy_id IS NOT NULL AND author_id IS NULL AND bundle_id IS NULL)
        OR
        (product_type = 'author'   AND author_id   IS NOT NULL AND strategy_id IS NULL AND bundle_id IS NULL)
        OR
        (product_type = 'bundle'   AND bundle_id   IS NOT NULL AND strategy_id IS NULL AND author_id IS NULL)
    )
);

CREATE TABLE promo_codes (
    id                  UUID PRIMARY KEY,
    code                VARCHAR(64) NOT NULL,
    description         VARCHAR(255),
    discount_percent    INTEGER,
    discount_amount_rub INTEGER,
    max_redemptions     INTEGER,
    current_redemptions INTEGER NOT NULL DEFAULT 0,
    expires_at          TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_promo_codes_code UNIQUE (code),
    CONSTRAINT ck_promo_codes_current_redemptions_non_negative
        CHECK (current_redemptions >= 0)
);

CREATE TABLE payments (
    id               UUID PRIMARY KEY,
    user_id          UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id       UUID NOT NULL REFERENCES subscription_products (id) ON DELETE RESTRICT,
    promo_code_id    UUID REFERENCES promo_codes (id) ON DELETE SET NULL,
    provider         payment_provider NOT NULL,
    status           payment_status NOT NULL,
    amount_rub       INTEGER NOT NULL,
    discount_rub     INTEGER NOT NULL DEFAULT 0,
    final_amount_rub INTEGER NOT NULL,
    currency         VARCHAR(3) NOT NULL,
    external_id      VARCHAR(255),
    stub_reference   VARCHAR(255),
    provider_payload JSONB,
    expires_at       TIMESTAMPTZ,
    confirmed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_payments_amount_rub_non_negative
        CHECK (amount_rub >= 0),
    CONSTRAINT ck_payments_discount_rub_non_negative
        CHECK (discount_rub >= 0),
    CONSTRAINT ck_payments_final_amount_rub_non_negative
        CHECK (final_amount_rub >= 0)
);

CREATE TABLE subscriptions (
    id                    UUID PRIMARY KEY,
    user_id               UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id            UUID NOT NULL REFERENCES subscription_products (id) ON DELETE RESTRICT,
    payment_id            UUID REFERENCES payments (id) ON DELETE SET NULL,
    lead_source_id        UUID REFERENCES lead_sources (id) ON DELETE SET NULL,
    applied_promo_code_id UUID REFERENCES promo_codes (id) ON DELETE SET NULL,
    status                subscription_status NOT NULL,
    autorenew_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    is_trial              BOOLEAN NOT NULL DEFAULT FALSE,
    manual_discount_rub   INTEGER NOT NULL DEFAULT 0,
    start_at              TIMESTAMPTZ NOT NULL,
    end_at                TIMESTAMPTZ NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_subscriptions_manual_discount_rub_non_negative
        CHECK (manual_discount_rub >= 0),
    CONSTRAINT ck_subscriptions_end_after_start
        CHECK (end_at > start_at)
);

CREATE TABLE legal_documents (
    id            UUID PRIMARY KEY,
    document_type legal_document_type NOT NULL,
    version       VARCHAR(50) NOT NULL,
    title         VARCHAR(255) NOT NULL,
    content_md    TEXT NOT NULL,
    source_path   VARCHAR(500),
    is_active     BOOLEAN NOT NULL DEFAULT FALSE,
    published_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_legal_documents_document_type_version UNIQUE (document_type, version)
);

CREATE TABLE user_consents (
    id          UUID PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES legal_documents (id) ON DELETE CASCADE,
    payment_id  UUID REFERENCES payments (id) ON DELETE SET NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    source      VARCHAR(32) NOT NULL,
    ip_address  VARCHAR(64),
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_user_consents_user_document_payment
        UNIQUE (user_id, document_id, payment_id)
);

CREATE TABLE messages (
    id          UUID PRIMARY KEY,
    thread      UUID,
    parent      UUID,
    author      UUID,
    user        UUID,
    moderator   UUID,
    strategy    UUID,
    bundle      UUID,
    deliver     VARCHAR(32)[] DEFAULT ARRAY[]::VARCHAR(32)[],
    channel     VARCHAR(32)[] DEFAULT ARRAY['telegram', 'miniapp']::VARCHAR(32)[],
    kind        VARCHAR(32),
    type        VARCHAR(32),
    status      VARCHAR(32) DEFAULT 'draft',
    moderation  VARCHAR(32) DEFAULT 'required',
    title       VARCHAR(255),
    comment     TEXT,
    schedule    TIMESTAMPTZ,
    published   TIMESTAMPTZ,
    archived    TIMESTAMPTZ,
    documents   JSONB DEFAULT '[]'::jsonb,
    text        JSONB DEFAULT '{}'::jsonb,
    deals       JSONB DEFAULT '[]'::jsonb,
    created     TIMESTAMPTZ NOT NULL,
    updated     TIMESTAMPTZ NOT NULL
);

CREATE TABLE audit_events (
    id            UUID PRIMARY KEY,
    actor_user_id UUID REFERENCES users (id) ON DELETE SET NULL,
    entity_type   VARCHAR(120) NOT NULL,
    entity_id     UUID,
    action        VARCHAR(120) NOT NULL,
    payload       JSONB,
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE notification_log (
    id                UUID PRIMARY KEY,
    message_id        UUID,
    user_id           UUID REFERENCES users (id) ON DELETE SET NULL,
    channel           notification_channel NOT NULL,
    sent_at           TIMESTAMPTZ,
    success           BOOLEAN NOT NULL DEFAULT FALSE,
    error_detail      TEXT,
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL
);
