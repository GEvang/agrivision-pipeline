from __future__ import annotations

import io
import sys
import threading

from agrivision.services.run_logging import thread_output_to


def test_each_thread_writes_only_to_its_own_log() -> None:
    logs = {name: io.StringIO() for name in ("a", "b")}
    ready = threading.Barrier(2)

    def worker(name: str) -> None:
        with thread_output_to(logs[name]):
            ready.wait()
            for _ in range(50):
                print(f"line from {name}")

    threads = [threading.Thread(target=worker, args=(name,)) for name in logs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert logs["a"].getvalue().count("line from a") == 50
    assert "line from b" not in logs["a"].getvalue()
    assert logs["b"].getvalue().count("line from b") == 50
    assert "line from a" not in logs["b"].getvalue()


def test_output_outside_a_run_is_not_captured() -> None:
    log = io.StringIO()
    with thread_output_to(log):
        pass

    print("dashboard output", file=sys.stdout)

    assert log.getvalue() == ""


def test_pipeline_log_lines_follow_the_routed_stream() -> None:
    from agrivision.pipeline import orchestrator

    log = io.StringIO()
    with thread_output_to(log):
        orchestrator.logger.info("stage message")

    assert log.getvalue() == "stage message\n"
