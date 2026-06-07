# PitchCopyTrade — Review Gate
> Обновлено: 2026-04-21

Текущий gate и открытые findings. Закрытые — в `doc/changelog.md`.

## Gate: GREEN

- основные блоки `T-001` ... `T-015` закрыты;
- subscriber checkout, staff auth redirect, structured composer, bot entry, Telegram delivery и auth recovery приведены к текущему контракту.

## Открытые findings

- Открытых findings нет.

## Что подтверждено

- checkout legal visibility работает по disclaimer-only contract;
- public checkout требует опубликованный `Дисклеймер`, а не полный legal pack;
- primary Mini App nav template держит `Каталог / Подписки / История`;
- attachments сохраняются в storage и доставляются в Telegram как media/document payload.
- structured composer теперь допускает ручной exact ticker на submit и backend импортирует инструмент по точному `symbol`, если локального `structured_instrument_id` нет.
- Google OAuth error UX больше не раскрывает backend exception text в login UI.
- bot/start и recovery surfaces используют `/miniapp` bootstrap route и deep-link `verify_telegram`.
- targeted regression run:
  - `./.venv/bin/python -m pytest tests/test_author_ui.py -q` -> `9 passed`
  - `./.venv/bin/python -m pytest tests/test_bot_baseline.py tests/test_auth_ui.py tests/test_public_catalog_checkout.py -q` -> `98 passed`

## Заключения по блокам

- Block 1 (`T-001` ... `T-007`) закрыт.
- Block 2 (`T-008` ... `T-012`) закрыт.
- Block 3 (`T-013`) закрыт.
- Block 4 (`T-014` ... `T-015`) закрыт.
- `T-010` закрыт после восстановления UI/runtime contract по новому инструменту.
- Финальный review-pass 2026-04-21 не открыл новых findings по закрытым задачам текущего цикла.
