"""tests/test_enc1_leitura_e_encoding.py -- ENC-1: unificacao da politica de
excecao/encoding entre todo_sync.py, todo_health.py e todo_freshness.py.

Antes desta fatia: `todo_sync.py`/`todo_health.py` NAO tinham nenhum
try/except em volta da leitura do TODO.md -- uma excecao (UnicodeDecodeError,
PermissionError etc.) propagava crua, imprimindo um traceback Python inteiro
(caminhos internos do sistema de arquivos inclusive) em stderr; o exit code 1
so acontecia por coincidencia (comportamento padrao do Python para excecao
nao tratada), nao por contrato D-6. `todo_freshness.py` engolia QUALQUER
excecao em silencio (ja coberto por ENC-1 em test_todo_freshness_e2e.py).

Depois desta fatia:
  - todo_sync.py / todo_health.py: mensagem CLARA (tipo + mensagem da
    excecao) em stderr, exit 1 (erro de execucao, D-6/CLI-1) -- nunca
    traceback cru por default.
  - Flag -v/--verbose em ambos: acrescenta o traceback completo, para quem
    precisa investigar a fundo.
  - BOM e CRLF exercitados via subprocess real end-to-end nos 3 scripts
    (nao so no parser em todo_lib.py, que e de outro agente nesta sessao).
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


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=_ENV,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _run(script, args, cwd):
    # WIN-CLI-1: sem `encoding="utf-8"` explicito, `text=True` decodifica a
    # saida capturada com a codepage padrao da plataforma -- cp1252 no
    # Windows. Os 3 scripts imprimem emoji (⏳/🔄/🔍/✅) em stdout/stderr;
    # bytes UTF-8 multi-byte nao sao validos cp1252 e a decodificacao falha
    # dentro da thread leitora do subprocess, que morre em silencio e deixa
    # `r.stdout`/`r.stderr` como None (nunca uma excecao capturavel aqui) --
    # sintoma medido no CI: `TypeError: argument of type 'NoneType' is not
    # iterable` num `"x" in r.stdout`. Round-trip byte-exato (ADR-0001) exige
    # encoding explicito nos dois lados, nao so no arquivo.
    return subprocess.run([sys.executable, script, *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8")


def _commit_todo_bytes(cwd, raw_bytes, msg="todo com bytes invalidos"):
    """Grava TODO.md com bytes ARBITRARIOS (nao decodificaveis como UTF-8
    de proposito nos testes de erro) e commita. Bytes crus para nao passar
    por normalizacao de newline do modo texto do Python na escrita da
    fixture -- o que importa aqui e o BYTE final no disco."""
    _git_init_isolado(cwd)
    with open(os.path.join(str(cwd), "TODO.md"), "wb") as fh:
        fh.write(raw_bytes)
    _git(cwd, "add", "TODO.md")
    _git(cwd, "commit", "-qm", msg)


_BYTES_INVALIDOS = b"| ID | Status |\n| :- | :- |\n| V-1 | \xff\xfe invalido |\n"


# ---------------------------------------------------------------------------
# todo_sync.py: leitura falha -> mensagem clara + exit 1, nunca traceback cru.
# ---------------------------------------------------------------------------

def test_sync_leitura_invalida_mensagem_clara_exit1_sem_traceback(tmp_path):
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    r = _run(SYNC, [], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "UnicodeDecodeError" in r.stderr
    assert "Traceback (most recent call last)" not in r.stderr


def test_sync_leitura_invalida_verbose_mostra_traceback(tmp_path):
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    r = _run(SYNC, ["--verbose"], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "UnicodeDecodeError" in r.stderr
    assert "Traceback (most recent call last)" in r.stderr


def test_sync_leitura_invalida_nao_aplica_nada(tmp_path):
    """Falha na leitura nunca deve deixar o sync tentar aplicar mudanca
    nenhuma -- to_flip vazio, applied False."""
    import todo_sync as S
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    rc, to_flip, applied = S.run(["--apply"], root=str(tmp_path))
    assert rc == 1 and to_flip == [] and not applied


# ---------------------------------------------------------------------------
# todo_health.py: leitura falha -> mensagem clara + exit 1, nunca traceback.
# ---------------------------------------------------------------------------

def test_health_leitura_invalida_mensagem_clara_exit1_sem_traceback(tmp_path):
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    r = _run(HEALTH, [], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "UnicodeDecodeError" in r.stderr
    assert "Traceback (most recent call last)" not in r.stderr


def test_health_leitura_invalida_verbose_mostra_traceback(tmp_path):
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    r = _run(HEALTH, ["--verbose"], cwd=tmp_path)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "UnicodeDecodeError" in r.stderr
    assert "Traceback (most recent call last)" in r.stderr


def test_health_leitura_invalida_run_devolve_sentinela_dedicado(tmp_path):
    """run() continua devolvendo None para 'sem dado' (estado valido: sem
    TODO.md, tabela vazia) -- leitura FALHA e um terceiro estado, distinto
    de None e de um dict de sucesso, para main() poder mapear em exit 1 sem
    reinterpretar o 'None' generico ja usado por outros ramos validos."""
    import todo_health as H
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    res = H.run(root=str(tmp_path))
    assert res is H.ERRO_LEITURA
    assert res is not None


# ---------------------------------------------------------------------------
# Ainda warn-only: todo_freshness com o mesmo arquivo invalido continua 0
# (regressao contra ENC-1 duplo-conserto -- ja coberto em
# test_todo_freshness_e2e.py, repetido aqui so como amarra de consistencia
# entre os 3 scripts para quem le este arquivo isolado).
# ---------------------------------------------------------------------------

def test_freshness_leitura_invalida_continua_exit0(tmp_path):
    _commit_todo_bytes(tmp_path, _BYTES_INVALIDOS)
    r = _run(FRESH, [], cwd=tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "UnicodeDecodeError" in r.stderr


# ---------------------------------------------------------------------------
# BOM + CRLF ponta-a-ponta pelos 3 scripts reais (subprocess), nao so o
# parser em todo_lib.py: fecha a lacuna "e teste os dois" da ADR-0001 (e).3.
# ---------------------------------------------------------------------------

_BOM = b"\xef\xbb\xbf"
_HEADER_CRLF = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\r\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\r\n"
).encode("utf-8")


def _row_crlf(iid, status):
    return (f"| {iid} | W1 | Grupo | Descrição | Média | — | Baixa | "
            f"{status} | — |\r\n").encode("utf-8")


def test_sync_apply_preserva_crlf_e_bom_no_resto_do_arquivo(tmp_path):
    """TODO.md com BOM na 1a linha e terminador CRLF em toda linha: --apply
    flipa SO a celula de Status da linha citada, e o resto do arquivo
    (inclusive o BOM e os \\r\\n) permanece byte-identico -- e o invariante
    de round-trip byte-exato (ADR-0001 b.1) exercitado pela interface real
    do todo_sync, nao so por uma chamada direta a set_status_cell."""
    raw = (_BOM + _HEADER_CRLF + _row_crlf("V-12", "⏳ Pendente")
           + _row_crlf("V-20", "⏳ Pendente"))
    _commit_todo_bytes(tmp_path, raw, msg="tabela com BOM+CRLF")
    # 1a execucao (sem --since) semeia a baseline em HEAD sem varrer o
    # historico (comportamento documentado em todo_sync.py) -- so DEPOIS
    # dela a entrega seguinte fica dentro da janela.
    _run(SYNC, ["--apply"], cwd=tmp_path)
    (tmp_path / "auth.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "auth.py")
    _git(tmp_path, "commit", "-qm", "feat: termina login V-12")

    r = _run(SYNC, ["--apply"], cwd=tmp_path)
    assert r.returncode == 2, (r.stdout, r.stderr)  # ha achado aplicado

    depois = (tmp_path / "TODO.md").read_bytes()
    assert depois.startswith(_BOM)                      # BOM intacto
    # todas as linhas de dado (que comecam com '|') continuam terminadas em
    # CRLF -- nenhuma virou LF puro so porque uma celula foi reescrita.
    linhas_crlf = [l for l in depois.split(b"\r\n")[:-1]]
    linhas_com_pipe = [l for l in linhas_crlf if l.lstrip(_BOM).startswith(b"|")]
    assert len(linhas_com_pipe) == 4  # header + separador + V-12 + V-20
    # a celula de status de V-12 avancou; V-20 continua intacta
    texto = depois.decode("utf-8-sig")
    assert "🔍 Pendente verificação" in texto
    assert "| V-20 |" in texto and "⏳ Pendente" in texto


def test_health_conta_certo_com_bom_e_crlf(tmp_path):
    raw = (_BOM + _HEADER_CRLF + _row_crlf("V-01", "🔍 Pendente verificação")
           + _row_crlf("V-02", "⏳ Pendente"))
    _commit_todo_bytes(tmp_path, raw, msg="tabela com BOM+CRLF")
    r = _run(HEALTH, [], cwd=tmp_path)
    assert r.returncode == 2, (r.stdout, r.stderr)  # V-01 preso em verificacao
    assert "2 itens" in r.stdout or "(2 itens)" in r.stdout


def test_freshness_funciona_com_bom_e_crlf(tmp_path):
    raw = (_BOM + _HEADER_CRLF + _row_crlf("V-12", "⏳ Pendente"))
    _commit_todo_bytes(tmp_path, raw, msg="tabela com BOM+CRLF")
    (tmp_path / "auth.py").write_bytes(b"x = 1\n")
    _git(tmp_path, "add", "auth.py")
    _git(tmp_path, "commit", "-qm", "feat: termina login V-12")

    r = _run(FRESH, [], cwd=tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "V-12" in r.stderr and "Status" in r.stderr
