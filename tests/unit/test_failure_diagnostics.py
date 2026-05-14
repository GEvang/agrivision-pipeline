from agrivision.services.failure_diagnostics import summarize_failure


def test_summarize_odm_container_start_failure() -> None:
    summary = summarize_failure("ODM-RGB failed with exit code 125. Docker mount args were -v data:/datasets.")

    assert "could not start" in summary
    assert "Docker" in summary


def test_summarize_odm_resource_failure() -> None:
    summary = summarize_failure("ODM-MAPIR failed with exit code 137. Docker mount args were -v data:/datasets.")

    assert "ran out of memory" in summary
    assert "MAPIR" in summary


def test_summarize_odm_reconstruction_crash() -> None:
    summary = summarize_failure("ODM-RGB failed with exit code 139. Docker mount args were --volumes-from app.")

    assert "crashed during reconstruction" in summary
    assert "RGB" in summary


def test_summarize_missing_compose() -> None:
    summary = summarize_failure("Docker Compose was not found on PATH.")

    assert summary == "Docker Compose was not found. Install Docker Desktop or make sure Docker is available on PATH."


def test_summarize_service_timeout() -> None:
    summary = summarize_failure(
        "Service in /workspace/OpenAgri-IrrigationManagement did not become reachable. "
        "Checked: http://host.docker.internal:8004/openapi.json"
    )

    assert "External service did not become reachable" in summary
    assert "OpenAgri-IrrigationManagement" in summary


def test_summarize_preview_dtype_failure() -> None:
    summary = summarize_failure("TypeError: Cannot convert fill_value nan to dtype uint8")

    assert "Preview generation failed" in summary
