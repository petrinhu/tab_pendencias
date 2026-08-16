#!/usr/bin/env python3
# tools/concurrent_inbox.py -- inbox/ por descoberta entre sessoes (TAB-CONC-002)
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
concurrent_inbox -- fallback de concorrencia entre sessoes/worktrees.

NAO e backlog normal. Quando nao ha orquestrador comum e duas sessoes
descobrem itens em paralelo, cada descoberta vira um arquivo:

  inbox/YYYYMMDD-HHMMSS-<session>-<slug>.md

O dreno automatico (session principal / --drain / bridge+intake) consome
esses arquivos. Health emite TAB_CONCURRENT_INBOX_PRESENT se houver .md.

API:
  write_discovery(root, session_id, slug, body_md) -> path
  list_pending(root) -> list[path]
  read_discovery(path) -> dict  (parse DISCOVERED_WORK se presente)

stdlib only; encoding utf-8 e newline explicitos.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

_WINDOWS_FORBIDDEN = '<>:"/\\|?*'
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
_MAX_SLUG = 60
_INBOX_DIRNAME = "inbox"

# reusa o parser mecanico se disponivel (mesmo processo tools/)
try:
    import intake_agent_bridge as _bridge
except ImportError:  # pragma: no cover - import flat em testes
    _bridge = None

_FRONTMATTER = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL
)


class ConcurrentInboxError(Exception):
    """Erro de uso deste modulo."""


def inbox_dir(root: str) -> str:
    return os.path.join(os.path.abspath(root), _INBOX_DIRNAME)


def sanitize_slug(raw: str) -> str:
    """Slug seguro para nome de arquivo em Windows e POSIX."""
    text = (raw or "").strip()
    out = []
    for ch in text:
        cp = ord(ch)
        if ch in _WINDOWS_FORBIDDEN or cp < 0x20 or ch.isspace():
            out.append("-")
        elif ch in "._-":
            out.append(ch)
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    safe = "".join(out)
    while "--" in safe:
        safe = safe.replace("--", "-")
    safe = safe.strip(".-_") or "item"
    if safe.upper() in _RESERVED:
        safe = f"{safe}_"
    if len(safe) > _MAX_SLUG:
        safe = safe[:_MAX_SLUG].rstrip(".-_") or "item"
    return safe


def sanitize_session(raw: str) -> str:
    return sanitize_slug(raw or "session")


def _timestamp_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def write_discovery(
    root: str,
    session_id: str,
    slug: str,
    body_md: str,
    *,
    timestamp: str | None = None,
) -> str:
    """Grava `inbox/YYYYMMDD-HHMMSS-<session>-<slug>.md` e devolve o path.

    `timestamp` so para testes (formato YYYYMMDD-HHMMSS). Se o path colidir,
    acrescenta sufixo -2, -3, ...
    """
    if root is None or not str(root).strip():
        raise ConcurrentInboxError("root obrigatorio")
    body = body_md if body_md is not None else ""
    sess = sanitize_session(session_id)
    slug_s = sanitize_slug(slug)
    ts = timestamp or _timestamp_compact()
    # so digitos e hifen no ts
    ts = re.sub(r"[^0-9-]", "", ts) or _timestamp_compact()

    d = inbox_dir(root)
    os.makedirs(d, mode=0o755, exist_ok=True)

    base = f"{ts}-{sess}-{slug_s}.md"
    path = os.path.join(d, base)
    n = 2
    while os.path.exists(path):
        path = os.path.join(d, f"{ts}-{sess}-{slug_s}-{n}.md")
        n += 1
        if n > 1000:
            raise ConcurrentInboxError(
                f"write_discovery: colisao excessiva em {d!r}"
            )

    # escrita atomica best-effort no mesmo dir
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body if body.endswith("\n") or body == "" else body + "\n")
    os.replace(tmp, path)
    return path


def list_pending(root: str) -> list[str]:
    """Lista paths absolutos de `inbox/*.md` pendentes (ordenados).

    Ignora `*.tmp` e arquivos ocultos. Diretorio ausente = lista vazia.
    """
    d = inbox_dir(root)
    if not os.path.isdir(d):
        return []
    out: list[str] = []
    try:
        names = os.listdir(d)
    except OSError:
        return []
    for name in names:
        if not name.endswith(".md"):
            continue
        if name.startswith("."):
            continue
        if name.endswith(".tmp.md") or name.endswith(".tmp"):
            continue
        full = os.path.join(d, name)
        if os.path.isfile(full):
            out.append(os.path.abspath(full))
    out.sort()
    return out


def count_pending(root: str) -> int:
    return len(list_pending(root))


def _parse_simple_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


def read_discovery(path: str) -> dict:
    """Le um arquivo de descoberta.

    Devolve dict com:
      path, body, frontmatter (dict), discovered (list[dict] do DISCOVERED_WORK)
    Se o corpo tiver blocos DISCOVERED_WORK, `discovered` e preenchido via
    intake_agent_bridge (quando importavel).
    """
    p = os.path.abspath(path)
    try:
        with open(p, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        raise ConcurrentInboxError(f"read_discovery: {exc}") from exc

    meta, body = _parse_simple_frontmatter(text)
    discovered: list[dict] = []
    if _bridge is not None:
        try:
            discovered = _bridge.parse_discovered_work(body or text)
        except Exception:
            discovered = []
    else:
        # fallback minimo: se comecar com DISCOVERED_WORK, devolve o body cru
        if re.search(r"(?m)^DISCOVERED_WORK\s*$", body or text):
            discovered = [{"raw": body or text}]

    return {
        "path": p,
        "body": body if meta else text,
        "frontmatter": meta,
        "discovered": discovered,
        "text": text,
    }
