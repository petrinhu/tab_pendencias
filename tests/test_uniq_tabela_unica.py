"""UNIQ-1 -- tabela unica DE TRABALHO (contrato SS5).

Cobre `todo_lib.work_tables`/`table_blocks` (o helper que responde "quantas
tabelas de trabalho ha") e o CHK-19 (`--audit` acusa 2+). Nenhuma fixture real
de consumidor: todo corpus deste arquivo e GERADO aqui.
"""
import pytest

import checks.chk_core as C
import todo_audit as A
import todo_lib as L

CAB = "| ID | Onda | Grupo | Status |"
SEP = "| :--- | :--- | :--- | :--- |"
LINHAS = ["| A-1 | W1 | Base | ⏳ Pendente |",
          "| A-2 | W1 | Base | ✅ Concluído |"]
TABELA = [CAB, SEP] + LINHAS
PREAMBULO = ["# TODO -- projeto de exemplo", "", "> Prosa de cabecalho.", ""]

# Tabela de REFERENCIA legitima: sem coluna Status.
REFERENCIA = ["| ID | Significado |",
              "| :--- | :--- |",
              "| A-1 | a primeira |",
              "| A-2 | a segunda |"]

# Legenda do vocabulario: TEM a palavra Status no cabecalho, mas nao tem coluna
# de identificador -- padrao real de cabecalho de TODO.md, nao pode virar
# achado (seria CRITICO falso).
LEGENDA = ["| Status | Significado |",
           "| :--- | :--- |",
           "| ⏳ Pendente | nao iniciado |",
           "| ✅ Concluído | finalizada |"]


def _arquivo(*blocos):
    linhas = list(PREAMBULO)
    for i, b in enumerate(blocos):
        if i:
            linhas.append("")
        linhas.extend(b)
    return "\n".join(linhas) + "\n"


def _ctx(text):
    return A.Context(root=".", todo_path=None, text=text,
                     table=L.parse_table(text), profile="core", config=None)


# ------------------------- work_tables (o helper) --------------------------

def test_uma_tabela_de_trabalho_e_contada_uma_vez():
    wt = L.work_tables(_arquivo(TABELA))
    assert len(wt) == 1
    assert wt[0]["n_rows"] == 2 and wt[0]["ncols"] == 4


def test_duas_tabelas_de_trabalho_sao_contadas_como_duas():
    wt = L.work_tables(_arquivo(TABELA, TABELA))
    assert len(wt) == 2
    assert wt[0]["line_no"] < wt[1]["line_no"]


def test_tabela_de_referencia_sem_status_nao_conta():
    assert len(L.work_tables(_arquivo(REFERENCIA, TABELA))) == 1


def test_legenda_de_status_sem_coluna_de_id_nao_conta():
    """`| Status | Significado |` e legenda de cabecalho, nao tabela de
    trabalho -- e o nucleo nem consegue eleger (nao tem coluna ID)."""
    assert len(L.work_tables(_arquivo(LEGENDA, TABELA))) == 1


def test_coluna_de_id_com_nome_composto_conta_como_trabalho():
    """"ID (AUD-*)" e coluna de identificador de verdade: uma 2a tabela assim
    e material de trabalho invisivel -- o caso que CHK-03 (celula exata "id")
    nao pega."""
    outra = ["| # | ID (AUD-*) | Severidade | Status |",
             "| :--- | :--- | :--- | :--- |",
             "| 1 | AUD-01 | Alta | ⏳ Pendente |"]
    assert len(L.work_tables(_arquivo(TABELA, outra))) == 2


def test_sub_status_de_tabela_alheia_nao_marca_como_trabalho():
    """HDR-1: "Sub-status" nao e coluna Status (mesma regra de fronteira de
    palavra do nucleo)."""
    alheia = ["| ID | Sub-status |", "| :--- | :--- |", "| X | y |"]
    assert L.work_tables(_arquivo(alheia)) == []


def test_metade_de_baixo_de_tabela_partida_nao_vira_segunda_tabela():
    """Linha em branco no meio parte o BLOCO, mas o cabecalho e um so: continua
    UMA tabela de trabalho (quem acusa a quebra e o check de linha em branco)."""
    partida = [CAB, SEP, LINHAS[0], "", LINHAS[1]]
    assert len(L.work_tables(_arquivo(partida))) == 1


def test_secoes_sob_subtitulo_nao_viram_tabelas_novas():
    """D-12: a MESMA tabela organizada sob subtitulos (sem repetir cabecalho)
    e legitima e continua contando como uma."""
    text = "\n".join(PREAMBULO + [CAB, SEP, LINHAS[0], "", "### Onda 2", "",
                                  LINHAS[1]]) + "\n"
    assert len(L.work_tables(text)) == 1


def test_arquivo_sem_tabela_nenhuma_devolve_lista_vazia():
    assert L.work_tables("# so prosa\n\nnada aqui.\n") == []


def test_tabela_de_trabalho_vazia_ainda_conta():
    """So cabecalho + separador: e tabela de trabalho, com 0 linha de dado."""
    wt = L.work_tables(_arquivo([CAB, SEP], TABELA))
    assert len(wt) == 2 and wt[0]["n_rows"] == 0


def test_work_tables_tolera_crlf_e_bom():
    text = L.BOM + _arquivo(TABELA, TABELA).replace("\n", "\r\n")
    assert len(L.work_tables(text)) == 2


# --------------------------------- CHK-19 ----------------------------------

def test_chk19_calado_com_uma_tabela_de_trabalho():
    assert C._chk19_tabela_unica(_ctx(_arquivo(TABELA))) == []


def test_chk19_calado_com_tabela_de_referencia_sem_status():
    assert C._chk19_tabela_unica(_ctx(_arquivo(REFERENCIA, TABELA))) == []
    assert C._chk19_tabela_unica(_ctx(_arquivo(LEGENDA, TABELA))) == []


def test_chk19_acusa_duas_tabelas_de_trabalho():
    achados = C._chk19_tabela_unica(_ctx(_arquivo(TABELA, TABELA)))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-19" and f.severity == "CRÍTICO"
    assert f.fixable is False
    assert "2 tabelas" in f.message
    # aponta para o cabecalho da SEGUNDA (onde o dado comeca a sumir)
    assert f.line_no == L.work_tables(_arquivo(TABELA, TABELA))[1]["line_no"]


def test_chk19_conta_todas_quando_ha_muitas():
    achados = C._chk19_tabela_unica(_ctx(_arquivo(TABELA, TABELA, TABELA)))
    assert len(achados) == 1 and "3 tabelas" in achados[0].message


def test_chk19_calado_em_arquivo_sem_tabela():
    assert C._chk19_tabela_unica(_ctx("# so prosa\n")) == []


def test_chk19_mensagem_diz_o_que_fazer():
    m = C._chk19_tabela_unica(_ctx(_arquivo(TABELA, TABELA)))[0].message
    assert "Consolide" in m and "REFERENCIA" in m


def test_chk19_registrado_como_core():
    ids = {c.id: c for c in A.CHECKS}
    assert "CHK-19" in ids and ids["CHK-19"].profile == "core"
    assert ids["CHK-19"].severity_default == "CRÍTICO"
    assert A.core_boundary_violations(A.CHECKS) == []


def test_chk19_aparece_no_relatorio_do_motor(tmp_path):
    (tmp_path / "TODO.md").write_text(_arquivo(TABELA, TABELA),
                                      encoding="utf-8", newline="")
    res = A.run_audit(str(tmp_path), checks=A.CHECKS, profile_override="core")
    assert any(f.check_id == "CHK-19" for f in res.findings)
    assert "CHK-19" in res.report_text


def test_chk19_nao_dispara_no_todo_do_proprio_repo():
    """Dogfooding: o TODO.md deste repositorio segue o proprio contrato."""
    import os
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "TODO.md"), encoding="utf-8",
              newline="") as fh:
        text = fh.read()
    assert C._chk19_tabela_unica(_ctx(text)) == []


@pytest.mark.parametrize("n", [2, 5])
def test_chk19_line_no_e_sempre_da_segunda(n):
    text = _arquivo(*([TABELA] * n))
    f = C._chk19_tabela_unica(_ctx(text))[0]
    assert f.line_no == L.work_tables(text)[1]["line_no"]
