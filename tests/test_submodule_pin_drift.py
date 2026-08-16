"""tests/test_submodule_pin_drift.py -- TAB-SOT-007: detector de drift do pin
de submodulo, read-only, offline-first e warn-only.

Cenario medido que originou a fatia (16/08/26): o gitlink de
`skills/tab_pendencias` em `petrinhu/claude-memory` apontava para um commit
67 commits atras de `origin/main`/`v1.0.2` -- ninguem percebeu ate alguem
medir a mao. Este arquivo reproduz esse cenario com repositorios git
temporarios (remote + superprojeto) em `tmp_path`, nunca contra a rede real
nem contra nomes de projeto desta maquina (AGN-1/ADR-0001 a).

Nao reusa helpers de outros arquivos de teste de proposito (cada arquivo e
auto-contido, mesma convencao do resto da suite).
"""
import os
import subprocess
import sys

import pytest

from conftest import git_init_isolado

import submodule_pin_drift as D

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
SCRIPT = os.path.join(TOOLS_DIR, "submodule_pin_drift.py")

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)


def _sha(cwd):
    return _git(cwd, "rev-parse", "HEAD").stdout.strip()


def _make_remote(tmp_path, n_commits=1, tag_at=None):
    """Repo 'remote' NAO-bare (ls-remote funciona igual contra um path local,
    bare ou nao -- so le refs). Cria `n_commits` commits sequenciais; devolve
    (path, [sha_de_cada_commit_em_ordem]). `tag_at` e um dict opcional
    {indice_do_commit (0-based): (nome_da_tag, anotada_bool)}."""
    remote = tmp_path / "remote_repo"
    remote.mkdir()
    git_init_isolado(remote)
    shas = []
    for i in range(n_commits):
        (remote / "f.txt").write_text(f"linha {i}\n", encoding="utf-8")
        _git(remote, "add", "f.txt")
        _git(remote, "commit", "-qm", f"c{i}")
        shas.append(_sha(remote))
        if tag_at and i in tag_at:
            nome, anotada = tag_at[i]
            if anotada:
                _git(remote, "tag", "-a", nome, "-m", "release")
            else:
                _git(remote, "tag", nome)
    return remote, shas


def _make_super_with_gitlink(tmp_path, submodule_path, pinned_sha,
                             remote_url=None):
    """Superprojeto com um gitlink (mode 160000) apontando para `pinned_sha`
    em `submodule_path`, SEM checkout do submodulo (prova que o detector le
    a arvore, nao o checkout). Se `remote_url` for dado, tambem grava um
    `.gitmodules` valido apontando para ele."""
    super_ = tmp_path / "super"
    super_.mkdir()
    git_init_isolado(super_)
    if remote_url is not None:
        (super_ / ".gitmodules").write_text(
            f'[submodule "sub"]\n\tpath = {submodule_path}\n'
            f'\turl = {remote_url}\n', encoding="utf-8")
        _git(super_, "add", ".gitmodules")
    _git(super_, "update-index", "--add", "--cacheinfo",
        f"160000,{pinned_sha},{submodule_path}")
    _git(super_, "commit", "-qm", "pin submodulo")
    return super_


# ------------------------------- pinned_sha: le a ARVORE, nao o checkout ----

def test_get_pinned_sha_le_gitlink_sem_checkout(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0])
    assert not (super_ / "sub").exists()  # nunca inicializado/checked out
    sha, err = D.get_pinned_sha(str(super_), "sub", timeout=5)
    assert err is None
    assert sha == shas[0]


def test_get_pinned_sha_path_errado_devolve_none_com_motivo(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0])
    sha, err = D.get_pinned_sha(str(super_), "caminho/nao/existe", timeout=5)
    assert sha is None
    assert err and "caminho/nao/existe" in err


def test_get_pinned_sha_de_arquivo_comum_nao_e_gitlink(tmp_path):
    """AGN-1: um path que existe mas NAO e submodulo (mode != 160000) nunca
    deve ser confundido com um pin -- falha declarada, nao um sha fantasma."""
    super_ = tmp_path / "super2"
    super_.mkdir()
    git_init_isolado(super_)
    (super_ / "arquivo.txt").write_text("x", encoding="utf-8")
    _git(super_, "add", "arquivo.txt")
    _git(super_, "commit", "-qm", "arquivo comum")
    sha, err = D.get_pinned_sha(str(super_), "arquivo.txt", timeout=5)
    assert sha is None
    assert err and "gitlink" in err.lower()


# ------------------------------- resolve URL via .gitmodules ---------------

def test_resolve_url_from_gitmodules(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    url, err = D.resolve_url_from_gitmodules(str(super_), "sub", timeout=5)
    assert err is None
    assert url == str(remote)


def test_resolve_url_sem_gitmodules_devolve_none_com_motivo(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0])  # sem .gitmodules
    url, err = D.resolve_url_from_gitmodules(str(super_), "sub", timeout=5)
    assert url is None
    assert err


# ------------------------------- tags remotas: peeled vs leve ---------------

def test_list_remote_tags_resolve_anotada_para_o_commit_nao_o_objeto_tag(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=2, tag_at={
        0: ("v1.0.0", False),   # leve
        1: ("v1.0.1", True),    # anotada
    })
    tags, err = D.list_remote_tags(str(tmp_path), str(remote), timeout=5)
    assert err is None
    assert tags["v1.0.0"] == shas[0]
    # tag anotada: o sha listado tem que ser o do COMMIT (peeled), nao do
    # objeto tag -- se list_remote_tags nao tratar "^{}" ele pegaria o sha
    # errado (do objeto tag, nao resolvivel como commit do rev-list).
    assert tags["v1.0.1"] == shas[1]


# ------------------------------- latest_release: semver, nao lexico --------

def test_latest_release_ordena_semver_nao_lexicografico():
    tags = {"v1.0.9": "s9", "v1.0.10": "s10", "nightly": "sn"}
    assert D.latest_release(tags) == ("v1.0.10", "s10")


def test_latest_release_sem_tags_semver_devolve_none():
    assert D.latest_release({"nightly": "x", "latest": "y"}) is None


# ------------------------------- cenario medido: 67 commits atras ----------

def test_check_drift_cenario_medido_pin_nao_tagueado_atras_de_release(tmp_path):
    """Espelha o incidente real: pin aponta para um commit ANTERIOR a toda
    tag conhecida, sem checkout local do submodulo (sem objetos locais).
    releases_behind e commits_behind ficam None (nao calculaveis sem o
    grafo/objetos), mas o detector AINDA ASSIM marca 'desatualizado' porque
    o sha comparado direto ja difere do ultimo release -- e o sinal minimo
    que nao pode depender de objetos locais."""
    remote, shas = _make_remote(tmp_path, n_commits=5, tag_at={4: ("v1.0.2", False)})
    pinned = shas[0]  # bem atras, sem tag
    super_ = _make_super_with_gitlink(tmp_path, "sub", pinned,
                                      remote_url=str(remote))
    r = D.check_drift(str(super_), "sub", timeout=5)
    assert r["pinned_sha"] == pinned
    assert r["latest_release_sha"] == shas[4]
    assert r["latest_release_tag"] == "v1.0.2"
    assert r["status"] == "desatualizado"
    assert r["releases_behind"] is None  # pin nao e uma tag conhecida
    assert r["commits_behind"] is None   # sem checkout local do submodulo
    assert any("nao" in n.lower() or "não" in n.lower() for n in r["notes"])


def test_check_drift_releases_behind_calculavel_quando_pin_e_uma_tag(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=3, tag_at={
        0: ("v1.0.0", False), 1: ("v1.0.1", False), 2: ("v1.0.2", False),
    })
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    r = D.check_drift(str(super_), "sub", timeout=5)
    assert r["releases_behind"] == 2  # v1.0.1 e v1.0.2 sao mais novas
    assert r["status"] == "desatualizado"


def test_check_drift_commits_behind_calculavel_com_submodulo_inicializado(tmp_path):
    """So quando o submodulo JA esta inicializado localmente (objetos
    presentes) o detector consegue contar commits -- sem fetch algum (o
    clone abaixo e feito pelo TESTE para simular esse estado, nunca pelo
    modulo sob teste)."""
    remote, shas = _make_remote(tmp_path, n_commits=4, tag_at={3: ("v1.0.2", False)})
    pinned = shas[0]
    super_ = _make_super_with_gitlink(tmp_path, "sub", pinned,
                                      remote_url=str(remote))
    _git(super_, "clone", "-q", str(remote), "sub")  # simula checkout previo
    r = D.check_drift(str(super_), "sub", timeout=5)
    assert r["commits_behind"] == 3


def test_check_drift_atualizado_quando_pin_e_a_ultima_tag(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=2, tag_at={1: ("v1.0.2", False)})
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[1],
                                      remote_url=str(remote))
    r = D.check_drift(str(super_), "sub", timeout=5)
    assert r["status"] == "atualizado"
    assert r["releases_behind"] == 0


# ------------------------------- sem rede: NUNCA finge frescor -------------

def test_check_drift_remoto_inalcancavel_declara_nao_verificavel(tmp_path):
    """Substitui 'rede ausente' por um remoto INALCANCAVEL (path local
    inexistente) -- git falha exatamente do mesmo jeito (mesma familia de
    erro que timeout/DNS morto), determinístico e 100% offline, sem
    depender de nada da maquina que roda o teste (armadilha: nao inventar
    dependencia de rede real num teste)."""
    remote, shas = _make_remote(tmp_path, n_commits=1)
    bogus_url = str(tmp_path / "isto_nao_existe_em_lugar_nenhum")
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=bogus_url)
    r = D.check_drift(str(super_), "sub", timeout=5)
    assert r["network_ok"] is False
    assert r["status"] == "nao_verificavel"
    assert r["status"] != "atualizado"  # nunca finge frescor
    assert r["latest_release_sha"] is None
    assert r["notes"]


def test_check_drift_sem_tags_semver_no_remoto_e_nao_verificavel(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1, tag_at={0: ("nightly", False)})
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    r = D.check_drift(str(super_), "sub", timeout=5)
    assert r["network_ok"] is True
    assert r["status"] == "nao_verificavel"


def test_check_drift_path_invalido_e_erro_de_execucao(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    r = D.check_drift(str(super_), "nao/existe", timeout=5)
    assert r["status"] == "erro"
    assert r["pinned_sha"] is None


# ------------------------------- branch opcional ----------------------------

def test_check_drift_branch_opcional_flipa_para_desatualizado(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=3, tag_at={0: ("v1.0.0", False)})
    # pin == a propria tag v1.0.0 (unica tag), mas o branch (HEAD/main) do
    # remoto ja avancou 2 commits alem dela -- --branch pega essa divergencia
    # que a comparacao so-por-tag nao pegaria.
    branch = _git(remote, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    r = D.check_drift(str(super_), "sub", branch=branch, timeout=5)
    assert r["releases_behind"] == 0     # nenhuma tag mais nova que v1.0.0
    assert r["branch_tip_sha"] == shas[2]
    assert r["status"] == "desatualizado"  # o branch denuncia o atraso


# ------------------------------- CLI (D-6/CLI-1) -----------------------------

def _run_cli(args, cwd):
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd,
                          capture_output=True, text=True)


def test_cli_help_exit0():
    r = _run_cli(["--help"], cwd=REPO_ROOT)
    assert r.returncode == 0, r.stderr
    assert "--path" in r.stdout


def test_cli_flag_desconhecida_exit1():
    r = _run_cli(["--path", "sub", "--aply"], cwd=REPO_ROOT)
    assert r.returncode == 1
    assert r.stderr.strip() != ""


def test_cli_path_obrigatorio_ausente_exit1():
    r = _run_cli([], cwd=REPO_ROOT)
    assert r.returncode == 1
    assert r.stderr.strip() != ""


def test_cli_exit0_quando_atualizado(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1, tag_at={0: ("v1.0.2", False)})
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    r = _run_cli(["--path", "sub", "--timeout", "5"], cwd=super_)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "status:" in r.stdout and "atualizado" in r.stdout


def test_cli_exit2_quando_desatualizado(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=3, tag_at={2: ("v1.0.2", False)})
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0],
                                      remote_url=str(remote))
    r = _run_cli(["--path", "sub", "--timeout", "5"], cwd=super_)
    assert r.returncode == 2, (r.stdout, r.stderr)


def test_cli_exit2_quando_nao_verificavel_sem_rede(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    bogus = str(tmp_path / "sem_remoto_aqui")
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0], remote_url=bogus)
    r = _run_cli(["--path", "sub", "--timeout", "5"], cwd=super_)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "nao_verificavel" in r.stdout or "não_verificavel" in r.stdout


def test_cli_url_explicita_ignora_gitmodules(tmp_path):
    """--url e um PARAMETRO explicito -- nunca precisa de .gitmodules, e a
    skill e agnostica a projeto/esquema de submodulo (AGN-1)."""
    remote, shas = _make_remote(tmp_path, n_commits=1, tag_at={0: ("v1.0.2", False)})
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0])  # sem .gitmodules
    r = _run_cli(["--path", "sub", "--url", str(remote), "--timeout", "5"],
                cwd=super_)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_cli_sem_url_nem_gitmodules_e_erro_de_execucao(tmp_path):
    remote, shas = _make_remote(tmp_path, n_commits=1)
    super_ = _make_super_with_gitlink(tmp_path, "sub", shas[0])  # sem .gitmodules
    r = _run_cli(["--path", "sub", "--timeout", "5"], cwd=super_)
    assert r.returncode == 1, (r.stdout, r.stderr)
