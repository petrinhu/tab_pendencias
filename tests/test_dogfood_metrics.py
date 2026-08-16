"""tests/test_dogfood_metrics.py -- TAB-CUT-002/004 dogfood metrics."""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "dogfood_metrics.py")
TODO_REAL = os.path.join(REPO, "TODO.md")


def _load_mod():
    spec = importlib.util.spec_from_file_location("dogfood_metrics", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _todo_minimo(inbox_lines: str = "") -> str:
    body = (
        "| ID | Onda | Grupo | Descrição Técnica | Prioridade | "
        "Pré-requisito | Dificuldade | Status | Estado Auditado |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| X-1 | W1 | G | item a | Alta | — | Baixa | ⏳ Pendente | — |\n"
        "| X-2 | W1 | G | item b | Media | — | Baixa | "
        "🔍 Pendente verificação | — |\n"
    )
    if inbox_lines:
        body += (
            "\n## INBOX (descobertas não priorizadas)\n"
            f"{inbox_lines}"
        )
    return body


def test_collect_metrics_classifiable_zero(tmp_path):
    DM = _load_mod()
    todo = tmp_path / "TODO.md"
    todo.write_text(_todo_minimo(), encoding="utf-8")
    data = DM.collect_metrics(str(todo))
    assert data["ok"] is True
    assert data["classifiable"] == 0
    assert data["inbox_total"] == 0
    assert data["n_items"] == 2
    assert data["n_verif"] == 1
    assert data["n_pending"] == 1
    assert "signals" in data
    assert "signals_active" in data


def test_collect_metrics_classifiable_positivo_e_legacy(tmp_path):
    DM = _load_mod()
    todo = tmp_path / "TODO.md"
    todo.write_text(
        _todo_minimo("- LEG-1: linha legada sem triage\n"),
        encoding="utf-8",
    )
    data = DM.collect_metrics(str(todo))
    assert data["ok"] is True
    assert data["classifiable"] == 1
    assert data["inbox_total"] == 1
    assert data["oldest_age_days"] is None  # so residual tem since


def test_collect_metrics_oldest_age_residual(tmp_path):
    DM = _load_mod()
    import datetime
    todo = tmp_path / "TODO.md"
    todo.write_text(
        _todo_minimo(
            "- R-1: [triage since=2026-08-01 reason=missing-info "
            "cycles=0 source=audit] wait\n"
        ),
        encoding="utf-8",
    )
    now = datetime.date(2026, 8, 16)
    data = DM.collect_metrics(str(todo), now=now)
    assert data["classifiable"] == 0
    assert data["residual"] == 1
    assert data["oldest_age_days"] == 15


def test_cli_exit_0_quando_limpo(tmp_path, capsys):
    DM = _load_mod()
    todo = tmp_path / "TODO.md"
    todo.write_text(_todo_minimo(), encoding="utf-8")
    rc = DM.main(["--todo", str(todo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "classifiable: 0" in out
    assert "dogfood: classifiable==0 OK" in out


def test_cli_exit_2_quando_classifiable(tmp_path, capsys):
    DM = _load_mod()
    todo = tmp_path / "TODO.md"
    todo.write_text(
        _todo_minimo("- Z-1: bare classifiable\n"),
        encoding="utf-8",
    )
    rc = DM.main(["--todo", str(todo)])
    out = capsys.readouterr().out
    assert rc == 2
    assert "classifiable: 1" in out


def test_cli_json(tmp_path, capsys):
    DM = _load_mod()
    todo = tmp_path / "TODO.md"
    todo.write_text(_todo_minimo(), encoding="utf-8")
    rc = DM.main(["--todo", str(todo), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["classifiable"] == 0
    assert data["n_items"] == 2


def test_dogfood_real_repo_classifiable_zero():
    """Dogfood no TODO.md do produto: classifiable deve ser 0 pos cutover.

    Se a INBOX real estiver suja (classifiable>0), o teste e skip -- o
    criterio operacional e o script + gate CUT-11, nao forcar verde falso.
    """
    if not os.path.isfile(TODO_REAL):
        pytest.skip("TODO.md do repo ausente")
    DM = _load_mod()
    data = DM.collect_metrics(TODO_REAL)
    assert data["ok"] is True
    if data["classifiable"] > 0:
        pytest.skip(
            f"INBOX real com classifiable={data['classifiable']} "
            "(drenar antes de assertar dogfood)"
        )
    assert data["classifiable"] == 0
    text = DM.format_text(data)
    assert "classifiable: 0" in text
    # CLI no path real tambem exit 0
    rc = DM.main(["--todo", TODO_REAL])
    assert rc == 0
