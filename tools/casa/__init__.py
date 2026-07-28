# tools/casa/__init__.py -- convencoes da CASA (opt-in), isoladas do nucleo
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
tools/casa/

Subpacote reservado para a logica de checks `profile == "casa"` (ADR-0001,
secao (a)): convencoes especificas da casa do autor (hoje so CHK-14,
Wiki+doc-iniciante -- ainda por implementar em CHK-CASA, W8). Nenhum check
`profile == "core"` pode importar nada daqui; `tools/todo_audit.py` prova
isso em CI via `core_boundary_violations()`, que verifica em que ARQUIVO
(nao so nome de modulo -- `tools/` nao e um pacote Python formal, os scripts
sao importados como modulos soltos via sys.path) o `run` de cada check
`core` foi definido.

Este arquivo fica vazio de checks de proposito ate a fatia CHK-CASA. A
funcao abaixo existe SO para o teste de fronteira de AUDIT-ENG poder provar
(antes de existir qualquer check 'casa' de verdade) que a deteccao de
violacao PEGA um caso real -- nunca e registrada em `tools.todo_audit.CHECKS`.
"""


def _only_for_boundary_test(ctx):
    """Nunca chamada em producao. Existe so para os testes de fronteira
    core-x-casa de `tools/todo_audit.py` terem uma funcao real, definida
    fisicamente neste arquivo, para apontar como violacao sintetica."""
    return []
