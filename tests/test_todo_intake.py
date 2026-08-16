"""tests/test_todo_intake.py -- TAB-ADD-001/002-meca/003-cascata/004-L0.

Motor offline de intake (`tools/todo_intake.py`): cascata de rota ADR-0002 (d),
dedup mecanica por ID exato, integracao L0 (append puro), residual INBOX com
metadado [triage ...], journal write-ahead e precondicoes de apply.

Nao reusa helpers de outros arquivos de teste (convencao da suite, ver
test_intake_journal.py). Fixtures sinteticas apenas -- IDs estilo #01 e prosa
em ingles (agnosticismo / ADR-0001).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from conftest import git_init_isolado

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
    "| #01 | W1 | Core | Bootstrap the packaging line simulator | High | "
    "- | Medium | ✅ Concluído | yes |\n"
)
ROW_B = (
    "| #02 | W1 | Core | Wire the conveyor belt sensor driver | High | "
    "#01 | Medium | 🔄 Em andamento | - |\n"
)
ROW_C = (
    "| #03 | W2 | Safety | Add emergency stop debounce logic | High | "
    "#02 | Low | ⏳ Pendente | - |\n"
)

TODO_BASE = (
    "# Aurora Widgets -- Engineering Backlog\n\n"
    "## Ticket table\n\n"
    + HEADER_9 + ROW_A + ROW_B + ROW_C +
    "\n## Notes\n\nSynthetic fixture only.\n"
)

TODO_COM_INBOX_CLASSIFICAVEL = (
    TODO_BASE +
    "\n## INBOX (descobertas não priorizadas)\n"
    "- #99: bare discovery without triage token\n"
)

TODO_COM_INBOX_RESIDUAL = (
    TODO_BASE +
    "\n## INBOX (descobertas não priorizadas)\n"
    "- #88: [triage since=2026-08-01 reason=missing-info cycles=0] "
    "waiting for more evidence\n"
)


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), env=ENV,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _repo_com_todo(tmp_path, texto=TODO_BASE, commit=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_init_isolado(repo)
    todo = repo / "TODO.md"
    todo.write_text(texto, encoding="utf-8", newline="\n")
    if commit:
        _git(repo, "add", "TODO.md")
        _git(repo, "commit", "-qm", "c0")
    return repo, todo


def _cand(**overrides):
    base = dict(
        candidate_id="cand-001",
        description="Draft the shift handover report template",
        source="test",
        evidence="fixture",
        source_item="",
        dependencies=[],
        item_id="#04",
        onda="W2",
        grupo="Reporting",
        prioridade="Medium",
        dificuldade="Low",
        prereq="-",
        status="⏳ Pendente",
        estado_auditado="-",
        fields_complete=True,
        authority_ok=True,
        is_foundation=False,
        is_local=True,
        is_scoped=False,
    )
    base.update(overrides)
    return I.WorkCandidate(**base)


def _assert_journal_done(repo, cid):
    """Prova positiva: arquivo de journal existe em disco com state=DONE.

    Nao basta "nao e orfao" -- sem write_candidate, list_orphans tambem nao
    acha o id e o teste passaria em falso.
    """
    jd = J.journal_dir_for(cwd=str(repo))
    assert jd is not None
    path = J.candidate_path(jd, cid)
    assert os.path.isfile(path), f"journal ausente em disco: {path}"
    rec, err = J.read_candidate_safe(path)
    assert err is None, err
    assert rec["candidate_id"] == cid
    assert rec["state"] == J.STATE_DONE


# ---------------------------------------------------------------------------
# decide_route -- cada ramo da cascata
# ---------------------------------------------------------------------------

def test_decide_route_duplicate_por_id_na_tabela():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(item_id="#02", is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_DUPLICATE


def test_decide_route_duplicate_por_id_na_inbox():
    table = L.parse_table(TODO_COM_INBOX_RESIDUAL)
    inbox = L.inbox_entries(TODO_COM_INBOX_RESIDUAL)
    c = _cand(item_id="#88", is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_DUPLICATE


def test_decide_route_needs_triage_quando_fields_incomplete():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(fields_complete=False, is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_NEEDS_TRIAGE


def test_decide_route_needs_triage_quando_dep_inexistente():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(dependencies=["#99"], fields_complete=True, is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_NEEDS_TRIAGE


def test_decide_route_needs_triage_descricao_vazia():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(description="   ", fields_complete=True, is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_NEEDS_TRIAGE


def test_decide_route_needs_triage_source_invalido():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(source="not-a-source", fields_complete=True, is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_NEEDS_TRIAGE


def test_decide_route_needs_leader_decision():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(authority_ok=False, is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_NEEDS_LEADER_DECISION


def test_decide_route_full_reorder_por_fundacao():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(is_foundation=True, is_local=True, is_scoped=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_FULL_REORDER


def test_decide_route_local_integration():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(is_local=True, is_scoped=False)
    assert I.decide_route(c, table, inbox) == I.ROUTE_LOCAL_INTEGRATION


def test_decide_route_scoped_reorder():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(is_local=False, is_scoped=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_SCOPED_REORDER


def test_decide_route_default_full_reorder():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(is_local=False, is_scoped=False, is_foundation=False)
    assert I.decide_route(c, table, inbox) == I.ROUTE_FULL_REORDER


def test_cascata_dup_vence_fields_incomplete():
    """P-dup e o primeiro predicado: ID existente vence fields_complete=False."""
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(item_id="#01", fields_complete=False)
    assert I.decide_route(c, table, inbox) == I.ROUTE_DUPLICATE


def test_cascata_campos_vence_autoridade():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(fields_complete=False, authority_ok=False)
    assert I.decide_route(c, table, inbox) == I.ROUTE_NEEDS_TRIAGE


# ---------------------------------------------------------------------------
# L0 dry-run / apply
# ---------------------------------------------------------------------------

def test_l0_dry_run_nao_escreve(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    result = I.run_intake(todo_path=str(todo), candidate=_cand(), apply=False)
    assert result.route == I.ROUTE_LOCAL_INTEGRATION
    assert result.applied is False
    assert result.rc == 2
    assert todo.read_text(encoding="utf-8") == antes


def test_l0_apply_escreve_uma_linha_e_preserva_bytes(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    table_antes = L.parse_table(antes)
    linhas_antigas = {
        it["id"]: table_antes["lines"][it["line_no"]]
        for it in table_antes["items"]
    }
    status_antigos = {it["id"]: it["status"] for it in table_antes["items"]}

    result = I.run_intake(todo_path=str(todo), candidate=_cand(), apply=True)
    assert result.rc == 0
    assert result.applied is True
    assert result.route == I.ROUTE_LOCAL_INTEGRATION

    depois = todo.read_text(encoding="utf-8")
    table_depois = L.parse_table(depois)
    ids = [it["id"] for it in table_depois["items"]]
    assert ids == ["#01", "#02", "#03", "#04"]
    # W1: status de linhas antigas identico
    for it in table_depois["items"]:
        if it["id"] in status_antigos:
            assert it["status"] == status_antigos[it["id"]]
    # linhas brutas de IDs antigos identicas (L0)
    for iid, raw in linhas_antigas.items():
        it = next(x for x in table_depois["items"] if x["id"] == iid)
        assert table_depois["lines"][it["line_no"]] == raw


def test_l0_inclui_marcador_candidate_id_recuperavel(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    cid = "cand-marker-42"
    result = I.run_intake(
        todo_path=str(todo),
        candidate=_cand(candidate_id=cid, item_id="#04"),
        apply=True,
    )
    assert result.rc == 0
    text = todo.read_text(encoding="utf-8")
    assert f"<!-- intake:{cid} -->" in text
    # recover_orphans ve o candidate_id no texto
    assert cid in text


def test_l0_journal_apos_apply_nao_e_orfao(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    cid = "cand-journal-l0"
    result = I.run_intake(
        todo_path=str(todo),
        candidate=_cand(candidate_id=cid, item_id="#04"),
        apply=True,
    )
    assert result.rc == 0
    jd = J.journal_dir_for(cwd=str(repo))
    orphans = J.list_orphans(jd)
    ids = [rec["candidate_id"] for _p, rec in orphans]
    assert cid not in ids
    _assert_journal_done(repo, cid)


def test_l0_item_id_vazio_nao_grava_journal_nem_todo(tmp_path):
    """L0 com item_id vazio aborta ANTES do journal (sem orfao permanente)."""
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    cid = "cand-empty-id"
    c = _cand(item_id="", candidate_id=cid, is_local=True)
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert result.applied is False
    err = (result.error or "").lower()
    assert "item_id" in err and ("vazio" in err or "empty" in err)
    assert todo.read_text(encoding="utf-8") == antes
    jd = J.journal_dir_for(cwd=str(repo))
    path = J.candidate_path(jd, cid)
    assert not os.path.exists(path), f"journal nao deveria existir: {path}"
    orphans = [rec["candidate_id"] for _p, rec in J.list_orphans(jd)]
    assert cid not in orphans


def test_l0_tabela_sintetica_id_hash_e_prosa_ingles(tmp_path):
    """Agnosticismo: ID estilo #01 e descricao em ingles, sem fixtures reais."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        candidate_id="cand-en-1",
        item_id="#07",
        description="Reconcile the weekly defect counters",
        grupo="Reporting",
        onda="W4",
        dependencies=["#03"],
        prereq="#03",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    assert any(it["id"] == "#07" for it in table["items"])


# ---------------------------------------------------------------------------
# _provar_invariantes (unitario)
# ---------------------------------------------------------------------------

def test_provar_invariantes_w1_status_antigo_alterado():
    """Mutante que remove o check W1 deve ser morto por este teste."""
    old_table = L.parse_table(TODO_BASE)
    # altera so a celula Status de #01 (item pre-existente)
    novo = TODO_BASE.replace(
        "| #01 | W1 | Core | Bootstrap the packaging line simulator | High | "
        "- | Medium | ✅ Concluído | yes |\n",
        "| #01 | W1 | Core | Bootstrap the packaging line simulator | High | "
        "- | Medium | ⏳ Pendente | yes |\n",
    )
    assert novo != TODO_BASE
    ok, motivo = I._provar_invariantes(
        novo,
        old_table=old_table,
        route=I.ROUTE_LOCAL_INTEGRATION,
        expected_item_delta=0,
        preserve_raw_ids=False,
    )
    assert ok is False
    assert motivo is not None
    assert "W1" in motivo


def test_provar_invariantes_preserve_raw_ids_linha_alterada():
    """Linha bruta de id antigo alterada com preserve_raw_ids=True deve falhar."""
    old_table = L.parse_table(TODO_BASE)
    # muda descricao de #02 sem mexer no Status -- bytes da linha divergem
    novo = TODO_BASE.replace(
        "Wire the conveyor belt sensor driver",
        "Wire the conveyor belt sensor drivers",
    )
    assert novo != TODO_BASE
    ok, motivo = I._provar_invariantes(
        novo,
        old_table=old_table,
        route=I.ROUTE_LOCAL_INTEGRATION,
        expected_item_delta=0,
        preserve_raw_ids=True,
    )
    assert ok is False
    assert motivo is not None
    assert "L0" in motivo or "bytes" in motivo.lower()


# ---------------------------------------------------------------------------
# residual INBOX
# ---------------------------------------------------------------------------

def test_needs_triage_grava_metadado_parseavel(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    cid = "cand-triage-meta"
    c = _cand(fields_complete=False, item_id="#50", candidate_id=cid,
              description="unclear scope for packaging")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0
    assert result.route == I.ROUTE_NEEDS_TRIAGE
    text = todo.read_text(encoding="utf-8")
    entries = L.inbox_entries(text)
    match = [e for e in entries if e["id"] == "#50"]
    assert len(match) == 1
    e = match[0]
    assert e["classifiable"] is False
    assert e["triage"]["valid"] is True
    assert e["triage"]["fields"]["reason"] == "missing-info"
    assert e["triage"]["fields"].get("cycles") == "0"
    _assert_journal_done(repo, cid)


def test_needs_leader_decision_reason_correta(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(authority_ok=False, item_id="#51",
              description="needs go/no-go from leader")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0
    assert result.route == I.ROUTE_NEEDS_LEADER_DECISION
    entries = L.inbox_entries(todo.read_text(encoding="utf-8"))
    e = next(x for x in entries if x["id"] == "#51")
    assert e["triage"]["valid"] is True
    assert e["triage"]["fields"]["reason"] == "needs-leader-decision"


def test_needs_triage_cria_secao_inbox_se_ausente(tmp_path):
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_BASE)
    assert "INBOX" not in todo.read_text(encoding="utf-8")
    c = _cand(fields_complete=False, item_id="#52")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0
    text = todo.read_text(encoding="utf-8")
    assert "## INBOX (descobertas não priorizadas)" in text


# ---------------------------------------------------------------------------
# precondicoes de apply
# ---------------------------------------------------------------------------

def test_apply_com_classifiable_preexistente_falha(tmp_path):
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_COM_INBOX_CLASSIFICAVEL)
    c = _cand(is_local=True, item_id="#04")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert "classifiable_inbox_present" in (result.error or "")
    # arquivo intocado
    assert "bare discovery" in todo.read_text(encoding="utf-8")
    assert "#04" not in [it["id"] for it in
                         L.parse_table(todo.read_text(encoding="utf-8"))["items"]]


def test_apply_com_working_tree_suja_falha(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    # suja o TODO.md
    todo.write_text(todo.read_text(encoding="utf-8") + "\n<!-- dirty -->\n",
                    encoding="utf-8")
    c = _cand(is_local=True)
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert result.error is not None
    assert "dirty" in result.error.lower() or "working tree" in result.error.lower() \
        or "suja" in result.error.lower() or "não commitada" in result.error.lower() \
        or "nao commitada" in result.error.lower() \
        or "mudança" in result.error.lower() or "mudanca" in result.error.lower()


def test_scoped_apply_not_implemented_sem_tocar_arquivo(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    c = _cand(is_local=False, is_scoped=True, item_id="#04")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert "not_implemented:SCOPED_REORDER" in (result.error or "")
    assert todo.read_text(encoding="utf-8") == antes


def test_full_apply_not_implemented_sem_tocar_arquivo(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    c = _cand(is_foundation=True, item_id="#04")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert "not_implemented:FULL_REORDER" in (result.error or "")
    assert todo.read_text(encoding="utf-8") == antes


def test_duplicate_apply_nao_cria_linha_journal_done(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    n_antes = len(L.parse_table(todo.read_text(encoding="utf-8"))["items"])
    cid = "cand-dup-1"
    c = _cand(item_id="#02", candidate_id=cid)
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0
    assert result.route == I.ROUTE_DUPLICATE
    assert result.existing_id == "#02"
    n_depois = len(L.parse_table(todo.read_text(encoding="utf-8"))["items"])
    assert n_depois == n_antes
    jd = J.journal_dir_for(cwd=str(repo))
    orphans = [rec["candidate_id"] for _p, rec in J.list_orphans(jd)]
    assert cid not in orphans
    _assert_journal_done(repo, cid)


def test_dry_run_com_classifiable_nao_bloqueia(tmp_path):
    """Drain-first so em apply; dry-run ainda classifica o candidato."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_COM_INBOX_CLASSIFICAVEL)
    c = _cand(is_local=True, item_id="#04")
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert result.rc == 2
    assert result.route == I.ROUTE_LOCAL_INTEGRATION


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_flag_desconhecida_e_erro(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "todo_intake", "--todo", str(todo),
         "--unknown-flag"],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env={**ENV, "PYTHONPATH": os.path.dirname(I.__file__)},
    )
    # argparse pode ser via script path
    r2 = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(I.__file__),
                                      "todo_intake.py"),
         "--todo", str(todo), "--unknown-flag"],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert r2.returncode == 1


def test_cli_dry_run_l0_exit_2(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    script = os.path.join(os.path.dirname(I.__file__), "todo_intake.py")
    r = subprocess.run(
        [sys.executable, script,
         "--todo", str(todo),
         "--candidate-id", "cand-cli-1",
         "--item-id", "#04",
         "--description", "Draft the shift handover report template",
         "--source", "test",
         "--fields-complete",
         "--local"],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 2
    assert "LOCAL_INTEGRATION" in r.stdout or "LOCAL_INTEGRATION" in r.stderr
