# tests/test_guard_stdlib_imports.py -- GUARD-FP
#
# O guard tools/ci/guard_stdlib_imports.py precisa distinguir import
# INTERNO do proprio projeto (ex.: `tools/todo_audit.py` fazendo
# `import checks.chk_graph`, onde `tools/checks/` e um pacote deste
# repositorio) de import de dependencia de TERCEIRO -- so o segundo viola
# o invariante "nucleo e stdlib pura" que o guard substitui (scanning de
# dependencia/CVE cortado do escopo, ver TODO.md/CI-1).
import os
import sys

import ci.guard_stdlib_imports as guard

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_guard_passa_limpo_no_proprio_repo():
    """Regressao do bug real: tools/todo_audit.py importa
    `checks.chk_graph`/`chk_frescor`/`chk_core` -- pacote `tools/checks/`
    deste MESMO repositorio, nao dependencia externa. O guard nao pode
    acusar isso."""
    from pathlib import Path
    exit_code = guard.main([os.path.join(REPO_ROOT, "tools")])
    assert exit_code == 0


def test_resolve_pacote_interno_com_init_e_permitido(tmp_path):
    """`import pkg.mod` resolve para arquivo real do proprio projeto
    (`root/pkg/__init__.py` + `root/pkg/mod.py`) -- deve ser permitido,
    sem depender de lista de nomes."""
    root = tmp_path / "raiz"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("VALOR = 1\n")
    (root / "consumidor.py").write_text("import pkg.mod\n")

    violacoes = guard.check_file(root / "consumidor.py", root)
    assert violacoes == []


def test_import_de_terceiro_real_ainda_e_acusado(tmp_path):
    """Prova que o guard continua discriminante: um nome que nao resolve
    para nenhum arquivo real da arvore (nem pacote, nem modulo) e uma
    dependencia de terceiro de verdade -- tem de ser acusado."""
    root = tmp_path / "raiz"
    root.mkdir()
    (root / "consumidor.py").write_text("import pacote_terceiro_inexistente\n")

    violacoes = guard.check_file(root / "consumidor.py", root)
    assert len(violacoes) == 1
    assert "pacote_terceiro_inexistente" in violacoes[0]


def test_import_de_terceiro_com_prefixo_igual_a_pacote_local_ainda_e_acusado(tmp_path):
    """Um pacote local `checks/` nao deve abrir excecao para nomes
    diferentes que apenas comecam igual (ex.: `checks2`) nem para
    submodulo que nao existe de fato dentro do pacote local."""
    root = tmp_path / "raiz"
    pkg = root / "checks"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "chk_core.py").write_text("")
    (root / "consumidor.py").write_text(
        "import checks2\n"
        "import checks.modulo_que_nao_existe\n"
    )

    violacoes = guard.check_file(root / "consumidor.py", root)
    assert len(violacoes) == 2


def test_import_from_pacote_interno_e_permitido(tmp_path):
    root = tmp_path / "raiz"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("VALOR = 1\n")
    (root / "consumidor.py").write_text("from pkg import mod\n")

    violacoes = guard.check_file(root / "consumidor.py", root)
    assert violacoes == []


def test_import_relativo_sempre_permitido(tmp_path):
    root = tmp_path / "raiz"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from . import b\n")
    (pkg / "b.py").write_text("")

    violacoes = guard.check_file(pkg / "a.py", root)
    assert violacoes == []


def test_import_flat_de_irmao_no_mesmo_nivel_e_permitido(tmp_path):
    """Layout flat (sem pacote): `import todo_lib` dentro de outro modulo
    no mesmo diretorio -- caso ja suportado antes desta correcao."""
    root = tmp_path / "raiz"
    root.mkdir()
    (root / "todo_lib.py").write_text("VALOR = 1\n")
    (root / "todo_sync.py").write_text("import todo_lib\n")

    violacoes = guard.check_file(root / "todo_sync.py", root)
    assert violacoes == []


def test_stdlib_continua_permitido(tmp_path):
    root = tmp_path / "raiz"
    root.mkdir()
    (root / "consumidor.py").write_text("import os\nimport json\nfrom pathlib import Path\n")

    violacoes = guard.check_file(root / "consumidor.py", root)
    assert violacoes == []
