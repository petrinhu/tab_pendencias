"""Suite do guard anti-vazamento de fixture real (tools/ci/guard_no_real_fixtures.py).

Cobre a CAMADA 3 (conteudo, item LEAK-2): a Camada 2 pre-existente checa
apenas o CAMINHO do arquivo versionado -- um nome de projeto-fonte real
dentro do TEXTO de um arquivo (comentario, docstring) passava batido. Esta
suite prova, nas duas direcoes, que a nova camada acusa quando o termo esta
presente e silencia quando nao esta -- e que a saida do proprio guard nunca
reproduz o termo proibido em claro (o guard nao pode se auto-acusar
vazando o que deveria proteger).
"""
import importlib.util
import os
import subprocess
import sys

from conftest import git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD_PATH = os.path.join(REPO_ROOT, "tools", "ci", "guard_no_real_fixtures.py")

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

# Termo SINTETICO usado nos testes -- nunca um nome real de projeto do
# lider (isso seria a mesma classe de vazamento que a suite existe para
# provar que o guard previne).
TERMO_SINTETICO = "projetoprivadoXYZ"
ENV_VAR = "TAB_PENDENCIAS_GUARD_FORBIDDEN_TERMS"


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_no_real_fixtures", GUARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load_guard()


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)


def _repo(tmp_path):
    git_init_isolado(tmp_path)
    return tmp_path


def _commit(root, rel_path, text):
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    _git(root, "add", rel_path)
    _git(root, "commit", "-qm", "add " + rel_path)


def _run_guard(root, env_extra=None):
    env = {**ENV}
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, GUARD_PATH], cwd=root, env=env,
                          capture_output=True, text=True)


# ------------------------------ unidade: mascaramento -----------------------

def test_mask_term_nao_reproduz_termo_literal():
    masked = G._mask_term(TERMO_SINTETICO)
    assert masked != TERMO_SINTETICO
    assert TERMO_SINTETICO not in masked
    assert masked[0] == TERMO_SINTETICO[0]
    assert masked[-1] == TERMO_SINTETICO[-1]
    assert "*" in masked


def test_mask_term_termo_curto_mascara_por_completo():
    masked = G._mask_term("ab")
    assert set(masked) == {"*"}
    assert len(masked) == 2


# ------------------------------ unidade: check de conteudo ------------------

def test_check_forbidden_content_acusa_termo_dentro_do_arquivo(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "nota.md", f"comentario menciona {TERMO_SINTETICO} aqui\n")
    violations = G.check_forbidden_content(root, ["nota.md"], [TERMO_SINTETICO])
    assert len(violations) == 1
    assert "nota.md:1" in violations[0]
    assert TERMO_SINTETICO not in violations[0]


def test_check_forbidden_content_e_case_insensitive(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "nota.md", f"{TERMO_SINTETICO.upper()} em maiusculas\n")
    violations = G.check_forbidden_content(root, ["nota.md"], [TERMO_SINTETICO])
    assert len(violations) == 1


def test_check_forbidden_content_silencia_sem_termo_presente(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "nota.md", "texto qualquer, nada suspeito por aqui\n")
    violations = G.check_forbidden_content(root, ["nota.md"], [TERMO_SINTETICO])
    assert violations == []


def test_check_forbidden_content_pula_arquivo_binario(tmp_path):
    root = _repo(tmp_path)
    bin_path = root / "img.bin"
    bin_path.write_bytes(b"\xff\xfe\x00" + TERMO_SINTETICO.encode("ascii") + b"\x00\xff")
    _git(root, "add", "img.bin")
    _git(root, "commit", "-qm", "bin")
    violations = G.check_forbidden_content(root, ["img.bin"], [TERMO_SINTETICO])
    assert violations == []


def test_check_forbidden_content_pula_o_proprio_arquivo_de_termos(tmp_path):
    """O .guard_forbidden_terms nunca e versionado (esta no .gitignore), mas
    a funcao tem que ignora-lo mesmo que apareca em `tracked` por engano --
    defesa em profundidade contra a propria fonte do termo virar 'achado'."""
    root = _repo(tmp_path)
    violations = G.check_forbidden_content(
        root, [G.ARQUIVO_TERMOS_LOCAL], [TERMO_SINTETICO]
    )
    assert violations == []


# ------------------------------ main(): discriminancia end-to-end ----------

def test_guard_acusa_termo_plantado_em_arquivo_versionado(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "TODO.md", "| ID |\n| :- |\n")
    _commit(root, "doc/nota.md", f"veja o projeto {TERMO_SINTETICO} citado aqui\n")

    res = _run_guard(root, env_extra={ENV_VAR: TERMO_SINTETICO})

    assert res.returncode == 1, res.stdout + res.stderr
    assert "doc/nota.md" in res.stdout
    assert TERMO_SINTETICO not in res.stdout
    assert TERMO_SINTETICO not in res.stderr


def test_guard_silencia_apos_remover_termo_plantado(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "TODO.md", "| ID |\n| :- |\n")
    _commit(root, "doc/nota.md", f"veja o projeto {TERMO_SINTETICO} citado aqui\n")

    res_vermelho = _run_guard(root, env_extra={ENV_VAR: TERMO_SINTETICO})
    assert res_vermelho.returncode == 1, res_vermelho.stdout + res_vermelho.stderr

    _commit(root, "doc/nota.md", "veja o projeto consumidor generico\n")
    res_verde = _run_guard(root, env_extra={ENV_VAR: TERMO_SINTETICO})
    assert res_verde.returncode == 0, res_verde.stdout + res_verde.stderr


def test_guard_declara_camada3_desligada_sem_termos_configurados(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "TODO.md", "| ID |\n| :- |\n")

    res = _run_guard(root)

    assert res.returncode == 0, res.stdout + res.stderr
    assert "CAMADA 3" in res.stdout
    assert "DESLIGADA" in res.stdout
    # "OK" sozinho nao pode parecer cobertura completa quando 2/3 camadas
    # opt-in estao desligadas -- tem que haver aviso explicito disso.
    assert "AVISO" in res.stdout


def test_guard_declara_camada3_ativa_quando_termo_configurado(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "TODO.md", "| ID |\n| :- |\n")

    res = _run_guard(root, env_extra={ENV_VAR: TERMO_SINTETICO})

    assert res.returncode == 0, res.stdout + res.stderr
    assert "CAMADA 3" in res.stdout
    assert "ATIVA" in res.stdout
    assert TERMO_SINTETICO not in res.stdout
