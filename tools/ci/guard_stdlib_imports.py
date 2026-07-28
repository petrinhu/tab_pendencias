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

Distincao INTERNO x TERCEIRO (GUARD-FP): um import absoluto e "deste
projeto" quando resolve, componente a componente, para um arquivo REAL sob
a raiz varrida -- exatamente como o importador do Python resolveria a
partir do topo do `sys.path` (`tools/`, aqui): cada componente do nome
dotted precisa ser um pacote (`<parte>/__init__.py`) para descer ao
proximo, e o ULTIMO precisa ser um modulo (`<parte>.py`) ou tambem um
pacote. Isto e estrutural e verificavel por `Path.is_file()` -- nao uma
lista de nomes permitidos que envelhece a cada novo subpacote (essa
deriva ja mordeu este projeto: o guard so nao pegava `tools/checks/`
porque nunca foi exercitado contra a propria estrutura).

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


def _resolves_to_local_file(module_name: str, root: Path) -> bool:
    """`module_name` (dotted, ex.: 'checks.chk_graph') resolve para um
    arquivo REAL sob `root`, seguindo a mesma regra de resolucao de pacote
    que o importador do Python usaria a partir de `root` no `sys.path`?

    Cada componente, exceto o ultimo, precisa ser um pacote
    (`<parte>/__init__.py`) para a resolucao continuar descendo. O ultimo
    componente e valido como modulo (`<parte>.py`) OU como pacote (mesma
    regra). Isto cobre tanto o import de subpacote (`checks.chk_graph`,
    com `tools/checks/__init__.py` existindo) quanto o layout flat sem
    pacote (`import todo_lib` com `tools/todo_lib.py` irmao)."""
    current = root
    parts = module_name.split(".")
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        pkg_init = current / part / "__init__.py"
        if pkg_init.is_file():
            current = current / part
            continue
        if is_last:
            return (current / f"{part}.py").is_file()
        return False
    return True


def check_file(path: Path, root: Path) -> list[str]:
    """Retorna lista de mensagens de violacao (vazia se limpo). `root` e a
    raiz varrida (a mesma passada a `main`/`_iter_py_files`), usada para
    resolver import absoluto interno vs. dependencia de terceiro."""
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
                if top in STDLIB or _resolves_to_local_file(alias.name, root):
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
            if top in STDLIB or _resolves_to_local_file(node.module, root):
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
        for path in _iter_py_files(root):
            files_checked += 1
            all_violations.extend(check_file(path, root))

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
