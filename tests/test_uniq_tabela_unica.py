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


# --------------------------------- CHK-20 ----------------------------------
# Linha em branco DENTRO da tabela: o mecanismo silencioso pelo qual uma
# tabela vira duas (o parser atravessa, o Markdown nao).

def _partida(n_brancas=1):
    """Tabela canonica com `n_brancas` linha(s) em branco no meio."""
    return _arquivo([CAB, SEP, LINHAS[0]] + [""] * n_brancas + [LINHAS[1]])


def test_blank_gaps_calado_em_tabela_contigua():
    assert L.blank_gaps_in_table(_arquivo(TABELA)) == []


def test_blank_gaps_acha_a_linha_em_branco_do_meio():
    text = _partida()
    gaps = L.blank_gaps_in_table(text)
    assert len(gaps) == 1
    assert text.split("\n")[gaps[0]["line_no"]].strip() == ""


def test_blank_gaps_ignora_buraco_com_heading():
    """D-12: a mesma tabela sob subtitulos e legitima -- nao e achado aqui."""
    text = "\n".join(PREAMBULO + [CAB, SEP, LINHAS[0], "", "### Onda 2", "",
                                  LINHAS[1]]) + "\n"
    assert L.blank_gaps_in_table(text) == []


def test_blank_gaps_nao_acusa_o_fim_do_arquivo():
    """Linha em branco DEPOIS da tabela nao esta dentro dela."""
    assert L.blank_gaps_in_table(_arquivo(TABELA) + "\n\nprosa final\n") == []


def test_blank_gaps_sem_tabela_devolve_vazio():
    assert L.blank_gaps_in_table("# so prosa\n\nnada\n") == []


def test_chk20_calado_na_tabela_limpa():
    assert C._chk20_linha_em_branco_na_tabela(_ctx(_arquivo(TABELA))) == []


def test_chk20_acusa_linha_em_branco_no_meio():
    achados = C._chk20_linha_em_branco_na_tabela(_ctx(_partida()))
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-20" and f.severity == "IMPORTANTE"
    assert f.fixable is False
    assert "ENCERRA a tabela" in f.message


def test_chk20_conta_as_brancas_do_buraco():
    f = C._chk20_linha_em_branco_na_tabela(_ctx(_partida(3)))[0]
    assert "3 linha(s) em branco" in f.message


def test_chk20_um_achado_por_buraco():
    text = _arquivo([CAB, SEP, LINHAS[0], "", LINHAS[1], "",
                     "| A-3 | W2 | Base | ⏳ Pendente |"])
    assert len(C._chk20_linha_em_branco_na_tabela(_ctx(text))) == 2


def test_chk20_declara_prosa_encontrada_no_buraco():
    text = _arquivo([CAB, SEP, LINHAS[0], "", "nota solta no meio", "",
                     LINHAS[1]])
    f = C._chk20_linha_em_branco_na_tabela(_ctx(text))[0]
    assert "linha(s) de prosa" in f.message


def test_chk20_calado_sob_subtitulo_d12():
    text = "\n".join(PREAMBULO + [CAB, SEP, LINHAS[0], "", "### Onda 2", "",
                                  LINHAS[1]]) + "\n"
    assert C._chk20_linha_em_branco_na_tabela(_ctx(text)) == []


def test_chk20_a_leitura_continua_completa_apesar_do_defeito():
    """Prova de que o defeito e SILENCIOSO (e por isso IMPORTANTE, nao
    CRITICO): com a linha em branco, os 2 itens continuam sendo lidos."""
    tbl = L.parse_table(_partida())
    assert [it["id"] for it in tbl["items"]] == ["A-1", "A-2"]


def test_chk20_e_chk19_juntos_quando_a_metade_de_baixo_repete_o_cabecalho():
    """Quebra consumada: dai o dado some de verdade e o CRITICO aparece."""
    text = _arquivo([CAB, SEP, LINHAS[0]] + [""] + [CAB, SEP, LINHAS[1]])
    assert len(C._chk19_tabela_unica(_ctx(text))) == 1
    assert [it["id"] for it in L.parse_table(text)["items"]] == ["A-1"]


def test_chk20_registrado_como_core_importante():
    ids = {c.id: c for c in A.CHECKS}
    assert "CHK-20" in ids and ids["CHK-20"].profile == "core"
    assert ids["CHK-20"].severity_default == "IMPORTANTE"


def test_chk20_aparece_no_relatorio_do_motor(tmp_path):
    (tmp_path / "TODO.md").write_text(_partida(), encoding="utf-8",
                                      newline="")
    res = A.run_audit(str(tmp_path), checks=A.CHECKS, profile_override="core")
    assert any(f.check_id == "CHK-20" for f in res.findings)
    assert "CHK-20" in res.report_text


def test_chk20_nao_dispara_no_todo_do_proprio_repo():
    import os
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "TODO.md"), encoding="utf-8",
              newline="") as fh:
        text = fh.read()
    assert C._chk20_linha_em_branco_na_tabela(_ctx(text)) == []


def test_chk20_tolera_crlf():
    text = _partida().replace("\n", "\r\n")
    assert len(C._chk20_linha_em_branco_na_tabela(_ctx(text))) == 1


# ----------------------- migrador: recusa em vez de adivinhar ---------------
# UNIQ-1 aplicado a `tools/todo_migrate_inbox.py`: com 2+ tabelas de trabalho
# ele NAO escolhe (antes elegia sempre a 1a do arquivo).

import os  # noqa: E402 -- so os testes de CLI abaixo precisam
import subprocess  # noqa: E402
import sys  # noqa: E402

import todo_migrate_inbox as M  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRADOR = os.path.join(REPO_ROOT, "tools", "todo_migrate_inbox.py")
INBOX = ["## INBOX (descobertas não priorizadas)", "",
         "- —: [triage since=2026-08-19 reason=missing-info] descoberta X"]


def _legado(*blocos_antes_da_inbox):
    """Arquivo LEGADO (INBOX DEPOIS da tabela) com os blocos dados."""
    linhas = list(PREAMBULO)
    for i, b in enumerate(blocos_antes_da_inbox):
        if i:
            linhas.append("")
        linhas.extend(b)
    linhas += [""] + INBOX
    return "\n".join(linhas) + "\n"


def test_plan_marca_ambiguidade_com_duas_tabelas_de_trabalho():
    info = M.plan(_legado(TABELA, TABELA))
    assert info["ambiguous"] is True
    assert info["work_tables"] == 2
    assert info["needs_migration"] is False
    assert "2 tabelas" in info["reason"]


def test_plan_nao_marca_ambiguidade_com_uma_tabela():
    info = M.plan(_legado(TABELA))
    assert info["ambiguous"] is False and info["work_tables"] == 1
    assert info["needs_migration"] is True


def test_plan_nao_marca_ambiguidade_com_tabela_de_referencia():
    info = M.plan(_legado(REFERENCIA, TABELA))
    assert info["ambiguous"] is False and info["work_tables"] == 1


def test_migrate_text_recusa_com_duas_tabelas_de_trabalho():
    with pytest.raises(M.MigrationError) as exc:
        M.migrate_text(_legado(TABELA, TABELA))
    assert "tabelas DE TRABALHO" in str(exc.value)


def test_migrate_text_ainda_migra_com_uma_so():
    novo, mudou = M.migrate_text(_legado(TABELA))
    assert mudou is True
    assert L.layout(novo)["canonical"] is True
    # nenhum item perdido no caminho
    assert [it["id"] for it in L.parse_table(novo)["items"]] == ["A-1", "A-2"]


def test_migrate_text_migra_com_referencia_junto():
    novo, mudou = M.migrate_text(_legado(REFERENCIA, TABELA))
    assert mudou is True and L.layout(novo)["canonical"] is True


def test_recusa_nao_toca_o_arquivo(tmp_path):
    alvo = tmp_path / "TODO.md"
    original = _legado(TABELA, TABELA)
    alvo.write_text(original, encoding="utf-8", newline="")
    r = subprocess.run([sys.executable, MIGRADOR, str(alvo), "--apply"],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 1
    assert "RECUSADA" in r.stderr
    assert alvo.read_text(encoding="utf-8") == original


def test_recusa_tambem_no_check(tmp_path):
    alvo = tmp_path / "TODO.md"
    alvo.write_text(_legado(TABELA, TABELA), encoding="utf-8", newline="")
    r = subprocess.run([sys.executable, MIGRADOR, str(alvo), "--check"],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 1 and "RECUSADA" in r.stderr


def test_com_uma_tabela_o_apply_continua_funcionando(tmp_path):
    alvo = tmp_path / "TODO.md"
    alvo.write_text(_legado(TABELA), encoding="utf-8", newline="")
    r = subprocess.run([sys.executable, MIGRADOR, str(alvo), "--apply"],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    depois = alvo.read_text(encoding="utf-8")
    assert L.layout(depois)["canonical"] is True


def test_a_recusa_diz_quantas_e_onde():
    info = M.plan(_legado(TABELA, TABELA))
    linhas = [w["line_no"] + 1 for w in L.work_tables(_legado(TABELA, TABELA))]
    for n in linhas:
        assert f"linha {n} " in info["reason"]


def test_recusa_mesmo_quando_o_nucleo_nao_elege_nenhuma():
    """Duas tabelas com coluna de ID de nome composto: `parse_table` nao elege
    nenhuma (exige a celula exata "id"), mas a ambiguidade e real e a recusa
    tem que preferir explicar isso a dizer so "sem tabela canonica"."""
    outra = ["| # | ID (AUD-*) | Severidade | Status |",
             "| :--- | :--- | :--- | :--- |",
             "| 1 | AUD-01 | Alta | ⏳ Pendente |"]
    info = M.plan(_legado(outra, outra))
    assert info["ambiguous"] is True and "2 tabelas" in info["reason"]
