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


def parse_table(text):
    """Retorna {'id_idx','status_idx','ncols','items':[{id,status,line_no}],
    'lines':[..]} ou None se nao houver tabela com colunas ID e Status.

    'lines' = text.split("\\n") (round-trip byte-exato com "\\n".join). So a 1a
    tabela e considerada (para no 2o cabecalho). Linhas cujo nº de celulas != nº
    de colunas do cabecalho sao IGNORADAS (defende escrita no lugar errado)."""
    lines = text.split("\n")
    id_idx = status_idx = ncols = None
    items = []
    for n, line in enumerate(lines):
        s = line.lstrip(BOM).strip()       # tolera BOM (so na 1a linha) e \r
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
        if _is_header(cells):              # 2a tabela: encerra a canonica
            break
        if len(cells) != ncols:            # linha malformada: ignora (seguro)
            continue
        iid = cells[id_idx]
        if not iid or iid in ("-", "—"):
            continue
        items.append({"id": iid, "status": cells[status_idx], "line_no": n})
    if id_idx is None:
        return None
    return {"id_idx": id_idx, "status_idx": status_idx, "ncols": ncols,
            "items": items, "lines": lines}


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
