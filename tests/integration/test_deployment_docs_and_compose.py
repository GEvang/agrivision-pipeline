from pathlib import Path


def test_deployment_documentation_mentions_canonical_path() -> None:
    content = Path("DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "canonical deployment assets" in content.lower()
    assert "deployment/docker/" in content


def test_root_compose_points_to_same_image_family() -> None:
    root_compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    deployment_compose = Path("deployment/docker/docker-compose.yml").read_text(
        encoding="utf-8"
    )
    assert "image: agrivision-pipeline:phase5" in root_compose
    assert "image: agrivision-pipeline:phase5" in deployment_compose
