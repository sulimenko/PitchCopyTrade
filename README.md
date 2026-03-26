# PitchCopyTrade

Текущий цикл проекта сфокусирован на чистке MVP subscriber contour:
- Mini App должен открываться с витрины стратегий;
- help должен жить как экран приложения;
- описание стратегий должно стать сильнее и структурнее;
- real-time данные по инструментам должны приходить через backend adapter;
- checkout/navigation defects должны быть разобраны до implementation pass.

## С чего начинать

Канонический набор документов:
- `doc/README.md` — старт исследования и локальный runbook без Docker
- `doc/blueprint.md` — текущий продуктовый контракт
- `doc/task.md` — только активный backlog
- `doc/review.md` — текущие findings и merge gate

## Быстрый практический выбор

Если цель:
- быстро поднять проект локально без Docker;
- смотреть GET/POST;
- редактировать public и Mini App view в браузере;
- открыть Mini App и staff без ручных токенов;

используйте `APP_DATA_MODE=file` и runbook из `doc/README.md`.

## Что важно помнить

- `file`-mode читает `storage/runtime/*`, а не напрямую `storage/seed/*`;
- перед воспроизводимыми локальными тестами runtime лучше чистить через `bash scripts/clean_storage.sh --apply --fresh-runtime`;
- browser preview Mini App полезен для верстки, но финальную проверку webview/navigation надо делать внутри Telegram на HTTPS;
- first-class preview mode доступен через `APP_PREVIEW_ENABLED=true` и `http://127.0.0.1:8011/preview`;
- старые фазы проекта сознательно не хранятся в текущих документах. Их архив — только git history.
