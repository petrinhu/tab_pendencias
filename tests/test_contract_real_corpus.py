"""tests/test_contract_real_corpus.py -- CONTR-1: rede de seguranca de contrato.

Congela o comportamento ATUAL do parser (`tools/todo_lib.py`) contra os 2
consumidores reais vivos do lider, ANTES das ondas que vao mexer no parser
por proposito (BUG-5 emoji-prefixo, SPRAWL-1 fim de tabela, PRED-FIX, etc. --
ver `docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md` secao
(b), o contrato que este arquivo testa). Sem isto, um conserto pode fazer
itens sumirem de um TODO.md real em silencio -- o mesmo incidente ("93% de
uma tabela invisivel") que originou o projeto inteiro.

REGRA DE PRIVACIDADE, SEM EXCECAO: as fixtures abaixo sao TODO.md de
projetos PRIVADOS do autor, fora deste repo, e NUNCA entram aqui -- nem em
trecho, nem em snapshot de dado (id/status/descricao real), nem em nome ou
caminho literal. Consequencias praticas neste arquivo:

  - Os caminhos NAO sao literais neste codigo: vem de variavel de ambiente
    (`TAB_PENDENCIAS_FIXTURE_A` / `TAB_PENDENCIAS_FIXTURE_B`), lidas em
    tempo de execucao. `pytest.skip` com mensagem clara quando a variavel
    nao esta definida OU quando o caminho nao existe -- o caminho NORMAL em
    qualquer clone publico ou job de CI, que nunca tem essas variaveis
    configuradas.
  - Nenhum ID ou trecho de descricao real e hardcoded aqui, com A UNICA
    excecao de "TODO-PARSER-BUG" e "ATOM-3": esses dois IDs ja sao PUBLICOS
    neste mesmo repo (citados no historico de decisao do projeto) como os
    2 defeitos vivos conhecidos do consumidor B -- usa-los aqui como
    PONTEIRO de localizacao nao adiciona nenhuma informacao nova ao repo.
    Toda outra amostra de linha (ex.: para o teste de `set_status_cell`) e
    DESCOBERTA em tempo de execucao (por propriedade, tipo "linha com pipe
    escapado"), nunca por ID literal.
  - O invariante "mapa de status congelado" usa o CACHE LOCAL do proprio
    pytest (`.pytest_cache/`, ja no `.gitignore` deste repo) como baseline
    -- nunca um arquivo versionado. Ausencia de baseline (1a execucao nesta
    maquina) = congela agora e o teste sai SKIPPED com aviso; da 2a execucao
    em diante, compara e ACUSA qual ID mudou de status (nao so "falhou").
"""
import os
import re

import pytest

import todo_lib as L


FIXTURE_ENV_A = "TAB_PENDENCIAS_FIXTURE_A"
FIXTURE_ENV_B = "TAB_PENDENCIAS_FIXTURE_B"

# Contagem de itens esperada em cada fixture real -- e informacao tecnica
# LEGITIMA (evidencia de regressao de contrato), diferente do CAMINHO/nome
# do projeto-fonte (que e privado e nunca e literal neste arquivo).
# Medido em sessao de auditoria por DOIS caminhos independentes --
# L.parse_table() e a recontagem escape-aware escrita do zero abaixo -- sem
# divergencia a reportar.
FIXTURE_A_ITEM_COUNT = 116
FIXTURE_B_ITEM_COUNT = 215

_FIXTURES = [
    pytest.param(FIXTURE_ENV_A, FIXTURE_A_ITEM_COUNT, "consumidor_a", id="consumidor_a"),
    pytest.param(FIXTURE_ENV_B, FIXTURE_B_ITEM_COUNT, "consumidor_b", id="consumidor_b"),
]


def _read_fixture(env_name):
    """Resolve o caminho da fixture real pela variavel de ambiente `env_name`
    e le com newline="" (nunca normaliza CRLF/LF na leitura -- ADR-0001
    (e).3). Pula o teste com motivo explicito se a variavel nao estiver
    definida OU se o caminho nao existir (o caso NORMAL em CI/clone
    publico, que nunca tem fixture real nem a variavel configurada)."""
    path = os.environ.get(env_name, "").strip()
    if not path:
        pytest.skip(
            f"variavel de ambiente {env_name} nao definida -- fixture real "
            "e SOMENTE LOCAL (nunca commitada; ver docstring deste "
            "arquivo). Exporte-a apontando para o TODO.md do consumidor "
            "real para exercitar este teste nesta maquina."
        )
    if not os.path.isfile(path):
        pytest.skip(
            f"{env_name}={path!r} nao aponta para um arquivo existente -- "
            "confira o caminho exportado."
        )
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


# ----------------------------------------------------------------------------
# Recontagem escape-aware INDEPENDENTE de todo_lib.parse_table -- escrita do
# zero (nao reusa _cells/_split_row do modulo sob teste) para nao confiar so
# no codigo sob teste. grep/awk ingenuo quebra no MESMO pipe escapado que o
# parser trata -- ja aconteceu numa auditoria manual anterior: o awk ingenuo
# acusou o arquivo errado por nao conhecer o escape GFM `\|`.
# ----------------------------------------------------------------------------
_SEP_INDEPENDENTE = re.compile(r"(?<!\\)\|")


def _independent_item_count(text):
    lines = text.split("\n")
    ncols = id_idx = None
    count = 0
    for line in lines:
        s = line.lstrip(L.BOM).strip()
        if not s.startswith("|"):
            continue
        parts = _SEP_INDEPENDENTE.split(s)
        if parts and parts[0].strip() == "":
            parts = parts[1:]
        if parts and parts[-1].strip() == "":
            parts = parts[:-1]
        cells = [c.strip() for c in parts]
        low = [c.lower() for c in cells]
        is_header = "id" in low and any("status" in c for c in low)
        is_sep = bool(cells) and set("".join(cells)) <= set("-: ")
        if ncols is None:
            if is_header:
                ncols = len(cells)
                id_idx = low.index("id")
            continue
        if is_sep:
            continue
        if is_header:            # 2o cabecalho ID+Status: encerra a canonica
            break
        if len(cells) != ncols:   # linha malformada: mesma guarda de seguranca
            continue
        iid = cells[id_idx]
        if not iid or iid in ("-", "—"):
            continue
        count += 1
    return count


@pytest.mark.parametrize("path,expected_count,key", _FIXTURES)
def test_contagem_de_itens_bate_parser_e_recontagem_independente(
    path, expected_count, key
):
    text = _read_fixture(path)
    tbl = L.parse_table(text)
    assert tbl is not None, f"{key}: nenhuma tabela ID+Status encontrada"
    parser_count = len(tbl["items"])
    independente = _independent_item_count(text)
    assert independente == parser_count == expected_count, (
        f"{key}: parser={parser_count}, recontagem_independente={independente}, "
        f"esperado={expected_count}"
    )


# ----------------------------------------------------------------------------
# Round-trip byte-exato (ADR-0001 b.1): "\n".join(parse_table(text)["lines"])
# == text ANTES de qualquer set_status_cell, e o resto do arquivo permanece
# byte-identico depois de N chamadas restritas as celulas de Status.
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("path,expected_count,key", _FIXTURES)
def test_roundtrip_byte_exato_antes_de_qualquer_escrita(path, expected_count, key):
    text = _read_fixture(path)
    tbl = L.parse_table(text)
    assert tbl is not None
    assert "\n".join(tbl["lines"]) == text, (
        f"{key}: round-trip split/join divergiu do arquivo original"
    )


@pytest.mark.parametrize("path,expected_count,key", _FIXTURES)
def test_roundtrip_apos_set_status_cell_em_todos_os_itens(path, expected_count, key):
    """Aplica set_status_cell em TODAS as N linhas de item (nao so uma amostra)
    e prova que (a) nenhuma linha fora do conjunto de Status mudou um byte
    sequer, (b) a contagem de itens continua a mesma, e (c) as N celulas de
    Status realmente mudaram para o valor setado."""
    text = _read_fixture(path)
    tbl = L.parse_table(text)
    original_lines = text.split("\n")
    lines = list(tbl["lines"])          # copia -- nao muta o dict do parse
    changed_line_nos = {it["line_no"] for it in tbl["items"]}
    for it in tbl["items"]:
        lines[it["line_no"]] = L.set_status_cell(
            lines[it["line_no"]], tbl["status_idx"], "🔍 Pendente verificação"
        )
    assert len(lines) == len(original_lines)
    for i, (before, after) in enumerate(zip(original_lines, lines)):
        if i in changed_line_nos:
            continue
        assert before == after, (
            f"{key}: linha {i + 1} mudou sem ter sido alvo de set_status_cell "
            "(round-trip quebrado fora da celula de Status)"
        )
    mutated_text = "\n".join(lines)
    tbl2 = L.parse_table(mutated_text)
    assert tbl2 is not None
    assert len(tbl2["items"]) == expected_count, (
        f"{key}: contagem mudou de {expected_count} para {len(tbl2['items'])} "
        "so por ter trocado a celula de Status em todas as linhas"
    )
    assert all(
        it["status"] == "🔍 Pendente verificação" for it in tbl2["items"]
    ), f"{key}: alguma celula de Status nao foi efetivamente trocada"


# ----------------------------------------------------------------------------
# set_status_cell nao corrompe: amostra deterministica (primeiro/meio/ultimo
# item) + toda linha com pipe escapado "\|" DESCOBERTA em tempo de execucao
# (nunca por ID hardcoded -- ver aviso de privacidade no topo do arquivo).
# ----------------------------------------------------------------------------

def _lines_with_escaped_pipe(tbl):
    return [it for it in tbl["items"] if "\\|" in tbl["lines"][it["line_no"]]]


@pytest.mark.parametrize("path,expected_count,key", _FIXTURES)
def test_set_status_cell_preserva_linha_byte_a_byte_amostra_real(
    path, expected_count, key
):
    text = _read_fixture(path)
    tbl = L.parse_table(text)
    n = len(tbl["items"])
    idx_deterministicos = sorted({0, n // 2, n - 1})
    amostra = [tbl["items"][i] for i in idx_deterministicos]
    amostra += _lines_with_escaped_pipe(tbl)
    assert amostra, f"{key}: amostra vazia -- fixture sem itens?"

    for it in amostra:
        original = tbl["lines"][it["line_no"]]
        cells_before = L._cells(original)
        mutada = L.set_status_cell(original, tbl["status_idx"], "🔍 Pendente verificação")
        cells_after = L._cells(mutada)
        assert len(cells_before) == len(cells_after) == tbl["ncols"], (
            f"{key}: numero de celulas mudou para o item id-hash="
            f"{hash(it['id']) & 0xffff:04x}"
        )
        for idx in range(tbl["ncols"]):
            if idx == tbl["status_idx"]:
                continue
            assert cells_before[idx] == cells_after[idx], (
                f"{key}: celula {idx} mudou fora da celula de Status "
                f"(item id-hash={hash(it['id']) & 0xffff:04x})"
            )
        assert cells_after[tbl["status_idx"]] == "🔍 Pendente verificação"


# ----------------------------------------------------------------------------
# Estabilidade do mapa de status (id -> status): baseline no cache local do
# proprio pytest (nunca versionado). Mecanismo de diff testado ISOLADAMENTE
# com dados sinteticos (sempre roda, mesmo sem as fixtures reais), depois
# reusado contra o corpus real.
# ----------------------------------------------------------------------------

def _frozen_map_diff(baseline, current):
    """Diff simetrico id->status entre dois mapas -- devolve {id: (antes,
    depois)} SO dos IDs cuja classificacao mudou, para o teste acusar qual
    item mudou, nao so 'falhou'."""
    keys = set(baseline) | set(current)
    return {
        k: (baseline.get(k), current.get(k))
        for k in keys
        if baseline.get(k) != current.get(k)
    }


def test_frozen_map_diff_acusa_o_id_que_mudou():
    baseline = {"A": "x", "B": "y", "C": "z"}
    current = {"A": "x", "B": "MUDOU", "C": "z"}
    assert _frozen_map_diff(baseline, current) == {"B": ("y", "MUDOU")}


def test_frozen_map_diff_detecta_id_removido_e_adicionado():
    baseline = {"A": "x", "B": "y"}
    current = {"A": "x", "C": "z"}
    assert _frozen_map_diff(baseline, current) == {"B": ("y", None), "C": (None, "z")}


def test_frozen_map_diff_vazio_quando_nada_mudou():
    m = {"A": "x", "B": "y"}
    assert _frozen_map_diff(dict(m), dict(m)) == {}


def _check_status_map_estavel(cache, key, path):
    text = _read_fixture(path)
    tbl = L.parse_table(text)
    current = {it["id"]: it["status"] for it in tbl["items"]}
    cache_key = f"contr1/status_map_{key}"
    baseline = cache.get(cache_key, None)
    if baseline is None:
        cache.set(cache_key, current)
        pytest.skip(
            f"{key}: baseline do mapa de status CONGELADO agora nesta "
            "maquina (.pytest_cache/, ja no .gitignore -- nunca versionado); "
            "rode a suite de novo para validar estabilidade contra ele."
        )
    mudou = _frozen_map_diff(baseline, current)
    assert not mudou, (
        f"{key}: classificacao de status mudou para {len(mudou)} item(ns) "
        f"desde o baseline congelado -- {mudou!r}"
    )


def test_mapa_status_congelado_consumidor_a(cache):
    _check_status_map_estavel(cache, "consumidor_a", FIXTURE_ENV_A)


def test_mapa_status_congelado_consumidor_b(cache):
    _check_status_map_estavel(cache, "consumidor_b", FIXTURE_ENV_B)


# ----------------------------------------------------------------------------
# Estado ATUAL dos 2 defeitos vivos conhecidos do consumidor B (IDs ja
# PUBLICOS neste repo -- ver TODO.md/AC-REAL). NAO conserta nada aqui -- so
# documenta o comportamento hoje, marcado xfail(strict=True): quando a onda
# AC-REAL (--audit/CHK-02) inverter a expectativa, o proprio xfail vira erro
# (XPASS), que e o sinal para atualizar/remover o marcador.
# ----------------------------------------------------------------------------

@pytest.mark.xfail(
    strict=True,
    reason=(
        "defeito vivo conhecido (consumidor B, ver TODO.md/AC-REAL): o item "
        "que DESCREVE o bug do pipe cru esta ele proprio invisivel -- o texto "
        "da propria linha tem '|' cru (nao escapado), a contagem de celulas "
        "diverge do cabecalho e a linha e descartada pela guarda de ncols "
        "(ADR-0001 b.5, 'descarte silencioso e o comportamento do nucleo "
        "hoje'). Autorreferencia ironica: o item some por causa do proprio "
        "bug que ele relata. Fica xfail ate a onda AC-REAL provar que "
        "--audit (CHK-02) o torna visivel/reportado -- se comecar a passar "
        "sem querer, xfail(strict=True) vira XPASS/erro: sinal para "
        "atualizar ou remover este teste."
    ),
)
def test_todo_parser_bug_deveria_ser_visivel_mas_nao_e_hoje():
    text = _read_fixture(FIXTURE_ENV_B)
    tbl = L.parse_table(text)
    ids = {it["id"] for it in tbl["items"]}
    assert "TODO-PARSER-BUG" in ids


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ADR-0001 (b).5: parse_table ainda NAO tem a chave aditiva "
        "'malformed' (fatia futura, fora do escopo de CONTR-1) -- hoje o "
        "fragmento truncado/duplicado do item ATOM-3 (consumidor B) e "
        "descartado pela guarda de ncols SEM deixar "
        "rastro nenhum no dict devolvido por parse_table. Quando a chave "
        "'malformed' existir (SPRAWL-1/CHK-02), este teste vira XPASS/erro: "
        "sinal para atualizar/remover."
    ),
)
def test_fragmento_truncado_de_atom3_ainda_sem_rastro_no_parser():
    text = _read_fixture(FIXTURE_ENV_B)
    tbl = L.parse_table(text)
    assert "malformed" in tbl


def test_atom3_resolve_hoje_para_a_linha_completa_apesar_do_fragmento_adjacente():
    """NAO e xfail: hoje o parser JA resolve ATOM-3 corretamente (o
    fragmento truncado adjacente e ignorado pela guarda de ncols antes de
    chegar a extrair um ID dele) -- comportamento correto que a fatia
    SPRAWL-1/FIX-ENG nao pode regredir (ex.: um fix de consolidacao mal
    filtrado poderia acidentalmente contar as DUAS linhas como duas
    entregas de ATOM-3)."""
    text = _read_fixture(FIXTURE_ENV_B)
    tbl = L.parse_table(text)
    atom3 = [it for it in tbl["items"] if it["id"] == "ATOM-3"]
    assert len(atom3) == 1, (
        f"esperado exatamente 1 ATOM-3 (a linha completa), achou {len(atom3)}"
    )
