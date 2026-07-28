#!/usr/bin/env python3
# tools/ci/guard_stdlib_imports.py -- guard "so stdlib" do CI (CI-1)
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
tools/ci/guard_stdlib_imports.py

Guard de CI (item CI-1 do TODO.md): falha se qualquer modulo Python sob
`tools/` importar algo fora da biblioteca padrao. E o substituto, por decisao
do Chief of Staff (ver TODO.md, notas de montagem), dos itens de scanning de
dependencia/CVE -- o runtime deste projeto e stdlib pura por desenho, e este
guard e a prova mecanica disso em CI, nao uma frase de doc.

Metodo: `ast` (nao grep/regex fragil -- ver TESTES.md e a armadilha #1 da
secao 8 do prompt_inicial.md: parsing ingenuo quebra onde o parser real nao
quebra). Cada arquivo .py sob a raiz varrida e parseado; toda instrucao
`import X` / `from X import Y` (em qualquer profundidade de bloco, nao so
top-level) tem o primeiro componente do modulo (`X.Y.Z` -> `X`) comparado
contra `sys.stdlib_module_names` (Python 3.10+). Import relativo
(`from . import foo`, `from .foo import bar`) e sempre permitido -- e
intra-pacote por definicao. Import absoluto que resolve para outro arquivo
irmao dentro da MESMA raiz varrida (ex.: `import todo_lib` dentro de
`todo_sync.py`, layout flat sem pacote) tambem e permitido.

Limitacao declarada (regra "no silent caps"): isto e analise ESTATICA. Import
dinamico via `importlib.import_module("nome_construido_em_runtime")` nao e
detectado -- nenhum modulo deste projeto faz isso hoje (verificavel por
grep de `importlib` no proprio guard, que roda antes deste check).

Uso:
    python3 tools/ci/guard_stdlib_imports.py [RAIZ ...]

RAIZ default: `tools`. Exit 0 = limpo; Exit 1 = pelo menos uma importacao
fora da stdlib (ou erro de sintaxe ao parsear um arquivo).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

STDLIB = set(sys.stdlib_module_names)


def _iter_py_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _local_module_names(root: Path) -> set[str]:
    """Nomes (sem .py) de todo arquivo .py sob `root`, para permitir import
    absoluto flat entre irmaos (ex.: todo_sync.py fazendo `import todo_lib`).
    """
    return {p.stem for p in _iter_py_files(root)}


def check_file(path: Path, local_modules: set[str]) -> list[str]:
    """Retorna lista de mensagens de violacao (vazia se limpo)."""
    violations: list[str] = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: erro de sintaxe ao parsear -- {exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in STDLIB or top in local_modules:
                    continue
                violations.append(
                    f"{path}:{node.lineno}: import fora da stdlib -- '{alias.name}'"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # import relativo (from . import X / from .X import Y):
                # sempre intra-pacote, permitido por definicao.
                continue
            if node.module is None:
                continue
            top = node.module.split(".")[0]
            if top in STDLIB or top in local_modules:
                continue
            violations.append(
                f"{path}:{node.lineno}: import fora da stdlib -- 'from {node.module} import ...'"
            )
    return violations


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path("tools")]
    all_violations: list[str] = []
    files_checked = 0

    for root in roots:
        if not root.is_dir():
            print(f"ERRO: raiz '{root}' nao existe ou nao e diretorio.", file=sys.stderr)
            return 1
        local_modules = _local_module_names(root)
        for path in _iter_py_files(root):
            files_checked += 1
            all_violations.extend(check_file(path, local_modules))

    if all_violations:
        print(f"guard_stdlib_imports: {len(all_violations)} violacao(oes) em "
              f"{files_checked} arquivo(s) verificado(s):\n")
        for v in all_violations:
            print(f"  {v}")
        print(
            "\nO nucleo deste projeto e stdlib pura por desenho (TODO.md, "
            "notas de montagem: substitui scanning de dependencia/CVE). Se "
            "a importacao acima e intencional, ela quebra esse invariante -- "
            "decisao para o lider, nao para o CI relaxar sozinho."
        )
        return 1

    print(f"guard_stdlib_imports: OK -- {files_checked} arquivo(s) verificado(s), "
          f"0 import fora da stdlib.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
