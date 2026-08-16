#!/usr/bin/env python3
# tools/todo_lib.py -- parser/lib compartilhada do toolkit de frescor da TODO.md
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
tools/todo_lib.py

Lib compartilhada do toolkit de frescor da TODO.md (so stdlib, offline,
zero dependencia externa). Usada por todo_freshness.py (git hook), todo_sync.py
(--sync) e todo_health.py (--health).

Cross-platform e byte-preserving: usa split("\\n")/join("\\n") (NAO splitlines,
que quebraria em separadores Unicode) e set_status_cell preserva o terminador
(CRLF/LF) e tolera BOM. Parser robusto a tabelas de 8 ou 9 colunas: localiza ID
e Status pelo NOME no cabecalho, divide a linha so nos pipes NAO escapados (no
GFM "\\|" e pipe literal da celula, nao separador -- vale dentro de code span),
exige que a linha tenha o MESMO nº de colunas do cabecalho (rejeita linha
malformada em vez de escrever no lugar errado), e para no 2º cabecalho (tabela
unica canonica).

Vocabulario de status da skill tab_pendencias:
  ✅ Concluído | 🔄 Em andamento | 🟡 Parcial | ⏳ Pendente | 💡 Decisão tomada
  | 🎨 Pendente design | 🔍 Pendente verificação
"""
import os
import re
import subprocess

BOM = "﻿"


def git(args, cwd=None):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=15)
    except Exception:
        return ""
    return r.stdout if r.returncode == 0 else ""


def repo_root(cwd=None):
    return (git(["rev-parse", "--show-toplevel"], cwd).strip() or None)


def git_dir(root):
    gd = git(["rev-parse", "--git-dir"], cwd=root).strip()
    if not gd:
        return None
    return gd if os.path.isabs(gd) else os.path.join(root, gd)


def touched_code(files):
    """Tocou trabalho substantivo (algo alem de bookkeeping da tabela/INBOX)?

    Mora aqui porque DOIS consumidores dependem dela: o todo_freshness.py
    (avisa quando codigo muda sem citar ID) e o todo_sync.py (commit que so
    mexe na tabela CITA o ID sem ter entregado nada -- criar item, reordenar,
    aprovar escopo --, logo nao e evidencia de entrega).

    So o `inbox/` do TOPO do repo e bookkeeping (INBOX da TODO.md, D-6). Um
    diretorio de CODIGO chamado `inbox` em qualquer nivel (ex.:
    `src/inbox/parser.py`) e trabalho substantivo -- TCH-1 corrigido: a
    checagem antiga (`"/inbox/" in f`) casava esse caso por substring de
    path e nunca flipava o ID citado. Caminho vem do git (diff/status), que
    sempre usa "/" independente de SO -- ADR-0001 (e).1."""
    for f in files:
        if os.path.basename(f) == "TODO.md":
            continue
        if f.startswith("inbox/"):
            continue
        return True
    return False


def find_todo(root):
    p = os.path.join(root, "TODO.md")
    return p if os.path.isfile(p) else None


# Separador de celula = pipe NAO escapado. No GFM, "\|" dentro de uma celula e
# um pipe literal (vale inclusive dentro de code span: `a \| b`), nao um
# separador -- um split("|") cru contaria celula demais e a guarda de ncols
# descartaria a linha inteira, em silencio.
_SEP = re.compile(r"(?<!\\)\|")


def _split_row(s):
    """Pedacos crus da linha, divididos so nos pipes NAO escapados.

    Round-trip byte-exato com "|".join (os "\\|" ficam intactos dentro dos
    pedacos). Numa linha de tabela bem formada ("| a | b |") o pedaco 0 e a
    borda vazia da esquerda -- por isso a celula de dados k mora em [1 + k],
    contrato que _cells e set_status_cell compartilham."""
    return _SEP.split(s)


def _cells(s):
    parts = _split_row(s.strip())
    if parts and parts[0].strip() == "":       # borda vazia da esquerda
        parts = parts[1:]
    if parts and parts[-1].strip() == "":      # borda vazia da direita
        parts = parts[:-1]
    return [c.strip() for c in parts]


def _is_separator(cells):
    return bool(cells) and set("".join(cells)) <= set("-: ")


_STATUS_WORD = re.compile(r"(?<![\w-])status\b")


def _is_header(cells):
    """Cabecalho canonico: celula exata "id" + alguma celula com a palavra
    "status" (nao substring crua). HDR-1: uma celula que so CONTEM "status"
    grudado por hifen ou underscore (ex.: "Sub-status" de tabela alheia) nao
    conta -- o lookbehind negativo exige que "status" comece em fronteira de
    palavra de verdade (inicio da celula, espaco ou pontuacao como "(", nunca
    "-"/"_"/letra colada), preservando "Status" e "Estado Auditado (Status)"."""
    low = [c.lower() for c in cells]
    return ("id" in low) and any(_STATUS_WORD.search(c) for c in low)


def _starts_foreign_table(lines, n, row_ncols):
    """SPRAWL-1/D-12: a linha `n` (que ja sabemos NAO ser separador nem
    cabecalho ID+Status) comeca uma tabela de OUTRO schema quando a linha
    SEGUINTE e um separador GFM valido (":-"/"-"/" ") com o MESMO numero de
    celulas dela -- esse e o padrao estrutural cabecalho+separador de
    qualquer tabela Markdown, e so ele (nunca so a contagem de colunas
    bater, o que aconteceria toda vez que uma linha de DADO da propria
    canonica for lida) distingue "comeco de tabela alheia" de "mais uma
    linha de dado da tabela em curso"."""
    if n + 1 >= len(lines):
        return False
    nxt = lines[n + 1].lstrip(BOM).strip()
    if not nxt.startswith("|"):
        return False
    sep_cells = _cells(nxt)
    return _is_separator(sep_cells) and len(sep_cells) == row_ncols


def parse_table(text):
    """Retorna {'id_idx','status_idx','ncols','items':[{id,status,line_no}],
    'lines':[..],'duplicate_ids':{id:[{line_no,status},...]},
    'headings_crossed':[{line_no,text},...],
    'malformed':[{line_no,raw,expected_ncols,got_ncols},...]} ou None se nao
    houver tabela com colunas ID e Status.

    'lines' = text.split("\\n") (round-trip byte-exato com "\\n".join). So a 1a
    tabela e considerada. Linhas cujo nº de celulas != nº de colunas do
    cabecalho sao IGNORADAS -- defende escrita no lugar errado, mas deixam
    rastro ADITIVO em 'malformed' (ADR-0001 b.5): nenhum consumidor que so
    le id_idx/status_idx/ncols/items/lines muda de comportamento; e
    --audit/CHK-02 que consome 'malformed' para diagnosticar a causa
    provavel (pipe cru? celula faltando? fragmento truncado?).

    SPRAWL-1, revisado por D-12 (decisoes_lider.md, 2026-07-28): a D-6
    original ("encerra no PROXIMO heading markdown, qualquer nivel")
    destruia 201 dos 215 itens de um consumidor real que organiza a MESMA
    tabela canonica sob ~20 subtitulos de organizacao visual -- recriando o
    incidente fundador do projeto por outro caminho. A regra correta: um
    heading NUNCA encerra a tabela por si so (por isso so e registrado em
    'headings_crossed', para o futuro --audit/CHK-03 relatar o span mesmo
    quando o parser decide atravessar); quem encerra e a ESTRUTURA que
    aparece em qualquer ponto da varredura: (i) uma 2a linha de cabecalho
    ID+Status (comportamento pre-existente, mantido), ou (ii) o comeco de
    uma tabela de OUTRO schema -- via `_starts_foreign_table` -- mesmo
    quando o nº de colunas dela COINCIDE por acaso com o da canonica (o
    SPRAWL-1 original de verdade: uma tabela alheia contada como itens
    fantasmas so porque o nº de celulas batia). Uma tabela alheia com nº de
    colunas DIFERENTE nunca precisou de deteccao especial: suas linhas ja
    sao ignoradas pela guarda de ncols de sempre, sem encerrar nada -- e
    isso e o que permite atravessar secoes inteiras de organizacao visual
    (consumidor B) sem reabrir a porta do bug.

    BUG-1': ID duplicado NAO trava o nucleo (ADR-0001 b.5, mesma politica do
    'malformed' -- descarte/ambiguidade nunca e fatal aqui). 'items' preserva
    TODAS as ocorrencias, sem filtrar nem decidir qual "vence" -- quem decide
    e o consumidor (`parse_status_map` mantem o comportamento pre-existente
    de ultima linha vence) ou o `--audit`/CHK-01 (via a chave aditiva
    'duplicate_ids', so com os IDs que aparecem 2+ vezes -- vazio quando nao
    ha duplicata). Chave ADITIVA: nenhum consumidor que so le
    id_idx/status_idx/ncols/items/lines muda de comportamento."""
    lines = text.split("\n")
    id_idx = status_idx = ncols = None
    items = []
    headings_crossed = []
    malformed = []
    for n, line in enumerate(lines):
        s = line.lstrip(BOM).strip()       # tolera BOM (so na 1a linha) e \r
        if id_idx is not None and s.startswith("#"):
            headings_crossed.append({"line_no": n, "text": s})
            continue
        if not s.startswith("|"):
            continue
        cells = _cells(s)
        if id_idx is None:
            if _is_header(cells):
                id_idx = next(i for i, c in enumerate(cells)
                              if c.lower() == "id")
                status_idx = next(i for i, c in enumerate(cells)
                                  if "status" in c.lower())
                ncols = len(cells)
            continue
        if _is_separator(cells):
            continue
        if _is_header(cells):              # 2a tabela ID+Status: encerra
            break
        if len(cells) == ncols and _starts_foreign_table(lines, n, len(cells)):
            break                           # D-12: tabela alheia, ncols colide
        if len(cells) != ncols:            # linha malformada: ignora (seguro),
            # mas ADR-0001 (b).5 exige rastro -- chave ADITIVA 'malformed'
            # (nenhum consumidor que so le id_idx/status_idx/ncols/items/
            # lines muda de comportamento; --audit/CHK-02 e quem consome
            # isto para diagnosticar a causa provavel).
            malformed.append({"line_no": n, "raw": line,
                              "expected_ncols": ncols, "got_ncols": len(cells)})
            continue
        iid = cells[id_idx]
        if not iid or iid in ("-", "—"):
            continue
        items.append({"id": iid, "status": cells[status_idx], "line_no": n})
    if id_idx is None:
        return None
    occurrences_by_id = {}
    for it in items:
        occurrences_by_id.setdefault(it["id"], []).append(
            {"line_no": it["line_no"], "status": it["status"]})
    duplicate_ids = {iid: occs for iid, occs in occurrences_by_id.items()
                      if len(occs) > 1}
    return {"id_idx": id_idx, "status_idx": status_idx, "ncols": ncols,
            "headings_crossed": headings_crossed, "malformed": malformed,
            "items": items, "lines": lines, "duplicate_ids": duplicate_ids}


def parse_status_map(text):
    """{id: status_text} (conveniencia p/ o git hook)."""
    tbl = parse_table(text)
    return {it["id"]: it["status"] for it in tbl["items"]} if tbl else {}


# Vocabulario de status (D-1, decisoes_lider.md): a celula pertence a
# exatamente um dos 7 kinds abaixo, decidido pelo PRIMEIRO caractere
# nao-espaco da celula (o emoji-prefixo) -- nunca por procura de substring no
# texto livre que vem depois do emoji (esse texto e do usuario: pode conter
# "verificar", "pendente", "concluido" como parte de qualquer frase, sem que
# isso mude a classificacao). Corrige a classe de bug BUG-5/SUB-1/SUB-2:
# "✅ Concluído ... VERIFICADO ..." classificado como preso em verificacao,
# "🔴 Bloqueado (dependente de X)" classificado como pendente (substring de
# "pendente" dentro de "dependente"), e "⏳ Pendente (verificar
# disponibilidade)" barrado de um flip legitimo (substring de "verifica").
_EMOJI_KIND = {
    "✅": "done",
    "🔄": "andamento",
    "🟡": "parcial",
    "⏳": "pendente",
    "💡": "decisao",
    "🎨": "design",
    "🔍": "verificacao",
}


def _status_kind(status):
    """Kind do vocabulario fechado (D-1) pelo emoji-prefixo, ou None quando a
    celula nao comeca com nenhum dos 7 -- o UNICO caso em que os predicados
    abaixo caem no fallback substring/word-boundary (ADR-0001 secao (d)):
    tabela legada sem emoji, ou emoji fora do vocabulario controlado (ex.:
    🔴 de um esquema proprio do usuario, tratado como 'sem emoji
    reconhecido', nao como um 8o kind)."""
    s = status.lstrip(BOM).strip()
    for emoji, kind in _EMOJI_KIND.items():
        if s.startswith(emoji):
            return kind
    return None


def _has_word(text, word):
    """Substring com fronteira de palavra (\\b) na frente, nunca substring
    crua -- e o que faz 'pendente' NAO casar dentro de 'dependente' e
    'conclu' NAO casar dentro de 'inconclusivo'. So fronteira de palavra na
    FRENTE (nao atras): o vocabulario e um radical pt-br que aceita flexao
    (Concluído/concluida, verificação/verificar), so a palavra anterior
    grudada e que e o falso-positivo. Opera sobre o vocabulario fechado de
    status (ADR-0001 (d): esta celula NAO e conteudo livre do usuario)."""
    return re.search(r"\b" + word, text.lower()) is not None


def status_classification_via(status):
    """Como a celula foi classificada -- gancho informativo para o futuro
    `--audit`/CHK-08 (AUDIT-ENG, ainda nao implementado) reportar tabela
    legada sem emoji, sem duplicar a deteccao aqui: "emoji" (contrato D-1, o
    caminho correto), "fallback" (sem nenhum dos 7 emojis, mas o vocabulario
    de texto puro foi reconhecido por word-boundary) ou "unknown" (nem
    emoji nem fallback reconheceram -- candidato a achado de CHK-08, "status
    fora do vocabulario"). Nenhum predicado abaixo (is_pending/is_done/...)
    consulta esta funcao para decidir; ela existe so para relato."""
    if _status_kind(status) is not None:
        return "emoji"
    if any(_has_word(status, w) for w in
           ("pendente", "andamento", "conclu", "verifica", "design")):
        return "fallback"
    return "unknown"


# PRED-FALLBACK (2026-07-29, prompt_fallback_legado.md): compostos que sao
# status CANONICOS de duas palavras, nao "pendente" com anotacao livre --
# tem de vencer independente da posicao, senao 'Pendente design' venceria
# por 'pendente'@0 e viraria flipavel, ressuscitando o caso grave do BUG-5
# dentro do proprio fallback que o corrigiu.
#
# GEMEO-DESIGN (2026-08-16): a 1a versao deste composto so casava a forma
# adjacente exata "pendente\s+design" (radical fixo "pendente", separador
# so espaco) -- hifen ("Pendente-design"), palavra intercalada ("Pendente
# depois design") e o radical "andamento" ("andamento design") escapavam em
# silencio e voltavam a ser flip-eligible. D-1 nao fala de FORMA, fala de
# CATEGORIA: qualquer celula legada que junte um radical (pendente/
# andamento) com o qualificador "design" descreve o composto "🎨 Pendente
# design", nao "pendente" com anotacao -- por isso a deteccao e por
# CO-OCORRENCIA (radical E qualificador em qualquer posicao/ordem/
# separador), nao por adjacencia regex.
#
# "verifica" preserva a exclusao do infinitivo "verificar" (verbo em nota
# livre -- 'Pendente (verificar disponibilidade)' e 'Em andamento (verificar
# com o time)' continuam SEM ser o composto, caindo na regra de posicao
# abaixo, como os 2 testes W15 exigem): o lookahead nega especificamente
# "r" + fronteira de palavra (o infinitivo), preservando
# "verificação"/"verificado"/"verifica" (substantivo/participio -- o status
# composto de fato).
_LEGACY_RADICAL = re.compile(r"\b(?:pendente|andamento)\b")
_LEGACY_QUALIFIER = (
    (re.compile(r"\bverifica(?!r\b)"), "verificacao"),
    (re.compile(r"\bdesign\b"), "design"),
)

# Vocabulario simples do fallback e o kind que cada radical decide quando
# vence por posicao (mesmos 7 kinds de _EMOJI_KIND, exceto parcial/decisao,
# que nao tem forma textual pura reconhecida historicamente pelo fallback).
_LEGACY_WORD_KIND = (
    ("pendente", "pendente"),
    ("andamento", "andamento"),
    ("conclu", "done"),
    ("verifica", "verificacao"),
    ("design", "design"),
)


def _classify_legacy(status):
    """Fallback de tabela legada sem emoji (ADR-0001 secao (d)): decide UMA
    UNICA categoria por celula, nunca duas -- e o que torna is_done() e
    is_awaiting_verification() mutuamente exclusivos POR CONSTRUCAO (a
    incoerencia medida em 'Concluído e verificado', que saia com os dois em
    True no fallback antigo por-predicado). Precedencia por POSICAO: entre
    as ocorrencias do vocabulario canonico com \\b na frente, a de MENOR
    indice na celula decide (empate nao existe, posicoes sao distintas) --
    o mesmo principio que a camada de emoji ja usa (o emoji ABRE a celula,
    o resto e anotacao).

    Compostos sao decididos ANTES da regra de posicao, por CO-OCORRENCIA
    (ver _LEGACY_RADICAL/_LEGACY_QUALIFIER, GEMEO-DESIGN): so disparam
    quando um radical (pendente/andamento) E um qualificador (design/
    verifica-nao-infinitivo) aparecem os DOIS na celula, em qualquer
    posicao/ordem/separador -- 'Concluído e verificado' nao tem radical
    (so 'conclu'), entao nunca entra aqui, e 'conclu'@0 continua vencendo
    por posicao abaixo, como o teste W15 exige. Devolve a mesma categoria
    de _status_kind, ou None quando nenhum vocabulo do fallback foi
    reconhecido."""
    s = status.lower()
    if _LEGACY_RADICAL.search(s):
        for pattern, kind in _LEGACY_QUALIFIER:
            if pattern.search(s):
                return kind
    best_pos, best_kind = None, None
    for word, kind in _LEGACY_WORD_KIND:
        m = re.search(r"\b" + word, s)
        if m is not None and (best_pos is None or m.start() < best_pos):
            best_pos, best_kind = m.start(), kind
    return best_kind


def is_pending(status):
    """⏳/🔄/🎨 = ainda nao concluido nem em verificacao. Usado em warnings/
    contagem (onde 'nao entregue' inclui 'pendente design')."""
    kind = _status_kind(status)
    if kind is None:
        kind = _classify_legacy(status)
    return kind in ("pendente", "andamento", "design")


def is_flip_eligible(status):
    """Elegivel a avancar para 🔍 num sync mecanico: SO ⏳ Pendente e
    🔄 Em andamento. Exclui 🎨 Pendente design (design nem existe), 🔍 (ja
    entregue), 🟡 Parcial, 💡, ✅ (ambiguos/ja resolvidos -> nao auto-flipar)."""
    kind = _status_kind(status)
    if kind is None:
        kind = _classify_legacy(status)
    return kind in ("pendente", "andamento")


def is_awaiting_verification(status):
    kind = _status_kind(status)
    if kind is None:
        kind = _classify_legacy(status)
    return kind == "verificacao"


def is_done(status):
    kind = _status_kind(status)
    if kind is None:
        kind = _classify_legacy(status)
    return kind == "done"


def cited_ids(message, ids):
    """IDs conhecidos citados na mensagem, com fronteira (V-1 nao casa em V-12,
    F1.4 nao casa em F1.45). re.escape protege ID com metachar. Funciona p/
    qualquer esquema de ID.

    CIT-1: o lookahead proibia QUALQUER "." logo apos o ID, inclusive o ponto
    final de frase ("fechei V-12." nunca casava) -- uso comum em prosa de
    commit. O "." so precisa continuar proibido quando e continuacao
    NUMERICA do proprio ID (ex.: "F1.4.5" nao pode confirmar "F1.4", pois
    seria citar um ID mais especifico); ponto seguido de nao-digito (fim de
    frase, ou nada) e permitido."""
    out = []
    for i in ids:
        pat = r"(?<![\w-])" + re.escape(i) + r"(?![\w-])(?!\.\d)"
        if re.search(pat, message):
            out.append(i)
    return out


def set_status_cell(line, status_idx, new_status):
    """Substitui SO a celula de Status, preservando o resto da linha E o
    terminador original (CRLF/LF/none). Re-padroniza a propria celula-alvo para
    1 espaco de cada lado."""
    stripped = line.rstrip("\r\n")
    tail = line[len(stripped):]            # "\r\n", "\n", "\r" ou ""
    parts = _split_row(stripped)           # linha comeca com '|' -> parts[0]==''
    target = 1 + status_idx                # celula de dados k <-> parts[1+k]
    if target >= len(parts):
        return line                        # estrutura inesperada: nao mexe
    parts[target] = f" {new_status} "
    return "|".join(parts) + tail


# HEADING-1 (ADR-0002, defeito medido no nucleo): a deteccao de secao da
# INBOX de planejamento exigia so `"inbox" in s.lower()` -- substring, em
# qualquer caixa, em qualquer heading. Isso engolia headings ALHEIOS que
# so contem a palavra comum "inbox" em prosa, como um heading de bus/
# mensageria ("## Inbox do bus (mensagens recebidas)", TAB-BUS-003:
# transporte de mensagens, NAO e a exception queue de planejamento). A
# palavra em si nao basta como sinal: "Inbox do bus" tambem comeca com a
# palavra "inbox" (case-insensitive), entao nem "\\bpalavra\\b" resolveria.
# O que distingue e a CAIXA: o contrato normativo
# (references/frescor-da-tabela.md SS5) usa literalmente o token "INBOX"
# em MAIUSCULA -- mesmo principio de "ID"/"Status" como tokens de
# cabecalho de tabela que nunca sao traduzidos (ADR-0001 secao d), so que
# aqui a caixa exata (nao so a palavra) e o sinal estrutural que separa o
# identificador de contrato do substantivo comum de prosa.
_INBOX_HEADING = re.compile(r"(?<![\w-])INBOX(?![\w-])")


def _is_inbox_heading(s):
    """Heading e a INBOX de planejamento (ADR-0002 secao f)? Exige o token
    'INBOX' maiusculo exato, como palavra isolada -- nunca substring solta
    'em qualquer caixa' (ver HEADING-1 acima)."""
    return bool(_INBOX_HEADING.search(s))


def inbox_items(text):
    """Linhas da secao '## INBOX ...' (ate o proximo heading). Ver
    HEADING-1: a deteccao de secao usa _is_inbox_heading, nao mais
    substring case-insensitive."""
    out = []
    in_inbox = False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            in_inbox = _is_inbox_heading(s)
            continue
        if in_inbox and s.startswith("- "):
            out.append(s[2:].strip())
    return out


# ADR-0002 secao (f): vocabulario fechado de motivos residuais e origens
# permitidas no metadado do item residual da INBOX.
TRIAGE_REASONS = frozenset({
    "missing-info", "conflicting-evidence", "dependency-conflict",
    "needs-leader-decision", "ownership-unavailable", "blocked-external",
})
TRIAGE_SOURCES = frozenset({"user", "bus", "agent", "audit", "test"})
_TRIAGE_KNOWN_KEYS = frozenset({"since", "reason", "source", "cycles", "ref"})
_TRIAGE_REQUIRED_KEYS = frozenset({"since", "reason"})

# Gramatica literal do ADR-0002 (f): "[triage" + 1+ pares " chave=valor" +
# "] " + descricao livre remanescente. Chaves em [a-z_], valores sao tokens
# sem espaco nem "]" (parseaveis por regex simples, sem YAML).
_TRIAGE_BLOCK = re.compile(
    r"^\[triage((?: [a-z_]+=[A-Za-z0-9._:\-]+)+)\] (.*)$", re.DOTALL)
_TRIAGE_PAIR = re.compile(r" ([a-z_]+)=([A-Za-z0-9._:\-]+)")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def format_triage_metadata(since, reason, source=None, cycles=None, ref=None):
    """Serializa o bloco '[triage ...] ' (ADR-0002 secao f) para prefixar a
    descricao livre de um item residual da INBOX -- ex.:
    `format_triage_metadata(since="2026-08-16", reason="needs-leader-decision")
    + "decisao pendente do lider"`. Nao valida os valores (quem chama e
    responsavel por 'reason' em TRIAGE_REASONS e 'since' em ISO
    'YYYY-MM-DD'); parse_triage_metadata sobre o resultado e a prova de
    round-trip (formatar -> analisar -> mesmos campos)."""
    pairs = [f"since={since}", f"reason={reason}"]
    if source is not None:
        pairs.append(f"source={source}")
    if cycles is not None:
        pairs.append(f"cycles={cycles}")
    if ref is not None:
        pairs.append(f"ref={ref}")
    return "[triage " + " ".join(pairs) + "] "


def parse_triage_metadata(description):
    """Analisa o prefixo '[triage ...] ' de uma descricao de item da INBOX
    (ADR-0002 secao f). Devolve dict:
      present      bloco '[triage ...]' detectado no INICIO da descricao?
      valid        bloco presente E sem nenhum erro (ver 'errors')?
      fields       {chave: valor} bruto (str), {} quando ausente
      errors       lista de motivos de invalidade (vazia quando valid)
      description  texto livre remanescente (a descricao inteira quando
                   'present' e False)

    'valid' e SEMPRE False quando 'present' e False -- e o mecanismo
    central do ADR: ausencia de token de triagem valido = classificavel
    por definicao (secao f), nunca uma lista de motivos INVALIDOS a
    policiar -- a unica lista fechada e a de motivos VALIDOS
    (TRIAGE_REASONS). Metadado malformado (chave desconhecida, reason fora
    do vocabulario, since fora do formato ISO, cycles nao inteiro, source
    fora do vocabulario) tambem nunca e descartado em silencio: 'present'
    continua True e 'errors' relata a causa (para o futuro --audit)."""
    m = _TRIAGE_BLOCK.match(description)
    if not m:
        return {"present": False, "valid": False, "fields": {},
                "errors": [], "description": description}
    fields = {}
    errors = []
    for k, v in _TRIAGE_PAIR.findall(m.group(1)):
        if k in fields:
            errors.append(f"chave repetida: {k!r}")
            continue
        fields[k] = v
    for k in fields:
        if k not in _TRIAGE_KNOWN_KEYS:
            errors.append(f"chave desconhecida: {k!r}")
    for k in sorted(_TRIAGE_REQUIRED_KEYS - fields.keys()):
        errors.append(f"chave obrigatoria ausente: {k!r}")
    if "since" in fields and not _ISO_DATE.match(fields["since"]):
        errors.append(f"since fora do formato ISO YYYY-MM-DD: {fields['since']!r}")
    if "reason" in fields and fields["reason"] not in TRIAGE_REASONS:
        errors.append(f"reason fora do vocabulario fechado: {fields['reason']!r}")
    if "source" in fields and fields["source"] not in TRIAGE_SOURCES:
        errors.append(f"source fora do vocabulario fechado: {fields['source']!r}")
    if "cycles" in fields and not fields["cycles"].isdigit():
        errors.append(f"cycles nao e inteiro >= 0: {fields['cycles']!r}")
    return {"present": True, "valid": not errors, "fields": fields,
            "errors": errors, "description": m.group(2)}


def inbox_entries(text):
    """inbox_items() decomposto (ADR-0002 secao f): cada entrada ganha o
    ID tentativo, a descricao livre e a classificacao de triagem. Formato
    de linha esperado (compat com o legado, references/frescor-da-tabela.md
    SS5): '<ID-ou-travessao>: descricao livre [com ou sem [triage ...]]'.

    Cada item do retorno:
      raw           texto integral da linha (== o que inbox_items ja
                    devolve, preservado 1:1 para round-trip/compat)
      id            parte antes do 1o ':' (None se a linha nao tem ':' --
                    formato ainda mais degradado que o legado sem
                    metadado, ja classificavel por definicao)
      description   parte livre apos o ':' (com ou sem bloco '[triage]';
                    == 'raw' quando nao ha ':')
      triage        dict de parse_triage_metadata sobre 'description'
      classifiable  True quando NAO ha bloco '[triage ...]' VALIDO -- o
                    mecanismo central do ADR-0002 (f): falta de token
                    valido drena no proximo intake, por definicao, nunca
                    por uma lista de motivos proibidos a policiar."""
    out = []
    for raw in inbox_items(text):
        head, sep, rest = raw.partition(":")
        if sep:
            iid, desc = head.strip(), rest.strip()
        else:
            iid, desc = None, raw
        triage = parse_triage_metadata(desc)
        out.append({"raw": raw, "id": iid, "description": desc,
                    "triage": triage, "classifiable": not triage["valid"]})
    return out
