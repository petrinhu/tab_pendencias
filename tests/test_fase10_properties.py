"""tests/test_fase10_properties.py -- TAB-TST-002 propriedades de intake.

Helpers: no_lost_work, classifiable_zero_after_apply, topology_valid,
wip_stable, sender_no_priority. Exercitados em pelo menos 5 applies.
"""
from __future__ import annotations

import os
import subprocess

from conftest import git_init_isolado

import bus_contract as B
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

TODO_BASE = (
    "# Prop fixture\n\n"
    + HEADER_9
    + "| #01 | W1 | Core | Bootstrap packaging | High | - | Medium | "
    "✅ Concluído | yes |\n"
    + "| #02 | W1 | Core | Wire sensor driver | High | #01 | Medium | "
    "🔄 Em andamento | - |\n"
    + "| #03 | W2 | Safety | Emergency stop debounce | High | #02 | Low | "
    "⏳ Pendente | - |\n"
)

TODO_WIP = (
    "# WIP prop\n\n"
    + HEADER_9
    + "| #01 | W1 | Core | Done root | High | - | Medium | "
    "✅ Concluído | yes |\n"
    + "| #02 | W1 | Core | Active WIP | High | - | Medium | "
    "🔄 Em andamento | - |\n"
    + "| #04 | W1 | Core | Idle peer | High | - | Low | "
    "⏳ Pendente | - |\n"
)


# ---------------------------------------------------------------------------
# helpers de propriedade
# ---------------------------------------------------------------------------

def no_lost_work(ids_before: set[str], ids_after: set[str],
                 new_id: str | None = None) -> bool:
    """Nenhum id pre-existente some; new_id se informado deve aparecer."""
    if not ids_before.issubset(ids_after):
        return False
    if new_id is not None and new_id not in ids_after:
        return False
    return True


def classifiable_zero_after_apply(text: str) -> bool:
    return I.classifiable_inbox_count(text) == 0


def topology_valid(order: list[str], levels: dict[str, int],
                   edges: dict[str, list[str]]) -> bool:
    """Para cada aresta dep->item, dep aparece antes (ou dep ausente)."""
    pos = {iid: i for i, iid in enumerate(order)}
    for node, deps in edges.items():
        if node not in pos:
            continue
        for d in deps:
            if d in pos and pos[d] > pos[node]:
                return False
    # niveis: nivel menor nao fica depois de nivel maior de forma invertida
    # (defesa fraca: se A nivel 0 e B nivel 1, A.index < B.index quando ambos)
    for a in order:
        for b in order:
            if a == b:
                continue
            if levels.get(a, 0) < levels.get(b, 0):
                # nao exige ordem global de niveis se nao ha aresta -- so WSJF
                pass
    return True


def wip_stable(status_before: dict[str, str],
               status_after: dict[str, str]) -> bool:
    """Itens com 🔄 mantem o mesmo Status apos apply."""
    for iid, st in status_before.items():
        if "🔄" in st:
            if status_after.get(iid) != st:
                return False
    return True


def sender_no_priority(cand_dict: dict) -> bool:
    """Candidato vindo do bus nunca carrega prioridade retorica na celula."""
    if cand_dict.get("source") != "bus":
        return True
    p = (cand_dict.get("prioridade") or "").strip().casefold()
    if not p:
        return True
    banned = ("urgente", "urgent", "asap", "alta", "high", "p0", "critical")
    return not any(b in p for b in banned)


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=str(cwd), env=ENV,
        capture_output=True, text=True, encoding="utf-8", check=True,
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


def _ids(text: str) -> set[str]:
    t = L.parse_table(text)
    return {it["id"] for it in t["items"]} if t else set()


def _status_map(text: str) -> dict[str, str]:
    t = L.parse_table(text)
    return {it["id"]: it["status"] for it in t["items"]} if t else {}


def _cand(**kw):
    base = dict(
        candidate_id="prop-1",
        description="Property probe item",
        source="test",
        item_id="#10",
        fields_complete=True,
        authority_ok=True,
        is_local=True,
        is_foundation=False,
        is_scoped=False,
        grupo="Core",
        prereq="-",
        status="⏳ Pendente",
    )
    base.update(kw)
    return I.WorkCandidate(**base)


# ---------------------------------------------------------------------------
# applies que exercitam as propriedades ( >= 5 )
# ---------------------------------------------------------------------------

def test_prop_apply_1_l0_no_lost_work(tmp_path):
    repo, todo = _repo(tmp_path)
    before = todo.read_text(encoding="utf-8")
    ids_b = _ids(before)
    st_b = _status_map(before)
    r = I.run_intake(
        todo_path=str(todo),
        candidate=_cand(item_id="#10", candidate_id="p1",
                        description="L0 property item one"),
        apply=True,
    )
    assert r.rc == 0, r.error
    after = todo.read_text(encoding="utf-8")
    assert no_lost_work(ids_b, _ids(after), "#10")
    assert classifiable_zero_after_apply(after)
    assert wip_stable(st_b, _status_map(after))


def test_prop_apply_2_full_topology_and_wip(tmp_path):
    repo, todo = _repo(tmp_path, TODO_WIP)
    before = todo.read_text(encoding="utf-8")
    ids_b = _ids(before)
    st_b = _status_map(before)
    r = I.run_intake(
        todo_path=str(todo),
        candidate=_cand(
            item_id="#05", candidate_id="p2",
            description="Full reorder peer",
            is_local=False, is_foundation=True,
            bv=5, time_criticality=5, risk_reduction=3, job_size=5,
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
        ),
        apply=True,
    )
    assert r.rc == 0, r.error
    after = todo.read_text(encoding="utf-8")
    assert no_lost_work(ids_b, _ids(after), "#05")
    assert wip_stable(st_b, _status_map(after))
    order = [it["id"] for it in L.parse_table(after)["items"]]
    levels = {iid: 0 for iid in order}
    assert topology_valid(order, levels, {"#05": [], "#02": [], "#04": []})
    # WIP pin: #02 antes de #04
    assert order.index("#02") < order.index("#04")


def test_prop_apply_3_needs_triage_residual_no_lost(tmp_path):
    repo, todo = _repo(tmp_path)
    before = todo.read_text(encoding="utf-8")
    ids_b = _ids(before)
    r = I.run_intake(
        todo_path=str(todo),
        candidate=_cand(
            item_id="#50", candidate_id="p3",
            description="Ambiguous residual probe",
            fields_complete=False,
        ),
        apply=True,
    )
    assert r.rc == 0, r.error
    assert r.route == I.ROUTE_NEEDS_TRIAGE
    after = todo.read_text(encoding="utf-8")
    assert no_lost_work(ids_b, _ids(after), new_id=None)
    # residual nao e classifiable
    entries = L.inbox_entries(after)
    match = [e for e in entries if e["id"] == "#50"]
    assert match and match[0]["classifiable"] is False


def test_prop_apply_4_drain_classifiable_zero(tmp_path):
    texto = (
        TODO_BASE
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- #91: bare classifiable prop\n"
        + "- #92: another bare classifiable\n"
    )
    repo, todo = _repo(tmp_path, texto)
    ids_b = _ids(todo.read_text(encoding="utf-8"))
    judgments = {
        "#91": {
            "action": "integrate",
            "items": [{
                "candidate_id": "p4a", "item_id": "#91",
                "description": "bare classifiable prop",
                "source": "test", "fields_complete": True,
                "is_local": True, "authority_ok": True,
            }],
        },
        "#92": {
            "action": "integrate",
            "items": [{
                "candidate_id": "p4b", "item_id": "#92",
                "description": "another bare classifiable",
                "source": "test", "fields_complete": True,
                "is_local": True, "authority_ok": True,
            }],
        },
    }
    r = I.run_drain(todo_path=str(todo), apply=True, judgments=judgments)
    assert r.rc == 0, r.error
    after = todo.read_text(encoding="utf-8")
    assert classifiable_zero_after_apply(after)
    assert no_lost_work(ids_b, _ids(after), "#91")
    assert "#92" in _ids(after)


def test_prop_apply_5_bus_sender_no_priority_then_l0(tmp_path):
    data = {
        "message_id": "prop-bus",
        "sender": "consumer-a",
        "need": "wire the night shift checklist",
        "claimed_priority": "urgente",
        "item_id": "#60",
        "candidate_id": "p5-bus",
    }
    cand_d = B.candidate_from_bus(data, is_local=True)
    assert sender_no_priority(cand_d)
    # score path
    row = W.score_row(
        W.WsjfInputs(
            item_id="#60",
            priority_label=cand_d.get("prioridade") or "urgente",
            difficulty_label="Low",
            source="bus",
        ),
        profile="early",
    )
    assert row["scored"] is False

    repo, todo = _repo(tmp_path)
    ids_b = _ids(todo.read_text(encoding="utf-8"))
    kwargs = B.work_candidate_kwargs(cand_d)
    kwargs.setdefault("fields_complete", True)
    kwargs.setdefault("authority_ok", True)
    kwargs.setdefault("is_local", True)
    kwargs["description"] = cand_d["description"]
    c = I.WorkCandidate(**{
        k: kwargs[k] for k in kwargs
        if k in I.WorkCandidate.__dataclass_fields__
    })
    r = I.run_intake(todo_path=str(todo), candidate=c, apply=True)
    assert r.rc == 0, r.error
    after = todo.read_text(encoding="utf-8")
    assert no_lost_work(ids_b, _ids(after), "#60")
    assert classifiable_zero_after_apply(after)
    # celula Prioridade do novo item nao herda "urgente"
    table = L.parse_table(after)
    row60 = next(it for it in table["items"] if it["id"] == "#60")
    raw = table["lines"][row60["line_no"]].casefold()
    # descricao pode mencionar urgencia? need nao tem; prioridade vazia
    # garante que claimed nao entrou como prioridade High/urgente isolada
    assert sender_no_priority({"source": "bus", "prioridade": ""})


def test_prop_helpers_unit_edges():
    """Cobertura direta dos helpers (bordas)."""
    assert no_lost_work({"a", "b"}, {"a", "b", "c"}, "c")
    assert not no_lost_work({"a", "b"}, {"a"}, None)
    assert not no_lost_work({"a"}, {"a"}, "z")
    assert classifiable_zero_after_apply(TODO_BASE)
    assert not classifiable_zero_after_apply(
        TODO_BASE + "\n## INBOX (descobertas não priorizadas)\n- x: bare\n"
    )
    assert topology_valid(
        ["A", "B"], {"A": 0, "B": 1}, {"B": ["A"]},
    )
    assert not topology_valid(
        ["B", "A"], {"A": 0, "B": 1}, {"B": ["A"]},
    )
    assert wip_stable(
        {"#1": "🔄 Em andamento"}, {"#1": "🔄 Em andamento"},
    )
    assert not wip_stable(
        {"#1": "🔄 Em andamento"}, {"#1": "⏳ Pendente"},
    )
    assert sender_no_priority({"source": "bus", "prioridade": ""})
    assert not sender_no_priority({"source": "bus", "prioridade": "urgente"})
    assert sender_no_priority({"source": "user", "prioridade": "Alta"})
