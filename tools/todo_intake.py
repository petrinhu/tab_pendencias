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

Fatia vertical TAB-ADD-001 / TAB-ADD-002-meca / TAB-ADD-003-cascata /
TAB-ADD-004-L0: recebe um WorkCandidate ja julgado (flags booleanas de
predicado preenchidas por quem chama -- o nucleo NAO infere de prosa),
decide a rota pela cascata fixa, e em --apply persiste apenas o que esta
implementado nesta fatia:

  DUPLICATE            -- nao cria linha; journal DONE
  LOCAL_INTEGRATION    -- append puro de 1 linha (L0)
  NEEDS_TRIAGE         -- residual INBOX com [triage reason=missing-info]
  NEEDS_LEADER_DECISION -- residual INBOX com [triage reason=needs-leader-decision]
  SCOPED_REORDER       -- dry-run ok; apply aborta not_implemented
  FULL_REORDER         -- dry-run ok; apply aborta not_implemented

Journal write-ahead (intake_journal) antes de mutacao; mark_done apos
escrita validada. Escrita atomica (temp + os.replace), encoding utf-8,
newline preservado. stdlib only.
"""
from __future__ import annotations

import argparse
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
INBOX_HEADING = "## INBOX (descobertas não priorizadas)"
INTAKE_MARKER_TMPL = "<!-- intake:{cid} -->"

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


@dataclass
class IntakeResult:
    rc: int
    route: str | None = None
    applied: bool = False
    error: str | None = None
    existing_id: str | None = None
    report_text: str = ""
    candidate_id: str = ""


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


def _existing_ids(table: dict | None, inbox: list) -> set[str]:
    ids: set[str] = set()
    if table:
        for it in table["items"]:
            if it["id"]:
                ids.add(it["id"])
    for e in inbox:
        if e.get("id"):
            ids.add(e["id"])
    return ids


def _table_ids(table: dict | None) -> set[str]:
    if not table:
        return set()
    return {it["id"] for it in table["items"] if it["id"]}


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
    iid = (candidate.item_id or "").strip()
    if not iid or iid in ("-", PLACEHOLDER):
        return False
    return iid in _existing_ids(table, inbox)


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

    # L0: linhas brutas de IDs antigos identicas
    if preserve_raw_ids:
        old_raw = _raw_lines_by_id(old_table)
        new_raw = _raw_lines_by_id(novo)
        for iid, raw in old_raw.items():
            if iid not in new_raw:
                return False, f"L0: linha de {iid!r} ausente apos append"
            if new_raw[iid] != raw:
                return False, (
                    f"L0: bytes da linha de {iid!r} mudaram (append puro "
                    "exige zero tocada)"
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
              apply: bool = False) -> IntakeResult:
    """Decide rota e, se apply, persiste. Nunca levanta para fluxos
    esperados -- devolve IntakeResult com rc."""
    try:
        return _run_intake_inner(todo_path=todo_path, candidate=candidate,
                                 apply=apply)
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
                      apply: bool) -> IntakeResult:
    if not candidate.candidate_id:
        raise IntakeError("candidate_id obrigatorio")

    text = _read_todo(todo_path)
    table = L.parse_table(text)
    if table is None:
        raise IntakeError("nenhuma tabela ID+Status reconhecida no TODO.md")
    inbox = L.inbox_entries(text)
    route = decide_route(candidate, table, inbox)

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
                f"DUPLICATE: id {candidate.item_id!r} ja existe -- sem acao"
            )
            report = "\n".join(report_lines) + "\n"
            return IntakeResult(
                rc=0, route=route, applied=False,
                existing_id=candidate.item_id.strip(),
                report_text=report, candidate_id=candidate.candidate_id,
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
    dirty, dirty_motivo = _working_tree_dirty(todo_path)
    if dirty:
        raise IntakeError(dirty_motivo or "working tree suja")

    classifiable = _classifiable_inbox_ids(inbox)
    if classifiable:
        raise IntakeError(
            "classifiable_inbox_present: drene a INBOX antes do intake "
            f"({', '.join(classifiable)})"
        )

    if route in (ROUTE_SCOPED_REORDER, ROUTE_FULL_REORDER):
        raise IntakeError(f"not_implemented:{route}")

    # L0 exige item_id nao vazio ANTES do journal -- senao grava NEW e
    # aborta depois, deixando orfao permanente sem mutacao util.
    if route == ROUTE_LOCAL_INTEGRATION:
        if not (candidate.item_id or "").strip():
            raise IntakeError("LOCAL_INTEGRATION exige item_id nao vazio")

    journal_dir = _journal_dir_for_todo(todo_path)
    _write_journal(candidate, journal_dir)

    if route == ROUTE_DUPLICATE:
        J.mark_done(journal_dir, candidate.candidate_id)
        report_lines.append(
            f"DUPLICATE: id {candidate.item_id!r} ja existe; journal DONE; "
            "nenhuma linha criada"
        )
        report = "\n".join(report_lines) + "\n"
        return IntakeResult(
            rc=0, route=route, applied=True,
            existing_id=candidate.item_id.strip(),
            report_text=report, candidate_id=candidate.candidate_id,
        )

    if route == ROUTE_LOCAL_INTEGRATION:
        novo = _build_l0_text(text, table, candidate)
        ok, motivo = _provar_invariantes(
            novo, old_table=table, route=route,
            expected_item_delta=1, preserve_raw_ids=True,
        )
        if not ok:
            raise IntakeError(f"invariante falhou antes da escrita: {motivo}")
        ok, motivo = _escrever_atomico(todo_path, novo)
        if not ok:
            raise IntakeError(f"escrita atomica falhou: {motivo}")
        # revalidar no disco
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

    if route in (ROUTE_NEEDS_TRIAGE, ROUTE_NEEDS_LEADER_DECISION):
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
    )


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="todo_intake",
        description=(
            "Motor mecanico de intake (ADR-0002): classifica WorkCandidate "
            "e persiste L0 / residual INBOX. SCOPED/FULL: so dry-run nesta "
            "fatia."
        ),
    )
    p.add_argument("--todo", required=False, default=None,
                   help="Caminho do TODO.md (default: ./TODO.md via find_todo)")
    p.add_argument("--apply", action="store_true",
                   help="Persiste a rota (default: dry-run)")
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
    p.add_argument("--json", action="store_true",
                   help="Ler WorkCandidate JSON de stdin")
    return p


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
        json_obj = None
        if args.json:
            raw = sys.stdin.read()
            try:
                json_obj = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError as exc:
                print(f"erro: JSON stdin invalido: {exc}", file=sys.stderr)
                return 1

        todo = args.todo
        if not todo:
            root = L.repo_root(os.getcwd()) or os.getcwd()
            todo = L.find_todo(root)
            if not todo:
                print("erro: TODO.md nao encontrado (passe --todo)",
                      file=sys.stderr)
                return 1

        candidate = _candidate_from_args(args, json_obj)
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
