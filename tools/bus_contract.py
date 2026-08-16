#!/usr/bin/env python3
# tools/bus_contract.py -- contrato mecanico bus -> WorkCandidate (TAB-BUS-*)
# Copyright (C) 2026 Petrus Silva Costa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
tools/bus_contract.py -- bus transporta FATOS, nao ranking (TAB-BUS-001..004).

Fronteira:
  - extrai necessidade, uso/evidencia, prazo factual e deps;
  - ``claimed_priority`` e prosa retorica ("urgente", "ASAP", "quando der")
    **NUNCA** viram score nem celula Prioridade;
  - ``time_criticality`` so entra se for int Fibonacci explicito
    (1,2,3,5,8,13,20) -- nunca inferido de texto;
  - ``candidate_from_bus`` devolve dict compativel com WorkCandidate
    (source="bus");
  - ``archive_allowed`` so e True quando o pedido ficou rastreavel
    (item/dup/residual com motivo / leader), nunca por "li a mensagem".

stdlib only. Nao importa todo_intake em tempo de import de ciclo; usa strings
de rota estaveis. Excecoes de dominio (fluxo especial de um remetente)
ficam FORA deste nucleo -- o caller decide apos extract_facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Alinhado a tools/wsjf.FIB_SCALE -- literal aqui para o teste poder mutar
# wsjf sem quebrar a regra do bus (e para nao forcar import de wsjf).
FIB_SCALE: tuple[int, ...] = (1, 2, 3, 5, 8, 13, 20)

# Rotas que, apos processamento, deixam rastro no TODO (TAB-BUS-002).
_TRACKABLE_ROUTES = frozenset({
    "DUPLICATE",
    "LOCAL_INTEGRATION",
    "SCOPED_REORDER",
    "FULL_REORDER",
    "NEEDS_TRIAGE",
    "NEEDS_LEADER_DECISION",
})

# Rotas mutativas exigem apply=True para o rastro existir em disco.
_MUTATIVE_ROUTES = frozenset({
    "LOCAL_INTEGRATION",
    "SCOPED_REORDER",
    "FULL_REORDER",
    "NEEDS_TRIAGE",
    "NEEDS_LEADER_DECISION",
})

# Rotulos retoricos comuns -- nunca pontuam (lista de deteccao, nao de score).
_RHETORICAL = frozenset({
    "urgente", "urgent", "asap", "critical", "critico", "crítico",
    "quando der", "high", "alta", "baixa", "media", "média", "low", "medium",
    "p0", "p1", "blocker", "bloqueante",
})

_INT_RE = re.compile(r"^-?\d+$")


@dataclass
class BusMessage:
    """Mensagem sintetica de bus (agnostica a transporte real).

    Campos livres podem vir de JSON do inbox do bus. Nada aqui e score.
    """
    message_id: str
    sender: str = ""
    body: str = ""
    need: str = ""
    evidence: str = ""
    deadline_fact: str = ""
    claimed_priority: str = ""
    time_criticality: Any = None
    business_value: Any = None
    risk_reduction: Any = None
    job_size: Any = None
    dependencies: list = field(default_factory=list)
    item_id: str = ""
    candidate_id: str = ""
    extra: dict = field(default_factory=dict)


def _as_fib_int(value: Any) -> int | None:
    """So aceita membro exato de FIB_SCALE (int ou str decimal)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        s = value.strip()
        if not _INT_RE.match(s):
            return None
        n = int(s)
    elif isinstance(value, int):
        n = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None
        n = int(value)
    else:
        return None
    if n in FIB_SCALE:
        return n
    return None


def _is_rhetorical_priority(text: str | None) -> bool:
    if not text:
        return False
    s = str(text).strip().casefold()
    if s in _RHETORICAL:
        return True
    # "urgente!!!" / "URGENT please"
    for token in re.split(r"[\s,;:|/]+", s):
        t = token.strip("!.?")
        if t in _RHETORICAL:
            return True
    return False


def bus_message_from_dict(data: dict) -> BusMessage:
    """Constroi BusMessage a partir de dict/JSON de corpus."""
    if not isinstance(data, dict):
        raise TypeError("bus message deve ser dict")
    deps = data.get("dependencies") or data.get("deps") or []
    if isinstance(deps, str):
        deps = [d.strip() for d in deps.split(",") if d.strip()]
    return BusMessage(
        message_id=str(data.get("message_id") or data.get("id") or ""),
        sender=str(data.get("sender") or data.get("from") or ""),
        body=str(data.get("body") or data.get("text") or ""),
        need=str(data.get("need") or data.get("request") or ""),
        evidence=str(data.get("evidence") or ""),
        deadline_fact=str(
            data.get("deadline_fact") or data.get("deadline") or ""
        ),
        claimed_priority=str(
            data.get("claimed_priority")
            or data.get("priority")
            or data.get("priority_label")
            or ""
        ),
        time_criticality=data.get("time_criticality", data.get("tc")),
        business_value=data.get("business_value", data.get("bv")),
        risk_reduction=data.get("risk_reduction", data.get("rr")),
        job_size=data.get("job_size", data.get("js")),
        dependencies=list(deps),
        item_id=str(data.get("item_id") or data.get("item_id_suggestion") or ""),
        candidate_id=str(data.get("candidate_id") or ""),
        extra={
            k: v for k, v in data.items()
            if k not in {
                "message_id", "id", "sender", "from", "body", "text", "need",
                "request", "evidence", "deadline_fact", "deadline",
                "claimed_priority", "priority", "priority_label",
                "time_criticality", "tc", "business_value", "bv",
                "risk_reduction", "rr", "job_size", "js", "dependencies",
                "deps", "item_id", "item_id_suggestion", "candidate_id",
            }
        },
    )


def extract_facts(msg: BusMessage | dict) -> dict:
    """Extrai fatos usaveis no intake. Nunca promove retorica a score.

    Chaves estaveis do retorno:
      need, evidence, deadline_fact, dependencies, item_id, sender,
      message_id, claimed_priority (eco, so auditoria),
      time_criticality (int fib ou None),
      business_value, risk_reduction, job_size (idem),
      rhetorical_priority_ignored (bool)
    """
    if isinstance(msg, dict):
        msg = bus_message_from_dict(msg)
    if not isinstance(msg, BusMessage):
        raise TypeError("extract_facts espera BusMessage ou dict")

    need = (msg.need or "").strip()
    if not need:
        # fallback: primeira linha do body sem prefixos de urgencia
        body = (msg.body or "").strip()
        if body:
            line = body.splitlines()[0].strip()
            # remove "URGENT:" / "urgente -" so do prefixo
            line = re.sub(
                r"^(urgent(e)?|asap|critical|cr[ií]tico)\s*[:\-]?\s*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            need = line

    tc = _as_fib_int(msg.time_criticality)
    bv = _as_fib_int(msg.business_value)
    rr = _as_fib_int(msg.risk_reduction)
    js = _as_fib_int(msg.job_size)

    rhetorical = _is_rhetorical_priority(msg.claimed_priority)
    # body com "urgente" sozinho nao vira claimed, mas se claimed_priority
    # vazio e body grita, ainda marcamos ignored=False (nao havia claim).
    if not rhetorical and msg.claimed_priority:
        # valor nao-vazio que nao e fib e nao e lista retorica conhecida:
        # ainda assim NUNCA pontua -- tratar como claim ignorado.
        rhetorical = True

    return {
        "message_id": (msg.message_id or "").strip(),
        "sender": (msg.sender or "").strip(),
        "need": need,
        "evidence": (msg.evidence or "").strip(),
        "deadline_fact": (msg.deadline_fact or "").strip(),
        "dependencies": list(msg.dependencies or []),
        "item_id": (msg.item_id or "").strip(),
        "claimed_priority": (msg.claimed_priority or "").strip(),
        "rhetorical_priority_ignored": bool(
            rhetorical or (msg.claimed_priority or "").strip()
        ),
        "time_criticality": tc,
        "business_value": bv,
        "risk_reduction": rr,
        "job_size": js,
        # eco do body so para journal/auditoria -- nunca score
        "body_excerpt": ((msg.body or "").strip()[:200]),
    }


def candidate_from_bus(
    msg: BusMessage | dict,
    *,
    candidate_id: str | None = None,
    fields_complete: bool | None = None,
    authority_ok: bool = True,
    is_local: bool = False,
    is_scoped: bool = False,
    is_foundation: bool = False,
) -> dict:
    """Dict compativel com ``todo_intake.WorkCandidate`` (source='bus').

    Nunca preenche ``prioridade`` a partir de claimed_priority / "urgente".
    Scores WSJF so com ints fib explicitos do payload.
    """
    facts = extract_facts(msg)
    cid = (candidate_id or "").strip()
    if not cid:
        if isinstance(msg, dict):
            cid = str(msg.get("candidate_id") or "").strip()
        elif isinstance(msg, BusMessage):
            cid = (msg.candidate_id or "").strip()
    if not cid:
        mid = facts["message_id"] or "bus"
        cid = f"bus-{mid}"

    desc = facts["need"] or facts["body_excerpt"] or "(empty bus need)"
    # evidencia: prefer field; senao message_id+sender
    evidence = facts["evidence"]
    if not evidence:
        bits = [b for b in (facts["sender"], facts["message_id"]) if b]
        evidence = "bus:" + ("/".join(bits) if bits else "unknown")

    # fields_complete: default True so se need + (evidence ou item_id)
    if fields_complete is None:
        fields_complete = bool(facts["need"]) and bool(
            facts["evidence"] or facts["item_id"]
        )

    out = {
        "candidate_id": cid,
        "description": desc,
        "source": "bus",
        "evidence": evidence,
        "source_item": "",
        "dependencies": list(facts["dependencies"]),
        "item_id": facts["item_id"],
        "prioridade": "",  # NUNCA claimed_priority
        "dificuldade": "",
        "fields_complete": bool(fields_complete),
        "authority_ok": bool(authority_ok),
        "is_foundation": bool(is_foundation),
        "is_local": bool(is_local),
        "is_scoped": bool(is_scoped),
        "bv": facts["business_value"],
        "time_criticality": facts["time_criticality"],
        "risk_reduction": facts["risk_reduction"],
        "job_size": facts["job_size"],
        # meta de auditoria (WorkCandidate ignora kwargs extras se construido
        # via campos conhecidos; callers que serializam JSON podem guardar)
        "_bus_message_id": facts["message_id"],
        "_bus_sender": facts["sender"],
        "_bus_deadline_fact": facts["deadline_fact"],
        "_bus_claimed_priority_ignored": facts["claimed_priority"] or None,
    }
    return out


def work_candidate_kwargs(cand: dict) -> dict:
    """Filtra chaves que ``todo_intake.WorkCandidate`` aceita."""
    allowed = {
        "candidate_id", "description", "source", "evidence", "source_item",
        "dependencies", "item_id", "onda", "grupo", "prioridade", "dificuldade",
        "prereq", "status", "estado_auditado", "fields_complete",
        "authority_ok", "is_foundation", "is_local", "is_scoped", "reason",
        "acceptance", "scoped_max_fraction", "bv", "time_criticality",
        "risk_reduction", "job_size", "peer_scores", "wsjf_profile",
        "comparable_epsilon",
    }
    return {k: v for k, v in cand.items() if k in allowed}


def archive_allowed(
    route: str | None,
    *,
    applied: bool = False,
    error: str | None = None,
    requires_work: bool = True,
) -> bool:
    """True se a mensagem pode ser arquivada como processada (TAB-BUS-002).

    Pedido que exige trabalho futuro so arquiva quando o rastro existe:
    - DUPLICATE (ligacao explicita a item existente) -- apply opcional;
    - LOCAL/SCOPED/FULL aplicados (item no TODO);
    - NEEDS_TRIAGE / NEEDS_LEADER_DECISION aplicados (residual com motivo).

    ``requires_work=False``: mensagem informativa sem pedido de trabalho
    futuro -- archive livre se nao houver erro (ex.: ack puro). O default
    assume que ha pedido de trabalho.
    """
    if error:
        return False
    if not requires_work:
        return True
    r = (route or "").strip().upper()
    if r not in _TRACKABLE_ROUTES:
        return False
    if r == "DUPLICATE":
        return True
    if r in _MUTATIVE_ROUTES:
        return bool(applied)
    return False
