#!/usr/bin/env python3
# tools/wsjf.py -- motor de scoring WSJF (TAB-WSJF-001..007)
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
tools/wsjf.py -- scoring WSJF mecânico (Fase 3 / TAB-WSJF-001..007).

Régua única Fibonacci modificada (1,2,3,5,8,13,20). Profiles early|safe.
Ordenação: nível topológico primeiro; WSJF só dentro do nível, e só se
todos os ids do nível tiverem score computável. Scores não persistem em
células do TODO.md. stdlib only. Não importa todo_intake (evita ciclo).
"""
from __future__ import annotations

import configparser
import functools
import os
import re
from dataclasses import dataclass

FIB_SCALE: tuple[int, ...] = (1, 2, 3, 5, 8, 13, 20)

PROFILES: frozenset[str] = frozenset({"early", "safe"})
DEFAULT_PROFILE: str = "early"

DEFAULT_COMPARABLE_EPSILON_EARLY: float = 0.5
DEFAULT_COMPARABLE_EPSILON_SAFE: float = 0.0

# early: rótulos qualitativos -> um fib (única tabela, documentada).
# Job Size alinhado à adaptação 3 do vault (Baixa=1-2, Média=3-5, Alta=8);
# ponto médio-alto de cada faixa, sempre em FIB_SCALE.
LABEL_TO_FIB: dict[str, int] = {
    "baixa": 2,
    "media": 5,
    "média": 5,
    "alta": 8,
    "low": 2,
    "medium": 5,
    "high": 8,
}

BUS_SOURCES: frozenset[str] = frozenset({"bus"})

_EMPTY_MARKERS = frozenset({"", "—", "-", "--"})
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def normalize_score(value, *, mode: str = "reject") -> int | None:
    """Aceita int/float/str numérico.

    mode='reject' (default safe): só membro exato de FIB_SCALE.
    mode='snap' (default early p/ números): vizinho mais próximo em FIB_SCALE;
              empate de distância (ex.: 4 -> 3 ou 5) ESTABILIZA PARA BAIXO.
    Fora de [1, 20], bool, None, '', '—', '-', '--', não-numérico -> None.
    Nunca trata True como 1.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        s = value.strip()
        if s in _EMPTY_MARKERS:
            return None
        if _INT_RE.match(s):
            num: int | float = int(s)
        elif _FLOAT_RE.match(s):
            num = float(s)
        else:
            return None
    elif isinstance(value, int):
        num = value
    elif isinstance(value, float):
        num = value
    else:
        return None

    if mode == "reject":
        if isinstance(num, float):
            if not num.is_integer():
                return None
            n = int(num)
        else:
            n = int(num)
        if n in FIB_SCALE:
            return n
        return None

    # snap
    if isinstance(num, float):
        if num < 1.0 or num > 20.0:
            return None
    else:
        if num < 1 or num > 20:
            return None

    best = FIB_SCALE[0]
    best_dist = abs(float(num) - float(best))
    for f in FIB_SCALE[1:]:
        d = abs(float(num) - float(f))
        if d < best_dist or (d == best_dist and f < best):
            best = f
            best_dist = d
    return best


def label_to_fib(label: str | None) -> int | None:
    """Normaliza acento/caixa; consulta LABEL_TO_FIB; senão None.

    'urgente', 'quando der', 'bloqueia X' -> None (não estão na tabela).
    """
    if label is None:
        return None
    if not isinstance(label, str):
        return None
    s = label.strip().lower()
    if s in _EMPTY_MARKERS:
        return None
    # dobra acentos basicos no radical (media/média já na tabela)
    for a, b in (
        ("á", "a"),
        ("à", "a"),
        ("â", "a"),
        ("ã", "a"),
        ("é", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ô", "o"),
        ("õ", "o"),
        ("ú", "u"),
        ("ç", "c"),
    ):
        s = s.replace(a, b)
    # apos dobra, "média" vira "media"
    return LABEL_TO_FIB.get(s) or LABEL_TO_FIB.get(label.strip().lower())


def cost_of_delay(bv: int, tc: int, rr: int) -> int:
    """bv + tc + rr. Exige ints (já normalizados). TypeError se None."""
    if bv is None or tc is None or rr is None:
        raise TypeError("cost_of_delay requires non-None ints")
    return int(bv) + int(tc) + int(rr)


def wsjf(cod: int, job_size: int) -> float:
    """float(cod) / float(job_size). job_size <= 0 -> ValueError."""
    if job_size is None or int(job_size) <= 0:
        raise ValueError("job_size must be > 0")
    return float(cod) / float(job_size)


@dataclass
class WsjfInputs:
    item_id: str
    business_value: int | None = None
    time_criticality: int | None = None
    risk_reduction: int | None = None
    job_size: int | None = None
    priority_label: str | None = None
    difficulty_label: str | None = None
    source: str = "user"


def resolve_wsjf_config(
    *,
    profile: str | None = None,
    comparable_epsilon: float | None = None,
    todo_path: str | None = None,
) -> tuple[str, float, str]:
    """Devolve (profile, epsilon, origin).

    Ordem: argumento explícito > `.tab_pendencias.ini` secção [wsjf]
           > default (early, 0.5).
    profile inválido degrada para early com aviso no origin (não explode).
    """
    ini_profile: str | None = None
    ini_eps: float | None = None
    if todo_path:
        root = os.path.dirname(os.path.abspath(todo_path)) or "."
        ini_path = os.path.join(root, ".tab_pendencias.ini")
        if os.path.isfile(ini_path):
            cp = configparser.ConfigParser()
            try:
                cp.read(ini_path, encoding="utf-8")
                if cp.has_section("wsjf"):
                    if cp.has_option("wsjf", "profile"):
                        ini_profile = cp.get("wsjf", "profile").strip()
                    if cp.has_option("wsjf", "comparable_epsilon"):
                        ini_eps = float(cp.get("wsjf", "comparable_epsilon"))
            except (configparser.Error, ValueError, OSError):
                pass

    origin_bits: list[str] = []
    resolved_profile = DEFAULT_PROFILE

    if profile is not None and str(profile).strip() != "":
        p = str(profile).strip().lower()
        if p in PROFILES:
            resolved_profile = p
            origin_bits.append("arg:profile")
        else:
            resolved_profile = DEFAULT_PROFILE
            origin_bits.append("invalid-profile-degraded-to-early")
    elif ini_profile is not None and ini_profile != "":
        p = ini_profile.strip().lower()
        if p in PROFILES:
            resolved_profile = p
            origin_bits.append("ini:profile")
        else:
            resolved_profile = DEFAULT_PROFILE
            origin_bits.append("ini-invalid-profile-degraded-to-early")
    else:
        origin_bits.append("default:profile")

    if comparable_epsilon is not None:
        resolved_eps = float(comparable_epsilon)
        origin_bits.append("arg:epsilon")
    elif ini_eps is not None:
        resolved_eps = float(ini_eps)
        origin_bits.append("ini:epsilon")
    else:
        if resolved_profile == "safe":
            resolved_eps = DEFAULT_COMPARABLE_EPSILON_SAFE
        else:
            resolved_eps = DEFAULT_COMPARABLE_EPSILON_EARLY
        origin_bits.append("default:epsilon")

    return resolved_profile, resolved_eps, "+".join(origin_bits)


def _as_wsjf_inputs(item: WsjfInputs | dict) -> WsjfInputs:
    if isinstance(item, WsjfInputs):
        return item
    if not isinstance(item, dict):
        raise TypeError("item must be WsjfInputs or dict")
    # aliases
    bv = item.get("business_value", item.get("bv"))
    tc = item.get("time_criticality", item.get("tc"))
    rr = item.get("risk_reduction", item.get("rr"))
    js = item.get("job_size", item.get("js"))
    return WsjfInputs(
        item_id=str(item.get("item_id") or item.get("id") or ""),
        business_value=bv,
        time_criticality=tc,
        risk_reduction=rr,
        job_size=js,
        priority_label=item.get("priority_label"),
        difficulty_label=item.get("difficulty_label"),
        source=str(item.get("source") or "user"),
    )


def score_row(
    item: WsjfInputs | dict,
    *,
    profile: str = "early",
) -> dict:
    """Dict estável com chaves fixas; scored só se 4 ints fib ok e js>0."""
    inp = _as_wsjf_inputs(item)
    prof = (profile or DEFAULT_PROFILE).strip().lower()
    if prof not in PROFILES:
        prof = DEFAULT_PROFILE
    mode = "snap" if prof == "early" else "reject"

    bv = normalize_score(inp.business_value, mode=mode)
    tc = normalize_score(inp.time_criticality, mode=mode)
    rr = normalize_score(inp.risk_reduction, mode=mode)
    js = normalize_score(inp.job_size, mode=mode)
    inputs_source = "absent"

    has_explicit = any(
        v is not None
        for v in (
            inp.business_value,
            inp.time_criticality,
            inp.risk_reduction,
            inp.job_size,
        )
    )
    if has_explicit and any(x is not None for x in (bv, tc, rr, js)):
        inputs_source = "explicit"

    src = (inp.source or "user").strip().lower()
    if prof == "early" and src not in BUS_SOURCES:
        filled_label = False
        if bv is None and inp.priority_label:
            mapped = label_to_fib(inp.priority_label)
            if mapped is not None:
                bv = mapped
                filled_label = True
        if js is None and inp.difficulty_label:
            mapped = label_to_fib(inp.difficulty_label)
            if mapped is not None:
                js = mapped
                filled_label = True
        if filled_label and inputs_source == "absent":
            inputs_source = "early-label"
        elif filled_label and inputs_source == "explicit":
            # mistura de ints + rótulo para furo residual
            pass

    cod = None
    w = None
    scored = False
    if bv is not None and tc is not None and rr is not None and js is not None:
        if js > 0:
            cod = cost_of_delay(bv, tc, rr)
            w = wsjf(cod, js)
            scored = True

    return {
        "id": inp.item_id,
        "bv": bv,
        "tc": tc,
        "rr": rr,
        "cod": cod,
        "job_size": js,
        "wsjf": w,
        "scored": scored,
        "profile": prof,
        "inputs_source": inputs_source,
    }


def compute_wsjf_table(
    items: list[WsjfInputs | dict],
    *,
    profile: str = "early",
) -> list[dict]:
    """score_row em cada item, na ordem de entrada. Sem Rank global."""
    return [score_row(it, profile=profile) for it in items]


def topology_before_wsjf(
    levels: dict[str, int],
    previous_order: list[str],
) -> list[str]:
    """Ordena por (level crescente, índice em previous_order). Sem scores."""
    prev_index = {iid: i for i, iid in enumerate(previous_order)}
    levels_insertion = {k: i for i, k in enumerate(levels.keys())}
    ids: list[str] = list(previous_order)
    for k in levels:
        if k not in prev_index:
            ids.append(k)

    def sort_key(iid: str) -> tuple[int, int]:
        lvl = levels.get(iid, 0)
        if iid in prev_index:
            return (lvl, prev_index[iid])
        # ausentes de previous_order: fim, estaveis por insercao em levels
        return (lvl, 10**9 + levels_insertion.get(iid, 0))

    return sorted(ids, key=sort_key)


def _scores_by_id(items_with_score: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in items_with_score:
        rid = row.get("id")
        if rid is not None:
            out[str(rid)] = row
    return out


def _wsjf_comparable(a: float, b: float, epsilon: float) -> bool:
    """True se |a-b| <= epsilon (comparáveis / empate estável)."""
    return abs(float(a) - float(b)) <= float(epsilon)


def stable_rank_within_level(
    items_with_score: list[dict],
    previous_order: list[str],
    comparable_epsilon: float,
    pinned: set[str] | None = None,
) -> list[str]:
    """Reordena UM nível (D-F3-5 + D-F3-9)."""
    score_map = _scores_by_id(items_with_score)
    order = list(previous_order)
    if not order:
        return order

    # Se algum id do previous_order não está scored: ordem original.
    for iid in order:
        row = score_map.get(iid)
        if row is None or not row.get("scored") or row.get("wsjf") is None:
            return order

    pin = set(pinned or ())
    prev_index = {iid: i for i, iid in enumerate(order)}

    def cmp_ids(a: str, b: str) -> int:
        wa = float(score_map[a]["wsjf"])
        wb = float(score_map[b]["wsjf"])
        if _wsjf_comparable(wa, wb, comparable_epsilon):
            return prev_index[a] - prev_index[b]
        if wa > wb:
            return -1
        if wa < wb:
            return 1
        return prev_index[a] - prev_index[b]

    if not pin:
        return sorted(order, key=functools.cmp_to_key(cmp_ids))

    # Pinados = barreiras de segmento (D-F3-9): reordenar so trechos livres
    # contiguos entre pins. Item livre NAO atravessa pin -- senao um slot
    # livre a esquerda do WIP aceitaria o peer de WSJF alto e "preemptaria".
    result = list(order)
    n = len(result)
    i = 0
    while i < n:
        if result[i] in pin:
            i += 1
            continue
        j = i
        while j < n and result[j] not in pin:
            j += 1
        segment = result[i:j]
        if len(segment) > 1:
            sorted_seg = sorted(segment, key=functools.cmp_to_key(cmp_ids))
            result[i:j] = sorted_seg
        i = j
    return result


def order_levels_then_wsjf(
    levels: dict[str, int],
    previous_order: list[str],
    scores: dict[str, dict],
    comparable_epsilon: float,
    pinned: set[str] | None = None,
) -> list[str]:
    """1) topology_before_wsjf 2) stable_rank_within_level por nível."""
    base = topology_before_wsjf(levels, previous_order)
    by_level: dict[int, list[str]] = {}
    for iid in base:
        lvl = levels.get(iid, 0)
        by_level.setdefault(lvl, []).append(iid)

    out: list[str] = []
    for lvl in sorted(by_level.keys()):
        group = by_level[lvl]
        items = []
        for iid in group:
            if iid in scores:
                items.append(scores[iid])
            else:
                items.append({"id": iid, "wsjf": None, "scored": False})
        ranked = stable_rank_within_level(
            items, group, comparable_epsilon, pinned=pinned,
        )
        out.extend(ranked)
    return out


def explain_move(
    item_id: str,
    old_wave: str,
    new_wave: str,
    cause: str,
    material_input: str,
) -> str:
    """Formato EXATO (3 linhas, sem em-dash, ASCII hyphen)."""
    return (
        f"ITEM {item_id}: {old_wave} -> {new_wave}\n"
        f"causa: {cause}\n"
        f"input_material_que_mudou: {material_input}"
    )
