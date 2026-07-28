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
"""
import os
import sys

import todo_lib as L

NEW_STATUS = "🔍 Pendente verificação"


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
    with open(todo, encoding="utf-8", newline="") as fh:  # preserva CRLF/LF
        text = fh.read()
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
    rc, _, _ = run(argv)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
