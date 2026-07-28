#!/usr/bin/env python3
# tools/todo_freshness.py -- hook post-commit warn-only de frescor da TODO.md
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
tools/todo_freshness.py

Git hook (Camada 2 local) de frescor da TODO.md. Cross-platform (stdlib),
warn-only, nunca bloqueia. Chamado pelo shim `post-commit`. Logica compartilhada
em todo_lib.py.

Dois avisos, so quando ha lacuna acionavel (silencioso caso contrario):
1. O commit tocou codigo mas nao citou nenhum ID do TODO.md.
2. O commit cita um ID cujo Status ainda e "Pendente"/"Em andamento" (lembra:
   implementacao entregue -> "Pendente verificacao"; "Concluido" so apos a onda
   de teste/auditoria).

Registra adesao em $GIT_DIR/todo-freshness.log para medir antes de automatizar.
"""
import os
import sys
from datetime import datetime, timezone

import todo_lib as L

try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Re-export (compat de testes + clareza).
parse_todo = L.parse_status_map
is_pending = L.is_pending
cited_ids = L.cited_ids
touched_code = L.touched_code   # subiu p/ a lib: o todo_sync.py tambem usa


def build_warnings(message, files, items):
    warns = []
    cited = L.cited_ids(message, list(items.keys()))
    for i in cited:
        if L.is_pending(items[i]):
            warns.append(
                f"[todo-fresh] o commit cita {i}, mas no TODO.md o Status segue "
                f"'{items[i]}'. Se entregou, atualize o Status (implementacao -> "
                "'Pendente verificacao'; 'Concluido' so apos a onda de "
                "teste/auditoria)."
            )
    if touched_code(files) and not cited:
        exemplo = next(iter(items)) if items else "ID"
        warns.append(
            "[todo-fresh] o commit tocou codigo mas nao citou nenhum ID de item "
            f"do TODO.md. Se fecha ou avanca um item, cite o ID (ex: {exemplo}) "
            "na mensagem para rastrear o status. (refactor/exploracao pode "
            "legitimamente nao mapear; isto so avisa, nunca bloqueia.)"
        )
    return warns, cited


def _log_adesao(root, touched, n_cited, n_warns):
    gd = L.git_dir(root)
    if not gd:
        return
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(os.path.join(gd, "todo-freshness.log"), "a",
                  encoding="utf-8") as fh:
            fh.write(f"{stamp} code={int(touched)} cited={n_cited} "
                     f"warns={n_warns}\n")
    except Exception:
        pass


def main():
    root = L.repo_root()
    if not root:
        return 0
    todo = L.find_todo(root)
    if not todo:
        return 0
    try:
        with open(todo, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return 0
    items = L.parse_status_map(text)
    if not items:
        return 0
    message = L.git(["log", "-1", "--format=%B"], cwd=root)
    files = [f for f in L.git(
        ["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], cwd=root
    ).splitlines() if f]
    warns, cited = build_warnings(message, files, items)
    _log_adesao(root, touched_code(files), len(cited), len(warns))
    for w in warns:
        print(w, file=sys.stderr)
    return 0  # warn-only: NUNCA bloqueia


if __name__ == "__main__":
    sys.exit(main())
