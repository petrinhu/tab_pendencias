"""tests/test_todo_freshness_e2e.py -- GAP-2: e2e de todo_freshness.main().

O caminho REAL (com `git diff-tree` de verdade contra HEAD, `git log -1
--format=%B` de verdade) nunca tinha sido exercitado -- so o nucleo
(`build_warnings`) era testado com listas de arquivos/mensagens fabricadas
a mao (`tests/test_todo_freshness.py`). Este arquivo monta repositorios git
TEMPORARIOS e descartaveis (`tmp_path` + `git init`) e roda o script de
verdade via subprocess, exatamente como o hook `post-commit` faria.

Invariante inegociavel testado em TODOS os cenarios, inclusive erro:
`todo_freshness` e warn-only -- exit code SEMPRE 0. Um exit != 0 quebraria
o commit de quem instalou o hook.

Documenta tambem, sem tentar consertar (fora do escopo desta fatia -- ver
ENC-1 no TODO.md): a politica atual de engolir QUALQUER excecao de leitura
em silencio.

Nada de rede, nada de sleep: cada teste e determinístico e limpa o proprio
tmp_path (pytest ja faz isso no teardown).
"""
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
FRESH = os.path.join(TOOLS_DIR, "todo_freshness.py")

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

_HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=_ENV,
                          capture_output=True, text=True, check=check)


def _git_init_isolado(cwd):
    """`git init` + desliga hook LOCAL a este repo: esta maquina tem
    `core.hooksPath` GLOBAL apontando para `~/.claude/githooks/` (ver
    `~/.gitconfig`), entao todo commit num repo temporario dispararia o
    hook AMBIENTE de verdade por baixo dos panos -- poluindo
    `$GIT_DIR/todo-freshness.log` e corrompendo a contagem deterministica
    destes testes, alem de rodar uma versao possivelmente DIFERENTE do
    script sob teste (ver MIG-DIFF na INBOX do TODO.md). Um
    `core.hooksPath` LOCAL (config do proprio repo temporario, NUNCA
    `--global`) para um diretorio vazio sobrescreve o global sem alterar
    nada fora do tmp_path."""
    _git(cwd, "init", "-q")
    hooks_vazio = os.path.join(str(cwd), ".git", "hooks-vazio-teste")
    os.makedirs(hooks_vazio, exist_ok=True)
    _git(cwd, "config", "core.hooksPath", hooks_vazio)


def _row(iid, status):
    return (f"| {iid} | W1 | Grupo | Descrição | Média | — | Baixa | "
            f"{status} | — |\n")


def _run_fresh(cwd):
    return subprocess.run([sys.executable, FRESH], cwd=cwd,
                          capture_output=True, text=True)


def _log_path(root):
    gd = _git(root, "rev-parse", "--git-dir").stdout.strip()
    gd = gd if os.path.isabs(gd) else os.path.join(str(root), gd)
    return os.path.join(gd, "todo-freshness.log")


def _init_repo_com_tabela(tmp_path, status_v12="⏳ Pendente"):
    """Commit RAIZ so com a tabela (nao toca codigo) -- evita de proposito
    o bug de diff-tree/--root documentado mais abaixo em qualquer teste que
    nao seja o proprio teste dedicado a ele."""
    _git_init_isolado(tmp_path)
    (tmp_path / "TODO.md").write_text(
        _HEADER_9 + _row("V-12", status_v12), encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "tabela inicial")
    return tmp_path


# ---------------------------------------------------------------------------
# Commit que toca codigo E cita um ID ainda pendente -> avisa; warn-only.
# ---------------------------------------------------------------------------

def test_e2e_commit_toca_codigo_cita_id_pendente_avisa_status(tmp_path):
    root = _init_repo_com_tabela(tmp_path)
    (root / "auth.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: termina login V-12")

    r = _run_fresh(root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "V-12" in r.stderr and "Status" in r.stderr
    assert "nao citou" not in r.stderr  # citou -- o outro aviso nao dispara

    log = open(_log_path(root), encoding="utf-8").read().splitlines()
    assert len(log) == 1
    assert "code=1 cited=1 warns=1" in log[0]


# ---------------------------------------------------------------------------
# Commit que toca codigo SEM citar nenhum ID -> avisa "nao citou".
# ---------------------------------------------------------------------------

def test_e2e_commit_toca_codigo_sem_citar_id_avisa(tmp_path):
    root = _init_repo_com_tabela(tmp_path)
    (root / "auth.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "auth.py")
    _git(root, "commit", "-qm", "feat: refactor generico")

    r = _run_fresh(root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "nao citou nenhum ID" in r.stderr

    log = open(_log_path(root), encoding="utf-8").read().splitlines()
    assert len(log) == 1
    assert "code=1 cited=0 warns=1" in log[0]


# ---------------------------------------------------------------------------
# Commit so de bookkeeping (so toca TODO.md), sem citar -> silencioso.
# ---------------------------------------------------------------------------

def test_e2e_commit_so_bookkeeping_sem_citar_silencioso(tmp_path):
    root = _init_repo_com_tabela(tmp_path)
    (root / "TODO.md").write_text(
        _HEADER_9 + _row("V-12", "⏳ Pendente") + _row("V-20", "⏳ Pendente"),
        encoding="utf-8")
    _git(root, "add", "TODO.md")
    # mensagem SEM citar nenhum ID de proposito -- senao dispara o aviso #1
    # (cita item pendente), que e o cenario do teste seguinte
    _git(root, "commit", "-qm", "docs(todo): reordena a tabela")

    r = _run_fresh(root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert r.stderr.strip() == ""  # so tocou a tabela, nao ha nada a avisar

    log = open(_log_path(root), encoding="utf-8").read().splitlines()
    assert len(log) == 1
    assert "code=0 cited=0 warns=0" in log[0]


# ---------------------------------------------------------------------------
# Commit de bookkeeping que CITA um ID ja entregue (🔍) -> silencioso.
# ---------------------------------------------------------------------------

def test_e2e_commit_bookkeeping_citando_id_ja_entregue_silencioso(tmp_path):
    root = _init_repo_com_tabela(tmp_path, status_v12="🔍 Pendente verificação")
    (root / "TODO.md").write_text(
        _HEADER_9 + _row("V-12", "🔍 Pendente verificação")
        + "\n<!-- nota de reordenacao -->\n", encoding="utf-8")
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "docs(todo): reordena em torno de V-12")

    r = _run_fresh(root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert r.stderr.strip() == ""


# ---------------------------------------------------------------------------
# Commit de bookkeeping citando ID AINDA pendente: o aviso #1 dispara mesmo
# sem tocar codigo -- documentado como comportamento ATUAL (nao gated por
# touched_code no codigo de build_warnings), nao um bug: o texto do aviso e
# condicional ("se entregou, atualize"), nao uma afirmacao de entrega.
# ---------------------------------------------------------------------------

def test_e2e_bookkeeping_citando_id_ainda_pendente_tambem_avisa_hoje(tmp_path):
    root = _init_repo_com_tabela(tmp_path, status_v12="⏳ Pendente")
    (root / "TODO.md").write_text(
        _HEADER_9 + _row("V-12", "⏳ Pendente") + _row("V-20", "⏳ Pendente"),
        encoding="utf-8")
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "docs(todo): cria V-20, referencia V-12 como pre-requisito")

    r = _run_fresh(root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "V-12" in r.stderr and "Status" in r.stderr


# ---------------------------------------------------------------------------
# Mensagem multi-linha: ID citado no RODAPE do corpo, nao na 1a linha --
# prova que `git log -1 --format=%B` (corpo inteiro) e usado, nao so o
# subject.
# ---------------------------------------------------------------------------

def test_e2e_id_citado_so_no_rodape_do_corpo_multilinhas_e_detectado(tmp_path):
    root = _init_repo_com_tabela(tmp_path)
    (root / "auth.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "auth.py")
    msg = "feat: termina login\n\nDetalhes da implementacao aqui.\n\nGAP-2\nV-12\n"
    _git(root, "commit", "-qm", msg)

    r = _run_fresh(root)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "V-12" in r.stderr  # citado no rodape -> reconhecido


# ---------------------------------------------------------------------------
# Log acumula entradas ao longo de commits sucessivos (multiplas chamadas
# do hook na mesma sessao de repo).
# ---------------------------------------------------------------------------

def test_e2e_log_acumula_entre_commits_sucessivos(tmp_path):
    root = _init_repo_com_tabela(tmp_path)
    for i in range(3):
        (root / f"f{i}.py").write_text("x\n", encoding="utf-8")
        _git(root, "add", f"f{i}.py")
        _git(root, "commit", "-qm", f"feat: passo {i} V-12")
        assert _run_fresh(root).returncode == 0

    log = open(_log_path(root), encoding="utf-8").read().splitlines()
    assert len(log) == 3
    assert all("code=1 cited=1" in l for l in log)


# ---------------------------------------------------------------------------
# Warn-only: exit SEMPRE 0, inclusive fora de repo, repo sem TODO.md, e
# TODO.md ilegivel (excecao de leitura engolida -- ENC-1 ainda em aberto).
# ---------------------------------------------------------------------------

def test_e2e_exit0_fora_de_repositorio_git(tmp_path):
    r = _run_fresh(tmp_path)  # tmp_path puro, sem git init
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert r.stderr.strip() == ""


def test_e2e_exit0_repo_git_sem_todo_md(tmp_path):
    _git_init_isolado(tmp_path)
    (tmp_path / "readme.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "readme.txt")
    _git(tmp_path, "commit", "-qm", "init")
    r = _run_fresh(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert r.stderr.strip() == ""


def test_e2e_exit0_todo_md_ilegivel_excecao_engolida_em_silencio(tmp_path):
    """Documenta o comportamento ATUAL (nao conserta -- ENC-1 no TODO.md):
    todo_freshness.main() engole QUALQUER excecao na leitura do TODO.md
    (`todo_freshness.py:123-127`, `except Exception: return 0`) e devolve 0
    sem nenhum log/aviso -- mesmo padrao para arquivo ilegivel, encoding
    invalido ou, como aqui, um diretorio no lugar do arquivo (IsADirectoryError
    e uma excecao concreta e determinista para forcar esse caminho sem
    depender de bits de permissao especificos do SO)."""
    _git_init_isolado(tmp_path)
    os.mkdir(tmp_path / "TODO.md")   # TODO.md e um DIRETORIO -> open() falha
    (tmp_path / "TODO.md" / "nada.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "TODO.md e um diretorio, de proposito")

    r = _run_fresh(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert r.stderr.strip() == ""  # excecao engolida: nenhum aviso, nenhum crash
    assert not os.path.isfile(_log_path(tmp_path))  # nem chegou a logar adesao


def test_e2e_exit0_mesmo_com_flag_desconhecida(tmp_path):
    """Excecao de contrato (D-6/CLI-1): freshness roda como git hook
    warn-only -- NENHUM caminho do argparse pode mudar o exit code, nem
    flag invalida."""
    root = _init_repo_com_tabela(tmp_path)
    r = subprocess.run([sys.executable, FRESH, "--nao-existe"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_e2e_exit0_com_help(tmp_path):
    root = _init_repo_com_tabela(tmp_path)
    r = subprocess.run([sys.executable, FRESH, "--help"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout, r.stderr)


# ---------------------------------------------------------------------------
# ACHADO (nao consertado -- fora do escopo desta fatia, e edicao em
# tools/ e do outro agente): `git diff-tree --no-commit-id --name-only -r
# HEAD` SEM `--root` devolve lista VAZIA de arquivos quando HEAD e o commit
# RAIZ do repositorio (sem pai) -- confirmado ao vivo com o git de verdade.
# Consequencia real em todo_freshness.py:132-134: no PRIMEIRO commit de
# qualquer repositorio, `files` fica sempre vazio, `touched_code(files)` e
# sempre False, e o aviso "commit tocou codigo mas nao citou ID" NUNCA
# dispara -- mesmo que o commit raiz toque um arquivo de codigo inteiro sem
# citar nenhum ID. xfail(strict=True): se um dia `--root` for adicionado (ou
# o diff for feito contra a arvore vazia por outro mecanismo), este teste
# vira XPASS/erro -- sinal para promove-lo a teste normal.
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=True,
    reason=(
        "tools/todo_freshness.py:132-134 chama 'git diff-tree --no-commit-id "
        "--name-only -r HEAD' SEM '--root'. No commit RAIZ de um repositorio "
        "(sem pai), esse comando devolve saida VAZIA -- confirmado ao vivo "
        "com git real (ver sessao de investigacao desta fatia, GAP-2). "
        "Resultado: o commit raiz nunca gera o aviso 'tocou codigo sem citar "
        "ID', mesmo quando toca codigo de verdade sem citar nada. NAO "
        "consertado aqui (edicao em tools/ e de outro agente nesta sessao); "
        "reportado ao team-lead para virar item de conserto (ex.: acoplar a "
        "SPRAWL-1/ENC-1 ou item novo). Quando o -- root' entrar, este teste "
        "vira XPASS: e o sinal para promove-lo."
    ),
)
def test_e2e_commit_raiz_toca_codigo_sem_citar_deveria_avisar_mas_nao_avisa(tmp_path):
    _git_init_isolado(tmp_path)
    (tmp_path / "TODO.md").write_text(
        _HEADER_9 + _row("V-12", "⏳ Pendente"), encoding="utf-8")
    (tmp_path / "auth.py").write_text("print('x')\n", encoding="utf-8")
    _git(tmp_path, "add", "TODO.md", "auth.py")
    _git(tmp_path, "commit", "-qm", "init: tabela + auth (sem citar ID)")

    r = _run_fresh(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    # comportamento CORRETO esperado (falha hoje -- ver reason acima):
    assert "nao citou nenhum ID" in r.stderr
