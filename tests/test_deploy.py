"""lines-update against a throwaway checkout, and the units: a light app
runs as you, from your checkout, under your own systemd, and nothing about
it needs root (serafina/docs/APPS.md, "Light apps")."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
DOCS = Path(__file__).resolve().parents[1] / "docs"
SH = shutil.which("dash") or shutil.which("sh")

needs_sh = pytest.mark.skipif(not (SH and shutil.which("git")), reason="needs a POSIX sh and git")


class Box:
    def __init__(self, tmp: Path, uid: str = "1000", build: str = "mkdir -p dist && echo built > dist/index.html"):
        self.app = tmp / "workspace" / "lines"
        self.app.mkdir(parents=True)
        gitconfig = tmp / "gitconfig"
        gitconfig.write_text("")
        self.env = {
            **os.environ,
            # The script's own tools (find, flock…) beside the shell, as they
            # are on astarte; on Windows that's Git's usr/bin.
            "PATH": os.pathsep.join([str(Path(SH).parent), os.environ["PATH"]]),
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self.script = tmp / "lines-update"
        text = (DEPLOY / "lines-update").read_text()
        for old, new in [
            ('APP="$HOME/workspace/lines"', f'APP="{self.app.as_posix()}"'),
            ('LOCK="$HOME/.cache/lines-update.lock"', f'LOCK="{(tmp / "cache" / "lock").as_posix()}"'),
            ("UV=/usr/local/bin/uv", "UV=true"),
            ('"$(id -u)"', f'"{uid}"'),
            # A stand-in for the frontend build: what matters here is the gate.
            ("npm ci --ignore-scripts --no-audit --no-fund --loglevel=error && npm run --silent build", build),
            # Never touch a real unit or the real log, even on astarte.
            ("systemctl --user is-enabled", "false"),
            ("logger -t", "true -t"),
        ]:
            assert old in text, old
            text = text.replace(old, new)
        if not shutil.which("flock"):
            text = text.replace("flock -n 9", "true")
        self.script.write_text(text, newline="\n")

        self.git("init", "-q", "-b", "main")
        (self.app / "frontend").mkdir()
        (self.app / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (self.app / "frontend" / "package.json").write_text("{}\n")
        self.git("add", "pyproject.toml", "frontend/package.json")
        self.git("commit", "-q", "-m", "one")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.ie", "-c", "commit.gpgsign=false", *args],
            cwd=self.app,
            check=True,
            capture_output=True,
            text=True,
            env=self.env,
        ).stdout.strip()

    def deploy(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [SH, self.script.as_posix(), *args], capture_output=True, text=True, env=self.env, stdin=subprocess.DEVNULL
        )


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


@needs_sh
def test_it_builds_main_as_checked_out(box):
    r = box.deploy()
    assert r.returncode == 0, r.stderr
    assert (box.app / "frontend" / "dist" / "index.html").is_file()
    assert "isn't enabled yet" in r.stdout


@needs_sh
def test_it_never_runs_as_root(tmp_path):
    box = Box(tmp_path, uid="0")
    r = box.deploy()
    assert r.returncode == 1 and "never root's" in r.stderr
    assert not (box.app / "frontend" / "dist").exists()


@needs_sh
def test_it_deploys_only_main(box):
    box.git("checkout", "-q", "-b", "side")
    r = box.deploy()
    assert r.returncode == 1 and "only main" in r.stderr
    assert not (box.app / "frontend" / "dist").exists()


@needs_sh
def test_it_wont_deploy_what_isnt_committed(box):
    (box.app / "pyproject.toml").write_text("[project]\nname = 'edited'\n")
    r = box.deploy()
    assert r.returncode == 1 and "aren't committed" in r.stderr


@needs_sh
def test_a_build_that_leaves_no_page_is_refused(tmp_path):
    box = Box(tmp_path, build="mkdir -p dist")
    r = box.deploy()
    assert r.returncode == 1 and "no page" in r.stderr


@needs_sh
def test_it_takes_no_arguments(box):
    for args in [("--signed",), ("/home/someone/else",), ("--yes",)]:
        assert box.deploy(*args).returncode == 2, args


def test_nothing_about_it_needs_root():
    names = {p.name for p in DEPLOY.iterdir()}
    # No system user to administer, no restart rule, no signed deploys.
    assert not {"lines-admin", "lines-reload.sudoers", "lines-deploy.sudoers", "allowed_signers"} & names
    for path in [*DEPLOY.iterdir(), DOCS / "deploy-astarte.md"]:
        text = path.read_text()
        assert not re.search(r"^\s*(?:\(.*;\s*)?sudo\s", text, re.M), path.name
        assert "/etc/lines" not in text and "/opt/lines" not in text, path.name


def test_the_units_are_yours_and_run_from_the_checkout():
    unit = (DEPLOY / "lines.service").read_text()
    for line in [
        "EnvironmentFile=%h/.config/lines/env",
        "WorkingDirectory=%h/workspace/lines",
        "ExecStart=%h/workspace/lines/.venv/bin/lines serve",
        "NoNewPrivileges=yes",
        "SystemCallFilter=@system-service",
        "WantedBy=default.target",
    ]:
        assert f"\n{line}\n" in unit, line
    backup = (DEPLOY / "lines-backup.service").read_text()
    assert "\nExecStart=%h/workspace/lines/.venv/bin/lines backup /mnt/media/lines-backup\n" in backup
    for text in (unit, backup):
        assert not re.search(r"^(User|Group|LoadCredential)=", text, re.M)


def test_its_settings_file_holds_the_passphrase_and_nothing_else_secret():
    example = (DEPLOY / "lines.env.example").read_text()
    assert re.search(r"^LINES_AGE_PASSPHRASE=$", example, re.M)
    assert re.search(r"^LINES_DATA_DIR=/home/danring/\.local/share/lines$", example, re.M)
