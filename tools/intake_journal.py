#!/usr/bin/env python3
# tools/intake_journal.py -- write-ahead journal de intake (TAB-ADD-000)
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
tools/intake_journal.py -- captura duravel e barata de candidatos a item de
TODO, ANTES de qualquer classificacao agentiva que possa terminar em
mutacao persistente (ADR-0002, secao (c)/T2; PLANO-MELHORIA... TAB-ADD-000).

O problema que isto resolve: entre "a descoberta foi entendida" e "a
descoberta foi persistida no TODO.md" existe uma janela. Se a sessao morre
nessa janela, a descoberta some -- e some em silencio. Este modulo fecha
essa janela com um journal write-ahead: grava o candidato em disco (fora do
`TODO.md`, fora do versionamento) ANTES de qualquer mutacao da tabela, e
oferece recuperacao idempotente de registros orfaos apos crash.

Escopo desta fatia (fronteira do brief): so a captura duravel e a
recuperacao. NAO implementa `--add`, classificacao de impacto (L0..L3) nem
reorder -- isso e TAB-ADD-001..007, escopo de outra fatia.

## Onde o journal mora

Dentro do git common dir (`git rev-parse --git-common-dir`), nunca dentro
do worktree/`.git` fisico local -- em um `git worktree`, `.git` e um
ARQUIVO que aponta para o common dir, nao um diretorio; usar
`--git-common-dir` (em vez de reimplementar a leitura desse arquivo) e o
que garante:

  1. o journal fica fora do `TODO.md` e fora do versionamento (o common
     dir nao e conteudo rastreado pelo proprio repositorio);
  2. o journal e COMPARTILHADO entre todos os worktrees do mesmo
     repositorio (todos resolvem para o mesmo common dir) -- uma sessao
     que descobre algo num worktree e outra sessao rodando noutro
     worktree do MESMO repo enxergam o mesmo journal;
  3. cross-platform: o comando `git rev-parse` ja resolve a semantica de
     worktree corretamente em qualquer SO com Git instalado -- este
     modulo nunca faz `os.path.join(root, ".git", ...)` a mao.

Caminho final: `<git-common-dir>/tab-pendencias/intake-journal/<arquivo>`.

## Formato do registro (um arquivo JSON por candidato)

```json
{
  "schema_version": 1,
  "candidate_id": "...",
  "created_at": "2026-08-16T12:34:56.789012+00:00",
  "updated_at": "2026-08-16T12:34:56.789012+00:00",
  "source": "user|bus|agent|audit|test",
  "description": "...",
  "source_item": "...",
  "state": "NEW|DONE"
}
```

## Nome de arquivo: sanitizacao cross-platform

O `candidate_id` e conteudo arbitrario (pode vir de fora: bus, agente,
usuario) e NUNCA vira nome de arquivo sem passar por
`sanitize_filename_component`, que remove os caracteres proibidos no
Windows (`< > : " / \\ | ? *` e controle 0x00-0x1F), corta espaco/ponto nas
pontas (Windows os rejeita ali), evita os nomes de dispositivo reservados
(`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`) e limita o comprimento.
Para garantir que dois `candidate_id` DIFERENTES que sanitizam para o
MESMO texto (ex.: `"cand:x"` e `"cand?x"` -> `"cand_x"`) nunca colidam em
disco, o nome final leva um sufixo hash do `candidate_id` ORIGINAL -- a
sanitizacao e so estetica, a unicidade e garantida pelo hash.

## Ciclo de vida e recuperacao

`write_candidate` grava com `state=NEW`. Depois que a integracao no
`TODO.md` for persistida e validada por quem chama (fora deste modulo, ver
TAB-ADD-001..007), o candidato vira `mark_done` (fica em disco, state=DONE,
nunca mais aparece como orfao) ou e removido com `remove_candidate`
(apagado do disco). As duas operacoes sao idempotentes -- chamar de novo
sobre algo ja feito nao e erro, so devolve `False`.

Um crash entre `write_candidate` e a marcacao de conclusao deixa o
registro em `state=NEW`: e um ORFAO, listado por `list_orphans`.
`recover_orphans` resolve o orfao contra o texto atual do `TODO.md`
(dedup mecanica por ID exato -- ADR-0002 secao (a), a etapa "deduplicacao
por ID exato" e classificada como mecanica/nucleo): se o `candidate_id`
aparece literalmente no texto (contrato: quem integra o candidato deve
gravar o `candidate_id` em algum marcador recuperavel na linha, ex.
comentario HTML ou coluna de evidencia -- fora do escopo desta fatia
implementar ESSE lado, TAB-ADD-004), o candidato ja foi integrado: marca
`DONE` e nao duplica nada. Caso contrario continua pendente, sem qualquer
efeito colateral -- rodar `recover_orphans` duas vezes seguidas produz o
mesmo resultado (idempotente por construcao: a unica escrita e
`mark_done`, que ja e idempotente).

Journal corrompido (JSON invalido) ou parcialmente escrito (arquivo
temporario de uma gravacao interrompida) nunca quebra a listagem/
recuperacao: `list_corrupted` reporta os arquivos ilegiveis separadamente,
`list_orphans`/`recover_orphans` os ignoram (nunca fazem `mark_done` as
cegas sobre um registro que nao da para interpretar).

## Segredo nunca entra no journal

`redact_secrets` e um filtro heuristico best-effort (regex sobre padroes
comuns: chave AWS, bloco de chave privada PEM, atribuicao tipo
`senha=...`/`token=...`, bearer token, JWT) aplicado a `description` antes
de gravar. Limitacao declarada (regra "no silent caps" do projeto): isto
NAO e um scanner de segredo exaustivo -- e defesa em profundidade, nao
substitui revisao humana nem um scanner dedicado (gitleaks etc.) na
fronteira que alimenta este modulo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

SCHEMA_VERSION = 1

STATE_NEW = "NEW"
STATE_DONE = "DONE"

VALID_SOURCES = frozenset({"user", "bus", "agent", "audit", "test"})

_JOURNAL_SUBPATH = ("tab-pendencias", "intake-journal")

_WINDOWS_FORBIDDEN_CHARS = '<>:"/\\|?*'
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_MAX_FILENAME_STEM = 100  # antes do sufixo de hash + ".json"


class IntakeJournalError(Exception):
    """Erro de uso deste modulo (source invalido, journal_dir nao
    resolvivel, etc.) -- nunca usado para "engolir" excecao de terceiro."""


# ---------------------------------------------------------------------------
# localizacao do journal (git common dir)
# ---------------------------------------------------------------------------

def _run_git(args, cwd):
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def resolve_git_common_dir(cwd=None):
    """Caminho ABSOLUTO do git common dir a partir de `cwd` (default: cwd
    do processo), via `git rev-parse --git-common-dir`. `None` se `cwd` nao
    estiver dentro de um repositorio git (ou git indisponivel).

    `git rev-parse` devolve o caminho relativo ao CWD em que o comando
    rodou (nao ao toplevel do repo) quando o common dir e local, e um
    caminho ABSOLUTO quando o common dir vive fora da arvore atual --
    exatamente o caso de um `git worktree` linked, onde `.git` ali e um
    ARQUIVO apontando para o repo principal. Por isso resolvemos relativo
    ao MESMO `cwd` passado ao subprocesso, nunca ao toplevel."""
    base = cwd if cwd is not None else os.getcwd()
    out = _run_git(["rev-parse", "--git-common-dir"], cwd=base)
    if not out:
        return None
    if os.path.isabs(out):
        resolved = out
    else:
        resolved = os.path.join(str(base), out)
    return os.path.normpath(os.path.abspath(resolved))


def journal_dir_for(cwd=None):
    """Diretorio do journal para o repositorio que contem `cwd`, ou `None`
    se `cwd` nao esta dentro de um repositorio git."""
    common_dir = resolve_git_common_dir(cwd=cwd)
    if common_dir is None:
        return None
    return os.path.join(common_dir, *_JOURNAL_SUBPATH)


# ---------------------------------------------------------------------------
# sanitizacao de nome de arquivo (cross-platform, Windows e o caso estrito)
# ---------------------------------------------------------------------------

def sanitize_filename_component(raw):
    """`raw` (qualquer string, inclusive vazia/so espaco/so ponto/com
    caracteres proibidos no Windows) -> componente de nome de arquivo
    seguro em Windows E POSIX. Nunca devolve string vazia."""
    out_chars = []
    for ch in raw:
        cp = ord(ch)
        if ch in _WINDOWS_FORBIDDEN_CHARS or cp < 0x20:
            out_chars.append("_")
        else:
            out_chars.append(ch)
    safe = "".join(out_chars).strip()
    # Windows rejeita nome terminado em ponto ou espaco.
    safe = safe.rstrip(". ").strip()
    if not safe:
        safe = "_"
    if safe.upper() in _RESERVED_WINDOWS_NAMES:
        safe = f"{safe}_"
    if len(safe) > _MAX_FILENAME_STEM:
        safe = safe[:_MAX_FILENAME_STEM]
        safe = safe.rstrip(". ") or "_"
    return safe


def _journal_filename(candidate_id):
    """Nome de arquivo deterministico e UNICO por `candidate_id`: prefixo
    legivel (sanitizado) + sufixo hash do candidate_id ORIGINAL. O hash
    desambigua candidatos diferentes que sanitizam para o mesmo prefixo
    (ver docstring do modulo) e o mesmo `candidate_id` sempre produz o
    MESMO nome (necessario para mark_done/remove_candidate acharem o
    arquivo em O(1), sem varrer o diretorio)."""
    stem = sanitize_filename_component(candidate_id)
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
    return f"{stem}--{digest}.json"


def candidate_path(journal_dir, candidate_id):
    """Caminho absoluto/relativo (conforme `journal_dir`) do arquivo do
    candidato -- deterministico, nao requer o arquivo existir."""
    return os.path.join(journal_dir, _journal_filename(candidate_id))


def new_candidate_id():
    """Gera um `candidate_id` novo, ja seguro como nome de arquivo por
    construcao (timestamp UTC compacto + 8 bytes aleatorios em hex) --
    nao depende de sanitizacao para o caminho comum, mas o modulo aceita
    `candidate_id` arbitrario de fora (bus/agente/usuario) em qualquer
    outra funcao, e esses SEMPRE passam por `sanitize_filename_component`
    antes de virar nome de arquivo."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{ts}Z-{secrets.token_hex(4)}"


# ---------------------------------------------------------------------------
# sanitizacao de segredo (defesa em profundidade, best-effort)
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    # bloco de chave privada PEM (RSA/EC/OPENSSH/generico)
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    # AWS access key id
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # atribuicao tipo chave=valor / chave: valor (api key, secret, token,
    # senha/password em pt-br e en, >= 8 chars de valor)
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|senha|password|passwd|pwd)"
        r"\b\s*[:=]\s*['\"]?[A-Za-z0-9\-_./+=]{8,}['\"]?"
    ),
    # bearer token
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_.=]{10,}"),
    # JWT (header.payload.signature em base64url)
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    # tokens de provedor com prefixo caracteristico (GitHub etc.)
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
]


def redact_secrets(text):
    """Aplica os padroes de `_SECRET_PATTERNS` e substitui cada trecho
    casado por `<REDACTED>`. Best-effort, ver limitacao no docstring do
    modulo -- nunca trate ausencia de match como prova de ausencia de
    segredo."""
    if not text:
        return text
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("<REDACTED>", out)
    return out


# ---------------------------------------------------------------------------
# escrita atomica
# ---------------------------------------------------------------------------

def _atomic_write_json(path, record):
    """Escreve `record` como JSON em `path` de forma atomica: arquivo
    temporario no MESMO diretorio (mesmo filesystem -- `os.replace` e
    atomico de verdade so entao) + fsync + releitura de conferencia antes
    do swap, mesmo padrao ja usado por `todo_fix.py` (`_escrever_atomico`).
    Se qualquer passo falhar, o temporario e removido e `path` NUNCA e
    tocado."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    texto = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".intake_journal.",
                                        suffix=".tmp", dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fd = None  # fdopen adotou o descritor; nao fechar de novo no finally
            fh.write(texto)
            fh.flush()
            os.fsync(fh.fileno())
        with open(tmp_path, encoding="utf-8", newline="") as fh:
            lido = fh.read()
        if lido != texto:
            raise IntakeJournalError(
                "conteudo lido de volta do arquivo temporario diverge do "
                "que foi escrito -- gravacao abortada antes de trocar o "
                "arquivo real")
        os.replace(tmp_path, path)
        tmp_path = None
    except OSError as exc:
        raise IntakeJournalError(
            f"falha de I/O gravando journal ({type(exc).__name__}: {exc})"
        ) from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# API principal: escrita, leitura, ciclo de vida
# ---------------------------------------------------------------------------

def write_candidate(candidate_id, *, source, description, source_item="",
                     created_at=None, cwd=None, journal_dir=None):
    """Grava o candidato ATOMICAMENTE, `state=NEW`, ANTES de qualquer
    mutacao do `TODO.md`. Devolve o caminho absoluto/relativo do arquivo
    escrito (o mesmo tipo de caminho de `journal_dir`).

    `journal_dir`, se dado, tem prioridade sobre `journal_dir_for(cwd)` --
    permite uso fora de um repositorio git (ex.: teste, ou um caller que ja
    resolveu o diretorio uma vez). Sem `journal_dir` e fora de um repo git,
    falha explicitamente (IntakeJournalError) em vez de inventar um
    caminho -- captura duravel sem saber ONDE durar nao e captura duravel.
    """
    if source not in VALID_SOURCES:
        raise IntakeJournalError(
            f"source invalido: {source!r} (esperado um de "
            f"{sorted(VALID_SOURCES)})")

    if journal_dir is None:
        journal_dir = journal_dir_for(cwd=cwd)
    if journal_dir is None:
        raise IntakeJournalError(
            "nao foi possivel localizar o git common dir a partir de "
            "'cwd' e nenhum 'journal_dir' explicito foi passado -- "
            "captura duravel exige saber onde gravar")

    now = created_at or datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "created_at": now,
        "updated_at": now,
        "source": source,
        "description": redact_secrets(description),
        "source_item": source_item,
        "state": STATE_NEW,
    }
    path = candidate_path(journal_dir, candidate_id)
    _atomic_write_json(path, record)
    return path


def read_candidate_safe(path):
    """(record, None) se `path` for JSON valido de um registro; (None,
    mensagem_de_erro) se corrompido/ilegivel. Nunca levanta excecao --
    quem lista o journal precisa poder reportar corrupcao sem quebrar."""
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            texto = fh.read()
    except OSError as exc:
        return None, f"falha de leitura ({type(exc).__name__}: {exc})"
    try:
        record = json.loads(texto)
    except json.JSONDecodeError as exc:
        return None, f"JSON invalido ({exc})"
    if not isinstance(record, dict) or "candidate_id" not in record:
        return None, "registro sem 'candidate_id' -- formato inesperado"
    return record, None


def _iter_journal_files(journal_dir):
    if not journal_dir or not os.path.isdir(journal_dir):
        return
    for nome in sorted(os.listdir(journal_dir)):
        # arquivos temporarios de uma gravacao atomica interrompida (crash
        # no meio de _atomic_write_json, antes do os.replace) nunca sao
        # candidatos validos -- ignorar, nunca tentar interpretar.
        if not nome.endswith(".json"):
            continue
        yield os.path.join(journal_dir, nome)


def list_corrupted(journal_dir):
    """[(path, mensagem_de_erro), ...] para todo arquivo `*.json` do
    journal que nao parseia como registro valido."""
    out = []
    for path in _iter_journal_files(journal_dir):
        record, err = read_candidate_safe(path)
        if record is None:
            out.append((path, err))
    return out


def list_orphans(journal_dir):
    """[(path, record), ...] para todo registro valido com
    `state != DONE` -- candidatos que sobreviveriam a um crash sem
    resolucao. Ignora silenciosamente arquivos corrompidos (reportados por
    `list_corrupted`) e arquivos temporarios."""
    out = []
    for path in _iter_journal_files(journal_dir):
        record, err = read_candidate_safe(path)
        if record is None:
            continue
        if record.get("state") != STATE_DONE:
            out.append((path, record))
    return out


def mark_done(journal_dir, candidate_id):
    """Marca o candidato como concluido (integracao persistida e
    validada). Idempotente: chamar de novo sobre um candidato ja `DONE`
    continua devolvendo `True` (reescreve o mesmo estado); candidato
    inexistente devolve `False`, nunca levanta excecao."""
    path = candidate_path(journal_dir, candidate_id)
    record, err = read_candidate_safe(path)
    if record is None:
        return False
    if record.get("state") == STATE_DONE:
        return True
    record["state"] = STATE_DONE
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(path, record)
    return True


def remove_candidate(journal_dir, candidate_id):
    """Remove o registro do disco (alternativa a `mark_done` na secao
    "ciclo de vida" do brief: 'vira concluido OU e removido com
    seguranca'). Idempotente: candidato ja removido/inexistente devolve
    `False` sem levantar excecao."""
    path = candidate_path(journal_dir, candidate_id)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise IntakeJournalError(
            f"falha removendo candidato {candidate_id!r} "
            f"({type(exc).__name__}: {exc})"
        ) from exc


# ---------------------------------------------------------------------------
# recuperacao idempotente (dedup mecanica por ID exato)
# ---------------------------------------------------------------------------

@dataclass
class RecoveryReport:
    recovered_as_duplicate: list = field(default_factory=list)
    still_pending: list = field(default_factory=list)
    corrupted: list = field(default_factory=list)

    def is_empty_action(self):
        return not self.recovered_as_duplicate and not self.still_pending


def _read_todo_text(todo_path):
    # utf-8-sig: descarta BOM se presente -- isto e leitura de BUSCA, nao
    # round-trip de escrita (o modulo nunca reescreve o TODO.md), entao
    # nao ha a exigencia de preservar BOM/CRLF byte-a-byte que existe em
    # todo_lib/todo_fix.
    with open(todo_path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def recover_orphans(journal_dir, todo_path=None, todo_text=None):
    """Reconcilia todo orfao do journal contra o estado atual do
    `TODO.md`: se o `candidate_id` ja aparece (literalmente) no texto, o
    candidato foi integrado por uma execucao anterior que morreu antes de
    marcar `DONE` -- este e o caso do meio da tabela T2 do ADR-0002
    ("apos os.replace, antes de DONE"). Marca `DONE` e NAO cria nada
    (dedup mecanica por ID exato). Caso contrario, o candidato continua
    pendente de classificacao completa (fora do escopo desta fatia,
    TAB-ADD-001+) -- nenhuma escrita acontece para esse caso, o que torna
    a funcao idempotente por construcao: repetir sem mudanca externa
    produz o mesmo relatorio, sem duplicar nada.

    Exatamente um de `todo_path`/`todo_text` deve ser dado quando ha
    orfaos a resolver contra a tabela; passar nenhum dos dois e valido
    (todo orfao sai como `still_pending`, sem tentar dedup)."""
    relatorio = RecoveryReport()
    relatorio.corrupted = [path for path, _err in list_corrupted(journal_dir)]

    orphans = list_orphans(journal_dir)
    if not orphans:
        return relatorio

    text = todo_text
    if text is None and todo_path is not None:
        text = _read_todo_text(todo_path)

    for _path, record in orphans:
        cid = record["candidate_id"]
        if text and cid in text:
            mark_done(journal_dir, cid)
            relatorio.recovered_as_duplicate.append(cid)
        else:
            relatorio.still_pending.append(cid)
    return relatorio


# ---------------------------------------------------------------------------
# CLI minima (uso manual / diagnostico -- wiring com o hook/health e de
# outra fatia, este modulo so expoe as funcoes)
# ---------------------------------------------------------------------------

def _cli_list_orphans(journal_dir):
    orphans = list_orphans(journal_dir)
    corrupted = list_corrupted(journal_dir)
    print(f"intake_journal: {len(orphans)} orfao(s), "
          f"{len(corrupted)} arquivo(s) corrompido(s) em {journal_dir!r}")
    for _path, record in orphans:
        print(f"  NEW  {record['candidate_id']}  "
              f"source={record.get('source')}  "
              f"desde={record.get('created_at')}")
    for path, err in corrupted:
        print(f"  CORROMPIDO  {path}: {err}")
    return 0


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(
        prog="intake_journal",
        description="Diagnostico manual do write-ahead journal de intake "
                     "(TAB-ADD-000). Leitura, sem mutar o TODO.md.")
    parser.add_argument("--journal-dir",
                        help="Override do diretorio do journal (default: "
                             "resolvido via git-common-dir do cwd).")
    parser.add_argument("--list-orphans", action="store_true",
                        help="Lista candidatos NEW (nao concluidos).")
    args = parser.parse_args(argv)

    journal_dir = args.journal_dir or journal_dir_for(cwd=os.getcwd())
    if journal_dir is None:
        print("intake_journal: nao foi possivel localizar o git common "
              "dir a partir do cwd atual, e --journal-dir nao foi dado.")
        return 1

    if args.list_orphans:
        return _cli_list_orphans(journal_dir)

    parser.print_help()
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
