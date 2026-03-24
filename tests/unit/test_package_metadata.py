from importlib import metadata


def test_package_exposes_console_script() -> None:
    entry_points = metadata.entry_points(group="console_scripts")
    matches = [ep for ep in entry_points if ep.name == "agrivision"]
    assert matches, "Expected agrivision console script to be registered."
