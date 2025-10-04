import sys

import pytest  # type: ignore[import]

from newsreader import main as main_module


@pytest.fixture(autouse=True)
def patch_environment(monkeypatch):
    """Keep CLI tests isolated from environment side effects."""

    monkeypatch.setattr(main_module, "setup_logging", lambda level: None)
    monkeypatch.setattr(main_module, "check_dependencies", lambda: True)
    yield


def test_main_invokes_daemon(monkeypatch):
    invoked = {}

    def fake_launch_daemon():
        invoked["daemon"] = True

    monkeypatch.setattr(main_module, "launch_daemon", fake_launch_daemon)
    monkeypatch.setattr(sys, "argv", ["main.py", "--daemon"])

    main_module.main()

    assert invoked.get("daemon") is True


def test_main_invokes_web(monkeypatch):
    captured = {}

    def fake_launch_web(*, host: str, port: int, debug: bool):
        captured["host"] = host
        captured["port"] = port
        captured["debug"] = debug

    monkeypatch.setattr(main_module, "launch_web", fake_launch_web)
    monkeypatch.setattr(sys, "argv", [
        "main.py",
        "--web",
        "--host",
        "127.0.0.5",
        "--port",
        "9012",
        "--debug",
    ])

    main_module.main()

    assert captured == {"host": "127.0.0.5", "port": 9012, "debug": True}
