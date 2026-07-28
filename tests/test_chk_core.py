"""Suite do CHK-CORE (TODO.md, item W7): CHK-01/02/03/04/08/11 --
integridade de tabela e vocabulario (`tools/checks/chk_core.py`).

Cada check tem (a) prova de silencio no corpus limpo (`clean.md`), (b) prova
de deteccao no corpus com o defeito plantado, e (c) prova de execucao real
contra as duas fixtures privadas (env vars, skip se ausentes).
"""
import contextlib
import io
import os

import pytest

import checks.chk_core as C
import todo_audit as A
import todo_lib as L

CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")

FIXTURE_A = os.environ.get("TAB_PENDENCIAS_FIXTURE_A")
FIXTURE_B = os.environ.get("TAB_PENDENCIAS_FIXTURE_B")


def _read(name):
    with open(os.path.join(CORPUS_DIR, name), encoding="utf-8", newline="") as fh:
        return fh.read()


def _ctx(text, root="."):
    table = L.parse_table(text)
    return A.Context(root=root, todo_path=None, text=text, table=table,
                      profile="core", config=None)


def _run_on_fixture(env_path, run_fn):
    if not env_path or not os.path.isfile(env_path):
        pytest.skip(f"fixture nao configurada ({env_path!r})")
    with open(env_path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    root = os.path.dirname(env_path)
    return run_fn(_ctx(text, root=root)), text


# --------------------------------- CHK-01 ----------------------------------

def test_chk01_calado_no_corpus_limpo():
    assert C._chk01_id_duplicado(_ctx(_read("clean.md"))) == []


def test_chk01_acusa_id_duplicado_como_julgamento():
    """defeito_id_duplicado.md: as 2 ocorrencias de OPS.1.1 divergem em 3
    celulas (Wave, Descricao, Status) -- ambiguo demais para a heuristica
    decidir sozinha, logo [julgamento], nao [auto-fixavel]."""
    achados = C._chk01_id_duplicado(_ctx(_read("defeito_id_duplicado.md")))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-01" and f.severity == "CRÍTICO"
    assert "OPS.1.1" in f.message and "2x" in f.message
    assert f.fixable is False
    assert "linha" in f.message.lower()


def test_chk01_marca_auto_fixavel_quando_so_uma_celula_diverge_por_placeholder():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-1 | W1 | Core | Something | High | - | Low | ⏳ Pendente | - |\n"
        "| Z-1 | W1 | Core | Something | High | - | Low | "
        "🔄 Em andamento | yes |\n"
    )
    achados = C._chk01_id_duplicado(_ctx(texto))
    assert len(achados) == 1
    assert achados[0].fixable is True
    assert achados[0].fix_ref == "remover_fragmento_duplicado"


def test_chk01_marca_auto_fixavel_quando_celula_e_prefixo_truncado():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-2 | W1 | Core | Provision the canary | High | - | Low | "
        "⏳ Pendente | - |\n"
        "| Z-2 | W1 | Core | Provision the canary cluster fully | High | "
        "- | Low | ⏳ Pendente | - |\n"
    )
    achados = C._chk01_id_duplicado(_ctx(texto))
    assert len(achados) == 1
    assert achados[0].fixable is True


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_chk01_roda_em_fixture_real(env_path):
    achados, _text = _run_on_fixture(env_path, C._chk01_id_duplicado)
    assert all(f.check_id == "CHK-01" for f in achados)


# --------------------------------- CHK-02 ----------------------------------

def test_chk02_calado_no_corpus_limpo():
    assert C._chk02_ncols_diverge(_ctx(_read("clean.md"))) == []


def test_chk02_calado_com_pipe_escapado_ok():
    assert C._chk02_ncols_diverge(_ctx(_read("defeito_pipe_escapado_ok.md"))) == []


def test_chk02_diagnostica_pipe_cru_nao_escapado_como_auto_fixavel():
    achados = C._chk02_ncols_diverge(_ctx(_read("defeito_pipe_cru_nao_escapado.md")))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-02" and f.severity == "CRÍTICO"
    assert "SUPOSICAO" in f.message.upper() or "SUPOSIÇÃO" in f.message
    assert "escapa" in f.message.lower() or "\\|" in f.message
    assert f.fixable is True
    assert f.fix_ref == "escapar_pipe_cru"


def test_chk02_diagnostica_fragmento_truncado_como_julgamento():
    achados = C._chk02_ncols_diverge(_ctx(_read("defeito_fragmento_truncado.md")))
    assert len(achados) == 1
    f = achados[0]
    assert f.fixable is False
    assert "truncad" in f.message.lower()


def test_chk02_diagnostica_celula_faltando_quando_linha_fecha_com_pipe():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-3 | W1 | Core | Missing one cell | High | - | Low | "
        "⏳ Pendente |\n"
    )
    achados = C._chk02_ncols_diverge(_ctx(texto))
    assert len(achados) == 1
    assert "faltando" in achados[0].message.lower()
    assert achados[0].fixable is False


def test_chk02_nao_confunde_tabela_alheia_bem_formada_com_defeito():
    """Cabecalho+separador+dados de uma tabela de OUTRO schema (2 colunas)
    logo apos a canonica: todas essas linhas entram em 'malformed' (D-12,
    o nucleo nunca reseta ncols), mas nao sao defeito nenhum -- CHK-02 tem
    que ficar CALADO sobre elas (cluster de 2+ com mesmo got_ncols e linhas
    proximas)."""
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-10 | W1 | Core | A | High | - | Low | ⏳ Pendente | - |\n"
        "\n"
        "### Outra secao, tabela de motivo (schema diferente)\n"
        "\n"
        "| ID | Motivo |\n"
        "| :- | :- |\n"
        "| `X-1` | Ainda nao comecou |\n"
        "| `X-2` | Bloqueado por outra coisa |\n"
        "| `X-3` | Aguardando decisao |\n"
    )
    achados = C._chk02_ncols_diverge(_ctx(texto))
    assert achados == []


def test_chk02_detecta_defeito_isolado_mesmo_perto_de_tabela_alheia():
    """O mesmo cenario acima, mas com uma linha GENUINAMENTE truncada da
    canonica (ncols=4, sem par proximo com o MESMO ncols) intercalada --
    essa continua sendo achado real, mesmo com a tabela alheia de 2
    colunas por perto (ncols diferente, clusters nao se confundem)."""
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-11 | W1 | Core | A | High | - | Low | ⏳ Pendente | - |\n"
        "| Z-12 | W1 | Core | Truncado no meio | High\n"
        "\n"
        "| ID | Motivo |\n"
        "| :- | :- |\n"
        "| `X-1` | Ainda nao comecou |\n"
        "| `X-2` | Bloqueado por outra coisa |\n"
    )
    achados = C._chk02_ncols_diverge(_ctx(texto))
    assert len(achados) == 1
    assert "truncad" in achados[0].message.lower()


def test_chk02_roda_em_fixture_real_so_acusa_os_2_defeitos_publicos_conhecidos():
    """Contra a fixture B (consumidor B): CHK-02 tem 41 entradas cruas em
    'malformed', mas 39 pertencem a 3 tabelas alheias legitimas (WSJF de 8
    colunas, 2 checklists de assets de 5/4 colunas, 1 tabela de motivo de 2
    colunas) -- so os 2 defeitos PUBLICOS ja documentados no proprio
    TODO.md deste repo (AC-REAL) sao achado real: TODO-PARSER-BUG (pipe
    cru) e o fragmento truncado adjacente a ATOM-3."""
    if not FIXTURE_B or not os.path.isfile(FIXTURE_B):
        pytest.skip(f"fixture nao configurada ({FIXTURE_B!r})")
    with open(FIXTURE_B, encoding="utf-8", newline="") as fh:
        text = fh.read()
    table = L.parse_table(text)
    assert len(table["malformed"]) > 2, "premissa do teste: fixture tem tabelas alheias"
    ctx = _ctx(text, root=os.path.dirname(FIXTURE_B))
    achados = C._chk02_ncols_diverge(ctx)
    assert len(achados) == 2
    raws_dos_achados = {a.line_no for a in achados}
    raws_genuinos = {m["raw"] for m in table["malformed"] if m["line_no"] in raws_dos_achados}
    assert any("TODO-PARSER-BUG" in r for r in raws_genuinos)
    assert any("ATOM-3" in r for r in raws_genuinos)


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_chk02_roda_em_fixture_real(env_path):
    achados, _text = _run_on_fixture(env_path, C._chk02_ncols_diverge)
    assert all(f.check_id == "CHK-02" for f in achados)


# --------------------------------- CHK-03 ----------------------------------

def test_chk03_calado_no_corpus_limpo():
    assert C._chk03_tabela_fragmentada(_ctx(_read("clean.md"))) == []


def test_chk03_acusa_tabela_fragmentada():
    achados = C._chk03_tabela_fragmentada(_ctx(_read("defeito_tabela_fragmentada.md")))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-03" and f.severity == "CRÍTICO"
    assert "fragmentada" in f.message.lower()
    assert "2" in f.message  # 2 cabecalhos


def test_chk03_informativo_quando_so_atravessa_headings_sem_fragmentar():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-4 | W1 | Core | A | High | - | Low | ⏳ Pendente | - |\n"
        "## Subsecao organizacional\n"
        "| Z-5 | W1 | Core | B | High | - | Low | ⏳ Pendente | - |\n"
    )
    achados = C._chk03_tabela_fragmentada(_ctx(texto))
    assert len(achados) == 1
    f = achados[0]
    assert f.severity == "COSMÉTICO"
    assert "legitim" in f.message.lower() or "informativo" in f.message.lower()


def test_chk03_sprawl_nao_e_fragmentacao_de_cabecalho():
    """defeito_sprawl.md tem uma tabela ALHEIA (sem colunas ID/Status) depois
    da canonica -- nao e um 2o cabecalho ID+Status, logo CHK-03 fica calado
    quanto a 'fragmentada' (comportamento D-12, correto)."""
    achados = C._chk03_tabela_fragmentada(_ctx(_read("defeito_sprawl.md")))
    assert not any("fragmentada" in f.message.lower() for f in achados)


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_chk03_roda_em_fixture_real(env_path):
    achados, _text = _run_on_fixture(env_path, C._chk03_tabela_fragmentada)
    assert all(f.check_id == "CHK-03" for f in achados)


# --------------------------------- CHK-04 ----------------------------------

def test_chk04_calado_no_corpus_limpo():
    assert C._chk04_ncols_divergente_entre_tabelas(_ctx(_read("clean.md"))) == []


def test_chk04_calado_quando_tabelas_fragmentadas_tem_mesmo_ncols():
    """defeito_tabela_fragmentada.md: as 2 tabelas tem 9 colunas cada --
    CHK-04 so acusa DIVERGENCIA de ncols, nao a fragmentacao em si (isso e
    CHK-03); aqui deve ficar calado."""
    texto = _read("defeito_tabela_fragmentada.md")
    assert C._chk04_ncols_divergente_entre_tabelas(_ctx(texto)) == []


def test_chk04_acusa_ncols_divergente_entre_2_tabelas():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-6 | W1 | Core | A | High | - | Low | ⏳ Pendente | - |\n"
        "\n"
        "| ID | Group | Description | Priority | Blocked By | Effort | "
        "Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-7 | Core | B | High | - | Low | ⏳ Pendente | - |\n"
    )
    achados = C._chk04_ncols_divergente_entre_tabelas(_ctx(texto))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-04" and f.severity == "CRÍTICO"
    assert "9" in f.message and "8" in f.message


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_chk04_roda_em_fixture_real(env_path):
    achados, _text = _run_on_fixture(env_path, C._chk04_ncols_divergente_entre_tabelas)
    assert all(f.check_id == "CHK-04" for f in achados)


# --------------------------------- CHK-08 ----------------------------------

def test_chk08_calado_no_corpus_limpo():
    """clean.md cobre os 7 status canonicos, todos via emoji -- zero achado."""
    assert C._chk08_status_fora_do_vocabulario(_ctx(_read("clean.md"))) == []


def test_chk08_calado_em_tabela_legada_8_colunas_com_emoji():
    texto = _read("defeito_tabela_legada_8_colunas.md")
    assert C._chk08_status_fora_do_vocabulario(_ctx(texto)) == []


def test_chk08_aviso_brando_para_legado_sem_emoji_reconhecido_por_palavra():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-8 | W1 | Core | A | High | - | Low | Pendente | - |\n"
    )
    achados = C._chk08_status_fora_do_vocabulario(_ctx(texto))
    assert len(achados) == 1
    assert achados[0].severity == "COSMÉTICO"


def test_chk08_mais_grave_para_emoji_desconhecido_ou_texto_solto():
    texto = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        "| Z-9 | W1 | Core | A | High | - | Low | 🔴 Bloqueado | - |\n"
    )
    achados = C._chk08_status_fora_do_vocabulario(_ctx(texto))
    assert len(achados) == 1
    assert achados[0].severity == "IMPORTANTE"


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_chk08_roda_em_fixture_real(env_path):
    achados, _text = _run_on_fixture(env_path, C._chk08_status_fora_do_vocabulario)
    assert all(f.check_id == "CHK-08" for f in achados)


# --------------------------------- CHK-11 ----------------------------------

def test_chk11_calado_no_corpus_limpo(tmp_path):
    texto = _read("clean.md")
    todo = tmp_path / "TODO.md"
    todo.write_text(texto, encoding="utf-8")
    achados = C._chk11_reconciliacao_contagem(_ctx(texto, root=str(tmp_path)))
    assert achados == []


def test_chk11_e_silencioso_em_stdout(tmp_path, capsys):
    """todo_health.run() imprime -- CHK-11 tem que suprimir isso (--audit
    nunca deve poluir stdout com o relatorio de outro comando)."""
    texto = _read("clean.md")
    todo = tmp_path / "TODO.md"
    todo.write_text(texto, encoding="utf-8")
    C._chk11_reconciliacao_contagem(_ctx(texto, root=str(tmp_path)))
    captured = capsys.readouterr()
    assert captured.out == ""


def test_chk11_acusa_divergencia_entre_health_e_contagem_independente(tmp_path, monkeypatch):
    texto = _read("clean.md")
    todo = tmp_path / "TODO.md"
    todo.write_text(texto, encoding="utf-8")

    def _health_mentiroso(root=None, verbose=False):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print("Saude da TODO.md (14 itens):")
        return {"itens": 14, "concluidos": 1, "pendentes": 1,
                "aguardando_verificacao": 1, "inbox": 0}

    import checks.chk_core as chk_core_mod
    monkeypatch.setattr(chk_core_mod.H, "run", _health_mentiroso)
    achados = C._chk11_reconciliacao_contagem(_ctx(texto, root=str(tmp_path)))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-11" and f.severity == "CRÍTICO"
    assert "14" in f.message and "7" in f.message


def test_contagem_independente_nao_reusa_parse_table_e_bate_no_corpus_limpo():
    assert C._contagem_independente(_read("clean.md")) == 7


@pytest.mark.parametrize("env_path", [FIXTURE_A, FIXTURE_B])
def test_chk11_roda_em_fixture_real_e_reconcilia_sem_falso_positivo(env_path):
    """As 2 fixtures reais sao bem-formadas -- reconciliacao tem que dar
    OK (zero achado), inclusive com pipe escapado em texto livre (fixture
    A) e tabelas alheias embutidas (fixture B): o contador independente
    precisa ser esperto o bastante para NAO se confundir com nenhuma das
    duas, senao CHK-11 vira ruido permanente em vez de sinal real."""
    achados, _text = _run_on_fixture(env_path, C._chk11_reconciliacao_contagem)
    assert achados == []


# ------------------------- registro no motor (fronteira) -------------------
#
# CHK-CORE nao define sua propria lista `CHECKS` (import circular com
# todo_audit.py, ver docstring do modulo) -- o registro de verdade e
# `todo_audit.CHECKS`, mesmo padrao ja provado por CHK-GRAPH/CHK-09/CHK-10
# (`tests/test_chk_graph.py`).

_MEUS_IDS = {"CHK-01", "CHK-02", "CHK-03", "CHK-04", "CHK-08", "CHK-11"}


def test_todos_os_meus_checks_estao_registrados_e_sao_profile_core():
    ids = {c.id: c for c in A.CHECKS}
    for cid in _MEUS_IDS:
        assert cid in ids, f"{cid} nao esta registrado em todo_audit.CHECKS"
        assert ids[cid].profile == "core"


def test_nenhum_check_core_vem_de_tools_casa():
    assert A.core_boundary_violations(A.CHECKS) == []
