from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import MultipleResultsFound

from pitchcopytrade.api.lifespan import _run_seeders
from pitchcopytrade.db.models.accounts import Role, User
from pitchcopytrade.db.seeders.admin import seed_admin
from pitchcopytrade.db.seeders.instruments import resolve_instruments_seed_path


class _ScalarResult:
    def __init__(self, value=None, *, error: Exception | None = None) -> None:
        self._value = value
        self._error = error

    def scalar_one_or_none(self):
        if self._error is not None:
            raise self._error
        return self._value


class FakeSeederSession:
    def __init__(self, *, existing_admin_result=None, admin_role_result=None) -> None:
        self.added: list[object] = []
        self.insert_user_role_called = False
        self.committed = False
        self.closed = False
        self.existing_admin_result = existing_admin_result
        self.admin_role_result = admin_role_result

    async def execute(self, statement):
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if "FROM users JOIN user_roles" in compiled and "roles.slug = 'admin'" in compiled:
            return self._existing_admin_result(compiled)
        if "FROM roles" in compiled and "roles.slug = 'admin'" in compiled:
            return _ScalarResult(self.admin_role_result)
        if "INSERT INTO user_roles" in compiled:
            self.insert_user_role_called = True
            return _ScalarResult(None)
        raise AssertionError(f"Unexpected statement: {compiled}")

    def _existing_admin_result(self, compiled: str) -> _ScalarResult:
        return _ScalarResult(self.existing_admin_result)

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

    async def close(self) -> None:
        self.closed = True


class MultiAdminSeederSession(FakeSeederSession):
    def __init__(self) -> None:
        super().__init__(existing_admin_result="admin-user-1")

    def _existing_admin_result(self, compiled: str) -> _ScalarResult:
        if "LIMIT 1" not in compiled:
            return _ScalarResult(
                error=MultipleResultsFound("Multiple rows were found when one or none was required"),
            )
        return _ScalarResult(self.existing_admin_result)


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


async def test_seed_admin_skips_when_multiple_admins_already_exist() -> None:
    session = MultiAdminSeederSession()

    created = await seed_admin(
        session,
        telegram_id=777001,
        email="admin@example.com",
    )

    assert created is False
    assert session.added == []
    assert session.insert_user_role_called is False
    assert session.committed is False


@pytest.mark.asyncio
async def test_run_seeders_skips_admin_bootstrap_without_error_log_for_multi_admin_state(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    instrument_session = FakeSeederSession()
    admin_session = MultiAdminSeederSession()
    sessions = [instrument_session, admin_session]

    def session_factory():
        return sessions.pop(0)

    async def fake_seed_instruments(session) -> int:
        assert session is instrument_session
        return 0

    settings = SimpleNamespace(admin_telegram_id=777001, admin_email="admin@example.com")
    monkeypatch.setattr("pitchcopytrade.db.session.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("pitchcopytrade.db.seeders.instruments.seed_instruments", fake_seed_instruments)

    with caplog.at_level(logging.INFO):
        await _run_seeders(settings)

    messages = [record.getMessage() for record in caplog.records]

    assert instrument_session.closed is True
    assert admin_session.closed is True
    assert not any(record.levelno >= logging.ERROR for record in caplog.records if record.name == "pitchcopytrade.api.lifespan")
    assert not any("Admin seeder failed" in message for message in messages)
    assert not any("Multiple rows were found when one or none was required" in message for message in messages)
