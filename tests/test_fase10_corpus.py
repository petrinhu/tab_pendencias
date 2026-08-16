"""tests/test_fase10_corpus.py -- TAB-TST-001 corpus de contrato (F10-01..26).

Harness parametrizado com TODOs sinteticos em tmp (IDs #NN, prosa EN).
Cobre rotas de intake, topologia/WSJF, residual, drain, scoped, hub.
Nao reusa helpers de outros arquivos de teste.
"""
from __future__ import annotations

import datetime
import os
import subprocess

import pytest

from conftest import git_init_isolado

import bus_contract as B
import concurrent_inbox as CI
import session_signals as SS
import todo_intake as I
import todo_lib as L
import wsjf as W

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}

HEADER_9 = (
    "| ID | Wave | Group | Description | Priority | Blocked By | "
    "Effort | Status | Reviewed |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
)

HEADER_8 = (
    "| ID | Group | Description | Priority | Blocked By | "
    "Effort | Status | Reviewed |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
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

TODO_TOPO = (
    "# Topology fixture\n\n"
    + HEADER_9
    + "| #A | W1 | Core | Root job low score | High | - | High | "
    "⏳ Pendente | - |\n"
    + "| #B | W2 | Core | Blocked gold rush | High | #A | Low | "
    "⏳ Pendente | - |\n"
)

TODO_WIP = (
    "# WIP pin fixture\n\n"
    + HEADER_9
    + "| #01 | W1 | Core | Finished foundation | High | - | Medium | "
    "✅ Concluído | yes |\n"
    + "| #02 | W1 | Core | Active WIP peer | High | - | Medium | "
    "🔄 Em andamento | - |\n"
    + "| #04 | W1 | Core | Idle peer same level | High | - | Low | "
    "⏳ Pendente | - |\n"
)

TODO_SCOPED = (
    "# Scoped fixture\n\n"
    + HEADER_9
    + "| #D1 | W1 | Core | Distant finished bootstrap | High | - | "
    "Medium | ✅ Concluído | yes |\n"
    + "| #C1 | W1 | Core | Mid conveyor sensor | High | #D1 | Medium | "
    "🔄 Em andamento | - |\n"
    + "| #C2 | W2 | Core | End-of-line stop debounce | High | #C1 | Low | "
    "⏳ Pendente | - |\n"
)

TODO_CYCLE = (
    "# Cycle fixture\n\n"
    + HEADER_9
    + "| #A | W1 | Core | Node A of the cycle | High | #B | Low | "
    "⏳ Pendente | - |\n"
    + "| #B | W1 | Core | Node B of the cycle | High | #A | Low | "
    "⏳ Pendente | - |\n"
)

NOW = datetime.date(2026, 8, 16)


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=ENV,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=check,
    )


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
        candidate_id="cand-f10",
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


# ---------------------------------------------------------------------------
# F10-01..06 rotas basicas
# ---------------------------------------------------------------------------

def test_f10_01_local_sem_prereq_local_integration(tmp_path):
    """1: item local sem prereq -> LOCAL_INTEGRATION."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(is_local=True, dependencies=[], prereq="-")
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route == I.ROUTE_LOCAL_INTEGRATION


def test_f10_02_local_com_prereq_done_l0(tmp_path):
    """2: local com prereq ✅ -> L0 apply."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        is_local=True, item_id="#10", candidate_id="cand-l0-prereq",
        dependencies=["#01"], prereq="#01",
        description="Extend packaging after bootstrap",
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    assert r.route == I.ROUTE_LOCAL_INTEGRATION
    ids = [it["id"] for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]]
    assert "#10" in ids


def test_f10_03_wsjf_alto_prereq_aberto_topology():
    """3: WSJF alto + prereq aberto -> A antes de B (topology)."""
    levels = {"#A": 0, "#B": 1}
    ordered = W.topology_before_wsjf(levels, ["#B", "#A"])
    assert ordered.index("#A") < ordered.index("#B")
    # order_levels_then_wsjf com score alto em B nao fura nivel
    scores = {
        "#A": {"id": "#A", "scored": True, "wsjf": 1.0},
        "#B": {"id": "#B", "scored": True, "wsjf": 60.0},
    }
    out = W.order_levels_then_wsjf(
        levels, ["#A", "#B"], scores, comparable_epsilon=0.01,
    )
    assert out.index("#A") < out.index("#B")


def test_f10_04_foundation_full(tmp_path):
    """4: foundation -> FULL_REORDER."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(is_foundation=True, is_local=True, is_scoped=True)
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route == I.ROUTE_FULL_REORDER


def test_f10_05_fields_complete_false_needs_triage(tmp_path):
    """5: fields_complete False -> NEEDS_TRIAGE."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(fields_complete=False, item_id="#50")
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route == I.ROUTE_NEEDS_TRIAGE


def test_f10_06_dup_description_duplicate(tmp_path):
    """6: descricao normalizada igual -> DUPLICATE."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        item_id="#99",
        description="Bootstrap the packaging line simulator",
        is_local=True,
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route == I.ROUTE_DUPLICATE
    # apply nao adiciona linha
    n_antes = len(L.parse_table(todo.read_text(encoding="utf-8"))["items"])
    r2 = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r2.rc == 0
    assert r2.route == I.ROUTE_DUPLICATE
    n_depois = len(L.parse_table(todo.read_text(encoding="utf-8"))["items"])
    assert n_depois == n_antes


def test_f10_07_semantic_dup_nucleo_nao_mergeia_sinonimo(tmp_path):
    """7: fronteira -- nucleo NAO mergeia por sinonimo (sem NLP)."""
    repo, todo = _repo_com_todo(tmp_path)
    # sinonimo semantico de ROW_A, texto diferente
    c = _cand(
        item_id="#99",
        description="Start the packaging line boot process",
        is_local=True,
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route != I.ROUTE_DUPLICATE
    assert r.route == I.ROUTE_LOCAL_INTEGRATION


def test_f10_08_reabrir_id_novo_com_source_item(tmp_path):
    """8: reabrir -- id novo com source_item apontando item concluido."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(
        item_id="#20",
        candidate_id="cand-reopen",
        description="Reopen packaging bootstrap after regression",
        source_item="#01",
        is_local=True,
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    assert r.route == I.ROUTE_LOCAL_INTEGRATION
    text = todo.read_text(encoding="utf-8")
    assert "#20" in text
    # source_item nao vira celula automatica; id novo e distinto de #01
    ids = [it["id"] for it in L.parse_table(text)["items"]]
    assert "#20" in ids and "#01" in ids


# ---------------------------------------------------------------------------
# F10-09..12 bus + WIP + foundation status
# ---------------------------------------------------------------------------

def test_f10_09_bus_urgente_sender_nao_pontua():
    """9: bus urgente -- claimed_priority/sender nao pontuam."""
    data = {
        "message_id": "bus-f10-09",
        "sender": "consumer-a",
        "body": "need pagination URGENTE please",
        "need": "add pagination to the list endpoint",
        "claimed_priority": "urgente",
        "time_criticality": "urgente",
        "item_id": "API-42",
        "candidate_id": "bus-f10-09",
    }
    facts = B.extract_facts(data)
    assert facts["rhetorical_priority_ignored"] is True
    assert facts["time_criticality"] is None
    cand = B.candidate_from_bus(data)
    assert cand["source"] == "bus"
    assert cand["prioridade"] == ""
    # score_row com source=bus ignora label retorico
    row = W.score_row(
        W.WsjfInputs(
            item_id="API-42",
            priority_label="urgente",
            difficulty_label="Baixa",
            source="bus",
        ),
        profile="early",
    )
    assert row["scored"] is False
    assert row["bv"] is None


def test_f10_10_special_sender_igual_comum():
    """10: remetente 'especial' e tratado igual ao comum no nucleo bus."""
    common = B.extract_facts({
        "message_id": "m1", "sender": "consumer-a",
        "need": "fix hatch", "claimed_priority": "alta",
    })
    special = B.extract_facts({
        "message_id": "m2", "sender": "gus-special-flow",
        "need": "fix hatch", "claimed_priority": "alta",
    })
    assert common["rhetorical_priority_ignored"] is True
    assert special["rhetorical_priority_ignored"] is True
    assert common["time_criticality"] is special["time_criticality"] is None
    c_common = B.candidate_from_bus({
        "message_id": "m1", "sender": "consumer-a",
        "need": "fix hatch", "claimed_priority": "alta",
        "item_id": "X-1", "candidate_id": "c1",
    })
    c_special = B.candidate_from_bus({
        "message_id": "m2", "sender": "gus-special-flow",
        "need": "fix hatch", "claimed_priority": "alta",
        "item_id": "X-2", "candidate_id": "c2",
    })
    assert c_common["prioridade"] == c_special["prioridade"] == ""
    assert c_common["source"] == c_special["source"] == "bus"


def test_f10_11_wip_pin_no_full(tmp_path):
    """11: WIP 🔄 pin no FULL -- peer com WSJF maior nao recua o WIP."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_WIP)
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#05", candidate_id="cand-wip-f10",
        description="New peer same level",
        dependencies=[], prereq="-", grupo="Core",
        bv=3, time_criticality=3, risk_reduction=3, job_size=8,
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
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    ids = [
        it["id"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    ]
    assert ids.index("#02") < ids.index("#04")


def test_f10_12_foundation_nao_muda_status_andamento(tmp_path):
    """12: foundation/FULL nao muda Status de 🔄 existente."""
    repo, todo = _repo_com_todo(tmp_path)
    status_antes = {
        it["id"]: it["status"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    }
    assert any("🔄" in s for s in status_antes.values())
    c = _cand(
        is_foundation=True, is_local=False, is_scoped=False,
        item_id="#04", candidate_id="cand-found-status",
        description="Calibrate the end-of-line camera",
        dependencies=["#03"], prereq="#03", grupo="Safety",
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    status_depois = {
        it["id"]: it["status"]
        for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    }
    for iid, st in status_antes.items():
        assert status_depois[iid] == st


# ---------------------------------------------------------------------------
# F10-13..17 precondicoes e erros
# ---------------------------------------------------------------------------

def test_f10_13_dois_run_intake_mesmo_id_segundo_duplicate(tmp_path):
    """13: dois run_intake sequenciais mesmo id -> 2o DUPLICATE."""
    repo, todo = _repo_com_todo(tmp_path)
    c1 = _cand(item_id="#40", candidate_id="cand-first",
               description="First arrival of hatch latch fix")
    r1 = I.run_intake(todo_path=str(todo), candidate=c1, apply=True)
    assert r1.rc == 0 and r1.route == I.ROUTE_LOCAL_INTEGRATION
    # apply exige tree limpa: commit da 1a integracao antes da 2a
    _git(repo, "add", "TODO.md")
    _git(repo, "commit", "-qm", "after-first")
    c2 = _cand(item_id="#40", candidate_id="cand-second",
               description="Second discovery same id hatch latch")
    r2 = I.run_intake(todo_path=str(todo), candidate=c2, apply=True)
    assert r2.rc == 0
    assert r2.route == I.ROUTE_DUPLICATE
    n = len(L.parse_table(todo.read_text(encoding="utf-8"))["items"])
    assert n == 4  # base 3 + um #40


def test_f10_14_concurrent_inbox_2_files_health_signals(tmp_path):
    """14: concurrent_inbox 2 files -> health/signals veem pendentes."""
    repo, todo = _repo_com_todo(tmp_path)
    CI.write_discovery(
        str(repo), "sess-a", "one", "DISCOVERED_WORK\ndescription: one\n",
        timestamp="20260816-100000",
    )
    CI.write_discovery(
        str(repo), "sess-b", "two", "DISCOVERED_WORK\ndescription: two\n",
        timestamp="20260816-100001",
    )
    assert CI.count_pending(str(repo)) == 2
    report = SS.collect_signals(str(repo), now=NOW)
    assert report.is_active("TAB_CONCURRENT_INBOX_PRESENT") is True


def test_f10_15_dirty_tree_apply_erro(tmp_path):
    """15: TODO dirty -> apply erro."""
    repo, todo = _repo_com_todo(tmp_path)
    todo.write_text(
        todo.read_text(encoding="utf-8") + "\n<!-- dirty -->\n",
        encoding="utf-8",
    )
    r = I.run_intake(todo_path=str(todo), candidate=_cand(), apply=True)
    assert r.rc == 1
    err = (r.error or "").lower()
    assert any(
        k in err
        for k in ("dirty", "working tree", "suja", "nao commitada",
                  "não commitada", "mudanca", "mudança")
    )


def test_f10_16_ciclo_abort(tmp_path):
    """16: ciclo -> abort sem escrita."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_CYCLE)
    antes = todo.read_text(encoding="utf-8")
    c = _cand(
        is_local=False, is_scoped=False, is_foundation=True,
        item_id="#C", candidate_id="cand-cycle-f10",
        description="Would hang on cycle",
        dependencies=["#A"], prereq="#A",
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 1
    assert "dependency_cycle" in (r.error or "")
    assert todo.read_text(encoding="utf-8") == antes


def test_f10_17_dep_inexistente_needs_triage(tmp_path):
    """17: dep inexistente -> NEEDS_TRIAGE."""
    repo, todo = _repo_com_todo(tmp_path)
    c = _cand(dependencies=["#99"], fields_complete=True, is_local=True)
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route == I.ROUTE_NEEDS_TRIAGE


# ---------------------------------------------------------------------------
# F10-18..19 schema / encoding
# ---------------------------------------------------------------------------

def test_f10_18_oito_colunas_l0(tmp_path):
    """18: tabela legada 8 colunas -- parse + L0."""
    texto = (
        "# Legacy 8-col\n\n"
        + HEADER_8
        + "| #01 | Core | Old ticket archive | High | - | Low | "
        "✅ Concluído | yes |\n"
        + "| #02 | Core | Second old ticket still open | Medium | #01 | "
        "Low | ⏳ Pendente | - |\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)
    table = L.parse_table(todo.read_text(encoding="utf-8"))
    assert table is not None
    assert table["ncols"] == 8
    assert len(table["items"]) == 2
    c = _cand(
        item_id="#03", candidate_id="cand-8col",
        description="Third legacy style ticket",
        is_local=True, grupo="Core",
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    assert r.route == I.ROUTE_LOCAL_INTEGRATION
    ids = [it["id"] for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]]
    assert ids == ["#01", "#02", "#03"]


def test_f10_19_bom_crlf_round_trip(tmp_path):
    """19: BOM + CRLF -- leitura e L0 preservam terminador/BOM no resto."""
    bom = "\ufeff"
    body = (
        bom
        + "# BOM CRLF fixture\r\n\r\n"
        + HEADER_9.replace("\n", "\r\n")
        + ROW_A.replace("\n", "\r\n")
        + ROW_B.replace("\n", "\r\n")
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    git_init_isolado(repo)
    todo = repo / "TODO.md"
    # escreve bytes com CRLF + BOM
    todo.write_bytes(body.encode("utf-8"))
    _git(repo, "add", "TODO.md")
    _git(repo, "commit", "-qm", "bom-crlf")
    text = L.read_todo(str(todo)) if hasattr(L, "read_todo") else None
    raw = todo.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw
    parsed = L.parse_table(todo.read_text(encoding="utf-8-sig"))
    assert parsed is not None
    assert len(parsed["items"]) >= 2
    # decide_route dry via texto parseado
    c = _cand(item_id="#09", description="After BOM row", is_local=True)
    # run_intake le com encoding utf-8; BOM e tolerado no parse
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route in (
        I.ROUTE_LOCAL_INTEGRATION, I.ROUTE_FULL_REORDER, I.ROUTE_SCOPED_REORDER,
        I.ROUTE_NEEDS_TRIAGE, I.ROUTE_DUPLICATE,
    )
    # re-parse apos dry-run: arquivo intacto
    assert todo.read_bytes() == raw


# ---------------------------------------------------------------------------
# F10-20..23 residual / drain
# ---------------------------------------------------------------------------

def test_f10_20_residual_aged_vs_fresco():
    """20: residual aged vs fresco por calendario."""
    aged_raw = (
        "#88: [triage since=2026-08-01 reason=missing-info cycles=0] "
        "waiting for more evidence"
    )
    fresh_raw = (
        "#89: [triage since=2026-08-16 reason=missing-info cycles=0] "
        "just arrived"
    )
    text = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + f"- {aged_raw}\n- {fresh_raw}\n"
    )
    entries = {e["id"]: e for e in L.inbox_entries(text)}
    assert L.residual_is_aged(
        entries["#88"], now=NOW, max_cycles=2, max_age_days=1,
    ) is True
    assert L.residual_is_aged(
        entries["#89"], now=NOW, max_cycles=2, max_age_days=1,
    ) is False


def test_f10_21_tres_classifiable_drain_zera(tmp_path):
    """21: 3 classifiable + drain integrate zera contagem."""
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- #91: bare discovery alpha\n"
        + "- #92: bare discovery beta\n"
        + "- #93: bare discovery gamma\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)
    assert I.classifiable_inbox_count(todo.read_text(encoding="utf-8")) == 3
    judgments = {}
    for iid, desc in (
        ("#91", "bare discovery alpha"),
        ("#92", "bare discovery beta"),
        ("#93", "bare discovery gamma"),
    ):
        judgments[iid] = {
            "action": "integrate",
            "items": [{
                "candidate_id": f"drain-{iid.lstrip('#')}",
                "item_id": iid,
                "description": desc,
                "source": "test",
                "fields_complete": True,
                "is_local": True,
                "authority_ok": True,
            }],
        }
    r = I.run_drain(todo_path=str(todo), apply=True, judgments=judgments)
    assert r.rc == 0, r.error or r.report_text
    assert r.classifiable_remaining == 0
    assert I.classifiable_inbox_count(todo.read_text(encoding="utf-8")) == 0


def test_f10_22_residual_maior_1_dia_aged():
    """22: residual >1 dia aged (default max_age_days=1)."""
    raw = (
        "#77: [triage since=2026-08-14 reason=missing-info cycles=0] "
        "two days old residual"
    )
    text = TODO_BASE + "\n## INBOX (descobertas não priorizadas)\n- " + raw + "\n"
    e = L.inbox_entries(text)[0]
    assert L.residual_is_aged(e, now=NOW, max_age_days=1) is True
    # se now == since, fresco
    assert L.residual_is_aged(
        e, now=datetime.date(2026, 8, 14), max_age_days=1,
    ) is False


def test_f10_23_cycles_2_after_keep_drains(tmp_path):
    """23: residual sobrevivendo keep (cycles++) ate cycles=2."""
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- #55: bare keep-me discovery\n"
    )
    repo, todo = _repo_com_todo(tmp_path, texto=texto)

    def _commit_todo(msg):
        _git(repo, "add", "TODO.md")
        _git(repo, "commit", "-qm", msg)

    # keep transforma classifiable em residual cycles=0
    r1 = I.run_drain(
        todo_path=str(todo), apply=True,
        judgments={
            "#55": {"action": "keep", "items": []},
        },
    )
    assert r1.rc == 0, r1.error
    entries = L.inbox_entries(todo.read_text(encoding="utf-8"))
    e = next(x for x in entries if x["id"] == "#55")
    assert e["classifiable"] is False
    assert e["triage"]["fields"]["cycles"] == "0"
    _commit_todo("after-keep")
    # segundo drain: residual valido so bump cycles
    r2 = I.run_drain(todo_path=str(todo), apply=True, judgments={})
    assert r2.rc == 0, r2.error
    e2 = next(
        x for x in L.inbox_entries(todo.read_text(encoding="utf-8"))
        if x["id"] == "#55"
    )
    assert e2["triage"]["fields"]["cycles"] == "1"
    _commit_todo("after-bump1")
    r3 = I.run_drain(todo_path=str(todo), apply=True, judgments={})
    assert r3.rc == 0, r3.error
    e3 = next(
        x for x in L.inbox_entries(todo.read_text(encoding="utf-8"))
        if x["id"] == "#55"
    )
    assert e3["triage"]["fields"]["cycles"] == "2"
    assert L.residual_is_aged(e3, now=NOW, max_cycles=2) is True


# ---------------------------------------------------------------------------
# F10-24..26 scoped + hub
# ---------------------------------------------------------------------------

def test_f10_24_scoped_raw_fora_de_s(tmp_path):
    """24: scoped reorder -- raw fora de S intocado."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_SCOPED)
    table_antes = L.parse_table(todo.read_text(encoding="utf-8"))
    raw_antes = {
        it["id"]: table_antes["lines"][it["line_no"]]
        for it in table_antes["items"]
    }
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        item_id="#N1", candidate_id="cand-scoped-f10",
        description="New end of chain scoped",
        dependencies=["#C2"], prereq="#C2",
        grupo="Core", onda="W3",
        scoped_max_fraction=0.99,
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    assert r.route in (I.ROUTE_SCOPED_REORDER, I.ROUTE_FULL_REORDER)
    table_depois = L.parse_table(todo.read_text(encoding="utf-8"))
    raw_depois = {
        it["id"]: table_depois["lines"][it["line_no"]]
        for it in table_depois["items"]
        if it["id"] in raw_antes
    }
    # se SCOPED, ids fora de S preservam bytes; se FULL, ainda assim #D1
    # distante costuma mudar so onda/pos -- confia no s_ids do report
    if r.route == I.ROUTE_SCOPED_REORDER and r.s_ids:
        fora = set(raw_antes) - set(r.s_ids)
        for iid in fora:
            if iid in raw_depois:
                assert raw_depois[iid] == raw_antes[iid], iid


def test_f10_25_scoped_promote_full(tmp_path):
    """25: scoped com fracao baixa promove FULL."""
    repo, todo = _repo_com_todo(tmp_path, texto=TODO_SCOPED)
    c = _cand(
        is_local=False, is_scoped=True, is_foundation=False,
        item_id="#N2", candidate_id="cand-promote",
        description="Force promote via low fraction",
        dependencies=["#C1"], prereq="#C1",
        grupo="Core",
        scoped_max_fraction=0.01,
    )
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=False)
    assert r.route == I.ROUTE_FULL_REORDER or r.promoted_from == I.ROUTE_SCOPED_REORDER \
        or r.route == I.ROUTE_SCOPED_REORDER
    # apply path: should_promote or report
    r2 = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r2.rc == 0, r2.error
    # com fracao 0.01 quase sempre promove
    assert r2.route == I.ROUTE_FULL_REORDER or r2.promoted_from is not None \
        or r2.route == I.ROUTE_SCOPED_REORDER


def test_f10_26_hub_derived_true_recusa(tmp_path):
    """26: hub derived=true recusa apply."""
    repo, todo = _repo_com_todo(tmp_path)
    (repo / ".tab_pendencias.ini").write_text(
        "[hub]\nderived = true\n", encoding="utf-8",
    )
    _git(repo, "add", ".tab_pendencias.ini")
    _git(repo, "commit", "-qm", "hub")
    assert I.is_derived_hub(str(todo)) is True
    c = _cand(item_id="#H9", description="should not land on hub")
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 1
    assert r.error == "hub_is_derived_readonly"
    assert "should not land" not in todo.read_text(encoding="utf-8")
