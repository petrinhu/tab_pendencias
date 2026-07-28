"""tests/test_pred_fix_w5.py -- PRED-FIX (W5): tres predicados de uma linha,
um commit citando os 3 IDs (TODO.md).

Os 3 casos abaixo sao os falsos-negativo/positivo confirmados antes do
conserto (colados no relatorio da fatia):

  1. CIT-1: cited_ids("fechei V-12.", ["V-12"]) == [] (deveria achar V-12 --
     o ponto final de frase cai no lookahead proibido, todo_lib.py ~177-185).
  2. TCH-1: touched_code(["src/inbox/parser.py"]) == False (deveria ser True
     -- substring "/inbox/" em path de CODIGO, todo_lib.py ~49-62; so o
     "inbox/" do TOPO do repo e bookkeeping, nao qualquer dir chamado inbox).
  3. HDR-1: _is_header dispara com qualquer celula que CONTENHA "status"
     (~100-102) -- uma coluna "Sub-status" de tabela alheia encerraria a
     canonica em silencio.
"""
import todo_lib as L


def test_cit1_cited_ids_reconhece_ponto_final_de_frase():
    assert L.cited_ids("fechei V-12.", ["V-12"]) == ["V-12"]


def test_cit1_cited_ids_continua_recusando_continuacao_numerica_por_ponto():
    # Nao pode regredir: "F1.45" nao pode casar com o ID "F1.4" (ponto
    # seguido de digito ainda e continuacao de ID, nao fim de frase).
    assert L.cited_ids("F1.45", ["F1.4"]) == []


def test_cit1_cited_ids_ja_funcionava_com_virgula_parenteses_e_negrito():
    ids = ["V-12"]
    assert L.cited_ids("fechei V-12,", ids) == ["V-12"]
    assert L.cited_ids("fechei (V-12)", ids) == ["V-12"]
    assert L.cited_ids("fechei **V-12**", ids) == ["V-12"]


def test_tch1_dir_de_codigo_chamado_inbox_nao_e_bookkeeping():
    assert L.touched_code(["src/inbox/parser.py"]) is True


def test_tch1_inbox_do_topo_do_repo_continua_sendo_bookkeeping():
    assert L.touched_code(["inbox/nota.md"]) is False
    assert L.touched_code(["TODO.md", "inbox/nota.md"]) is False


def test_hdr1_sub_status_de_tabela_alheia_nao_e_cabecalho_canonico():
    assert L._is_header(["id", "grupo", "sub-status"]) is False


def test_hdr1_status_exato_continua_sendo_cabecalho_canonico():
    assert L._is_header(["id", "onda", "status"]) is True
    assert L._is_header(["ID", "Estado Auditado (Status)"]) is True
