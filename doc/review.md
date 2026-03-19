# PitchCopyTrade — Current Review Gate
> Обновлено: 2026-03-20
> Этот файл хранит только текущие findings и gate на следующий merge.

## Общий вывод

Базовый продукт работает, но следующий staff rollout еще не готов к выкладке как финальный operator contour.

Причина не в core backend, а в UI/governance gaps:
- staff shell слишком похож на public UI;
- grid layer не унифицирован;
- existing staff rows нельзя полноценно править в одном CRUD pattern;
- onboarding нового `admin/author` все еще слишком ручной;
- язык интерфейса еще не везде приведен к русскому.

## Текущие findings

### [P1] Staff shell не соответствует operator-first contract

Сейчас staff UI держится на больших кнопках и разрозненных topbar actions. Для `admin`, `author`, `moderation` нужен отдельный compact shell:
- left rail
- breadcrumb
- `back`
- compact actions
- role switch

### [P1] Нет единого grid language

Списки уже частично табличные, но это разные handcrafted HTML tables. Канонический следующий слой должен быть один: `AG Grid Community`.

### [P1] Existing staff records недостаточно редактируемы

Создание `admin/author` уже есть, но existing rows нельзя полноценно править через единый CRUD flow. Особенно это критично для:
- `admin/staff`
- `admin/authors`

### [P1] Mutability rules не собраны в единый enforceable contract

Сущности уже имеют статусные переходы, но для следующего UI нужно явно enforce:
- recommendations editable только в `draft`, `review`
- strategies editable только в `draft`
- payments editable/actionable только в `created`, `pending`
- subscriptions только через допустимые actions
- legal active version read-only

### [P1] Staff onboarding слишком ручной

Текущий flow требует ручной пересылки invite link оператором. Это не считается приемлемым canonical path.

Нужен contract:
- create `display_name + email + roles`
- send invite email automatically
- registry показывает `sent / failed / resent`
- resend инвалидирует старые invite links
- все активные admin получают контрольные письма о создании `admin/author` и о failed delivery

### [P2] Русский язык еще не доведен как жесткий UI contract

Все видимые labels и статусы должны быть русскими. Английские значения допустимы только в коде и БД.

## Что должно считаться готовностью следующего блока

Merge считается готовым только если одновременно выполнены все пункты:

1. staff shell переведен на compact operator-first layout;
2. все staff list/registry/queue screens работают через `AG Grid Community`;
3. `admin/staff` и `admin/authors` получили полноценный CRUD/edit flow;
4. mutability rules по статусам enforced и отражены в UI;
5. onboarding нового `admin/author` больше не требует ручной пересылки invite link;
6. UI статусы и labels переведены на русский.

## Worker target

Следующий исполнитель должен брать как canonical source:
- [doc/blueprint.md](/Users/alexey/site/PitchCopyTrade/doc/blueprint.md)
- [doc/task.md](/Users/alexey/site/PitchCopyTrade/doc/task.md)

Исторические completed phases не использовать как источник правды.
