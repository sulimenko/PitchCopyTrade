# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-20
> Этот файл хранит только текущие findings и gate на следующий merge.

## Общий вывод

Базовый продукт работает, текущий governance blocker по `admin/authors` закрыт, и staff rollout больше не имеет открытых edit-flow обходов для последнего активного администратора.

## Текущие findings

- Активных governance findings на текущий момент нет.

## Что должно считаться готовностью следующего блока

Merge считается готовым только если одновременно выполнены все пункты:

1. все staff list/registry/queue screens работают через `AG Grid Community`;
2. `admin/staff` и `admin/authors` получили полноценный CRUD/edit flow;
3. `active/inactive` работает как action flow;
4. mutability rules по статусам enforced и отражены в UI;
5. onboarding нового `admin/author` больше не требует ручной пересылки invite link;
6. control emails администраторам одинаково работают в `db` и `file` mode;
7. UI статусы и labels переведены на русский;
8. ни один edit flow не может обойти правило последнего активного администратора.

## Worker target

Следующий исполнитель должен брать как canonical source:
- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)

Исторические completed phases не использовать как источник правды.

## Next UX block

Следующий приоритет после закрытия текущего governance gate:
- runtime resilience для Telegram bot;
- deploy troubleshooting и smoke-check для connectivity к `api.telegram.org`;
- автоматическое восстановление polling после временных сетевых ошибок.

Следующий staff UX/onboarding block после этого:
- fallback path для `/login?invite_token=...`, если Telegram widget не отрисовался;
- deep-link / copy / resend сценарий вместо серого placeholder;
- unclipped row menus в staff registries;
- убрать raw invite URL из primary cell в `/admin/staff`.
