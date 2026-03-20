# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-20
> Этот файл хранит только текущие findings и gate на следующий merge.

## Общий вывод

Базовый продукт работает, тестовый пакет проходит, но текущий staff rollout еще не готов к следующему merge как завершенный operator contour.

Причина теперь уже конкретная:
- остался один governance-блокер в staff edit flow: через drawer edit можно обойти защиту последнего активного администратора.

## Текущие findings

### [P1] Edit flow staff row обходит защиту последнего активного администратора

Через drawer-редактирование staff row нельзя допускать снятие роли `admin` у последнего активного администратора. Эта защита уже существует в отдельном revoke-flow и должна быть полностью повторена в update-flow.

## Что должно считаться готовностью следующего блока

Merge считается готовым только если одновременно выполнены все пункты:

1. все staff list/registry/queue screens работают через `AG Grid Community`;
2. `admin/staff` и `admin/authors` получили полноценный CRUD/edit flow;
3. `active/inactive` работает как action flow;
4. mutability rules по статусам enforced и отражены в UI;
5. onboarding нового `admin/author` больше не требует ручной пересылки invite link;
6. control emails администраторам одинаково работают в `db` и `file` mode;
7. UI статусы и labels переведены на русский;
8. edit flow не может обойти правило последнего активного администратора.

## Worker target

Следующий исполнитель должен брать как canonical source:
- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)

Исторические completed phases не использовать как источник правды.
