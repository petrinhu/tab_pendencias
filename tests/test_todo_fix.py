"""Suíte do motor de `--fix` (FIX-ENG, ADR-0001 seção c): `tools/todo_fix.py`.

Fatia de MAIOR risco do projeto -- todas as outras leem, esta ESCREVE no
TODO.md do usuário. Por isso a suíte cobre, além da lógica de correção:
precondição de árvore limpa, escrita atômica com prova ANTES de commitar,
CRLF/BOM, tabela legada de 8 colunas, arquivo somente-leitura e interrupção
no meio da escrita.

`--fix` consome `Finding.fixable`/`fix_ref` já decidido pelos checks (CHK-01/
CHK-02) -- nunca redecide fixabilidade (ADR-0001 c). Hoje só dois `fix_ref`
são de fato produzidos pelo catálogo registrado: `escapar_pipe_cru` (CHK-02)
e `remover_fragmento_duplicado` (CHK-01); CHK-03/CHK-04/CHK-09 nunca marcam
`fixable=True` na implementação atual, então "consolidar tabela fragmentada"
e "corrigir claim obsoleta" (previstos no ADR/TODO.md) não têm nenhum
achado real para consumir ainda -- ver nota no relatório final, não é
lacuna desta fatia.
"""
import os
import subprocess
import sys

import pytest
import todo_fix as F
import todo_lib as L
from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
FIX = os.path.join(TOOLS_DIR, "todo_fix.py")

# ACHADO (CI-2, prova local 2026-08-16): jobs de container do GitHub Actions
# rodam como root por padrao, e root ignora bits de permissao POSIX -- um
# `chmod 0o555` (sem escrita) no diretorio nao bloqueia a escrita do PROPRIO
# root nele. Reproduzido com podman/docker (archlinux:latest): a mesma
# suite, mesmo cenario, da rc=2/applied=True como root em vez do
# rc=1/applied=False esperado como usuario comum -- nao e regressao do
# codigo, e o ambiente tornando a precondicao do teste inalcancavel. A
# condicao do skip abaixo e ROOT (EUID==0), nunca "container" nem "Linux":
# em usuario comum, dentro OU fora de container, o teste roda normal (e
# roda -- ver `tools/ci/` archlinux/debian/fedora quando o passo de
# privilege-drop existir). `os.geteuid` nao existe no Windows; a guarda
# `hasattr` evita AttributeError la sem nunca produzir skip falso (no
# Windows a condicao e sempre False, o teste roda).
_RODANDO_COMO_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, env=_ENV, capture_output=True,
                    check=True)


def _run_cli(args, cwd):
    return subprocess.run([sys.executable, FIX, *args], cwd=cwd,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)

# Linha com pipe cru DENTRO de code span -- 1 celula a mais (10 obtidas, 9
# esperadas); o unico pipe cru esta dentro das cracases, posicao inequivoca.
LINHA_PIPE_CRU = (
    "| P-01 | W1 | Core | Prova `nm x.a | grep -E gl` = 0 | Alta | — | "
    "Média | ⏳ Pendente | — |\n"
)
LINHA_PIPE_ESCAPADA = (
    "| P-01 | W1 | Core | Prova `nm x.a \\| grep -E gl` = 0 | Alta | — | "
    "Média | ⏳ Pendente | — |\n"
)

TODO_PIPE_CRU = HEADER_9 + LINHA_PIPE_CRU

# Duplicata onde só a célula Estado Auditado diverge por placeholder vazio
# ("—") vs conteúdo real -- candidato inequívoco de fragmento/lixo (mesma
# heurística de chk_core._candidato_fragmento).
TODO_DUP_FRAGMENTO = (
    HEADER_9 +
    "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
    "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | ✓ |\n"
)

TODO_LIMPO = HEADER_9 + (
    "| V-1 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
)

# Tabela legada de 8 colunas (sem "Onda") -- ADR-0001 (b.2): ncols deriva do
# cabeçalho real, nunca de uma constante 9.
HEADER_8 = (
    "| ID | Grupo | Descrição | Prioridade | Pré-requisito | Dificuldade | "
    "Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- |\n"
)
LINHA_8_PIPE_CRU = (
    "| P-01 | Core | Prova `nm x.a | grep -E gl` = 0 | Alta | — | Média | "
    "⏳ Pendente | — |\n"
)
TODO_8_PIPE_CRU = HEADER_8 + LINHA_8_PIPE_CRU


def _repo(tmp_path, todo_text, filename="TODO.md"):
    _git_init_isolado(tmp_path)
    todo = tmp_path / filename
    todo.write_bytes(todo_text.encode("utf-8"))
    _git(tmp_path, "add", filename)
    _git(tmp_path, "commit", "-qm", "tabela inicial")
    return tmp_path, todo


# ------------------------------- build_plan --------------------------------

def test_build_plan_vazio_em_corpus_limpo(tmp_path):
    root, todo = _repo(tmp_path, TODO_LIMPO)
    plan = F.build_plan(str(root))
    assert plan.items == []


def test_build_plan_detecta_pipe_cru_como_escapar_pipe_cru(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    plan = F.build_plan(str(root))
    assert len(plan.items) == 1
    it = plan.items[0]
    assert it.fix_ref == "escapar_pipe_cru"
    assert it.check_id == "CHK-02"
    assert it.aplicavel is True
    assert "\\|" in it.diff or "escapad" in it.diff.lower()


def test_build_plan_detecta_duplicata_fragmento_como_remover(tmp_path):
    root, todo = _repo(tmp_path, TODO_DUP_FRAGMENTO)
    plan = F.build_plan(str(root))
    assert len(plan.items) == 1
    it = plan.items[0]
    assert it.fix_ref == "remover_fragmento_duplicado"
    assert it.check_id == "CHK-01"
    assert it.aplicavel is True
    # mostra o diff das DUAS linhas envolvidas antes de aplicar
    assert "V-9" in it.diff


def test_build_plan_sem_todo_md(tmp_path):
    _git_init_isolado(tmp_path)
    (tmp_path / "readme.txt").write_text("x")
    _git(tmp_path, "add", "readme.txt")
    _git(tmp_path, "commit", "-qm", "init")
    plan = F.build_plan(str(tmp_path))
    assert plan.items == [] and plan.todo_path is None


# --------------------------------- dry-run ----------------------------------

def test_run_fix_dry_run_nao_toca_arquivo(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()
    result = F.run_fix(str(root))
    assert result.rc == 2                     # ha achado(s), mas nao aplicou
    assert result.applied is False
    assert todo.read_bytes() == antes          # NUNCA escreve sem --apply


def test_run_fix_dry_run_exit0_sem_achados(tmp_path):
    root, todo = _repo(tmp_path, TODO_LIMPO)
    result = F.run_fix(str(root))
    assert result.rc == 0
    assert result.applied is False


# ------------------------------ --apply: escapar ----------------------------

def test_apply_escapar_pipe_cru_corrige_e_preserva_resto(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    result = F.run_fix(str(root), apply_classes=["escapar_pipe_cru"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_bytes().decode("utf-8")
    assert "\\|" in novo
    # o item passa a ser reconhecido pelo parser (deixou de ser malformed)
    tbl = L.parse_table(novo)
    ids = [i["id"] for i in tbl["items"]]
    assert "P-01" in ids
    assert tbl["malformed"] == []


def test_apply_escapar_pipe_cru_nao_mexe_no_resto_do_arquivo(tmp_path):
    texto = HEADER_9 + LINHA_PIPE_CRU + (
        "| V-2 | W1 | Core | Outro item | Alta | — | Média | "
        "🔄 Em andamento | — |\n")
    root, todo = _repo(tmp_path, texto)
    F.run_fix(str(root), apply_classes=["escapar_pipe_cru"])
    novo = todo.read_text(encoding="utf-8")
    assert "| V-2 | W1 | Core | Outro item | Alta | — | Média | " \
           "🔄 Em andamento | — |\n" in novo


# ------------------------------ --apply: remover ----------------------------

def test_apply_remover_fragmento_duplicado_remove_a_linha_certa(tmp_path):
    root, todo = _repo(tmp_path, TODO_DUP_FRAGMENTO)
    tbl_antes = L.parse_table(TODO_DUP_FRAGMENTO)
    n_antes = len(tbl_antes["items"])
    result = F.run_fix(str(root), apply_classes=["remover_fragmento_duplicado"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl_novo = L.parse_table(novo)
    assert len(tbl_novo["items"]) == n_antes - 1
    assert tbl_novo["duplicate_ids"] == {}
    # a ocorrencia MANTIDA e a que tinha o "✓" (conteudo real), nao a
    # placeholder "—" -- prova de que a heuristica escolheu o lado certo.
    assert novo.count("| ✓ |") == 1
    assert "V-9" in novo


# ------------------------------ --apply all ---------------------------------

def test_apply_all_aplica_as_duas_classes_no_mesmo_arquivo(tmp_path):
    texto = HEADER_9 + LINHA_PIPE_CRU + (
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | ✓ |\n")
    root, todo = _repo(tmp_path, texto)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl = L.parse_table(novo)
    assert tbl["malformed"] == []
    assert tbl["duplicate_ids"] == {}
    ids = [i["id"] for i in tbl["items"]]
    assert ids.count("P-01") == 1 and ids.count("V-9") == 1


# ------------------------- precondição: árvore limpa ------------------------

def test_apply_aborta_se_working_tree_do_todo_sujo(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    todo.write_text(todo.read_text(encoding="utf-8") + "\n<!-- edicao em voo -->\n",
                    encoding="utf-8")           # modificacao NAO commitada
    sujo_antes = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace").stdout
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 1
    assert result.applied is False
    sujo_depois = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout
    assert sujo_antes == sujo_depois           # nada mudou, nem o dirty-diff


def test_apply_prossegue_com_working_tree_limpa(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True


def test_apply_aborta_sem_repositorio_git_resolvivel(tmp_path):
    """`run_fix` chamado direto (não via CLI, que já barra 'fora de repo'
    antes) sobre um diretorio SEM `git init` -- a precondição de árvore
    limpa não consegue provar nada sem git, e trata isso como sujo por
    segurança (nunca aplica sem conseguir provar)."""
    todo = tmp_path / "TODO.md"
    todo.write_bytes(TODO_PIPE_CRU.encode("utf-8"))
    result = F.run_fix(str(tmp_path), apply_classes=["all"])
    assert result.rc == 1
    assert result.applied is False
    assert todo.read_bytes() == TODO_PIPE_CRU.encode("utf-8")


def test_dry_run_nao_exige_working_tree_limpa(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    todo.write_text(todo.read_text(encoding="utf-8") + "\n<!-- edicao em voo -->\n",
                    encoding="utf-8")
    result = F.run_fix(str(root))              # sem apply_classes = dry-run
    assert result.rc == 2                      # so mostra, nao precisa de arvore limpa
    assert result.applied is False


# --------------------------- CRLF / BOM / legado -----------------------------

def test_apply_preserva_crlf(tmp_path):
    texto = (HEADER_9 + LINHA_PIPE_CRU).replace("\n", "\r\n")
    root, todo = _repo(tmp_path, texto)
    antes_crlf = todo.read_bytes().count(b"\r\n")
    F.run_fix(str(root), apply_classes=["all"])
    depois = todo.read_bytes()
    assert depois.count(b"\r\n") == antes_crlf
    assert b"\\|" in depois


def test_apply_preserva_bom(tmp_path):
    texto = "﻿" + HEADER_9 + LINHA_PIPE_CRU
    root, todo = _repo(tmp_path, texto)
    F.run_fix(str(root), apply_classes=["all"])
    depois = todo.read_bytes().decode("utf-8")
    assert depois.startswith("﻿")
    assert "\\|" in depois


def test_apply_funciona_em_tabela_legada_8_colunas(tmp_path):
    root, todo = _repo(tmp_path, TODO_8_PIPE_CRU)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl = L.parse_table(novo)
    assert tbl["ncols"] == 8
    assert tbl["malformed"] == []
    assert "P-01" in [i["id"] for i in tbl["items"]]


# --------------------------- casos que dao medo ------------------------------

@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason=(
        "WIN-CHMOD-1 (medido no CI, 16/08/26): a premissa POSIX do teste -- "
        "os.replace()/rename() ignora os bits do ARQUIVO-alvo, so exige "
        "escrita no diretorio -- nao vale no Windows. La, "
        "MoveFileEx/ReplaceFile RECUSA destino com o atributo somente-"
        "leitura (o proprio docstring abaixo ja previa essa divergencia). "
        "O produto trata isso corretamente (OSError generico ao redor de "
        "os.replace em _escrever_atomico -> rc=1 limpo, sem corromper o "
        "TODO.md original -- ver test_apply_interrupcao_no_replace_nao_"
        "corrompe_original), entao isto e uma diferenca de SEMANTICA DE "
        "PLATAFORMA a documentar, nao um defeito a consertar."
    ),
)
def test_apply_arquivo_somente_leitura_e_substituido_via_rename_atomico(tmp_path):
    """No POSIX, `os.replace` e um `rename()`: exige permissao de ESCRITA no
    DIRETORIO (proximo teste), nao no arquivo-alvo -- os bits do proprio
    arquivo nao bloqueiam a troca de entrada de diretorio. Por isso um
    TODO.md somente-leitura (0o444) e substituido normalmente aqui; a
    escrita atomica e o que faz essa propriedade valer (escrita in-place
    teria falhado com PermissionError no open("w") do arquivo real). No
    Windows o comportamento pode divergir (MoveFileEx pode recusar destino
    somente-leitura) -- coberto pelo tratamento generico de OSError ao redor
    de `os.replace`, testado separadamente (interrupcao simulada)."""
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    os.chmod(todo, 0o444)
    try:
        result = F.run_fix(str(root), apply_classes=["all"])
    finally:
        os.chmod(todo, 0o644)
    assert result.rc == 2 and result.applied is True
    assert "\\|" in todo.read_text(encoding="utf-8")


@pytest.mark.skipif(
    _RODANDO_COMO_ROOT,
    reason=(
        "root ignora bits de permissao POSIX -- chmod 0o555 no diretorio "
        "nao bloqueia escrita do proprio root nele, entao a precondicao "
        "do teste (escrita deve falhar) nunca se estabelece. Condicao e "
        "EUID==0 (nao container, nao plataforma): roda normal como "
        "usuario comum em qualquer SO/ambiente, inclusive dentro de "
        "container."
    ),
)
@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason=(
        "WIN-CHMOD-1 (medido no CI, 16/08/26): os.chmod() no Windows nao "
        "implementa os bits de execucao/escrita POSIX para DIRETORIOS (so "
        "alterna o atributo somente-leitura de ARQUIVO) -- chmod 0o555 "
        "aqui e um no-op, a escrita do TODO.md tem sucesso normalmente, e "
        "a precondicao do teste (escrita deve falhar) nunca se "
        "estabelece. Diferenca de modelo de permissao da plataforma, nao "
        "um defeito do produto."
    ),
)
def test_apply_diretorio_sem_permissao_de_escrita_falha_limpo(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()
    os.chmod(root, 0o555)
    try:
        result = F.run_fix(str(root), apply_classes=["all"])
        assert result.rc == 1
        assert result.applied is False
    finally:
        os.chmod(root, 0o755)
    assert todo.read_bytes() == antes


def test_apply_interrupcao_no_replace_nao_corrompe_original(tmp_path, monkeypatch):
    """OSError generico em os.replace (PermissionError, readonly Windows,
    interrupcao) -> rc=1, TODO intacto, tmp limpo. FIX-RISCO-C: o CI nao
    exercita o path real de destino somente-leitura no Windows; este mock
    prova o handling generico que cobre esse residual."""
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()

    def _replace_quebrado(*a, **kw):
        raise OSError("interrupcao simulada no meio da escrita")

    monkeypatch.setattr(F.os, "replace", _replace_quebrado)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 1
    assert result.applied is False
    assert todo.read_bytes() == antes          # original intacto
    assert "falha de I/O" in result.report_text
    assert "OSError" in result.report_text
    # nenhum arquivo temporario orfao deixado no diretorio
    sobras = [f for f in os.listdir(root) if "todo_fix" in f or f.endswith(".tmp")]
    assert sobras == [], sobras


def test_apply_oserror_generico_permission_error(tmp_path, monkeypatch):
    """PermissionError e subclasse de OSError; handling generico sem
    corromper (mesma rede de seguranca que cobriria readonly Windows)."""
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()

    def _replace_negado(*a, **kw):
        raise PermissionError("destino somente-leitura simulado")

    monkeypatch.setattr(F.os, "replace", _replace_negado)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 1
    assert result.applied is False
    assert todo.read_bytes() == antes
    assert "falha de I/O" in result.report_text
    assert "PermissionError" in result.report_text


# ------------------------------ lock em --apply -----------------------------

def test_apply_com_lock_held_timeout_e_todo_intacto(tmp_path):
    """Segundo --apply com lock ocupado: timeout, rc=1, TODO intacto
    (FIX-RISCO-A/B)."""
    import threading

    import todo_lock as LK

    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()
    lock_path = LK.default_lock_path(str(todo))
    held = threading.Event()
    release = threading.Event()

    def holder():
        with LK.TodoWriteLock(str(todo), lock_path=lock_path, timeout=5.0):
            held.set()
            release.wait(timeout=5.0)

    th = threading.Thread(target=holder)
    th.start()
    assert held.wait(timeout=2.0), "holder nao adquiriu"

    result = F.run_fix(
        str(root), apply_classes=["all"], lock_timeout=0.25,
    )
    release.set()
    th.join(timeout=3.0)

    assert result.rc == 1
    assert result.applied is False
    assert "todo_lock" in result.report_text.lower() or "timeout" in (
        result.report_text.lower()
    )
    assert todo.read_bytes() == antes


def test_apply_reentrant_sob_mesmo_lock(tmp_path):
    """run_fix apply sob lock ja detido no mesmo thread reusa (reentrancy)."""
    import todo_lock as LK

    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    lock_path = LK.default_lock_path(str(todo))
    with LK.TodoWriteLock(str(todo), lock_path=lock_path, timeout=2.0):
        result = F.run_fix(str(root), apply_classes=["all"], lock_timeout=2.0)
    assert result.rc == 2 and result.applied is True
    assert "\\|" in todo.read_text(encoding="utf-8")


def test_dry_run_nao_adquire_lock(tmp_path):
    """Dry-run nao pede lock: com lock held de outro thread ainda roda e
    nao escreve (preferencia: dry-run sem lock)."""
    import threading

    import todo_lock as LK

    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()
    lock_path = LK.default_lock_path(str(todo))
    held = threading.Event()
    release = threading.Event()

    def holder():
        with LK.TodoWriteLock(str(todo), lock_path=lock_path, timeout=5.0):
            held.set()
            release.wait(timeout=5.0)

    th = threading.Thread(target=holder)
    th.start()
    assert held.wait(timeout=2.0)

    result = F.run_fix(str(root))  # dry-run
    release.set()
    th.join(timeout=3.0)

    assert result.rc == 2
    assert result.applied is False
    assert todo.read_bytes() == antes


def test_apply_recusa_se_releitura_do_arquivo_temporario_diverge(tmp_path, monkeypatch):
    """Prova dedicada da releitura byte-a-byte ANTES do swap (achado do
    mutation testing desta fatia: em disco saudavel a releitura NUNCA
    diverge de verdade, entao sem este mock nenhum teste natural exercita
    esse caminho de defesa -- ele existiria no codigo mas nunca seria
    provado). Simula uma releitura corrompida (bit-flip hipotetico de
    disco); o motor tem que abortar ANTES do `os.replace`, sem tocar o
    TODO.md real e sem deixar arquivo temporario orfao."""
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()
    monkeypatch.setattr(F, "_ler_de_volta",
                        lambda tmp_path: "conteudo corrompido, diverge do escrito")
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 1
    assert result.applied is False
    assert todo.read_bytes() == antes
    sobras = [f for f in os.listdir(root) if "todo_fix" in f or f.endswith(".tmp")]
    assert sobras == [], sobras


def test_verificacao_pre_escrita_recusa_quando_posicao_do_pipe_e_ambigua(tmp_path):
    """Duas celulas a mais (got=11, esperado=9), mas so 1 pipe cru esta
    DENTRO de code span (o `a | b`) -- o outro excesso ("x | y", fora de
    crase) e ambiguo demais para localizar com seguranca. O motor RECUSA
    aplicar em vez de adivinhar qual pipe escapar."""
    linha_ambigua = (
        "| P-02 | W1 | Core | Prova `a | b` end | Alta | x | y | Média | "
        "⏳ Pendente | — |\n"
    )
    texto = HEADER_9 + linha_ambigua
    root, todo = _repo(tmp_path, texto)
    plan = F.build_plan(str(root))
    assert len(plan.items) == 1
    assert plan.items[0].aplicavel is False
    assert plan.items[0].motivo_recusa
    result = F.run_fix(str(root), apply_classes=["all"])
    # nada aplicavel -> nao escreve nada
    assert todo.read_bytes().decode("utf-8") == texto


# ------------------------------ prova de contagem ---------------------------

def test_apply_declara_contagem_esperada_antes_de_remover(tmp_path):
    root, todo = _repo(tmp_path, TODO_DUP_FRAGMENTO)
    plan = F.build_plan(str(root))
    it = plan.items[0]
    assert it.delta_itens == -1


def test_apply_escape_bem_sucedido_soma_um_item_novo(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    plan = F.build_plan(str(root))
    it = plan.items[0]
    assert it.delta_itens == 1


# --------------------------------- CLI --------------------------------------

def test_cli_help_exit0(tmp_path):
    r = _run_cli(["--help"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "--apply" in r.stdout


def test_cli_flag_desconhecida_erro(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    r = _run_cli(["--aply", "all"], cwd=root)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""


def test_cli_classe_invalida_erro(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    r = _run_cli(["--apply", "classe_que_nao_existe"], cwd=root)
    assert r.returncode == 1, (r.stdout, r.stderr)


def test_cli_fora_de_repo_git(tmp_path):
    r = _run_cli([], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)


def test_cli_dry_run_exit2_e_nao_escreve(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    antes = todo.read_bytes()
    r = _run_cli([], cwd=root)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert todo.read_bytes() == antes


def test_cli_apply_exit2_e_escreve(tmp_path):
    root, todo = _repo(tmp_path, TODO_PIPE_CRU)
    r = _run_cli(["--apply", "escapar_pipe_cru"], cwd=root)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "\\|" in todo.read_text(encoding="utf-8")


# --------------------- prova direta de _provar_invariantes ------------------
#
# `_provar_invariantes` só é exercitada hoje, via `run_fix`, com os dados que
# `_montar_novo_texto` monta a partir da MESMA tabela -- tautologicamente
# consistentes por construção, então nenhum cenário natural de `run_fix`
# jamais faz a checagem "linha preservada bate byte-a-byte" reprovar (achado
# do mutation testing desta fatia: remover essa checagem inteira não muda
# nenhum resultado de teste via `run_fix`). Os dois testes abaixo chamam a
# função de prova DIRETAMENTE com invariantes sintéticos deliberadamente
# incoerentes, provando que ela É uma rede de segurança de verdade -- não
# decorativa -- para o dia em que um bug futuro em `_montar_novo_texto`
# produzir dados inconsistentes.

def test_provar_invariantes_recusa_quando_linha_preservada_diverge():
    texto = "| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n"
    # texto.split("\n") -> 4 elementos (o 4o e "" do \n final)
    invariantes = {
        "n_linhas_esperado": 4,
        "linhas_preservadas": {2: "linha deliberadamente ERRADA"},
        "remocoes_ordenadas": [],
        "n_items_esperado": 1,
    }
    ok, motivo = F._provar_invariantes(texto, invariantes)
    assert ok is False
    assert "sobrevive" in motivo


def test_provar_invariantes_aceita_quando_tudo_bate():
    texto = "| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n"
    invariantes = {
        "n_linhas_esperado": 4,
        "linhas_preservadas": {0: "| ID | Status |", 1: "| :- | :- |",
                               3: ""},
        "remocoes_ordenadas": [],
        "n_items_esperado": 1,
    }
    ok, motivo = F._provar_invariantes(texto, invariantes)
    assert ok is True and motivo is None


def test_provar_invariantes_recusa_divergencia_so_trailing_space():
    """AUD-FUP-1: divergencia so de espaco em branco tem que falhar.

    Um mutante que troca `!=` por `.strip() != .strip()` mataria o teste de
    conteudo grosseiro e sobreviveria a suite -- este caso isola so o
    trailing space (mesmo texto logico, bytes diferentes).
    """
    texto = "| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n"
    linha_real = "| V-1 | ⏳ Pendente |"
    assert L.parse_table(texto)["lines"][2] == linha_real
    invariantes = {
        "n_linhas_esperado": 4,
        "linhas_preservadas": {2: linha_real + " "},  # so trailing space
        "remocoes_ordenadas": [],
        "n_items_esperado": 1,
    }
    ok, motivo = F._provar_invariantes(texto, invariantes)
    assert ok is False
    assert "sobrevive" in motivo
    # Prova do ponto cego: com strip a divergencia some -- a comparacao
    # byte-exata e o que a rede precisa preservar.
    assert (linha_real + " ").strip() == linha_real.strip()


def test_provar_invariantes_recusa_divergencia_so_cr_de_crlf():
    """AUD-FUP-1: terminador CR residual (split de CRLF em \\n) diverge.

    text.split('\\n') deixa '\\r' no fim da linha quando o arquivo era CRLF.
    Se o texto novo perdeu o CR, a linha 'preservada' nao sobrevive byte-a-byte.
    """
    # Resultado "novo" ja normalizado em LF (sem CR nas linhas).
    texto = "| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n"
    linha_com_cr = "| V-1 | ⏳ Pendente |\r"
    invariantes = {
        "n_linhas_esperado": 4,
        "linhas_preservadas": {2: linha_com_cr},
        "remocoes_ordenadas": [],
        "n_items_esperado": 1,
    }
    ok, motivo = F._provar_invariantes(texto, invariantes)
    assert ok is False
    assert "sobrevive" in motivo
    # .strip() tambem engole o CR -- mutante strip() passaria silenciosamente.
    assert linha_com_cr.strip() == "| V-1 | ⏳ Pendente |"


def test_provar_e_escrever_recusa_whitespace_sem_tocar_disco(tmp_path):
    """AUD-FUP-1: a falha da prova bloqueia o apply (nada escrito)."""
    todo = tmp_path / "TODO.md"
    texto = "| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n"
    todo.write_text(texto, encoding="utf-8")
    antes = todo.read_bytes()
    invariantes = {
        "n_linhas_esperado": 4,
        "linhas_preservadas": {2: "| V-1 | ⏳ Pendente | "},
        "remocoes_ordenadas": [],
        "n_items_esperado": 1,
    }
    ok, motivo = F._provar_e_escrever(str(todo), texto, invariantes)
    assert ok is False
    assert "sobrevive" in motivo
    assert todo.read_bytes() == antes


# ------------------------- prova de fixture real (skip se ausente) ----------

FIXTURE_A = os.environ.get("TAB_PENDENCIAS_FIXTURE_A")
FIXTURE_B = os.environ.get("TAB_PENDENCIAS_FIXTURE_B")


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_build_plan_roda_read_only_em_fixture_real(env_path, tmp_path):
    """AC-FIX (W10) roda --fix de verdade sobre uma CÓPIA do corpus; aqui só
    provamos que `build_plan` (SEMPRE read-only, nunca escreve) roda sem
    lançar exceção contra o arquivo real e sem tocar nele -- nunca contra o
    arquivo original de fato (só leitura, hash conferido antes/depois)."""
    if not env_path or not os.path.isfile(env_path):
        pytest.skip(f"fixture nao configurada ({env_path!r})")
    import hashlib
    with open(env_path, "rb") as fh:
        antes = hashlib.sha256(fh.read()).hexdigest()
    root = os.path.dirname(env_path)
    plan = F.build_plan(root, todo_path=env_path)
    assert isinstance(plan.items, list)
    with open(env_path, "rb") as fh:
        depois = hashlib.sha256(fh.read()).hexdigest()
    assert antes == depois, "build_plan NUNCA pode tocar o arquivo (so leitura)"
