"""tests/test_hub_guard.py -- TAB-HUB-001 guarda hub derived read-only."""
from __future__ import annotations

import os
import subprocess

import pytest

from conftest import git_init_isolado
import todo_intake as I

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}

_HEADER = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
)


def _todo(tmp_path, *, hub: bool = False, inbox_line: str | None = None):
    git_init_isolado(tmp_path)
    body = (
        "# TODO hub mock\n\n"
        + _HEADER
        + "| H-1 | W1 | Core | Aggregate counts | Baixa | — | Baixa | "
        "⏳ Pendente | — |\n"
    )
    if inbox_line:
        body += (
            "\n## INBOX (descobertas não priorizadas)\n\n"
            f"{inbox_line}\n"
        )
    (tmp_path / "TODO.md").write_text(body, encoding="utf-8")
    if hub:
        (tmp_path / ".tab_pendencias.ini").write_text(
            "[hub]\nderived = true\n",
            encoding="utf-8",
        )
    subprocess.run(
        ["git", "add", "TODO.md"]
        + ([".tab_pendencias.ini"] if hub else []),
        cwd=tmp_path,
        env=ENV,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-qm", "init"],
        cwd=tmp_path,
        env=ENV,
        check=True,
        capture_output=True,
    )
    return str(tmp_path / "TODO.md")


def test_is_derived_hub_true_false(tmp_path):
    todo = _todo(tmp_path, hub=True)
    assert I.is_derived_hub(todo) is True
    # sem ini
    other = tmp_path / "proj"
    other.mkdir()
    todo2 = _todo(other, hub=False)
    assert I.is_derived_hub(todo2) is False


def test_is_derived_hub_accepts_yes_on(tmp_path):
    git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text("# t\n\n" + _HEADER, encoding="utf-8")
    (tmp_path / ".tab_pendencias.ini").write_text(
        "[hub]\nderived = yes\n", encoding="utf-8"
    )
    assert I.is_derived_hub(str(todo)) is True


def test_run_intake_apply_blocked_on_hub(tmp_path):
    todo = _todo(tmp_path, hub=True)
    cand = I.WorkCandidate(
        candidate_id="c1",
        description="should not land on hub",
        source="agent",
        item_id="H-2",
        fields_complete=True,
        is_local=True,
        authority_ok=True,
    )
    # dry-run ainda classifica
    dry = I.run_intake(todo_path=todo, candidate=cand, apply=False)
    assert dry.rc in (0, 2)
    assert dry.error != "hub_is_derived_readonly"
    # apply bloqueia
    res = I.run_intake(todo_path=todo, candidate=cand, apply=True)
    assert res.rc == 1
    assert res.error == "hub_is_derived_readonly"
    assert "hub_is_derived_readonly" in res.report_text
    # arquivo intacto
    text = open(todo, encoding="utf-8").read()
    assert "H-2" not in text
    assert "should not land" not in text


def test_run_drain_apply_blocked_on_hub(tmp_path):
    todo = _todo(
        tmp_path,
        hub=True,
        inbox_line="- X-1: classifiable leftover",
    )
    res = I.run_drain(todo_path=todo, apply=True, judgments={})
    assert res.rc == 1
    assert res.error == "hub_is_derived_readonly"
    assert res.applied is False


def test_run_intake_apply_ok_without_hub_flag(tmp_path):
    todo = _todo(tmp_path, hub=False)
    cand = I.WorkCandidate(
        candidate_id="c2",
        description="normal project item",
        source="agent",
        item_id="N-9",
        fields_complete=True,
        is_local=True,
        authority_ok=True,
    )
    res = I.run_intake(todo_path=todo, candidate=cand, apply=True)
    assert res.rc == 0
    assert res.applied is True
    assert res.route == I.ROUTE_LOCAL_INTEGRATION
