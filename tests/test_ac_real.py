"""tests/test_ac_real.py -- AC-REAL: aceitacao do `--audit` em corpus real.

Decide se o `--audit` cumpre a promessa que motivou o projeto inteiro (o
incidente "93% de uma tabela invisivel"). Dois ACs, um por consumidor real:

  AC-1 (consumidor B, TAB_PENDENCIAS_FIXTURE_B): o `--audit` tem de achar
      (a) o item invisivel ao parser por pipe cru no proprio texto
          (TODO-PARSER-BUG) -- CHK-02, celula(s) A MAIS, diagnostico de pipe
          nao escapado, sugestao `\\|`, [auto-fixavel];
      (b) o fragmento truncado/duplicado adjacente a ATOM-3 -- CHK-02,
          celula(s) A MENOS, [julgamento];
      (c) o span/sprawl da tabela canonica -- CHK-03.
  AC-2 (consumidor A, TAB_PENDENCIAS_FIXTURE_A): contagem reconciliada
      (parser == contagem independente) e zero achado CRITICO.

Localizacao SEMPRE por CONTEUDO (texto da propria linha malformada, nunca
numero de linha hardcoded) -- os dois arquivos reais sao editados por outras
sessoes a qualquer momento (confirmado: 3 edicoes so hoje). Um teste ancorado
em numero de linha vira falso alarme na primeira mexida alheia.

Insumo: reusa o MESMO mecanismo de snapshot imutavel de
`test_contract_real_corpus.py` (SNAPSHOT-1/BASELINE-FRAGIL) -- nunca o
arquivo vivo diretamente para as asserções de conteudo/achado. A UNICA
excecao deliberada e `test_ac_real_read_only_*`, que precisa operar sobre o
CAMINHO REAL (nao uma copia) porque e exatamente o que --audit tocaria em
producao -- read-only e provado por hash antes/depois desse arquivo, nunca
do snapshot.

Mutation testing (mandato do team-lead): sabota-se uma funcao INTERNA
chamada por dentro do check registrado (nunca o proprio `run` topo-de-modulo
registrado em `todo_audit.CHECKS`, cuja referencia ja foi capturada por
VALOR no import do motor -- monkeypatch nele nao teria efeito nenhum sobre
`run_audit()`; o helper interno e resolvido por nome no NAMESPACE do modulo
a cada chamada, entao o monkeypatch se propaga). Via `monkeypatch`, nunca
editando um arquivo em `tools/checks/` (dois outros agentes trabalham
nesses arquivos em paralelo nesta sessao) -- mesma tecnica ja em uso por
`test_contract_real_corpus.py` (`monkeypatch.setattr(L, "is_done", ...)`),
so que aqui aplicada aos checks concretos.
"""
import hashlib
import os
import re

import pytest
import todo_audit as A
import todo_lib as L
from checks import chk_core
from test_contract_real_corpus import (
    FIXTURE_A_ITEM_COUNT,
    FIXTURE_ENV_A,
    FIXTURE_ENV_B,
    _independent_item_count,
    _read_fixture,
)

# ----------------------------------------------------------------------------
# (0) --audit e read-only contra o ARQUIVO REAL -- nao a copia/snapshot.
# Prova em separado do resto do arquivo porque e a UNICA parte deste modulo
# que tem justificativa para tocar o caminho vivo (e mesmo assim NUNCA
# escreve nele -- so le, duas vezes, com hash entre as leituras).
# ----------------------------------------------------------------------------

def _md5_bytes(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


@pytest.mark.parametrize(
    "env_var,label",
    [(FIXTURE_ENV_A, "consumidor_a"), (FIXTURE_ENV_B, "consumidor_b")],
)
def test_ac_real_read_only_hash_identico_no_arquivo_real(env_var, label):
    """`run_audit()` -- a MESMA funcao que AC-1/AC-2 chamam abaixo -- nunca
    escreve no TODO.md real, provado por md5 antes/depois do arquivo VIVO
    (nao do snapshot). Independente do resto da suite: continua rodando
    mesmo se o mecanismo de snapshot mudar de forma."""
    path = os.environ.get(env_var, "").strip()
    if not path or not os.path.isfile(path):
        pytest.skip(
            f"{env_var} nao definida ou nao aponta para arquivo existente -- "
            "fixture real e SOMENTE LOCAL (nunca commitada).")
    antes = _md5_bytes(path)
    A.run_audit(os.path.dirname(path), todo_path=path)
    depois = _md5_bytes(path)
    assert antes == depois, (
        f"{label}: --audit (run_audit) alterou o arquivo REAL -- "
        "read-only quebrado.")


# ----------------------------------------------------------------------------
# Insumo comum: snapshot imutavel (mesmo mecanismo de test_contract_real_
# corpus.py) escrito numa copia temporaria (tmp_path do pytest, fora do
# repositorio rastreado) -- nunca o arquivo vivo para as asserções abaixo.
# ----------------------------------------------------------------------------

def _write_snapshot_as_todo(text, tmp_path):
    tmp_todo = tmp_path / "TODO.md"
    with open(tmp_todo, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return tmp_todo


def _frozen_table_and_report(cache, env_name, key, tmp_path):
    text = _read_fixture(cache, env_name, key)
    table = L.parse_table(text)
    assert table is not None, f"{key}: snapshot sem tabela ID+Status"
    tmp_todo = _write_snapshot_as_todo(text, tmp_path)
    result = A.run_audit(str(tmp_path), todo_path=str(tmp_todo))
    return text, table, result


# ----------------------------------------------------------------------------
# AC-1(a) -- TODO-PARSER-BUG: pipe cru, localizado por CONTEUDO (a propria
# linha malformada cita o ID no texto), nunca por numero de linha.
# ----------------------------------------------------------------------------

def _malformado_por_conteudo(table, agulha):
    """As linhas malformadas cujo texto ORIGINAL contem `agulha` -- e assim
    que `AC-1` acha a linha sem depender do numero dela, que muda a cada
    edicao alheia do arquivo real."""
    return [m for m in table["malformed"] if agulha in m["raw"]]


def _achados_chk02_na_linha(findings, line_no):
    return [f for f in findings if f.check_id == "CHK-02" and f.line_no == line_no]


def _assert_pipe_cru_encontrado(m, findings):
    achados = _achados_chk02_na_linha(findings, m["line_no"])
    assert len(achados) == 1, (
        "--audit nao reportou (ou reportou mais de uma vez) o achado CHK-02 "
        f"para a linha do pipe cru de TODO-PARSER-BUG (line_no={m['line_no']})"
    )
    achado = achados[0]
    assert achado.severity == "CRÍTICO", (
        f"TODO-PARSER-BUG deveria ser CRITICO, achou {achado.severity}")
    assert achado.fixable is True, "TODO-PARSER-BUG deveria ser [auto-fixavel]"
    assert achado.fix_ref == "escapar_pipe_cru", (
        f"fix_ref inesperado: {achado.fix_ref!r}")
    msg_low = achado.message.lower()
    assert "pipe" in msg_low, achado.message
    assert "a mais" in msg_low, achado.message
    assert "\\|" in achado.message, (
        "diagnostico tem de sugerir o escape '\\|' -- " + achado.message)


def test_ac1a_todo_parser_bug_pipe_cru_encontrado_por_conteudo(cache, tmp_path):
    _text, table, result = _frozen_table_and_report(
        cache, FIXTURE_ENV_B, "consumidor_b", tmp_path)

    candidatos = _malformado_por_conteudo(table, "TODO-PARSER-BUG")
    assert len(candidatos) == 1, (
        "esperado exatamente 1 linha malformada citando 'TODO-PARSER-BUG' "
        f"no snapshot congelado -- achou {len(candidatos)}. Se o defeito "
        "vivo foi corrigido no arquivo real, este teste precisa ser "
        "revisitado (nao forcar verde)."
    )
    m = candidatos[0]
    assert m["got_ncols"] > m["expected_ncols"], (
        "esperado celula(s) A MAIS (assinatura de pipe cru), nao a menos -- "
        f"got={m['got_ncols']} expected={m['expected_ncols']}"
    )
    _assert_pipe_cru_encontrado(m, result.findings)


# ----------------------------------------------------------------------------
# AC-1(b) -- fragmento truncado/duplicado adjacente a ATOM-3.
# ----------------------------------------------------------------------------

def _assert_fragmento_truncado_encontrado(m, findings):
    achados = _achados_chk02_na_linha(findings, m["line_no"])
    assert len(achados) == 1, (
        "--audit nao reportou (ou reportou mais de uma vez) o achado CHK-02 "
        f"para o fragmento truncado adjacente a ATOM-3 (line_no={m['line_no']})"
    )
    achado = achados[0]
    assert achado.severity == "CRÍTICO", (
        f"fragmento truncado deveria ser CRITICO, achou {achado.severity}")
    assert achado.fixable is False, (
        "fragmento truncado exige julgamento humano -- nao pode ser "
        "[auto-fixavel]")
    assert achado.fix_ref is None
    msg_low = achado.message.lower()
    assert "a menos" in msg_low, achado.message
    assert "truncad" in msg_low, achado.message  # "truncado"/"truncada"


def test_ac1b_fragmento_truncado_atom3_encontrado_por_conteudo(cache, tmp_path):
    _text, table, result = _frozen_table_and_report(
        cache, FIXTURE_ENV_B, "consumidor_b", tmp_path)

    candidatos = _malformado_por_conteudo(table, "ATOM-3")
    assert len(candidatos) == 1, (
        "esperado exatamente 1 linha malformada citando 'ATOM-3' no "
        f"snapshot congelado -- achou {len(candidatos)}."
    )
    m = candidatos[0]
    assert m["got_ncols"] < m["expected_ncols"], (
        "esperado celula(s) A MENOS (assinatura de fragmento truncado) -- "
        f"got={m['got_ncols']} expected={m['expected_ncols']}"
    )
    _assert_fragmento_truncado_encontrado(m, result.findings)

    # Mesmo invariante ja provado em test_contract_real_corpus.py (nao
    # regride aqui): o fragmento adjacente NUNCA duplica o ATOM-3 real como
    # item -- continua exatamente 1 ocorrencia em 'items'.
    atom3_items = [it for it in table["items"] if it["id"] == "ATOM-3"]
    assert len(atom3_items) == 1, (
        f"esperado exatamente 1 ATOM-3 em 'items', achou {len(atom3_items)}")


# ----------------------------------------------------------------------------
# AC-1(c) -- span/sprawl da tabela canonica (CHK-03). O numero de headings
# atravessados e recomputado a partir do PROPRIO snapshot (nunca um numero
# magico fixo) -- so a EXISTENCIA e a SEVERIDADE do achado sao travadas.
# ----------------------------------------------------------------------------

def _esperado_n_crossed(table):
    itens_e_malformed = table["items"] + table["malformed"]
    assert itens_e_malformed, "snapshot sem itens/malformed -- nao da pra medir span"
    fim_canonica = max(x["line_no"] for x in itens_e_malformed)
    return len([h for h in table["headings_crossed"] if h["line_no"] < fim_canonica])


def _assert_chk03_sprawl_presente(table, findings):
    achados = [f for f in findings if f.check_id == "CHK-03"]
    assert achados, "CHK-03 nao produziu nenhum achado para o sprawl conhecido"
    esperado = _esperado_n_crossed(table)
    assert esperado > 0, (
        "o cenario de sprawl pressupoe >=1 heading atravessado -- o "
        "snapshot mudou de forma que o cenario conhecido nao se aplica "
        "mais (investigar, nunca so ajustar o teste para passar)")
    achado = achados[0]
    assert achado.severity == "COSMÉTICO", (
        f"esperado COSMETICO (atravessa headings sem 2o cabecalho "
        f"ID+Status) -- achou {achado.severity}. Se virou CRITICO, a "
        "tabela real ganhou fragmentacao de verdade (2 cabecalhos) -- "
        "investigar antes de ajustar o teste.")
    assert "atravessa" in achado.message.lower(), achado.message
    m = re.search(r"atravessa (\d+) heading", achado.message)
    assert m is not None, f"mensagem sem contagem de headings: {achado.message}"
    assert int(m.group(1)) == esperado, (
        f"CHK-03 reportou {m.group(1)} headings atravessados, "
        f"recomputado independentemente = {esperado}")


def test_ac1c_sprawl_da_tabela_canonica_reportado_por_chk03(cache, tmp_path):
    _text, table, result = _frozen_table_and_report(
        cache, FIXTURE_ENV_B, "consumidor_b", tmp_path)
    _assert_chk03_sprawl_presente(table, result.findings)


# ----------------------------------------------------------------------------
# AC-2 -- consumidor A: contagem reconciliada + zero CRITICO.
# ----------------------------------------------------------------------------

def _assert_zero_critico(findings):
    criticos = [f for f in findings if f.severity == "CRÍTICO"]
    assert not criticos, (
        "AC-2 exige zero achado CRITICO (ou, se houver, listado e "
        "explicado -- nunca 'passou' por omissao). Encontrado(s): "
        + "; ".join(
            f"{f.check_id} linha {f.line_no}: {f.message}" for f in criticos)
    )


def test_ac2_consumidor_a_zero_critico_e_contagem_reconciliada(cache, tmp_path):
    text, table, result = _frozen_table_and_report(
        cache, FIXTURE_ENV_A, "consumidor_a", tmp_path)

    _assert_zero_critico(result.findings)

    # Reconciliacao independente (mesma logica ja auditada em
    # test_contract_real_corpus.py: caminho de codigo DIFERENTE de
    # parse_table, escrito do zero, escape-aware) -- prova adicional ao
    # CHK-11 (que roda todo_health.run() por dentro do motor).
    parser_count = len(table["items"])
    independente = _independent_item_count(text)
    assert parser_count == independente == FIXTURE_A_ITEM_COUNT, (
        f"parser={parser_count} independente={independente} "
        f"esperado={FIXTURE_A_ITEM_COUNT}")

    # Prova que CHK-11 (a reconciliacao PROPRIA do motor) de fato EXECUTOU
    # -- sem isto, "zero CRITICO" acima poderia ser falso-verde por o
    # check nunca ter rodado (perfil errado, excecao engolida etc.).
    assert any(c.id == "CHK-11" for c in A.CHECKS), "CHK-11 sumiu do registro"
    assert not any("CHK-11" in n for n in result.notices), (
        f"CHK-11 nao executou normalmente -- avisos do motor: {result.notices}")


# ----------------------------------------------------------------------------
# Mutation testing (mandato do team-lead): sabota-se um HELPER INTERNO
# chamado por dentro do check registrado -- nunca o proprio `run` topo-de-
# modulo (a referencia em `todo_audit.CHECKS` ja foi capturada por VALOR no
# import do motor; monkeypatch no nome topo-de-modulo NAO se propagaria).
# `monkeypatch` desfaz tudo ao fim de cada teste -- nenhum arquivo em
# `tools/checks/` e tocado, nem em memoria depois do teardown.
# ----------------------------------------------------------------------------

def test_mutacao_chk02_silenciado_derruba_ac1a_e_ac1b(cache, tmp_path, monkeypatch):
    text = _read_fixture(cache, FIXTURE_ENV_B, "consumidor_b")
    table = L.parse_table(text)
    assert table is not None
    m_pipe = next(m for m in table["malformed"] if "TODO-PARSER-BUG" in m["raw"])
    m_atom3 = next(m for m in table["malformed"] if "ATOM-3" in m["raw"])
    tmp_todo = _write_snapshot_as_todo(text, tmp_path)

    # `_malformed_genuinos` e resolvido por NOME dentro do corpo de
    # `_chk02_ncols_diverge` a cada chamada (lookup no namespace do modulo,
    # nao capturado por valor) -- o monkeypatch se propaga atraves do
    # `run` ja registrado em `todo_audit.CHECKS`.
    monkeypatch.setattr(chk_core, "_malformed_genuinos", lambda malformed: [])
    result = A.run_audit(str(tmp_path), todo_path=str(tmp_todo))

    assert not any(f.check_id == "CHK-02" for f in result.findings), (
        "sabotagem sem efeito -- CHK-02 continuou achando algo (o teste de "
        "mutacao nao provou nada)")

    with pytest.raises(AssertionError, match="TODO-PARSER-BUG"):
        _assert_pipe_cru_encontrado(m_pipe, result.findings)
    with pytest.raises(AssertionError, match="ATOM-3"):
        _assert_fragmento_truncado_encontrado(m_atom3, result.findings)


def test_mutacao_chk03_silenciado_derruba_ac1c(cache, tmp_path, monkeypatch):
    text = _read_fixture(cache, FIXTURE_ENV_B, "consumidor_b")
    table = L.parse_table(text)
    assert table is not None
    tmp_todo = _write_snapshot_as_todo(text, tmp_path)

    # `_cabecalhos_id_status` e chamado por nome dentro de
    # `_chk03_tabela_fragmentada` -- mesma tecnica de propagacao acima.
    monkeypatch.setattr(chk_core, "_cabecalhos_id_status", lambda lines: [])
    result = A.run_audit(str(tmp_path), todo_path=str(tmp_todo))

    assert not any(f.check_id == "CHK-03" for f in result.findings), (
        "sabotagem sem efeito -- CHK-03 continuou achando o sprawl")

    with pytest.raises(AssertionError, match="CHK-03"):
        _assert_chk03_sprawl_presente(table, result.findings)


def test_mutacao_chk11_contagem_independente_derruba_ac2(cache, tmp_path, monkeypatch):
    """Mutacao na direcao OPOSTA das duas acima: AC-2 afirma 'zero CRITICO',
    entao a mutacao que prova o teste tem de INTRODUZIR uma divergencia real
    (nao silenciar um achado ja existente, que aqui nao existe) -- quebra o
    contador independente do proprio CHK-11 em +1, o que faz
    `reportado != independente` virar verdade e CHK-11 acusar CRITICO."""
    text = _read_fixture(cache, FIXTURE_ENV_A, "consumidor_a")
    tmp_todo = _write_snapshot_as_todo(text, tmp_path)

    original = chk_core._contagem_independente
    monkeypatch.setattr(chk_core, "_contagem_independente",
                        lambda t: original(t) + 1)
    result = A.run_audit(str(tmp_path), todo_path=str(tmp_todo))

    criticos = [f for f in result.findings if f.severity == "CRÍTICO"]
    assert criticos, "sabotagem sem efeito -- CHK-11 nao acusou divergencia"
    assert any(f.check_id == "CHK-11" for f in criticos), (
        "achado CRITICO existe mas nao e do CHK-11 -- sabotagem errada")

    with pytest.raises(AssertionError, match="CRITICO"):
        _assert_zero_critico(result.findings)
