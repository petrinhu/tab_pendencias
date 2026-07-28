#!/usr/bin/env python3
# tools/todo_fix.py -- motor do `--fix` (FIX-ENG, ADR-0001 seção c)
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
tools/todo_fix.py

Motor do `--fix` (FIX-ENG, ADR-0001 seção c): a fatia de MAIOR risco do
projeto -- `--audit`/`todo_sync`/`todo_health`/`todo_freshness` só LEEM;
este módulo ESCREVE no TODO.md do usuário. Um erro aqui corrompe dado de
terceiro de um jeito que nenhum teste desta suíte vai presenciar.

Contrato (ADR-0001 c, não redecidido aqui): `--fix` consome o que os checks
do `--audit` já decidiram -- `Finding.fixable`/`Finding.fix_ref`, emitidos
por `checks/chk_core.py` -- e NUNCA redecide o que é fixável. Hoje só dois
`fix_ref` são de fato produzidos pelo catálogo registrado:

  escapar_pipe_cru            (CHK-02) -- pipe cru não escapado, célula(s)
                                a mais.
  remover_fragmento_duplicado (CHK-01) -- ID duplicado onde uma ocorrência
                                é claramente fragmento/lixo (placeholder
                                vazio ou prefixo truncado da outra).

`CHK-03`/`CHK-04` (tabela fragmentada) e `CHK-09` (claim obsoleta) NUNCA
marcam `fixable=True` na implementação atual -- "consolidar tabela
fragmentada" e "corrigir claim obsoleta" (previstos no ADR-0001/TODO.md)
não têm hoje nenhum achado real para este motor consumir; ver nota "no
silent caps" no relatório final da fatia, não é lacuna deste módulo.

--- Regra de segurança adicional deste motor (além do que CHK-02 decide) ---

CHK-02 marca `fixable=True` sempre que há célula(s) a mais, mesmo quando a
mensagem é a heurística GENÉRICA ("algum '|' literal não foi escapado",
sem apontar POSIÇÃO exata). Este motor é deliberadamente MAIS conservador
que o check: só aplica a correção quando consegue localizar, sem ambiguidade,
pipe(s) cru(s) dentro de um code span (crase) cuja contagem feche EXATAMENTE
o excesso de células -- o único subcaso em que a posição é inequívoca. Nos
demais casos (marcados [auto-fixável] pelo `--audit`, mas sem posição
localizável com segurança por este motor), o item aparece no plano como
NÃO aplicável, com o motivo explícito -- nunca escreve adivinhando.

--- Escrita atômica com prova ANTES de commitar ---------------------------

Nunca escreve in-place. Monta o texto novo inteiro em memória, reparseia e
prova os invariantes (round-trip do que não foi tocado + contagem de itens
esperada, calculada ANTES de escrever) contra esse texto; só then grava um
arquivo temporário no MESMO diretório (mesmo filesystem, `os.replace`
atômico de verdade), relê o que foi escrito e confere byte-a-byte, e só
troca o arquivo real por último. Qualquer falha em qualquer um desses
passos aborta SEM tocar o TODO.md real -- "escrever sem conseguir provar é
pior que não escrever" (o mandato do team-lead).

Pré-condição (ADR-0001 c, D-6): `--apply` só roda com a working tree do
TODO.md limpa (`git status --porcelain -- <path>` vazio); working tree suja,
ou ausência de repositório git resolvível, aborta ANTES de qualquer escrita.

Uso:
  python3 todo_fix.py                              # dry-run: so mostra o plano
  python3 todo_fix.py --apply escapar_pipe_cru      # aplica so esta classe
  python3 todo_fix.py --apply remover_fragmento_duplicado
  python3 todo_fix.py --apply all                   # aplica todas as detectadas

Exit codes (D-6, os mesmos 3 valores fixos do resto do toolkit): 0 =
execução ok e nada a corrigir; 1 = erro de execução (não é repositório git,
TODO.md ilegível, working tree suja ao aplicar, falha de escrita); 2 =
execução ok e há 1+ correção disponível (mostrada em dry-run OU aplicada).
"""
from __future__ import annotations

import argparse
import configparser
import os
import re
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field

import todo_audit as A
import todo_lib as L
from checks import chk_core

_CONHECIDOS = ("escapar_pipe_cru", "remover_fragmento_duplicado")


class FixError(Exception):
    """Erro de execução (D-6): TODO.md ilegível, etc. -- vira exit 1."""


# ------------------------------- estruturas --------------------------------

@dataclass(frozen=True)
class PlanItem:
    """Um item do plano de correção -- não confunda com `Finding` (que é do
    `--audit`): este é o que o MOTOR DE FIX decidiu que consegue (ou não)
    tocar com segurança a partir de um achado marcado `fixable=True`."""
    fix_ref: str
    check_id: str
    description: str
    line_no: int          # 0-based, mesmo indice de `table['lines']`
    diff: str | None
    aplicavel: bool       # False = marcado fixable pelo check, mas o MOTOR
                          # recusa aplicar (posição ambígua, ver docstring
                          # do módulo) -- nunca escreve adivinhando.
    motivo_recusa: str | None
    delta_itens: int      # impacto esperado em len(table['items']) se este
                          # item for aplicado sozinho: +1 (escape que produz
                          # item novo), 0 (escape que não produz item), -1
                          # (remoção de uma ocorrência duplicada).


@dataclass(frozen=True)
class FixPlan:
    todo_path: str | None
    items: list = field(default_factory=list)     # list[PlanItem]
    notices: list = field(default_factory=list)   # list[str] -- no silent caps


@dataclass
class FixResult:
    rc: int
    report_text: str
    applied: bool
    plan: FixPlan | None


# ------------------------------- leitura ------------------------------------

def _read_todo(todo_path):
    """Leitura explícita de encoding (D-11/ADR-0001 e.3): utf-8 sempre,
    `newline=""` para preservar CRLF/LF -- o mesmo contrato de
    `todo_audit._read_todo`/`todo_sync.run`."""
    try:
        with open(todo_path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except Exception as exc:
        raise FixError(
            f"Falha ao ler TODO.md ({type(exc).__name__}): {exc}") from exc


def _ler_e_parsear(todo_path):
    text = _read_todo(todo_path)
    return text, L.parse_table(text)


# ------------------------- escapar_pipe_cru (CHK-02) ------------------------
#
# Estratégia deliberadamente restrita (ver docstring do módulo): só escapa
# pipe(s) crus localizados DENTRO de um code span (crase) -- o único
# subcaso em que a posição é inequívoca -- e só quando a contagem exata
# fecha com o excesso de células. Qualquer ambiguidade recusa, nunca
# adivinha (nunca escreve no lugar errado, mesma filosofia conservadora do
# núcleo, ADR-0001 b.5).

_CODE_SPAN = re.compile(r"`[^`\n]*`")
_RAW_PIPE = re.compile(r"(?<!\\)\|")


def _pipes_dentro_de_code_span(s):
    """Posições (0-based, na string `s`) de pipes NÃO escapados que estão
    dentro de algum code span (crase). Lista ordenada crescente."""
    out = []
    for span in _CODE_SPAN.finditer(s):
        ini, fim = span.span()
        for m in _RAW_PIPE.finditer(s, ini, fim):
            out.append(m.start())
    return sorted(out)


def _escapar_posicoes(s, posicoes):
    """Insere '\\' antes de cada posição -- processa da DIREITA para a
    ESQUERDA para não invalidar os índices anteriores ainda não tratados."""
    out = s
    for p in sorted(posicoes, reverse=True):
        out = out[:p] + "\\" + out[p:]
    return out


def _tentar_escapar_pipe_cru(raw_line, expected_ncols):
    """(nova_linha_ou_None, motivo_recusa_ou_None). Preserva o terminador
    original (CRLF/LF/nenhum) -- mesmo contrato de `todo_lib.set_status_cell`."""
    stripped = raw_line.rstrip("\r\n")
    tail = raw_line[len(stripped):]
    obtido = len(L._cells(stripped))
    excesso = obtido - expected_ncols
    if excesso <= 0:
        return None, (
            f"linha não tem célula(s) em excesso (obtidas={obtido}, "
            f"esperadas={expected_ncols}) -- não é o caso 'pipe cru' que "
            "este fixer trata.")
    posicoes = _pipes_dentro_de_code_span(stripped)
    if len(posicoes) != excesso:
        return None, (
            f"{len(posicoes)} pipe(s) cru(s) localizado(s) dentro de code "
            f"span (crase), mas o excesso de célula(s) é {excesso} -- "
            "posição ambígua fora de code span; o motor de fix RECUSA "
            "adivinhar (nunca escreve no lugar errado).")
    nova_stripped = _escapar_posicoes(stripped, posicoes)
    if len(L._cells(nova_stripped)) != expected_ncols:
        return None, (
            "após escapar os pipes localizados em code span, a linha ainda "
            f"não reparseia para {expected_ncols} célula(s) -- recusado.")
    return nova_stripped + tail, None


# --------------------- remover_fragmento_duplicado (CHK-01) -----------------

def _sem_terminador(raw):
    return raw.rstrip("\r\n")


# ------------------------------- construção do plano -------------------------

def _itens_do_plano(root, todo_path, text, table):
    ctx = A.Context(root=root, todo_path=todo_path, text=text, table=table,
                    profile="core", config=configparser.ConfigParser())
    items = []
    notices = []

    # ---- CHK-02 -> escapar_pipe_cru ---------------------------------------
    malformed_by_line = {m["line_no"]: m for m in table["malformed"]}
    for f in chk_core._chk02_ncols_diverge(ctx):
        if not (f.fixable and f.fix_ref == "escapar_pipe_cru"):
            continue
        m = malformed_by_line.get(f.line_no)
        if m is None:
            notices.append(
                f"CHK-02 marcou a linha {f.line_no + 1} como [auto-fixável], "
                "mas o motor de fix não encontrou a entrada correspondente "
                "em 'malformed' -- pulado, no silent caps.")
            continue
        raw = table["lines"][f.line_no]
        nova, recusa = _tentar_escapar_pipe_cru(raw, m["expected_ncols"])
        if recusa:
            items.append(PlanItem(
                fix_ref="escapar_pipe_cru", check_id="CHK-02",
                description=(
                    f"linha {f.line_no + 1}: CHK-02 marcou [auto-fixável], "
                    "mas o motor de fix RECUSA aplicar automaticamente"),
                line_no=f.line_no, diff=None, aplicavel=False,
                motivo_recusa=recusa, delta_itens=0))
            continue
        id_idx = table["id_idx"]
        cell_id = L._cells(nova)[id_idx] if id_idx < len(L._cells(nova)) else ""
        vira_item = bool(cell_id) and cell_id not in ("-", "—")
        diff = f"- {_sem_terminador(raw)}\n+ {_sem_terminador(nova)}"
        items.append(PlanItem(
            fix_ref="escapar_pipe_cru", check_id="CHK-02",
            description=(
                f"linha {f.line_no + 1}: escapar pipe cru dentro de code "
                "span (célula a mais)"),
            line_no=f.line_no, diff=diff, aplicavel=True,
            motivo_recusa=None, delta_itens=1 if vira_item else 0))

    # ---- CHK-01 -> remover_fragmento_duplicado ----------------------------
    dup_by_first_line = {occs[0]["line_no"]: (iid, occs)
                          for iid, occs in table["duplicate_ids"].items()}
    for f in chk_core._chk01_id_duplicado(ctx):
        if not (f.fixable and f.fix_ref == "remover_fragmento_duplicado"):
            continue
        found = dup_by_first_line.get(f.line_no)
        if found is None:
            notices.append(
                f"CHK-01 marcou um achado na linha {f.line_no + 1} como "
                "[auto-fixável], mas o motor de fix não conseguiu "
                "re-associar o grupo de duplicatas correspondente -- "
                "pulado, no silent caps.")
            continue
        iid, occs = found
        cells = [L._cells(table["lines"][o["line_no"]]) for o in occs]
        candidato = chk_core._candidato_fragmento(
            cells, table["id_idx"], table["status_idx"])
        if candidato is None:
            # defensivo: Finding.fixable já implica candidato != None (mesma
            # função), mas nunca confiar em invariante alheio sem checar.
            notices.append(
                f"CHK-01 marcou {iid!r} como [auto-fixável], mas o motor de "
                "fix não conseguiu re-derivar qual ocorrência remover -- "
                "pulado, no silent caps.")
            continue
        remover = occs[candidato]
        manter = occs[1 - candidato]
        diff = (
            f"- linha {remover['line_no'] + 1} (REMOVIDA): "
            f"{_sem_terminador(table['lines'][remover['line_no']])}\n"
            f"  linha {manter['line_no'] + 1} (mantida): "
            f"{_sem_terminador(table['lines'][manter['line_no']])}")
        items.append(PlanItem(
            fix_ref="remover_fragmento_duplicado", check_id="CHK-01",
            description=(
                f"ID {iid!r}: remover ocorrência duplicada/fragmento na "
                f"linha {remover['line_no'] + 1} (mantendo a linha "
                f"{manter['line_no'] + 1})"),
            line_no=remover["line_no"], diff=diff, aplicavel=True,
            motivo_recusa=None, delta_itens=-1))

    items.sort(key=lambda it: it.line_no)
    return items, notices


def build_plan(root, todo_path=None):
    """Núcleo READ-ONLY: monta o plano sem nunca escrever nada. Reusado por
    `run_fix` (dry-run) e por consumidores externos (ex.: a sugestão de
    `--fix` ao final de todo `--audit`, regra fixa do líder -- fiada
    conversacional em `SKILL.md`, de outra fatia; aqui só o hook mecânico)."""
    todo_path = todo_path or L.find_todo(root)
    if not todo_path:
        return FixPlan(todo_path=None, items=[], notices=[])
    text, table = _ler_e_parsear(todo_path)
    if not table:
        return FixPlan(todo_path=todo_path, items=[], notices=[
            "Nenhuma tabela ID+Status reconhecida no arquivo; nada a "
            "corrigir."])
    items, notices = _itens_do_plano(root, todo_path, text, table)
    return FixPlan(todo_path=todo_path, items=items, notices=notices)


# ------------------------- precondição: árvore limpa -------------------------

def _working_tree_status(root, todo_path):
    """(sujo: bool, motivo_ou_None). Precisa de um repositório git
    resolvível para PROVAR árvore limpa (ADR-0001 c) -- na ausência de git,
    ou em qualquer falha ao consultar, trata como sujo por segurança
    (nunca aplica sem conseguir provar que está limpo)."""
    rr = L.repo_root(root)
    if not rr:
        return True, (
            "não é um repositório git resolvível a partir daqui -- --apply "
            "exige git para provar a working tree limpa antes de escrever")
    rel = os.path.relpath(os.path.abspath(todo_path), rr)
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--", rel],
                           cwd=rr, capture_output=True, text=True, timeout=15)
    except Exception as exc:
        return True, f"git status falhou ao executar ({type(exc).__name__}: {exc})"
    if r.returncode != 0:
        return True, (
            f"git status --porcelain falhou (rc={r.returncode}): "
            f"{(r.stderr or '').strip()}")
    if r.stdout.strip():
        return True, (
            "working tree do TODO.md tem mudança(s) não commitada(s):\n"
            f"{r.stdout.strip()}")
    return False, None


# ------------------------------- aplicação -----------------------------------

def _montar_novo_texto(table, selecionados):
    """(novo_texto, invariantes) -- nunca toca disco. `invariantes` é o que
    `_provar_e_escrever` confere ANTES de gravar qualquer coisa."""
    lines = list(table["lines"])   # cópia -- nunca muta table['lines']
    malformed_by_line = {m["line_no"]: m for m in table["malformed"]}

    escapes = [it for it in selecionados if it.fix_ref == "escapar_pipe_cru"]
    remocoes_itens = [it for it in selecionados
                       if it.fix_ref == "remover_fragmento_duplicado"]

    for it in escapes:
        m = malformed_by_line.get(it.line_no)
        if m is None:
            raise FixError(
                f"linha {it.line_no + 1}: entrada 'malformed' correspondente "
                "sumiu antes de aplicar -- abortado por segurança.")
        nova, recusa = _tentar_escapar_pipe_cru(lines[it.line_no],
                                                m["expected_ncols"])
        if recusa:
            raise FixError(f"linha {it.line_no + 1}: {recusa}")
        lines[it.line_no] = nova

    remocoes_ordenadas = sorted({it.line_no for it in remocoes_itens})
    remocoes_set = set(remocoes_ordenadas)
    linhas_preservadas = {i: l for i, l in enumerate(lines)
                          if i not in remocoes_set}
    novas_linhas = [l for i, l in enumerate(lines) if i not in remocoes_set]

    n_items_antes = len(table["items"])
    delta_total = sum(it.delta_itens for it in selecionados)
    invariantes = {
        "n_items_esperado": n_items_antes + delta_total,
        "n_linhas_esperado": len(novas_linhas),
        "linhas_preservadas": linhas_preservadas,
        "remocoes_ordenadas": remocoes_ordenadas,
    }
    return "\n".join(novas_linhas), invariantes


def _provar_invariantes(novo_texto, invariantes):
    """(ok, motivo_ou_None) -- SEMPRE roda ANTES de qualquer escrita em
    disco. Prova, em ordem: (1) o arquivo resultante ainda tem tabela
    ID+Status; (2) numero de linhas bate com o esperado; (3) toda linha
    preservada (não tocada por este --fix) sobrevive BYTE-A-BYTE no
    resultado, no índice ajustado pelas remoções; (4) contagem de itens
    bate com a esperada, calculada ANTES de escrever (ADR-0001 c: "a
    contagem nova é explicitada ANTES de aplicar, não depois" para fixes
    de remoção -- aqui vale igual para o caso combinado)."""
    novo_table = L.parse_table(novo_texto)
    if novo_table is None:
        return False, "o arquivo resultante não tem mais nenhuma tabela ID+Status"

    esperado_linhas = invariantes["n_linhas_esperado"]
    if len(novo_table["lines"]) != esperado_linhas:
        return False, (
            f"número de linhas do resultado ({len(novo_table['lines'])}) "
            f"diverge do esperado ({esperado_linhas})")

    remocoes_ordenadas = invariantes["remocoes_ordenadas"]
    for i_original, texto_original in invariantes["linhas_preservadas"].items():
        deslocamento = sum(1 for r in remocoes_ordenadas if r < i_original)
        i_novo = i_original - deslocamento
        if (i_novo >= len(novo_table["lines"])
                or novo_table["lines"][i_novo] != texto_original):
            return False, (
                f"linha originalmente na posição {i_original + 1} não "
                "sobrevive byte-a-byte no arquivo resultante -- round-trip "
                "quebrado fora do que este --fix deveria tocar")

    esperado_itens = invariantes["n_items_esperado"]
    if len(novo_table["items"]) != esperado_itens:
        return False, (
            f"número de itens do resultado ({len(novo_table['items'])}) "
            f"diverge do esperado ({esperado_itens})")

    return True, None


def _ler_de_volta(tmp_path):
    """Isolada em função própria (não inline) para que a suíte consiga
    exercitar de propósito o caminho em que a releitura DIVERGE do que foi
    escrito -- em disco saudável isso nunca diverge de verdade, então sem
    este ponto de mock o teste de mutação não teria como matar um mutante
    que enfraquecesse esta comparação (achado real de mutation testing
    desta fatia, ver relatório)."""
    with open(tmp_path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _escrever_atomico(todo_path, novo_texto):
    """Escrita ATÔMICA (D-11/ADR-0001 e.3, mandato do team-lead): arquivo
    temporário no MESMO diretório (mesmo filesystem -- `os.replace` atômico
    de verdade) + fsync + releitura byte-a-byte ANTES do swap. Se qualquer
    passo falhar, o arquivo temporário é removido e o TODO.md real NUNCA é
    tocado -- (ok, motivo_ou_None)."""
    d = os.path.dirname(os.path.abspath(todo_path)) or "."
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".todo_fix.", suffix=".tmp",
                                        dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(novo_texto)
            fh.flush()
            os.fsync(fh.fileno())
        lido = _ler_de_volta(tmp_path)
        if lido != novo_texto:
            return False, (
                "conteúdo lido de volta do arquivo temporário diverge do "
                "que foi escrito -- abortado antes de trocar o arquivo real")
        os.replace(tmp_path, todo_path)
        tmp_path = None  # substituído com sucesso -- nada mais a limpar
    except OSError as exc:
        return False, f"falha de I/O ({type(exc).__name__}: {exc})"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return True, None


def _provar_e_escrever(todo_path, novo_texto, invariantes):
    ok, motivo = _provar_invariantes(novo_texto, invariantes)
    if not ok:
        return False, motivo
    return _escrever_atomico(todo_path, novo_texto)


# ------------------------------- relatório -----------------------------------

def _render_plan(plan, aplicados=None):
    aplicados = aplicados or []
    aplicados_ids = {(it.fix_ref, it.line_no) for it in aplicados}
    lines = ["=== tab_pendencias --fix ===",
             f"TODO.md: {plan.todo_path if plan.todo_path else '(não encontrado)'}",
             ""]
    if not plan.items:
        lines.append("Nada a corrigir (nenhum achado [auto-fixável] pendente).")
    else:
        for it in plan.items:
            if (it.fix_ref, it.line_no) in aplicados_ids:
                tag = "[APLICADO]"
            elif it.aplicavel:
                tag = "[proposto]"
            else:
                tag = "[NÃO APLICÁVEL -- recusado pelo motor de fix]"
            lines.append(f"- {it.check_id} ({it.fix_ref}) {tag}: {it.description}")
            if it.diff:
                for dl in it.diff.splitlines():
                    lines.append(f"    {dl}")
            if it.motivo_recusa:
                lines.append(f"    motivo da recusa: {it.motivo_recusa}")
            sinal = "+" if it.delta_itens >= 0 else ""
            lines.append(
                f"    impacto esperado na contagem de itens: "
                f"{sinal}{it.delta_itens}")
            lines.append("")
    if plan.notices:
        lines.append("Avisos do motor (no silent caps):")
        for n in plan.notices:
            lines.append(f"  - {n}")
        lines.append("")
    if aplicados:
        lines.append(
            f"{len(aplicados)} correção(ões) aplicada(s) e escrita(s) no "
            "TODO.md.")
    elif plan.items:
        lines.append(
            "Nada foi escrito (dry-run). Rode com --apply <classe...> para "
            "aplicar (ou --apply all para todas as classes detectadas "
            "nesta execução).")
    return "\n".join(lines) + "\n"


# --------------------------------- núcleo -------------------------------------

def run_fix(root, todo_path=None, apply_classes=None):
    """Núcleo testável, sem argparse/sys.exit. `apply_classes=None` (default)
    é SEMPRE dry-run -- nunca escreve. Retorna `FixResult`."""
    todo_path = todo_path or L.find_todo(root)
    if not todo_path:
        return FixResult(
            rc=0, applied=False, plan=FixPlan(todo_path=None),
            report_text="Sem TODO.md na raiz; nada a corrigir.")

    try:
        text, table = _ler_e_parsear(todo_path)
    except FixError as exc:
        return FixResult(rc=1, applied=False, plan=None, report_text=str(exc))

    if not table:
        plan = FixPlan(todo_path=todo_path, items=[], notices=[
            "Nenhuma tabela ID+Status reconhecida no arquivo; nada a "
            "corrigir."])
        return FixResult(rc=0, applied=False, plan=plan,
                         report_text=_render_plan(plan))

    items, notices = _itens_do_plano(root, todo_path, text, table)
    plan = FixPlan(todo_path=todo_path, items=items, notices=notices)

    if not items:
        return FixResult(rc=0, applied=False, plan=plan,
                         report_text=_render_plan(plan))

    if not apply_classes:
        return FixResult(rc=2, applied=False, plan=plan,
                         report_text=_render_plan(plan))

    accepted_all = "all" in apply_classes
    accepted = set(apply_classes)
    selecionados = [it for it in items
                    if it.aplicavel and (accepted_all or it.fix_ref in accepted)]

    if not selecionados:
        texto = _render_plan(plan) + (
            "\nNenhum item aplicável corresponde às classes pedidas em "
            "--apply; nada foi escrito.\n")
        return FixResult(rc=2, applied=False, plan=plan, report_text=texto)

    sujo, motivo = _working_tree_status(root, todo_path)
    if sujo:
        texto = (
            "Abortado ANTES de qualquer escrita: working tree do TODO.md "
            f"não está limpa -- {motivo}\n--fix nunca mistura com edição em "
            "voo de outra sessão/agente; commite ou descarte as mudanças "
            "antes de rodar --apply.")
        return FixResult(rc=1, applied=False, plan=plan, report_text=texto)

    try:
        novo_texto, invariantes = _montar_novo_texto(table, selecionados)
    except FixError as exc:
        return FixResult(rc=1, applied=False, plan=plan,
                         report_text=f"Falha ao montar a correção: {exc}")

    ok, motivo_falha = _provar_e_escrever(todo_path, novo_texto, invariantes)
    if not ok:
        texto = (
            "Abortado ANTES de escrever (prova de round-trip/contagem "
            f"falhou): {motivo_falha}. O TODO.md NÃO foi tocado.")
        return FixResult(rc=1, applied=False, plan=plan, report_text=texto)

    texto = _render_plan(plan, aplicados=selecionados)
    return FixResult(rc=2, applied=True, plan=plan, report_text=texto)


# --------------------------------- CLI (D-6) ----------------------------------

class _Parser(argparse.ArgumentParser):
    """Contrato de exit code (D-6/CLI-1): erro de parsing sai 1, nunca 2 --
    2 é reservado a 'há correção disponível'."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _fix_ref_choices():
    return sorted(_CONHECIDOS) + ["all"]


def _build_parser():
    p = _Parser(
        prog="todo_fix.py",
        description=(
            "Motor do --fix (FIX-ENG, ADR-0001 seção c): aplica APENAS "
            "correção mecânica e byte-preserving marcada [auto-fixável] "
            "pelos checks do --audit (hoje: escapar pipe cru de CHK-02, "
            "remover fragmento/duplicata de CHK-01). NUNCA muda Status, "
            "nunca reordena, nunca toca branch/commit do repositório."),
        epilog=(
            "Exit codes: 0 = execução ok, nada a corrigir; 1 = erro de "
            "execução (não é repositório git, TODO.md ilegível, working "
            "tree suja ao aplicar, falha de escrita); 2 = execução ok, há "
            "1+ correção disponível (mostrada em dry-run OU aplicada)."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--apply", nargs="+", metavar="CLASSE", default=None,
        choices=_fix_ref_choices(),
        help=(
            "Aplica as classes de fix informadas (fix_ref: "
            f"{', '.join(_CONHECIDOS)}), ou 'all' para todas as detectadas "
            "nesta execução. Default (sem --apply): dry-run, só mostra o "
            "plano, nunca escreve."))
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Acrescenta traceback completo em stderr se algo inesperado "
             "falhar (default: só tipo + mensagem da exceção).")
    return p


def main(argv):
    args = _build_parser().parse_args(argv)
    root = L.repo_root()
    if not root:
        print("Não é um repositório git.")
        return 1
    try:
        result = run_fix(root, apply_classes=args.apply)
    except Exception as exc:  # noqa: BLE001 -- última rede de segurança: erro
        # não previsto vira mensagem clara + exit 1, nunca traceback cru
        # (D-6/CLI-1), consistente com o resto do toolkit.
        print(f"Falha inesperada no --fix ({type(exc).__name__}): {exc}",
              file=sys.stderr)
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return 1
    print(result.report_text)
    return result.rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
