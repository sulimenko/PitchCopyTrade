from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from pitchcopytrade.db.models.accounts import Role, User
from pitchcopytrade.db.seeders.admin import seed_admin
from pitchcopytrade.db.seeders.instruments import resolve_instruments_seed_path


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSeederSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.insert_user_role_called = False
        self.committed = False

    async def execute(self, statement):
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if "FROM users JOIN user_roles" in compiled and "roles.slug = 'admin'" in compiled:
            return _ScalarResult(None)
        if "FROM roles" in compiled and "roles.slug = 'admin'" in compiled:
            return _ScalarResult(None)
        if "INSERT INTO user_roles" in compiled:
            self.insert_user_role_called = True
            return _ScalarResult(None)
        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, entity: object) -> None:
        if getattr(entity, "id", None) is None:
            if isinstance(entity, Role):
                entity.id = "role-admin"
            elif isinstance(entity, User):
                entity.id = "user-admin"
        self.added.append(entity)

    async def flush(self) -> None:
        for entity in self.added:
            if getattr(entity, "id", None) is None:
                if isinstance(entity, Role):
                    entity.id = "role-admin"
                elif isinstance(entity, User):
                    entity.id = "user-admin"

    async def commit(self) -> None:
        self.committed = True


def test_resolve_instruments_seed_path_from_storage_root(tmp_path: Path, monkeypatch) -> None:
    storage_root = tmp_path / "container-app" / "runtime-storage"
    seed_dir = storage_root / "seed" / "json"
    seed_dir.mkdir(parents=True)
    seed_file = seed_dir / "instruments.json"
    seed_file.write_text(json.dumps([{"ticker": "SBER"}]), encoding="utf-8")

    fake_settings = SimpleNamespace(
        storage=SimpleNamespace(
            seed_json_root=str(seed_dir),
            root=str(storage_root),
        )
    )
    monkeypatch.setattr("pitchcopytrade.db.seeders.instruments.get_settings", lambda: fake_settings)

    assert resolve_instruments_seed_path() == seed_file


async def test_seed_admin_uses_insert_instead_of_relationship_append() -> None:
    session = FakeSeederSession()

    created = await seed_admin(
        session,
        telegram_id=777001,
        email="admin@example.com",
    )

    assert created is True
    assert session.insert_user_role_called is True
    assert session.committed is True
