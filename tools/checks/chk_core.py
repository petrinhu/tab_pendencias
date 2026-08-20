# tools/checks/chk_core.py -- CHK-CORE: integridade de tabela e vocabulario
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
tools/checks/chk_core.py

CHK-CORE (TODO.md, item W7): integridade estrutural da tabela canonica e do
vocabulario de status. Todos com `profile == "core"`:

  CHK-01 -- ID duplicado (todas as ocorrencias, com diff resumido).
  CHK-02 -- nº de celulas != cabecalho, com DIAGNOSTICO heuristico da causa.
  CHK-03 -- multiplos cabecalhos ID+Status (tabela fragmentada) + span.
  CHK-04 -- ncols divergente entre tabelas ID+Status (pre-condicao FIX-ENG).
  CHK-08 -- status fora do vocabulario canonico (D-1).
  CHK-11 -- reconciliacao do total do todo_health com contagem independente.
  CHK-19 -- mais de uma tabela DE TRABALHO no arquivo (UNIQ-1).
  CHK-20 -- linha em branco DENTRO da tabela canonica (UNIQ-1 b).

Nenhum check aqui reimplementa parsing: consome as chaves ADITIVAS que
`todo_lib.parse_table` ja expoe (`malformed`, `duplicate_ids`,
`headings_crossed`) e os predicados/helpers ja existentes
(`status_classification_via`, `_cells`, `_is_header`). CHK-11 e a unica
excecao parcial: a contagem "independente" e, por desenho (ver docstring do
proprio check), um caminho de codigo DIFERENTE do de `parse_table`, para nao
ser tautologica.

Registro em `todo_audit.CHECKS`: este modulo NAO define sua propria lista
`CHECKS` (ao contrario do que uma versao anterior deste arquivo fazia) --
`todo_audit.py` importa as funcoes `_chkNN_*` diretamente e constroi os
`Check(...)` no registro central, mesmo padrao ja em uso por
`checks/chk_graph.py` e `checks/chk_frescor.py`.
"""
from __future__ import annotations

import contextlib
import io
import re

import todo_health as H
import todo_lib as L

# `Finding` e importado DENTRO do corpo de cada funcao de check (nao aqui no
# topo do modulo) -- o mesmo padrao de `checks/chk_graph.py`/`chk_frescor.py`:
# `todo_audit.py` importa este modulo NO MEIO do seu proprio carregamento
# (apos definir Check/Finding, mas antes de terminar o arquivo), entao um
# `from todo_audit import Finding` no topo veria um modulo `todo_audit`
# parcialmente inicializado (import circular). Import local resolve porque
# so executa quando o check RODA de fato, momento em que todo_audit.py ja
# terminou de carregar por completo.

# ------------------------------- CHK-01 -----------------------------------

_PLACEHOLDER = ("-", "—", "")


def _celula_e_placeholder(c):
    return c.strip() in _PLACEHOLDER


def _candidato_fragmento(occs_cells, id_idx, status_idx):
    """Indice (dentro de `occs_cells`) da ocorrencia que parece claramente
    fragmento/lixo, ou None quando a diferenca exige julgamento humano.

    Heuristica DELIBERADAMENTE conservadora (ADR-0001, 'no silent caps': um
    diagnostico e sempre declarado como suposicao, nunca fato): só aponta um
    candidato quando, comparando cada PAR de ocorrencias, exatamente UMA
    celula (fora ID/Status) diverge E essa divergencia e ou (a) uma delas e
    placeholder vazio ("-"/"—"/"") enquanto a outra tem conteudo real, ou (b)
    uma e um PREFIXO estrito da outra (assinatura tipica de escrita
    truncada/copy-paste incompleto). Duas ou mais celulas divergindo (ex.:
    Wave E Descricao E Status, como no corpus `defeito_id_duplicado.md`) e
    tratado como ambiguo demais para decidir sozinho -- fica [julgamento]."""
    if len(occs_cells) != 2:
        return None  # 3+ ocorrencias: heuristica par-a-par nao escala, julgamento
    a, b = occs_cells
    if len(a) != len(b):
        return None
    divergentes = [i for i in range(len(a))
                   if i not in (id_idx, status_idx) and a[i] != b[i]]
    if len(divergentes) != 1:
        return None
    i = divergentes[0]
    if _celula_e_placeholder(a[i]) and not _celula_e_placeholder(b[i]):
        return 0
    if _celula_e_placeholder(b[i]) and not _celula_e_placeholder(a[i]):
        return 1
    if a[i] and b[i].startswith(a[i]) and a[i] != b[i]:
        return 0
    if b[i] and a[i].startswith(b[i]) and a[i] != b[i]:
        return 1
    return None


def _chk01_id_duplicado(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table or not table["duplicate_ids"]:
        return []
    out = []
    for iid, occs in sorted(table["duplicate_ids"].items()):
        raws = [table["lines"][o["line_no"]] for o in occs]
        cells = [L._cells(r) for r in raws]
        resumo = "; ".join(
            f"linha {o['line_no'] + 1} (status={o['status']!r})"
            for o in occs)
        candidato = _candidato_fragmento(cells, table["id_idx"],
                                          table["status_idx"])
        msg = f"ID {iid!r} aparece {len(occs)}x -- {resumo}."
        fixable = candidato is not None
        if fixable:
            linha_lixo = occs[candidato]["line_no"] + 1
            msg += (f" SUPOSICAO (heuristica, nao fato): a ocorrencia da "
                    f"linha {linha_lixo} parece fragmento/lixo (demais "
                    "celulas identicas, so uma diverge por placeholder "
                    "vazio ou prefixo truncado).")
        else:
            msg += (" Julgamento humano necessario: as ocorrencias divergem "
                    "em mais de uma celula (ou 3+ ocorrencias), sem sinal "
                    "mecanico de qual e a valida.")
        out.append(Finding(
            check_id="CHK-01", severity="CRÍTICO", message=msg,
            line_no=occs[0]["line_no"], fixable=fixable,
            fix_ref="remover_fragmento_duplicado" if fixable else None))
    return out


# ------------------------------- CHK-02 -----------------------------------

_CODE_SPAN_COM_PIPE = re.compile(r"`[^`\n]*\|[^`\n]*`")


def _diagnostico_malformed(m):
    """(mensagem, fixable, fix_ref) -- SEMPRE prefixado com 'SUPOSICAO' (no
    silent caps: o diagnostico e heuristica, ADR-0001 'Riscos'). Tres causas
    conhecidas: pipe cru nao escapado (celula A MAIS), fragmento truncado
    (celulas A MENOS, linha nao fecha em '|'), celula faltando (celulas A
    MENOS, linha fecha em '|' normalmente -- so esqueceram de preencher)."""
    raw = m["raw"]
    esperado, obtido = m["expected_ncols"], m["got_ncols"]
    if obtido > esperado:
        extra = obtido - esperado
        if _CODE_SPAN_COM_PIPE.search(raw):
            return (
                f"{extra} celula(s) a mais ({obtido} obtidas, {esperado} "
                f"esperadas) -- SUPOSICAO: pipe cru dentro de um code span "
                "(crase) nao foi escapado; troque o '|' literal por '\\|'.",
                True, "escapar_pipe_cru")
        return (
            f"{extra} celula(s) a mais ({obtido} obtidas, {esperado} "
            "esperadas) -- SUPOSICAO: algum '|' literal na linha nao foi "
            "escapado; troque por '\\|' no ponto que nao deveria separar "
            "coluna.",
            True, "escapar_pipe_cru")
    falta = esperado - obtido
    fecha_com_pipe = raw.rstrip("\r\n").rstrip().endswith("|")
    if not fecha_com_pipe or falta >= max(2, esperado // 2):
        return (
            f"{falta} celula(s) a menos ({obtido} obtidas, {esperado} "
            "esperadas), linha nao termina em '|' -- SUPOSICAO: fragmento "
            "truncado (escrita/copia cortada no meio); confira se ha uma "
            "ocorrencia completa do mesmo ID antes de remover.",
            False, None)
    return (
        f"{falta} celula(s) a menos ({obtido} obtidas, {esperado} "
        "esperadas), linha termina em '|' normalmente -- SUPOSICAO: celula "
        "faltando (coluna nao preenchida); adicione a(s) celula(s) que "
        "falta(m).",
        False, None)


def _malformed_genuinos(malformed, max_gap=2):
    """Filtra `malformed` removendo as entradas que fazem parte de um
    CLUSTER de 2+ linhas com o MESMO `got_ncols` e `line_no` proximos entre
    si (gap <= max_gap, que cobre exatamente cabecalho + 1 linha de
    separador GFM PULADA antes da 1a linha de dado -- separador nunca entra
    em 'malformed', `todo_lib.py` o descarta antes da guarda de ncols).

    Essa e a assinatura estrutural de uma tabela ALHEIA bem-formada
    (cabecalho+separador+dados, ex.: uma tabela de prioridade WSJF de 8
    colunas ou uma checklist de assets de 5 colunas em outra secao do MESMO
    documento) que so aparece em 'malformed' porque o nucleo (D-12) nunca
    reseta ncols/id_idx ao encontrar um cabecalho sem celula 'status' --
    ela nao e um defeito, e dado legitimo de OUTRA tabela.

    Uma entrada ISOLADA (sem vizinho de mesmo ncols por perto) e o sinal
    contrario: defeito GENUINO da canonica (fragmento truncado ou pipe cru
    na propria linha) -- confirmado contra a fixture real do CONTR-1: os
    UNICOS 2 malformed isolados sao exatamente TODO-PARSER-BUG (pipe cru,
    ncols a mais) e o fragmento truncado adjacente a ATOM-3 (ncols a
    menos), os 2 defeitos vivos publicos que AC-REAL pede para o --audit
    tornar visiveis; as outras dezenas de 'malformed' do mesmo arquivo sao
    todas linhas de tabelas alheias em cluster, corretamente silenciadas
    aqui. SUPOSICAO/heuristica -- nao fato (no silent caps)."""
    by_ncols = {}
    for i, m in enumerate(malformed):
        by_ncols.setdefault(m["got_ncols"], []).append(i)
    em_cluster = set()
    for _ncols, idxs in by_ncols.items():
        idxs_sorted = sorted(idxs, key=lambda i: malformed[i]["line_no"])
        cluster = [idxs_sorted[0]]
        for prev_i, cur_i in zip(idxs_sorted, idxs_sorted[1:]):
            if malformed[cur_i]["line_no"] - malformed[prev_i]["line_no"] <= max_gap:
                cluster.append(cur_i)
            else:
                if len(cluster) >= 2:
                    em_cluster.update(cluster)
                cluster = [cur_i]
        if len(cluster) >= 2:
            em_cluster.update(cluster)
    return [m for i, m in enumerate(malformed) if i not in em_cluster]


def _chk02_ncols_diverge(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table or not table["malformed"]:
        return []
    out = []
    for m in _malformed_genuinos(table["malformed"]):
        msg, fixable, fix_ref = _diagnostico_malformed(m)
        out.append(Finding(
            check_id="CHK-02", severity="CRÍTICO", message=msg,
            line_no=m["line_no"], fixable=fixable, fix_ref=fix_ref))
    return out


# --------------------------- CHK-03 / CHK-04 -------------------------------

def _cabecalhos_id_status(lines):
    """Linha (0-based) + ncols de TODA linha que e cabecalho ID+Status --
    inclusive alem do fim da tabela canonica (parse_table so registra a
    1a). Reusa L._cells/L._is_header (mesmos helpers do nucleo, nao
    reimplementados) para nao divergir do que o parser considera
    cabecalho."""
    out = []
    for n, line in enumerate(lines):
        s = line.lstrip(L.BOM).strip()
        if not s.startswith("|"):
            continue
        cells = L._cells(s)
        if L._is_header(cells):
            out.append({"line_no": n, "ncols": len(cells)})
    return out


def _chk03_tabela_fragmentada(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table:
        return []
    cabecalhos = _cabecalhos_id_status(table["lines"])
    if not cabecalhos:
        return []
    itens_e_malformed = table["items"] + table["malformed"]
    fim_canonica = (max(x["line_no"] for x in itens_e_malformed)
                     if itens_e_malformed else cabecalhos[0]["line_no"])
    inicio_canonica = cabecalhos[0]["line_no"]
    span = f"linhas {inicio_canonica + 1}-{fim_canonica + 1}"
    # So conta heading que INTERROMPE dado real (line_no antes do ultimo
    # item/malformed processado) -- um heading APOS o ultimo item e prosa de
    # epilogo (ex.: "## Notes" de encerramento), scaneada pelo parser so
    # porque ele varre ate o EOF procurando 2o cabecalho/tabela alheia, mas
    # nao interrompe tabela nenhuma: nao e achado, e ruido.
    crossed_relevantes = [h for h in table["headings_crossed"]
                          if h["line_no"] < fim_canonica]
    n_crossed = len(crossed_relevantes)

    out = []
    if len(cabecalhos) > 1:
        prox = cabecalhos[1]["line_no"] + 1
        out.append(Finding(
            check_id="CHK-03", severity="CRÍTICO",
            message=(
                f"{len(cabecalhos)} cabecalhos ID+Status encontrados no "
                f"arquivo -- tabela fragmentada. Canonica ({span}) encerra "
                f"no 1o cabecalho repetido (linha {prox}); linhas de uma 2a "
                "tabela do MESMO schema a partir dai NAO entram em 'items' "
                "(D-6/ADR-0001 b.4) -- consolide com --fix so depois de "
                "confirmar ncols identicos (CHK-04)."),
            line_no=cabecalhos[1]["line_no"], fixable=False))
    elif n_crossed > 0:
        out.append(Finding(
            check_id="CHK-03", severity="COSMÉTICO",
            message=(
                f"Canonica ({span}) atravessa {n_crossed} heading(s) "
                "markdown sem encerrar (D-12: heading nunca encerra por si "
                "so) -- informativo, nao e defeito: organizacao visual em "
                "subtitulos e legitima."),
            line_no=inicio_canonica, fixable=False))
    return out


def _chk04_ncols_divergente_entre_tabelas(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table:
        return []
    cabecalhos = _cabecalhos_id_status(table["lines"])
    if len(cabecalhos) < 2:
        return []
    canonico = table["ncols"]
    out = []
    for h in cabecalhos[1:]:
        if h["ncols"] != canonico:
            out.append(Finding(
                check_id="CHK-04", severity="CRÍTICO",
                message=(
                    f"Cabecalho ID+Status na linha {h['line_no'] + 1} tem "
                    f"{h['ncols']} coluna(s), a canonica tem {canonico} -- "
                    "consolidar as duas tabelas sem antes igualar o "
                    "numero de colunas faz item sumir ou desalinhar de "
                    "coluna (pre-condicao de FIX-ENG, nunca pular)."),
                line_no=h["line_no"], fixable=False))
    return out


# ------------------------------- CHK-19 ------------------------------------
# Numeracao: CHK-15..18 estao RESERVADOS ao modulo `--audit=repo` (v1.1, D-5,
# citados em docs/adr/0001-*.md); o proximo numero realmente livre e 19.

def _chk19_tabela_unica(ctx):
    """UNIQ-1: mais de UMA tabela de trabalho no arquivo.

    Diferente de CHK-03, que conta CABECALHOS `ID`+`Status` (celula exata
    "id") ao longo do arquivo inteiro: este conta BLOCOS markdown cujo
    cabecalho tem coluna Status e coluna de identificador. Isso pega dois
    casos que CHK-03 nao pega -- (a) uma 2a tabela de trabalho cuja coluna de
    ID nao se chama exatamente "ID" (ex.: "ID (AUD-*)"), que o nucleo nem
    consegue eleger e por isso passa despercebida, e (b) o fato de o defeito
    ser de BLOCO (o que o Markdown renderiza como tabela), nao de linha de
    cabecalho solta. Quando os dois disparam juntos, os dois estao certos e
    dizem a mesma coisa por angulos diferentes -- redundancia deliberada num
    defeito que ja custou um backlog de 491 itens lido como 1 item."""
    from todo_audit import Finding
    if ctx.text is None:
        return []
    tabelas = L.work_tables(ctx.text)
    if len(tabelas) < 2:
        return []
    onde = "; ".join(
        f"linha {w['line_no'] + 1} ({w['n_rows']} linha(s) de dado)"
        for w in tabelas)
    return [Finding(
        check_id="CHK-19", severity="CRÍTICO",
        message=(
            f"{len(tabelas)} tabelas DE TRABALHO (com coluna Status) no "
            f"arquivo -- {onde}. O contrato exige exatamente UMA "
            "(references/frescor-da-tabela.md SS5): a leitura para no 1o "
            "cabecalho repetido, entao os itens das tabelas seguintes NAO "
            "entram em 'items' nem em contagem nenhuma -- ficam invisiveis "
            "sem erro na tela. Consolide numa tabela so; se alguma for "
            "tabela de REFERENCIA (legenda, matriz, scoring), tire dela a "
            "coluna Status, que e o que a marca como de trabalho."),
        line_no=tabelas[1]["line_no"], fixable=False)]


# ------------------------------- CHK-20 ------------------------------------

def _chk20_linha_em_branco_na_tabela(ctx):
    """UNIQ-1 (b): linha em branco DENTRO do span da tabela canonica.

    E o mecanismo SILENCIOSO pelo qual uma tabela vira duas: em Markdown a
    linha em branco encerra a tabela ali (a metade de baixo passa a renderizar
    como outra tabela ou como prosa solta), enquanto o parser deste toolkit
    atravessa e continua lendo os itens -- ninguem ve nada errado ate a
    proxima edicao repetir o cabecalho na metade de baixo, e ai a leitura para
    no cabecalho repetido e os itens de la somem (CHK-19/CHK-03).

    Severidade IMPORTANTE, nao CRITICO, por medicao do dano: enquanto so ha a
    linha em branco, NENHUM item deixa de ser lido nem contado por este
    toolkit (`parse_table` atravessa) -- o que quebra e a renderizacao e a
    leitura de qualquer consumidor que respeite o Markdown. O CRITICO fica
    reservado ao estado em que dado ja esta invisivel de fato, que e o do
    CHK-19. Buraco que contem HEADING nao entra (organizacao visual em
    subtitulo e legitima por D-12, e CHK-03 ja a relata como informativa)."""
    from todo_audit import Finding
    if ctx.text is None or not ctx.table:
        return []
    out = []
    for g in L.blank_gaps_in_table(ctx.text, table=ctx.table):
        n_brancas = len(g["blanks"])
        extra = (f" O buraco (linhas {g['start'] + 1}-{g['end'] + 1}) tem "
                 f"{len(g['prose'])} linha(s) de prosa junto." if g["prose"]
                 else "")
        out.append(Finding(
            check_id="CHK-20", severity="IMPORTANTE",
            message=(
                f"{n_brancas} linha(s) em branco DENTRO da tabela (a partir "
                f"da linha {g['line_no'] + 1}).{extra} Em Markdown a linha em "
                "branco ENCERRA a tabela: dali para baixo o arquivo ja "
                "renderiza como uma segunda tabela (ou prosa solta), embora "
                "este parser atravesse e continue lendo os itens -- e o "
                "caminho silencioso para uma tabela virar duas, e ai a "
                "leitura para no cabecalho repetido e itens somem sem erro na "
                "tela. Remova a(s) linha(s) em branco; organizar a tabela em "
                "subtitulos (com heading) continua legitimo (D-12)."),
            line_no=g["line_no"], fixable=False))
    return out


# ------------------------------- CHK-08 ------------------------------------

def _chk08_status_fora_do_vocabulario(ctx):
    from todo_audit import Finding
    table = ctx.table
    if not table:
        return []
    out = []
    for it in table["items"]:
        via = L.status_classification_via(it["status"])
        if via == "emoji":
            continue
        if via == "fallback":
            out.append(Finding(
                check_id="CHK-08", severity="COSMÉTICO",
                message=(
                    f"ID {it['id']!r}: status {it['status']!r} sem "
                    "emoji-prefixo (D-1), mas reconhecido por palavra do "
                    "vocabulario legado -- aviso brando, considere migrar "
                    "para o emoji correspondente."),
                line_no=it["line_no"], fixable=False))
        else:  # "unknown"
            out.append(Finding(
                check_id="CHK-08", severity="IMPORTANTE",
                message=(
                    f"ID {it['id']!r}: status {it['status']!r} nao "
                    "corresponde a nenhum dos 7 emojis canonicos nem ao "
                    "vocabulario legado por palavra -- emoji desconhecido "
                    "ou texto solto; corrija para um dos 7 status "
                    "canonicos."),
                line_no=it["line_no"], fixable=False))
    return out


# ------------------------------- CHK-11 ------------------------------------

_PIPE_NAO_ESCAPADO = re.compile(r"(?<!\\)\|")


def _contagem_independente(text):
    """Conta itens da tabela canonica por um caminho DIFERENTE do de
    `parse_table` -- nao chama `_cells`/`_is_header`/`_starts_foreign_table`
    nem a deteccao de tabela alheia por header+separador (D-12): so localiza
    o 1o cabecalho por uma checagem simples e literal (celula 'id' + alguma
    celula com 'status'), fixa o ncols DAQUELE cabecalho (tambem por uma
    contagem de celulas propria, sem reusar `_cells`), e daí conta toda
    linha subsequente que comeca com '|', nao e separador, tem o MESMO
    numero de celulas do cabecalho e 1a celula nao vazia -- ate um 2o
    cabecalho igual ou o fim do arquivo. A guarda de ncols aqui e
    deliberadamente mais BURRA que a do nucleo (nao reconhece tabela alheia
    por header+separador quando o ncols COINCIDE por acaso, D-12) -- e por
    isso que uma divergencia e informativa: sinaliza tanto regressao real
    quanto o caso limite em que uma tabela alheia de mesmo ncols existe (o
    proprio cenario que D-12 foi desenhado para tratar).

    Escape GFM `\\|` E' respeitado (via `_PIPE_NAO_ESCAPADO`, o MESMO padrao
    regex de `todo_lib._SEP`, mas reescrito aqui, sem importar/chamar a
    funcao do nucleo): pipe literal dentro de texto livre e uma regra
    ESTAVEL do formato, nao a logica sofisticada (deteccao de tabela alheia,
    2o cabecalho) que este contador deliberadamente NAO reproduz -- ignorar
    o escape faria QUALQUER linha com `\\|` na Descricao (comum: exemplo de
    comando shell, code span) contar celulas a mais e sumir da contagem
    independente por engano, gerando ruido em vez de sinal (medido contra a
    fixture real A do CONTR-1: sem isto, 6 itens legitimos com `\\|` na
    descricao desapareciam da contagem, falso-positivo de CHK-11). Deve
    divergir de `todo_health`/`parse_table` quando O CODIGO DELES tiver um
    bug -- reusar o mesmo caminho seria tautologico (CHK-CORE, TODO.md)."""
    lines = text.split("\n")
    ncols_esperado = None
    count = 0
    for line in lines:
        s = line.strip().lstrip("﻿")
        if not s.startswith("|"):
            continue
        parts = _PIPE_NAO_ESCAPADO.split(s.strip("|")) if s.strip("|") else [""]
        cells = [c.strip() for c in parts]
        low = [c.lower() for c in cells]
        is_hdr = "id" in low and any("status" in c for c in low)
        if ncols_esperado is None:
            if is_hdr:
                ncols_esperado = len(cells)
            continue
        if is_hdr:
            break
        if set("".join(cells)) <= set("-: "):
            continue  # linha separadora GFM
        if len(cells) != ncols_esperado:
            continue  # nem defeito nem item: celula a mais/menos (malformed
            # OU linha de uma tabela alheia de ncols diferente) -- nao e
            # ITEM da canonica de nenhuma forma, mesma semantica de
            # parse_table (malformed nunca vira item).
        if not cells[0]:
            continue
        count += 1
    return count


def _chk11_reconciliacao_contagem(ctx):
    from todo_audit import Finding
    if not ctx.table or not ctx.text:
        return []
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            health = H.run(root=ctx.root)
        except Exception:
            return []
    if health is None or health is H.ERRO_LEITURA or not isinstance(health, dict):
        return []
    reportado = health["itens"]
    independente = _contagem_independente(ctx.text)
    if reportado == independente:
        return []
    return [Finding(
        check_id="CHK-11", severity="CRÍTICO",
        message=(
            f"todo_health relata {reportado} item(ns); uma contagem "
            f"INDEPENDENTE (caminho de codigo diferente, sem reusar "
            f"parse_table) conta {independente} -- divergencia de "
            f"{abs(reportado - independente)}. Achado, nao ruido: e a "
            "classe de bug que ja fez o todo_health reportar 14 itens num "
            "arquivo de 215 sem avisar nada."),
        line_no=None, fixable=False)]
