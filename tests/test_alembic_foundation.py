from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_alembic_env_targets_metadata() -> None:
    env_contents = (ROOT / "alembic" / "env.py").read_text()

    assert "target_metadata = Base.metadata" in env_contents
    assert "compare_server_default" in env_contents
    assert "settings.database.alembic_url" in env_contents


def test_alembic_offline_upgrade_sql_smoke() -> None:
    result = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "alembic"), "upgrade", "head", "--sql"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE lead_sources" in result.stdout
    assert "CREATE TABLE subscriptions" in result.stdout
    assert "CREATE TABLE recommendation_attachments" in result.stdout
