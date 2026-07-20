from pathlib import Path


def test_deployment_documentation_mentions_root_assets() -> None:
    content = Path("DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "docker-compose.yml" in content
    assert "Start AgriVision Windows.bat" in content


def test_root_compose_points_to_expected_image_family() -> None:
    root_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "image: agrivision-pipeline:phase5" in root_compose
    assert "dockerfile: Dockerfile" in root_compose
