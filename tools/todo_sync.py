#!/usr/bin/env python3
# tools/todo_sync.py -- sync mecanico e deterministico da TODO.md
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
tools/todo_sync.py

--sync DETERMINISTICO da TODO.md (offline, sem LLM, sem rede). A "metade barata"
do frescor, executavel: le os commits desde o ultimo sync, acha os IDs citados,
e para cada item ainda ⏳/🔄 propoe avancar para 🔍 Pendente verificação.
NUNCA seta ✅ (so apos a onda de teste/auditoria) e NUNCA reordena (julgamento).

Evidencia de ENTREGA = commit que citou o ID **e** tocou trabalho substantivo
(L.touched_code). Commit que so mexe na TODO.md/inbox cita o ID sem ter
entregado nada -- criar item, reordenar, aprovar escopo -- e nao conta.

Uso:
  python3 todo_sync.py            # propoe (mostra o que faria; nao escreve)
  python3 todo_sync.py --apply    # aplica no TODO.md e grava o ref de sync
  python3 todo_sync.py --since <ref>   # janela explicita (ex: uma tag/commit)

Ref de sync incremental em $GIT_DIR/todo-sync-ref. Primeira execucao sem ref
NAO varre o historico: a linha de base passa a ser HEAD (citacao antiga de item
ainda pendente viraria flip indevido). Para ler o passado de proposito, passe
--since <ref> explicitamente. --apply e sempre explicito.

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
    # WIN-CLI-1: no Windows a codepage padrao do console e cp1252 (nao
    # UTF-8) -- sem isto, qualquer print() com emoji (⏳/🔄/🔍/✅, usados na
    # descricao/epilog do --help e nas mensagens de execucao abaixo) crasha
    # com UnicodeEncodeError e o processo sai com traceback cru em vez do
    # contrato de exit code (D-6/CLI-1). Mesmo guard ja usado em
    # todo_health.py (stdout) e todo_freshness.py (stderr); aqui e stdout
    # porque e onde este script imprime emoji.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NEW_STATUS = "🔍 Pendente verificação"


class _Parser(argparse.ArgumentParser):
    """Contrato de exit code (D-6/CLI-1): erro de parsing (flag desconhecida,
    valor faltando) sai 1 ('erro de execucao'), NAO 2 -- o 2 e reservado ao
    resultado do sync (ha item(ns) elegivel(is)), senao um typo de flag e uma
    sincronizacao bem-sucedida ficariam indistinguiveis para o CI."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser():
    p = _Parser(
        prog="todo_sync.py",
        description=(
            "Sync mecanico e deterministico da TODO.md (offline, sem LLM, "
            "sem rede): le os commits desde o ultimo sync, acha os IDs "
            "citados e propoe avancar itens ⏳ Pendente/🔄 Em andamento para "
            "🔍 Pendente verificacao. NUNCA seta ✅ e NUNCA reordena."
        ),
        epilog=(
            "Exit codes: 0 = ok, nada a sincronizar; 1 = erro de execucao "
            "(nao e repositorio git); 2 = ha item(ns) elegivel(is), "
            "proposto(s) ou aplicado(s)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--apply", action="store_true",
        help="Aplica no TODO.md e grava o ref de sync incremental "
             "(default: so mostra o que faria, nao escreve).")
    p.add_argument(
        "--since", metavar="REF",
        help="Janela explicita de commits (ex.: uma tag ou commit); ignora "
             "o ref incremental salvo e varre o passado de proposito.")
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Se a leitura do TODO.md falhar, acrescenta o traceback "
             "completo em stderr (default: so tipo + mensagem da excecao).")
    return p


def _ref_path(root):
    gd = L.git_dir(root)
    return os.path.join(gd, "todo-sync-ref") if gd else None


def _last_sync_ref(root):
    p = _ref_path(root)
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except Exception:
        return None


def _save_sync_ref(root):
    p = _ref_path(root)
    head = L.git(["rev-parse", "HEAD"], cwd=root).strip()
    if not p or not head:
        return
    try:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(head)
    except Exception:
        pass


def _parse_log(raw):
    """[(mensagem, [arquivos])] do formato '%x1e%B%x1f' + --name-only."""
    out = []
    for rec in raw.split("\x1e"):
        if not rec.strip():
            continue
        msg, _, files = rec.partition("\x1f")
        out.append((msg.strip("\n"),
                    [f for f in files.split("\n") if f.strip()]))
    return out


def _resolves(root, ref):
    """A ref existe neste clone? (rev-parse --verify, nao 'saida vazia')."""
    return bool(L.git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                      cwd=root).strip())


def _commits_since(root, since):
    """[(mensagem, [arquivos])] dos commits no range (since..HEAD).

    --name-only vem vazio em commit de merge (sem diff por padrao), logo merge
    nao conta como entrega -- conservador de proposito: merge nao entrega, o
    commit de baixo dele entrega.

    A ref e validada por rev-parse ANTES de rodar o log: range vazio (nada novo
    desde o ultimo sync, o caso comum) e ref inexistente (clone raso) produzem
    os dois saida vazia, e inferir pela saida fazia o caso comum cair no
    fallback e varrer o historico inteiro."""
    if since and not _resolves(root, since):
        print(f"[todo-sync] ref '{since}' invalida ou nao alcancavel (clone "
              "raso?); varrendo todo o historico.", file=sys.stderr)
        since = None
    rng = f"{since}..HEAD" if since else "HEAD"
    raw = L.git(["log", rng, "--format=%x1e%B%x1f", "--name-only"], cwd=root)
    return _parse_log(raw)


def run(argv, root=None):
    """Nucleo testavel. Retorna (rc, to_flip, applied)."""
    apply = "--apply" in argv
    verbose = "--verbose" in argv or "-v" in argv
    since = None
    if "--since" in argv:
        try:
            since = argv[argv.index("--since") + 1]
        except IndexError:
            since = None
    root = root or L.repo_root()
    if not root:
        print("Nao e um repositorio git.")
        return 1, [], False
    todo = L.find_todo(root)
    if not todo:
        print("Sem TODO.md na raiz; nada a sincronizar.")
        return 0, [], False
    try:
        with open(todo, encoding="utf-8", newline="") as fh:  # preserva CRLF/LF
            text = fh.read()
    except Exception as exc:
        # ENC-1: erro de execucao (D-6/CLI-1) -- mensagem clara em stderr,
        # nunca o traceback cru do Python. --verbose acrescenta o traceback.
        print(f"Falha ao ler TODO.md ({type(exc).__name__}): {exc}",
              file=sys.stderr)
        if verbose:
            traceback.print_exc(file=sys.stderr)
        return 1, [], False
    tbl = L.parse_table(text)
    if not tbl or not tbl["items"]:
        print("Sem tabela de itens no TODO.md.")
        return 0, [], False

    by_id = {it["id"]: it for it in tbl["items"]}
    ids = list(by_id.keys())
    first_run = False
    if since is None:
        since = _last_sync_ref(root)
        first_run = since is None

    cited = set()
    if first_run:
        # Sem ref, varrer o historico inteiro ressuscita citacao antiga de item
        # AINDA pendente -- e commit de bookkeeping (criar item, reordenar,
        # aprovar escopo) cita o ID sem ter entregado nada. A linha de base
        # passa a ser HEAD; para ler o passado de proposito, --since <ref>.
        print("[todo-sync] 1a execucao neste repo (sem ref de sync): linha de "
              "base = HEAD, o historico NAO e varrido. Rode --apply para "
              "gravar a base; para varrer o passado, use --since <ref>.")
    else:
        for msg, files in _commits_since(root, since):
            if not L.touched_code(files):      # so mexeu na tabela/INBOX
                continue                       # citou, mas nao entregou
            for i in L.cited_ids(msg, ids):
                cited.add(i)
    to_flip = [i for i in cited if L.is_flip_eligible(by_id[i]["status"])]

    if not to_flip:
        print("Nada a sincronizar: nenhum item citado esta ⏳/🔄.")
        if apply:
            _save_sync_ref(root)
        return 0, [], False

    head = "Aplicando" if apply else "Proposto (rode com --apply para escrever)"
    print(f"{head}: {len(to_flip)} item(ns) -> {NEW_STATUS}")
    lines = tbl["lines"]
    for i in sorted(to_flip):
        it = by_id[i]
        print(f"  {i}: '{it['status']}'  ->  '{NEW_STATUS}'")
        if apply:
            lines[it["line_no"]] = L.set_status_cell(
                lines[it["line_no"]], tbl["status_idx"], NEW_STATUS)

    if apply:
        out = "\n".join(lines)            # split("\n")+join = round-trip exato
        with open(todo, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        _save_sync_ref(root)
        print("TODO.md atualizado. ✅ nunca e setado aqui; reordenar continua "
              "sendo /tab_pendencias --reorder (julgamento).")
    return 0, to_flip, apply


def main(argv):
    """CLI (D-6/CLI-1): argparse so valida flags/--help; run() mantem o
    parsing proprio (usado tambem pelos testes que chamam run() direto).
    O exit code de 'achados' (2) e decidido aqui, sem mudar o contrato
    interno de run() (rc 0/1), que outros testes/consumidores ja dependem."""
    _build_parser().parse_args(argv)
    rc, to_flip, _ = run(argv)
    if rc != 0:
        return rc
    return 2 if to_flip else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
