"""Suite do motor de `--audit` (AUDIT-ENG). Cobre so o MOTOR e a
infraestrutura de registro/perfil/relatorio/CLI -- os checks concretos
(CHK-01..14) sao de outras fatias (CHK-CORE, CHK-GRAPH, CHK-09, CHK-10,
CHK-CASA); aqui so existe o check de exemplo CHK-00 (fora do catalogo, prova
o mecanismo ponta a ponta).

ADR de referencia: docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md
"""
import hashlib
import os
import subprocess
import sys

import pytest

import todo_audit as A

from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
AUDIT = os.path.join(TOOLS_DIR, "todo_audit.py")

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

TODO_OK = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
    "| V-12 | W2 | Auth | Login | Alta | — | Média | ⏳ Pendente | — |\n"
)

TODO_ID_COM_ESPACO = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
    "| V 12 | W2 | Auth | Login | Alta | — | Média | ⏳ Pendente | — |\n"
)


def _run(args, cwd):
    return subprocess.run([sys.executable, AUDIT, *args], cwd=cwd,
                          capture_output=True, text=True)


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, env=_ENV, capture_output=True,
                   check=True)


def _repo(tmp_path, todo_text=TODO_OK):
    """Repo git isolado (HOOKISO-1) com um TODO.md; devolve (root, todo_path)."""
    _git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(todo_text, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "tabela")
    return tmp_path, todo


def _md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


# --------------------------- (a) registro de checks ---------------------------

def test_check_sem_profile_e_typeerror():
    """`profile` e OBRIGATORIO no dataclass Check -- omitir e TypeError na
    construcao, nunca um bug latente descoberto em producao (ADR-0001 a)."""
    with pytest.raises(TypeError):
        A.Check(id="CHK-X", title="t", severity_default="COSMÉTICO",
                run=lambda ctx: [])


def test_check_nenhum_campo_tem_default_estrutural():
    """Mais forte que o teste acima: NENHUM campo de `Check` pode ter
    default, verificado via introspeccao de `dataclasses.fields()` -- nao
    depende de uma chamada de construtor especifica (que so testa UMA
    combinacao de argumentos omitidos). Isto pega de forma direta e
    declarativa qualquer regressao futura que reintroduza um default em
    QUALQUER campo (nao so `profile`), seja por reordenacao de campos ou
    por edicao direta -- e o jeito mais robusto de provar a garantia."""
    import dataclasses
    for f in dataclasses.fields(A.Check):
        assert f.default is dataclasses.MISSING, (
            f"Check.{f.name} tem default ({f.default!r}) -- viola a "
            "obrigatoriedade de declaracao explicita (ADR-0001 a)")
        assert f.default_factory is dataclasses.MISSING, (
            f"Check.{f.name} tem default_factory -- idem")


def test_check_profile_invalido_e_valueerror():
    with pytest.raises(ValueError):
        A.Check(id="CHK-X", title="t", profile="bogus",
                severity_default="COSMÉTICO", run=lambda ctx: [])


def test_check_severity_default_invalida_e_valueerror():
    with pytest.raises(ValueError):
        A.Check(id="CHK-X", title="t", profile="core",
                severity_default="bogus", run=lambda ctx: [])


def test_registro_real_tem_ao_menos_um_check_core():
    assert any(c.profile == "core" for c in A.CHECKS)


# ------------------- fronteira core x casa (teste nasce com o motor) ----------

def test_fronteira_registro_real_nenhum_core_vem_de_casa():
    """Sobre o registro REAL (CHECKS): nenhum check profile=='core' tem `run`
    definido dentro de tools/casa/. Vale mesmo com 0 checks 'casa' hoje --
    e o teste que sera acionado no dia em que o 1o check 'casa' for
    codado (ADR-0001, 'Riscos'): nasce ANTES, nao depois."""
    assert A.core_boundary_violations(A.CHECKS) == []


def test_fronteira_detecta_violacao_sintetica():
    """Prova que a funcao de fronteira PEGA uma violacao de verdade (teste
    vermelho pelo motivo certo): um Check 'core' cujo run mora fisicamente
    em tools/casa/ tem que aparecer na lista de violacoes."""
    import casa as _casa_pkg
    fake = A.Check(id="CHK-FAKE", title="violacao sintetica", profile="core",
                   severity_default="COSMÉTICO", run=_casa_pkg._only_for_boundary_test)
    violacoes = A.core_boundary_violations([fake])
    assert violacoes == ["CHK-FAKE"]


def test_fronteira_nao_acusa_check_casa_legitimo():
    import casa as _casa_pkg
    legit = A.Check(id="CHK-FAKE2", title="check casa legitimo", profile="casa",
                    severity_default="COSMÉTICO", run=_casa_pkg._only_for_boundary_test)
    assert A.core_boundary_violations([legit]) == []


# ------------------------------ (a) perfil ativo -------------------------------

def test_perfil_default_e_core_sem_ini(tmp_path):
    root, _ = _repo(tmp_path)
    cfg, err = A.load_config(str(root))
    assert err is None
    profile, origin = A.active_profile(cfg, cli_override=None)
    assert profile == "core" and "default" in origin


def test_perfil_lido_do_ini(tmp_path):
    root, _ = _repo(tmp_path)
    (root / ".tab_pendencias.ini").write_text("[profile]\nname = casa\n",
                                                encoding="utf-8")
    cfg, err = A.load_config(str(root))
    assert err is None
    profile, origin = A.active_profile(cfg, cli_override=None)
    assert profile == "casa" and "ini" in origin


def test_flag_cli_sobrepoe_o_ini(tmp_path):
    root, _ = _repo(tmp_path)
    (root / ".tab_pendencias.ini").write_text("[profile]\nname = casa\n",
                                                encoding="utf-8")
    cfg, _ = A.load_config(str(root))
    profile, origin = A.active_profile(cfg, cli_override="core")
    assert profile == "core" and "--profile" in origin


def test_ini_malformado_cai_pra_core_com_aviso(tmp_path):
    root, _ = _repo(tmp_path)
    (root / ".tab_pendencias.ini").write_text("[profile\nname = casa\n",
                                                encoding="utf-8")  # sintaxe invalida
    cfg, err = A.load_config(str(root))
    assert err is not None
    profile, _ = A.active_profile(cfg, cli_override=None)
    assert profile == "core"


def test_ini_com_valor_desconhecido_cai_pra_core(tmp_path):
    root, _ = _repo(tmp_path)
    (root / ".tab_pendencias.ini").write_text("[profile]\nname = bogus\n",
                                                encoding="utf-8")
    cfg, _err = A.load_config(str(root))
    profile, origin = A.active_profile(cfg, cli_override=None)
    assert profile == "core"
    assert "invalido" in origin or "bogus" in origin


# --------------------------- (c) motor: run_audit() ----------------------------

def test_run_audit_sem_todo_md_e_estado_valido_zero_achados(tmp_path):
    _git_init_isolado(tmp_path)
    (tmp_path / "x.txt").write_text("x")
    _git(tmp_path, "add", "x.txt")
    _git(tmp_path, "commit", "-qm", "init")
    res = A.run_audit(str(tmp_path))
    assert res.findings == []


def test_run_audit_com_exemplo_core_acha_id_com_espaco(tmp_path):
    root, _todo = _repo(tmp_path, TODO_ID_COM_ESPACO)
    res = A.run_audit(str(root))
    assert any(f.check_id == "CHK-00" for f in res.findings)
    f = next(f for f in res.findings if f.check_id == "CHK-00")
    assert f.line_no == 2  # 0-based: linha 3 do arquivo (1-based)
    assert f.severity == "COSMÉTICO"


def test_run_audit_tabela_limpa_zero_achados(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)
    res = A.run_audit(str(root))
    assert res.findings == []


def test_run_audit_e_read_only_hash_identico(tmp_path):
    root, todo = _repo(tmp_path, TODO_ID_COM_ESPACO)
    antes = _md5(todo)
    A.run_audit(str(root))
    depois = _md5(todo)
    assert antes == depois


def test_check_casa_pulado_quando_perfil_core_gera_aviso_no_silent_caps(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)

    def _run_casa(ctx):
        return []

    fake_casa = A.Check(id="CHK-CASA-FAKE", title="fake casa", profile="casa",
                        severity_default="COSMÉTICO", run=_run_casa)
    res = A.run_audit(str(root), checks=A.CHECKS + [fake_casa])
    assert any("CHK-CASA-FAKE" in n and "core" in n for n in res.notices)
    assert "CHK-CASA-FAKE" not in res.report_text.split("Avisos")[0]


def test_check_casa_roda_quando_perfil_casa(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)
    (root / ".tab_pendencias.ini").write_text("[profile]\nname = casa\n",
                                                encoding="utf-8")
    calls = []

    def _run_casa(ctx):
        calls.append(1)
        return []

    fake_casa = A.Check(id="CHK-CASA-FAKE", title="fake casa", profile="casa",
                        severity_default="COSMÉTICO", run=_run_casa)
    A.run_audit(str(root), checks=A.CHECKS + [fake_casa])
    assert calls == [1]


def test_check_que_lanca_excecao_nao_derruba_o_audit(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)

    def _quebra(ctx):
        raise RuntimeError("boom")

    fake = A.Check(id="CHK-BOOM", title="quebra", profile="core",
                   severity_default="COSMÉTICO", run=_quebra)
    res = A.run_audit(str(root), checks=A.CHECKS + [fake])
    assert any("CHK-BOOM" in n for n in res.notices)
    assert not any(f.check_id == "CHK-BOOM" for f in res.findings)


def test_no_silent_caps_trunca_e_declara_quantos_ficaram_de_fora(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)

    def _muitos(ctx):
        return [A.Finding(check_id="CHK-MANY", severity="COSMÉTICO",
                          message=f"achado {i}", line_no=i)
                for i in range(10)]

    fake = A.Check(id="CHK-MANY", title="muitos achados", profile="core",
                   severity_default="COSMÉTICO", run=_muitos)
    res = A.run_audit(str(root), checks=[fake], max_per_check=3)
    assert len(res.findings) == 10          # nada e descartado internamente
    assert "achado 0" in res.report_text and "achado 2" in res.report_text
    assert "achado 9" not in res.report_text
    assert "+7" in res.report_text or "7 nao mostrados" in res.report_text.lower() \
        or "7 omitidos" in res.report_text.lower()


def test_fixable_e_fix_ref_aparecem_no_relatorio(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)

    def _fixavel(ctx):
        return [A.Finding(check_id="CHK-FX", severity="COSMÉTICO",
                          message="algo auto-fixavel", line_no=0,
                          fixable=True, fix_ref="escapar_pipe")]

    fake = A.Check(id="CHK-FX", title="fixavel", profile="core",
                   severity_default="COSMÉTICO", run=_fixavel)
    res = A.run_audit(str(root), checks=[fake])
    assert "[auto-fixável" in res.report_text
    assert "escapar_pipe" in res.report_text


def test_julgamento_aparece_quando_nao_fixavel(tmp_path):
    root, _todo = _repo(tmp_path, TODO_ID_COM_ESPACO)
    res = A.run_audit(str(root))
    assert "[julgamento]" in res.report_text


# ------------------------------ --output: nunca no repo ------------------------

def test_output_dentro_do_repo_e_recusado(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)
    alvo = root / "relatorio.txt"
    r = _run(["--output", str(alvo)], cwd=root)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert not alvo.exists()


def test_output_fora_do_repo_escreve_relatorio(tmp_path):
    root, _todo = _repo(tmp_path, TODO_ID_COM_ESPACO)
    fora = tmp_path.parent / f"relatorio-{tmp_path.name}.txt"
    try:
        r = _run(["--output", str(fora)], cwd=root)
        assert r.returncode == 2, (r.stdout, r.stderr)
        assert fora.exists()
        assert "CHK-00" in fora.read_text(encoding="utf-8")
    finally:
        if fora.exists():
            fora.unlink()


# ------------------------------ CLI / exit codes (D-6) --------------------------

def test_help_exit0():
    r = _run(["--help"], cwd=REPO_ROOT)
    assert r.returncode == 0, r.stderr
    assert "--profile" in r.stdout
    assert "--todo" in r.stdout


def test_flag_desconhecida_e_erro(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)
    r = _run(["--zzz-desconhecida"], cwd=root)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""


def test_exit0_sem_achados(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)
    r = _run([], cwd=root)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_exit2_com_achado_cosmetico(tmp_path):
    root, _todo = _repo(tmp_path, TODO_ID_COM_ESPACO)
    r = _run([], cwd=root)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "CHK-00" in r.stdout


def test_exit1_fora_de_repo(tmp_path):
    r = _run([], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)


def test_perfil_invalido_via_cli_e_erro(tmp_path):
    root, _todo = _repo(tmp_path, TODO_OK)
    r = _run(["--profile", "bogus"], cwd=root)
    assert r.returncode == 1, (r.stdout, r.stderr)


# ------------------------- --audit e sempre read-only (CLI real) ---------------

def test_cli_read_only_mesmo_com_achados_e_flags_diversas(tmp_path):
    root, todo = _repo(tmp_path, TODO_ID_COM_ESPACO)
    antes = _md5(todo)
    for args in ([], ["--profile", "casa"], ["-v"], ["--max-per-check", "1"]):
        _run(args, cwd=root)
        assert _md5(todo) == antes, f"TODO.md mudou depois de {args}"


# ------------------------------ dogfooding real ---------------------------------

def test_dogfood_proprio_repo():
    """Roda --audit contra o TODO.md deste proprio repo -- read-only e exit
    code valido (0 ou 2, nunca 1: o TODO.md deste repo e bem-formado)."""
    todo_path = os.path.join(REPO_ROOT, "TODO.md")
    antes = _md5(todo_path)
    r = _run([], cwd=REPO_ROOT)
    depois = _md5(todo_path)
    assert antes == depois
    assert r.returncode in (0, 2), (r.stdout, r.stderr)


@pytest.mark.parametrize("env_var", ["TAB_PENDENCIAS_FIXTURE_A",
                                      "TAB_PENDENCIAS_FIXTURE_B"])
def test_dogfood_fixture_real_read_only(env_var):
    path = os.environ.get(env_var)
    if not path or not os.path.isfile(path):
        pytest.skip(f"{env_var} nao configurada (fixture local, nunca commitada)")
    antes = _md5(path)
    r = _run([], cwd=os.path.dirname(path))
    depois = _md5(path)
    assert antes == depois
    assert r.returncode in (0, 2), (r.stdout, r.stderr)


# --------------------- compatibilidade de sintaxe (piso de Python) -------------
#
# D-9 fixa que o produto nao pode exigir Python 3.11+ (tomllib); o piso real
# (RHEL9 = 3.9, Ubuntu 22.04 = 3.10) nunca foi testado em CI nem declarado em
# lugar nenhum do repo (achado do proprio team-lead, ADR-0001 nao fecha essa
# lacuna). Estes testes NAO fecham essa lacuna (fatia de outro item) -- so
# provam que `todo_audit.py`, especificamente, nao introduz sintaxe PEP 604
# (`int | None`, `list[X]`) que quebraria SEM o `from __future__ import
# annotations` presente no topo do arquivo.

def test_future_annotations_presente():
    """`from __future__ import annotations` e o que torna `int | None` e
    `list[X]` seguros em Python < 3.10 (PEP 563: a anotacao vira string,
    nunca e avaliada como expressao em runtime) -- sem ele, os `X | None`
    usados neste modulo quebrariam na IMPORTACAO em 3.9/3.10."""
    with open(AUDIT, encoding="utf-8") as fh:
        conteudo = fh.read()
    assert "from __future__ import annotations" in conteudo


def test_uniao_pep604_so_aparece_em_posicao_de_anotacao():
    """Mais forte que so checar a presenca do future import: prova, via AST,
    que todo uso de `|` (BitOr) no modulo esta em posicao de ANOTACAO
    (protegida pelo future import), nunca como expressao avaliada em
    runtime (isso SIM quebraria em Python < 3.10, mesmo com o future
    import -- PEP 563 so protege anotacoes, nao expressao qualquer)."""
    import ast

    with open(AUDIT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=AUDIT)

    anotacoes = set()

    class _ColetaAnotacoes(ast.NodeVisitor):
        def visit_AnnAssign(self, node):
            anotacoes.add(id(node.annotation))
            self.generic_visit(node)

        def _visit_func(self, node):
            for a in list(node.args.args) + list(node.args.posonlyargs) + \
                    list(node.args.kwonlyargs):
                if a.annotation is not None:
                    anotacoes.add(id(a.annotation))
            if node.returns is not None:
                anotacoes.add(id(node.returns))
            self.generic_visit(node)

        visit_FunctionDef = _visit_func
        visit_AsyncFunctionDef = _visit_func

    _ColetaAnotacoes().visit(tree)

    # BitOr pode aparecer ANINHADO dentro de uma anotacao maior (ex.: o
    # BinOp de "int | None" e filho do no de anotacao coletado, nao o
    # proprio no) -- por isso marca todo DESCENDENTE (incl. ele mesmo) de
    # cada anotacao coletada como "protegido", antes de procurar BitOr
    # fora dessa marca.
    dentro = set()
    for node in ast.walk(tree):
        if id(node) in anotacoes:
            for sub in ast.walk(node):
                dentro.add(id(sub))

    fora_de_anotacao = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
        and id(node) not in dentro
    ]

    assert fora_de_anotacao == [], (
        f"BitOr ('|') fora de posicao de anotacao nas linhas "
        f"{fora_de_anotacao} -- quebraria em Python < 3.10 mesmo com "
        "from __future__ import annotations (que so protege anotacoes)")


def test_modulo_importa_em_outras_versoes_de_python_instaladas():
    """Prova adicional (proxy, nao substitui um piso 3.9 real -- esta
    maquina so tem 3.11+): importa o modulo e constroi 1 Check por
    subprocess em toda versao de python3.X !=  a corrente que estiver no
    PATH. Se nenhuma outra versao estiver instalada, skip (nao e falha:
    so significa que a maquina nao oferece mais nenhum proxy de
    compatibilidade alem do interpretador default)."""
    import shutil

    candidatos = ["python3.9", "python3.10", "python3.11", "python3.12",
                  "python3.13"]
    encontrados = [c for c in candidatos if shutil.which(c)
                   and shutil.which(c) != sys.executable]
    if not encontrados:
        pytest.skip("nenhuma outra versao de python3.X disponivel nesta "
                    "maquina para testar como proxy de compatibilidade")
    script = (
        f"import sys; sys.path.insert(0, {TOOLS_DIR!r}); import todo_audit as A; "
        "c = A.Check(id='X', title='t', profile='core', "
        "severity_default='COSMÉTICO', run=lambda ctx: []); "
        "print('OK', c.id)"
    )
    for exe in encontrados:
        r = subprocess.run([exe, "-c", script], capture_output=True, text=True)
        assert r.returncode == 0, (exe, r.stdout, r.stderr)
        assert "OK X" in r.stdout, (exe, r.stdout, r.stderr)


# ------------------------------ --todo PATH (AUDIT-PATH) -----------------------
#
# `--todo PATH` audita um TODO.md que NAO precisa estar no cwd corrente nem
# no mesmo repositorio git -- necessario para AC-REAL (W8) rodar --audit
# contra as fixtures dos consumidores A/B, que vivem FORA deste repositorio
# e nunca podem ser copiadas para dentro dele.

def _repo_em(root_dir, todo_text=TODO_OK, com_git=True):
    """Cria um TODO.md em `root_dir`; se `com_git`, inicializa um repo git
    isolado (HOOKISO-1) ali tambem. Devolve o Path do TODO.md."""
    root_dir.mkdir(parents=True, exist_ok=True)
    if com_git:
        _git_init_isolado(root_dir)
    todo = root_dir / "TODO.md"
    todo.write_text(todo_text, encoding="utf-8")
    if com_git:
        _git(root_dir, "add", "TODO.md")
        _git(root_dir, "commit", "-qm", "tabela")
    return todo


def test_todo_flag_audita_arquivo_fora_do_cwd_atual(tmp_path):
    """O cwd de invocacao nao e sequer repositorio git, e mesmo assim o
    alvo (outro repo) e auditado corretamente via --todo."""
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    alvo_root = tmp_path / "alvo"
    todo_alvo = _repo_em(alvo_root, TODO_ID_COM_ESPACO)

    r = _run(["--todo", str(todo_alvo)], cwd=invocador)
    assert r.returncode == 2, (r.stdout, r.stderr)   # CHK-00 acha o ID com espaco
    assert "CHK-00" in r.stdout
    assert str(todo_alvo) in r.stdout


def test_todo_flag_read_only_hash_identico(tmp_path):
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    alvo_root = tmp_path / "alvo"
    todo_alvo = _repo_em(alvo_root, TODO_ID_COM_ESPACO)
    antes = _md5(todo_alvo)
    _run(["--todo", str(todo_alvo)], cwd=invocador)
    depois = _md5(todo_alvo)
    assert antes == depois


def test_todo_flag_arquivo_solto_sem_git_ainda_funciona_com_aviso(tmp_path):
    """Alvo SEM nenhum repositorio git acima dele: checks estruturais
    (CHK-00, que nao depende de git) continuam rodando; o motor DECLARA a
    ausencia de contexto git explicitamente (no silent caps) em vez de
    deixar CHK-09/CHK-10 falharem contexto por contexto sem explicacao
    sistemica."""
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    alvo_root = tmp_path / "solto"
    todo_alvo = _repo_em(alvo_root, TODO_ID_COM_ESPACO, com_git=False)

    r = _run(["--todo", str(todo_alvo)], cwd=invocador)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "CHK-00" in r.stdout
    assert "repositorio git" in r.stdout.lower()


def test_todo_flag_basename_diferente_de_todo_md_e_erro(tmp_path):
    """Restricao deliberada: --todo so aceita um arquivo chamado EXATAMENTE
    'TODO.md' (a mesma convencao hardcoded em L.find_todo). Sem isso,
    CHK-11 (que re-descobre 'root/TODO.md' via todo_health.run(root=...))
    compararia contra um arquivo diferente do auditado, ou nenhum -- e o
    relatorio passaria a impressao de ter verificado algo que nao
    verificou."""
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    alvo_root = tmp_path / "alvo"
    alvo_root.mkdir()
    outro = alvo_root / "pendencias.md"
    outro.write_text(TODO_OK, encoding="utf-8")

    r = _run(["--todo", str(outro)], cwd=invocador)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""
    assert "TODO.md" in r.stderr


def test_todo_flag_arquivo_inexistente_e_erro_sem_traceback_cru(tmp_path):
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    inexistente = tmp_path / "nao-existe" / "TODO.md"

    r = _run(["--todo", str(inexistente)], cwd=invocador)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Traceback" not in r.stderr
    assert r.stderr.strip() != ""


def test_todo_flag_relativo_e_resolvido_para_absoluto(tmp_path):
    _repo_em(tmp_path / "alvo", TODO_OK)
    r = _run(["--todo", os.path.join("alvo", "TODO.md")], cwd=tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_sem_todo_flag_continua_exigindo_repo_git_no_cwd(tmp_path):
    """Preserva o comportamento ATUAL: sem --todo, o cwd precisa ser repo
    git -- --todo e estritamente aditivo, nunca muda o caminho default."""
    r = _run([], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)


def test_todo_flag_output_protegido_contra_o_repo_do_alvo_nao_do_cwd(tmp_path):
    """--output continua proibido de escrever dentro do repo do ALVO (nao
    do cwd de invocacao, que pode ser um repo totalmente diferente)."""
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    _git_init_isolado(invocador)
    alvo_root = tmp_path / "alvo"
    todo_alvo = _repo_em(alvo_root, TODO_OK)

    dentro_do_alvo = alvo_root / "relatorio.txt"
    r = _run(["--todo", str(todo_alvo), "--output", str(dentro_do_alvo)],
             cwd=invocador)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert not dentro_do_alvo.exists()

    fora = tmp_path / "relatorio-fora.txt"
    r2 = _run(["--todo", str(todo_alvo), "--output", str(fora)], cwd=invocador)
    assert r2.returncode == 0, (r2.stdout, r2.stderr)
    assert fora.exists()


def test_todo_flag_com_contexto_git_correto_chk10_nao_reclama_de_repo(tmp_path):
    """CHK-10 roda `todo_sync.py` com cwd=raiz resolvida do ALVO -- se a
    resolucao estiver correta (git auto-descobre a partir de QUALQUER
    subdir da arvore), CHK-10 nunca deve embutir 'Nao e um repositorio
    git' quando o alvo de fato mora dentro de um repo git valido."""
    invocador = tmp_path / "invocador"
    invocador.mkdir()
    alvo_root = tmp_path / "alvo"
    todo_alvo = _repo_em(alvo_root, TODO_OK)

    r = _run(["--todo", str(todo_alvo)], cwd=invocador)
    assert "Nao e um repositorio git" not in r.stdout
