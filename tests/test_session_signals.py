"""tests/test_session_signals.py -- Fase 6 motor de sinais + aging (INTAKE-AGE-1).

Relogio injetado: now=date(2026, 8, 16). Grep-guard: session_signals nao
importa run_intake / FULL_REORDER / wsjf / openai / urllib.
"""
from __future__ import annotations

import ast
import datetime
import os
import subprocess
import sys
import time

import pytest

from conftest import git_init_isolado as _git_init_isolado
import session_signals as SS
import todo_lib as L

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
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


def _row(iid, status):
    return (f"| {iid} | W1 | Grupo | Descrição | Média | — | Baixa | "
            f"{status} | — |\n")


def _repo(tmp_path, todo_text, extra_commits=0):
    _git_init_isolado(tmp_path)
    (tmp_path / "TODO.md").write_text(todo_text, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    for i in range(extra_commits):
        p = tmp_path / f"f{i}.txt"
        p.write_text("x", encoding="utf-8")
        _git(tmp_path, "add", f"f{i}.txt")
        _git(tmp_path, "commit", "-qm", f"c{i}")
    return tmp_path


def _meta(since, reason, cycles=0):
    return L.format_triage_metadata(
        since=since, reason=reason, cycles=cycles
    )


# ---------------------------------------------------------------------------
# residual_is_aged (todo_lib)
# ---------------------------------------------------------------------------

def test_residual_aged_by_cycles():
    desc = _meta("2026-08-16", "missing-info", cycles=2) + "x"
    e = L.inbox_entries(f"## INBOX\n- R-1: {desc}\n")[0]
    assert L.residual_is_aged(e, now=NOW, max_cycles=2, max_age_days=1) is True
    assert L.residual_is_aged(e, now=NOW, max_cycles=3, max_age_days=99) is False


def test_residual_aged_by_age_days():
    desc = _meta("2026-08-14", "missing-info", cycles=0) + "x"
    e = L.inbox_entries(f"## INBOX\n- R-1: {desc}\n")[0]
    # age = 2 dias >= 1
    assert L.residual_is_aged(e, now=NOW, max_cycles=99, max_age_days=1) is True
    # limiar alto
    assert L.residual_is_aged(e, now=NOW, max_cycles=99, max_age_days=10) is False


def test_residual_fresh_today_not_aged():
    desc = _meta("2026-08-16", "needs-leader-decision", cycles=0) + "wait"
    e = L.inbox_entries(f"## INBOX\n- L-1: {desc}\n")[0]
    assert L.residual_is_aged(e, now=NOW) is False


def test_classifiable_never_aged():
    e = L.inbox_entries("## INBOX\n- bare discovery\n")[0]
    assert e["classifiable"] is True
    assert L.residual_is_aged(e, now=NOW) is False


def test_load_signals_config_defaults_and_ini(tmp_path):
    assert L.load_signals_config(None)["triage_max_cycles"] == 2
    todo = tmp_path / "TODO.md"
    todo.write_text("x", encoding="utf-8")
    cfg = L.load_signals_config(str(todo))
    assert cfg["status_sync_min_commits"] == 5
    (tmp_path / ".tab_pendencias.ini").write_text(
        "[signals]\ntriage_max_cycles = 4\nstatus_sync_min_days = 9\n",
        encoding="utf-8",
    )
    cfg2 = L.load_signals_config(str(todo))
    assert cfg2["triage_max_cycles"] == 4
    assert cfg2["status_sync_min_days"] == 9
    assert cfg2["triage_max_age_days"] == 1  # default preservado


# ---------------------------------------------------------------------------
# Predicados collect_signals
# ---------------------------------------------------------------------------

def test_five_leader_new_no_triage_no_leader_aged(tmp_path):
    """5 leader novos cycles=0 since=hoje -> TRIAGE False, LEADER_AGED False."""
    lines = []
    for i in range(5):
        m = _meta("2026-08-16", "needs-leader-decision", cycles=0)
        lines.append(f"- L-{i}: {m}wait leader\n")
    texto = (
        _HEADER_9 + _row("H-1", "⏳ Pendente")
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "".join(lines)
    )
    root = _repo(tmp_path, texto)
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_TRIAGE_REQUIRED") is False
    assert rep.is_active("TAB_LEADER_DECISION_AGED") is False
    assert rep.metrics["needs_leader_count"] == 5
    assert rep.metrics["inbox_count"] == 5


def test_one_leader_aged_fires_leader_and_triage(tmp_path):
    """1 leader aged (since antigo) -> LEADER_AGED + TRIAGE."""
    m = _meta("2026-08-01", "needs-leader-decision", cycles=0)
    texto = (
        _HEADER_9 + _row("H-1", "⏳ Pendente")
        + "\n## INBOX (descobertas não priorizadas)\n"
        + f"- L-1: {m}wait\n"
    )
    root = _repo(tmp_path, texto)
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_LEADER_DECISION_AGED") is True
    assert rep.is_active("TAB_TRIAGE_REQUIRED") is True
    assert "aged_residual" in ",".join(rep.by_id("TAB_TRIAGE_REQUIRED").reasons)


def test_create_required_git_sem_todo(tmp_path):
    _git_init_isolado(tmp_path)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-qm", "init")
    rep = SS.collect_signals(str(tmp_path), now=NOW)
    assert rep.is_active("TAB_TODO_CREATE_REQUIRED") is True


def test_status_sync_recommended(tmp_path):
    texto = _HEADER_9 + _row("H-1", "⏳ Pendente")
    root = _repo(tmp_path, texto, extra_commits=5)
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.metrics["commits_since_todo_touch"] == 5
    assert rep.is_active("TAB_STATUS_SYNC_RECOMMENDED") is True


def test_status_sync_silent_without_pending_work(tmp_path):
    texto = _HEADER_9 + _row("H-1", "✅ Concluído")
    root = _repo(tmp_path, texto, extra_commits=5)
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_STATUS_SYNC_RECOMMENDED") is False


def test_verification_aging_by_count(tmp_path):
    linhas = [_row(f"V-{i}", "🔍 Pendente verificação") for i in range(5)]
    texto = _HEADER_9 + "".join(linhas)
    root = _repo(tmp_path, texto)
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_VERIFICATION_AGING") is True
    assert rep.metrics["n_verif"] == 5


def test_verification_aging_by_days(tmp_path):
    texto = _HEADER_9 + _row("V-1", "🔍 Pendente verificação")
    root = _repo(tmp_path, texto)
    # força days_since_todo_touch alto via now_ts distante do commit
    future_ts = time.time() + 10 * 86400
    rep = SS.collect_signals(str(root), now=NOW, now_ts=future_ts)
    assert rep.metrics["n_verif"] == 1
    assert rep.metrics["days_since_todo_touch"] >= 7
    assert rep.is_active("TAB_VERIFICATION_AGING") is True


def test_recovery_required_journal_orphan(tmp_path):
    import intake_journal as J

    texto = _HEADER_9 + _row("H-1", "⏳ Pendente")
    root = _repo(tmp_path, texto)
    J.write_candidate(
        candidate_id="orphan-1",
        description="lost mid-intake",
        source="agent",
        cwd=str(root),
    )
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_INTAKE_RECOVERY_REQUIRED") is True
    assert rep.metrics["journal_orphan_count"] >= 1


def test_classifiable_fires_triage(tmp_path):
    texto = (
        _HEADER_9 + _row("H-1", "⏳ Pendente")
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- C-1: bare discovery\n"
    )
    root = _repo(tmp_path, texto)
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_TRIAGE_REQUIRED") is True
    assert rep.metrics["classifiable_count"] == 1


def test_concurrent_inbox_signal(tmp_path):
    import concurrent_inbox as CI

    texto = (
        _HEADER_9 + _row("H-1", "⏳ Pendente")
        + "\n## INBOX (descobertas não priorizadas)\n"
    )
    root = _repo(tmp_path, texto)
    CI.write_discovery(
        str(root), "sess-a", "found-x",
        "DISCOVERED_WORK\ndescription: from other session\nblast_radius: local\n",
        timestamp="20260816-120000",
    )
    rep = SS.collect_signals(str(root), now=NOW)
    assert rep.is_active("TAB_CONCURRENT_INBOX_PRESENT") is True
    assert rep.is_active("TAB_TRIAGE_REQUIRED") is True


def test_format_machine_and_human(tmp_path):
    texto = (
        _HEADER_9 + _row("H-1", "⏳ Pendente")
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- C-1: bare\n"
    )
    root = _repo(tmp_path, texto)
    rep = SS.collect_signals(str(root), now=NOW)
    machine = SS.format_machine(rep)
    human = SS.format_human(rep)
    assert "TAB_TRIAGE_REQUIRED" in machine
    assert "TAB_TRIAGE_REQUIRED" in human


# ---------------------------------------------------------------------------
# Grep-guard: motor sem intake/wsjf/rede
# ---------------------------------------------------------------------------

def test_session_signals_no_forbidden_imports():
    path = os.path.join(TOOLS_DIR, "session_signals.py")
    src = open(path, encoding="utf-8").read()
    forbidden = ("run_intake", "FULL_REORDER", "wsjf", "openai", "urllib")
    for term in forbidden:
        assert term not in src, f"termo proibido em session_signals: {term}"
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in (
                    "openai", "urllib", "wsjf", "todo_intake",
                )
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            assert mod not in ("openai", "urllib", "wsjf", "todo_intake")
