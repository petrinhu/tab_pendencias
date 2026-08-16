"""tests/test_todo_intake.py -- TAB-ADD-001..007 (intake + SCOPED/FULL + strip).

Motor offline de intake (`tools/todo_intake.py`): cascata de rota ADR-0002 (d),
dedup mecanica por ID exato (tabela), integracao L0 (append puro), residual
INBOX com metadado [triage ...], strip residual apos integracao (007),
SCOPED/FULL apply (raw fora de S, topo, journal), journal write-ahead e
precondicoes de apply.

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


def test_decide_route_id_so_na_inbox_residual_nao_e_duplicate():
    """TAB-ADD-007: P-dup conta so a tabela -- residual re-entra no pipeline."""
    table = L.parse_table(TODO_COM_INBOX_RESIDUAL)
    inbox = L.inbox_entries(TODO_COM_INBOX_RESIDUAL)
    c = _cand(item_id="#88", is_local=True)
    assert I.decide_route(c, table, inbox) == I.ROUTE_LOCAL_INTEGRATION


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
# TAB-ADD-007 -- strip residual INBOX com mesmo id apos integracao
# ---------------------------------------------------------------------------

TODO_RESIDUAL_LEADER = (
    TODO_BASE +
    "\n## INBOX (descobertas não priorizadas)\n"
    "- DEC-1: [triage since=2026-08-16 reason=needs-leader-decision "
    "source=user cycles=0] pick a route for the packing station "
    "<!-- intake:cand-dec-old -->\n"
    "- #77: [triage since=2026-08-16 reason=missing-info cycles=0] "
    "keep this other residual\n"
)

TODO_RESIDUAL_COM_ID_DE_TABELA = (
    TODO_BASE +
    "\n## INBOX (descobertas não priorizadas)\n"
    "- #02: [triage since=2026-08-16 reason=needs-leader-decision "
    "source=user cycles=0] stale residual of already-integrated id "
    "<!-- intake:cand-stale -->\n"
    "- #77: [triage since=2026-08-16 reason=missing-info cycles=0] "
    "keep this other residual\n"
)


def test_strip_inbox_id_remove_so_linha_do_id():
    """Unitario: so a linha do id alvo some; heading e outras linhas ficam."""
    text = TODO_RESIDUAL_LEADER
    out = I._strip_inbox_id(text, "DEC-1")
    assert "DEC-1:" not in out
    assert "#77:" in out
    assert "## INBOX (descobertas não priorizadas)" in out
    # tabela intocada
    assert "| #01 |" in out and "| #03 |" in out
    # id inexistente: no-op
    assert I._strip_inbox_id(text, "NOPE") == text
    # id vazio: no-op
    assert I._strip_inbox_id(text, "") == text
    assert I._strip_inbox_id(text, "-") == text


def test_l0_apply_remove_residual_mesmo_id_preserva_outros(tmp_path):
    """Apos decisao do lider: L0 com DEC-1 entra na tabela e some da INBOX."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_RESIDUAL_LEADER)
    c = _cand(
        candidate_id="cand-dec-reentry",
        item_id="DEC-1",
        description="Wire packing station after leader go",
        is_local=True,
        fields_complete=True,
        authority_ok=True,
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_LOCAL_INTEGRATION
    text = todo.read_text(encoding="utf-8")
    table = L.parse_table(text)
    assert any(it["id"] == "DEC-1" for it in table["items"])
    entries = L.inbox_entries(text)
    ids = [e["id"] for e in entries]
    assert "DEC-1" not in ids
    assert "#77" in ids
    # invariante: nunca id simultaneo tabela+INBOX
    assert not I._ids_in_table_and_inbox(text)
    _assert_journal_done(repo, "cand-dec-reentry")


def test_duplicate_apply_limpa_residual_mesmo_id(tmp_path):
    """DUPLICATE (id ja na tabela) enriquece limpando residual com o mesmo id."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_RESIDUAL_COM_ID_DE_TABELA)
    n_antes = len(L.parse_table(todo.read_text(encoding="utf-8"))["items"])
    cid = "cand-dup-strip"
    c = _cand(item_id="#02", candidate_id=cid, is_local=True)
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_DUPLICATE
    text = todo.read_text(encoding="utf-8")
    n_depois = len(L.parse_table(text)["items"])
    assert n_depois == n_antes
    entries = L.inbox_entries(text)
    ids = [e["id"] for e in entries]
    assert "#02" not in ids
    assert "#77" in ids
    assert not I._ids_in_table_and_inbox(text)
    _assert_journal_done(repo, cid)


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


# ---------------------------------------------------------------------------
# FULL_REORDER / SCOPED_REORDER (TAB-ADD-005 / TAB-ADD-006)
# ---------------------------------------------------------------------------

TODO_CYCLE = (
    "# Cycle fixture\n\n"
    + HEADER_9
    + "| #A | W1 | Core | Node A of the cycle | High | #B | Low | "
    "⏳ Pendente | - |\n"
    + "| #B | W1 | Core | Node B of the cycle | High | #A | Low | "
    "⏳ Pendente | - |\n"
)


def test_full_reorder_insere_apos_cadeia_e_preserva_status(tmp_path):
    """FULL: A->B, candidato C depende B => ordem A,B,C; status A/B intactos."""
    repo, todo = _repo_com_todo(tmp_path)
    status_antes = {
        it["id"]: it["status"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    }
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#04",
        candidate_id="cand-full-1",
        description="Calibrate the end-of-line camera",
        dependencies=["#03"],
        prereq="#03",
        grupo="Safety",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_FULL_REORDER
    assert result.applied is True
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    ids = [it["id"] for it in table["items"]]
    assert ids == ["#01", "#02", "#03", "#04"]
    for it in table["items"]:
        if it["id"] in status_antes:
            assert it["status"] == status_antes[it["id"]]
    row04 = next(x for x in table["items"] if x["id"] == "#04")
    raw04 = table["lines"][row04["line_no"]]
    assert "<!-- intake:cand-full-1 -->" in raw04
    assert "Calibrate the end-of-line camera" in raw04
    _assert_journal_done(repo, "cand-full-1")


def test_full_reorder_ciclo_aborta_arquivo_intacto(tmp_path):
    """Ciclo: rc=1 dependency_cycle; arquivo intacto; sem journal orfao."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_CYCLE)
    antes = todo.read_text(encoding="utf-8")
    cid = "cand-cycle"
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#C",
        candidate_id=cid,
        description="Would hang on cycle",
        dependencies=["#A"],
        prereq="#A",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert "dependency_cycle" in (result.error or "")
    assert todo.read_text(encoding="utf-8") == antes
    # build falhou antes do journal -- sem NEW orfao nem DONE indevido
    jd = J.journal_dir_for(cwd=str(repo))
    assert not os.path.exists(J.candidate_path(jd, cid))
    orphans = [rec["candidate_id"] for _p, rec in J.list_orphans(jd)]
    assert cid not in orphans


# Fixture single-Grupo: evita promo multi-Grupo (Core+Safety) do TODO_BASE.
TODO_SCOPED_CHAIN = (
    "# Aurora Widgets -- Engineering Backlog\n\n"
    "## Ticket table\n\n"
    + HEADER_9
    + "| #D1 | W1 | Core | Distant finished bootstrap | High | - | "
    "Medium | ✅ Concluído | yes |\n"
    + "| #C1 | W1 | Core | Mid conveyor sensor | High | #D1 | Medium | "
    "🔄 Em andamento | - |\n"
    + "| #C2 | W2 | Core | End-of-line stop debounce | High | #C1 | Low | "
    "⏳ Pendente | - |\n"
    + "\n## Notes\n\nSynthetic fixture only.\n"
)


def test_scoped_reorder_preserva_raw_fora_de_S(tmp_path):
    """SCOPED: item distante no topo + cadeia no fim; raw fora de S identico."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_SCOPED_CHAIN)
    antes = todo.read_text(encoding="utf-8")
    table_antes = L.parse_table(antes)
    raw_antes = {
        it["id"]: table_antes["lines"][it["line_no"]]
        for it in table_antes["items"]
    }
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        item_id="#N1",
        candidate_id="cand-scoped-1",
        description="Add a packaging label checksum",
        dependencies=["#C2"],
        prereq="#C2",
        grupo="Core",
        onda="W3",
        scoped_max_fraction=1.0,  # evita promo por fracao
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_SCOPED_REORDER, result.report_text
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    raw_depois = {
        it["id"]: table["lines"][it["line_no"]]
        for it in table["items"] if it["id"] in raw_antes
    }
    # #D1 concluido e fora da cadeia aberta -- raw byte-a-byte
    assert raw_depois["#D1"] == raw_antes["#D1"]
    for iid in raw_antes:
        if iid in (result.s_ids or []):
            continue
        assert raw_depois[iid] == raw_antes[iid], (
            f"raw de {iid!r} fora de S mudou"
        )
    assert any(it["id"] == "#N1" for it in table["items"])
    _assert_journal_done(repo, "cand-scoped-1")


def test_scoped_s_vazio_preserva_todos_raws_existentes(tmp_path):
    """SCOPED sem deps abertas: S vazio; todos raws existentes intatos."""
    repo, todo = _repo_com_todo(tmp_path)
    table_antes = L.parse_table(todo.read_text(encoding="utf-8"))
    raw_antes = {
        it["id"]: table_antes["lines"][it["line_no"]]
        for it in table_antes["items"]
    }
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        item_id="#04",
        candidate_id="cand-scoped-empty-s",
        description="Independent packaging note",
        dependencies=[],
        prereq="-",
        scoped_max_fraction=1.0,
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_SCOPED_REORDER
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    for it in table["items"]:
        if it["id"] in raw_antes:
            raw = table["lines"][it["line_no"]]
            assert raw == raw_antes[it["id"]], (
                f"raw de {it['id']!r} mudou sob S vazio/minimo"
            )
    assert any(it["id"] == "#04" for it in table["items"])
    _assert_journal_done(repo, "cand-scoped-empty-s")


def test_scoped_fracao_baixa_promove_full(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        is_local=False, is_scoped=True,
        item_id="#04",
        candidate_id="cand-promote",
        description="Promote when S is large relative to n",
        dependencies=["#03"],
        prereq="#03",
        scoped_max_fraction=0.0,
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_FULL_REORDER
    assert result.promoted_from == I.ROUTE_SCOPED_REORDER
    assert "promoted_from" in result.report_text
    assert any(
        it["id"] == "#04"
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    )


def test_scoped_multi_grupo_promove_full(tmp_path):
    """S toca Core+#02 e Safety+#03: promove multi-Grupo (nao por fracao).

    Mata mutante que dropa o ramo multi-Grupo em should_promote_scoped_to_full.
    """
    repo, todo = _repo_com_todo(tmp_path)  # TODO_BASE: #02 Core + #03 Safety
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        fields_complete=True,
        item_id="#04",
        candidate_id="cand-multi-g",
        description="Cross-group scoped insertion under Safety stop",
        dependencies=["#03"],
        prereq="#03",
        grupo="Safety",
        scoped_max_fraction=1.0,  # nao promove por fracao
    )
    # Prova de precondicao: S real cobre 2 Grupos
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    S = I.compute_safe_subgraph_S(table, c)
    assert "#02" in S and "#03" in S, S
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_FULL_REORDER, result.report_text
    assert result.promoted_from == I.ROUTE_SCOPED_REORDER
    assert "multi-Grupo" in (result.report_text or "")
    assert any(
        it["id"] == "#04"
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    )
    _assert_journal_done(repo, "cand-multi-g")


def test_scoped_full_dry_run_rc2_sem_escrita(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    cases = [
        dict(is_local=False, is_scoped=True, is_foundation=False,
             candidate_id="cand-dry-s"),
        dict(is_local=False, is_scoped=False, is_foundation=True,
             candidate_id="cand-dry-f"),
    ]
    for kwargs in cases:
        c = _cand(item_id="#04", **kwargs)
        result = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
        assert result.rc == 2
        assert result.applied is False
        assert todo.read_text(encoding="utf-8") == antes


def test_full_w1_status_andamento_e_concluido_intactos(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    table_antes = L.parse_table(todo.read_text(encoding="utf-8"))
    st = {it["id"]: it["status"] for it in table_antes["items"]}
    assert any("✅" in s for s in st.values())
    assert any("🔄" in s for s in st.values())
    c = _cand(
        is_foundation=True, is_local=False,
        item_id="#10",
        candidate_id="cand-w1",
        description="Sensor watchdog timer",
        dependencies=["#02"],
        prereq="#02",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    for it in table["items"]:
        if it["id"] in st:
            assert it["status"] == st[it["id"]], it


def test_scoped_item_id_vazio_antes_do_journal(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    cid = "cand-scoped-empty"
    c = _cand(
        is_local=False, is_scoped=True, item_id="",
        candidate_id=cid,
        description="missing id",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert "item_id" in (result.error or "").lower()
    assert todo.read_text(encoding="utf-8") == antes
    jd = J.journal_dir_for(cwd=str(repo))
    assert not os.path.exists(J.candidate_path(jd, cid))


def test_full_item_id_vazio_antes_do_journal(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    cid = "cand-full-empty"
    c = _cand(
        is_foundation=True, is_local=False, item_id="",
        candidate_id=cid,
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 1
    assert "item_id" in (result.error or "").lower()
    jd = J.journal_dir_for(cwd=str(repo))
    assert not os.path.exists(J.candidate_path(jd, cid))


def test_full_agnostico_ids_hash_prosa_ingles(tmp_path):
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        is_foundation=True, is_local=False,
        item_id="#10",
        candidate_id="cand-en-full",
        description="Reconcile weekly defect counters after sensor fix",
        dependencies=["#03"],
        prereq="#03",
        grupo="Reporting",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    text = todo.read_text(encoding="utf-8")
    assert "#10" in text
    assert "Reconcile weekly defect counters" in text
    assert "<!-- intake:cand-en-full -->" in text


def test_scoped_journal_done_em_disco(tmp_path):
    """SCOPED single-Grupo: journal DONE e rota NAO promove (contra multi-Grupo)."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_SCOPED_CHAIN)
    cid = "cand-scoped-j"
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        item_id="#N2",
        candidate_id=cid,
        description="Scoped journal proof",
        dependencies=["#C2"],
        prereq="#C2",
        grupo="Core",
        scoped_max_fraction=1.0,  # evita promo por fracao
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_SCOPED_REORDER, result.report_text
    assert result.promoted_from is None
    assert any(
        it["id"] == "#N2"
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    )
    _assert_journal_done(repo, cid)


# ---------------------------------------------------------------------------
# WSJF / FULL (TAB-WSJF-001..007 -- §4.2 do blueprint Fase 3)
# ---------------------------------------------------------------------------

TODO_TWO_ROOTS = (
    "# Two roots fixture\n\n"
    + HEADER_9
    + "| #A | W1 | Core | Root job low score | High | - | High | "
    "⏳ Pendente | - |\n"
    + "| #B | W1 | Core | Root job high score | High | - | Low | "
    "⏳ Pendente | - |\n"
)

TODO_TOPO_BEATS = (
    "# Topology beats WSJF fixture\n\n"
    + HEADER_9
    + "| #A | W1 | Core | Root job low score | High | - | High | "
    "⏳ Pendente | - |\n"
    + "| #B | W2 | Core | Blocked gold rush | High | #A | Low | "
    "⏳ Pendente | - |\n"
)

TODO_WIP_PIN = (
    "# WIP pin fixture\n\n"
    + HEADER_9
    + "| #01 | W1 | Core | Finished foundation | High | - | Medium | "
    "✅ Concluído | yes |\n"
    + "| #02 | W1 | Core | Active WIP peer | High | - | Medium | "
    "🔄 Em andamento | - |\n"
    + "| #04 | W1 | Core | Idle peer same level | High | - | Low | "
    "⏳ Pendente | - |\n"
)


def test_full_without_scores_keeps_orig_order(tmp_path):
    """Candidato com bv sozinho: peers sem score => ordem original da cadeia."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#04",
        candidate_id="cand-wsjf-alone",
        description="Calibrate the end-of-line camera",
        dependencies=["#03"],
        prereq="#03",
        grupo="Safety",
        bv=20,
        time_criticality=20,
        risk_reduction=20,
        job_size=1,
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    ids = [
        it["id"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    ]
    assert ids == ["#01", "#02", "#03", "#04"]


def test_full_wsjf_reorders_only_within_level(tmp_path):
    """Duas raizes: #B (WSJF alto) sobe dentro do nivel 0; sem furar topologia."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_TWO_ROOTS)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#C",
        candidate_id="cand-wsjf-level",
        description="Third root at level zero",
        dependencies=[],
        prereq="-",
        grupo="Core",
        bv=5,
        time_criticality=5,
        risk_reduction=5,
        job_size=8,
        peer_scores={
            "#A": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 13,
            },
            "#B": {
                "bv": 20, "time_criticality": 13,
                "risk_reduction": 13, "job_size": 1,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    ids = [
        it["id"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    ]
    # #B (WSJF max) antes de #A no nivel 0; #C tambem nivel 0
    assert ids.index("#B") < ids.index("#A")
    assert set(ids) == {"#A", "#B", "#C"}


def test_full_topology_beats_wsjf_plan_example(tmp_path):
    """TAB-WSJF-003: #A nivel 0 antes de #B nivel 1 mesmo com WSJF 60."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_TOPO_BEATS)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#C",
        candidate_id="cand-topo",
        description="Peer of blocked gold rush",
        dependencies=["#A"],
        prereq="#A",
        grupo="Core",
        bv=8,
        time_criticality=5,
        risk_reduction=3,
        job_size=5,
        peer_scores={
            "#A": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 8,
            },
            "#B": {
                "bv": 20, "time_criticality": 20,
                "risk_reduction": 20, "job_size": 1,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    ids = [
        it["id"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    ]
    assert ids.index("#A") < ids.index("#B")


def test_full_wip_pin_not_preempted_by_higher_wsjf(tmp_path):
    """#02 em 🔄 pinado: peer com WSJF maior no mesmo nivel nao o recua."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_WIP_PIN)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#05",
        candidate_id="cand-wip",
        description="New peer same level",
        dependencies=[],
        prereq="-",
        grupo="Core",
        bv=3,
        time_criticality=3,
        risk_reduction=3,
        job_size=8,
        peer_scores={
            "#01": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 8,
            },
            "#02": {
                "bv": 2, "time_criticality": 2,
                "risk_reduction": 2, "job_size": 13,
            },
            "#04": {
                "bv": 20, "time_criticality": 20,
                "risk_reduction": 20, "job_size": 1,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    ids = [
        it["id"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    ]
    # #02 (WIP) permanece a frente de #04 mesmo com WSJF menor
    assert ids.index("#02") < ids.index("#04")


def test_full_explain_move_in_report_when_position_changes(tmp_path):
    """Report material contem as 3 linhas de explain_move."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_TWO_ROOTS)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#C",
        candidate_id="cand-explain",
        description="Third root",
        dependencies=[],
        prereq="-",
        grupo="Core",
        bv=5,
        time_criticality=5,
        risk_reduction=5,
        job_size=8,
        peer_scores={
            "#A": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 13,
            },
            "#B": {
                "bv": 20, "time_criticality": 13,
                "risk_reduction": 13, "job_size": 1,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    rt = result.report_text
    assert "ITEM #B:" in rt or "ITEM #A:" in rt
    assert "causa:" in rt
    assert "input_material_que_mudou:" in rt


def test_full_explain_move_operator_reflects_wsjf_swap(tmp_path):
    """Swap A(baixo) B(alto): causa de A usa '<' e a de B usa '>'."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_TWO_ROOTS)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#C",
        candidate_id="cand-explain-op",
        description="Third root",
        dependencies=[],
        prereq="-",
        grupo="Core",
        bv=5,
        time_criticality=5,
        risk_reduction=5,
        job_size=8,
        peer_scores={
            "#A": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 13,
            },
            "#B": {
                "bv": 20, "time_criticality": 13,
                "risk_reduction": 13, "job_size": 1,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    rt = result.report_text

    def _causa_for(item_id: str) -> str:
        lines = rt.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"ITEM {item_id}:"):
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].startswith("causa:"):
                        return lines[j]
        return ""

    causa_a = _causa_for("#A")
    causa_b = _causa_for("#B")
    assert causa_a, f"missing causa for #A in:\n{rt}"
    assert causa_b, f"missing causa for #B in:\n{rt}"
    assert "<" in causa_a, causa_a
    assert ">" in causa_b, causa_b
    assert "WSJF" in causa_a and "peer" in causa_a
    assert "WSJF" in causa_b and "peer" in causa_b


def test_full_no_spurious_wsjf_report_when_order_unchanged(tmp_path):
    """Sem peer_scores: report nao usa 'WSJF' como causa."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#04",
        candidate_id="cand-nospur",
        description="No peer scores path",
        dependencies=["#03"],
        prereq="#03",
        grupo="Safety",
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    # causas de topologia/onda ok; proibido "WSJF" como causa
    for line in result.report_text.splitlines():
        if line.startswith("causa:"):
            assert "WSJF" not in line


def test_l0_ignores_wsjf_fields_and_preserves_bytes(tmp_path):
    """L0 + scores altos: raws existentes identicos; append no fim."""
    repo, todo = _repo_com_todo(tmp_path)
    antes = todo.read_text(encoding="utf-8")
    table_antes = L.parse_table(antes)
    raw_antes = {
        it["id"]: table_antes["lines"][it["line_no"]]
        for it in table_antes["items"]
    }
    c = _cand(
        is_local=True, is_scoped=False, is_foundation=False,
        item_id="#04",
        candidate_id="cand-l0-wsjf",
        description="Local only despite high scores",
        bv=20,
        time_criticality=20,
        risk_reduction=20,
        job_size=1,
        peer_scores={
            "#01": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 8,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_LOCAL_INTEGRATION
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    raw_depois = {
        it["id"]: table["lines"][it["line_no"]]
        for it in table["items"] if it["id"] in raw_antes
    }
    for iid, raw in raw_antes.items():
        assert raw_depois[iid] == raw
    ids = [it["id"] for it in table["items"]]
    assert ids[-1] == "#04"


def test_scoped_ignores_wsjf_this_phase(tmp_path):
    """SCOPED + peer_scores invertidos: Kahn/orig; sem reordenar por WSJF."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_SCOPED_CHAIN)
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        item_id="#N3",
        candidate_id="cand-scoped-wsjf",
        description="Scoped should ignore peer_scores",
        dependencies=["#C2"],
        prereq="#C2",
        grupo="Core",
        onda="W3",
        scoped_max_fraction=1.0,
        bv=20,
        time_criticality=20,
        risk_reduction=20,
        job_size=1,
        peer_scores={
            "#C1": {
                "bv": 1, "time_criticality": 1,
                "risk_reduction": 1, "job_size": 13,
            },
            "#C2": {
                "bv": 20, "time_criticality": 20,
                "risk_reduction": 20, "job_size": 1,
            },
            "#D1": {
                "bv": 13, "time_criticality": 13,
                "risk_reduction": 13, "job_size": 1,
            },
        },
    )
    result = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert result.rc == 0, result.error
    assert result.route == I.ROUTE_SCOPED_REORDER, result.report_text
    ids = [
        it["id"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    ]
    # cadeia original D1,C1,C2 se mantém (Kahn+orig); candidato no fim da S
    assert ids.index("#D1") < ids.index("#C1") < ids.index("#C2")
    assert ids.index("#C2") < ids.index("#N3")


def test_json_cli_reads_explicit_scores(tmp_path):
    """--json com bv/tc/rr/job_size preenche o dataclass (dry-run)."""
    repo, todo = _repo_com_todo(tmp_path)
    payload = {
        "candidate_id": "cand-json-wsjf",
        "item_id": "#04",
        "description": "JSON score path",
        "source": "test",
        "fields_complete": True,
        "is_foundation": True,
        "bv": 8,
        "time_criticality": 5,
        "risk_reduction": 3,
        "job_size": 5,
        "peer_scores": {
            "#01": {
                "bv": 2, "time_criticality": 2,
                "risk_reduction": 2, "job_size": 8,
            },
        },
    }
    # dry-run via API do parser (mesmo caminho do CLI)
    class _Args:
        candidate_id = None
        item_id = None
        description = None
        source = None
        evidence = None
        source_item = None
        dep = None
        fields_complete = False
        no_authority = False
        foundation = False
        local = False
        scoped = False
        reason = None
        bv = None
        time_criticality = None
        risk_reduction = None
        job_size = None

    cand = I._candidate_from_args(_Args(), payload)
    assert cand.bv == 8
    assert cand.time_criticality == 5
    assert cand.risk_reduction == 3
    assert cand.job_size == 5
    assert cand.peer_scores["#01"]["bv"] == 2
    result = I.run_intake(todo_path=str(todo), candidate=cand, apply=False)
    assert result.rc == 2
    assert result.route == I.ROUTE_FULL_REORDER


# ---------------------------------------------------------------------------
# TAB-ADD-002 -- dedup por descricao normalizada (mecanico, sem NLP)
# ---------------------------------------------------------------------------

def test_normalize_free_text_strip_collapse_casefold():
    assert I.normalize_free_text("  Foo   BAR \n") == "foo bar"
    assert I.free_text_for_dedup(
        "Wire the conveyor  <!-- intake:cand-x -->"
    ) == "wire the conveyor"


def test_decide_route_duplicate_por_descricao_na_tabela():
    """Mesma descricao (normalizada) de linha existente -> DUPLICATE."""
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    # ROW_B description: "Wire the conveyor belt sensor driver"
    c = _cand(
        item_id="#99",
        description="  wire   the CONVEYOR belt sensor driver  ",
        is_local=True,
    )
    assert I.decide_route(c, table, inbox) == I.ROUTE_DUPLICATE
    eid, kind = I.find_duplicate_match(c, table, inbox)
    assert kind == "description_table"
    assert eid == "#02"


def test_decide_route_descricao_diferente_nao_e_duplicate():
    table = L.parse_table(TODO_BASE)
    inbox = L.inbox_entries(TODO_BASE)
    c = _cand(
        item_id="#99",
        description="Completely different work item about valves",
        is_local=True,
    )
    assert I.decide_route(c, table, inbox) == I.ROUTE_LOCAL_INTEGRATION


def test_decide_route_duplicate_por_descricao_na_inbox_residual():
    table = L.parse_table(TODO_COM_INBOX_RESIDUAL)
    inbox = L.inbox_entries(TODO_COM_INBOX_RESIDUAL)
    c = _cand(
        item_id="#77",
        description="waiting for more evidence",
        is_local=True,
    )
    assert I.decide_route(c, table, inbox) == I.ROUTE_DUPLICATE
    eid, kind = I.find_duplicate_match(c, table, inbox)
    assert kind == "description_inbox"
    assert eid == "#88"


def test_acceptance_compatible_so_quando_ambos_preenchidos():
    assert I._acceptance_compatible("", "x") is True
    assert I._acceptance_compatible("A", "") is True
    assert I._acceptance_compatible("pass tests", "PASS   tests") is True
    assert I._acceptance_compatible("pass tests", "other") is False


# ---------------------------------------------------------------------------
# TAB-INBOX-003/004 --drain
# ---------------------------------------------------------------------------

TODO_DRAIN = (
    TODO_BASE
    + "\n## INBOX (descobertas não priorizadas)\n"
    + "- #50: bare classifiable discovery about seals\n"
    + "- #88: [triage since=2026-08-01 reason=missing-info cycles=0 "
    "source=audit] waiting for more evidence\n"
    + "- #90: [triage since=2026-08-02 reason=needs-leader-decision "
    "cycles=1 source=agent] needs human call on API break\n"
)


def test_drain_dry_run_lista_e_exit_2(tmp_path):
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_DRAIN)
    antes = todo.read_text(encoding="utf-8")
    result = I.run_drain(todo_path=str(todo), apply=False)
    assert result.rc == 2
    assert result.applied is False
    assert result.classifiable_remaining == 1
    assert "classifiable" in result.report_text
    # TAB-CUT-001: linha legada sem [triage] emite legacy_inbox_line
    assert "legacy_inbox_line: '#50'" in result.report_text
    assert "TAB-CUT-001" in result.report_text
    # residual com triage valido NAO gera legacy_inbox_line
    assert "legacy_inbox_line: '#88'" not in result.report_text
    assert todo.read_text(encoding="utf-8") == antes


def test_drain_apply_exige_judgment_para_classifiable(tmp_path):
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_DRAIN)
    result = I.run_drain(todo_path=str(todo), apply=True, judgments={})
    assert result.rc == 1
    assert "classifiable_sem_judgment" in (result.error or "")


def test_drain_apply_integrate_classifiable_e_bump_residual(tmp_path):
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_DRAIN)
    judgments = {
        "#50": {
            "action": "integrate",
            "items": [{
                "candidate_id": "drain-50",
                "item_id": "#50",
                "description": "bare classifiable discovery about seals",
                "source": "audit",
                "fields_complete": True,
                "is_local": True,
                "authority_ok": True,
            }],
        },
    }
    result = I.run_drain(
        todo_path=str(todo), apply=True, judgments=judgments,
    )
    assert result.rc == 0, result.report_text + (result.error or "")
    assert result.applied is True
    assert result.classifiable_remaining == 0
    texto = todo.read_text(encoding="utf-8")
    assert I.classifiable_inbox_count(texto) == 0
    # #50 entrou na tabela
    table = L.parse_table(texto)
    ids = {it["id"] for it in table["items"]}
    assert "#50" in ids
    # residual cycles++ (incluindo needs-leader, sem auto-integrar)
    entries = L.inbox_entries(texto)
    by_id = {e["id"]: e for e in entries}
    assert by_id["#88"]["triage"]["fields"]["cycles"] == "1"
    assert by_id["#90"]["triage"]["fields"]["cycles"] == "2"
    assert by_id["#90"]["triage"]["fields"]["reason"] == "needs-leader-decision"
    # #50 sumiu da INBOX
    assert "#50" not in by_id
    _assert_journal_done(repo, "drain-50")


def test_drain_apply_split_e_keep(tmp_path):
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- FIX-RISCO-1: two concurrency risks bundled\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)
    judgments = {
        "FIX-RISCO-1": {
            "action": "split",
            "items": [
                {
                    "candidate_id": "split-a",
                    "item_id": "FIX-RISCO-A",
                    "description": "TOCTOU window on apply",
                    "source": "audit",
                    "fields_complete": True,
                    "is_local": True,
                    "authority_ok": True,
                },
                {
                    "candidate_id": "split-b",
                    "item_id": "FIX-RISCO-B",
                    "description": "Windows os.replace readonly edge",
                    "source": "audit",
                    "fields_complete": True,
                    "is_local": True,
                    "authority_ok": True,
                },
            ],
        },
    }
    result = I.run_drain(
        todo_path=str(todo), apply=True, judgments=judgments,
    )
    assert result.rc == 0, result.error or result.report_text
    texto2 = todo.read_text(encoding="utf-8")
    assert I.classifiable_inbox_count(texto2) == 0
    ids = {it["id"] for it in L.parse_table(texto2)["items"]}
    assert "FIX-RISCO-A" in ids and "FIX-RISCO-B" in ids
    assert not any(
        e.get("id") == "FIX-RISCO-1" for e in L.inbox_entries(texto2)
    )


def test_drain_cli_dry_run(tmp_path):
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_DRAIN)
    rc = I.main(["--todo", str(todo), "--drain"])
    assert rc == 2


def test_drain_mutation_classifiable_zero_em_var_tmp(tmp_path):
    """Mutation leve: pos-drain, classifiable_count==0 (em /var/tmp via tmp)."""
    # pytest tmp_path ja e isolado; reforca escrita sob /var/tmp se existir
    import pathlib
    base = pathlib.Path("/var/tmp")
    if base.is_dir() and os.access(base, os.W_OK):
        root = base / f"tab_drain_mut_{os.getpid()}"
        root.mkdir(exist_ok=True)
        try:
            repo, todo = _repo_com_todo(root, texto=TODO_DRAIN)
            judgments = {
                "#50": {
                    "action": "integrate",
                    "items": [{
                        "candidate_id": "mut-50",
                        "item_id": "#50",
                        "description": "bare classifiable discovery about seals",
                        "source": "test",
                        "fields_complete": True,
                        "is_local": True,
                        "authority_ok": True,
                    }],
                },
            }
            r = I.run_drain(
                todo_path=str(todo), apply=True, judgments=judgments,
            )
            assert r.rc == 0
            assert I.classifiable_inbox_count(
                todo.read_text(encoding="utf-8")
            ) == 0
        finally:
            # nao apagar a forca; deixar o SO limpar /var/tmp
            pass
    else:
        repo, todo = _repo_com_todo(tmp_path, texto=TODO_DRAIN)
        judgments = {
            "#50": {
                "action": "integrate",
                "items": [{
                    "candidate_id": "mut-50",
                    "item_id": "#50",
                    "description": "bare classifiable discovery about seals",
                    "source": "test",
                    "fields_complete": True,
                    "is_local": True,
                    "authority_ok": True,
                }],
            },
        }
        r = I.run_drain(
            todo_path=str(todo), apply=True, judgments=judgments,
        )
        assert r.rc == 0
        assert I.classifiable_inbox_count(
            todo.read_text(encoding="utf-8")
        ) == 0


# ---------------------------------------------------------------------------
# TAB-INBOX-005 -- drain nao apaga INBOX antes do intake
# ---------------------------------------------------------------------------

def test_drain_intake_fail_preserva_inbox_e_todo_byte_igual(tmp_path):
    """Intake falha (item_id vazio em L0) -> TODO byte-identico; sem journal DONE.

    Regressao do AUD-EXTREME Q14: strip-before-intake apagava a linha e
    applied=False mentia. Mutation: se strip voltar a preceder intake, falha.
    """
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- LEGACY-1: old inbox line without triage metadata\n"
        + "- #88: [triage since=2026-08-01 reason=missing-info cycles=0 "
        "source=audit] waiting for more evidence\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)
    antes = todo.read_text(encoding="utf-8")
    judgments = {
        "LEGACY-1": {
            "action": "integrate",
            "items": [{
                "candidate_id": "drain-legacy-no-id",
                # sem item_id: LOCAL_INTEGRATION aborta antes de journal/write
                "description": "distinct desc so not description-dup",
                "source": "audit",
                "fields_complete": True,
                "is_local": True,
                "authority_ok": True,
            }],
        },
    }
    result = I.run_drain(
        todo_path=str(todo), apply=True, judgments=judgments,
    )
    assert result.rc == 1, result.report_text
    assert result.applied is False
    assert "item_id" in (result.error or "").lower() or "item_id" in (
        result.report_text or ""
    ).lower()
    depois = todo.read_text(encoding="utf-8")
    assert depois == antes, (
        "TODO mutado apesar de intake falhar -- strip-before-intake?"
    )
    entries = L.inbox_entries(depois)
    by_id = {e.get("id"): e for e in entries}
    assert "LEGACY-1" in by_id
    assert by_id["LEGACY-1"].get("classifiable") is True
    # residual nao deve ter sido bumped (cycles permanece 0)
    assert by_id["#88"]["triage"]["fields"]["cycles"] == "0"
    jdir = repo / ".tab_pendencias" / "intake-journal"
    if jdir.is_dir():
        assert not list(jdir.glob("*drain-legacy-no-id*DONE*"))
        assert not list(jdir.glob("*DONE*drain-legacy*"))
        # nenhum DONE para este candidato
        for p in jdir.iterdir():
            assert "drain-legacy-no-id" not in p.name or "DONE" not in p.name.upper()


def test_drain_l0_bom_tira_classifiable_e_entra_tabela(tmp_path):
    """Happy path L0: linha sai da INBOX e entra na tabela (TAB-INBOX-005)."""
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- LEGACY-2: cutover classifiable line for happy path\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)
    judgments = {
        "LEGACY-2": {
            "action": "integrate",
            "items": [{
                "candidate_id": "drain-legacy-ok",
                "item_id": "LEGACY-2",
                "description": "cutover classifiable line for happy path",
                "source": "audit",
                "fields_complete": True,
                "is_local": True,
                "authority_ok": True,
            }],
        },
    }
    result = I.run_drain(
        todo_path=str(todo), apply=True, judgments=judgments,
    )
    assert result.rc == 0, result.error or result.report_text
    assert result.applied is True
    texto2 = todo.read_text(encoding="utf-8")
    assert I.classifiable_inbox_count(texto2) == 0
    ids = {it["id"] for it in L.parse_table(texto2)["items"]}
    assert "LEGACY-2" in ids
    assert not any(
        e.get("id") == "LEGACY-2" for e in L.inbox_entries(texto2)
    )
    _assert_journal_done(repo, "drain-legacy-ok")


def test_drain_split_segundo_filho_falha_preserva_origem(tmp_path):
    """Split: 1o filho OK, 2o falha -> origem ainda na INBOX; 1o na tabela."""
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- BUNDLE-1: two risks that must split\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)
    judgments = {
        "BUNDLE-1": {
            "action": "split",
            "items": [
                {
                    "candidate_id": "split-ok",
                    "item_id": "BUNDLE-A",
                    "description": "first risk ok",
                    "source": "audit",
                    "fields_complete": True,
                    "is_local": True,
                    "authority_ok": True,
                },
                {
                    "candidate_id": "split-bad",
                    # sem item_id -> falha L0
                    "description": "second risk missing id",
                    "source": "audit",
                    "fields_complete": True,
                    "is_local": True,
                    "authority_ok": True,
                },
            ],
        },
    }
    result = I.run_drain(
        todo_path=str(todo), apply=True, judgments=judgments,
    )
    assert result.rc == 1
    texto2 = todo.read_text(encoding="utf-8")
    ids = {it["id"] for it in L.parse_table(texto2)["items"]}
    assert "BUNDLE-A" in ids  # sucesso parcial na tabela
    # origem ainda na INBOX (nao stripada porque o grupo nao fechou)
    assert any(e.get("id") == "BUNDLE-1" for e in L.inbox_entries(texto2))
    assert "BUNDLE-B" not in ids
