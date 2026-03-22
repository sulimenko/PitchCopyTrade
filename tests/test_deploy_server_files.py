from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_server_compose_base_supports_standalone_proxy_setup() -> None:
    compose = _read("deploy/docker-compose.server.yml")
    env_example = _read("deploy/env.server.example")

    assert "host.docker.internal:host-gateway" in compose
    assert "--proxy-headers" in compose
    assert "--forwarded-allow-ips='*'" in compose
    assert "API_PORT_BINDING" in compose
    assert "DOCKER_NETWORK_NAME" in compose
    assert "API_PORT_BINDING=127.0.0.1:8110:8000" in env_example


def test_server_compose_shared_override_supports_external_network_aliases() -> None:
    shared_compose = _read("deploy/docker-compose.server.shared.yml")
    env_example = _read("deploy/env.server.example")
    deploy_readme = _read("deploy/README.md")

    assert "external: true" in shared_compose
    assert "API_ALIAS" in shared_compose
    assert "BOT_ALIAS" in shared_compose
    assert "WORKER_ALIAS" in shared_compose
    assert "DOCKER_NETWORK_EXTERNAL=true" in env_example
    assert "docker-compose.server.shared.yml" in deploy_readme
