from pathlib import Path


def test_deployment_documentation_mentions_root_canonical_assets() -> None:
    content = Path("DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "canonical operational assets" in content.lower()
    assert "docker-compose.yml" in content
    assert "install_agrivision.sh" in content


def test_root_compose_uses_expected_image_family() -> None:
    root_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "image: agrivision-pipeline:local" in root_compose
