#!/usr/bin/env python3
# scripts/dogfood_metrics.py -- metricas de cutover / dogfood (TAB-CUT-002/004)
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
Metricas de dogfood / cutover (TAB-CUT-002, TAB-CUT-004).

Le a TODO.md do cwd (ou ``--todo``), imprime contagens de INBOX e os
sinais de ``session_signals.collect_signals``, e sai com:

- exit 0 se ``classifiable == 0`` (criterio dogfood verde);
- exit 2 se ``classifiable > 0`` (metrica / canary sujo -- **nao** e hard
  fail de CI generico; so sinaliza residual classifiable).

stdlib only. Read-only: nunca escreve no TODO.

Uso::

    python3 scripts/dogfood_metrics.py
    python3 scripts/dogfood_metrics.py --todo /path/to/TODO.md
    python3 scripts/dogfood_metrics.py --json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path


def product_root_from_here() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_tools_on_path(product: Path) -> None:
    tools = str(product / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)


def _oldest_age_days(entries, now: datetime.date) -> int | None:
    """Idade em dias do residual com ``since`` mais antigo; None se vazio."""
    oldest = None
    for e in entries:
        if e.get("classifiable"):
            continue
        since = ((e.get("triage") or {}).get("fields") or {}).get("since")
        if not since:
            continue
        try:
            d = datetime.date.fromisoformat(str(since))
        except (TypeError, ValueError):
            continue
        if oldest is None or d < oldest:
            oldest = d
    if oldest is None:
        return None
    return (now - oldest).days


def collect_metrics(todo_path: str, *, now=None, now_ts=None) -> dict:
    """Monta o dict de metricas a partir de um path de TODO.md."""
    import todo_lib as L
    import session_signals as SS

    if now is None:
        now = datetime.date.today()
    todo_path = os.path.abspath(todo_path)
    root = os.path.dirname(todo_path)

    try:
        with open(todo_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return {
            "ok": False,
            "error": f"leitura_todo:{type(exc).__name__}:{exc}",
            "todo": todo_path,
        }

    tbl = L.parse_table(text)
    items = tbl["items"] if tbl else []
    entries = L.inbox_entries(text)
    classifiable = [e for e in entries if e.get("classifiable")]
    residual = [e for e in entries if not e.get("classifiable")]
    n_verif = sum(1 for it in items if L.is_awaiting_verification(it["status"]))
    n_pending = sum(
        1 for it in items
        if (it["status"] or "").strip().startswith("⏳")
        or (it["status"] or "").strip().startswith("🔄")
    )

    report = SS.collect_signals(root, now=now, now_ts=now_ts)
    signals = {
        s.id: {"active": s.active, "reasons": list(s.reasons)}
        for s in report.signals
    }
    active = [s.id for s in report.signals if s.active]

    return {
        "ok": True,
        "todo": todo_path,
        "inbox_total": len(entries),
        "classifiable": len(classifiable),
        "residual": len(residual),
        "oldest_age_days": _oldest_age_days(entries, now),
        "n_items": len(items),
        "n_verif": n_verif,
        "n_pending": n_pending,
        "signals": signals,
        "signals_active": active,
        "metrics": dict(report.metrics),
    }


def format_text(data: dict) -> str:
    if not data.get("ok"):
        return f"erro: {data.get('error', 'desconhecido')}\n"
    lines = [
        "=== tab_pendencias dogfood_metrics ===",
        f"todo: {data['todo']}",
        f"inbox_total: {data['inbox_total']}",
        f"classifiable: {data['classifiable']}",
        f"residual: {data['residual']}",
        f"oldest_age_days: {data['oldest_age_days']}",
        f"n_items: {data['n_items']}",
        f"n_verif: {data['n_verif']}",
        f"n_pending: {data['n_pending']}",
        "signals_active:",
    ]
    if data["signals_active"]:
        for sid in data["signals_active"]:
            reasons = data["signals"][sid].get("reasons") or []
            if reasons:
                lines.append(f"  {sid} {','.join(reasons)}")
            else:
                lines.append(f"  {sid}")
    else:
        lines.append("  (none)")
    # Criterio dogfood (TAB-CUT-002): classifiable == 0
    if data["classifiable"] == 0:
        lines.append("dogfood: classifiable==0 OK")
    else:
        lines.append(
            f"dogfood: classifiable={data['classifiable']} "
            "(drenar com --drain antes do cutover)"
        )
    return "\n".join(lines) + "\n"


def resolve_todo(todo_arg: str | None, cwd: str | None = None) -> str | None:
    """Resolve path do TODO.md: --todo explicito ou find_todo no cwd."""
    import todo_lib as L

    if todo_arg:
        p = os.path.abspath(todo_arg)
        return p if os.path.isfile(p) else None
    root = cwd if cwd is not None else os.getcwd()
    return L.find_todo(root)


def main(argv: list[str] | None = None) -> int:
    product = product_root_from_here()
    _ensure_tools_on_path(product)

    parser = argparse.ArgumentParser(
        description=(
            "Metricas de dogfood/cutover da TODO.md "
            "(exit 0 se classifiable==0, exit 2 se classifiable>0)."
        ),
    )
    parser.add_argument(
        "--todo",
        default=None,
        help="Caminho do TODO.md (default: TODO.md do cwd via find_todo)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite JSON em stdout em vez do formato texto",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help=argparse.SUPPRESS,  # testes
    )
    args = parser.parse_args(argv)

    todo = resolve_todo(args.todo, cwd=args.cwd)
    if not todo:
        msg = "erro: TODO.md nao encontrado (passe --todo ou rode no projeto)\n"
        sys.stderr.write(msg)
        return 1

    data = collect_metrics(todo)
    if not data.get("ok"):
        sys.stderr.write(format_text(data) if not args.json else
                         json.dumps(data, ensure_ascii=False) + "\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(format_text(data))

    # exit 0 = classifiable limpo; 2 = metrica suja (nao erro de execucao)
    if data["classifiable"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
