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
                           text=True, timeout=15)
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


def is_pending(status):
    """⏳/🔄/🎨 = ainda nao concluido nem em verificacao. Usado em warnings/
    contagem (onde 'nao entregue' inclui 'pendente design')."""
    kind = _status_kind(status)
    if kind is not None:
        return kind in ("pendente", "andamento", "design")
    if _has_word(status, "verifica"):
        return False
    return _has_word(status, "pendente") or _has_word(status, "andamento")


def is_flip_eligible(status):
    """Elegivel a avancar para 🔍 num sync mecanico: SO ⏳ Pendente e
    🔄 Em andamento. Exclui 🎨 Pendente design (design nem existe), 🔍 (ja
    entregue), 🟡 Parcial, 💡, ✅ (ambiguos/ja resolvidos -> nao auto-flipar)."""
    kind = _status_kind(status)
    if kind is not None:
        return kind in ("pendente", "andamento")
    if _has_word(status, "verifica") or _has_word(status, "design"):
        return False
    return _has_word(status, "pendente") or _has_word(status, "andamento")


def is_awaiting_verification(status):
    kind = _status_kind(status)
    if kind is not None:
        return kind == "verificacao"
    return _has_word(status, "verifica")


def is_done(status):
    kind = _status_kind(status)
    if kind is not None:
        return kind == "done"
    return _has_word(status, "conclu")


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


def inbox_items(text):
    """Linhas da secao '## INBOX ...' (ate o proximo heading)."""
    out = []
    in_inbox = False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("#"):
            in_inbox = "inbox" in s.lower()
            continue
        if in_inbox and s.startswith("- "):
            out.append(s[2:].strip())
    return out
