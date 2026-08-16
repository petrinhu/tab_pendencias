"""tests/test_session_hook_adapter.py -- adapter Claude-Code (TAB-HOOK-001..004).

Fail-open, exit 0, emite TRIAGE quando ha classifiable. Sem regra de negocio
propria (so wiring para session_signals).
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys

from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
HOOKS_DIR = os.path.join(TOOLS_DIR, "hooks")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import tab_pendencias_reminder as hook  # noqa: E402
import session_signals as SS  # noqa: E402

NOW = datetime.date(2026, 8, 16)

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

_HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=_ENV, capture_output=True,
                   check=True)


def _repo_with_classifiable(tmp_path):
    _git_init_isolado(tmp_path)
    texto = (
        _HEADER_9
        + "| H-1 | W1 | G | d | Média | — | Baixa | ⏳ Pendente | — |\n"
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- C-1: bare discovery\n"
    )
    (tmp_path / "TODO.md").write_text(texto, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    return tmp_path


def test_parse_hook_stdin_invalid_uses_getcwd():
    data = hook.parse_hook_stdin("not-json{{{")
    assert "cwd" in data
    assert os.path.isdir(data["cwd"])


def test_parse_hook_stdin_empty_uses_getcwd():
    data = hook.parse_hook_stdin("")
    assert os.path.isdir(data["cwd"])


def test_parse_hook_stdin_none_uses_getcwd():
    data = hook.parse_hook_stdin(None)
    assert os.path.isdir(data["cwd"])


def test_parse_hook_stdin_respects_cwd(tmp_path):
    payload = json.dumps({"cwd": str(tmp_path), "hook_event_name": "SessionStart"})
    data = hook.parse_hook_stdin(payload)
    assert data["cwd"] == str(tmp_path)


def test_run_hook_fail_open_continue_true():
    out = hook.run_hook("{not json")
    assert out.get("continue") is True


def test_run_hook_emits_triage(tmp_path):
    root = _repo_with_classifiable(tmp_path)
    payload = json.dumps({"cwd": str(root)})
    out = hook.run_hook(payload, now=NOW)
    assert out["continue"] is True
    ctx = out.get("additionalContext") or ""
    assert "TAB_TRIAGE_REQUIRED" in ctx


def test_run_hook_cli_exit_zero(tmp_path):
    root = _repo_with_classifiable(tmp_path)
    script = os.path.join(HOOKS_DIR, "tab_pendencias_reminder.py")
    r = subprocess.run(
        [sys.executable, script],
        cwd=str(root),
        input=json.dumps({"cwd": str(root)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout.strip())
    assert data["continue"] is True
    assert "TAB_TRIAGE_REQUIRED" in (data.get("additionalContext") or "")


def test_adapter_has_no_business_predicates():
    """Adapter so faz wiring -- predicados de aging/sync nao moram nele."""
    path = os.path.join(HOOKS_DIR, "tab_pendencias_reminder.py")
    src = open(path, encoding="utf-8").read()
    for term in (
        "residual_is_aged",
        "triage_max_cycles",
        "FULL_REORDER",
        "run_intake",
        "wsjf",
        "openai",
    ):
        assert term not in src, term
    assert "collect_signals" in src
