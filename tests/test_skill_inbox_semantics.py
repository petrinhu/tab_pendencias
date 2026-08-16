"""tests/test_skill_inbox_semantics.py -- INBOX e exception queue (Fase 7).

Garante que o corpo do SKILL.md e o reference de frescor NAO mandam mais
toda descoberta para a INBOX como fila normal; e que o contrato de
descoberta / templates de vault existem.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_skill_frontmatter_description_unchanged_shape():
    """Nao reescrever description neste PR: so existe e e uma linha."""
    text = (REPO / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---"
    assert lines[1].startswith("name:")
    assert lines[2].startswith("description:")
    # description nao deve ter sido "esvaziada"
    assert len(lines[2]) > 40


def test_skill_inbox_is_exception_queue_not_default_path():
    text = (REPO / "SKILL.md").read_text(encoding="utf-8")
    # semantica nova
    assert "exception queue" in text.casefold()
    assert "DISCOVERED_WORK" in text
    assert "todo_intake" in text or "tools/todo_intake.py" in text
    # NAO pode restar a regra velha como norma vigente (sem marcar historico)
    # A frase canonica antiga:
    old = "vai para a INBOX na hora"
    if old in text:
        # so aceitavel dentro de bloco historico
        idx = text.index(old)
        window = text[max(0, idx - 200): idx + 80].casefold()
        assert "historico" in window or "histórica" in window or "obsoleto" in window


def test_frescor_reference_marks_legacy_and_intake():
    text = (REPO / "references" / "frescor-da-tabela.md").read_text(
        encoding="utf-8"
    )
    assert "exception queue" in text.casefold() or "pipeline de intake" in text.casefold()
    assert "Historico" in text or "histórico" in text.casefold() or "Historico" in text
    assert "hub-agregador" in text or "Hub agregador" in text


def test_vault_templates_exist_and_are_path_clean():
    import re
    email_re = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
    paths = [
        REPO / "templates" / "vault" / "CLAUDE.md.fragment.md",
        REPO / "templates" / "vault" / "tabela-pendencias-frescor.overlay.md",
        REPO / "templates" / "vault" / "settings.sanitized.hook-snippet.json",
        REPO / "templates" / "agents" / "implementer-discovery-contract.md",
    ]
    for p in paths:
        assert p.is_file(), f"missing {p}"
        blob = p.read_text(encoding="utf-8")
        assert "/home/" not in blob
        assert not email_re.search(blob), f"email in {p}"


def test_settings_snippet_relative_hook_path():
    text = (
        REPO / "templates" / "vault" / "settings.sanitized.hook-snippet.json"
    ).read_text(encoding="utf-8")
    assert "skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py" in text
    assert "$HOME" not in text
    assert "/home/" not in text
    # command nao e absoluto
    import json
    data = json.loads(text)
    raw = json.dumps(data.get("hooks", {}))
    assert "python3 skills/tab_pendencias/" in raw


def test_implementer_contract_has_discovered_work_fields():
    text = (
        REPO / "templates" / "agents" / "implementer-discovery-contract.md"
    ).read_text(encoding="utf-8")
    for field in (
        "DISCOVERED_WORK",
        "source_item:",
        "description:",
        "evidence:",
        "known_dependencies:",
        "blast_radius:",
    ):
        assert field in text
    assert "nao editam" in text.casefold() or "não" in text.casefold() or "Nao editar" in text or "não editar" in text.casefold()


def test_claude_fragment_has_six_steps():
    text = (
        REPO / "templates" / "vault" / "CLAUDE.md.fragment.md"
    ).read_text(encoding="utf-8")
    for n in range(1, 7):
        assert f"{n}." in text
    assert "TRIAGE_REQUIRED" in text or "TAB_TRIAGE_REQUIRED" in text
