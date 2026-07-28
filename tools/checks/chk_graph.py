# tools/checks/chk_graph.py -- CHK-GRAPH: grafo de dependencias (CHK-05/06/07)
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
tools/checks/chk_graph.py

CHK-GRAPH (W7, TODO.md): um walk no grafo de pre-requisitos da tabela
canonica, tres perguntas:

  CHK-05 -- pre-requisito citando ID inexistente (severidade IMPORTANTE).
  CHK-06 -- ciclo de dependencia; reporta o CICLO INTEIRO
            ("A -> B -> C -> A"), nao so "ha um ciclo" (severidade CRITICO).
  CHK-07 -- Onda inconsistente com a dependencia, dois casos independentes:
            (a) o item esta na MESMA onda de um pre-requisito seu;
            (b) o item aparece ANTES do proprio pre-requisito na ordem das
            linhas (severidade IMPORTANTE).

Os tres sao `profile == "core"` (ADR-0001 secao a): dependem so da
estrutura ID/Onda/Pre-requisito que o proprio produto define, nenhuma
convencao da casa.

--- Deteccao das colunas Onda e Pre-requisito -------------------------------

`todo_lib.parse_table` so expoe `id_idx`/`status_idx` (contrato ADR-0001
b.2, localizados por NOME de cabecalho, nunca por posicao fixa ou
`ncols == 9` hardcoded). As colunas Onda/Pre-requisito nao tem esse mesmo
contrato ainda no nucleo -- este modulo estende o MESMO principio (nome do
cabecalho, agnostico a posicao) para elas, com uma lista pequena de
sinonimos pt+en (o mesmo padrao que a ADR-0001 secao (d) ja fixou para
CHK-09: default embutido pt+en, sem exigir vocabulario do autor). Ausencia
de uma das colunas (schema legado sem Onda -- `ADR-0001 b.2`, ou uma tabela
sem coluna de dependencia nenhuma) NAO e erro: os checks que dependem dela
simplesmente nao acham nada para reportar (lista vazia), o mesmo tratamento
que uma tabela legada de 8 colunas ja recebe no resto do nucleo.

--- Politica de lista de pre-requisitos com virgula (decisao desta fatia) ---

A celula de Pre-requisito PODE ser uma lista ("F2.1, F2.2") OU um unico ID
que por acaso CONTEM virgula -- o produto e agnostico a esquema de ID
(SS4.0 do prompt), entao um ID como "OPS,1" e legitimo. Politica adotada,
documentada aqui e testada em `tests/test_chk_graph.py`: primeiro tenta o
texto INTEIRO da celula como UM UNICO ID, contra o conjunto de IDs
conhecidos da propria tabela; se bater, e um unico pre-requisito (mesmo com
virgula dentro). So quando o texto inteiro NAO bate com nenhum ID
conhecido e' que a celula e dividida por virgula, cada pedaco stripado
tratado como um ID separado. "ID inteiro vence" carrega uma ambiguidade
genuina (um ID inventado que colide texto-a-texto com uma lista de dois
IDs existentes concatenados por virgula), mas essa colisao exige uma
coincidencia exata que a pratica nao produz -- e a UNICA leitura que nao
quebra nem o caso lista nem o caso ID-com-virgula sem exigir uma sintaxe de
escape nova que o produto ainda nao define.

--- Onda com travessao (itens concluidos / fora do fluxo) -------------------

Uma celula de Onda vazia, "-" ou "--" (travessao, D-6) significa "fora do
fluxo de ondas" (item concluido, cancelado, etc.) -- nunca participa da
comparacao de "mesma onda" do CHK-07(a): se o item OU o pre-requisito
citado tem Onda-travessao, o par e ignorado por essa checagem (nao ha
"onda" real para comparar). A checagem de ORDEM do CHK-07(b) independe de
Onda: vale sempre que o pre-requisito exista na tabela, porque a garantia
"a ordem das linhas E a ordem de execucao recomendada" (TODO.md, topo) nao
e condicionada a estar ou nao dentro do fluxo de ondas.

Auto-referencia (`item` cita a si mesmo como pre-requisito) e deliberada-
mente ignorada aqui: e um ciclo de tamanho 1, e o CHK-06 (mais informativo,
severidade CRITICO) ja o cobre -- reportar de novo em CHK-07 so duplicaria
o mesmo achado com um rotulo menos claro.
"""
from __future__ import annotations

import unicodedata

import todo_lib as L

_DASH = ("", "-", "—")  # vazio, hifen, travessao (D-6): "fora do fluxo"

_ONDA_NAMES = ("onda", "wave")
_PREREQ_NAMES = (
    "pre-requisito", "prerequisito", "pré-requisito", "requisito",
    "blocked by", "depends on", "dependency", "dependencies",
)

# Orcamento de passos da enumeracao de ciclos (CHK-06): generoso o bastante
# para qualquer TODO.md real (dezenas a poucas centenas de itens, poucos
# pre-requisitos por item) nunca chegar perto -- existe so para nao deixar
# uma entrada ADVERSARIAL (grafo denso construido de proposito) travar o
# motor num loop sem fim. Se estourado, o proprio achado declara a
# interrupcao (no silent caps): ver `_find_all_cycles`.
_CYCLE_STEP_BUDGET = 200_000


def _norm(s):
    """minusculo + sem diacritico -- SO para comparar NOME de coluna
    (schema fixo do produto), nunca aplicado ao conteudo livre do usuario
    (ADR-0001 secao d trata os dois como camadas diferentes)."""
    nfkd = unicodedata.normalize("NFKD", s)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.strip().lower()


_ONDA_NAMES_NORM = {_norm(n) for n in _ONDA_NAMES}
_PREREQ_NAMES_NORM = {_norm(n) for n in _PREREQ_NAMES}


def _header_cells(table):
    """Celulas da linha de cabecalho real (ID+Status) da tabela canonica.

    `table` (retorno de `L.parse_table`) so expoe `id_idx`/`status_idx`, nao
    as celulas do cabecalho em si -- refaz a localizacao varrendo
    `table["lines"]` pelo MESMO criterio que `todo_lib._is_header` usa
    (celula do id_idx == "id", celula do status_idx contem "status"), sem
    duplicar a logica de seccionamento do parser (so procura a linha, nao
    reimplementa o fim-de-tabela)."""
    id_idx, status_idx, ncols = (table["id_idx"], table["status_idx"],
                                  table["ncols"])
    for raw in table["lines"]:
        s = raw.lstrip(L.BOM).strip()
        if not s.startswith("|"):
            continue
        cells = L._cells(s)
        if len(cells) != ncols:
            continue
        if (cells[id_idx].strip().lower() == "id"
                and "status" in cells[status_idx].lower()):
            return cells
    return None


def _find_col(table, names_norm):
    cells = _header_cells(table)
    if not cells:
        return None
    for i, c in enumerate(cells):
        if _norm(c) in names_norm:
            return i
    return None


def _onda_idx(table):
    return _find_col(table, _ONDA_NAMES_NORM)


def _prereq_idx(table):
    return _find_col(table, _PREREQ_NAMES_NORM)


def _rows(table, onda_idx, prereq_idx):
    """Uma entrada por ITEM da tabela (mesma ordem/duplicatas de
    `table["items"]`), com as celulas de Onda/Pre-requisito relidas da
    propria linha (`parse_table` so guarda id/status/line_no por item)."""
    out = []
    for it in table["items"]:
        line = table["lines"][it["line_no"]]
        cells = L._cells(line.lstrip(L.BOM).strip())
        onda = cells[onda_idx].strip() if onda_idx is not None else None
        prereq_raw = cells[prereq_idx].strip() if prereq_idx is not None else ""
        out.append({"id": it["id"], "line_no": it["line_no"],
                    "onda": onda, "prereq_raw": prereq_raw})
    return out


def _split_prereqs(raw, known_ids):
    """Lista de IDs referenciados por uma celula de Pre-requisito, sob a
    politica "ID inteiro vence" documentada no topo do modulo."""
    text = raw.strip()
    if text in _DASH:
        return []
    if text in known_ids:
        return [text]
    return [p.strip() for p in text.split(",") if p.strip()]


def _build_graph(rows, known_ids):
    """(`graph`, `order`): `graph[id]` = lista de IDs dos quais `id`
    depende (deduplicada, so referencias VALIDAS -- inexistentes sao CHK-05,
    nao entram no grafo de ciclo); `order` = IDs na ordem da 1a aparicao na
    tabela, usada por `_find_all_cycles` para canonizar o ponto de partida
    de cada ciclo (evita reportar a mesma rotacao 2x)."""
    graph = {}
    order = []
    seen = set()
    for row in rows:
        rid = row["id"]
        if rid not in seen:
            seen.add(rid)
            order.append(rid)
        bucket = graph.setdefault(rid, [])
        for ref in _split_prereqs(row["prereq_raw"], known_ids):
            if ref in known_ids and ref not in bucket:
                bucket.append(ref)
    return graph, order


def _find_all_cycles(graph, order, step_budget=_CYCLE_STEP_BUDGET):
    """Todos os ciclos ELEMENTARES do grafo (`list[list[id]]`, cada lista e
    o ciclo na ordem de percurso, sem repetir o no inicial no fim -- quem
    formata a seta de volta e o chamador) + `bool` "orcamento estourado".

    DFS com poda por RANK (a mesma tecnica que da correcao ao algoritmo de
    Johnson, sem o conjunto de bloqueio que so acelera): cada ciclo tem
    exatamente um no de MENOR rank (posicao de 1a aparicao na tabela); a
    busca a partir de `start` so avanca para vizinhos de rank >= rank(start),
    entao cada ciclo elementar so pode ser descoberto UMA vez, pela busca
    que comeca no seu proprio no de menor rank -- sem essa poda, a mesma
    volta apareceria uma vez por no do ciclo (rotacoes duplicadas)."""
    rank = {node: i for i, node in enumerate(order)}
    cycles = []
    steps = 0
    estourado = False

    def dfs(start, node, visited, path):
        nonlocal steps, estourado
        if estourado:
            return
        for neigh in graph.get(node, ()):
            steps += 1
            if steps > step_budget:
                estourado = True
                return
            if neigh == start:
                cycles.append(list(path))
            elif rank[neigh] > rank[start] and neigh not in visited:
                visited.add(neigh)
                path.append(neigh)
                dfs(start, neigh, visited, path)
                path.pop()
                visited.discard(neigh)
                if estourado:
                    return

    for start in order:
        dfs(start, start, {start}, [start])
        if estourado:
            break
    return cycles, estourado


def chk05(ctx):
    table = ctx.table
    if not table:
        return []
    from todo_audit import Finding  # import tardio: quebra o ciclo de
    # importacao com todo_audit.py (que registra este check importando este
    # MODULO) -- por ser dentro do corpo da funcao, so executa quando o
    # check RODA (run_audit chamando check.run), momento em que todo_audit
    # ja terminou de carregar por completo.
    prereq_idx = _prereq_idx(table)
    if prereq_idx is None:
        return []
    known_ids = {it["id"] for it in table["items"]}
    rows = _rows(table, _onda_idx(table), prereq_idx)
    out = []
    for row in rows:
        for ref in _split_prereqs(row["prereq_raw"], known_ids):
            if ref not in known_ids:
                out.append(Finding(
                    check_id="CHK-05", severity="IMPORTANTE",
                    message=(f"{row['id']!r} cita pre-requisito {ref!r}, "
                             "que nao existe na tabela"),
                    line_no=row["line_no"]))
    return out


def chk06(ctx):
    table = ctx.table
    if not table:
        return []
    from todo_audit import Finding
    prereq_idx = _prereq_idx(table)
    if prereq_idx is None:
        return []
    known_ids = {it["id"] for it in table["items"]}
    rows = _rows(table, _onda_idx(table), prereq_idx)
    graph, order = _build_graph(rows, known_ids)
    id_to_line = {}
    for row in rows:
        id_to_line.setdefault(row["id"], row["line_no"])

    cycles, estourado = _find_all_cycles(graph, order)
    out = []
    for cyc in cycles:
        caminho = " → ".join(cyc + [cyc[0]])
        out.append(Finding(
            check_id="CHK-06", severity="CRÍTICO",
            message=f"ciclo de dependência: {caminho}",
            line_no=id_to_line.get(cyc[0])))
    if estourado:
        out.append(Finding(
            check_id="CHK-06", severity="CRÍTICO",
            message=(
                "enumeração de ciclos interrompida por orçamento de passos "
                f"({_CYCLE_STEP_BUDGET}) -- pode haver ciclo(s) adicional(is) "
                "não enumerado(s) além dos listados acima (no silent caps)."),
            line_no=None))
    return out


def chk07(ctx):
    table = ctx.table
    if not table:
        return []
    from todo_audit import Finding
    prereq_idx = _prereq_idx(table)
    if prereq_idx is None:
        return []
    onda_idx = _onda_idx(table)
    known_ids = {it["id"] for it in table["items"]}
    rows = _rows(table, onda_idx, prereq_idx)

    id_to_line = {}
    id_to_onda = {}
    for row in rows:
        id_to_line.setdefault(row["id"], row["line_no"])
        id_to_onda.setdefault(row["id"], row["onda"])

    out = []
    for row in rows:
        for ref in _split_prereqs(row["prereq_raw"], known_ids):
            if ref not in known_ids or ref == row["id"]:
                continue  # inexistente = CHK-05; auto-referencia = CHK-06
            prereq_line = id_to_line[ref]
            if row["line_no"] < prereq_line:
                out.append(Finding(
                    check_id="CHK-07", severity="IMPORTANTE",
                    message=(f"{row['id']!r} aparece antes do proprio "
                             f"pre-requisito {ref!r} na ordem das linhas"),
                    line_no=row["line_no"]))
            if onda_idx is not None:
                onda_item = row["onda"]
                onda_prereq = id_to_onda.get(ref)
                if (onda_item not in _DASH and onda_prereq not in _DASH
                        and onda_item == onda_prereq):
                    out.append(Finding(
                        check_id="CHK-07", severity="IMPORTANTE",
                        message=(f"{row['id']!r} esta na MESMA onda "
                                 f"({onda_item}) do seu pre-requisito "
                                 f"{ref!r}"),
                        line_no=row["line_no"]))
    return out
