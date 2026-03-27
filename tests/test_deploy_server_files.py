from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_server_deploy_files_reflect_current_repo_contract() -> None:
    compose = _read("deploy/docker-compose.server.yml")
    deploy_readme = _read("deploy/README.md")
    env_example = _read(".env.example")

    assert "container_name: pct-api" in compose
    assert "container_name: pct-bot" in compose
    assert "container_name: pct-worker" in compose
    assert "external: true" in compose
    assert "name: ptfin-backend" in compose
    assert "env_file:" in compose
    assert "../.env" in compose
    assert "APP_DATA_MODE=file" in env_example
    assert "APP_PREVIEW_ENABLED=true" in env_example
    assert "cp .env.example .env" in deploy_readme
    assert "deploy/docker-compose.server.shared.yml" in deploy_readme
    assert "больше не считаются актуальным контрактом" in deploy_readme


def test_root_local_docker_artifacts_are_removed() -> None:
    assert not (PROJECT_ROOT / "docker-compose.yml").exists()
    assert not (PROJECT_ROOT / "deploy" / "env.server.example").exists()
