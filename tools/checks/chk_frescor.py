# tools/checks/chk_frescor.py -- CHK-09 (claims obsoletas) e CHK-10 (proposta do sync)
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
tools/checks/chk_frescor.py

Dois checks do catalogo (W7, TODO.md) que confrontam a tabela com a
REALIDADE do git -- os dois pontos onde uma `TODO.md` pode "mentir com ar
de verdade" mesmo com a estrutura (ID/Status/grafo) perfeita:

  CHK-09 -- claims obsoletas na Descrição ("não pushado", "commit local",
            "branch X"...) verificadas contra o git real (`git ls-remote`,
            `git cat-file -e`, `git diff <main> --`). Severidade default
            IMPORTANTE, mas cada achado tem severidade PRÓPRIA: IMPORTANTE
            quando a evidência aponta a claim como possivelmente obsoleta,
            COSMÉTICO quando não foi possível confirmar NEM refutar (no
            silent caps -- declarado, nunca silenciado). Nunca CRÍTICO:
            este check é fundamentalmente heurístico ("[julgamento]"), não
            uma violação estrutural.
  CHK-10 -- roda `todo_sync.py` **sem** `--apply` (nunca com) e anexa a
            proposta ao relatório como UM ÚNICO achado informativo
            (severidade COSMÉTICO, sempre exatamente 1 -- nunca N achados
            por item proposto, para não inflar a contagem de algo que não
            é defeito da tabela).

Os dois são `profile == "core"` (ADR-0001 secao a): nenhuma convenção da
casa, aplicam a qualquer TODO.md que use o vocabulário de status do
produto.

--- Idioma no conteúdo livre (ADR-0001 secao d) -----------------------------

CHK-09 nunca hardcodeia string literal de julgamento no corpo do check: os
padrões vêm de `DEFAULT_PATTERNS` (pt+en, embutido no código como fallback)
e são ESTENDIDOS -- nunca substituídos, salvo override explícito -- por
`.tab_pendencias.ini`, seção `[audit.chk09]`, chave `patterns = ...`
(string única separada por vírgula; `configparser` não tem lista nativa
como TOML). `tests/test_chk_frescor.py` prova isso com um corpus em INGLÊS.

--- CHK-09: por que "read-only" não é o mesmo que "sem rede" ---------------

`--audit` é sempre read-only quanto ao ESTADO local (nunca commit/checkout/
branch/reset, nunca `git fetch` -- que grava refs remote-tracking em
`.git/`). `git ls-remote <remote>` é a ferramenta certa aqui porque consulta
o remoto DIRETAMENTE, sem tocar em nada local -- é por isso que o
team-lead o recomendou como a forma canônica de verificar "isto já foi
pushado?" sem um fetch. Ausência de remoto, falha de rede, ou timeout viram
achado COSMÉTICO "não verificável" (nunca um `True`/`False` silencioso).

--- CHK-09: as duas famílias de claim reconhecidas --------------------------

Cada padrão (default ou de config) cai numa de duas famílias, decidida por
conter ou não a palavra "branch" (a mesma palavra em pt e en, convenientemente
-- não precisa de config extra para decidir a família):

  "push"   -- claims sobre o trabalho ainda não ter chegado ao remoto
              ("não pushado", "commit local"...). Veredito via
              `git ls-remote` (sha exato) ou, quando o objeto do remoto já
              está disponível localmente, `git merge-base --is-ancestor`.
              Quando o veredito via remoto fica "desconhecido" (sem remoto,
              rede falhou), uma evidência AUXILIAR opcional e 100% offline
              é tentada: se a Descrição cita um arquivo entre crases
              (` `arquivo.ext` `) e esse arquivo já está idêntico ao branch
              principal LOCAL (`git cat-file -e <main>:<path>` +
              `git diff <main> HEAD -- <path>` vazio), isso upgrada o
              veredito para "obsoleta" -- é uma pergunta ligeiramente
              diferente ("já chegou no tronco local") mas reforça o mesmo
              sinal sem precisar de rede.
  "branch" -- claims que citam uma branch específica ("está na branch X").
              Veredito via `git ls-remote --heads <remote> <nome>`: branch
              ausente no remoto = evidência de merge/remoção (obsoleta);
              presente = claim ainda sustentada (sem achado).

Em QUALQUER família, veredito "sustentada" (evidência mostra que a claim
segue válida) não produz achado -- não é defeito reportar o que já é
verdade.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import todo_lib as L

DEFAULT_PATTERNS = (
    "não pushado", "nao pushado", "not pushed",
    "commit local", "local commit", "branch ",
)

_CFG_SECTION = "audit.chk09"
# So extrai nome de branch quando esta entre crases (` `nome` `) e a crase
# vem LOGO em seguida (no maximo 1 palavra "adjetivo" no meio, ex.: "branch
# descartavel `nome`") -- a mesma convencao de code-span que o proprio
# TODO.md ja usa para identificadores/caminhos/branches. Isto foi calibrado
# em DUAS rodadas contra o corpus real de `consumidor A`
# (TAB_PENDENCIAS_FIXTURE_A), cada uma expondo uma classe de falso
# positivo diferente:
#   1) SEM exigir crase nenhuma: "branch novo"/"branch em runtime"/"branch
#      Win32" (usos legitimos da palavra "branch" em portugues -- branch de
#      CODIGO if/else, ou "novo" como adjetivo posposto) geravam achado
#      IMPORTANTE fantasma ("branch 'novo' nao existe no remoto").
#   2) Exigindo crase mas permitindo ATE 3 "palavras" soltas (`\S+`) entre
#      "branch" e a crase: a classe `\S+` nao exclui a propria crase, entao
#      uma frase longa com VARIAS crases (comum no corpus: "branch Win32
#      (sentinelas/`WINAPI`/ordem...") deixava o "skip" engolir a crase de
#      abertura de um span NAO RELACIONADO e capturar lixo ate a crase
#      seguinte. A classe abaixo (`[^\s\`()/]+`) exclui crase, parenteses e
#      barra do "skip word" -- um adjetivo solto (ex.: "descartavel") ainda
#      casa, mas qualquer coisa com parenteses/barra no meio (sinal de que
#      o texto seguiu para outra oracao, nao para o NOME da branch) trava a
#      extracao, que degrada para None (fica "desconhecido"/COSMETICO) em
#      vez de arriscar um nome errado.
_BRANCH_TOKEN_RE = re.compile(r"branch\b(?:\s+[^\s`()/]+)?\s*`([^`]+)`",
                              re.IGNORECASE)
_FILE_TOKEN_RE = re.compile(r"`([^`\s][^`]*?\.[A-Za-z0-9_]+)`")


# ------------------------------- config (ADR-0001 d) ----------------------

def _cfg_str(cfg, key, default=None):
    return cfg.get(_CFG_SECTION, key, fallback=default)


def _cfg_int(cfg, key, default):
    try:
        return cfg.getint(_CFG_SECTION, key, fallback=default)
    except ValueError:
        return default


def _cfg_patterns(cfg):
    """Lista de padroes ativa: DEFAULT_PATTERNS (pt+en) ESTENDIDA pelos
    padroes de `.tab_pendencias.ini` [audit.chk09] patterns -- nunca
    substituida, salvo `patterns_override = true` explicito (ADR-0001 d)."""
    extra_raw = _cfg_str(cfg, "patterns", "") or ""
    extra = [p.strip() for p in extra_raw.split(",") if p.strip()]
    try:
        override = cfg.getboolean(_CFG_SECTION, "patterns_override",
                                  fallback=False)
    except ValueError:
        override = False
    if override:
        return extra or list(DEFAULT_PATTERNS)
    out = list(DEFAULT_PATTERNS)
    low = [p.lower() for p in out]
    for p in extra:
        if p.lower() not in low:
            out.append(p)
            low.append(p.lower())
    return out


# ------------------------------- git helpers (read-only) ------------------

def _git(root, args, timeout):
    """(ok, saida_ou_erro) -- nunca lanca excecao (ADR-0001 c: um check de
    terceiro nao pode derrubar o motor; aqui o isolamento e feito na
    PROPRIA ferramenta, nao so confiando no catch generico de
    `run_audit`), e nunca chama subcomando que muta estado local (sem
    commit/checkout/branch/reset/fetch -- `ls-remote` consulta o remoto
    SEM gravar nada local, ao contrario de `fetch`)."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True,
                           text=True, timeout=timeout)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        return False, msg or f"git {' '.join(args)} falhou (rc={r.returncode})"
    return True, r.stdout


def _first_remote(root, cfg, timeout):
    configured = _cfg_str(cfg, "remote")
    if configured:
        return configured.strip()
    ok, out = _git(root, ["remote"], timeout)
    if not ok or not out.strip():
        return None
    return out.strip().splitlines()[0].strip()


def _head_sha(root, timeout):
    ok, out = _git(root, ["rev-parse", "HEAD"], timeout)
    return out.strip() if ok else None


def _current_branch(root, timeout):
    ok, out = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"], timeout)
    if not ok:
        return None
    b = out.strip()
    return b if b and b != "HEAD" else None


def _ls_remote_refs(root, remote, timeout):
    """{ref: sha} do remoto via `git ls-remote` -- nunca `fetch` (ver
    docstring do modulo). (refs_ou_None, erro_ou_None)."""
    ok, out = _git(root, ["ls-remote", remote], timeout)
    if not ok:
        return None, out
    refs = {}
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            sha, ref = parts
            refs[ref.strip()] = sha.strip()
    return refs, None


def _object_exists(root, obj, timeout):
    ok, _out = _git(root, ["cat-file", "-e", obj], timeout)
    return ok


def _is_ancestor(root, ancestor, descendant, timeout):
    ok, _out = _git(root, ["merge-base", "--is-ancestor", ancestor,
                           descendant], timeout)
    return ok


def _main_branch(root, cfg, timeout):
    configured = _cfg_str(cfg, "main_branch")
    if configured:
        return configured.strip()
    for cand in ("main", "master"):
        if _object_exists(root, cand, timeout):
            return cand
    return None


# ------------------------------- veredito por familia ----------------------
#
# Cada `_verify_*` devolve (veredito, evidencia): veredito em
# {"obsoleta", "sustentada", "desconhecido"}. "sustentada" = claim
# permanece valida (NUNCA vira achado -- nao e defeito reportar o que ja e
# verdade). "desconhecido" = nao foi possivel confirmar nem refutar (SEMPRE
# vira achado COSMETICO -- no silent caps, nunca tratado como "tudo bem").

def _verify_push_claim(root, cfg, timeout):
    remote = _first_remote(root, cfg, timeout)
    if not remote:
        return "desconhecido", "sem remoto git configurado neste repositório"
    head = _head_sha(root, timeout)
    if not head:
        return "desconhecido", "não foi possível obter HEAD (git rev-parse HEAD falhou)"
    refs, err = _ls_remote_refs(root, remote, timeout)
    if refs is None:
        return "desconhecido", f"git ls-remote {remote} falhou ou expirou: {err}"
    remote_shas = set(refs.values())
    if head in remote_shas:
        matched = next(ref for ref, sha in refs.items() if sha == head)
        return "obsoleta", (
            f"HEAD ({head[:8]}) já está no remoto '{remote}' (ref {matched})")

    branch = _current_branch(root, timeout)
    candidatos = ([f"refs/heads/{branch}"] if branch else []) + ["HEAD"]
    remote_sha = matched_ref = None
    for cand in candidatos:
        if cand in refs:
            remote_sha, matched_ref = refs[cand], cand
            break
    if not remote_sha:
        return "desconhecido", (
            f"remoto '{remote}' não tem ref correspondente à branch atual "
            f"({branch or '?'}) -- nada com o que comparar")
    if not _object_exists(root, remote_sha, timeout):
        return "desconhecido", (
            f"objeto do remoto ({remote_sha[:8]}, ref {matched_ref}) não "
            "está disponível localmente -- ancestralidade não decidível "
            "sem `git fetch` (--audit nunca faz fetch)")
    if _is_ancestor(root, head, remote_sha, timeout):
        return "obsoleta", (
            f"HEAD ({head[:8]}) é ancestral do remoto '{remote}' "
            f"({remote_sha[:8]}, ref {matched_ref}) -- já está pushado")
    if _is_ancestor(root, remote_sha, head, timeout):
        return "sustentada", (
            f"remoto '{remote}' ({remote_sha[:8]}) está atrás de HEAD "
            f"({head[:8]}) -- há commit(s) local(is) genuinamente não "
            "pushado(s)")
    return "desconhecido", (
        f"HEAD ({head[:8]}) e o remoto '{remote}' ({remote_sha[:8]}) "
        "divergiram -- não dá para concluir se a claim segue válida")


def _verify_via_main_local(root, cfg, timeout, path):
    """Evidencia AUXILIAR, 100% offline (sem remoto): so chamada quando o
    veredito via remoto ja deu 'desconhecido'. Responde uma pergunta
    ligeiramente diferente ("ja chegou no tronco LOCAL?") que reforca o
    mesmo sinal quando aplicavel. Nunca upgrada para 'sustentada' -- so
    fortalece 'obsoleta' quando o arquivo citado ja e identico ao branch
    principal local; ausencia de sinal aqui nao decide nada (fica
    'desconhecido')."""
    if not path:
        return None
    main = _main_branch(root, cfg, timeout)
    if not main:
        return None
    if not _object_exists(root, f"{main}:{path}", timeout):
        return None
    ok, out = _git(root, ["diff", main, "HEAD", "--", path], timeout)
    if ok and out.strip() == "":
        return f"arquivo `{path}` já está idêntico a '{main}' localmente"
    return None


def _verify_branch_claim(root, cfg, timeout, branch_name):
    remote = _first_remote(root, cfg, timeout)
    if not remote:
        return "desconhecido", "sem remoto git configurado neste repositório"
    if not branch_name:
        return "desconhecido", (
            "não foi possível extrair o nome da branch citada na descrição")
    ok, out = _git(root, ["ls-remote", "--heads", remote, branch_name], timeout)
    if not ok:
        return "desconhecido", (
            f"git ls-remote --heads {remote} {branch_name} falhou ou expirou: {out}")
    if out.strip():
        return "sustentada", f"branch '{branch_name}' ainda existe no remoto '{remote}'"
    return "obsoleta", (
        f"branch '{branch_name}' não existe mais no remoto '{remote}' -- "
        "possivelmente já mesclada/removida")


def _kind_of(pattern):
    return "branch" if "branch" in pattern.lower() else "push"


# ------------------------- citacao vs. afirmacao (falso positivo real) -----
#
# Achado auto-referencial medido ao vivo: a PROPRIA linha do CHK-09 na
# TODO.md deste repositorio ("Claims obsoletas na Descrição (\"não
# pushado\", \"commit local\", \"branch X\") verificadas...") dispara os
# proprios padroes -- o texto MENCIONA os padroes como exemplo de catalogo,
# nao esta FAZENDO nenhuma dessas claims sobre o proprio item. Criterio
# escolhido (adversarialmente honesto, nao um regex fragil de "isto parece
# exemplo"): uma ocorrencia entre aspas retas/tipograficas ADJACENTES (aspa
# abrindo imediatamente antes do match, aspa do MESMO tipo fechando pouco
# depois, sem outra abertura no meio) e uma CITACAO/enumeracao de string
# literal, nao uma afirmacao sobre o item -- exatamente o padrao de
# `("não pushado", "commit local", "branch X")`. A janela de fechamento e
# CURTA (40 caracteres) e a adjacencia de abertura e ESTRITA (o caractere
# imediatamente anterior, sem tolerancia de espaco) de proposito: evita que
# aspas soltas, longe no mesmo paragrafo, encapsulem por acidente uma claim
# genuina (o mesmo cuidado que ja levou a exigir crase ADJACENTE, nao "em
# algum lugar da frase", para nome de branch). Se nenhuma aspa casar dessa
# forma, a ocorrencia conta normalmente como possivel afirmacao.
_QUOTE_PAIRS = (('"', '"'), ("“", "”"))


def _e_citacao_entre_aspas(desc, start, end):
    antes = desc[:start]
    depois = desc[end:end + 40]
    for abre, fecha in _QUOTE_PAIRS:
        if not antes.endswith(abre):
            continue
        idx_fecha = depois.find(fecha)
        if idx_fecha == -1:
            continue
        if abre not in depois[:idx_fecha]:
            return True
    return False


def _pattern_tem_ocorrencia_fora_de_citacao(desc, pattern):
    for m in re.finditer(re.escape(pattern), desc, re.IGNORECASE):
        if not _e_citacao_entre_aspas(desc, m.start(), m.end()):
            return True
    return False


def _extract_branch_name(desc):
    """Primeiro nome de branch valido apos a palavra 'branch' (ver o
    comentario de `_BRANCH_TOKEN_RE` acima sobre exigir crase). Recusa
    tambem candidatos cujo contexto IMEDIATAMENTE anterior cite '.git'
    (ex.: "consumidor A.wiki.git, branch `master`") -- a branch citada pertence
    a OUTRO repositorio (o da wiki), nao ao que este --audit esta rodando;
    verificar contra o remoto ERRADO e uma segunda classe de falso
    positivo medida no mesmo corpus real."""
    for m in _BRANCH_TOKEN_RE.finditer(desc):
        antes = desc[max(0, m.start() - 40):m.start()]
        if ".git" in antes.lower():
            continue
        return m.group(1)
    return None


# ------------------------------- deteccao de coluna/celulas -----------------

def _header_cells(table):
    """Celulas do cabecalho real (mesmo criterio de `todo_lib._is_header`,
    reaplicado aqui em vez de expor `line_no` do cabecalho no contrato do
    parser -- mesmo padrao usado por `chk_graph._header_cells`)."""
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


def _desc_idx(table):
    cells = _header_cells(table)
    if not cells:
        return None
    for i, c in enumerate(cells):
        low = c.lower()
        if "descri" in low or "description" in low:
            return i
    return None


def _row_cells(line):
    return L._cells(line.lstrip(L.BOM))


# ------------------------------- CHK-09 ------------------------------------

def _build_finding_chk09(item_id, line_no, pats, veredito, evidencia):
    if veredito == "sustentada":
        return None
    from todo_audit import Finding  # import tardio: quebra o ciclo com
    # `todo_audit` (que registra este check importando o MODULO); dentro do
    # corpo da funcao so executa quando o check RODA.
    severity = "IMPORTANTE" if veredito == "obsoleta" else "COSMÉTICO"
    rotulo = ("possivelmente OBSOLETA" if veredito == "obsoleta"
             else "não verificável")
    citados = "', '".join(pats)
    return Finding(
        check_id="CHK-09", severity=severity, fixable=False,
        message=(f"{item_id!r} cita '{citados}' na descrição -- claim "
                 f"{rotulo}. Evidência: {evidencia}."),
        line_no=line_no)


def chk09(ctx):
    table = ctx.table
    if not table or not table["items"]:
        return []
    cfg = ctx.config
    timeout = _cfg_int(cfg, "timeout", 10)
    patterns = _cfg_patterns(cfg)
    desc_idx = _desc_idx(table)
    if desc_idx is None:
        return []

    cache = {}
    out = []
    for it in table["items"]:
        cells = _row_cells(table["lines"][it["line_no"]])
        if desc_idx >= len(cells):
            continue
        desc = cells[desc_idx]
        hits = [p for p in patterns
                if _pattern_tem_ocorrencia_fora_de_citacao(desc, p)]
        if not hits:
            continue

        push_hits = [p for p in hits if _kind_of(p) != "branch"]
        branch_hits = [p for p in hits if _kind_of(p) == "branch"]

        if push_hits:
            if "push" not in cache:
                cache["push"] = _verify_push_claim(ctx.root, cfg, timeout)
            veredito, evidencia = cache["push"]
            if veredito == "desconhecido":
                m = _FILE_TOKEN_RE.search(desc)
                extra = _verify_via_main_local(
                    ctx.root, cfg, timeout, m.group(1) if m else None)
                if extra:
                    veredito = "obsoleta"
                    evidencia = (f"{evidencia}; adicionalmente, {extra} "
                                "(evidência offline via branch principal local)")
            f = _build_finding_chk09(it["id"], it["line_no"], push_hits,
                                     veredito, evidencia)
            if f:
                out.append(f)

        if branch_hits:
            nome = _extract_branch_name(desc)
            key = ("branch", nome)
            if key not in cache:
                cache[key] = _verify_branch_claim(ctx.root, cfg, timeout, nome)
            veredito, evidencia = cache[key]
            f = _build_finding_chk09(it["id"], it["line_no"], branch_hits,
                                     veredito, evidencia)
            if f:
                out.append(f)
    return out


# ------------------------------- CHK-10 ------------------------------------

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TODO_SYNC_PATH = os.path.join(_TOOLS_DIR, "todo_sync.py")

_AVISO_CANONICO = (
    "AVISO CANÔNICO: citar o ID de um item num commit NÃO é o mesmo que "
    "ter entregue o item -- leia esta proposta com desconfiança "
    "(§4, references/frescor-da-tabela.md)."
)


def _baseline_message(root):
    """(baseline_existe, mensagem) -- extraido como funcao propria (testavel
    isoladamente) porque a PRESENCA do achado de CHK-10 (ver `chk10` abaixo)
    e condicional, mas a LOGICA de detectar/descrever o baseline nao
    precisa ficar acoplada a essa condicional pra ser verificada."""
    gd = L.git_dir(root)
    ref_path = os.path.join(gd, "todo-sync-ref") if gd else None
    if ref_path and os.path.isfile(ref_path):
        return True, f"baseline 'todo-sync-ref' presente ({ref_path})."
    return False, (
        "SEM baseline 'todo-sync-ref' -- esta execução tem semântica de 1ª "
        "execução (linha de base = HEAD, o histórico NÃO é varrido; use "
        "--since <ref> para ler o passado de propósito)."
    )


def chk10(ctx):
    """Roda `todo_sync.py` SEM `--apply` (nunca com -- `--apply` jamais
    aparece nos argumentos abaixo) e anexa a proposta ao relatorio como NO
    MAXIMO UM Finding (nunca N achados por item proposto -- nao inflar a
    contagem de algo que nao e defeito da tabela).

    Diferente de CHK-09 (que so fica em silencio quando a claim se
    sustenta), CHK-10 fica em silencio -- lista VAZIA, nao achado nenhum --
    quando `todo_sync.py` roda limpo e NAO ha nada a propor (`rc == 0`, o
    contrato de exit code do proprio `todo_sync.py`/D-6): "informacao anexa"
    so faz sentido quando ha algo pra anexar (proposta real OU falha de
    execucao); do contrario a tabela genuinamente nao tem nada digno de
    nota aqui, e reportar do mesmo jeito violaria a propria instrucao do
    team-lead de nao inflar a contagem de achados com o que nao e problema.
    Isto tambem preserva o invariante do motor "tabela limpa -> 0 achados"
    (varios testes de `test_todo_audit.py`, anteriores a este check,
    dependem dele -- CHK-00/05/06/07 ja nao o violam por nao acharem nada
    em fixture sintetica limpa; CHK-10 tinha que seguir a mesma regra)."""
    from todo_audit import Finding

    baseline_existe, baseline_msg = _baseline_message(ctx.root)

    try:
        r = subprocess.run([sys.executable, _TODO_SYNC_PATH], cwd=ctx.root,
                           capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        msg = (f"{_AVISO_CANONICO} {baseline_msg}\ntodo_sync.py não "
              "respondeu em 30s (timeout) -- não foi possível determinar "
              "se há proposta.")
        return [Finding(check_id="CHK-10", severity="COSMÉTICO",
                        fixable=False, message=msg, line_no=None)]
    except Exception as exc:  # noqa: BLE001 -- isolamento deliberado (ver
        # docstring do modulo/ADR-0001 c): uma falha aqui vira achado
        # declarado, nunca deixa o motor quebrar nem fica silenciosa.
        msg = (f"{_AVISO_CANONICO} {baseline_msg}\nfalha ao rodar "
              f"todo_sync.py ({type(exc).__name__}: {exc}).")
        return [Finding(check_id="CHK-10", severity="COSMÉTICO",
                        fixable=False, message=msg, line_no=None)]

    if r.returncode == 0:
        # nada a propor e a execucao foi limpa -- de proposito SEM achado
        # (ver docstring acima).
        return []

    saida = r.stdout or ""
    if r.stderr.strip():
        saida = f"{saida}\n[stderr] {r.stderr.strip()}"
    rotulo = "erro de execução" if r.returncode == 1 else f"rc={r.returncode}"
    msg = (f"{_AVISO_CANONICO} {baseline_msg}\ntodo_sync.py (sem --apply, "
          f"{rotulo}):\n{saida.strip()}")
    return [Finding(check_id="CHK-10", severity="COSMÉTICO", fixable=False,
                    message=msg, line_no=None)]
