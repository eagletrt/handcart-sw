"""Updates of the handcart repo, against real git repos in a temporary folder."""

import subprocess

import pytest

from backend.system import System
from shared.config import Update


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def commit(repo, message):
    (repo / "file.txt").write_text(message)
    git(repo, "add", "file.txt")
    git(repo, "-c", "user.name=test", "-c", "user.email=test@test", "commit", "-m", message)
    git(repo, "push", "--quiet", "origin", "HEAD:main")


@pytest.fixture
def repos(tmp_path):
    """(a developer's clone, the handcart's clone) of the same remote."""
    remote, developer, handcart = tmp_path / "remote.git", tmp_path / "developer", tmp_path / "handcart"
    subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", remote], check=True)
    subprocess.run(["git", "clone", "--quiet", remote, developer], check=True, capture_output=True)
    commit(developer, "feat: first")
    subprocess.run(["git", "clone", "--quiet", remote, handcart], check=True, capture_output=True)
    return developer, handcart


@pytest.fixture
def system(repos):
    return System(Update(remote="origin", branch="main", health_timeout=1), repo=repos[1])


def test_not_checked_yet(system):
    assert system.info().checked_at is None


def test_up_to_date(system):
    system.check()
    info = system.info()
    assert info.updates == []
    assert info.check_problem is None
    assert info.checked_at  # "12:23"
    assert info.version  # "abc1234 2026-10-21"


def test_new_commits_on_the_branch_are_updates(system, repos):
    developer, _ = repos
    commit(developer, "fix: second")
    commit(developer, "feat: third")
    system.check()
    updates = system.info().updates
    assert [line.split(" ", 1)[1] for line in updates] == ["feat: third", "fix: second"]  # newest first


def test_no_network_is_a_problem_not_an_error(system, repos):
    git(repos[1], "remote", "set-url", "origin", "/nowhere")
    system.check()
    assert "Could not reach origin" in system.info().check_problem


def test_nothing_to_update(system):
    system.check()
    assert system.start_update() == "Already up to date"


def test_update_reboot_and_shut_down_only_on_the_handcart(system, repos):
    commit(repos[0], "feat: new")
    system.check()
    assert "Only on the handcart" in system.start_update()
    assert "Only on the handcart" in system.reboot()
    assert "Only on the handcart" in system.shut_down()


def test_a_branch_missing_on_the_remote_is_said_so(repos):
    system = System(Update(remote="origin", branch="renamed", health_timeout=1), repo=repos[1])
    system.check()
    assert system.info().check_problem == "The branch renamed is not on origin"
