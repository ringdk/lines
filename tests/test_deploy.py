"""lines-update against throwaway repositories: a light app deploys
main from your checkout as you, with no signing key, and never as root
(serafina/docs/APPS.md, "Light apps")."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
SH = shutil.which("dash") or shutil.which("sh")

pytestmark = pytest.mark.skipif(not (SH and shutil.which("git")), reason="needs a POSIX sh and git")


class Box:
    def __init__(self, tmp: Path, uid: str = "1000"):
        self.src = tmp / "src"
        self.dest = tmp / "opt" / "lines"
        for d in (self.dest, tmp / "pythons", tmp / "build"):
            d.mkdir(parents=True)
        gitconfig = tmp / "gitconfig"
        gitconfig.write_text("")
        self.env = {
            **os.environ,
            # The script's own tools (find, ls…) beside the shell, as they are
            # on astarte; on Windows that's Git's usr/bin.
            "PATH": os.pathsep.join([str(Path(SH).parent), os.environ["PATH"]]),
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
        }

        self.script = tmp / "lines-update"
        text = (DEPLOY / "lines-update").read_text()
        for old, new in [
            ("DEST=/opt/lines", f"DEST={self.dest.as_posix()}"),
            ("SRC=/home/danring/workspace/lines", f"SRC={self.src.as_posix()}"),
            ("LOCK=/home/danring/.cache/lines-update.lock", f"LOCK={(tmp / 'cache' / 'lock').as_posix()}"),
            ("PYTHONS=/opt/lines-python", f"PYTHONS={(tmp / 'pythons').as_posix()}"),
            ("UV=/usr/local/bin/uv", "UV=true"),
            ('"$(id -u)"', f'"{uid}"'),
            ('chmod -R a+rX "$PYTHONS" "$DEST/.venv"', "true"),
            ("mktemp -d /var/tmp/", f"mktemp -d {(tmp / 'build').as_posix()}/"),
            # A stand-in for the frontend build: what matters here is the gate.
            (
                "npm ci --ignore-scripts --no-audit --no-fund --loglevel=error && npm run --silent build",
                "mkdir -p dist && echo built > dist/index.html",
            ),
            # Never touch a real unit or the real deploy log, even on astarte.
            ("systemctl ", "false "),
            ("logger -t", "true -t"),
        ]:
            assert old in text, old
            text = text.replace(old, new)
        if not shutil.which("flock"):
            text = text.replace("flock -n 9", "true")
        self.script.write_text(text, newline="\n")

        self.src.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.src / "frontend").mkdir()
        (self.src / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (self.src / "frontend" / "package.json").write_text("{}\n")
        self.git("add", "pyproject.toml", "frontend/package.json")
        self.git("commit", "-q", "-m", "one")

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.ie", "-c", "commit.gpgsign=false", *args],
            cwd=cwd or self.src,
            check=True,
            capture_output=True,
            text=True,
            env=self.env,
        ).stdout.strip()

    def commit(self, message: str) -> str:
        (self.src / "change.txt").write_text(message)
        self.git("add", "change.txt")
        self.git("commit", "-q", "-m", message)
        return self.head()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def deployed(self) -> str:
        return self.git("rev-parse", "HEAD", cwd=self.dest)

    def deploy(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [SH, self.script.as_posix(), *args], capture_output=True, text=True, env=self.env, stdin=subprocess.DEVNULL
        )


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


def test_the_first_deploy_clones_and_builds(box):
    r = box.deploy()
    assert r.returncode == 0, r.stderr
    assert box.deployed() == box.head()
    assert (box.dest / "frontend" / "dist" / "index.html").is_file()


def test_later_deploys_take_main_without_a_key_or_a_question(box):
    box.deploy()
    two = box.commit("two")
    r = box.deploy()
    assert r.returncode == 0, r.stderr
    assert "two" in r.stdout
    assert box.deployed() == two

    # What `uv sync` would have made, so there's nothing left to build.
    program = box.dest / ".venv" / "bin" / "lines"
    program.parent.mkdir(parents=True)
    program.write_text("#!/bin/sh\n")
    program.chmod(0o755)
    assert "Already up to date" in box.deploy().stdout


def test_it_deploys_main_whatever_your_checkout_has_out(box):
    box.deploy()
    two = box.commit("two")
    box.git("checkout", "-q", "-b", "side")
    box.commit("unfinished")
    assert box.deploy().returncode == 0
    assert box.deployed() == two


def test_it_never_runs_as_root(tmp_path):
    box = Box(tmp_path, uid="0")
    r = box.deploy()
    assert r.returncode == 1
    assert "not with sudo" in r.stderr
    assert not (box.dest / ".git").exists()


def test_it_only_moves_forward(box):
    box.deploy()
    two = box.commit("two")
    assert box.deploy().returncode == 0

    box.git("reset", "-q", "--hard", "HEAD~1")
    box.commit("another two")
    r = box.deploy()
    assert r.returncode == 1
    assert "no longer follows" in r.stderr
    assert box.deployed() == two


def test_it_wont_deploy_over_changes_made_by_hand(box):
    box.deploy()
    one = box.deployed()
    (box.dest / "pyproject.toml").write_text("[project]\nname = 'edited'\n")
    box.commit("two")
    r = box.deploy()
    assert r.returncode == 1
    assert "changes made by hand" in r.stderr
    assert box.deployed() == one


def test_it_wont_clone_over_something_else(box):
    (box.dest / "stray").write_text("x")
    r = box.deploy()
    assert r.returncode == 1
    assert not (box.dest / ".git").exists()


def test_it_takes_no_arguments(box):
    for args in [("--signed",), ("/home/someone/else",), ("--yes",)]:
        assert box.deploy(*args).returncode == 2, args
    assert not (box.dest / ".git").exists()


def rules(name: str) -> list[str]:
    text = (DEPLOY / name).read_text()
    return [line for line in text.splitlines() if line.strip() and not line.startswith("#")]


def test_the_one_sudo_rule_is_a_restart():
    assert rules("lines-reload.sudoers") == [
        "danring ALL=(root) NOPASSWD: /usr/bin/systemctl restart lines.service"
    ]
    # A light app has no signed deploys, so nothing to allow or trust for them.
    assert not (DEPLOY / "lines-deploy.sudoers").exists()
    assert not (DEPLOY / "allowed_signers").exists()


def test_the_unit_runs_as_its_own_user_on_loopback_hardened():
    unit = (DEPLOY / "lines.service").read_text()
    for line in [
        "User=lines",
        "WorkingDirectory=/opt/lines",
        "StateDirectoryMode=0700",
        "LoadCredential=passphrase:/etc/lines/passphrase",
        "IPAddressAllow=localhost",
        "SocketBindAllow=tcp:8795",
        "ProtectSystem=strict",
        "ProtectHome=yes",
        "NoNewPrivileges=yes",
        "CapabilityBoundingSet=",
        "SystemCallFilter=@system-service",
    ]:
        assert f"\n{line}\n" in unit, line
    assert "Environment=LINES_AGE_PASSPHRASE" not in unit
