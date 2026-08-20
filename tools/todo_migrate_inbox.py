#!/usr/bin/env python3
# tools/todo_migrate_inbox.py -- migra TODO.md legado (INBOX depois da
# tabela) para a ordem canonica (INBOX antes, tabela por ultimo) -- LAYOUT-1
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
tools/todo_migrate_inbox.py

Converte um ``TODO.md`` do formato LEGADO (secao ``## INBOX`` DEPOIS da
tabela, ou qualquer texto depois do fim da tabela) para a **ordem canonica**
do contrato (LAYOUT-1, ``references/frescor-da-tabela.md`` SS5):

    1. linha 1: titulo H1
    2. preambulo livre (prosa, blockquote, legendas, notas)
    3. ``## INBOX (...)`` -- exception queue
    4. (opcional) mais prosa/secoes livres
    5. A TABELA canonica
    6. EOF logo apos a ultima linha da tabela

**So a ORDEM dos blocos muda.** O conteudo da tabela e o da INBOX sao
movidos LINHA A LINHA, byte a byte: nenhuma celula, nenhum bullet, nenhum
espaco interno e reescrito. A unica coisa que o motor produz do zero sao as
linhas EM BRANCO de costura entre os blocos (e a preservacao do terminador
CRLF/LF e do BOM originais).

Idempotente: rodar de novo num arquivo ja canonico nao muda um byte.

**Recusa em vez de adivinhar (UNIQ-1):** com 2+ BLOCOS de tabela no arquivo
(qualquer tabela, com ou sem coluna ``Status`` -- o contrato exige UMA, sem
qualificacao), nao ha como saber qual e a canonica: este utilitario acusa e
sai com erro, sem tocar em nada. Antes ele elegia sempre a 1a tabela do
arquivo, e numa medicao real isso significou tratar uma tabela de 3 itens como
canonica no lugar de uma de 339.

Prova antes de escrever (mesma politica de ``todo_fix.py``): o texto novo e
reparseado e comparado com o original -- multiset de linhas identico, IDs e
status dos itens identicos e na mesma ordem, entradas da INBOX identicas e
na mesma ordem. Qualquer divergencia ABORTA sem tocar o arquivo real.
Escrita atomica (tmp no mesmo diretorio + fsync + releitura + os.replace).

Cross-platform: so stdlib, ``encoding``/``newline`` sempre explicitos,
``os.path.join``, nada de permissao POSIX nem de shell.

Uso:
  python3 tools/todo_migrate_inbox.py                 # dry-run no TODO.md do repo
  python3 tools/todo_migrate_inbox.py --check         # so diagnostica
  python3 tools/todo_migrate_inbox.py --apply         # converte
  python3 tools/todo_migrate_inbox.py CAMINHO/TODO.md --apply

Exit codes (D-6, os mesmos 3 do resto do toolkit): 0 = execucao ok e nada a
migrar (ou ``--apply`` concluido); 1 = erro de execucao (arquivo ilegivel,
sem tabela canonica, estrutura ambigua, falha de escrita); 2 = execucao ok e
HA migracao pendente (``--check``/dry-run).
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import todo_lib as L  # noqa: E402


# ---------------------------------------------------------------------------
# nucleo (puro, testavel sem disco)
# ---------------------------------------------------------------------------

class MigrationError(Exception):
    """Migracao recusada -- o arquivo NAO e tocado."""


def _split_trailing_newline(text: str) -> tuple[list[str], bool]:
    """(linhas_de_conteudo, terminava_com_\\n).

    ``"a\\nb\\n".split("\\n")`` devolve ``["a", "b", ""]``; esse "" final e
    artefato do terminador, nao uma linha. Separar aqui e o que deixa o
    round-trip byte-exato (junta com "\\n" e recoloca o terminador)."""
    ends = text.endswith("\n")
    lines = text.split("\n")
    if ends:
        lines = lines[:-1]
    return lines, ends


def _blank_line(lines: list[str]) -> str:
    """Linha em branco no terminador do arquivo: "\\r" quando o arquivo usa
    CRLF (as linhas ficam com "\\r" sobrando apos o split em "\\n"), "" em
    LF puro."""
    return "\r" if any(ln.endswith("\r") for ln in lines) else ""


def _trim_trailing_blanks(block: list[str]) -> list[str]:
    out = list(block)
    while out and out[-1].strip() == "":
        out.pop()
    return out


def plan(text: str) -> dict:
    """Diagnostico sem escrever nada. Devolve dict:

      order/legacy/canonical/inbox_line/table_span/trailing  (de
                    ``todo_lib.layout``)
      table_blocks     quantos BLOCOS de tabela markdown o arquivo tem
      work_tables      quantos desses blocos tem coluna Status (informativo)
      ambiguous        True quando ha 2+ blocos de tabela: a migracao e
                       RECUSADA (nao ha como saber qual e a canonica)
      needs_migration  True quando ha o que reordenar
      reason           frase curta do porque (ou None)
    """
    table = L.parse_table(text)
    lay = L.layout(text, table=table)
    lay = dict(lay)
    lay["ambiguous"] = False
    # UNIQ-1: com 2+ tabelas DE TRABALHO, QUAL delas e a canonica e uma decisao
    # que este utilitario NAO tem como tomar -- e adivinhar custa caro: numa
    # medicao real ele elegeu uma tabela de 3 itens no lugar de uma de 339 (a
    # eleita e sempre a 1a do arquivo, que nao tem nenhuma razao de ser a
    # certa). Recusar e acusar, sempre; escolher, nunca. Vem ANTES do teste de
    # LAYOUT_NO_TABLE porque com varias tabelas de trabalho o diagnostico util
    # e a ambiguidade, mesmo quando nenhuma delas e eleita pelo nucleo.
    blocos = L.table_blocks(text)
    lay["table_blocks"] = len(blocos)
    lay["work_tables"] = len(L.work_tables(text))
    if len(blocos) > 1:
        onde = ", ".join(f"linha {b['start'] + 1}" for b in blocos[:10])
        if len(blocos) > 10:
            onde += f", ... (+{len(blocos) - 10}; a contagem acima e completa)"
        lay["needs_migration"] = False
        lay["ambiguous"] = True
        lay["reason"] = (
            f"ha {len(blocos)} blocos de tabela no arquivo (comecando em "
            f"{onde}). O contrato exige UMA tabela, sem qualificacao "
            "(references/frescor-da-tabela.md SS5), e este utilitario NAO "
            "escolhe qual e a canonica: resolva antes (consolide numa tabela "
            "so; legenda/sumario/scoring viram bullets; linha em branco ou "
            "heading dentro da tabela tambem cria bloco novo) e rode de "
            "novo. Rode `python3 tools/todo_audit.py` (CHK-19/CHK-20) para "
            "ver tudo de uma vez")
        return lay
    if lay["order"] == L.LAYOUT_NO_TABLE:
        lay["needs_migration"] = False
        lay["reason"] = ("sem tabela canonica (nenhum cabecalho com colunas "
                         "ID e Status) -- nada a migrar")
        return lay
    if lay["canonical"]:
        lay["needs_migration"] = False
        lay["reason"] = None
        return lay
    lay["needs_migration"] = True
    if lay["legacy"]:
        lay["reason"] = (f"secao INBOX na linha {lay['inbox_line'] + 1}, "
                         f"DEPOIS da tabela (linhas "
                         f"{lay['table_span'][0] + 1}-"
                         f"{lay['table_span'][1] + 1})")
    else:
        n, _txt = lay["trailing"][0]
        lay["reason"] = (f"texto depois do fim da tabela a partir da linha "
                         f"{n + 1}")
    return lay


def migrate_text(text: str) -> tuple[str, bool]:
    """(texto_novo, mudou). Levanta ``MigrationError`` quando a conversao
    nao pode ser feita com seguranca -- nunca devolve um texto adivinhado.

    Algoritmo (deliberadamente burro, para nao ter como corromper dado):
      1. recorta o bloco da TABELA (span de ``todo_lib.table_span``) e o
         bloco da INBOX (``todo_lib.inbox_region``) como LISTAS DE LINHAS,
         sem tocar em nenhuma delas;
      2. o resto do arquivo (`outros`), na ORDEM ORIGINAL, vira o preambulo;
      3. remonta: outros + INBOX + TABELA + EOF.
    """
    lay = plan(text)
    if lay.get("ambiguous"):
        raise MigrationError(lay["reason"])
    if lay["order"] == L.LAYOUT_NO_TABLE:
        raise MigrationError(
            "sem tabela canonica (nenhum cabecalho com colunas ID e Status) "
            "-- este utilitario so reordena arquivo que tem tabela")
    if not lay["needs_migration"]:
        return text, False

    bom = text.startswith(L.BOM)
    body = text[len(L.BOM):] if bom else text
    lines, ends_nl = _split_trailing_newline(body)
    t_start, t_end = lay["table_span"]
    # indices de linha sao os mesmos com ou sem BOM (o BOM nao acrescenta
    # linha nenhuma); recalcular sobre `body` mantem tudo num referencial so
    i_head, i_end = L.inbox_region(body)

    if t_end >= len(lines):
        raise MigrationError(
            "span da tabela ultrapassa o fim do arquivo -- estrutura "
            "inesperada, nada foi tocado")
    if i_head is not None and not (i_end <= t_start or i_head > t_end):
        raise MigrationError(
            "a secao INBOX e a tabela se SOBREPOEM (a INBOX comeca dentro "
            "do span da tabela ou vice-versa) -- estrutura ambigua, nada "
            "foi tocado; separe as duas a mao e rode de novo")

    tabela = lines[t_start:t_end + 1]
    inbox = lines[i_head:i_end] if i_head is not None else []
    tomados = set(range(t_start, t_end + 1))
    if i_head is not None:
        tomados |= set(range(i_head, i_end))
    # O resto do arquivo, na ORDEM ORIGINAL. Onde um bloco foi recortado
    # sobra um "buraco" que juntaria as linhas em branco dos dois lados
    # (`\n\n\n`, que o markdownlint MD012 reprova). So NESSE ponto -- e so
    # quando a linha ja emitida tambem e branca -- a linha em branco
    # excedente e descartada: nenhuma linha em branco de uma regiao INTACTA
    # e tocada, entao bloco de codigo cercado e prosa continuam byte a byte.
    outros: list[str] = []
    buraco = False
    for n, ln in enumerate(lines):
        if n in tomados:
            buraco = True
            continue
        if (buraco and ln.strip() == "" and outros
                and outros[-1].strip() == ""):
            continue
        outros.append(ln)
        buraco = False

    br = _blank_line(lines)
    novo: list[str] = _trim_trailing_blanks(outros)
    inbox = _trim_trailing_blanks(inbox)
    if inbox:
        if novo:
            novo.append(br)
        novo.extend(inbox)
    if novo:
        novo.append(br)
    novo.extend(tabela)

    novo_texto = "\n".join(novo) + ("\n" if ends_nl else "")
    if bom:
        novo_texto = L.BOM + novo_texto

    _provar(text, novo_texto)
    return novo_texto, True


def _provar(antigo: str, novo: str) -> None:
    """Invariantes provados ANTES de qualquer escrita. Qualquer falha e
    ``MigrationError`` -- "escrever sem conseguir provar e pior que nao
    escrever"."""
    a_lines, _ = _split_trailing_newline(antigo.lstrip(L.BOM))
    n_lines, _ = _split_trailing_newline(novo.lstrip(L.BOM))
    # (1) multiset de linhas nao-brancas identico: nenhuma linha de conteudo
    # criada, perdida ou reescrita -- so reordenada.
    a_cont = sorted(ln for ln in a_lines if ln.strip())
    n_cont = sorted(ln for ln in n_lines if ln.strip())
    if a_cont != n_cont:
        faltando = [ln for ln in a_cont if ln not in n_cont][:1]
        sobrando = [ln for ln in n_cont if ln not in a_cont][:1]
        raise MigrationError(
            "conteudo nao-branco divergiu na remontagem (faltando="
            f"{faltando!r} sobrando={sobrando!r}) -- nada foi escrito")
    # (2) a tabela canonica reparseia com os MESMOS itens, na mesma ordem.
    t_a, t_n = L.parse_table(antigo), L.parse_table(novo)
    if t_n is None:
        raise MigrationError("o resultado nao reparseia como tabela canonica")
    ia = [(it["id"], it["status"]) for it in t_a["items"]]
    inn = [(it["id"], it["status"]) for it in t_n["items"]]
    if ia != inn:
        raise MigrationError(
            f"itens da tabela divergiram ({len(ia)} antes, {len(inn)} depois)"
            " -- nada foi escrito")
    if t_a["ncols"] != t_n["ncols"] or t_a["id_idx"] != t_n["id_idx"] \
            or t_a["status_idx"] != t_n["status_idx"]:
        raise MigrationError(
            "o cabecalho da tabela mudou de forma na remontagem -- nada "
            "foi escrito")
    # (3) a INBOX reparseia com as MESMAS entradas, na mesma ordem.
    if L.inbox_items(antigo) != L.inbox_items(novo):
        raise MigrationError(
            "as entradas da INBOX divergiram na remontagem -- nada foi "
            "escrito")
    # (4) o resultado E canonico (senao a migracao nao seria idempotente).
    if not L.layout(novo, table=t_n)["canonical"]:
        raise MigrationError(
            "o resultado ainda nao esta na ordem canonica -- nada foi "
            "escrito")


# ---------------------------------------------------------------------------
# disco
# ---------------------------------------------------------------------------

def read_text(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _ler_de_volta(tmp_path: str) -> str:
    with open(tmp_path, encoding="utf-8", newline="") as fh:
        return fh.read()


def escrever_atomico(path: str, novo_texto: str) -> tuple[bool, str | None]:
    """tmp no MESMO diretorio + fsync + releitura byte-a-byte + os.replace.
    Falha em qualquer passo => arquivo real intocado."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".todo_migrate_inbox.",
                                        suffix=".tmp", dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(novo_texto)
            fh.flush()
            os.fsync(fh.fileno())
        if _ler_de_volta(tmp_path) != novo_texto:
            return False, ("conteudo lido de volta do temporario diverge do "
                           "que foi escrito -- abortado antes do swap")
        os.replace(tmp_path, path)
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="todo_migrate_inbox.py",
        description=("Reordena um TODO.md legado para a ordem canonica: "
                     "INBOX ANTES da tabela, tabela por ultimo, EOF logo "
                     "depois dela."))
    p.add_argument("todo", nargs="?", default=None,
                   help="caminho do TODO.md (default: o do repositorio git "
                        "atual)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true",
                   help="grava a conversao (default: so mostra)")
    g.add_argument("--check", action="store_true",
                   help="so diagnostica: exit 2 se ha migracao pendente")
    g.add_argument("--dry-run", action="store_true",
                   help="explicita o default (nao grava nada)")
    return p


def _resolver_todo(arg: str | None) -> str | None:
    if arg:
        return arg if os.path.isfile(arg) else None
    root = L.repo_root()
    return L.find_todo(root) if root else None


def main(argv) -> int:
    args = _build_parser().parse_args(argv)
    path = _resolver_todo(args.todo)
    if not path:
        print("TODO.md nao encontrado (passe o caminho ou rode dentro de um "
              "repositorio git com TODO.md na raiz).", file=sys.stderr)
        return 1
    try:
        text = read_text(path)
    except OSError as exc:
        print(f"nao consegui ler {path}: {exc}", file=sys.stderr)
        return 1

    info = plan(text)
    print(f"arquivo: {path}")
    print(f"ordem detectada: {info['order']}")
    if info["table_span"]:
        print(f"tabela: linhas {info['table_span'][0] + 1}-"
              f"{info['table_span'][1] + 1}")
    if info["inbox_line"] is not None:
        print(f"INBOX: linha {info['inbox_line'] + 1}")

    if info.get("ambiguous"):
        print(f"migracao RECUSADA: {info['reason']}.", file=sys.stderr)
        return 1
    if info["order"] == L.LAYOUT_NO_TABLE:
        print(info["reason"])
        return 1
    if not info["needs_migration"]:
        print("ja esta na ordem canonica -- nada a fazer.")
        return 0

    print(f"migracao pendente: {info['reason']}")
    if not args.apply:
        print("dry-run: nada foi escrito. Rode com --apply para converter.")
        return 2

    try:
        novo, mudou = migrate_text(text)
    except MigrationError as exc:
        print(f"migracao RECUSADA: {exc}", file=sys.stderr)
        return 1
    if not mudou:
        print("ja esta na ordem canonica -- nada a fazer.")
        return 0
    ok, motivo = escrever_atomico(path, novo)
    if not ok:
        print(f"falha ao escrever: {motivo}", file=sys.stderr)
        return 1
    print("migrado: INBOX movida para antes da tabela; arquivo termina na "
          "tabela.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
