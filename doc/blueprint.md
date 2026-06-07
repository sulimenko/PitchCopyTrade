# PitchCopyTrade — Blueprint

This file is the stable project contract used by AI Pipeline v8 tasks and reviews.

## Product profile

PitchCopyTrade is a Telegram-first marketplace for subscriptions to investment strategy messages.

Main surfaces:

- public catalog and checkout;
- Telegram Mini App subscriber workspace;
- web staff surfaces for admin, author and moderator;
- background worker for lifecycle jobs, delivery and scheduled publishing.

## Current runtime direction

The active runtime target is DB mode:

```text
APP_DATA_MODE=db
```

DB mode means PostgreSQL with SQLAlchemy 2 async and Alembic migrations.

Legacy areas that should be removed, migrated or avoided in new feature work:

- `APP_DATA_MODE=file`;
- JSON-backed file repositories;
- `storage/seed/*` demo datasets;
- `storage/runtime/*` as a persistence model;
- old local file-mode parity tasks.

New tasks must not expand legacy file mode unless the task explicitly asks to remove, migrate or clean it.

## Architecture rules

- API routes handle HTTP, forms and templates; business logic lives in services.
- Data access belongs in repositories or well-scoped DB utilities, not templates.
- Alembic migrations are required for DB schema changes.
- Payments and subscriptions must keep strict state transitions.
- Checkout must not grant access before final paid or confirmed state.
- Pending, failed, cancelled and expired payment states must not grant delivery access.
- Subscriber data must be scoped to the current Telegram identity.
- Author data must be scoped to the author's allowed strategies/messages.
- Admin and moderator actions must not bypass role checks.

## Subscriber UX contract

- Subscriber product UX is Telegram-first and Mini App-first.
- Bot command surface should stay minimal.
- Protected subscriber web fallback must not become the primary UX.
- Telegram WebApp data must be validated by backend code.
- UI text visible to users must be Russian.
- Do not add onboarding or help text unless the task explicitly requests it.

## Staff and author contract

- Admin, author and moderator are staff/web surfaces.
- Author workspace is message-centric.
- Canonical author surfaces include:
  - `/author/messages`;
  - `/author/messages/new`;
  - `/author/messages/<id>/edit`.
- Author UI uses unified composer plus history table.

## AI Pipeline v8 usage

- Task workflow rules live in `doc/task.md`.
- Project-specific AI settings live in `doc/ai/chatgpt/project-settings.md`.
- Task templates live in `doc/ai/chatgpt/task-template.md` and `doc/ai/chatgpt/followup-template.md`.
- Review rules live in `doc/ai/chatgpt/reviewer.instructions.md`.
- `doc/review.md` is only a short pointer to the current review gate.
- Historical task notes live in `doc/changelog.md`.
