from pathlib import Path


def test_env_template_exists():
    assert Path('.env.example').exists()
