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
  - SNAPSHOT-1 (achado do team-lead, 2a rodada do BASELINE-FRAGIL): as
    fixtures sao arquivos VIVOS de OUTROS projetos, editados por OUTRAS
    sessoes a QUALQUER momento -- inclusive enquanto esta suite roda (caso
    real: 2 itens do consumidor B perderam o emoji-prefixo reconhecido
    entre uma execucao e a seguinte). Testar contra o arquivo AO VIVO faz o
    contrato inteiro -- contagem, round-trip, classificacao -- quebrar por
    TRABALHO LEGITIMO alheio, nao por regressao deste projeto. Por isso
    TODOS os testes deste arquivo leem um SNAPSHOT imutavel (tambem no
    cache do pytest, nunca versionado, com metadados de origem/data ao
    lado), congelado uma vez e reusado ate regeneracao EXPLICITA -- nunca
    o arquivo vivo diretamente (ver `_frozen_fixture_text`).
"""
import datetime
import json
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


# Caminho EXPLICITO de regeneracao (SNAPSHOT-1/BASELINE-FRAGIL): regenerar
# e ato CONSCIENTE do operador, nunca automatico -- por isso exige exportar
# esta variavel (nome por chave, nao um "--force" que alguem digita sem
# pensar). Uma UNICA variavel governa os DOIS congelamentos (snapshot de
# texto + baseline de classificacao) -- deliberado: regenerar o snapshot
# sem regenerar o baseline junto reabriria a MESMA fragilidade um nivel
# acima (baseline antigo comparado contra snapshot novo).
ENV_REGEN_BASELINE = "TAB_PENDENCIAS_REGEN_BASELINE_CONTR1"


def _read_live_fixture(env_name):
    """Le o arquivo VIVO apontado pela variavel de ambiente `env_name`, com
    newline="" (nunca normaliza CRLF/LF -- ADR-0001 (e).3). Pula o teste com
    motivo explicito se a variavel nao estiver definida OU se o caminho nao
    existir (o caso NORMAL em CI/clone publico). Uso RESTRITO: so
    `_frozen_fixture_text` chama isto, na captura do snapshot -- nenhum
    teste le o arquivo vivo diretamente (ver SNAPSHOT-1 na docstring do
    modulo)."""
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
        return fh.read(), path


def _frozen_fixture_text(cache, env_name, key, regen):
    """Devolve `(texto, recapturado)` -- o texto SEMPRE vem de um SNAPSHOT
    imutavel no cache do pytest (nunca do arquivo vivo diretamente), e
    `recapturado` e True quando este chamado ACABOU de (re)capturar o
    snapshot (1a execucao nesta maquina, ou `regen=True`).

    SNAPSHOT-1: o arquivo apontado por `env_name` e de OUTRO projeto,
    editado por OUTRA sessao a qualquer momento -- inclusive durante esta
    suite. Ler o arquivo vivo a cada execucao faz o contrato (contagem,
    round-trip, classificacao) quebrar por trabalho legitimo alheio. O
    snapshot fixa o insumo; so muda por regeneracao EXPLICITA (nunca
    automatica, nunca por os testes reexecutarem)."""
    text_key = f"contr1/snapshot_v1_{key}"
    meta_key = f"contr1/snapshot_v1_{key}_meta"
    cached = None if regen else cache.get(text_key, None)
    if cached is not None:
        return cached, False
    text, path = _read_live_fixture(env_name)
    cache.set(text_key, text)
    cache.set(meta_key, {
        "origem_env_var": env_name,
        "origem_caminho": path,
        "congelado_em": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "motivo": "regen_deliberado" if regen else "1a_execucao",
    })
    return text, True


def _read_fixture(cache, env_name, key):
    """Fachada usada pelos testes de contrato: devolve o texto CONGELADO da
    fixture (nunca o arquivo vivo -- ver `_frozen_fixture_text`). Compartilha
    a MESMA variavel de regen que o baseline de classificacao
    (`ENV_REGEN_BASELINE`), para que um unico ato deliberado regenere os dois
    juntos. `pytest.skip` (nao AssertionError) na 1a captura/regen -- e um
    estado de setup, nao um resultado de teste."""
    regen = bool(os.environ.get(ENV_REGEN_BASELINE, "").strip())
    text, recapturado = _frozen_fixture_text(cache, env_name, key, regen)
    if recapturado:
        pytest.skip(
            f"{key}: snapshot da fixture "
            + (f"REGENERADO deliberadamente via {ENV_REGEN_BASELINE}=1"
               if regen else "CONGELADO agora (1a execucao nesta maquina)")
            + " -- .pytest_cache/, ja no .gitignore, nunca versionado "
              "(metadados de origem/data ao lado). Rode a suite de novo "
              "para exercitar os testes de contrato contra este snapshot."
        )
    return text


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
    path, expected_count, key, cache
):
    text = _read_fixture(cache, path, key)
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
def test_roundtrip_byte_exato_antes_de_qualquer_escrita(path, expected_count, key, cache):
    text = _read_fixture(cache, path, key)
    tbl = L.parse_table(text)
    assert tbl is not None
    assert "\n".join(tbl["lines"]) == text, (
        f"{key}: round-trip split/join divergiu do arquivo original"
    )


@pytest.mark.parametrize("path,expected_count,key", _FIXTURES)
def test_roundtrip_apos_set_status_cell_em_todos_os_itens(path, expected_count, key, cache):
    """Aplica set_status_cell em TODAS as N linhas de item (nao so uma amostra)
    e prova que (a) nenhuma linha fora do conjunto de Status mudou um byte
    sequer, (b) a contagem de itens continua a mesma, e (c) as N celulas de
    Status realmente mudaram para o valor setado."""
    text = _read_fixture(cache, path, key)
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
    path, expected_count, key, cache
):
    text = _read_fixture(cache, path, key)
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
# Estabilidade do mapa de status (id -> CLASSIFICACAO DERIVADA): baseline no
# cache local do proprio pytest (nunca versionado). Mecanismo de diff testado
# ISOLADAMENTE com dados sinteticos (sempre roda, mesmo sem as fixtures
# reais), depois reusado contra o corpus real.
#
# BASELINE-FRAGIL: a versao anterior congelava o TEXTO BRUTO da celula de
# Status. Isso e forte demais -- as fixtures sao arquivos VIVOS, editados por
# outras sessoes (donos legitimos do arquivo), e qualquer edicao de prosa
# (acrescentar um detalhe, uma data, uma ressalva) quebrava o teste mesmo
# quando o emoji-prefixo e a classificacao derivada (D-1) permaneciam
# IDENTICOS -- ou seja, o teste acusava uma mudanca que nao e o que ele
# existe para detectar (o proposito declarado e: acusar quando um CONSERTO
# DE PARSER futuro reclassificar algum item). Agora o baseline congela o
# RESULTADO dos predicados de classificacao (`_status_kind`,
# `status_classification_via`, `is_pending`, `is_flip_eligible`,
# `is_awaiting_verification`, `is_done`), nao a celula inteira.
# ----------------------------------------------------------------------------

def _status_classification(status):
    """Classificacao DERIVADA de uma celula de Status -- kind do
    emoji-prefixo (D-1) mais o resultado de cada predicado de negocio, NUNCA
    o texto bruto da celula. E exatamente o que `BASELINE-FRAGIL` passa a
    congelar: uma edicao de prosa que preserva emoji/predicados nao muda
    esta tupla; uma reclassificacao real (outro emoji, ou os predicados
    discordando) muda."""
    return (
        L._status_kind(status),
        L.status_classification_via(status),
        L.is_pending(status),
        L.is_flip_eligible(status),
        L.is_awaiting_verification(status),
        L.is_done(status),
    )


def _frozen_map_diff(baseline, current):
    """Diff simetrico id->classificacao entre dois mapas -- devolve {id:
    (antes, depois)} SO dos IDs cuja classificacao mudou, para o teste
    acusar qual item mudou, nao so 'falhou'. `baseline` pode vir do cache
    do pytest (JSON: tupla desserializa como lista) -- normalizado para
    tupla antes de comparar, senao toda entrada aparentaria ter mudado so
    pela diferenca de tipo list/tuple."""
    def _norm(v):
        return tuple(v) if isinstance(v, list) else v

    baseline = {k: _norm(v) for k, v in baseline.items()}
    current = {k: _norm(v) for k, v in current.items()}
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
    """`path` aqui e o nome da variavel de ambiente (ver `_FIXTURES`).
    SNAPSHOT-1: le o texto pelo SNAPSHOT congelado (`_frozen_fixture_text`),
    nunca o arquivo vivo -- e o mesmo `regen` (`ENV_REGEN_BASELINE`) que
    controla o snapshot TAMBEM reseta o baseline de classificacao na MESMA
    chamada, atomicamente: regenerar o snapshot sem regenerar o baseline
    junto compararia classificacao NOVA contra baseline VELHO, reabrindo a
    mesma fragilidade um nivel acima."""
    regen = bool(os.environ.get(ENV_REGEN_BASELINE, "").strip())
    text, snapshot_recapturado = _frozen_fixture_text(cache, path, key, regen)
    tbl = L.parse_table(text)
    current = {
        it["id"]: _status_classification(it["status"]) for it in tbl["items"]
    }
    # v2: chave NOVA de proposito. A chave antiga (`status_map_{key}`)
    # guardava o TEXTO bruto da celula -- reaproveitar o mesmo nome faria a
    # 1a execucao pos-conserto comparar tupla contra string e acusar TODO
    # item como "mudou" por um motivo que nao e reclassificacao nenhuma.
    cache_key = f"contr1/status_classification_v2_{key}"

    # Baseline tem de ser re-congelado sempre que o SNAPSHOT foi
    # (re)capturado nesta mesma chamada -- senao compararia a classificacao
    # do snapshot NOVO contra o baseline do snapshot ANTIGO, o que e uma
    # divergencia espuria (nao uma reclassificacao do parser).
    baseline = None if (regen or snapshot_recapturado) else cache.get(cache_key, None)
    if baseline is None:
        cache.set(cache_key, current)
        alvo = "snapshot da fixture e baseline de classificacao" if snapshot_recapturado \
            else "baseline de classificacao"
        if regen:
            pytest.skip(
                f"{key}: {alvo} REGENERADOS deliberadamente via "
                f"{ENV_REGEN_BASELINE}=1 -- use isto SO quando a mudanca for "
                "legitima (conserto de parser proposital, ou aceitar o "
                "estado atual da fixture como novo ponto de partida), nunca "
                "por reflexo para silenciar um vermelho. Rode a suite de "
                "novo SEM esta variavel para validar contra o estado novo."
            )
        pytest.skip(
            f"{key}: {alvo} CONGELADO agora (1a execucao nesta maquina) -- "
            ".pytest_cache/, ja no .gitignore, nunca versionado. Rode a "
            "suite de novo para validar estabilidade contra este estado."
        )
    mudou = _frozen_map_diff(baseline, current)
    assert not mudou, (
        f"{key}: classificacao DERIVADA de status mudou para {len(mudou)} "
        f"item(ns) desde o baseline congelado -- {mudou!r}"
    )


def test_mapa_status_congelado_consumidor_a(cache):
    _check_status_map_estavel(cache, "consumidor_a", FIXTURE_ENV_A)


def test_mapa_status_congelado_consumidor_b(cache):
    _check_status_map_estavel(cache, "consumidor_b", FIXTURE_ENV_B)


# ----------------------------------------------------------------------------
# BASELINE-FRAGIL: prova de que `_status_classification` ignora edicao de
# prosa (o caso real do bug -- ver docstring da secao acima) mas ainda
# distingue uma reclassificacao de verdade.
# ----------------------------------------------------------------------------

def test_classificacao_identica_apesar_de_prosa_diferente():
    """O caso real que quebrava o teste antigo: mesmo emoji-prefixo, prosa
    anexa diferente (outra sessao editou o arquivo vivo) -- classificacao
    tem de ser a MESMA tupla."""
    a = _status_classification("✅ Concluído: FEITO 2026-07-16")
    b = _status_classification(
        "✅ Concluído PARCIAL. ESPELHO LOCAL APROVADO 2026-07-28 por "
        "qa-engineer independente: defeito real achado e corrigido."
    )
    assert a == b


def test_classificacao_muda_quando_emoji_muda():
    pendente = _status_classification("⏳ Pendente (piloto combinado)")
    verificacao = _status_classification("🔍 Pendente verificação")
    assert pendente != verificacao


# ----------------------------------------------------------------------------
# SNAPSHOT-1: prova com corpus SINTETICO (nunca a fixture real -- nao se
# sabota arquivo rastreado nem fixture viva) de que o mecanismo inteiro
# (snapshot de texto + baseline de classificacao) (a) IGNORA qualquer
# edicao do arquivo vivo -- prosa OU reclassificacao real -- depois de
# congelado; (b) ainda acusa, nomeando o ID, quando o PROPRIO PARSER muda
# de comportamento sobre o MESMO insumo congelado (o caso que o teste
# existe para pegar); (c) o caminho de regeneracao e deliberado, unico e
# atomico para os dois congelamentos.
# ----------------------------------------------------------------------------

class _FakeCache:
    """Cache minima que roundtripa por JSON, igual ao cache real do pytest
    (`request.config.cache`) -- crucial para exercitar de verdade a
    normalizacao tupla/lista de `_frozen_map_diff` (sem o roundtrip, o bug
    de comparar tupla contra lista nunca apareceria neste teste)."""

    def __init__(self):
        self._dados = {}

    def get(self, key, default):
        if key not in self._dados:
            return default
        return json.loads(self._dados[key])

    def set(self, key, value):
        self._dados[key] = json.dumps(value)


_TODO_HEADER = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)


def _todo_sintetico(status_x1):
    return (
        "# Sintetico BASELINE-FRAGIL\n\n" + _TODO_HEADER +
        f"| X-1 | W1 | Core | Item 1 | Alta | — | Média | {status_x1} | — |\n"
        "| X-2 | W2 | Core | Item 2 | Alta | — | Média | ⏳ Pendente | — |\n"
    )


def test_snapshot_ignora_qualquer_edicao_do_arquivo_vivo_depois_de_congelado(
    tmp_path, monkeypatch
):
    """O caso real que gerou esta 2a rodada: o consumidor B foi editado
    por OUTRA sessao (2 itens perderam o emoji-prefixo) enquanto a suite
    rodava. Depois do snapshot congelado, NENHUMA edicao do arquivo vivo
    -- nem prosa, nem reclassificacao de verdade -- pode voltar a
    acusar."""
    env_name = "TAB_PENDENCIAS_TESTE_SINTETICO_SNAPSHOT_IMUNE"
    fixture_path = tmp_path / "TODO_sintetico.md"
    cache = _FakeCache()

    fixture_path.write_text(_todo_sintetico("✅ Concluído: v1"), encoding="utf-8")
    monkeypatch.setenv(env_name, str(fixture_path))
    with pytest.raises(pytest.skip.Exception, match="CONGELADO agora"):
        _check_status_map_estavel(cache, "sintetico_imune", env_name)

    # "Outra sessao" edita o arquivo VIVO com prosa nova (mesma classificacao).
    fixture_path.write_text(
        _todo_sintetico("✅ Concluído: v2, detalhe anexado por outra sessao"),
        encoding="utf-8",
    )
    _check_status_map_estavel(cache, "sintetico_imune", env_name)  # nao levanta

    # "Outra sessao" agora faz uma RECLASSIFICACAO real no arquivo vivo
    # (perde o emoji-prefixo, igual ao caso real do consumidor B) -- o
    # snapshot ja congelado tem de blindar isso tambem.
    fixture_path.write_text(
        _todo_sintetico("Concluido sem emoji-prefixo (edicao alheia)"),
        encoding="utf-8",
    )
    _check_status_map_estavel(cache, "sintetico_imune", env_name)  # nao levanta


def test_baseline_acusa_quando_o_PROPRIO_PARSER_reclassifica_o_insumo_congelado(
    tmp_path, monkeypatch
):
    """Mutacao do PARSER (nao do dado -- ver teste acima): com o insumo
    CONGELADO e sem nenhuma edicao de arquivo, simula um conserto de
    parser que muda `is_done` -- o baseline tem de acusar, nomeando X-1.
    Restaurado o predicado, volta a ficar limpo."""
    env_name = "TAB_PENDENCIAS_TESTE_SINTETICO_PARSER_MUTADO"
    fixture_path = tmp_path / "TODO_sintetico.md"
    cache = _FakeCache()

    fixture_path.write_text(_todo_sintetico("✅ Concluído: v1"), encoding="utf-8")
    monkeypatch.setenv(env_name, str(fixture_path))
    with pytest.raises(pytest.skip.Exception, match="CONGELADO agora"):
        _check_status_map_estavel(cache, "sintetico_parser", env_name)

    # Nenhuma edicao de arquivo -- simula um CONSERTO DE PARSER que muda o
    # predicado is_done (ex.: um refactor de ADR-0001 que altera a regra).
    monkeypatch.setattr(L, "is_done", lambda status: False)
    with pytest.raises(AssertionError, match=r"X-1"):
        _check_status_map_estavel(cache, "sintetico_parser", env_name)

    # Restaurado o predicado (monkeypatch desfeito no proximo `undo`
    # explicito) -- volta a ficar limpo, prova que o vermelho nao e
    # permanente.
    monkeypatch.undo()
    _check_status_map_estavel(cache, "sintetico_parser", env_name)  # nao levanta


def test_regeneracao_atomica_de_snapshot_e_baseline_via_env_var(tmp_path, monkeypatch):
    """Regen deliberado (UMA variavel) recongela snapshot E baseline
    JUNTOS -- nunca so um dos dois (o que compararia classificacao nova
    contra baseline velho)."""
    env_name = "TAB_PENDENCIAS_TESTE_SINTETICO_REGEN_ATOMICO"
    fixture_path = tmp_path / "TODO_sintetico.md"
    cache = _FakeCache()

    fixture_path.write_text(_todo_sintetico("⏳ Pendente"), encoding="utf-8")
    monkeypatch.setenv(env_name, str(fixture_path))
    with pytest.raises(pytest.skip.Exception, match="CONGELADO agora"):
        _check_status_map_estavel(cache, "sintetico_regen", env_name)

    # "Outra sessao" faz uma mudanca REAL e legitima no arquivo vivo --
    # sem regen, o snapshot blinda: nao acusa nada.
    fixture_path.write_text(_todo_sintetico("✅ Concluído"), encoding="utf-8")
    _check_status_map_estavel(cache, "sintetico_regen", env_name)  # nao levanta

    # Regen deliberado via env var -- skip explicito, recongela os DOIS
    # (snapshot com o conteudo novo + baseline derivado dele) numa unica
    # chamada.
    monkeypatch.setenv(ENV_REGEN_BASELINE, "1")
    with pytest.raises(pytest.skip.Exception, match="REGENERADOS deliberadamente"):
        _check_status_map_estavel(cache, "sintetico_regen", env_name)
    monkeypatch.delenv(ENV_REGEN_BASELINE)

    # Depois do regen, o MESMO estado (agora "✅ Concluído") passa limpo
    # contra o snapshot/baseline novos.
    _check_status_map_estavel(cache, "sintetico_regen", env_name)  # nao levanta


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
def test_todo_parser_bug_deveria_ser_visivel_mas_nao_e_hoje(cache):
    text = _read_fixture(cache, FIXTURE_ENV_B, "consumidor_b")
    tbl = L.parse_table(text)
    ids = {it["id"] for it in tbl["items"]}
    assert "TODO-PARSER-BUG" in ids


def test_fragmento_truncado_de_atom3_agora_com_rastro_no_parser(cache):
    """CHK-CORE/ADR-0001 (b).5: a chave 'malformed' nasceu em todo_lib.py --
    o fragmento truncado/duplicado adjacente a ATOM-3 (consumidor B) deixa
    de ser invisivel: aparece em 'malformed' com o numero da linha, mesmo
    continuando fora de 'items' (a guarda de ncols do nucleo nao mudou, so
    deixou de ser silenciosa). Promovido de xfail(strict) para teste normal
    -- XPASS investigado, nao falso sinal."""
    text = _read_fixture(cache, FIXTURE_ENV_B, "consumidor_b")
    tbl = L.parse_table(text)
    assert "malformed" in tbl
    assert len(tbl["malformed"]) >= 1


def test_atom3_resolve_hoje_para_a_linha_completa_apesar_do_fragmento_adjacente(cache):
    """NAO e xfail: hoje o parser JA resolve ATOM-3 corretamente (o
    fragmento truncado adjacente e ignorado pela guarda de ncols antes de
    chegar a extrair um ID dele) -- comportamento correto que a fatia
    SPRAWL-1/FIX-ENG nao pode regredir (ex.: um fix de consolidacao mal
    filtrado poderia acidentalmente contar as DUAS linhas como duas
    entregas de ATOM-3)."""
    text = _read_fixture(cache, FIXTURE_ENV_B, "consumidor_b")
    tbl = L.parse_table(text)
    atom3 = [it for it in tbl["items"] if it["id"] == "ATOM-3"]
    assert len(atom3) == 1, (
        f"esperado exatamente 1 ATOM-3 (a linha completa), achou {len(atom3)}"
    )
