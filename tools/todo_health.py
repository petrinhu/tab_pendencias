#!/usr/bin/env python3
# tools/todo_health.py -- relatorio de saude/frescor da TODO.md
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
tools/todo_health.py

--health: relatorio LOCAL de saude da TODO.md (offline, sem LLM, sem rede).
Da o dado para "medir antes de escalar":
  - itens presos em 🔍 Pendente verificação (falso-done residual: entregue mas a
    onda TST-*/AUD-* nunca rodou)
  - tamanho da INBOX (descobertas nao priorizadas)
  - adesao a citar ID nos commits (do $GIT_DIR/todo-freshness.log)

Uso: python3 todo_health.py

ENC-1: falha de leitura do TODO.md (encoding invalido, permissao, etc.) vira
mensagem CLARA em stderr + exit 1 (erro de execucao, D-6/CLI-1) -- nunca
traceback cru. --verbose acrescenta o traceback completo.
"""
import argparse
import os
import sys
import traceback

import todo_lib as L

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class _Parser(argparse.ArgumentParser):
    """Contrato de exit code (D-6/CLI-1): erro de parsing sai 1 ('erro de
    execucao'), NAO 2 (reservado a 'ha item(ns) preso(s) em verificacao')."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser():
    p = _Parser(
        prog="todo_health.py",
        description=(
            "Relatorio local de saude/frescor da TODO.md (offline, sem LLM, "
            "sem rede): itens presos em 🔍 Pendente verificacao (falso-done "
            "residual), tamanho da INBOX, e adesao a citar ID nos commits."
        ),
        epilog=(
            "Exit codes: 0 = ok, nenhum item preso em verificacao; 1 = erro "
            "de execucao (nao e repositorio git); 2 = ha item(ns) preso(s) "
            "em 🔍 Pendente verificacao."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Se a leitura do TODO.md falhar, acrescenta o traceback "
             "completo em stderr (default: so tipo + mensagem da excecao).")
    return p


def _adesao(root):
    gd = L.git_dir(root)
    if not gd:
        return None
    p = os.path.join(gd, "todo-freshness.log")
    try:
        with open(p, encoding="utf-8") as fh:
            linhas = fh.read().splitlines()
    except Exception:
        return None
    code = [l for l in linhas if "code=1" in l]
    if not code:
        return None
    citaram = [l for l in code if "cited=0" not in l]
    pct = round(100 * len(citaram) / len(code))
    return f"{len(citaram)}/{len(code)} commits de codigo citaram ID ({pct}%)"


# ENC-1: sentinela DISTINTO de None -- `run()` ja devolve None para dois
# estados VALIDOS ("nao e repo git", "sem TODO.md"/"sem tabela": nada a
# reportar, main() os desambigua via L.repo_root()). Uma leitura que FALHOU
# (erro de execucao, D-6) nao pode reusar esse mesmo None generico: main()
# precisaria adivinhar a causa, e um falso "sem TODO.md" sairia exit 0
# quando deveria ser 1. `is ERRO_LEITURA` (identidade de objeto, nunca
# confundido com um dict de sucesso nem com None) resolve isso sem mudar o
# contrato dos dois `None` ja existentes.
ERRO_LEITURA = object()


def run(root=None, verbose=False):
    """Nucleo testavel. Retorna um dict com as metricas, None (estado valido
    sem dado: nao e repo git / sem TODO.md / sem tabela) ou ERRO_LEITURA
    (leitura do TODO.md falhou -- erro de execucao, D-6/ENC-1)."""
    root = root or L.repo_root()
    if not root:
        print("Nao e um repositorio git.")
        return None
    todo = L.find_todo(root)
    if not todo:
        print("Sem TODO.md na raiz.")
        return None
    try:
        with open(todo, encoding="utf-8") as fh:
            text = fh.read()
    except Exception as exc:
        print(f"Falha ao ler TODO.md ({type(exc).__name__}): {exc}",
              file=sys.stderr)
        if verbose:
            traceback.print_exc(file=sys.stderr)
        return ERRO_LEITURA
    tbl = L.parse_table(text)
    if not tbl:
        print("Sem tabela no TODO.md.")
        return None

    items = tbl["items"]
    pend = [it for it in items if L.is_pending(it["status"])]
    verif = [it for it in items if L.is_awaiting_verification(it["status"])]
    done = [it for it in items if L.is_done(it["status"])]
    inbox = L.inbox_items(text)

    print(f"Saude da TODO.md ({len(items)} itens):")
    print(f"  ✅ concluidos: {len(done)}")
    print(f"  ⏳/🔄 pendentes (nao entregues): {len(pend)}")
    print(f"  🔍 aguardando verificacao (entregue, falta teste/auditoria): "
          f"{len(verif)}")
    for it in verif[:10]:
        print(f"       presos em 🔍 -> {it['id']}")
    if len(verif) > 10:
        print(f"       ... (+{len(verif) - 10})")
    print(f"  INBOX (descobertas nao priorizadas): {len(inbox)}")
    ad = _adesao(root)
    print(f"  adesao a citar ID: {ad}" if ad
          else "  adesao a citar ID: (sem dados ainda no todo-freshness.log)")
    if pend:
        print("Dica: rode todo_sync.py para sincronizar status entregue->🔍 "
              "(determinístico); /tab_pendencias --reorder para re-priorizar.")
    return {"itens": len(items), "concluidos": len(done), "pendentes": len(pend),
            "aguardando_verificacao": len(verif), "inbox": len(inbox)}


def main(argv):
    """CLI (D-6/CLI-1). run() devolve dict (sucesso), None (estado valido
    sem dado) ou ERRO_LEITURA (ENC-1: leitura falhou); aqui e decidido o
    exit code visivel: 'nao e repo git' e falha de leitura sao erro de
    execucao (1), mas 'sem TODO.md'/'sem tabela' e estado valido (0, nada a
    reportar) -- consistente com todo_sync.py, que ja faz essa mesma
    distincao. Chama L.repo_root() de novo (2o subprocess git) so para
    desambiguar a causa da falha sem mudar a assinatura/contrato ja
    existente de run()."""
    args = _build_parser().parse_args(argv)
    res = run(verbose=args.verbose)
    if res is ERRO_LEITURA:
        return 1
    if res is not None:
        return 2 if res["aguardando_verificacao"] > 0 else 0
    return 1 if L.repo_root() is None else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
