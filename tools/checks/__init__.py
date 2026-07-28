# tools/checks/__init__.py -- checks concretos do catalogo CHK-01..14
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
tools/checks/

Subpacote com os checks concretos do catalogo (CHK-01..14), um modulo por
fatia (ex.: `chk_graph.py` para CHK-05/06/07 -- CHK-GRAPH). Todos os checks
aqui sao `profile == "core"` a menos que a propria fatia diga o contrario;
nenhum modulo deste subpacote importa nada de `tools/casa/` (fronteira
ADR-0001 secao a). `tools/todo_audit.py` importa cada modulo e registra os
`Check` correspondentes em `CHECKS` -- este subpacote nao registra nada
sozinho, so define funcoes `run(ctx) -> list[Finding]` e (opcionalmente)
helpers puros de deteccao/parsing reutilizados pelos testes.
"""
