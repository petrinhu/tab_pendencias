import os
import subprocess
import sys

# Permite `import todo_lib` / `import todo_sync` / etc. ao rodar pytest de
# qualquer cwd: os modulos moram em tools/ (layout monorepo), um nivel acima
# de tests/, nao no mesmo diretorio (diferenca do antigo ~/.claude/githooks/,
# onde tudo ficava plano no mesmo dir das tests).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


# Identidade git so para os commits de fixture (NUNCA `git config --global`).
ENV_GIT_TESTE = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                  "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git_init_isolado(cwd):
    """`git init` + desliga hook LOCAL a este repo de fixture (HOOKISO-1).

    Esta maquina tem `core.hooksPath` GLOBAL (`~/.gitconfig`) apontando para
    `~/.claude/githooks/` -- sem esta protecao, todo `git commit` num repo
    temporario de teste dispara o hook AMBIENTE de verdade por baixo dos
    panos (potencialmente uma versao DIVERGENTE do script sob teste, ver
    MIG-DIFF na INBOX do TODO.md), escrevendo em
    `$GIT_DIR/todo-freshness.log` e corrompendo a contagem/isolamento
    deterministico dos testes que dependem desse arquivo ou do numero exato
    de linhas nele.

    Um `core.hooksPath` **local** (config do proprio repo de fixture, NUNCA
    `--global` -- isso mudaria a maquina do lider) para um diretorio vazio
    sobrescreve o global sem tocar nada fora do `cwd` do teste. Compartilhado
    entre os arquivos de teste que criam repositorios git (nao duplicar esta
    logica de novo num 4o arquivo -- importar daqui).

    BRANCH-DEFAULT-1 (2026-08-16): o nome do branch inicial de `git init` vem
    de `init.defaultBranch`, que e por-ambiente (maquina de dev do lider tem
    "main" configurado globalmente; runner do GitHub Actions -- ubuntu,
    windows e os 3 containers de distro -- nao tem NADA configurado, entao
    cai no default legado do proprio git, "master"). Testes que fabricam um
    remoto e comparam a branch ATUAL contra ele (CHK-09, `_verify_push_claim`
    em `chk_frescor.py`) ficavam refens a essa loteria: sob "master" a claim
    "commit local, nunca pushado" nao batia com nenhum candidato
    (`refs/heads/master` nem existe no remoto, que so tem `refs/heads/main`
    -- o nome pushado explicitamente pelos testes), e o veredito virava
    "desconhecido" (achado COSMETICO) em vez de "sustentada" (zero achado).
    `git symbolic-ref HEAD` e comando de plumbing antigo, existe em qualquer
    git (Linux/Windows/mac), e fixa o branch inicial ANTES do 1o commit sem
    depender de `-b`/`--initial-branch` (so a partir do git 2.28) -- runners
    minimalistas (containers debian/fedora/archlinux) podem ter git mais
    velho. Fixar aqui, uma vez, deixa TODOS os consumidores de
    `git_init_isolado` deterministicos em relacao ao `init.defaultBranch` do
    ambiente, sem editar cada arquivo de teste."""
    subprocess.run(["git", "init", "-q"], cwd=cwd, env=ENV_GIT_TESTE,
                   capture_output=True, check=True)
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"],
                   cwd=cwd, env=ENV_GIT_TESTE, capture_output=True,
                   check=True)
    hooks_vazio = os.path.join(str(cwd), ".git", "hooks-vazio-teste")
    os.makedirs(hooks_vazio, exist_ok=True)
    subprocess.run(["git", "config", "core.hooksPath", hooks_vazio], cwd=cwd,
                   env=ENV_GIT_TESTE, capture_output=True, check=True)
