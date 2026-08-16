#!/usr/bin/env python3
# tools/todo_intake.py -- motor mecanico de intake (TAB-ADD-001..004-L0)
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
tools/todo_intake.py -- nucleo offline de intake (ADR-0002).

Fatia vertical TAB-ADD-001..007 + TAB-ADD-002 (dedup texto) + TAB-INBOX
(drain): recebe um WorkCandidate ja julgado (flags booleanas de predicado
preenchidas por quem chama -- o nucleo NAO infere de prosa), decide a rota
pela cascata fixa, e em --apply persiste:

  DUPLICATE            -- id exato na tabela OU descricao normalizada
                          (strip/whitespace/casefold) na tabela ou INBOX
                          residual; criterios de aceitacao iguais se ambos
                          tiverem o campo; SEM NLP/semantica (fronteira agent)
  LOCAL_INTEGRATION    -- append puro de 1 linha (L0); strip residual mesmo id
  NEEDS_TRIAGE         -- residual INBOX com [triage reason=missing-info]
  NEEDS_LEADER_DECISION -- residual INBOX com [triage reason=needs-leader-decision]
  SCOPED_REORDER       -- menor subgrafo S; equivalencia-restrita fora de S;
                          promove a FULL se |S|/n > fracao ou S multi-Grupo;
                          strip residual mesmo id
  FULL_REORDER         -- topo estavel + ondas W1..; sem renumerar IDs;
                          W1 (Status de existentes intocado); strip residual
  --drain              -- tria INBOX classifiable com --judgments-json;
                          residual valido so increments cycles; pos-condicao
                          classifiable_inbox_count == 0 apos apply

Subgrafo S (pragmatico, TAB-ADD-005): deps abertas do candidato + ancestrais
nao-done transitivos + descendentes transitivos + peers de mesma onda
(ou mesmo nivel topo se onda ausente). |S|/n usa so ids EXISTENTES.
Headings no meio da tabela: best-effort / fora do escopo fino desta fatia
(fixtures de teste nao usam heading entre data rows; o rebuild colapsa
data rows num bloco contiguo apos o separator).

SCOPED/FULL montam o texto em memoria primeiro; journal write-ahead so
depois do build ok, imediatamente antes da escrita atomica; mark_done
apos validacao. L0/residual/DUPLICATE: journal antes da mutacao (estavel).
Escrita atomica (temp + os.replace), encoding utf-8, newline preservado.
stdlib only.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

import intake_journal as J
import todo_lib as L
import wsjf as W

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROUTE_DUPLICATE = "DUPLICATE"
ROUTE_NEEDS_TRIAGE = "NEEDS_TRIAGE"
ROUTE_NEEDS_LEADER_DECISION = "NEEDS_LEADER_DECISION"
ROUTE_FULL_REORDER = "FULL_REORDER"
ROUTE_LOCAL_INTEGRATION = "LOCAL_INTEGRATION"
ROUTE_SCOPED_REORDER = "SCOPED_REORDER"

VALID_SOURCES = frozenset({"user", "bus", "agent", "audit", "test"})

DEFAULT_STATUS = "⏳ Pendente"
PLACEHOLDER = "—"
# hifen ASCII e travessao unicode (conteudo de celula "vazio")
_EMPTY_CELL = frozenset({"", "-", PLACEHOLDER, "—", "--"})
INBOX_HEADING = "## INBOX (descobertas não priorizadas)"
INTAKE_MARKER_TMPL = "<!-- intake:{cid} -->"
_INTAKE_MARKER_RE = re.compile(r"\s*<!--\s*intake:[^>]*-->\s*", re.IGNORECASE)

# Heuristica de eficiencia SCOPED->FULL (ADR-0002 (e)). Calibracao formal
# e futura; default honesto 0.5 ate o protocolo de corpus fechar.
DEFAULT_SCOPED_MAX_FRACTION = 0.5
ENV_SCOPED_MAX_FRACTION = "TAB_INTAKE_SCOPED_MAX_FRACTION"

# Drain: residual com este reason nao e auto-integrado (so cycles++).
REASON_NEEDS_LEADER = "needs-leader-decision"

# Colunas reconhecidas por nome (agnostico a lingua do cabecalho).
_COL_ALIASES = {
    "id": ("id",),
    "onda": ("onda", "wave"),
    "grupo": ("grupo", "group"),
    "descricao": (
        "descricao", "descrição", "descricao tecnica", "descrição técnica",
        "description",
    ),
    "prioridade": ("prioridade", "priority"),
    "prereq": (
        "pre-requisito", "pré-requisito", "prerequisito", "prereq",
        "blocked by", "blocked_by", "depends on",
    ),
    "dificuldade": ("dificuldade", "effort", "job size"),
    "status": ("status",),
    "estado_auditado": (
        "estado auditado", "reviewed", "auditado", "estado_auditado",
    ),
}


class IntakeError(Exception):
    """Erro de execucao (exit 1)."""


@dataclass
class WorkCandidate:
    """Candidato a item -- campos minimos do ADR-0002 + inputs de julgamento.

    O nucleo NAO infere is_local/is_scoped/etc. de prosa: quem chama
    (agente na skill, CLI com flags) preenche os booleanos.
    """
    candidate_id: str
    description: str
    source: str = "user"
    evidence: str = ""
    source_item: str = ""
    dependencies: list = field(default_factory=list)
    item_id: str = ""
    onda: str = ""
    grupo: str = ""
    prioridade: str = ""
    dificuldade: str = ""
    prereq: str = ""
    status: str = DEFAULT_STATUS
    estado_auditado: str = ""
    fields_complete: bool = False
    authority_ok: bool = True
    is_foundation: bool = False
    is_local: bool = False
    is_scoped: bool = False
    reason: str = ""  # override opcional do reason de triagem
    # criterios de aceitacao opcionais (TAB-ADD-002): se candidato E alvo
    # tiverem o campo nao-vazio, entram no P-dup por descricao; senao so
    # a descricao normalizada. O nucleo NAO infere criterios de prosa.
    acceptance: str = ""
    # override da fracao SCOPED; None = env / ini / DEFAULT_SCOPED_MAX_FRACTION
    scoped_max_fraction: float | None = None
    # WSJF (TAB-WSJF): scores opcionais -- nao entram na cascata de rota;
    # so FULL_REORDER consome; nao persistem em celulas novas do TODO.md.
    bv: int | None = None
    time_criticality: int | None = None
    risk_reduction: int | None = None
    job_size: int | None = None
    peer_scores: dict | None = None
    wsjf_profile: str | None = None
    comparable_epsilon: float | None = None


@dataclass
class IntakeResult:
    rc: int
    route: str | None = None
    applied: bool = False
    error: str | None = None
    existing_id: str | None = None
    report_text: str = ""
    candidate_id: str = ""
    promoted_from: str | None = None
    s_ids: list = field(default_factory=list)
    s_fraction: float | None = None
    dup_match: str | None = None  # id | description_table | description_inbox


@dataclass
class DrainResult:
    rc: int
    applied: bool = False
    error: str | None = None
    report_text: str = ""
    classifiable_remaining: int = 0
    residual_bumped: list = field(default_factory=list)
    integrated: list = field(default_factory=list)
    kept: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# leitura / utilitarios de tabela
# ---------------------------------------------------------------------------

def _read_todo(todo_path: str) -> str:
    try:
        with open(todo_path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError as exc:
        raise IntakeError(
            f"falha ao ler TODO.md ({type(exc).__name__}: {exc})"
        ) from exc


def _normalize_header_name(name: str) -> str:
    s = name.strip().lower()
    # dobra acentos basicos sem depender de unicodedata extra
    for a, b in (("á", "a"), ("à", "a"), ("â", "a"), ("ã", "a"),
                 ("é", "e"), ("ê", "e"), ("í", "i"), ("ó", "o"),
                 ("ô", "o"), ("õ", "o"), ("ú", "u"), ("ç", "c")):
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    return s


def _header_cells(table: dict) -> list[str]:
    """Celulas do cabecalho ID+Status (ordem = colunas da tabela)."""
    for line in table["lines"]:
        s = line.lstrip(L.BOM).strip().rstrip("\r")
        if not s.startswith("|"):
            continue
        cells = L._cells(s)
        if L._is_header(cells):
            return cells
    raise IntakeError("cabecalho ID+Status nao encontrado apos parse_table")


def _col_index_map(header_cells: list[str]) -> dict[str, int]:
    """Mapa role -> indice de coluna (somente roles reconhecidos)."""
    normalized = [_normalize_header_name(c) for c in header_cells]
    out: dict[str, int] = {}
    for role, aliases in _COL_ALIASES.items():
        for i, cell in enumerate(normalized):
            if cell in aliases or any(a in cell for a in aliases if len(a) > 3):
                # "status" e palavra exata (evita "sub-status" etc. --
                # o parser ja exige ID+Status; aqui so mapeamos)
                if role == "status" and cell != "status" and "status" not in cell.split():
                    # aceita celula que contenha a palavra status isolada
                    if not re.search(r"(?<![\w-])status\b", cell):
                        continue
                out[role] = i
                break
    if "id" not in out:
        # fallback: id_idx do parse
        out["id"] = 0
    return out


def _table_ids(table: dict | None) -> set[str]:
    if not table:
        return set()
    return {it["id"] for it in table["items"] if it["id"]}


def normalize_free_text(text: str) -> str:
    """Normalizacao mecanica de texto livre (TAB-ADD-002).

    strip + colapsa whitespace + casefold. Nao faz stem/lemma/semantica:
    equivalencia alem de string normalizada e julgamento do agente.
    """
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


def free_text_for_dedup(text: str) -> str:
    """Texto livre para P-dup: remove marcador intake recuperavel e normaliza."""
    s = _INTAKE_MARKER_RE.sub(" ", text or "")
    return normalize_free_text(s)


def _acceptance_compatible(a: str, b: str) -> bool:
    """Se ambos tiverem criterios nao-vazios, exigem igualdade normalizada.
    Caso contrario a comparacao de descricao sozinha basta."""
    aa = (a or "").strip()
    bb = (b or "").strip()
    if not aa or not bb:
        return True
    return normalize_free_text(aa) == normalize_free_text(bb)


def _table_row_descriptions(table: dict | None) -> list[tuple[str, str]]:
    """Lista (id, descricao bruta da celula) da tabela canônica."""
    if not table:
        return []
    try:
        header = _header_cells(table)
    except IntakeError:
        return []
    colmap = _col_index_map(header)
    desc_idx = colmap.get("descricao")
    if desc_idx is None:
        return []
    out: list[tuple[str, str]] = []
    for it in table["items"]:
        iid = it.get("id") or ""
        if not iid:
            continue
        cells = _row_cells(table, it["line_no"])
        desc = cells[desc_idx] if desc_idx < len(cells) else ""
        out.append((iid, desc))
    return out


def _inbox_free_description(entry: dict) -> str:
    """Descricao livre da entrada INBOX (sem prefixo [triage] se parseavel)."""
    triage = entry.get("triage") or {}
    if triage.get("present"):
        return triage.get("description") or ""
    return entry.get("description") or ""


def find_duplicate_match(
    candidate: WorkCandidate,
    table: dict | None,
    inbox: list,
) -> tuple[str | None, str | None]:
    """Localiza duplicata mecanica. Devolve (existing_id, kind) ou (None, None).

    kind: 'id' | 'description_table' | 'description_inbox'

    Fronteira (TAB-ADD-002): so string normalizada (+ acceptance se ambos
    tiverem). Sem NLP. ID so na residual NAO conta como id-dup (reentrada
    TAB-ADD-007); descricao normalizada na residual SIM conta.
    """
    iid = (candidate.item_id or "").strip()
    if iid and iid not in ("-", PLACEHOLDER) and iid in _table_ids(table):
        return iid, "id"

    cand_desc = free_text_for_dedup(candidate.description)
    if not cand_desc:
        return None, None
    cand_acc = candidate.acceptance or ""

    for row_id, row_desc in _table_row_descriptions(table):
        if free_text_for_dedup(row_desc) == cand_desc and _acceptance_compatible(
            cand_acc, ""
        ):
            return row_id, "description_table"

    for entry in inbox or []:
        free = _inbox_free_description(entry)
        if free_text_for_dedup(free) == cand_desc and _acceptance_compatible(
            cand_acc, ""
        ):
            eid = entry.get("id")
            if eid and eid not in ("-", PLACEHOLDER):
                return str(eid), "description_inbox"
            # sem id utilizavel: marca com token sintetico para strip por raw
            return entry.get("raw") or "?", "description_inbox"
    return None, None


def _p_campos(candidate: WorkCandidate, table: dict | None) -> bool:
    """P-campos mecanico: flag de julgamento + deps resolvem + descricao
    nao vazia + source valido."""
    if not candidate.fields_complete:
        return False
    if not (candidate.description or "").strip():
        return False
    if candidate.source not in VALID_SOURCES:
        return False
    known = _table_ids(table)
    for dep in candidate.dependencies or []:
        dep = (dep or "").strip()
        if not dep or dep in ("-", PLACEHOLDER):
            continue
        # deps multiplas "A, B" -- cada token
        for part in re.split(r"[,;]\s*", dep):
            part = part.strip()
            if part and part not in ("-", PLACEHOLDER) and part not in known:
                return False
    return True


def _p_dup(candidate: WorkCandidate, table: dict | None, inbox: list) -> bool:
    """P-dup: id na tabela OU descricao normalizada (TAB-ADD-002).

    ID so na INBOX residual NAO e duplicata por id (TAB-ADD-007). Descricao
    normalizada igual na residual e.
    """
    existing, _kind = find_duplicate_match(candidate, table, inbox)
    return existing is not None


def decide_route(candidate: WorkCandidate, table: dict | None,
                 inbox: list) -> str:
    """Cascata ADR-0002 (d): primeiro que casa vence, ordem fixa."""
    if _p_dup(candidate, table, inbox):
        return ROUTE_DUPLICATE
    if not _p_campos(candidate, table):
        return ROUTE_NEEDS_TRIAGE
    if not candidate.authority_ok:
        return ROUTE_NEEDS_LEADER_DECISION
    if candidate.is_foundation:
        return ROUTE_FULL_REORDER
    if candidate.is_local:
        return ROUTE_LOCAL_INTEGRATION
    if candidate.is_scoped:
        return ROUTE_SCOPED_REORDER
    return ROUTE_FULL_REORDER


# ---------------------------------------------------------------------------
# precondicoes apply
# ---------------------------------------------------------------------------

def _working_tree_dirty(todo_path: str) -> tuple[bool, str | None]:
    """(sujo, motivo). Sem git resolvivel = sujo por seguranca."""
    abs_todo = os.path.abspath(todo_path)
    root = L.repo_root(os.path.dirname(abs_todo)) or L.repo_root(
        os.path.dirname(abs_todo) or ".")
    # tenta a partir do dir do arquivo e do cwd
    if not root:
        root = L.repo_root(os.getcwd())
    if not root:
        return True, (
            "nao e um repositorio git resolvivel -- --apply exige git "
            "para provar a working tree limpa antes de escrever"
        )
    rel = os.path.relpath(abs_todo, root)
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", rel],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
    except Exception as exc:
        return True, f"git status falhou ({type(exc).__name__}: {exc})"
    if r.returncode != 0:
        return True, (
            f"git status --porcelain falhou (rc={r.returncode}): "
            f"{(r.stderr or '').strip()}"
        )
    if r.stdout.strip():
        return True, (
            "working tree do TODO.md tem mudanca(s) nao commitada(s):\n"
            f"{r.stdout.strip()}"
        )
    return False, None


def _classifiable_inbox_ids(inbox: list) -> list[str]:
    out = []
    for e in inbox:
        if e.get("classifiable"):
            label = e.get("id") or e.get("raw") or "?"
            out.append(str(label))
    return out


# ---------------------------------------------------------------------------
# montagem de texto (em memoria)
# ---------------------------------------------------------------------------

def _cell_terminator(sample_line: str) -> str:
    """Sufixo de linha antes do split por \\n ('' ou '\\r')."""
    if sample_line.endswith("\r"):
        return "\r"
    return ""


def _format_row(ncols: int, colmap: dict[str, int],
                values: dict[str, str], terminator: str = "") -> str:
    cells = [PLACEHOLDER] * ncols
    for role, idx in colmap.items():
        if 0 <= idx < ncols and role in values and values[role] is not None:
            cells[idx] = values[role]
    # id e status sao obrigatorios quando presentes no map
    body = "| " + " | ".join(cells) + " |"
    return body + terminator


def _prereq_cell(candidate: WorkCandidate) -> str:
    if candidate.prereq:
        return candidate.prereq
    deps = [d for d in (candidate.dependencies or []) if d and d not in ("-", PLACEHOLDER)]
    if deps:
        return ", ".join(deps)
    return PLACEHOLDER


def _description_with_marker(candidate: WorkCandidate) -> str:
    marker = INTAKE_MARKER_TMPL.format(cid=candidate.candidate_id)
    desc = (candidate.description or "").strip()
    if marker in desc:
        return desc
    if desc:
        return f"{desc} {marker}"
    return marker


def _last_table_data_line_no(table: dict) -> int:
    if not table["items"]:
        # apos o separador: procurar ultima linha de pipe da tabela
        # fallback: cabecalho
        for i, line in enumerate(table["lines"]):
            s = line.lstrip(L.BOM).strip().rstrip("\r")
            if s.startswith("|") and L._is_header(L._cells(s)):
                # separador costuma ser i+1
                return i + 1
        raise IntakeError("tabela sem itens e sem cabecalho localizavel")
    return max(it["line_no"] for it in table["items"])


def _build_l0_text(text: str, table: dict, candidate: WorkCandidate) -> str:
    header = _header_cells(table)
    colmap = _col_index_map(header)
    ncols = table["ncols"]
    last = _last_table_data_line_no(table)
    term = _cell_terminator(table["lines"][last] if table["lines"] else "")
    iid = (candidate.item_id or "").strip()
    if not iid:
        raise IntakeError("LOCAL_INTEGRATION exige item_id nao vazio")

    values = {
        "id": iid,
        "onda": candidate.onda or PLACEHOLDER,
        "grupo": candidate.grupo or PLACEHOLDER,
        "descricao": _description_with_marker(candidate),
        "prioridade": candidate.prioridade or PLACEHOLDER,
        "prereq": _prereq_cell(candidate),
        "dificuldade": candidate.dificuldade or PLACEHOLDER,
        "status": candidate.status or DEFAULT_STATUS,
        "estado_auditado": candidate.estado_auditado or PLACEHOLDER,
    }
    # preencher id/status mesmo se aliases falharem
    if "id" in colmap:
        values["id"] = iid
    if "status" in colmap:
        values["status"] = candidate.status or DEFAULT_STATUS

    new_row = _format_row(ncols, colmap, values, terminator=term)
    lines = list(table["lines"])
    insert_at = last + 1
    lines.insert(insert_at, new_row)
    return "\n".join(lines)


def _utc_date_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _build_inbox_line(candidate: WorkCandidate, route: str) -> str:
    if route == ROUTE_NEEDS_LEADER_DECISION:
        reason = candidate.reason or "needs-leader-decision"
    else:
        reason = candidate.reason or "missing-info"
    if reason not in L.TRIAGE_REASONS:
        reason = "missing-info" if route == ROUTE_NEEDS_TRIAGE else "needs-leader-decision"
    meta = L.format_triage_metadata(
        since=_utc_date_iso(),
        reason=reason,
        source=candidate.source if candidate.source in VALID_SOURCES else None,
        cycles=0,
    )
    marker = INTAKE_MARKER_TMPL.format(cid=candidate.candidate_id)
    desc = (candidate.description or "").strip() or candidate.candidate_id
    if marker not in desc:
        desc = f"{desc} {marker}"
    iid = (candidate.item_id or "").strip() or PLACEHOLDER
    return f"- {iid}: {meta}{desc}"


def _find_inbox_region(lines: list[str]) -> tuple[int | None, int | None]:
    """(heading_idx, end_idx exclusive). end = proximo heading ou len."""
    heading = None
    for i, line in enumerate(lines):
        s = line.lstrip(L.BOM).strip().rstrip("\r")
        if s.startswith("#") and L._is_inbox_heading(s):
            heading = i
            break
    if heading is None:
        return None, None
    end = len(lines)
    for j in range(heading + 1, len(lines)):
        s = lines[j].lstrip(L.BOM).strip().rstrip("\r")
        if s.startswith("#"):
            end = j
            break
    return heading, end


def _build_residual_text(text: str, candidate: WorkCandidate,
                         route: str) -> str:
    lines = text.split("\n")
    new_line = _build_inbox_line(candidate, route)
    # preservar terminator CRLF se o arquivo usa
    sample = next((ln for ln in lines if ln.endswith("\r")), None)
    if sample is not None and not new_line.endswith("\r"):
        new_line = new_line + "\r"

    heading, end = _find_inbox_region(lines)
    if heading is None:
        # criar secao no fim
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(INBOX_HEADING + ("\r" if sample is not None else ""))
        lines.append(new_line)
        return "\n".join(lines)

    # inserir antes do fim da secao (apos ultima linha de conteudo)
    insert_at = end
    # se a secao termina com linhas em branco antes do proximo heading,
    # colocar apos o ultimo item - 
    k = end - 1
    while k > heading and lines[k].strip() == "":
        k -= 1
    insert_at = k + 1
    lines.insert(insert_at, new_line)
    return "\n".join(lines)


def _strip_inbox_id(text: str, item_id: str) -> str:
    """Remove da secao INBOX linhas com o mesmo id (TAB-ADD-007).

    So remove bullets `- ID: ...` cujo token de id casa exatamente com
    item_id. Outras linhas da INBOX e o heading permanecem. Sem secao
    INBOX ou id vazio/placeholder: no-op (texto inalterado).
    """
    iid = (item_id or "").strip()
    if not iid or iid in ("-", PLACEHOLDER):
        return text
    lines = text.split("\n")
    heading, end = _find_inbox_region(lines)
    if heading is None:
        return text
    out: list[str] = []
    for i, line in enumerate(lines):
        if heading < i < end:
            s = line.lstrip(L.BOM).strip().rstrip("\r")
            if s.startswith("- "):
                raw = s[2:].strip()
                head, sep, _rest = raw.partition(":")
                if sep and head.strip() == iid:
                    continue
        out.append(line)
    return "\n".join(out)


def _strip_inbox_raw(text: str, raw: str) -> str:
    """Remove da INBOX a linha cujo corpo apos '- ' casa com raw exato."""
    target = (raw or "").strip()
    if not target:
        return text
    lines = text.split("\n")
    heading, end = _find_inbox_region(lines)
    if heading is None:
        return text
    out: list[str] = []
    for i, line in enumerate(lines):
        if heading < i < end:
            s = line.lstrip(L.BOM).strip().rstrip("\r")
            if s.startswith("- ") and s[2:].strip() == target:
                continue
        out.append(line)
    return "\n".join(out)


def _rewrite_inbox_entry_line(
    text: str,
    *,
    match_raw: str | None = None,
    match_id: str | None = None,
    new_body: str,
) -> str:
    """Substitui uma linha da INBOX (por raw ou id) por new_body (sem '- ')."""
    lines = text.split("\n")
    heading, end = _find_inbox_region(lines)
    if heading is None:
        return text
    sample = next((ln for ln in lines if ln.endswith("\r")), None)
    body = new_body
    if sample is not None and not body.endswith("\r"):
        # terminator so no join; lines store content without final \\n
        pass
    out: list[str] = []
    replaced = False
    for i, line in enumerate(lines):
        if heading < i < end and not replaced:
            s = line.lstrip(L.BOM).strip().rstrip("\r")
            if s.startswith("- "):
                raw = s[2:].strip()
                hit = False
                if match_raw is not None and raw == match_raw.strip():
                    hit = True
                elif match_id is not None:
                    head, sep, _rest = raw.partition(":")
                    if sep and head.strip() == match_id.strip():
                        hit = True
                if hit:
                    term = "\r" if line.endswith("\r") else ""
                    out.append(f"- {new_body}{term}")
                    replaced = True
                    continue
        out.append(line)
    return "\n".join(out)


def classifiable_inbox_count(text: str) -> int:
    return sum(1 for e in L.inbox_entries(text) if e.get("classifiable"))


# ---------------------------------------------------------------------------
# grafo / SCOPED S / FULL reorder (TAB-ADD-005 / TAB-ADD-006)
# ---------------------------------------------------------------------------

def _split_dep_tokens(raw: str) -> list[str]:
    """Tokens de dependencia a partir de celula ou campo livre.

    Split por virgula ou ponto-e-virgula; strip; ignora vazio/hifen/travessao.
    Nao aplica a politica "ID inteiro vence" do chk_graph: intake so aceita
    IDs que ja existem na tabela conhecida (filtro no chamador).
    """
    text = (raw or "").strip()
    if text in _EMPTY_CELL:
        return []
    out = []
    for part in re.split(r"[,;]", text):
        p = part.strip()
        if p and p not in _EMPTY_CELL:
            out.append(p)
    return out


def _candidate_dep_ids(candidate: WorkCandidate, known: set[str]) -> list[str]:
    """Deps do candidato que existem na tabela (ordem estavel, dedup)."""
    seen: set[str] = set()
    ordered: list[str] = []
    sources: list[str] = []
    for d in candidate.dependencies or []:
        sources.extend(_split_dep_tokens(d if isinstance(d, str) else str(d)))
    if candidate.prereq:
        sources.extend(_split_dep_tokens(candidate.prereq))
    for t in sources:
        if t in known and t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _row_cells(table: dict, line_no: int) -> list[str]:
    raw = table["lines"][line_no]
    return L._cells(raw.lstrip(L.BOM).strip().rstrip("\r"))


def _item_meta_map(table: dict) -> dict[str, dict]:
    """id -> {status, line_no, index, cells, prereqs, onda, grupo, raw}."""
    header = _header_cells(table)
    colmap = _col_index_map(header)
    known = {it["id"] for it in table["items"] if it["id"]}
    meta: dict[str, dict] = {}
    for idx, it in enumerate(table["items"]):
        iid = it["id"]
        if not iid:
            continue
        cells = _row_cells(table, it["line_no"])
        prereq_raw = ""
        if "prereq" in colmap and colmap["prereq"] < len(cells):
            prereq_raw = cells[colmap["prereq"]]
        # so referencias validas na tabela entram no grafo de reorder
        prereqs = [p for p in _split_dep_tokens(prereq_raw) if p in known]
        onda = ""
        if "onda" in colmap and colmap["onda"] < len(cells):
            onda = cells[colmap["onda"]]
        grupo = ""
        if "grupo" in colmap and colmap["grupo"] < len(cells):
            grupo = cells[colmap["grupo"]]
        meta[iid] = {
            "status": it["status"],
            "line_no": it["line_no"],
            "index": idx,
            "cells": list(cells),
            "prereqs": prereqs,
            "onda": onda,
            "grupo": grupo,
            "raw": table["lines"][it["line_no"]],
        }
    return meta


def _topo_levels(graph: dict[str, list[str]], nodes: list[str]) -> dict[str, int]:
    """Nivel topológico: 0 = sem prereq no grafo; senao 1+max(prereqs)."""
    levels: dict[str, int] = {}

    def level_of(nid: str, stack: set[str]) -> int:
        if nid in levels:
            return levels[nid]
        if nid in stack:
            # ciclo -- o detector principal levanta; aqui trava em 0
            levels[nid] = 0
            return 0
        stack.add(nid)
        prereqs = [p for p in graph.get(nid, []) if p in graph or p in levels
                   or p in nodes]
        # so conta prereqs que sao nos do grafo sob ordenacao
        node_set = set(nodes)
        prereqs = [p for p in graph.get(nid, []) if p in node_set]
        if not prereqs:
            levels[nid] = 0
        else:
            levels[nid] = 1 + max(level_of(p, stack) for p in prereqs)
        stack.discard(nid)
        return levels[nid]

    for n in nodes:
        level_of(n, set())
    return levels


def _detect_cycle(graph: dict[str, list[str]], nodes: list[str]) -> list[str] | None:
    """DFS: devolve um ciclo (lista de ids) ou None."""
    node_set = set(nodes)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    parent: dict[str, str | None] = {n: None for n in nodes}

    def dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        for v in graph.get(u, []):
            if v not in node_set:
                continue
            if color[v] == GRAY:
                # reconstruir ciclo u -> ... -> v -> u
                cyc = [v]
                cur = u
                while cur != v and cur is not None:
                    cyc.append(cur)
                    cur = parent.get(cur)
                cyc.append(v)
                cyc.reverse()
                return cyc
            if color[v] == WHITE:
                parent[v] = u
                found = dfs(v)
                if found:
                    return found
        color[u] = BLACK
        return None

    for n in nodes:
        if color[n] == WHITE:
            found = dfs(n)
            if found:
                return found
    return None


def _stable_topo_sort(graph: dict[str, list[str]],
                      nodes: list[str],
                      orig_index: dict[str, int]) -> list[str]:
    """Kahn estavel: entre ready, menor orig_index primeiro (W2 / TAB-WSJF)."""
    node_set = set(nodes)
    indeg = {n: 0 for n in nodes}
    children: dict[str, list[str]] = {n: [] for n in nodes}
    for n in nodes:
        for p in graph.get(n, []):
            if p not in node_set:
                continue
            # aresta p -> n (p deve vir antes de n)
            children[p].append(n)
            indeg[n] += 1

    ready = sorted(
        [n for n in nodes if indeg[n] == 0],
        key=lambda x: orig_index.get(x, 10**9),
    )
    out: list[str] = []
    while ready:
        u = ready.pop(0)
        out.append(u)
        for v in children[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
                ready.sort(key=lambda x: orig_index.get(x, 10**9))
    if len(out) != len(nodes):
        cyc = _detect_cycle(graph, nodes)
        label = " -> ".join(cyc) if cyc else "unknown"
        raise IntakeError(f"dependency_cycle: {label}")
    return out


def _build_full_graph(meta: dict[str, dict],
                      candidate: WorkCandidate,
                      cand_id: str) -> tuple[dict[str, list[str]], list[str], dict[str, int]]:
    """Grafo id -> lista de prereqs; nos = existentes + candidato; indices."""
    graph: dict[str, list[str]] = {}
    nodes: list[str] = []
    orig_index: dict[str, int] = {}
    for iid, m in meta.items():
        nodes.append(iid)
        orig_index[iid] = m["index"]
        graph[iid] = list(m["prereqs"])
    known = set(meta)
    cand_deps = _candidate_dep_ids(candidate, known)
    if cand_id in graph:
        raise IntakeError(f"item_id {cand_id!r} colide com id existente no grafo")
    nodes.append(cand_id)
    orig_index[cand_id] = len(meta)  # desempate: depois dos existentes
    graph[cand_id] = cand_deps
    return graph, nodes, orig_index


def compute_safe_subgraph_S(
    table: dict,
    candidate: WorkCandidate,
    meta: dict[str, dict] | None = None,
) -> set[str]:
    """Menor subgrafo seguro S de ids EXISTENTES (candidato nao entra em |S|).

    1. deps = dependencies/prereq do candidato presentes na tabela
    2. open_deps = deps cujo status NAO e done (L.is_done)
    3. fecha para tras: ancestrais transitivos nao-done
    4. fecha para frente: descendentes transitivos na tabela
    5. peers: mesma onda do contexto de insercao com overlap de prereq,
       ou mesmo nivel topológico se onda ausente
    """
    if meta is None:
        meta = _item_meta_map(table)
    known = set(meta)
    if not known:
        return set()
    deps = _candidate_dep_ids(candidate, known)
    open_deps = {d for d in deps if not L.is_done(meta[d]["status"])}
    S: set[str] = set(open_deps)

    # ancestrais nao-done
    stack = list(open_deps)
    while stack:
        cur = stack.pop()
        for p in meta[cur]["prereqs"]:
            if p not in known:
                continue
            if L.is_done(meta[p]["status"]):
                continue
            if p not in S:
                S.add(p)
                stack.append(p)

    # descendentes: quem depende (transitivo) de algo em S
    dependents: dict[str, list[str]] = {i: [] for i in known}
    for iid, m in meta.items():
        for p in m["prereqs"]:
            if p in dependents:
                dependents[p].append(iid)
    stack = list(S)
    while stack:
        cur = stack.pop()
        for d in dependents.get(cur, []):
            if d not in S:
                S.add(d)
                stack.append(d)

    # peers
    target_waves: set[str] = set()
    for d in open_deps:
        w = (meta[d]["onda"] or "").strip()
        if w not in _EMPTY_CELL:
            target_waves.add(w)
    cw = (candidate.onda or "").strip()
    if cw not in _EMPTY_CELL:
        target_waves.add(cw)

    if target_waves:
        base = set(S) | set(open_deps)
        for iid, m in meta.items():
            w = (m["onda"] or "").strip()
            if w not in target_waves:
                continue
            pr = set(m["prereqs"])
            if iid in base or (pr & base) or (not pr and open_deps):
                S.add(iid)
    else:
        # nivel topo pelo grafo so de existentes
        graph_ex = {i: list(meta[i]["prereqs"]) for i in known}
        levels = _topo_levels(graph_ex, list(known))
        if open_deps:
            target_levels = {levels[d] for d in open_deps if d in levels}
        else:
            # candidato sem deps abertas: nivel 0 peers (itens raiz nao-done)
            target_levels = {0}
        for iid, m in meta.items():
            if levels.get(iid) in target_levels and not L.is_done(m["status"]):
                pr = set(m["prereqs"])
                if iid in open_deps or (pr & S) or (not pr and not open_deps):
                    S.add(iid)

    return S


def resolve_scoped_max_fraction(
    candidate: WorkCandidate,
    todo_path: str | None = None,
) -> float:
    """Ordem: candidate.scoped_max_fraction > env > ini > default 0.5."""
    if candidate.scoped_max_fraction is not None:
        return float(candidate.scoped_max_fraction)
    env = os.environ.get(ENV_SCOPED_MAX_FRACTION)
    if env is not None and str(env).strip() != "":
        try:
            return float(env)
        except ValueError:
            pass
    if todo_path:
        root = os.path.dirname(os.path.abspath(todo_path)) or "."
        ini_path = os.path.join(root, ".tab_pendencias.ini")
        if os.path.isfile(ini_path):
            cp = configparser.ConfigParser()
            try:
                cp.read(ini_path, encoding="utf-8")
                if cp.has_option("intake", "scoped_reorder_max_fraction"):
                    return float(cp.get("intake", "scoped_reorder_max_fraction"))
            except (configparser.Error, ValueError, OSError):
                pass
    return DEFAULT_SCOPED_MAX_FRACTION


def should_promote_scoped_to_full(
    S: set[str],
    meta: dict[str, dict],
    fraction: float,
) -> tuple[bool, str]:
    """Promove se |S|/n > fraction ou S toca >1 Grupo distinto."""
    n = len(meta)
    if n == 0:
        return False, ""
    frac = len(S) / n
    if frac > fraction:
        return True, f"|S|/n={frac:.3f} > {fraction}"
    grupos = set()
    for iid in S:
        g = (meta[iid].get("grupo") or "").strip()
        if g not in _EMPTY_CELL:
            grupos.add(g)
    if len(grupos) > 1:
        return True, f"S multi-Grupo: {sorted(grupos)}"
    return False, ""


def _format_cells_row(cells: list[str], terminator: str = "") -> str:
    body = "| " + " | ".join(cells) + " |"
    return body + terminator


def _set_cell(cells: list[str], idx: int | None, value: str) -> None:
    if idx is None or idx < 0:
        return
    while len(cells) <= idx:
        cells.append(PLACEHOLDER)
    cells[idx] = value


def _wave_label(level: int) -> str:
    return f"W{level + 1}"


def _status_kind_andamento(status: str) -> bool:
    """True se Status e 🔄 Em andamento (emoji-prefixo D-1)."""
    return L._status_kind(status) == "andamento"


def _collect_wsjf_inputs(
    candidate: WorkCandidate,
    nodes: list[str],
    cand_id: str,
) -> list[W.WsjfInputs]:
    """Monta WsjfInputs do candidato + peers.

    Peers so entram com ints explicitos em candidate.peer_scores --
    NUNCA scrapa Prioridade/Dificuldade da tabela (D-F3-4).
    """
    peers = candidate.peer_scores or {}
    out: list[W.WsjfInputs] = []
    for iid in nodes:
        if iid == cand_id:
            out.append(
                W.WsjfInputs(
                    item_id=cand_id,
                    business_value=candidate.bv,
                    time_criticality=candidate.time_criticality,
                    risk_reduction=candidate.risk_reduction,
                    job_size=candidate.job_size,
                    priority_label=candidate.prioridade or None,
                    difficulty_label=candidate.dificuldade or None,
                    source=candidate.source or "user",
                )
            )
            continue
        raw = peers.get(iid) if isinstance(peers, dict) else None
        if not isinstance(raw, dict):
            out.append(W.WsjfInputs(item_id=iid, source="user"))
            continue
        bv = raw.get("bv", raw.get("business_value"))
        tc = raw.get("time_criticality", raw.get("tc"))
        rr = raw.get("risk_reduction", raw.get("rr"))
        js = raw.get("job_size", raw.get("js"))
        out.append(
            W.WsjfInputs(
                item_id=iid,
                business_value=bv,
                time_criticality=tc,
                risk_reduction=rr,
                job_size=js,
                source="user",
            )
        )
    return out


def _wsjf_explain_existing_moves(
    *,
    old_order: list[str],
    new_order: list[str],
    old_waves: dict[str, str],
    new_waves: dict[str, str],
    levels: dict[str, int],
    scores: dict[str, dict],
    graph: dict[str, list[str]],
    candidate: WorkCandidate,
) -> list[str]:
    """Blocos explain_move so para posicao ou onda realmente mudada."""
    old_pos = {i: n for n, i in enumerate(old_order)}
    new_pos = {i: n for n, i in enumerate(new_order)}
    blocks: list[str] = []
    peer_ids = sorted((candidate.peer_scores or {}).keys())
    cand_id = (candidate.item_id or "").strip()
    material_bits = []
    if any(
        x is not None
        for x in (
            candidate.bv,
            candidate.time_criticality,
            candidate.risk_reduction,
            candidate.job_size,
        )
    ):
        material_bits.append(
            f"candidate {cand_id} scores bv={candidate.bv} "
            f"tc={candidate.time_criticality} rr={candidate.risk_reduction} "
            f"js={candidate.job_size}"
        )
    if peer_ids:
        material_bits.append(
            "peer_scores fornecidos para " + ",".join(peer_ids)
        )
    default_material = (
        "; ".join(material_bits) if material_bits else "topologia recalculada"
    )

    for iid in old_order:
        if iid not in new_pos:
            continue
        pos_changed = old_pos.get(iid) != new_pos.get(iid)
        ow = (old_waves.get(iid) or "").strip() or PLACEHOLDER
        nw = (new_waves.get(iid) or "").strip() or PLACEHOLDER
        wave_changed = ow != nw
        if not pos_changed and not wave_changed:
            continue

        prereqs = graph.get(iid, [])
        # causa: topologia se nivel/onda mudou por prereq; senao WSJF
        cause = ""
        if wave_changed and prereqs:
            p = prereqs[0]
            cause = (
                f"prerequisito {p} no grafo; nivel "
                f"{ow}->{nw}"
            )
            material = f"topologia: dep {p}"
        elif pos_changed:
            row = scores.get(iid) or {}
            w_self = row.get("wsjf")
            # achar peer no mesmo nivel com score
            lvl = levels.get(iid, 0)
            peers_same = [
                j for j in new_order
                if j != iid and levels.get(j, 0) == lvl
            ]
            peer_txt = ""
            peer_w: float | None = None
            for j in peers_same:
                jr = scores.get(j) or {}
                if jr.get("scored") and jr.get("wsjf") is not None and w_self is not None:
                    peer_w = float(jr["wsjf"])
                    peer_txt = f"peer {j} {peer_w:.1f}"
                    break
            if w_self is not None and peer_txt and peer_w is not None:
                ws = float(w_self)
                diff = abs(ws - peer_w)
                eps = candidate.comparable_epsilon
                if eps is not None and diff <= float(eps):
                    op = "~"
                elif ws == peer_w:
                    op = "~"
                elif ws > peer_w:
                    op = ">"
                else:
                    op = "<"
                cause = f"WSJF {ws:.1f} {op} {peer_txt}"
            elif w_self is not None:
                cause = f"WSJF {float(w_self):.1f} reordena pos no nivel"
            else:
                cause = f"pos {old_pos.get(iid)}->{new_pos.get(iid)} no nivel"
            material = default_material
        else:
            cause = f"onda recalculada {ow}->{nw}"
            material = default_material

        blocks.append(
            W.explain_move(iid, ow, nw, cause, material)
        )
    return blocks


def _build_reorder_rows(
    table: dict,
    candidate: WorkCandidate,
    meta: dict[str, dict],
    S: set[str] | None = None,
    todo_path: str | None = None,
) -> tuple[list[str], list[str], dict[str, int], dict[str, dict]]:
    """Constroi linhas de dados reordenadas (FULL ou SCOPED).

    Retorna (ordered_ids, data_row_strings, levels, scores_by_id).

    S is None (FULL): nivel-primeiro + WSJF intra-nivel (se todos scored);
    recalcula onda de todos os existentes.
    S is not None (SCOPED nao promovido): Kahn+orig; fora de S preserva raw
    byte-a-byte; em S reformata e pode atualizar so onda; status de
    existentes sempre intocado. Candidato = linha nova com marker.

    Prereq de existentes intocado. Candidato usa prereq/deps do candidate.
    Headings no meio: nao preservados no bloco de data (ver docstring modulo).
    """
    cand_id = (candidate.item_id or "").strip()
    if not cand_id:
        raise IntakeError("FULL_REORDER/SCOPED_REORDER exige item_id nao vazio")

    header = _header_cells(table)
    colmap = _col_index_map(header)
    ncols = table["ncols"]
    graph, nodes, orig_index = _build_full_graph(meta, candidate, cand_id)

    cyc = _detect_cycle(graph, nodes)
    if cyc:
        raise IntakeError(f"dependency_cycle: {' -> '.join(cyc)}")

    levels = _topo_levels(graph, nodes)
    scores: dict[str, dict] = {}

    if S is None:
        # FULL: topologia por nivel + WSJF so dentro do nivel (D-F3-6/7)
        prev = sorted(nodes, key=lambda i: orig_index.get(i, 10**9))
        cfg_profile, eps, _orig = W.resolve_wsjf_config(
            profile=candidate.wsjf_profile,
            comparable_epsilon=candidate.comparable_epsilon,
            todo_path=todo_path,
        )
        inputs = _collect_wsjf_inputs(candidate, nodes, cand_id)
        table_scores = W.compute_wsjf_table(inputs, profile=cfg_profile)
        scores = {row["id"]: row for row in table_scores}
        pinned = {
            iid for iid, m in meta.items()
            if _status_kind_andamento(m["status"])
        }
        # candidato novo nunca e pinado
        ordered = W.order_levels_then_wsjf(
            levels, prev, scores, eps, pinned=pinned,
        )
    else:
        ordered = _stable_topo_sort(graph, nodes, orig_index)

    # terminador a partir de uma linha de dados existente
    sample_ln = next(iter(meta.values()))["line_no"] if meta else 0
    term = _cell_terminator(table["lines"][sample_ln] if table["lines"] else "")

    onda_idx = colmap.get("onda")
    rows_out: list[str] = []
    for iid in ordered:
        if iid == cand_id:
            values = {
                "id": cand_id,
                "onda": _wave_label(levels.get(cand_id, 0)),
                "grupo": candidate.grupo or PLACEHOLDER,
                "descricao": _description_with_marker(candidate),
                "prioridade": candidate.prioridade or PLACEHOLDER,
                "prereq": _prereq_cell(candidate),
                "dificuldade": candidate.dificuldade or PLACEHOLDER,
                "status": candidate.status or DEFAULT_STATUS,
                "estado_auditado": candidate.estado_auditado or PLACEHOLDER,
            }
            # FULL/SCOPED: onda do candidato por nivel topo (TAB-ADD-006)
            row = _format_row(ncols, colmap, values, terminator=term)
            rows_out.append(row)
            continue

        m = meta[iid]
        # SCOPED: fora de S = raw original intacto (cinto; equivalencia valida)
        if S is not None and iid not in S:
            rows_out.append(m["raw"])
            continue

        cells = list(m["cells"])
        # garantir ncols
        if len(cells) < ncols:
            cells.extend([PLACEHOLDER] * (ncols - len(cells)))
        elif len(cells) > ncols:
            cells = cells[:ncols]
        if onda_idx is not None:
            _set_cell(cells, onda_idx, _wave_label(levels.get(iid, 0)))
        # W1: status permanece cells[status_idx] original
        rows_out.append(_format_cells_row(cells, terminator=term))

    return ordered, rows_out, levels, scores


def _data_line_span(meta: dict[str, dict]) -> tuple[int, int]:
    """(first_data_line_no, last_data_line_no) inclusive."""
    if not meta:
        raise IntakeError("tabela sem itens para reorder")
    nos = [m["line_no"] for m in meta.values()]
    return min(nos), max(nos)


def _rewrite_table_data_block(
    text: str,
    table: dict,
    meta: dict[str, dict],
    new_data_rows: list[str],
) -> str:
    """Substitui o bloco de data rows (min..max line_no) pelas novas linhas.

    Preserva header, separator e todo texto fora do span de data.
    Headings que estavam ENTRE data rows no span original sao removidos
    com o span (best-effort; fora do escopo fino desta fatia).
    """
    lines = list(table["lines"])
    if not meta:
        # tabela so com header: inserir apos separator
        # achar separator apos header
        header_i = None
        for i, line in enumerate(lines):
            s = line.lstrip(L.BOM).strip().rstrip("\r")
            if s.startswith("|") and L._is_header(L._cells(s)):
                header_i = i
                break
        if header_i is None:
            raise IntakeError("cabecalho nao encontrado no rewrite")
        sep_i = header_i + 1
        insert_at = sep_i + 1
        new_lines = lines[:insert_at] + new_data_rows + lines[insert_at:]
        return "\n".join(new_lines)

    first, last = _data_line_span(meta)
    new_lines = lines[:first] + new_data_rows + lines[last + 1:]
    return "\n".join(new_lines)


def build_full_reorder_text(
    text: str,
    table: dict,
    candidate: WorkCandidate,
    meta: dict[str, dict] | None = None,
    todo_path: str | None = None,
) -> tuple[str, list[str], set[str], list[str]]:
    """FULL_REORDER em memoria.

    Retorna (novo_texto, ordered_ids, moved_existing_ids, explain_blocks).
    """
    if meta is None:
        meta = _item_meta_map(table)
    ordered, rows, levels, scores = _build_reorder_rows(
        table, candidate, meta, S=None, todo_path=todo_path,
    )
    novo = _rewrite_table_data_block(text, table, meta, rows)
    cand_id = (candidate.item_id or "").strip()
    # ids existentes cuja posicao relativa mudou ou linha sera reescrita
    old_order = [it["id"] for it in table["items"] if it["id"]]
    new_existing_order = [i for i in ordered if i != cand_id]
    moved = set()
    if old_order != new_existing_order:
        # qualquer id cuja posicao mudou
        old_pos = {i: n for n, i in enumerate(old_order)}
        for n, i in enumerate(new_existing_order):
            if old_pos.get(i) != n:
                moved.add(i)
    # ondas podem mudar mesmo com mesma ordem -- todos com onda recalculada
    # em FULL todos existentes sao "tocados" na celula onda se coluna existe
    header = _header_cells(table)
    colmap = _col_index_map(header)
    if "onda" in colmap:
        moved |= set(old_order)

    old_waves = {
        iid: (meta[iid].get("onda") or "").strip()
        for iid in old_order if iid in meta
    }
    new_waves = {
        iid: _wave_label(levels.get(iid, 0)) for iid in new_existing_order
    }
    graph, nodes, _oi = _build_full_graph(meta, candidate, cand_id)
    explain_blocks = _wsjf_explain_existing_moves(
        old_order=old_order,
        new_order=new_existing_order,
        old_waves=old_waves,
        new_waves=new_waves,
        levels=levels,
        scores=scores,
        graph=graph,
        candidate=candidate,
    )
    return novo, ordered, moved, explain_blocks


def build_scoped_reorder_text(
    text: str,
    table: dict,
    candidate: WorkCandidate,
    S: set[str],
    meta: dict[str, dict] | None = None,
) -> tuple[str, list[str], set[str]]:
    """SCOPED: topo com raw fora de S intacto + prova de equivalencia.

    Path com S (nao FULL): ids ∉ S reusam meta[iid]['raw'] byte-a-byte.
    Se algum id ∉ S ainda diverger (cinto e suspensorio), aborta com
    scoped_equivalence_failed (nao escreve -- caller trata).
    WSJF nao se aplica a SCOPED nesta fase (D-F3-7).
    """
    if meta is None:
        meta = _item_meta_map(table)
    ordered, rows, _levels, _scores = _build_reorder_rows(
        table, candidate, meta, S=S,
    )
    novo = _rewrite_table_data_block(text, table, meta, rows)
    # validar equivalencia fora de S antes de devolver
    novo_table = L.parse_table(novo)
    if novo_table is None:
        raise IntakeError("scoped_equivalence_failed: resultado sem tabela")
    new_raw = _raw_lines_by_id(novo_table)
    for iid, m in meta.items():
        if iid in S:
            continue
        if iid not in new_raw:
            raise IntakeError(
                f"scoped_equivalence_failed: id {iid!r} sumiu"
            )
        if new_raw[iid] != m["raw"]:
            raise IntakeError(
                f"scoped_equivalence_failed: id {iid!r} fora de S mudou "
                "(raw_line diverge; re-rode como FULL_REORDER)"
            )
    cand_id = (candidate.item_id or "").strip()
    old_order = [it["id"] for it in table["items"] if it["id"]]
    new_existing_order = [i for i in ordered if i != cand_id]
    moved = set()
    if old_order != new_existing_order:
        old_pos = {i: n for n, i in enumerate(old_order)}
        for n, i in enumerate(new_existing_order):
            if old_pos.get(i) != n:
                moved.add(i)
    # so conta moved dentro de S (fora de S e raw-identico por contrato)
    return novo, ordered, moved & S


# ---------------------------------------------------------------------------
# invariantes + escrita atomica
# ---------------------------------------------------------------------------

def _status_map_from_table(table: dict) -> dict[str, str]:
    return {it["id"]: it["status"] for it in table["items"]}


def _raw_lines_by_id(table: dict) -> dict[str, str]:
    return {it["id"]: table["lines"][it["line_no"]] for it in table["items"]}


def _ids_in_table_and_inbox(text: str) -> list[str]:
    table = L.parse_table(text)
    inbox = L.inbox_entries(text)
    table_ids = _table_ids(table)
    both = []
    for e in inbox:
        iid = e.get("id")
        if iid and iid in table_ids:
            both.append(iid)
    return both


def _provar_invariantes(
    novo_texto: str,
    *,
    old_table: dict,
    route: str,
    expected_item_delta: int,
    preserve_raw_ids: bool,
    preserve_raw_ids_except: set[str] | None = None,
) -> tuple[bool, str | None]:
    novo = L.parse_table(novo_texto)
    if novo is None:
        return False, "arquivo resultante sem tabela ID+Status"

    # contagem de itens da tabela
    expected_n = len(old_table["items"]) + expected_item_delta
    if len(novo["items"]) != expected_n:
        return False, (
            f"contagem de itens divergente: got {len(novo['items'])}, "
            f"expected {expected_n}"
        )

    # W1: Status de linhas pre-existentes intacto
    old_status = _status_map_from_table(old_table)
    new_status = _status_map_from_table(novo)
    for iid, st in old_status.items():
        if iid not in new_status:
            if expected_item_delta < 0:
                continue
            return False, f"item pre-existente {iid!r} sumiu do resultado"
        if new_status[iid] != st:
            return False, (
                f"W1 violado: Status de {iid!r} mudou de {st!r} para "
                f"{new_status[iid]!r}"
            )

    # L0: preserve_raw_ids=True -> todos os ids antigos.
    # SCOPED: preserve_raw_ids_except=S -> todos exceto S.
    # FULL: nenhum dos dois (so W1 + contagem).
    check_raw = preserve_raw_ids or (preserve_raw_ids_except is not None)
    if check_raw:
        except_ids = preserve_raw_ids_except or set()
        old_raw = _raw_lines_by_id(old_table)
        new_raw = _raw_lines_by_id(novo)
        for iid, raw in old_raw.items():
            if iid in except_ids:
                continue
            if iid not in new_raw:
                return False, f"linha de {iid!r} ausente apos escrita"
            if new_raw[iid] != raw:
                if preserve_raw_ids and not except_ids:
                    return False, (
                        f"L0: bytes da linha de {iid!r} mudaram (append puro "
                        "exige zero tocada)"
                    )
                return False, (
                    f"scoped: bytes da linha de {iid!r} fora de S mudaram"
                )

    both = _ids_in_table_and_inbox(novo_texto)
    if both:
        return False, (
            f"item simultaneo na tabela e na INBOX: {both}"
        )

    return True, None


def _escrever_atomico(todo_path: str, novo_texto: str) -> tuple[bool, str | None]:
    d = os.path.dirname(os.path.abspath(todo_path)) or "."
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".todo_intake.", suffix=".tmp",
                                        dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(novo_texto)
            fh.flush()
            os.fsync(fh.fileno())
        with open(tmp_path, encoding="utf-8", newline="") as fh:
            lido = fh.read()
        if lido != novo_texto:
            return False, (
                "conteudo lido de volta do temporario diverge -- abortado "
                "antes de trocar o arquivo real"
            )
        os.replace(tmp_path, todo_path)
        tmp_path = None
    except OSError as exc:
        return False, f"falha de I/O ({type(exc).__name__}: {exc})"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return True, None


def _journal_dir_for_todo(todo_path: str) -> str:
    abs_todo = os.path.abspath(todo_path)
    cwd = os.path.dirname(abs_todo) or os.getcwd()
    jd = J.journal_dir_for(cwd=cwd)
    if jd is None:
        jd = J.journal_dir_for(cwd=os.getcwd())
    if jd is None:
        raise IntakeError(
            "journal impossivel: nao foi possivel localizar git common "
            "dir (repositorio git exigido para write-ahead journal)"
        )
    return jd


def _write_journal(candidate: WorkCandidate, journal_dir: str) -> None:
    J.write_candidate(
        candidate.candidate_id,
        source=candidate.source if candidate.source in VALID_SOURCES else "test",
        description=candidate.description or candidate.candidate_id,
        source_item=candidate.source_item or "",
        journal_dir=journal_dir,
    )


# ---------------------------------------------------------------------------
# nucleo run_intake
# ---------------------------------------------------------------------------

def run_intake(*, todo_path: str, candidate: WorkCandidate,
              apply: bool = False,
              enforce_clean_tree: bool = True,
              enforce_empty_classifiable: bool = True) -> IntakeResult:
    """Decide rota e, se apply, persiste. Nunca levanta para fluxos
    esperados -- devolve IntakeResult com rc.

    enforce_* = False so para o proprio --drain (apos a 1a escrita a arvore
    fica suja; classifiable ja foi pre-processado). Chamadores externos
    devem deixar os defaults True.
    """
    try:
        return _run_intake_inner(
            todo_path=todo_path, candidate=candidate, apply=apply,
            enforce_clean_tree=enforce_clean_tree,
            enforce_empty_classifiable=enforce_empty_classifiable,
        )
    except IntakeError as exc:
        return IntakeResult(
            rc=1, error=str(exc), candidate_id=candidate.candidate_id,
            report_text=f"erro: {exc}\n",
        )
    except J.IntakeJournalError as exc:
        return IntakeResult(
            rc=1, error=str(exc), candidate_id=candidate.candidate_id,
            report_text=f"erro journal: {exc}\n",
        )


def _run_intake_inner(*, todo_path: str, candidate: WorkCandidate,
                      apply: bool,
                      enforce_clean_tree: bool = True,
                      enforce_empty_classifiable: bool = True) -> IntakeResult:
    if not candidate.candidate_id:
        raise IntakeError("candidate_id obrigatorio")

    text = _read_todo(todo_path)
    table = L.parse_table(text)
    if table is None:
        raise IntakeError("nenhuma tabela ID+Status reconhecida no TODO.md")
    inbox = L.inbox_entries(text)
    route = decide_route(candidate, table, inbox)
    dup_id, dup_kind = find_duplicate_match(candidate, table, inbox)

    report_lines = [
        "=== tab_pendencias --add (intake) ===",
        f"candidate_id: {candidate.candidate_id}",
        f"item_id: {candidate.item_id or '-'}",
        f"route: {route}",
        f"mode: {'apply' if apply else 'dry-run'}",
    ]

    # dry-run: so decide
    if not apply:
        if route == ROUTE_DUPLICATE:
            report_lines.append(
                f"DUPLICATE: match={dup_kind} existing={dup_id!r} -- sem acao"
            )
            report = "\n".join(report_lines) + "\n"
            return IntakeResult(
                rc=0, route=route, applied=False,
                existing_id=(dup_id if dup_kind != "description_inbox"
                             or (dup_id and ":" not in str(dup_id))
                             else None) or (
                    candidate.item_id.strip() if candidate.item_id else None
                ),
                report_text=report, candidate_id=candidate.candidate_id,
                dup_match=dup_kind,
            )
        report_lines.append(
            "dry-run: nenhuma escrita. Rode com --apply para persistir."
        )
        report = "\n".join(report_lines) + "\n"
        return IntakeResult(
            rc=2, route=route, applied=False,
            report_text=report, candidate_id=candidate.candidate_id,
        )

    # ---- apply ----
    if enforce_clean_tree:
        dirty, dirty_motivo = _working_tree_dirty(todo_path)
        if dirty:
            raise IntakeError(dirty_motivo or "working tree suja")

    if enforce_empty_classifiable:
        classifiable = _classifiable_inbox_ids(inbox)
        if classifiable:
            raise IntakeError(
                "classifiable_inbox_present: drene a INBOX antes do intake "
                f"({', '.join(classifiable)})"
            )

    # item_id obrigatorio ANTES do journal para rotas que criam linha
    # (L0 / SCOPED / FULL) -- senao grava NEW e aborta com orfao inutil.
    if route in (
        ROUTE_LOCAL_INTEGRATION, ROUTE_SCOPED_REORDER, ROUTE_FULL_REORDER,
    ):
        if not (candidate.item_id or "").strip():
            raise IntakeError(
                f"{route} exige item_id nao vazio"
            )

    journal_dir = _journal_dir_for_todo(todo_path)

    if route == ROUTE_DUPLICATE:
        _write_journal(candidate, journal_dir)
        iid = (candidate.item_id or "").strip()
        existing = dup_id
        # TAB-ADD-007 + TAB-ADD-002: limpa residual do id do candidato e do
        # id casado (descricao na residual ou id na tabela).
        stripped = text
        for strip_id in (iid, existing if dup_kind == "id" else None,
                         existing if dup_kind == "description_table" else None,
                         existing if dup_kind == "description_inbox" else None):
            if not strip_id or strip_id in ("-", PLACEHOLDER):
                continue
            # description_inbox pode devolver raw (com ':') -- strip por raw
            if dup_kind == "description_inbox" and strip_id == existing:
                if ":" in str(strip_id) or any(
                    e.get("raw") == strip_id for e in inbox
                ):
                    stripped = _strip_inbox_raw(stripped, str(strip_id))
                else:
                    stripped = _strip_inbox_id(stripped, str(strip_id))
            else:
                stripped = _strip_inbox_id(stripped, str(strip_id))
        if stripped != text:
            ok, motivo = _provar_invariantes(
                stripped, old_table=table, route=route,
                expected_item_delta=0, preserve_raw_ids=True,
            )
            if not ok:
                raise IntakeError(
                    f"invariante falhou antes da escrita: {motivo}"
                )
            ok, motivo = _escrever_atomico(todo_path, stripped)
            if not ok:
                raise IntakeError(f"escrita atomica falhou: {motivo}")
            escrito = _read_todo(todo_path)
            ok, motivo = _provar_invariantes(
                escrito, old_table=table, route=route,
                expected_item_delta=0, preserve_raw_ids=True,
            )
            if not ok:
                raise IntakeError(
                    f"invariante falhou apos escrita: {motivo}"
                )
            report_lines.append(
                f"DUPLICATE: match={dup_kind} existing={existing!r}; "
                "residual relacionado removido se havia; journal DONE"
            )
        else:
            report_lines.append(
                f"DUPLICATE: match={dup_kind} existing={existing!r}; "
                "journal DONE; nenhuma linha criada"
            )
        J.mark_done(journal_dir, candidate.candidate_id)
        report = "\n".join(report_lines) + "\n"
        existing_out = None
        if existing and dup_kind in ("id", "description_table"):
            existing_out = str(existing)
        elif existing and dup_kind == "description_inbox" and ":" not in str(existing):
            existing_out = str(existing)
        elif iid:
            existing_out = iid
        return IntakeResult(
            rc=0, route=route, applied=True,
            existing_id=existing_out,
            report_text=report, candidate_id=candidate.candidate_id,
            dup_match=dup_kind,
        )

    if route == ROUTE_LOCAL_INTEGRATION:
        _write_journal(candidate, journal_dir)
        novo = _build_l0_text(text, table, candidate)
        # TAB-ADD-007: apos montar a linha, limpa residual com o mesmo id
        novo = _strip_inbox_id(novo, (candidate.item_id or "").strip())
        ok, motivo = _provar_invariantes(
            novo, old_table=table, route=route,
            expected_item_delta=1, preserve_raw_ids=True,
        )
        if not ok:
            raise IntakeError(f"invariante falhou antes da escrita: {motivo}")
        ok, motivo = _escrever_atomico(todo_path, novo)
        if not ok:
            raise IntakeError(f"escrita atomica falhou: {motivo}")
        escrito = _read_todo(todo_path)
        ok, motivo = _provar_invariantes(
            escrito, old_table=table, route=route,
            expected_item_delta=1, preserve_raw_ids=True,
        )
        if not ok:
            raise IntakeError(f"invariante falhou apos escrita: {motivo}")
        J.mark_done(journal_dir, candidate.candidate_id)
        report_lines.append(
            f"LOCAL_INTEGRATION: append de {candidate.item_id!r} "
            f"(marker intake:{candidate.candidate_id})"
        )
        report = "\n".join(report_lines) + "\n"
        return IntakeResult(
            rc=0, route=route, applied=True,
            report_text=report, candidate_id=candidate.candidate_id,
        )

    if route in (ROUTE_SCOPED_REORDER, ROUTE_FULL_REORDER):
        # Build em memoria ANTES do journal: ciclo/equivalencia nao deixa
        # orfao NEW (journal so imediatamente antes da escrita atomica).
        meta = _item_meta_map(table)
        n = len(meta)
        S: set[str] = set()
        promoted_from = None
        effective_route = route
        s_fraction = None

        if route == ROUTE_SCOPED_REORDER:
            S = compute_safe_subgraph_S(table, candidate, meta=meta)
            frac_limit = resolve_scoped_max_fraction(candidate, todo_path)
            s_fraction = (len(S) / n) if n else 0.0
            promote, why = should_promote_scoped_to_full(S, meta, frac_limit)
            if promote:
                promoted_from = ROUTE_SCOPED_REORDER
                effective_route = ROUTE_FULL_REORDER
                report_lines.append(
                    f"promoted_from={ROUTE_SCOPED_REORDER} -> "
                    f"{ROUTE_FULL_REORDER} ({why})"
                )
            else:
                report_lines.append(
                    f"|S|/n={s_fraction:.3f} (limit={frac_limit}); "
                    f"|S|={len(S)} ids={sorted(S)[:12]}"
                )

        explain_blocks: list[str] = []
        if effective_route == ROUTE_SCOPED_REORDER:
            novo, ordered, moved = build_scoped_reorder_text(
                text, table, candidate, S, meta=meta,
            )
            preserve_except = set(S)
            use_preserve_raw = False
        else:
            novo, ordered, moved, explain_blocks = build_full_reorder_text(
                text, table, candidate, meta=meta, todo_path=todo_path,
            )
            preserve_except = None
            use_preserve_raw = False

        # TAB-ADD-007: strip residual com o mesmo id antes da prova/escrita
        novo = _strip_inbox_id(novo, (candidate.item_id or "").strip())

        ok, motivo = _provar_invariantes(
            novo, old_table=table, route=effective_route,
            expected_item_delta=1,
            preserve_raw_ids=use_preserve_raw,
            preserve_raw_ids_except=preserve_except,
        )
        if not ok:
            raise IntakeError(f"invariante falhou antes da escrita: {motivo}")

        _write_journal(candidate, journal_dir)
        ok, motivo = _escrever_atomico(todo_path, novo)
        if not ok:
            raise IntakeError(f"escrita atomica falhou: {motivo}")
        escrito = _read_todo(todo_path)
        ok, motivo = _provar_invariantes(
            escrito, old_table=table, route=effective_route,
            expected_item_delta=1,
            preserve_raw_ids=use_preserve_raw,
            preserve_raw_ids_except=preserve_except,
        )
        if not ok:
            raise IntakeError(f"invariante falhou apos escrita: {motivo}")
        J.mark_done(journal_dir, candidate.candidate_id)
        moved_list = sorted(moved)[:20]
        report_lines.append(
            f"{effective_route}: inseriu {candidate.item_id!r} "
            f"(marker intake:{candidate.candidate_id}); "
            f"ordem={ordered}; moved={moved_list}"
        )
        if s_fraction is not None:
            report_lines.append(f"s_fraction={s_fraction:.3f}")
        # TAB-WSJF-006: so movimentos materiais (pos/onda); sem linha solta
        for block in explain_blocks:
            report_lines.append(block)
        report = "\n".join(report_lines) + "\n"
        return IntakeResult(
            rc=0, route=effective_route, applied=True,
            report_text=report, candidate_id=candidate.candidate_id,
            promoted_from=promoted_from,
            s_ids=sorted(S),
            s_fraction=s_fraction,
        )

    if route in (ROUTE_NEEDS_TRIAGE, ROUTE_NEEDS_LEADER_DECISION):
        _write_journal(candidate, journal_dir)
        novo = _build_residual_text(text, candidate, route)
        ok, motivo = _provar_invariantes(
            novo, old_table=table, route=route,
            expected_item_delta=0, preserve_raw_ids=True,
        )
        if not ok:
            raise IntakeError(f"invariante falhou antes da escrita: {motivo}")
        ok, motivo = _escrever_atomico(todo_path, novo)
        if not ok:
            raise IntakeError(f"escrita atomica falhou: {motivo}")
        escrito = _read_todo(todo_path)
        ok, motivo = _provar_invariantes(
            escrito, old_table=table, route=route,
            expected_item_delta=0, preserve_raw_ids=True,
        )
        if not ok:
            raise IntakeError(f"invariante falhou apos escrita: {motivo}")
        # metadado residual parseavel
        entries = L.inbox_entries(escrito)
        iid = (candidate.item_id or "").strip()
        found = None
        for e in entries:
            if iid and e.get("id") == iid:
                found = e
                break
            if candidate.candidate_id in (e.get("description") or ""):
                found = e
                break
        if found is None or not found["triage"]["valid"]:
            raise IntakeError(
                "residual INBOX gravado sem metadado [triage] valido"
            )
        J.mark_done(journal_dir, candidate.candidate_id)
        report_lines.append(
            f"{route}: residual INBOX id={found.get('id')!r} "
            f"reason={found['triage']['fields'].get('reason')}"
        )
        report = "\n".join(report_lines) + "\n"
        return IntakeResult(
            rc=0, route=route, applied=True,
            report_text=report, candidate_id=candidate.candidate_id,
        )

    raise IntakeError(f"rota desconhecida: {route!r}")


# ---------------------------------------------------------------------------
# --drain (TAB-INBOX-003/004)
# ---------------------------------------------------------------------------

def _judgment_key_for_entry(entry: dict) -> str:
    iid = entry.get("id")
    if iid and str(iid).strip() and str(iid).strip() not in ("-", PLACEHOLDER):
        return str(iid).strip()
    return (entry.get("raw") or "").strip()


def _candidate_from_judgment_dict(data: dict) -> WorkCandidate:
    """Monta WorkCandidate a partir de um dict do --judgments-json."""
    if not isinstance(data, dict):
        raise IntakeError("item de judgment deve ser objeto JSON")
    deps = data.get("dependencies") or []
    if isinstance(deps, str):
        deps = [d.strip() for d in re.split(r"[,;]", deps) if d.strip()]
    cid = data.get("candidate_id") or data.get("item_id") or ""
    if not cid:
        raise IntakeError("judgment item exige candidate_id ou item_id")
    return WorkCandidate(
        candidate_id=str(cid),
        description=str(data.get("description") or ""),
        source=str(data.get("source") or "agent"),
        evidence=str(data.get("evidence") or ""),
        source_item=str(data.get("source_item") or ""),
        dependencies=list(deps),
        item_id=str(data.get("item_id") or ""),
        onda=str(data.get("onda") or ""),
        grupo=str(data.get("grupo") or ""),
        prioridade=str(data.get("prioridade") or ""),
        dificuldade=str(data.get("dificuldade") or ""),
        prereq=str(data.get("prereq") or ""),
        status=str(data.get("status") or DEFAULT_STATUS),
        estado_auditado=str(data.get("estado_auditado") or ""),
        fields_complete=bool(data.get("fields_complete", False)),
        authority_ok=bool(data.get("authority_ok", True)),
        is_foundation=bool(data.get("is_foundation", False)),
        is_local=bool(data.get("is_local", False)),
        is_scoped=bool(data.get("is_scoped", False)),
        reason=str(data.get("reason") or ""),
        acceptance=str(data.get("acceptance") or ""),
        bv=data.get("bv"),
        time_criticality=data.get("time_criticality"),
        risk_reduction=data.get("risk_reduction"),
        job_size=data.get("job_size"),
        peer_scores=data.get("peer_scores")
        if isinstance(data.get("peer_scores"), dict) else None,
        wsjf_profile=(
            str(data["wsjf_profile"])
            if data.get("wsjf_profile") is not None else None
        ),
        scoped_max_fraction=(
            float(data["scoped_max_fraction"])
            if data.get("scoped_max_fraction") is not None else None
        ),
    )


def _bump_cycles_fields(fields: dict) -> dict:
    out = dict(fields)
    raw = out.get("cycles", "0")
    try:
        n = int(raw) if str(raw).isdigit() else 0
    except (TypeError, ValueError):
        n = 0
    out["cycles"] = str(n + 1)
    return out


def _format_residual_body(entry: dict, fields: dict, free_desc: str) -> str:
    meta = L.format_triage_metadata(
        since=fields.get("since") or _utc_date_iso(),
        reason=fields.get("reason") or "missing-info",
        source=fields.get("source"),
        cycles=int(fields["cycles"]) if str(fields.get("cycles", "")).isdigit()
        else 0,
        ref=fields.get("ref"),
    )
    iid = entry.get("id") or PLACEHOLDER
    return f"{iid}: {meta}{free_desc}"


def run_drain(*, todo_path: str, apply: bool = False,
              judgments: dict | None = None) -> DrainResult:
    """Drena a INBOX residual (TAB-INBOX-003/004).

    - classifiable (sem triage valido): dry-run lista + exit 2; apply exige
      entrada em judgments (integrate|split|keep).
    - residual com triage valido: em apply, incrementa cycles; reason
      needs-leader-decision NAO auto-integra.
    - pos-condicao apply ok: classifiable_inbox_count == 0 (senao rc=1).
    - working tree limpa exigida no apply (igual intake).
    """
    try:
        return _run_drain_inner(
            todo_path=todo_path, apply=apply, judgments=judgments or {},
        )
    except IntakeError as exc:
        return DrainResult(
            rc=1, applied=False, error=str(exc),
            report_text=f"erro: {exc}\n",
        )
    except J.IntakeJournalError as exc:
        return DrainResult(
            rc=1, applied=False, error=str(exc),
            report_text=f"erro journal: {exc}\n",
        )


def _run_drain_inner(*, todo_path: str, apply: bool,
                     judgments: dict) -> DrainResult:
    text = _read_todo(todo_path)
    table = L.parse_table(text)
    if table is None:
        raise IntakeError("nenhuma tabela ID+Status reconhecida no TODO.md")
    entries = L.inbox_entries(text)
    classifiable = [e for e in entries if e.get("classifiable")]
    residual = [e for e in entries if not e.get("classifiable")]

    report_lines = [
        "=== tab_pendencias --drain ===",
        f"mode: {'apply' if apply else 'dry-run'}",
        f"classifiable: {len(classifiable)}",
        f"residual: {len(residual)}",
    ]

    missing_judgments: list[str] = []
    for e in classifiable:
        key = _judgment_key_for_entry(e)
        if key not in judgments:
            missing_judgments.append(key or "(sem-chave)")

    for e in classifiable:
        key = _judgment_key_for_entry(e)
        report_lines.append(
            f"classifiable: {key!r} desc={_inbox_free_description(e)[:60]!r}"
        )
    for e in residual:
        fields = (e.get("triage") or {}).get("fields") or {}
        report_lines.append(
            f"residual: {e.get('id')!r} reason={fields.get('reason')!r} "
            f"cycles={fields.get('cycles', '0')}"
        )

    if not apply:
        if classifiable or residual:
            if classifiable and missing_judgments:
                report_lines.append(
                    "dry-run: classifiable exige --judgments-json no apply; "
                    f"faltando: {', '.join(missing_judgments)}"
                )
            else:
                report_lines.append(
                    "dry-run: nenhuma escrita. Rode com --apply para persistir."
                )
            report = "\n".join(report_lines) + "\n"
            return DrainResult(
                rc=2, applied=False, report_text=report,
                classifiable_remaining=len(classifiable),
            )
        report_lines.append("INBOX vazia -- nada a drenar.")
        return DrainResult(
            rc=0, applied=False, report_text="\n".join(report_lines) + "\n",
            classifiable_remaining=0,
        )

    # ---- apply ----
    dirty, dirty_motivo = _working_tree_dirty(todo_path)
    if dirty:
        raise IntakeError(dirty_motivo or "working tree suja")

    if classifiable and missing_judgments:
        raise IntakeError(
            "classifiable_sem_judgment: forneca --judgments-json para: "
            + ", ".join(missing_judgments)
        )

    # Validar judgments antes de mutar
    to_integrate: list[WorkCandidate] = []
    keep_specs: list[tuple[dict, dict]] = []  # (entry, judgment)
    for e in classifiable:
        key = _judgment_key_for_entry(e)
        j = judgments[key]
        if not isinstance(j, dict):
            raise IntakeError(f"judgment de {key!r} deve ser objeto")
        action = (j.get("action") or "").strip().lower()
        if action == "keep":
            reason = j.get("reason") or "missing-info"
            if reason not in L.TRIAGE_REASONS:
                raise IntakeError(
                    f"keep em {key!r}: reason fora do vocabulario: {reason!r}"
                )
            keep_specs.append((e, j))
        elif action == "integrate":
            items = j.get("items")
            if items is None and j.get("item_id"):
                items = [j]
            if not items or len(items) != 1:
                raise IntakeError(
                    f"integrate em {key!r} exige exatamente 1 item "
                    "(campo items[0] ou campos flat)"
                )
            to_integrate.append(_candidate_from_judgment_dict(items[0]))
        elif action == "split":
            items = j.get("items") or []
            if not items:
                raise IntakeError(f"split em {key!r} exige items nao-vazio")
            for it in items:
                to_integrate.append(_candidate_from_judgment_dict(it))
        else:
            raise IntakeError(
                f"judgment de {key!r}: action deve ser "
                f"integrate|split|keep (recebido {action!r})"
            )

    # 1) residual: cycles++ (inclui needs-leader -- sem auto-integrar)
    work = text
    bumped: list[str] = []
    for e in residual:
        fields = dict((e.get("triage") or {}).get("fields") or {})
        free = _inbox_free_description(e)
        new_fields = _bump_cycles_fields(fields)
        body = _format_residual_body(e, new_fields, free)
        work = _rewrite_inbox_entry_line(
            work, match_raw=e.get("raw"), new_body=body,
        )
        bumped.append(str(e.get("id") or e.get("raw")))

    # 2) keep: classifiable -> residual com triage
    kept_ids: list[str] = []
    for e, j in keep_specs:
        reason = j.get("reason") or "missing-info"
        free = _inbox_free_description(e)
        if j.get("description"):
            free = str(j["description"])
        fields = {
            "since": _utc_date_iso(),
            "reason": reason,
            "source": j.get("source") or "agent",
            "cycles": "0",
        }
        body = _format_residual_body(e, fields, free)
        work = _rewrite_inbox_entry_line(
            work, match_raw=e.get("raw"), new_body=body,
        )
        kept_ids.append(_judgment_key_for_entry(e))

    # 3) remove linhas de integrate/split (originais classifiable)
    integrate_keys = set()
    for e in classifiable:
        key = _judgment_key_for_entry(e)
        j = judgments[key]
        action = (j.get("action") or "").strip().lower()
        if action in ("integrate", "split"):
            work = _strip_inbox_raw(work, e.get("raw") or "")
            integrate_keys.add(key)

    # Escreve estado intermediario (inbox preparada) se algo mudou
    if work != text:
        ok, motivo = _escrever_atomico(todo_path, work)
        if not ok:
            raise IntakeError(f"escrita atomica (pre-intake) falhou: {motivo}")
        text = work

    # 4) run_intake por candidato (arvore ja suja; classifiable deve ser 0)
    integrated_ids: list[str] = []
    for cand in to_integrate:
        result = run_intake(
            todo_path=todo_path,
            candidate=cand,
            apply=True,
            enforce_clean_tree=False,
            enforce_empty_classifiable=True,
        )
        if result.rc != 0:
            raise IntakeError(
                f"intake falhou para {cand.candidate_id!r} "
                f"(route={result.route}): {result.error or result.report_text}"
            )
        integrated_ids.append(cand.item_id or cand.candidate_id)
        report_lines.append(
            f"integrated: {cand.item_id or cand.candidate_id!r} "
            f"route={result.route}"
        )

    final_text = _read_todo(todo_path)
    remaining = classifiable_inbox_count(final_text)
    report_lines.append(f"classifiable_remaining: {remaining}")
    report_lines.append(f"residual_bumped: {bumped}")
    report_lines.append(f"kept: {kept_ids}")
    report_lines.append(f"integrated: {integrated_ids}")

    if remaining != 0:
        report = "\n".join(report_lines) + "\n"
        return DrainResult(
            rc=1, applied=True, error="classifiable_inbox_count != 0",
            report_text=report, classifiable_remaining=remaining,
            residual_bumped=bumped, integrated=integrated_ids, kept=kept_ids,
        )

    report_lines.append("drain ok: classifiable_inbox_count == 0")
    return DrainResult(
        rc=0, applied=True,
        report_text="\n".join(report_lines) + "\n",
        classifiable_remaining=0,
        residual_bumped=bumped, integrated=integrated_ids, kept=kept_ids,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _candidate_from_args(args, json_obj=None) -> WorkCandidate:
    data = dict(json_obj or {})
    # flags CLI sobrescrevem JSON
    def pick(key, cli_val, default=None):
        if cli_val is not None and cli_val != "" and cli_val is not False:
            return cli_val
        if key in data:
            return data[key]
        return default

    deps = list(args.dep or [])
    if not deps and isinstance(data.get("dependencies"), list):
        deps = list(data["dependencies"])

    fields_complete = bool(args.fields_complete or data.get("fields_complete"))
    authority_ok = not args.no_authority
    if "authority_ok" in data and args.no_authority is False:
        # so se --no-authority nao foi passado; argparse store_true default False
        if not args.no_authority:
            authority_ok = bool(data.get("authority_ok", True))
    if args.no_authority:
        authority_ok = False

    is_foundation = bool(args.foundation or data.get("is_foundation"))
    is_local = bool(args.local or data.get("is_local"))
    is_scoped = bool(args.scoped or data.get("is_scoped"))

    cid = pick("candidate_id", args.candidate_id) or data.get("candidate_id")
    if not cid:
        raise IntakeError("--candidate-id (ou JSON candidate_id) obrigatorio")
    desc = pick("description", args.description)
    if desc is None:
        desc = data.get("description", "")
    source = pick("source", args.source) or data.get("source") or "user"

    def _opt_int(key_cli, key_json, alt_json=None):
        """Lê int opcional de CLI ou JSON; None se ausente/vazio."""
        raw = getattr(args, key_cli, None)
        if raw is None or raw == "":
            if key_json in data and data[key_json] is not None:
                raw = data[key_json]
            elif alt_json and alt_json in data and data[alt_json] is not None:
                raw = data[alt_json]
            else:
                return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    peer_scores = data.get("peer_scores")
    if peer_scores is not None and not isinstance(peer_scores, dict):
        peer_scores = None

    return WorkCandidate(
        candidate_id=str(cid),
        description=str(desc or ""),
        source=str(source),
        evidence=str(pick("evidence", args.evidence) or data.get("evidence") or ""),
        source_item=str(
            pick("source_item", args.source_item)
            or data.get("source_item") or ""
        ),
        dependencies=deps,
        item_id=str(pick("item_id", args.item_id) or data.get("item_id") or ""),
        onda=str(data.get("onda") or ""),
        grupo=str(data.get("grupo") or ""),
        prioridade=str(data.get("prioridade") or ""),
        dificuldade=str(data.get("dificuldade") or ""),
        prereq=str(data.get("prereq") or ""),
        status=str(data.get("status") or DEFAULT_STATUS),
        estado_auditado=str(data.get("estado_auditado") or ""),
        fields_complete=fields_complete,
        authority_ok=authority_ok,
        is_foundation=is_foundation,
        is_local=is_local,
        is_scoped=is_scoped,
        reason=str(args.reason or data.get("reason") or ""),
        acceptance=str(
            getattr(args, "acceptance", None)
            or data.get("acceptance")
            or ""
        ),
        scoped_max_fraction=(
            float(data["scoped_max_fraction"])
            if data.get("scoped_max_fraction") is not None
            else None
        ),
        bv=_opt_int("bv", "bv", "business_value"),
        time_criticality=_opt_int("time_criticality", "time_criticality", "tc"),
        risk_reduction=_opt_int("risk_reduction", "risk_reduction", "rr"),
        job_size=_opt_int("job_size", "job_size", "js"),
        peer_scores=peer_scores,
        wsjf_profile=(
            str(data["wsjf_profile"])
            if data.get("wsjf_profile") is not None
            else None
        ),
        comparable_epsilon=(
            float(data["comparable_epsilon"])
            if data.get("comparable_epsilon") is not None
            else None
        ),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="todo_intake",
        description=(
            "Motor mecanico de intake (ADR-0002): classifica WorkCandidate "
            "e persiste L0 / residual INBOX / SCOPED_REORDER / FULL_REORDER; "
            "--drain tria a INBOX residual."
        ),
    )
    p.add_argument("--todo", required=False, default=None,
                   help="Caminho do TODO.md (default: ./TODO.md via find_todo)")
    p.add_argument("--apply", action="store_true",
                   help="Persiste a rota (default: dry-run)")
    p.add_argument("--drain", action="store_true",
                   help="Drena a INBOX (TAB-INBOX-004); ver --judgments-json")
    p.add_argument(
        "--judgments-json", default=None,
        help="JSON de julgamentos do drain (path ou '-' = stdin)",
    )
    p.add_argument("--candidate-id", default=None)
    p.add_argument("--item-id", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--source", default=None,
                   help="user|bus|agent|audit|test")
    p.add_argument("--evidence", default=None)
    p.add_argument("--source-item", default=None)
    p.add_argument("--dep", action="append", default=None,
                   help="Dependencia (ID); repetivel")
    p.add_argument("--fields-complete", action="store_true",
                   help="Julgamento: P-campos (campos minimos ok)")
    p.add_argument("--no-authority", action="store_true",
                   help="Julgamento: P-autoridade falso")
    p.add_argument("--foundation", action="store_true",
                   help="Julgamento: P-fundacao")
    p.add_argument("--local", action="store_true",
                   help="Julgamento: P-local (L0)")
    p.add_argument("--scoped", action="store_true",
                   help="Julgamento: P-escopado (L1)")
    p.add_argument("--reason", default=None,
                   help="Override do reason de triagem (vocabulario fechado)")
    p.add_argument("--acceptance", default=None,
                   help="Criterios de aceitacao opcionais (TAB-ADD-002)")
    p.add_argument("--bv", default=None, type=int,
                   help="WSJF business value (fib int)")
    p.add_argument("--time-criticality", default=None, type=int,
                   dest="time_criticality",
                   help="WSJF time criticality (fib int)")
    p.add_argument("--risk-reduction", default=None, type=int,
                   dest="risk_reduction",
                   help="WSJF risk reduction (fib int)")
    p.add_argument("--job-size", default=None, type=int, dest="job_size",
                   help="WSJF job size (fib int)")
    p.add_argument("--json", action="store_true",
                   help="Ler WorkCandidate JSON de stdin")
    return p


def _load_judgments(path_or_dash: str) -> dict:
    if path_or_dash == "-":
        raw = sys.stdin.read()
    else:
        try:
            with open(path_or_dash, encoding="utf-8", newline="") as fh:
                raw = fh.read()
        except OSError as exc:
            raise IntakeError(
                f"falha ao ler judgments-json ({type(exc).__name__}: {exc})"
            ) from exc
    try:
        obj = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise IntakeError(f"judgments-json invalido: {exc}") from exc
    if not isinstance(obj, dict):
        raise IntakeError("judgments-json deve ser um objeto {id: judgment}")
    return obj


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse: flag desconhecida / -h
        code = exc.code
        if code in (0, None):
            return 0
        return 1

    try:
        todo = args.todo
        if not todo:
            root = L.repo_root(os.getcwd()) or os.getcwd()
            todo = L.find_todo(root)
            if not todo:
                print("erro: TODO.md nao encontrado (passe --todo)",
                      file=sys.stderr)
                return 1

        if args.drain:
            judgments = {}
            if args.judgments_json:
                judgments = _load_judgments(args.judgments_json)
            elif args.json:
                # --json no drain = judgments em stdin
                raw = sys.stdin.read()
                try:
                    obj = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError as exc:
                    print(f"erro: JSON stdin invalido: {exc}", file=sys.stderr)
                    return 1
                if not isinstance(obj, dict):
                    print("erro: judgments stdin deve ser objeto",
                          file=sys.stderr)
                    return 1
                judgments = obj
            result = run_drain(
                todo_path=todo, apply=args.apply, judgments=judgments,
            )
        else:
            json_obj = None
            if args.json:
                raw = sys.stdin.read()
                try:
                    json_obj = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError as exc:
                    print(f"erro: JSON stdin invalido: {exc}", file=sys.stderr)
                    return 1

            candidate = _candidate_from_args(args, json_obj)
            if args.acceptance:
                candidate.acceptance = args.acceptance
            result = run_intake(todo_path=todo, candidate=candidate,
                                apply=args.apply)
    except IntakeError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(result.report_text)
    if result.error and result.rc != 0:
        sys.stderr.write(f"erro: {result.error}\n")
    return result.rc


if __name__ == "__main__":
    raise SystemExit(main())
