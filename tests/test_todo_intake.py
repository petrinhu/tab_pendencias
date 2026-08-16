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
