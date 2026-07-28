"""Contrato de CLI (CLI-1, D-6): argparse + --help nos 3 scripts; exit codes
fixos (0 = ok/sem achados, 1 = erro de execucao, 2 = achados); flag
desconhecida nunca e engolida em silencio. `todo_freshness.py` e a EXCECAO
que continua warn-only, exit 0 SEMPRE (invariante de contrato com quem
instalou o hook: um exit != 0 quebraria o commit).

Testado via subprocess (a interface real que o CI e o usuario usam), nao so
chamando main()/run() em processo -- e o proprio argparse so dispara
SystemExit em erro/--help, que subprocess captura como exit code de verdade.
"""
import os
import subprocess
import sys

from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
SYNC = os.path.join(TOOLS_DIR, "todo_sync.py")
HEALTH = os.path.join(TOOLS_DIR, "todo_health.py")
FRESH = os.path.join(TOOLS_DIR, "todo_freshness.py")

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _run(script, args, cwd):
    return subprocess.run([sys.executable, script, *args], cwd=cwd,
                          capture_output=True, text=True)


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, env=_ENV, capture_output=True,
                   check=True)


def _repo(tmp_path, status_v12="⏳ Pendente"):
    """Repo git com TODO.md de 1 item (V-12); devolve (root, todo_path, base_sha).

    HOOKISO-1: usa `git_init_isolado` (conftest.py), nao `git init` cru --
    esta maquina tem `core.hooksPath` GLOBAL apontando para
    `~/.claude/githooks/`, e sem a protecao cada commit feito aqui
    dispararia o hook AMBIENTE de verdade por baixo dos panos."""
    _git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(
        "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
        "Dificuldade | Status | Estado Auditado |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        f"| V-12 | W2 | Auth | Login | Alta | — | Média | {status_v12} | — |\n",
        encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "tabela")
    base = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                          cwd=tmp_path, capture_output=True, text=True
                          ).stdout.split()[0]
    return tmp_path, todo, base


# ------------------------------- --help (0) -----------------------------------

def test_sync_help_exit0_e_documenta_flags(tmp_path):
    r = _run(SYNC, ["--help"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "--apply" in r.stdout and "--since" in r.stdout


def test_health_help_exit0(tmp_path):
    r = _run(HEALTH, ["--help"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "-h" in r.stdout or "--help" in r.stdout


def test_freshness_help_exit0(tmp_path):
    r = _run(FRESH, ["--help"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "-h" in r.stdout or "--help" in r.stdout


# --------------------- flag desconhecida = erro, nunca silencioso -------------

def test_sync_flag_desconhecida_erro_e_nao_aplica(tmp_path):
    root, todo, base = _repo(tmp_path)
    (root / "auth.py").write_text("x")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: termina login V-12")
    antes = todo.read_text(encoding="utf-8")
    r = _run(SYNC, ["--aply", "--since", base], cwd=root)  # typo proposital
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""
    assert todo.read_text(encoding="utf-8") == antes  # nao mudou nada


def test_health_flag_desconhecida_erro(tmp_path):
    root, todo, base = _repo(tmp_path)
    r = _run(HEALTH, ["--aply"], cwd=root)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""


def test_freshness_flag_desconhecida_continua_exit0(tmp_path):
    """Excecao de contrato: mesmo flag invalida nao pode mudar o exit code."""
    root, todo, base = _repo(tmp_path)
    r = _run(FRESH, ["--aply"], cwd=root)
    assert r.returncode == 0, (r.stdout, r.stderr)


# ------------------------------ todo_sync: exit codes --------------------------

def test_sync_exit0_sem_achados(tmp_path):
    root, todo, base = _repo(tmp_path)
    r = _run(SYNC, ["--since", base], cwd=root)  # nada citado desde a base
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_sync_exit2_com_achados_modo_proposta(tmp_path):
    root, todo, base = _repo(tmp_path)
    (root / "auth.py").write_text("x")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: termina login V-12")
    r = _run(SYNC, ["--since", base], cwd=root)  # sem --apply
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert todo.read_text(encoding="utf-8").count("⏳ Pendente") == 1  # nao escreveu


def test_sync_exit2_com_achados_modo_apply(tmp_path):
    root, todo, base = _repo(tmp_path)
    (root / "auth.py").write_text("x")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: termina login V-12")
    r = _run(SYNC, ["--apply", "--since", base], cwd=root)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "🔍 Pendente verificação" in todo.read_text(encoding="utf-8")


def test_sync_exit1_fora_de_repo(tmp_path):
    r = _run(SYNC, [], cwd=tmp_path)  # tmp_path puro, sem git init
    assert r.returncode == 1, (r.stdout, r.stderr)


# ------------------------------ todo_health: exit codes ------------------------

def test_health_exit0_sem_item_preso_em_verificacao(tmp_path):
    root, todo, base = _repo(tmp_path, status_v12="✅ Concluído")
    r = _run(HEALTH, [], cwd=root)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_health_exit2_com_item_preso_em_verificacao(tmp_path):
    root, todo, base = _repo(tmp_path, status_v12="🔍 Pendente verificação")
    r = _run(HEALTH, [], cwd=root)
    assert r.returncode == 2, (r.stdout, r.stderr)


def test_health_exit1_fora_de_repo(tmp_path):
    r = _run(HEALTH, [], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)


def test_health_exit0_repo_git_sem_todo_md(tmp_path):
    """Repo git valido sem TODO.md: estado valido (nada a reportar), NAO erro
    -- consistente com todo_sync.py, que ja trata 'sem TODO.md' como exit 0."""
    _git_init_isolado(tmp_path)
    (tmp_path / "readme.txt").write_text("x")
    _git(tmp_path, "add", "readme.txt")
    _git(tmp_path, "commit", "-qm", "init")
    r = _run(HEALTH, [], cwd=tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)


# ------------------------------ todo_freshness: sempre 0 ------------------------

def test_freshness_exit0_fora_de_repo(tmp_path):
    r = _run(FRESH, [], cwd=tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_freshness_exit0_mesmo_com_aviso_real(tmp_path):
    """Ha aviso de frescor de verdade (commit cita item ainda pendente), mas
    o exit continua 0 -- e o hook post-commit que nunca pode bloquear."""
    root, todo, base = _repo(tmp_path)
    (root / "auth.py").write_text("x")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: termina login V-12")
    r = _run(FRESH, [], cwd=root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "V-12" in r.stderr  # o aviso existe...
    # ...mas nao muda o exit code (warn-only, invariante de contrato).


# ------------------------------ HOOKISO-1: prova da protecao -------------------
#
# Esta maquina tem `core.hooksPath` GLOBAL (`~/.gitconfig`) apontando para
# `~/.claude/githooks/` -- sem `git_init_isolado` (conftest.py), o commit
# abaixo (toca codigo E cita V-12, o gatilho mais forte que existe) faria o
# hook AMBIENTE de verdade escrever em `$GIT_DIR/todo-freshness.log` por
# baixo dos panos. Prova positiva: o arquivo nao existe depois do commit.
# Continua valida (trivialmente) em maquinas/CI sem esse hook global
# configurado -- o que ela garante e que a protecao NUNCA introduz o
# efeito colateral, com ou sem hook ambiente presente.

def test_hookiso1_hook_ambiente_nao_escreve_log_dentro_da_fixture(tmp_path):
    root, todo, base = _repo(tmp_path)
    (root / "auth.py").write_text("x")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: termina login V-12")

    gd = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root,
                        capture_output=True, text=True).stdout.strip()
    gd = gd if os.path.isabs(gd) else os.path.join(str(root), gd)
    log = os.path.join(gd, "todo-freshness.log")
    assert not os.path.exists(log), (
        "o hook AMBIENTE (core.hooksPath global) escreveu dentro do repo de "
        "teste -- a protecao HOOKISO-1 (git_init_isolado) falhou"
    )


def test_hookiso1_core_hookspath_local_sobrescreve_o_global(tmp_path):
    """Prova estrutural, independente de o hook ambiente existir ou nao
    nesta maquina: dentro da fixture, `core.hooksPath` resolve para um
    diretorio LOCAL ao repo de teste, nunca para o valor global."""
    root, todo, base = _repo(tmp_path)
    global_path = subprocess.run(
        ["git", "config", "--global", "--get", "core.hooksPath"],
        capture_output=True, text=True
    ).stdout.strip()
    local_path = subprocess.run(
        ["git", "config", "core.hooksPath"], cwd=root,
        capture_output=True, text=True
    ).stdout.strip()
    assert local_path != "", "core.hooksPath local nao foi configurado na fixture"
    assert str(root) in local_path, (
        f"core.hooksPath local ({local_path!r}) nao aponta para dentro do "
        f"repo de teste ({root!r})"
    )
    if global_path:  # so faz sentido comparar se esta maquina tem hook global
        assert local_path != global_path, (
            "core.hooksPath dentro da fixture ainda resolve para o global "
            f"({global_path!r}) -- a protecao HOOKISO-1 nao sobrescreveu"
        )
