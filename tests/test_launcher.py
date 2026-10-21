"""The ./handcart.py launcher (standard library only, so loaded from its path)."""

import importlib.util

import pytest

from shared.config import ROOT, UPDATE_STEP_FILE


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("launcher", ROOT / "handcart.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "UPDATE_STEP", tmp_path / "update-step.txt")
    return module


def test_the_step_file_is_the_one_the_display_reads(launcher):
    spec = importlib.util.spec_from_file_location("fresh", ROOT / "handcart.py")
    assert spec is not None and spec.loader is not None
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    assert fresh.UPDATE_STEP == UPDATE_STEP_FILE


def test_the_display_stops_showing_the_update_however_it_ends(launcher, monkeypatch):
    def broken_update() -> int:
        launcher.step("Installing abc1234")
        assert launcher.UPDATE_STEP.read_text() == "Installing abc1234"
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(launcher, "update_steps", broken_update)
    with pytest.raises(RuntimeError):
        launcher.update([])
    assert not launcher.UPDATE_STEP.exists()  # else the display would say "Updating" for ever


class FakeUpdate:
    """The update with git and the services faked: what it installed, restarted and left for the display."""

    def __init__(self, launcher, monkeypatch, tmp_path, changed_files: list[str]) -> None:
        self.installed: list[bool] = []  # one per install_services call: with the splash or not
        self.restarted: list[bool] = []  # one per restart: with the display or not

        def output(cmd: list[str]) -> str:
            if "diff" in cmd:
                return "\n".join(changed_files)
            if cmd[-1] == "HEAD":
                return "aaa1111"
            if "rev-parse" in cmd:
                return "bbb2222"
            return ""  # git status: no local changes

        def install_services(splash: bool = True) -> int:
            self.installed.append(splash)
            return 0

        def restart(timeout: float, display: bool = False) -> None:
            self.restarted.append(display)

        monkeypatch.setattr(launcher, "LAST_UPDATE", tmp_path / "last-update.txt")
        monkeypatch.setattr(launcher, "backend_state", lambda: None)
        monkeypatch.setattr(launcher, "output", output)
        monkeypatch.setattr(launcher, "run", lambda *args, **kwargs: 0)
        monkeypatch.setattr(launcher, "install", lambda commit: None)
        monkeypatch.setattr(launcher, "tests", lambda: None)
        monkeypatch.setattr(launcher, "install_services", install_services)
        monkeypatch.setattr(launcher, "restart", restart)
        assert launcher.update([]) == 0
        self.result = launcher.LAST_UPDATE.read_text()


def test_changed_services_are_installed_by_the_update(launcher, monkeypatch, tmp_path):
    update = FakeUpdate(launcher, monkeypatch, tmp_path, ["system/services/handcart-backend.service"])
    assert update.installed == [False]  # no splash: it did not change, and rebuilding it takes minutes
    assert update.restarted == [True]  # with the display, which may have changed too
    assert "by hand" not in update.result  # nothing left to do: no note on the display


def test_a_changed_splash_is_rebuilt(launcher, monkeypatch, tmp_path):
    update = FakeUpdate(launcher, monkeypatch, tmp_path, ["system/splash/handcart.script"])
    assert update.installed == [True]


def test_only_code_changes_install_nothing(launcher, monkeypatch, tmp_path):
    update = FakeUpdate(launcher, monkeypatch, tmp_path, ["src/backend/handcart.py"])
    assert update.installed == []
    assert update.restarted == [False]
    assert update.result.endswith("Updated aaa1111 -> bbb2222\n")


def test_changed_boot_files_are_left_to_do_by_hand(launcher, monkeypatch, tmp_path):
    update = FakeUpdate(launcher, monkeypatch, tmp_path, ["system/raspberry/cmdline.txt"])
    assert update.installed == []  # never installed by the update: a broken cmdline.txt stops the Pi
    assert "by hand" in update.result  # the display shows it as a note to act on
