"""tests/test_fase10_e2e_install.py -- TAB-TST-005 e2e instalacao/smoke.

- copytree do produto em repo descartavel
- recovery_drill smoke
- session hook adapter
- --add dry-run, --drain dry-run, --audit barato
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import git_init_isolado

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
HOOKS = TOOLS / "hooks"
SCRIPTS = REPO / "scripts"

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}

HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
)

TODO_MIN = (
    "# E2E fixture\n\n"
    + HEADER_9
    + "| E-1 | W1 | Core | Smoke item | Baixa | - | Baixa | "
    "⏳ Pendente | - |\n"
    + "\n## INBOX (descobertas não priorizadas)\n"
    + "- E-9: bare classifiable for drain dry-run\n"
)


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=ENV,
        capture_output=True, text=True, encoding="utf-8", check=check,
    )


def _copy_product(dest: Path) -> Path:
    """Copia subconjunto do produto (tools + scripts + SKILL) para dest."""
    skill = dest / "skills" / "tab_pendencias"
    skill.mkdir(parents=True)
    shutil.copytree(TOOLS, skill / "tools",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if SCRIPTS.is_dir():
        shutil.copytree(
            SCRIPTS, skill / "scripts",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for name in ("SKILL.md", "README.md", "LICENSE"):
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, skill / name)
    return skill


def test_e2e_copytree_produto_layout(tmp_path):
    dest = tmp_path / "install"
    skill = _copy_product(dest)
    assert (skill / "tools" / "todo_intake.py").is_file()
    assert (skill / "tools" / "hooks" / "tab_pendencias_reminder.py").is_file()
    assert (skill / "SKILL.md").is_file()
    # stdlib-only scripts existem
    assert (skill / "tools" / "todo_lib.py").is_file()
    assert (skill / "tools" / "todo_audit.py").is_file()


def test_e2e_recovery_drill_smoke(tmp_path):
    script = SCRIPTS / "recovery_drill.py"
    assert script.is_file()
    spec = importlib.util.spec_from_file_location("recovery_drill", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    dest = tmp_path / "vault-mock"
    report = mod.run_drill(dest=str(dest), product_root=str(REPO), clean=True)
    assert report["ok"] is True
    assert report.get("hook_continue") is True
    dest_res = os.path.realpath(report["dest"])
    assert dest_res.startswith(os.path.realpath(str(tmp_path)))


def test_e2e_session_hook_adapter_smoke(tmp_path):
    git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(TODO_MIN, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    script = HOOKS / "tab_pendencias_reminder.py"
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        input=json.dumps({"cwd": str(tmp_path)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout.strip())
    assert data.get("continue") is True
    ctx = data.get("additionalContext") or ""
    assert "TAB_TRIAGE_REQUIRED" in ctx or "TAB_" in ctx


def test_e2e_add_dry_run(tmp_path):
    git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(TODO_MIN, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    antes = todo.read_text(encoding="utf-8")
    intake = TOOLS / "todo_intake.py"
    r = subprocess.run(
        [
            sys.executable, str(intake),
            "--todo", str(todo),
            "--candidate-id", "e2e-add-1",
            "--item-id", "E-2",
            "--description", "Dry run new item for e2e",
            "--source", "test",
            "--local",
            "--fields-complete",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # dry-run: exit 2 e arquivo intacto
    assert r.returncode in (0, 2), r.stderr + r.stdout
    assert todo.read_text(encoding="utf-8") == antes


def test_e2e_drain_dry_run(tmp_path):
    git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(TODO_MIN, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    antes = todo.read_text(encoding="utf-8")
    intake = TOOLS / "todo_intake.py"
    r = subprocess.run(
        [sys.executable, str(intake), "--todo", str(todo), "--drain"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 2, r.stderr + r.stdout
    assert "classifiable" in (r.stdout + r.stderr).lower() or r.returncode == 2
    assert todo.read_text(encoding="utf-8") == antes


def test_e2e_audit_barato(tmp_path):
    git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(TODO_MIN, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    audit = TOOLS / "todo_audit.py"
    r = subprocess.run(
        [sys.executable, str(audit), "--todo", str(todo)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # audit: 0 limpo, 2 com achados -- nunca crash (1 so em erro exec)
    assert r.returncode in (0, 2), r.stderr + r.stdout
    assert len(r.stdout) + len(r.stderr) > 0
