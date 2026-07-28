"""tests/test_todo_health.py -- GAP-1: suite do zero para tools/todo_health.py.

Ate esta fatia, `todo_health.py` era o UNICO modulo do toolkit sem nenhum
teste proprio (so os exit codes basicos apareciam de raspao em
test_cli_contract.py) -- e ja falhou em silencio em producao: reportou
**14 itens** num arquivo real com **215** sem nenhum aviso (motivo de
CHK-11, ainda nao implementado, no TODO.md). Este arquivo cobre:

  - contagem por categoria de status, reconciliada com uma contagem
    INDEPENDENTE feita aqui (nunca chamando run() de novo, nem reusando
    _cells/_split_row de todo_lib para gerar o esperado -- seria tautologia);
  - a lista de itens presos em 🔍 (stdout), exata;
  - contagem de INBOX;
  - a metrica `_adesao` (le $GIT_DIR/todo-freshness.log);
  - arquivo vazio, tabela sem itens, tabela legada de 8 colunas;
  - os exit codes do contrato (0/1/2) via subprocess -- a interface real
    que o CI usa;
  - um teste dedicado a CLASSE do bug "14 de 215" (arquivo grande onde a
    contagem poderia divergir silenciosamente).

Nao reusa os helpers `_repo`/`_git` de test_cli_contract.py de proposito:
cada arquivo de teste e auto-contido (nenhuma dependencia entre suites).
"""
import os
import re
import subprocess
import sys

import pytest

from conftest import git_init_isolado as _git_init_isolado
import todo_health as H
import todo_lib as L


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
HEALTH = os.path.join(TOOLS_DIR, "todo_health.py")

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

_HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=_ENV, capture_output=True,
                   check=True)


# _git_init_isolado (protecao HOOKISO-1 contra o core.hooksPath GLOBAL desta
# maquina) mora em conftest.py e e IMPORTADA acima -- nao duplicar aqui.


def _row(iid, status):
    return (f"| {iid} | W1 | Grupo | Descrição | Média | — | Baixa | "
            f"{status} | — |\n")


def _repo(tmp_path, todo_text):
    """Repo git local com o TODO.md dado ja commitado. Devolve o path."""
    _git_init_isolado(tmp_path)
    (tmp_path / "TODO.md").write_text(todo_text, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "tabela")
    return tmp_path


def _run_cli(cwd, *args):
    return subprocess.run([sys.executable, HEALTH, *args], cwd=cwd,
                          capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Contagem por categoria: reconciliada com contagem INDEPENDENTE feita aqui
# (bookkeeping manual da propria construcao da fixture, nao chamando o
# parser nem repetindo a chamada de run() para produzir o esperado).
# ---------------------------------------------------------------------------

def test_contagem_por_categoria_bate_com_contagem_independente(tmp_path, capsys):
    # Construcao deliberada: cada bucket tem uma contagem DIFERENTE, para que
    # um bug que troque duas contagens de lugar (ex.: pendentes <-> presos)
    # nao passe por coincidencia de numeros iguais.
    linhas = []
    esperado_done = 0
    esperado_pend = 0          # ⏳ + 🔄 + 🎨 (is_pending)
    esperado_verif = 0         # 🔍
    esperado_outros = 0        # 🟡 Parcial / 💡 Decisão tomada (nem pend nem done nem verif)
    plano = (
        ["✅ Concluído"] * 3
        + ["⏳ Pendente"] * 5
        + ["🔄 Em andamento"] * 2
        + ["🎨 Pendente design"] * 1
        + ["🔍 Pendente verificação"] * 4
        + ["🟡 Parcial"] * 2
        + ["💡 Decisão tomada"] * 1
    )
    for i, status in enumerate(plano):
        iid = f"GAP-{i:03d}"
        linhas.append(_row(iid, status))
        if status.startswith("✅"):
            esperado_done += 1
        elif status.startswith(("⏳", "🔄", "🎨")):
            esperado_pend += 1
        elif status.startswith("🔍"):
            esperado_verif += 1
        else:
            esperado_outros += 1
    texto = _HEADER_9 + "".join(linhas)
    esperado_total = len(plano)
    assert esperado_done + esperado_pend + esperado_verif + esperado_outros == esperado_total

    root = _repo(tmp_path, texto)
    res = H.run(root=str(root))

    assert res["itens"] == esperado_total
    assert res["concluidos"] == esperado_done
    assert res["pendentes"] == esperado_pend
    assert res["aguardando_verificacao"] == esperado_verif


def test_lista_de_presos_em_verificacao_e_exata(tmp_path, capsys):
    """A lista impressa de IDs presos em 🔍 contem EXATAMENTE os itens
    certos -- nem a mais (item pendente/concluido vazando na lista) nem a
    menos (item preso que nao aparece)."""
    plano = [
        ("V-01", "✅ Concluído"),
        ("V-02", "🔍 Pendente verificação"),
        ("V-03", "⏳ Pendente"),
        ("V-04", "🔍 Pendente verificação"),
        ("V-05", "🔄 Em andamento"),
    ]
    texto = _HEADER_9 + "".join(_row(i, s) for i, s in plano)
    root = _repo(tmp_path, texto)
    capsys.readouterr()
    res = H.run(root=str(root))
    out = capsys.readouterr().out

    esperados = {"V-02", "V-04"}
    impressos = set(re.findall(r"presos em 🔍 -> (\S+)", out))
    assert impressos == esperados
    assert res["aguardando_verificacao"] == len(esperados)


def test_lista_de_presos_trunca_em_10_e_avisa_o_resto(tmp_path):
    """run() imprime no maximo 10 IDs presos e depois um resumo '(+N)' -- 12
    itens presos deve mostrar 10 linhas 'presos em' + o resumo com +2."""
    linhas = [_row(f"V-{i:02d}", "🔍 Pendente verificação") for i in range(12)]
    texto = _HEADER_9 + "".join(linhas)
    root = _repo(tmp_path, texto)
    r = subprocess.run([sys.executable, HEALTH], cwd=root,
                       capture_output=True, text=True)
    n_presos = r.stdout.count("presos em 🔍 ->")
    assert n_presos == 10, r.stdout
    assert "(+2)" in r.stdout, r.stdout
    assert r.returncode == 2


# ---------------------------------------------------------------------------
# INBOX
# ---------------------------------------------------------------------------

def test_contagem_de_inbox(tmp_path):
    texto = (
        _HEADER_9 + _row("V-01", "⏳ Pendente")
        + "\n## INBOX (descobertas não priorizadas)\n"
        "- achado 1\n- achado 2\n- achado 3\n"
        "## Outra seção\n- não conta aqui\n"
    )
    root = _repo(tmp_path, texto)
    res = H.run(root=str(root))
    assert res["inbox"] == 3


def test_inbox_vazia_conta_zero(tmp_path):
    texto = _HEADER_9 + _row("V-01", "⏳ Pendente")
    root = _repo(tmp_path, texto)
    res = H.run(root=str(root))
    assert res["inbox"] == 0


# ---------------------------------------------------------------------------
# _adesao -- metrica de citar ID, lida de $GIT_DIR/todo-freshness.log
# ---------------------------------------------------------------------------

def test_adesao_sem_log_devolve_none(tmp_path):
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "⏳ Pendente"))
    assert H._adesao(str(root)) is None


def test_adesao_sem_linha_code1_devolve_none(tmp_path):
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "⏳ Pendente"))
    gd = L.git_dir(str(root))
    with open(os.path.join(gd, "todo-freshness.log"), "w", encoding="utf-8") as fh:
        fh.write("2026-07-28T10:00:00Z code=0 cited=0 warns=0\n")
    assert H._adesao(str(root)) is None


def test_adesao_calcula_percentual_independente(tmp_path):
    """3 commits de codigo (code=1): 2 citaram ID, 1 nao -- 66% (2/3),
    calculado aqui a mao, sem chamar _adesao para produzir o esperado."""
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "⏳ Pendente"))
    gd = L.git_dir(str(root))
    linhas = [
        "2026-07-28T10:00:00Z code=1 cited=1 warns=0\n",
        "2026-07-28T10:05:00Z code=1 cited=0 warns=1\n",
        "2026-07-28T10:10:00Z code=1 cited=2 warns=0\n",
        "2026-07-28T10:15:00Z code=0 cited=0 warns=0\n",  # ignorado: nao e code=1
    ]
    with open(os.path.join(gd, "todo-freshness.log"), "w", encoding="utf-8") as fh:
        fh.writelines(linhas)
    total_code1 = sum(1 for l in linhas if "code=1" in l)
    citaram = sum(1 for l in linhas if "code=1" in l and "cited=0" not in l)
    pct_esperado = round(100 * citaram / total_code1)
    assert (total_code1, citaram, pct_esperado) == (3, 2, 67)

    resultado = H._adesao(str(root))
    assert resultado == f"{citaram}/{total_code1} commits de codigo citaram ID ({pct_esperado}%)"


def test_run_reporta_adesao_quando_ha_log(tmp_path, capsys):
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "⏳ Pendente"))
    gd = L.git_dir(str(root))
    with open(os.path.join(gd, "todo-freshness.log"), "w", encoding="utf-8") as fh:
        fh.write("2026-07-28T10:00:00Z code=1 cited=1 warns=0\n")
    capsys.readouterr()
    H.run(root=str(root))
    out = capsys.readouterr().out
    assert "1/1 commits de codigo citaram ID (100%)" in out


def test_run_reporta_ausencia_de_dados_de_adesao_sem_log(tmp_path, capsys):
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "⏳ Pendente"))
    capsys.readouterr()
    H.run(root=str(root))
    out = capsys.readouterr().out
    assert "sem dados ainda no todo-freshness.log" in out


# ---------------------------------------------------------------------------
# Bordas: arquivo vazio, tabela sem itens, tabela legada de 8 colunas
# ---------------------------------------------------------------------------

def test_run_todo_vazio_devolve_none(tmp_path, capsys):
    root = _repo(tmp_path, "")
    capsys.readouterr()
    res = H.run(root=str(root))
    out = capsys.readouterr().out
    assert res is None
    assert "Sem tabela no TODO.md." in out


def test_run_tabela_sem_itens_devolve_zeros(tmp_path):
    """Cabecalho + separador, mas nenhuma linha de dado: tabela existe, 0
    itens -- estado valido, nao erro."""
    texto = _HEADER_9
    root = _repo(tmp_path, texto)
    res = H.run(root=str(root))
    assert res == {"itens": 0, "concluidos": 0, "pendentes": 0,
                    "aguardando_verificacao": 0, "inbox": 0}


def test_run_tabela_legada_8_colunas(tmp_path):
    texto = (
        "| ID | Grupo | Descrição | Prioridade | Pré-requisito | Dificuldade "
        "| Status | Estado Auditado |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| ORG-1 | Infra | Setup | Alta | — | Média | ⏳ Pendente | — |\n"
        "| ORG-2 | Infra | CI | Alta | ORG-1 | Média | 🔍 Pendente verificação | — |\n"
    )
    root = _repo(tmp_path, texto)
    res = H.run(root=str(root))
    assert res["itens"] == 2
    assert res["pendentes"] == 1
    assert res["aguardando_verificacao"] == 1


def test_run_sem_todo_md_devolve_none(tmp_path, capsys):
    _git_init_isolado(tmp_path)
    (tmp_path / "readme.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "readme.txt")
    _git(tmp_path, "commit", "-qm", "init")
    capsys.readouterr()
    res = H.run(root=str(tmp_path))
    out = capsys.readouterr().out
    assert res is None
    assert "Sem TODO.md na raiz." in out


def test_run_root_sem_todo_md_devolve_none(tmp_path, capsys):
    """run(root=...) so usa 'root' para localizar find_todo/git_dir -- um
    dir qualquer sem TODO.md tem o mesmo efeito de "sem TODO.md na raiz".
    O caminho "nao e repo git" de verdade (via L.repo_root(), subprocess
    git real) e exercitado pela CLI nos testes de exit code abaixo."""
    capsys.readouterr()
    res = H.run(root=str(tmp_path))
    assert res is None


# ---------------------------------------------------------------------------
# Exit codes do contrato (D-6/CLI-1), via subprocess -- interface real do CI.
# ---------------------------------------------------------------------------

def test_cli_exit1_sem_repo_git():
    """Sem `root=` explicito, main() usa L.repo_root() (subprocess git real):
    fora de um repositorio, e erro de execucao -> exit 1. A mensagem "Nao e
    um repositorio git." vem de run() e vai para STDOUT (nao stderr) -- so
    o exit code e o contrato aqui."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run_cli(d)
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert "Nao e um repositorio git." in r.stdout


def test_cli_exit0_sem_item_preso(tmp_path):
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "✅ Concluído"))
    r = _run_cli(root)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_cli_exit2_com_item_preso(tmp_path):
    root = _repo(tmp_path, _HEADER_9 + _row("V-01", "🔍 Pendente verificação"))
    r = _run_cli(root)
    assert r.returncode == 2, (r.stdout, r.stderr)


def test_cli_exit0_repo_git_sem_todo_md(tmp_path):
    _git_init_isolado(tmp_path)
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "x.txt")
    _git(tmp_path, "commit", "-qm", "init")
    r = _run_cli(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_cli_exit0_arquivo_vazio(tmp_path):
    root = _repo(tmp_path, "")
    r = _run_cli(root)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_cli_exit0_tabela_sem_itens(tmp_path):
    root = _repo(tmp_path, _HEADER_9)
    r = _run_cli(root)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_cli_help_exit0():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run_cli(d, "--help")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert "--help" in r.stdout or "-h" in r.stdout


def test_cli_flag_desconhecida_erro():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _run_cli(d, "--nao-existe")
        assert r.returncode == 1, (r.stdout, r.stderr)
        assert r.stderr.strip() != ""


# ---------------------------------------------------------------------------
# Classe do bug "14 de 215": arquivo GRANDE onde o health poderia subcontar.
#
# Contagem INDEPENDENTE escrita do zero aqui (mesmo espirito de
# test_contract_real_corpus.py: nao reusa _cells/_split_row de todo_lib nem
# chama run() duas vezes para produzir o esperado) -- e a rede de seguranca
# que teria acusado o incidente real (14 reportados onde 215 eram reais)
# antes dele chegar em producao.
# ---------------------------------------------------------------------------

_SEP_INDEP = re.compile(r"(?<!\\)\|")


def _contagem_independente_de_linhas_de_tabela(texto):
    """Reconta linhas de item da tabela direto do texto cru, sem tocar
    L.parse_table nem qualquer helper de todo_lib."""
    total = 0
    ncols = id_idx = None
    for linha in texto.split("\n"):
        s = linha.strip()
        if not s.startswith("|"):
            continue
        partes = _SEP_INDEP.split(s)
        if partes and partes[0].strip() == "":
            partes = partes[1:]
        if partes and partes[-1].strip() == "":
            partes = partes[:-1]
        celulas = [c.strip() for c in partes]
        baixo = [c.lower() for c in celulas]
        eh_cabecalho = "id" in baixo and any("status" in c for c in baixo)
        eh_separador = bool(celulas) and set("".join(celulas)) <= set("-: ")
        if ncols is None:
            if eh_cabecalho:
                ncols = len(celulas)
                id_idx = baixo.index("id")
            continue
        if eh_separador:
            continue
        if eh_cabecalho:
            break
        if len(celulas) != ncols:
            continue
        iid = celulas[id_idx]
        if not iid or iid in ("-", "—"):
            continue
        total += 1
    return total


def test_classe_bug_14_de_215_arquivo_grande_nao_subconta(tmp_path):
    """215 itens reais (tamanho do incidente que originou CHK-11): a
    contagem que o health reporta tem que bater com a recontagem
    independente. Se divergir, a mensagem diz QUANTO -- nao so 'falhou'."""
    n = 215
    ciclo = ["✅ Concluído", "⏳ Pendente", "🔄 Em andamento",
             "🔍 Pendente verificação", "🟡 Parcial", "💡 Decisão tomada",
             "🎨 Pendente design"]
    linhas = []
    for i in range(n):
        status = ciclo[i % len(ciclo)]
        linhas.append(_row(f"BIG-{i:04d}", status))
    texto = _HEADER_9 + "".join(linhas)

    independente = _contagem_independente_de_linhas_de_tabela(texto)
    assert independente == n  # sanidade da propria fixture antes de tudo

    root = _repo(tmp_path, texto)
    res = H.run(root=str(root))
    assert res["itens"] == independente, (
        f"health subcontou/sobrecontou: reportou {res['itens']} de "
        f"{independente} itens reais (diferenca={independente - res['itens']})"
    )


def test_classe_bug_14_de_215_via_cli_exit_code_consistente(tmp_path):
    """O mesmo arquivo grande, mas pela interface real (subprocess): com 31
    itens em 🔍 (215 // 7, um por ciclo) o exit code tem que ser 2, nunca 0
    por causa de uma contagem truncada que escondesse os itens presos."""
    n = 215
    ciclo = ["✅ Concluído", "⏳ Pendente", "🔄 Em andamento",
             "🔍 Pendente verificação", "🟡 Parcial", "💡 Decisão tomada",
             "🎨 Pendente design"]
    esperado_presos = sum(1 for i in range(n) if ciclo[i % len(ciclo)].startswith("🔍"))
    assert esperado_presos > 0
    linhas = [_row(f"BIG-{i:04d}", ciclo[i % len(ciclo)]) for i in range(n)]
    texto = _HEADER_9 + "".join(linhas)
    root = _repo(tmp_path, texto)
    r = _run_cli(root)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert f"({n} itens)" in r.stdout, r.stdout
