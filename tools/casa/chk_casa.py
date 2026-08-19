# tools/casa/chk_casa.py -- CHK-CASA: convencoes da casa (perfil "casa", opt-in)
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
tools/casa/chk_casa.py

CHK-CASA (TODO.md, item W8): tres checks, todos `profile == "casa"`
(ADR-0001 secao a) -- convencoes ESPECIFICAS da casa do autor, nunca
assumidas de um repositorio generico. Fora do perfil "casa" nenhum dos tres
roda (`todo_audit.py` filtra por `profile` ANTES de chamar `run`); e este
modulo que prova, na pratica, que a fronteira nucleo-generico x
convencoes-da-casa (ADR-0001) funciona -- ate esta fatia, `tools/casa/`
so continha `_only_for_boundary_test` (`tools/casa/__init__.py`), uma
funcao sintetica que nunca roda em producao.

  CHK-12 -- ordem inviolavel: item cujo ID comeca com "TST-" ou "AUD-"
            (convencao da casa para teste-nao-unitario/auditoria, ver
            `references/catalogo-testes-auditorias.md`) tem que (a) citar
            via Pre-requisito o que cobre, e (b) estar agendado (ordem das
            linhas) DEPOIS de cada item citado. Regra literal do prompt:
            "teste nao-unitario vem depois da implementacao; auditoria vem
            depois de codigo E teste" -- por isso um AUD-* que cita um
            TST-* como pre-requisito ja fica corretamente ordenado depois
            dele por esta MESMA checagem (nao ha logica especial para
            "depois de teste" alem de tratar o TST-* como mais um
            pre-requisito comum).
  CHK-13 -- INBOX (`references/frescor-da-tabela.md` SS5.1): toda linha
            "- <ID tentativo ou -->: descricao curta" e verificada em dois
            eixos independentes -- formato (falta o separador ':', ou
            descricao vazia apos ele) e ID duplicando um ID JA presente na
            tabela canonica (sinal de que a descoberta ja foi drenada e a
            linha ficou esquecida, ou de colisao acidental que vira CHK-01
            assim que `--create`/`--reorder` drenar a INBOX).
  CHK-14 -- item fixo de Wiki + documentacao para iniciante, presente como
            ULTIMA onda da tabela (regra da casa: memoria do lider,
            "feedback_wiki_docs_iniciante" -- ultima onda/pos-tag,
            executado por technical-writer, nunca inline). Ausencia e
            SEMPRE COSMETICO com sugestao, nunca CRITICO -- e uma
            convencao de organizacao, nao um defeito de dado.

Nenhum dos tres reimplementa deteccao de coluna: reusa `checks.chk_graph`
(modulo `profile == "core"`) para localizar Onda/Pre-requisito por nome
(sinonimos pt+en ja testados) e a politica "ID inteiro vence" de
`_split_prereqs` -- casa DEPENDER de core e a direcao permitida da
fronteira (ADR-0001 a); so o inverso (core importar de `tools.casa`) e
proibido e verificado em CI por `todo_audit.core_boundary_violations`.

Nenhum destes checks assume portugues no conteudo livre (ADR-0001 secao d):
so os PREFIXOS `TST-`/`AUD-` (convencao fechada da casa, documentada em
`references/catalogo-testes-auditorias.md`) sao hardcoded -- Descricao,
formato de ID do usuario e o texto livre da INBOX nunca sao. CHK-14
reconhece "Wiki + doc iniciante" por uma lista de padroes com DEFAULT pt+en
embutido, extensivel (nao substituivel, salvo override explicito) via
`.tab_pendencias.ini` secao `[audit.chk14]` chave `patterns` -- o MESMO
mecanismo que ADR-0001 secao (d) ja fixa para CHK-09, uma unica forma de
configuracao no projeto inteiro em vez de reinventar por check.
"""
from __future__ import annotations

import re

import todo_lib as L
from checks import chk_graph as G

# ----------------------------------- CHK-12 ---------------------------------

_TST_AUD_PREFIXES = ("TST-", "AUD-")


def _e_tst_ou_aud(iid):
    return iid.startswith(_TST_AUD_PREFIXES)


def chk12(ctx):
    from todo_audit import Finding  # import tardio: ver nota de padrao em
    # checks/chk_graph.py -- so executa quando o check RODA de fato,
    # momento em que todo_audit.py ja terminou de carregar por completo.
    table = ctx.table
    if not table:
        return []
    prereq_idx = G._prereq_idx(table)
    if prereq_idx is None:
        return []
    known_ids = {it["id"] for it in table["items"]}
    onda_idx = G._onda_idx(table)
    rows = G._rows(table, onda_idx, prereq_idx)

    id_to_line = {}
    for row in rows:
        id_to_line.setdefault(row["id"], row["line_no"])

    out = []
    for row in rows:
        if not _e_tst_ou_aud(row["id"]):
            continue
        prereqs = G._split_prereqs(row["prereq_raw"], known_ids)
        cobertos = [p for p in prereqs if p in known_ids and p != row["id"]]
        if not cobertos:
            out.append(Finding(
                check_id="CHK-12", severity="IMPORTANTE",
                message=(
                    f"{row['id']!r} segue a convencao da casa TST-*/AUD-* "
                    "(teste nao-unitario ou auditoria, "
                    "references/catalogo-testes-auditorias.md) mas nao "
                    "declara nenhum Pre-requisito valido -- a convencao "
                    "espera que este item cite, via Pre-requisito, o que "
                    "ele cobre."),
                line_no=row["line_no"], fixable=False))
            continue
        for ref in cobertos:
            ref_line = id_to_line[ref]
            if row["line_no"] < ref_line:
                out.append(Finding(
                    check_id="CHK-12", severity="CRÍTICO",
                    message=(
                        f"{row['id']!r} (convencao TST-*/AUD-*) esta "
                        f"agendado ANTES do item que cobre ({ref!r}, linha "
                        f"{ref_line + 1}) -- ordem inviolavel: teste "
                        "nao-unitario vem depois da implementacao, "
                        "auditoria vem depois de codigo e teste. Se a "
                        "ordenacao produz o contrario, o Pre-requisito (ou "
                        "a Onda) esta errado."),
                    line_no=row["line_no"], fixable=False))
    return out


# ----------------------------------- CHK-13 ---------------------------------

_INBOX_PLACEHOLDER = ("", "-", "—")


def _inbox_raw_lines(lines):
    """[{line_no, raw}] -- mesma secao/criterio de `todo_lib.inbox_items`
    (heading contendo "inbox", linhas "- ..." ate o proximo heading), mas
    preservando `line_no` (que o helper do nucleo nao expoe, e nao ha razao
    para mudar o contrato do nucleo so por conveniencia deste check da
    casa -- ADR-0001, 'Riscos': o utilitario compartilhado vai para o
    nucleo, nunca o inverso; esta e uma pequena releitura LOCAL, restrita a
    este check, nao uma dependencia nova do nucleo)."""
    out = []
    in_inbox = False
    for n, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#"):
            in_inbox = "inbox" in s.lower()
            continue
        if in_inbox and s.startswith("- "):
            out.append({"line_no": n, "raw": s[2:].strip()})
    return out


def chk13(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table:
        return []
    known_ids = {it["id"] for it in table["items"]}
    out = []
    for entry in _inbox_raw_lines(table["lines"]):
        raw = entry["raw"]
        if not raw:
            continue
        if ":" not in raw:
            out.append(Finding(
                check_id="CHK-13", severity="COSMÉTICO",
                message=(
                    f"Linha da INBOX {raw!r} nao segue o formato "
                    "'<ID tentativo ou -->: descricao curta' "
                    "(references/frescor-da-tabela.md SS5.1) -- falta o "
                    "separador ':'."),
                line_no=entry["line_no"], fixable=False))
            continue
        id_part, desc_part = raw.split(":", 1)
        id_part = id_part.strip()
        if not desc_part.strip():
            out.append(Finding(
                check_id="CHK-13", severity="COSMÉTICO",
                message=(
                    f"Linha da INBOX {raw!r} tem ID mas descricao vazia "
                    "apos ':' -- o formato exige uma descricao curta do que "
                    "apareceu."),
                line_no=entry["line_no"], fixable=False))
        if id_part not in _INBOX_PLACEHOLDER and id_part in known_ids:
            out.append(Finding(
                check_id="CHK-13", severity="IMPORTANTE",
                message=(
                    f"Linha da INBOX cita ID {id_part!r}, que ja existe na "
                    "tabela canonica -- ou a descoberta ja foi drenada e a "
                    "linha da INBOX ficou esquecida (drenagem incompleta de "
                    "--create/--reorder), ou o ID tentativo colide por "
                    "acaso com um ID em uso (drenar assim criaria ID "
                    "duplicado, CHK-01)."),
                line_no=entry["line_no"], fixable=False))
    return out


# ----------------------------------- CHK-14 ---------------------------------

# Default embutido pt+en (ADR-0001 secao d, mesmo mecanismo de CHK-09):
# extensivel via .tab_pendencias.ini [audit.chk14] patterns = ..., nunca
# substituido por completo -- soma-se ao default, igual ao contrato de
# CHK-09. Palavras deliberadamente especificas (baixo risco de colisao por
# substring dentro de outra palavra comum, mas ainda assim comparadas com
# fronteira de palavra -- memoria do lider, "eu " casando dentro de "seu").
_WIKI_INICIANTE_DEFAULT_PATTERNS = (
    "wiki", "iniciante", "beginner", "getting started", "documentacao",
    "documentation", "novato",
)

_CONFIG_SECTION_CHK14 = "audit.chk14"
_CONFIG_KEY_PATTERNS = "patterns"

_DESC_HEADER_SUBSTR = ("descri", "description")  # "Descrição"/"Descrição
# Técnica"/"description" -- substring normalizada (sem acento, minusculo),
# nao exige nome exato de coluna (a coluna de descricao nao tem contrato
# fixo de nome no nucleo, so ID/Status tem via todo_lib._is_header).


def _patterns_chk14(config):
    patterns = list(_WIKI_INICIANTE_DEFAULT_PATTERNS)
    if config is not None:
        raw = config.get(_CONFIG_SECTION_CHK14, _CONFIG_KEY_PATTERNS,
                          fallback=None)
        if raw:
            extra = [p.strip().lower() for p in raw.split(",") if p.strip()]
            patterns.extend(p for p in extra if p)
    return patterns


def _find_desc_idx(table):
    cells = G._header_cells(table)
    if not cells:
        return None
    for i, c in enumerate(cells):
        norm = G._norm(c)
        if any(sub in norm for sub in _DESC_HEADER_SUBSTR):
            return i
    return None


def _matches_any_pattern(text, patterns):
    norm = G._norm(text)
    for p in patterns:
        if re.search(r"\b" + re.escape(G._norm(p)) + r"\b", norm):
            return True
    return False


def _row_cells(table, line_no):
    line = table["lines"][line_no]
    return L._cells(line.lstrip(L.BOM).strip())


def _last_onda_items(table):
    """(rotulo_da_ultima_onda_ou_None, [item,...]) -- itens da ULTIMA onda
    real (nao travessao/vazia) na ordem das linhas. Sem coluna Onda
    (schema legado de 8 colunas), degrada para o unico ultimo item da
    tabela (nao ha onda para agrupar, mas ainda ha uma "ultima linha" cuja
    Descricao pode ser checada) -- nunca lanca excecao, nunca assume
    ncols == 9 (ADR-0001 b.2)."""
    onda_idx = G._onda_idx(table)
    if onda_idx is None:
        return None, (table["items"][-1:] if table["items"] else [])
    onda_por_item = []
    for it in table["items"]:
        cells = _row_cells(table, it["line_no"])
        onda = cells[onda_idx].strip() if onda_idx < len(cells) else ""
        onda_por_item.append((it, onda))
    ultima = None
    for _it, onda in reversed(onda_por_item):
        if onda not in ("", "-", "—"):
            ultima = onda
            break
    if ultima is None:
        return None, []
    itens = [it for it, onda in onda_por_item if onda == ultima]
    return ultima, itens


def chk14(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table or not table["items"]:
        return []
    desc_idx = _find_desc_idx(table)
    if desc_idx is None:
        return []  # sem coluna de descricao identificavel: nao ha o que ler
    ultima_onda, itens = _last_onda_items(table)
    if not itens:
        return []
    patterns = _patterns_chk14(ctx.config)
    for it in itens:
        cells = _row_cells(table, it["line_no"])
        desc = cells[desc_idx] if desc_idx < len(cells) else ""
        if _matches_any_pattern(desc, patterns):
            return []  # achado -- convencao presente, motor fica em silencio
    rotulo = f" ({ultima_onda!r})" if ultima_onda else ""
    return [Finding(
        check_id="CHK-14", severity="COSMÉTICO",
        message=(
            f"Nenhum item da ultima onda{rotulo} descreve a convencao da "
            "casa de Wiki + documentacao para iniciante (item fixo de fim "
            "de tabela, pos-tag). Sugestao: adicione um item na ultima "
            "onda cobrindo Wiki do repositorio + documentacao didatica "
            "para iniciante em computacao (nunca inline -- executor "
            "technical-writer/ux-writer)."),
        line_no=itens[-1]["line_no"], fixable=False)]
