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
    aprovar escopo --, logo nao e evidencia de entrega)."""
    for f in files:
        if os.path.basename(f) == "TODO.md":
            continue
        if f.startswith("inbox/") or "/inbox/" in f:
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


def _is_header(cells):
    low = [c.lower() for c in cells]
    return ("id" in low) and any("status" in c for c in low)


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


def is_pending(status):
    """⏳/🔄/🎨 = ainda nao concluido nem em verificacao. Usado em warnings/
    contagem (onde 'nao entregue' inclui 'pendente design')."""
    s = status.lower()
    if "verifica" in s:
        return False
    return ("pendente" in s) or ("andamento" in s)


def is_flip_eligible(status):
    """Elegivel a avancar para 🔍 num sync mecanico: SO ⏳ Pendente e
    🔄 Em andamento. Exclui 🎨 Pendente design (design nem existe), 🔍 (ja
    entregue), 🟡 Parcial, 💡, ✅ (ambiguos/ja resolvidos -> nao auto-flipar)."""
    s = status.lower()
    if "verifica" in s or "design" in s:
        return False
    return ("pendente" in s) or ("andamento" in s)


def is_awaiting_verification(status):
    return "verifica" in status.lower()


def is_done(status):
    return "conclu" in status.lower()


def cited_ids(message, ids):
    """IDs conhecidos citados na mensagem, com fronteira (V-1 nao casa em V-12,
    F1.4 nao casa em F1.45). re.escape protege ID com metachar. Funciona p/
    qualquer esquema de ID."""
    out = []
    for i in ids:
        if re.search(r"(?<![\w-])" + re.escape(i) + r"(?![\w.-])", message):
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
