#!/usr/bin/env python3
# scripts/recovery_drill.py -- mock vault + smoke do hook (TAB-VAULT-005)
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
Recovery drill offline (TAB-VAULT-005).

Monta um vault **sintetico** em ``dest`` (default ``/var/tmp/tab-pendencias-recovery-drill``):

1. Copia templates do produto + adapter do hook sob
   ``dest/skills/tab_pendencias/...`` (sem clonar rede).
2. Escreve ``settings.sanitized.json`` a partir do snippet (paths relativos).
3. Smoke do hook com stdin JSON cujo ``cwd`` aponta para um projeto mock
   **dentro** de ``dest``.
4. Assert: o hook resolveu so arquivos sob ``dest`` (nada em /home do host
   fora do dest; o command do settings e relativo ao root do mock).

stdlib only. Nao precisa de git clone real de claude-memory (isso e o
drill de bump no vault; aqui o produto prova o layout e o path hygiene).

Uso::

    python3 scripts/recovery_drill.py
    python3 scripts/recovery_drill.py --dest /var/tmp/meu-drill
    python3 scripts/recovery_drill.py --dest /tmp/x --product-root .
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_DEST = "/var/tmp/tab-pendencias-recovery-drill"

# Arquivos minimos do produto que o drill precisa enxergar no mock.
_PRODUCT_COPY = (
    "tools/hooks/tab_pendencias_reminder.py",
    "tools/session_signals.py",
    "tools/todo_lib.py",
    "templates/vault/settings.sanitized.hook-snippet.json",
    "templates/vault/CLAUDE.md.fragment.md",
    "templates/vault/tabela-pendencias-frescor.overlay.md",
    "templates/agents/implementer-discovery-contract.md",
    "SKILL.md",
    "references/frescor-da-tabela.md",
)


class RecoveryDrillError(Exception):
    """Falha de setup ou de assercao do drill."""


def product_root_from_here() -> Path:
    """Raiz do produto: pai de scripts/."""
    return Path(__file__).resolve().parent.parent


def _copy_product_tree(product: Path, skill_root: Path) -> list[str]:
    """Copia arquivos listados; devolve paths relativos copiados."""
    copied: list[str] = []
    for rel in _PRODUCT_COPY:
        src = product / rel
        if not src.is_file():
            raise RecoveryDrillError(f"produto incompleto: falta {rel}")
        dst = skill_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied


def _write_settings(dest: Path) -> Path:
    snippet = (
        dest
        / "skills"
        / "tab_pendencias"
        / "templates"
        / "vault"
        / "settings.sanitized.hook-snippet.json"
    )
    data = json.loads(snippet.read_text(encoding="utf-8"))
    # Remove meta; settings real nao precisa de _comment.
    data.pop("_comment", None)
    out = dest / "settings.sanitized.json"
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return out


def _assert_settings_paths_relative(settings_path: Path, dest: Path) -> None:
    text = settings_path.read_text(encoding="utf-8")
    if "/home/" in text or "$HOME" in text or "\\" in text.replace("\\n", ""):
        # barra invertida em JSON escape e ok; path Windows absoluto nao.
        if "/home/" in text or "$HOME" in text:
            raise RecoveryDrillError(
                "settings sanitizado contem path absoluto de maquina "
                f"({settings_path})"
            )
    data = json.loads(text)
    commands: list[str] = []

    def _walk(obj):
        if isinstance(obj, dict):
            if "command" in obj and isinstance(obj["command"], str):
                commands.append(obj["command"])
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(data)
    if not commands:
        raise RecoveryDrillError("settings sem nenhum command de hook")
    for cmd in commands:
        if cmd.startswith("/") or cmd.startswith("~"):
            raise RecoveryDrillError(f"command absoluto proibido: {cmd!r}")
        # deve citar o path relativo do adapter no submodulo
        if "skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py" not in cmd:
            raise RecoveryDrillError(
                "command nao aponta para o adapter do produto: "
                f"{cmd!r}"
            )
        # o arquivo tem de existir sob dest
        rel = "skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py"
        hook_file = dest / rel
        if not hook_file.is_file():
            raise RecoveryDrillError(f"hook ausente no mock: {hook_file}")
        # path resolvido deve ficar dentro de dest
        resolved = hook_file.resolve()
        dest_res = dest.resolve()
        try:
            resolved.relative_to(dest_res)
        except ValueError as exc:
            raise RecoveryDrillError(
                f"hook resolve fora do dest: {resolved} not in {dest_res}"
            ) from exc


def _mock_project(dest: Path) -> Path:
    """Projeto minimo com TODO limpo sob dest (cwd do smoke)."""
    proj = dest / "mock-project"
    proj.mkdir(parents=True, exist_ok=True)
    todo = proj / "TODO.md"
    todo.write_text(
        "# TODO mock\n\n"
        "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
        "Dificuldade | Status | Estado Auditado |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| M-1 | W1 | Core | Mock item | Baixa | — | Baixa | "
        "⏳ Pendente | — |\n",
        encoding="utf-8",
        newline="\n",
    )
    return proj


def smoke_hook(dest: Path, project: Path) -> dict:
    """Roda o adapter com PYTHONPATH = tools do mock; cwd = project."""
    tools = dest / "skills" / "tab_pendencias" / "tools"
    hook = tools / "hooks" / "tab_pendencias_reminder.py"
    env = os.environ.copy()
    # Garante import flat (session_signals, todo_lib) so do mock.
    env["PYTHONPATH"] = str(tools) + os.pathsep + env.get("PYTHONPATH", "")
    stdin = json.dumps({"cwd": str(project)}, ensure_ascii=False)
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(project),
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RecoveryDrillError(
            f"hook exit {proc.returncode}: stderr={proc.stderr!r}"
        )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise RecoveryDrillError(
            f"hook stdout nao-JSON: {proc.stdout!r}"
        ) from exc
    if out.get("continue") is not True:
        raise RecoveryDrillError(f"hook nao devolveu continue=true: {out!r}")
    return out


def run_drill(
    dest: str | os.PathLike | None = None,
    product_root: str | os.PathLike | None = None,
    *,
    clean: bool = True,
) -> dict:
    """Executa o drill. Devolve relatorio dict; levanta RecoveryDrillError."""
    product = Path(product_root) if product_root else product_root_from_here()
    product = product.resolve()
    dest_path = Path(dest) if dest else Path(DEFAULT_DEST)
    if clean and dest_path.exists():
        shutil.rmtree(dest_path)
    dest_path.mkdir(parents=True, exist_ok=True)
    dest_path = dest_path.resolve()

    skill_root = dest_path / "skills" / "tab_pendencias"
    skill_root.mkdir(parents=True, exist_ok=True)
    copied = _copy_product_tree(product, skill_root)
    settings = _write_settings(dest_path)
    _assert_settings_paths_relative(settings, dest_path)
    project = _mock_project(dest_path)
    # projeto tambem tem de ficar dentro de dest
    try:
        project.resolve().relative_to(dest_path)
    except ValueError as exc:
        raise RecoveryDrillError("mock project fora do dest") from exc

    hook_out = smoke_hook(dest_path, project)

    # prova de semântica nova: SKILL copiada menciona intake / exception
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    if "exception queue" not in skill_text.lower() and "intake" not in skill_text.lower():
        raise RecoveryDrillError(
            "SKILL copiada parece sem semantica de intake/exception queue"
        )

    return {
        "ok": True,
        "dest": str(dest_path),
        "product_root": str(product),
        "copied": copied,
        "settings": str(settings),
        "project": str(project),
        "hook_continue": True,
        "hook_has_context": bool(hook_out.get("additionalContext")),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Recovery drill mock vault (TAB-VAULT-005)")
    p.add_argument(
        "--dest",
        default=DEFAULT_DEST,
        help=f"diretorio do mock vault (default {DEFAULT_DEST})",
    )
    p.add_argument(
        "--product-root",
        default=None,
        help="raiz do produto tab_pendencias (default: pai de scripts/)",
    )
    p.add_argument(
        "--keep",
        action="store_true",
        help="nao apagar dest existente antes de montar",
    )
    p.add_argument("--json", action="store_true", help="relatorio JSON em stdout")
    args = p.parse_args(argv)
    try:
        report = run_drill(
            dest=args.dest,
            product_root=args.product_root,
            clean=not args.keep,
        )
    except RecoveryDrillError as exc:
        print(f"recovery_drill: FALHA -- {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"recovery_drill: OK -- dest={report['dest']} "
            f"copied={len(report['copied'])} hook_continue=true"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
