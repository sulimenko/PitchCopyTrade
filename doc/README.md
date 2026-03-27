# PitchCopyTrade — Research Entry
> Обновлено: 2026-03-26
> Этот файл — стартовая точка нового цикла исследования MVP.

## Канонические документы

- `doc/README.md` — быстрый вход в проект и локальный runbook без Docker
- `doc/blueprint.md` — текущий продуктовый и UX-контракт
- `doc/task.md` — только активный backlog
- `doc/review.md` — текущие findings и merge gate

Все старые фазы считаются архивом в git history и в эти документы не переносятся.

## Короткий снимок проекта

- backend: `FastAPI` + `Jinja2`
- bot: `aiogram`
- worker: polling loop
- public views:
  - `/catalog`
  - `/catalog/strategies/{slug}`
  - `/checkout/{product_id}`
- miniapp views:
  - `/app`
  - `/app/catalog`
  - `/app/help`
  - `/app/status`
  - `/app/payments`
  - `/app/subscriptions`
- staff views:
  - `/login`
  - `/admin/*`
  - `/author/*`
  - `/moderation/*`

Важные факты текущего цикла:
- canonical runtime env file = `.env`, sample template = `.env.example`;
- `deploy/docker-compose.server.yml` и `deploy/migrate.sh` должны читать тот же `.env`;
- для локального исследования без Docker основной режим = `APP_DATA_MODE=file`;
- `api` не стартует без `INTERNAL_API_SECRET`;
- `file`-mode работает поверх `storage/runtime/*`, поэтому локальные данные нужно периодически сбрасывать;
- `db`-mode нужен только если вы реально хотите поднимать локальный PostgreSQL и проверять server-like сценарии;
- для MVP-исследования `file`-mode удобнее и быстрее.

## First-class preview mode

Для локальной верстки без Telegram токенов и cookies включите:

```bash
export APP_PREVIEW_ENABLED=true
```

Preview surfaces:

- `http://127.0.0.1:8000/preview`
- `http://127.0.0.1:8000/preview/app/catalog`
- `http://127.0.0.1:8000/preview/app/status`
- `http://127.0.0.1:8000/preview/app/help`
- `http://127.0.0.1:8000/preview/admin/dashboard`
- `http://127.0.0.1:8000/preview/author/dashboard`

Это локальный browser preview для layout work. Он не заменяет финальную проверку внутри Telegram WebApp.

## Local dev access bootstrap

Если нужен один локальный вход без Telegram/OAuth, откройте:

- `http://127.0.0.1:8000/dev/bootstrap`

Что делает bootstrap:

- поднимает один staff-аккаунт с ролями `admin`, `author`, `moderator`;
- ставит staff session cookie, staff mode cookie и Telegram fallback cookie поверх текущей session/cookie модели;
- открывает нужную surface сразу в браузере;
- работает только в `development`, `test` и `local` env.

Bootstrap-аккаунт:

- email: `dev-superuser@pitchcopytrade.local`
- password: `local-dev-password`
- Telegram ID: `999000099`

Доступные режимы:

- `admin` -> `/admin/dashboard`
- `author` -> `/author/dashboard`
- `moderator` -> `/moderation/queue`
- `catalog` -> `/app/catalog`

Это dev-only ускоритель для локального доступа. Он не заменяет preview mode и не должен использоваться как production path.

## Локальный запуск без Docker

### 1. Подготовка окружения

```bash
cd /Users/alexey/site/PitchCopyTrade

if [ ! -x ./.venv/bin/python ]; then
  python3.12 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -e ".[dev]"
fi
```

Если зависимости уже стоят в `.venv`, этого достаточно.

### 2. Сбросить mutable runtime перед воспроизводимой проверкой

```bash
cd /Users/alexey/site/PitchCopyTrade
bash scripts/clean_storage.sh --apply --fresh-runtime
```

Зачем это нужно:
- `storage/runtime/json/*` и `storage/runtime/blob/*` меняются во время локальных тестов;
- после очистки file-mode заново поднимется от `storage/seed/*`;
- без этого можно получить ложные результаты, потому что runtime уже "запомнил" старые локальные действия.

### 3. Терминал 1: поднять `api`

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_ENV=development
export APP_HOST=127.0.0.1
export APP_PORT=8000
export BASE_URL=http://127.0.0.1:8000
export ADMIN_BASE_URL=http://127.0.0.1:8000/admin
export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret
export TELEGRAM_USE_WEBHOOK=false
export TELEGRAM_BOT_USERNAME=local_preview_bot

./.venv/bin/python -m uvicorn pitchcopytrade.main:app --reload --host 127.0.0.1 --port 8000
```

Этого уже достаточно, чтобы:
- смотреть public views;
- тестировать GET/POST формы;
- открывать miniapp screens в браузере через demo auth link;
- править шаблоны и сразу видеть изменения.

### 4. Терминал 2: поднять `worker` при необходимости

Нужно только если вы исследуете lifecycle/reminder/scheduled сценарии.

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_ENV=development
export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret

./.venv/bin/python -m pitchcopytrade.worker.main
```

### 5. Терминал 3: поднять `bot` только если есть реальный Telegram token

Для обычной локальной верстки и HTML-проверок бот не нужен.

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_ENV=development
export BASE_URL=https://<your-https-host>
export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret
export TELEGRAM_USE_WEBHOOK=false
export TELEGRAM_BOT_TOKEN=<real-token>
export TELEGRAM_BOT_USERNAME=<real-bot-username>

./.venv/bin/python -m pitchcopytrade.bot.main
```

Без реального токена этот контур поднимать не нужно.

### 6. Reproducible file-mode smoke profile

Для повторяемых smoke-check'ов используйте профиль:

```bash
source scripts/local_file_profile.sh
bash scripts/local_file_smoke.sh
```

Профиль выставляет `APP_PREVIEW_ENABLED=true` и проверяет preview/public URL в одном коротком прогоне.

## Что открывать в браузере

### Public views

После старта `api`:

- `http://127.0.0.1:8000/catalog`
- `http://127.0.0.1:8000/catalog/strategies/momentum-ru`
- `http://127.0.0.1:8000/checkout/product-1`
- `http://127.0.0.1:8000/legal/doc-disclaimer`

Это хороший слой для:
- быстрой проверки GET;
- проверки form POST;
- правки layout, typography, spacing, cards, CTA.

### Mini App views: как открыть в обычном браузере

Есть три уровня полезности.

#### Вариант A — просто посмотреть entry screens

Открыть напрямую:

- `http://127.0.0.1:8000/app`
- `http://127.0.0.1:8000/miniapp`

Это полезно для:
- `app/miniapp_entry.html`
- `public/miniapp_bootstrap.html`

Но этого недостаточно для защищенных `/app/*` страниц.

#### Вариант B — browser preview для настоящих `/app/*` screen'ов

Сгенерируйте demo subscriber link:

```bash
cd /Users/alexey/site/PitchCopyTrade

export APP_DATA_MODE=file
export APP_STORAGE_ROOT=storage
export BASE_URL=http://127.0.0.1:8000
export ADMIN_BASE_URL=http://127.0.0.1:8000/admin
export APP_SECRET_KEY=local-app-secret
export INTERNAL_API_SECRET=local-internal-secret

./.venv/bin/python - <<'PY'
import asyncio
from pitchcopytrade.repositories.public import FilePublicRepository
from pitchcopytrade.services.public import TelegramSubscriberProfile, upsert_telegram_subscriber
from pitchcopytrade.auth.session import build_telegram_login_link_token

async def main():
    repo = FilePublicRepository()
    user = await upsert_telegram_subscriber(
        repo,
        TelegramSubscriberProfile(
            telegram_user_id=700000001,
            username="local_subscriber",
            first_name="Local",
            last_name="Subscriber",
            timezone_name="Asia/Almaty",
        ),
    )
    await repo.commit()
    print(
        f"http://127.0.0.1:8000/tg-auth?token={build_telegram_login_link_token(user)}&next=/app/catalog"
    )

asyncio.run(main())
PY
```

Откройте напечатанную ссылку один раз в браузере. Она:
- поставит subscriber cookie;
- перекинет вас в `/app/catalog`.

После этого можно открывать и редактировать в браузере:

- `http://127.0.0.1:8000/app/catalog`
- `http://127.0.0.1:8000/app/help`
- `http://127.0.0.1:8000/app/status`
- `http://127.0.0.1:8000/app/payments`
- `http://127.0.0.1:8000/app/subscriptions`
- `http://127.0.0.1:8000/app/feed`

Это сейчас лучший local-browser path для miniapp templates.

#### Вариант C — финальная проверка в Telegram

Browser preview не заменяет:
- `Telegram.WebApp.initData`;
- поведение настоящего webview;
- deep link / web_app кнопки;
- эффекты "одной вкладки" внутри Telegram.

Для финальной валидации miniapp-навигации нужен HTTPS и реальный запуск из Telegram.

## Canonical validation checklist

### Canonical preview URLs for design and layout work

Use these URLs as the default browser-preview entry set:

- `http://127.0.0.1:8000/preview`
- `http://127.0.0.1:8000/preview/app/catalog`
- `http://127.0.0.1:8000/preview/app/status`
- `http://127.0.0.1:8000/preview/app/help`
- `http://127.0.0.1:8000/preview/app/payments`
- `http://127.0.0.1:8000/preview/app/subscriptions`
- `http://127.0.0.1:8000/preview/admin/dashboard`
- `http://127.0.0.1:8000/preview/author/dashboard`

These are for local browser preview only. They are not a substitute for Telegram WebApp behavior.

### Canonical real-device Telegram scenarios

Check these flows in a real Telegram client:

1. Open the bot and press `/start`.
2. Open the bot and press `/help`.
3. Launch the Mini App and confirm it lands on `/app/catalog`.
4. Move from catalog to strategy detail and then to checkout without leaving the same webview.
5. Open `/app/help` from inside the Mini App and return to catalog in the same webview.
6. Confirm checkout submission creates a payment/subscription pair and returns a success screen.

### Minimum smoke-check matrix

- `public`
  - `/catalog`
  - `/catalog/strategies/{slug}`
  - `/checkout/{product_id}`
  - `/legal/{document_id}`
- `miniapp`
  - `/app/catalog`
  - `/app/strategies/{slug}`
  - `/app/help`
  - `/app/status`
  - `/app/payments`
  - `/app/subscriptions`
- `admin`
  - `/login`
  - `/admin/dashboard`
  - one strategy edit screen
  - one product edit screen
- `author`
  - `/author/dashboard`
  - `/author/recommendations`
  - inline recommendation create
  - watchlist add/remove

Keep browser preview and Telegram device checks separate when you report results.

## Какие view править в первую очередь

### Для главной и витрины

- `src/pitchcopytrade/web/templates/public/catalog.html`
- `src/pitchcopytrade/web/templates/public/strategy_detail.html`
- `src/pitchcopytrade/web/templates/public/checkout.html`
- `src/pitchcopytrade/web/templates/public/checkout_success.html`

### Для Mini App entry/help/navigation

- `src/pitchcopytrade/web/templates/app/miniapp_entry.html`
- `src/pitchcopytrade/web/templates/public/miniapp_bootstrap.html`
- `src/pitchcopytrade/web/templates/app/_miniapp_nav.html`
- `src/pitchcopytrade/web/templates/app/help.html`
- `src/pitchcopytrade/web/templates/app/status.html`
- `src/pitchcopytrade/web/templates/app/payments.html`
- `src/pitchcopytrade/web/templates/app/subscriptions.html`

### Для bot/help/entry logic

- `src/pitchcopytrade/bot/handlers/start.py`
- `src/pitchcopytrade/api/routes/auth.py`
- `src/pitchcopytrade/api/routes/public.py`
- `src/pitchcopytrade/api/routes/app.py`

## Как проверять GET и POST локально

### Простые GET

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -i http://127.0.0.1:8000/catalog
curl -i 'http://127.0.0.1:8000/api/instruments?q=SBER'
```

### Public checkout POST

```bash
curl -i -X POST http://127.0.0.1:8000/checkout/product-1 \
  -d 'full_name=Local Tester' \
  -d 'email=local@example.com' \
  -d 'timezone_name=Asia/Almaty' \
  -d 'lead_source_name=local_test' \
  -d 'accepted_document_ids=doc-disclaimer' \
  -d 'accepted_document_ids=doc-offer' \
  -d 'accepted_document_ids=doc-privacy_policy' \
  -d 'accepted_document_ids=doc-payment_consent'
```

Ожидаемое поведение в `file`-mode:
- HTTP `201 Created`;
- экран `Заявка создана`;
- новые записи в `storage/runtime/json/payments.json` и `storage/runtime/json/subscriptions.json`.

### Mini App GET после demo auth

После открытия `tg-auth` ссылки можно делать:

```bash
curl -i http://127.0.0.1:8000/app/catalog
curl -i http://127.0.0.1:8000/app/help
```

Но для `curl` уже понадобится cookie jar. Для обычной верстки проще открыть эти URL прямо в браузере после one-time auth link.

## Если нужен local PostgreSQL без Docker

Это возможно, но не рекомендуется как основной путь для текущего MVP-исследования.

Причина:
- `db`-mode требует локальный PostgreSQL;
- schema поднимается из `deploy/schema.sql`;
- startup seeders добавляют инструменты и bootstrap admin, но не дают такой же быстрый subscriber-facing демо-контур, как `file`-mode.

Для дизайна и subscriber flow сначала используйте `file`-mode.

## Ограничения текущего исследования

- `Straddle.pdf` — image-based PDF. Он годится как визуальный reference, но не как полноценный текстовый источник для автоматического анализа.
- текущий `/api/instruments` еще не использует `meta.pbull.kz`;
- browser preview Mini App пока технический, а не first-class dev mode;
- one-tab behavior надо проверять именно в Telegram, а не только в Chrome/Safari.
