# tools/checks/chk_projeto.py -- CHK-21: checklist paralelo fora do TODO.md
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
tools/checks/chk_projeto.py

CHK-21 (UNIQ-2): **uma tabela de checklist por PROJETO**, e ela vive no
`TODO.md`. Ordem do lider (2026-08-20): "so deve haver uma tabela checklist por
projeto". Enquanto CHK-19 olha para DENTRO do arquivo auditado, este olha para
o resto do projeto atras de fila de trabalho paralela.

Tres decisoes de desenho, todas com o mesmo motivo -- **falso positivo aqui e
caro**: um achado sobre o indice de ADR de um projeto vira ruido, e ruido faz o
usuario ignorar o audit inteiro.

  (a) DISCRIMINANTE ESTREITO (`todo_lib.checklist_tables`): a tabela so conta
      como checklist se tiver coluna de identificador, coluna Status E pelo
      menos uma linha cujo Status comeca com um dos 7 emojis do vocabulario
      fechado (D-1). Tabela de ADR com `Status = Aceito`, matriz de rotas e
      contagem de auditoria NAO casam. Limitacao declarada: checklist paralelo
      escrito sem emoji nao e detectado (falso negativo deliberado).
  (b) VARREDURA BARATA E DECLARADA: so arquivos `.md`, preferindo
      `git ls-files` (respeita `.gitignore` de graca e nao entra em
      `node_modules`/`build`); sem git, `os.walk` com lista de diretorios
      pulados. Tetos de arquivos e de tamanho, e o teto que for ATINGIDO e
      declarado como achado COSMETICO (no silent caps: "varri menos do que o
      projeto tem" nunca fica implicito).
  (c) DESLIGAVEL por `.tab_pendencias.ini` (`[audit] checklist_scan = off`) e
      com exclusoes extras por `checklist_exclude` -- projeto que mantem
      exemplos didaticos em `docs/` nao precisa conviver com achado eterno.

Severidade IMPORTANTE, nao CRITICO: um checklist paralelo divide a fonte da
verdade (o defeito real), mas NAO torna invisivel nenhum item do `TODO.md`
auditado -- CRITICO, nesta suite, e reservado a dado que sumiu de fato.
"""
from __future__ import annotations

import fnmatch
import os

import todo_lib as L

_CFG_SECTION = "audit"
MAX_ARQUIVOS = 400          # teto de arquivos lidos (declarado quando atingido)
MAX_BYTES = 1_000_000       # teto por arquivo (declarado quando atingido)

# Diretorios que nunca sao fila de trabalho de projeto: dependencia de
# terceiro, artefato de build, material de teste/exemplo (fixture com tabela
# canonica e o caso mais provavel de falso positivo).
_DIRS_PULADOS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "vendor", "third_party",
    "site-packages", "__pycache__", ".venv", "venv", "env", "build", "dist",
    "target", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "tests", "test", "fixtures", "corpus", "templates", "examples",
})


def _cfg(cfg, key, default=""):
    if cfg is None:
        return default
    try:
        return cfg.get(_CFG_SECTION, key, fallback=default)
    except Exception:
        return default


def _exclusoes_extra(cfg):
    bruto = _cfg(cfg, "checklist_exclude", "")
    return [g.strip() for g in bruto.replace("\n", ",").split(",") if g.strip()]


def _rel(root, caminho):
    try:
        return os.path.relpath(caminho, root).replace(os.sep, "/")
    except ValueError:                      # drives diferentes no Windows
        return caminho.replace(os.sep, "/")


def _via_git(root):
    """Arquivos .md rastreados, ou None quando nao ha git utilizavel.

    `git ls-files` da de graca o que seria caro reimplementar: respeita
    `.gitignore`, ignora submodulo e nao entra em diretorio de dependencia."""
    if not L.git_dir(root):
        return None
    saida = L.git(["ls-files", "-z", "--", "*.md", "*.MD"], cwd=root)
    if not saida:
        return None
    return [os.path.join(root, p.replace("/", os.sep))
            for p in saida.split("\0") if p.strip()]


def _via_walk(root):
    achados = []
    for base, dirs, arquivos in os.walk(root):
        dirs[:] = [d for d in dirs
                   if d not in _DIRS_PULADOS and not d.startswith(".")]
        for nome in arquivos:
            if nome.lower().endswith(".md"):
                achados.append(os.path.join(base, nome))
    return achados


def _candidatos(root, cfg):
    """(caminhos, origem, truncado_em) -- ja filtrados e ordenados."""
    arquivos = _via_git(root)
    origem = "git ls-files"
    if arquivos is None:
        arquivos = _via_walk(root)
        origem = "varredura de diretorio (sem git resolvivel)"
    extras = _exclusoes_extra(cfg)
    filtrados = []
    for caminho in sorted(set(arquivos)):
        rel = _rel(root, caminho)
        partes = set(rel.split("/")[:-1])
        if partes & _DIRS_PULADOS:
            continue
        if any(fnmatch.fnmatch(rel, g) for g in extras):
            continue
        filtrados.append(caminho)
    truncado = len(filtrados) > MAX_ARQUIVOS
    return filtrados[:MAX_ARQUIVOS], origem, truncado


def chk21(ctx):
    """CHK-21: tabela de checklist FORA do TODO.md, no mesmo projeto."""
    from todo_audit import Finding
    if _cfg(ctx.config, "checklist_scan", "on").strip().lower() in (
            "off", "false", "0", "no"):
        return []
    root = ctx.root
    if not root or not os.path.isdir(root):
        return []
    alvo = os.path.abspath(ctx.todo_path) if ctx.todo_path else None
    arquivos, origem, truncado = _candidatos(root, ctx.config)

    out = []
    grandes = []
    for caminho in arquivos:
        if alvo and os.path.abspath(caminho) == alvo:
            continue
        try:
            if os.path.getsize(caminho) > MAX_BYTES:
                grandes.append(_rel(root, caminho))
                continue
            with open(caminho, encoding="utf-8", newline="",
                      errors="replace") as fh:
                texto = fh.read()
        except OSError:
            continue                     # arquivo sumiu/sem permissao: segue
        for tab in L.checklist_tables(texto):
            out.append(Finding(
                check_id="CHK-21", severity="IMPORTANTE",
                message=(
                    f"Tabela de checklist FORA do TODO.md: "
                    f"{_rel(root, caminho)}, linha {tab['line_no'] + 1} "
                    f"({tab['n_rows']} linha(s) de dado, "
                    f"{tab['n_status_canonicos']} com status do vocabulario "
                    "desta skill). O projeto tem UMA tabela de pendencias e "
                    "ela vive no TODO.md: checklist paralelo divide a fonte "
                    "da verdade (dois lugares para marcar a mesma coisa, e "
                    "nenhum dos dois confiavel). Funda os itens na tabela do "
                    "TODO.md e deixe no lugar antigo, se precisar, so um "
                    "ponteiro em prosa. Documentacao de produto com coluna "
                    "Status (indice de ADR, matriz, contagem) NAO cai aqui: "
                    "so casa tabela com ID + Status + status do vocabulario "
                    "fechado."),
                line_no=None, fixable=False))
    if truncado or grandes:
        detalhe = []
        if truncado:
            detalhe.append(f"varredura limitada aos {MAX_ARQUIVOS} primeiros "
                           "arquivos .md (em ordem alfabetica)")
        if grandes:
            detalhe.append(f"{len(grandes)} arquivo(s) acima de "
                           f"{MAX_BYTES} bytes nao lido(s): "
                           f"{', '.join(grandes[:3])}")
        out.append(Finding(
            check_id="CHK-21", severity="COSMÉTICO",
            message=("Escopo da varredura (no silent caps) -- origem da "
                     f"lista: {origem}; " + "; ".join(detalhe) +
                     ". Pode haver checklist paralelo fora do que foi lido."),
            line_no=None, fixable=False))
    return out
