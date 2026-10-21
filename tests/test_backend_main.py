"""The backend's start: what it tells systemd, and what it leaves for the frontend when it stops."""

import socket
import tempfile
from pathlib import Path

import backend.__main__ as main


def test_systemd_hears_ready_and_the_watchdog(monkeypatch):
    # a short path: unix socket paths are limited to about 100 characters
    address = str(Path(tempfile.mkdtemp(prefix="sd", dir="/tmp")) / "notify")
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as systemd:
        systemd.bind(address)
        monkeypatch.setenv("NOTIFY_SOCKET", address)
        main.notify_systemd("READY=1")
        main.notify_systemd("WATCHDOG=1")
        assert systemd.recv(64) == b"READY=1"
        assert systemd.recv(64) == b"WATCHDOG=1"


def test_without_systemd_nothing_is_sent(monkeypatch):
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    main.notify_systemd("WATCHDOG=1")  # no socket to send to: just returns


def test_the_reason_of_a_failure_is_left_for_the_frontend(monkeypatch, tmp_path):
    error_file = tmp_path / "var" / "backend-error.txt"
    monkeypatch.setattr(main, "BACKEND_ERROR_FILE", error_file)
    main.report_failure(OSError("can0: No such device"))
    assert error_file.read_text() == "OSError: can0: No such device"
