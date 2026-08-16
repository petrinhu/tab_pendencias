"""Suite do guard anti-vazamento de fixture real (tools/ci/guard_no_real_fixtures.py).

Cobre as tres camadas principais:
- CAMADA 1 (tamanho de tabela GFM) -- unica sempre ativa no CI publico
  sem configuracao (AUD-FUP-2).
- CAMADA 2 (termo proibido no CAMINHO) -- opt-in (AUD-FUP-2).
- CAMADA 3 (termo proibido no CONTEUDO, LEAK-2) -- opt-in.

Prova nas duas direcoes (acusa / silencia) e que a saida do guard nunca
reproduz o termo proibido em claro (auto-vazamento).
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
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


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
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


# ------------------------------ unidade: CAMADA 1 (tamanho de tabela) -------

def _tabela_gfm(n_dados: int) -> str:
    """Tabela GFM com cabecalho + separador + n_dados linhas de dados."""
    linhas = ["| ID | Status |", "| :- | :- |"]
    for i in range(n_dados):
        linhas.append(f"| X-{i} | pendente |")
    return "\n".join(linhas) + "\n"


def test_check_table_sizes_acusa_acima_do_limite(tmp_path):
    """AUD-FUP-2 / CAMADA 1: bloco com LIMITE+1 linhas de dados e achado."""
    root = _repo(tmp_path)
    n = G.LIMITE_LINHAS_DADOS + 1
    _commit(root, "big.md", _tabela_gfm(n))
    violations = G.check_table_sizes(root, ["big.md"])
    assert len(violations) == 1
    assert "big.md" in violations[0]
    assert str(G.LIMITE_LINHAS_DADOS) in violations[0]
    assert str(n) in violations[0]


def test_check_table_sizes_silencia_no_limite(tmp_path):
    """AUD-FUP-2 / CAMADA 1: exatamente LIMITE linhas de dados nao acusa."""
    root = _repo(tmp_path)
    _commit(root, "ok.md", _tabela_gfm(G.LIMITE_LINHAS_DADOS))
    violations = G.check_table_sizes(root, ["ok.md"])
    assert violations == []


def test_guard_main_acusa_tabela_grande_sem_termos(tmp_path):
    """AUD-FUP-2: CAMADA 1 via main() sem termos (CI publico)."""
    root = _repo(tmp_path)
    _commit(root, "huge.md", _tabela_gfm(G.LIMITE_LINHAS_DADOS + 5))
    res = _run_guard(root)
    assert res.returncode == 1, res.stdout + res.stderr
    assert "huge.md" in res.stdout
    assert "CAMADA 1" in res.stdout or str(G.LIMITE_LINHAS_DADOS) in res.stdout


# ------------------------------ unidade: CAMADA 2 (caminho) -----------------

def test_check_forbidden_path_names_acusa_termo_no_caminho():
    """AUD-FUP-2 / CAMADA 2: termo no path e achado; rotulo mascarado.

    O path em si e o achado e por isso aparece no relato (nao da para
    apontar o arquivo sem citar o path). O que a camada mascara e o
    trecho '(mascarado) ...' -- o mesmo contrato da CAMADA 3.
    """
    rel = f"docs/{TERMO_SINTETICO}/notas.md"
    violations = G.check_forbidden_path_names([rel], [TERMO_SINTETICO])
    assert len(violations) == 1
    assert rel in violations[0]
    masked = G._mask_term(TERMO_SINTETICO)
    assert masked in violations[0]
    assert "mascarado" in violations[0]
    # O termo so pode aparecer como componente do path, nao no rotulo
    # mascarado: o rotulo e p*...*Z, nao o termo inteiro apos "mascarado".
    assert f"'{TERMO_SINTETICO}'" not in violations[0]
    assert f"'{masked}'" in violations[0]


def test_check_forbidden_path_names_e_case_insensitive():
    rel = f"docs/{TERMO_SINTETICO.upper()}/x.md"
    violations = G.check_forbidden_path_names([rel], [TERMO_SINTETICO])
    assert len(violations) == 1
    assert G._mask_term(TERMO_SINTETICO) in violations[0]


def test_check_forbidden_path_names_silencia_sem_termo():
    violations = G.check_forbidden_path_names(
        ["docs/consumidor/notas.md", "TODO.md"], [TERMO_SINTETICO]
    )
    assert violations == []


def test_guard_main_acusa_termo_no_caminho(tmp_path):
    """AUD-FUP-2: CAMADA 2 via main() com termo so no path (conteudo limpo)."""
    root = _repo(tmp_path)
    _commit(root, "TODO.md", "| ID |\n| :- |\n")
    rel = f"docs/{TERMO_SINTETICO}/notas.md"
    _commit(root, rel, "texto limpo, sem o termo no corpo\n")
    res = _run_guard(root, env_extra={ENV_VAR: TERMO_SINTETICO})
    assert res.returncode == 1, res.stdout + res.stderr
    assert "docs/" in res.stdout
    assert "caminho" in res.stdout
    masked = G._mask_term(TERMO_SINTETICO)
    assert masked in res.stdout
    # Rotulo mascarado nao cita o termo literal entre aspas.
    assert f"'{TERMO_SINTETICO}'" not in res.stdout
    # Conteudo limpo: so 1 achado (path), nao linha de conteudo.
    assert res.stdout.count("achado") >= 1


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
