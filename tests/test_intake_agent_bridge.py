"""tests/test_intake_agent_bridge.py -- ponte agentiva + e2e DISCOVERED_WORK.

Prova o caminho agentivo: texto DISCOVERED_WORK (preenchido por agente) ->
bridge mecanico (sem LLM) -> run_intake apply -> linha na tabela + journal DONE.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from conftest import git_init_isolado

import intake_agent_bridge as B
import intake_journal as J
import todo_intake as I
import todo_lib as L

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

HEADER_9 = (
    "| ID | Wave | Group | Description | Priority | Blocked By | "
    "Effort | Status | Reviewed |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
)
ROW_A = (
    "| #01 | W1 | Core | Bootstrap packaging | High | - | Medium | "
    "✅ Concluído | yes |\n"
)
TODO_BASE = (
    "# Agentive fixture\n\n## Table\n\n"
    + HEADER_9 + ROW_A +
    "\n## Notes\n\nSynthetic.\n"
)


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=ENV, capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=check,
    )


def _repo(tmp_path, texto=TODO_BASE):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_init_isolado(repo)
    todo = repo / "TODO.md"
    todo.write_text(texto, encoding="utf-8", newline="\n")
    _git(repo, "add", "TODO.md")
    _git(repo, "commit", "-qm", "c0")
    return repo, todo


def test_parse_discovered_work_single_block():
    block = """
Some agent chatter...

DISCOVERED_WORK
source_item: #01
description: Add latch interlock on the hatch
evidence: tests/test_hatch.py:12
known_dependencies: #01
blast_radius: local
"""
    items = B.parse_discovered_work(block)
    assert len(items) == 1
    assert items[0]["source_item"] == "#01"
    assert "latch interlock" in items[0]["description"]
    assert items[0]["blast_radius"] == "local"


def test_parse_discovered_work_multiple_blocks():
    block = """
DISCOVERED_WORK
source_item: A
description: First find
evidence: a:1
known_dependencies: unknown
blast_radius: unknown

DISCOVERED_WORK
source_item: B
description: Second find
evidence: b:2
known_dependencies: A
blast_radius: component
"""
    items = B.parse_discovered_work(block)
    assert len(items) == 2
    assert items[1]["blast_radius"] == "component"


def test_judgment_blast_radius_map():
    local = B.judgment_from_discovered({
        "description": "x", "blast_radius": "local",
        "known_dependencies": "", "source_item": "S",
    })
    assert local["is_local"] is True
    assert local["fields_complete"] is True
    assert local["is_scoped"] is False

    comp = B.judgment_from_discovered({
        "description": "y", "blast_radius": "component",
        "known_dependencies": "A, B", "source_item": "S",
    })
    assert comp["is_scoped"] is True
    assert comp["dependencies"] == ["A", "B"]

    sys_j = B.judgment_from_discovered({
        "description": "z", "blast_radius": "system",
        "known_dependencies": "unknown", "source_item": "S",
    })
    assert sys_j["is_foundation"] is True
    assert sys_j["dependencies"] == []

    unk = B.judgment_from_discovered({
        "description": "w", "blast_radius": "unknown",
        "known_dependencies": "", "source_item": "S",
    })
    assert unk["fields_complete"] is False


def test_e2e_discovered_work_bridge_intake_apply(tmp_path):
    """Caminho agentivo: bloco -> bridge -> run_intake apply -> tabela+journal."""
    repo, todo = _repo(tmp_path)
    block = """
DISCOVERED_WORK
source_item: #01
description: Document the hatch interlock edge cases
evidence: review-notes:3
known_dependencies: #01
blast_radius: local
item_id: #20
candidate_id: agent-hatch-1
"""
    discovered = B.parse_discovered_work(block)
    assert len(discovered) == 1
    judgment = B.judgment_from_discovered(discovered[0])
    # agente (ou orquestrador) fecha item_id se o bloco trouxe
    assert judgment["item_id"] == "#20"
    assert judgment["is_local"] is True
    assert judgment["fields_complete"] is True

    cand = I.WorkCandidate(
        candidate_id=judgment["candidate_id"],
        description=judgment["description"],
        source=judgment["source"],
        evidence=judgment["evidence"],
        source_item=judgment["source_item"],
        dependencies=judgment["dependencies"],
        item_id=judgment["item_id"],
        fields_complete=judgment["fields_complete"],
        authority_ok=judgment["authority_ok"],
        is_local=judgment["is_local"],
        is_scoped=judgment["is_scoped"],
        is_foundation=judgment["is_foundation"],
    )
    result = I.run_intake(todo_path=str(todo), candidate=cand, apply=True)
    assert result.rc == 0, result.error or result.report_text
    assert result.route == I.ROUTE_LOCAL_INTEGRATION
    assert result.applied is True

    texto = todo.read_text(encoding="utf-8")
    ids = {it["id"] for it in L.parse_table(texto)["items"]}
    assert "#20" in ids
    assert "intake:agent-hatch-1" in texto

    jd = J.journal_dir_for(cwd=str(repo))
    assert jd is not None
    path = J.candidate_path(jd, "agent-hatch-1")
    assert os.path.isfile(path)
    rec, err = J.read_candidate_safe(path)
    assert err is None
    assert rec["state"] == J.STATE_DONE
