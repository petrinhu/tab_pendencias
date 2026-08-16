"""tests/test_install_recipe_e2e.py -- HOOKDOC-1: a receita de instalacao do
`tools/README.md` executada AO PE DA LETRA, com um `git commit` de verdade
(nao chamando `todo_freshness.py` via subprocess como os outros e2e fazem).

Motivacao: o defeito reportado (`HOOKDOC-1`) nunca teria aparecido em
`tests/test_todo_freshness_e2e.py`, porque aqueles testes invocam o script
Python diretamente -- nunca passam pelo shim `post-commit` nem pelo
`core.hooksPath`, que e exatamente onde a receita antiga quebrava (o shim
procurava `todo_freshness.py` um nivel acima de `.githooks/`, mas a receita
copiava tudo para DENTRO de `.githooks/`). Este arquivo copia os arquivos
reais do repo para dentro de um repositorio git temporario seguindo os
passos exatos de cada secao do README, e comita de verdade -- se a receita
divergir do layout que o shim espera, o commit sai sem o aviso e o teste
falha, exatamente como aconteceu ao vivo.

Nao reimplementa o parsing do Markdown (frágil, divergiria da prosa sem
avisar) -- os comandos aqui espelham literalmente os blocos de codigo do
README; ao mudar a receita la, mude aqui tambem (o `git show --stat`/review
do PR pega a divergencia).
"""
import os
import shutil
import stat
import subprocess

from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
HOOKS_SRC = os.path.join(TOOLS_DIR, "hooks")

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

_HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=_ENV,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _row(iid, status):
    return (f"| {iid} | W1 | Grupo | Descrição | Média | — | Baixa | "
            f"{status} | — |\n")


def _log_path(root):
    gd = _git(root, "rev-parse", "--git-dir").stdout.strip()
    gd = gd if os.path.isabs(gd) else os.path.join(str(root), gd)
    return os.path.join(gd, "todo-freshness.log")


def _exec_bit(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# Secao "Por projeto (recomendado)" do tools/README.md, passo a passo.
# ---------------------------------------------------------------------------

def test_receita_por_projeto_do_readme_dispara_o_hook_de_verdade(tmp_path):
    root = tmp_path
    _git_init_isolado(root)

    # mkdir -p .githooks/hooks
    hooks_dir = root / ".githooks" / "hooks"
    hooks_dir.mkdir(parents=True)

    # cp tools/hooks/post-commit tools/hooks/_chain.sh .githooks/hooks/
    shutil.copy(os.path.join(HOOKS_SRC, "post-commit"), hooks_dir / "post-commit")
    shutil.copy(os.path.join(HOOKS_SRC, "_chain.sh"), hooks_dir / "_chain.sh")

    # cp tools/todo_freshness.py tools/todo_lib.py .githooks/
    shutil.copy(os.path.join(TOOLS_DIR, "todo_freshness.py"), root / ".githooks" / "todo_freshness.py")
    shutil.copy(os.path.join(TOOLS_DIR, "todo_lib.py"), root / ".githooks" / "todo_lib.py")

    # chmod +x .githooks/hooks/post-commit
    _exec_bit(hooks_dir / "post-commit")

    # git config core.hooksPath .githooks/hooks
    _git(root, "config", "core.hooksPath", ".githooks/hooks")

    (root / "TODO.md").write_text(_HEADER_9 + _row("V-12", "⏳ Pendente"), encoding="utf-8")
    (root / "auth.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "TODO.md", "auth.py", ".githooks")
    commit = _git(root, "commit", "-qm", "feat: termina login V-12")

    # O hook post-commit NUNCA bloqueia (warn-only): o commit tem que ter
    # sido aceito de qualquer forma. O que prova que a receita funciona e o
    # aviso ter sido emitido -- se o shim nao acha todo_freshness.py, ele
    # falha em silencio (o proprio contrato warn-only engole o erro), entao
    # a prova real e a linha do log de adesao, nao so o exit code do commit.
    assert commit.returncode == 0

    log = open(_log_path(root), encoding="utf-8").read().splitlines()
    assert len(log) == 1, (
        "hook nao rodou -- a receita do README nao esta produzindo o layout "
        "que tools/hooks/post-commit espera (script um nivel acima do shim)")
    assert "code=1 cited=1 warns=1" in log[0]


# ---------------------------------------------------------------------------
# Secao "Global (todos os repositorios da maquina)" do tools/README.md.
#
# NUNCA usa `git config --global` de verdade (mudaria a maquina do lider) --
# em vez disso, aponta core.hooksPath LOCAL para o tools/hooks/ real deste
# clone, que e o mesmo efeito de resolucao de caminho que o --global teria.
# ---------------------------------------------------------------------------

def test_receita_global_do_readme_aponta_direto_pro_clone_sem_copiar_nada(tmp_path):
    root = tmp_path
    _git_init_isolado(root)
    _git(root, "config", "core.hooksPath", HOOKS_SRC)

    (root / "TODO.md").write_text(_HEADER_9 + _row("V-99", "⏳ Pendente"), encoding="utf-8")
    (root / "outro.py").write_text("y = 2\n", encoding="utf-8")
    _git(root, "add", "TODO.md", "outro.py")
    commit = _git(root, "commit", "-qm", "feat: outra coisa V-99")
    assert commit.returncode == 0

    log = open(_log_path(root), encoding="utf-8").read().splitlines()
    assert len(log) == 1
    assert "code=1 cited=1 warns=1" in log[0]


def test_receita_global_no_op_silencioso_em_repo_sem_todo_md(tmp_path):
    """A mesma secao promete no-op silencioso onde nao ha TODO.md."""
    root = tmp_path
    _git_init_isolado(root)
    _git(root, "config", "core.hooksPath", HOOKS_SRC)

    (root / "x.py").write_text("z = 3\n", encoding="utf-8")
    _git(root, "add", "x.py")
    commit = _git(root, "commit", "-qm", "chore: sem TODO.md")
    assert commit.returncode == 0
    assert commit.stdout.strip() == "" and commit.stderr.strip() == ""
