import run


def test_run_module_exposes_main():
    assert hasattr(run, "main")
    assert callable(run.main)


def test_run_module_exposes_load_local_env():
    assert hasattr(run, "load_local_env")
    assert callable(run.load_local_env)