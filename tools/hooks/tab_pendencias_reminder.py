#!/usr/bin/env python3
# tools/hooks/tab_pendencias_reminder.py -- adapter Claude-Code (TAB-HOOK-004)
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
Adapter de hook Claude Code para o motor de sinais de frescor.

Contrato (TAB-HOOK-001..004):
  - stdin JSON -> stdout JSON `{continue: true, additionalContext?: str}`
  - JSON invalido/vazio: cwd = getcwd(), fail-open
  - exit SEMPRE 0 (nunca bloqueia a sessao)
  - zero regra de negocio propria: so chama `session_signals.collect_signals`
  - offline, sem LLM, sem rede, sem escrever TODO.md

A logica vive em `tools/session_signals.py`. Este arquivo e wiring.
"""
from __future__ import annotations

import json
import os
import sys

# tools/ e o pai de tools/hooks/ -- garante import flat do monorepo.
# realpath: quando o hook e invocado via symlink (ex.: ~/.grok/hooks/scripts/),
# abspath aponta para o link e o parent deixa de ser tools/ -- o import quebra.
_HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
_TOOLS_DIR = os.path.dirname(_HOOKS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import session_signals as SS  # noqa: E402


def parse_hook_stdin(raw):
    """Parse do stdin do Claude Code. Fail-open.

    Devolve dict com pelo menos `cwd` (string). JSON invalido, vazio ou
    nao-dict -> cwd = os.getcwd().
    """
    cwd_fallback = os.getcwd()
    if raw is None:
        return {"cwd": cwd_fallback}
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            return {"cwd": cwd_fallback}
    text = raw if isinstance(raw, str) else str(raw)
    text = text.strip()
    if not text:
        return {"cwd": cwd_fallback}
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"cwd": cwd_fallback}
    if not isinstance(data, dict):
        return {"cwd": cwd_fallback}
    cwd = (data.get("cwd") or cwd_fallback or "").strip()
    if not cwd or not os.path.isdir(cwd):
        cwd = cwd_fallback
    data = dict(data)
    data["cwd"] = cwd
    return data


def build_hook_output(report):
    """Monta o JSON de resposta. Sempre continue=true."""
    out = {"continue": True}
    human = SS.format_human(report)
    machine = SS.format_machine(report)
    if human or machine:
        # machine (IDs) primeiro para a thread parsear; prosa em seguida.
        ctx_parts = []
        if machine:
            ctx_parts.append(machine)
        if human:
            ctx_parts.append(human)
        out["additionalContext"] = "\n".join(ctx_parts)
    return out


def run_hook(stdin_text=None, now=None, now_ts=None, cfg=None):
    """Nucleo testavel. Nunca levanta; devolve o dict de saida."""
    try:
        data = parse_hook_stdin(stdin_text)
        root = data.get("cwd") or os.getcwd()
        report = SS.collect_signals(root, now=now, cfg=cfg, now_ts=now_ts)
        return build_hook_output(report)
    except Exception:
        return {"continue": True}


def main(argv=None):
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    out = run_hook(raw)
    try:
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.write("\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
