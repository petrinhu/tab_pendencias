"""CORP-0 -- corpus sintetico de aceitacao (AC-0).

Prova que o nucleo (`todo_lib.parse_table` e `set_status_cell`) e genuinamente
agnostico a projeto: outra lingua (ingles), dois esquemas de ID (`#NN` e
`XYZ.9.9`), outra estrutura de secoes -- nada aqui se parece com um TODO.md do
autor. Os fixtures moram em `tests/corpus/*.md`, um arquivo por conteudo:

  clean.md                              -- tabela valida, zero defeito (controle
                                            negativo: prova ausencia de falso
                                            positivo).
  defeito_id_duplicado.md               -- ID repetido com dois status
                                            diferentes (revela BUG-1', xfail).
  defeito_pipe_cru_nao_escapado.md      -- `|` cru dentro de uma celula: a
                                            linha vira "celula a mais" e o
                                            nucleo a descarta em silencio (por
                                            desenho -- ver ADR-1 secao b.5).
  defeito_pipe_escapado_ok.md           -- o mesmo `|`, mas escapado como
                                            `\\|`: DEVE parsear normalmente
                                            (controle positivo).
  defeito_fragmento_truncado.md         -- linha com celulas faltando (arquivo
                                            cortado no meio): mesma politica de
                                            descarte silencioso do nucleo.
  defeito_tabela_fragmentada.md         -- dois cabecalhos ID+Status em
                                            sequencia: o nucleo hoje encerra a
                                            tabela canonica no 1o cabecalho
                                            repetido (comportamento correto,
                                            mantido -- CHK-03 e quem reporta o
                                            fragmento, fora de escopo aqui).
  defeito_tabela_legada_8_colunas.md    -- tabela legada sem coluna `Onda`:
                                            precisa continuar sendo lida.
  defeito_crlf.md                       -- terminador CRLF byte-exato.
  defeito_bom.md                        -- BOM UTF-8 na 1a linha.
  defeito_sprawl.md                     -- tabela canonica seguida de heading
                                            markdown + uma 2a tabela de 9
                                            celulas sem colunas ID/Status:
                                            SPRAWL-1 consertado (D-12) -- o
                                            nucleo agora encerra a canonica ao
                                            detectar o comeco da tabela alheia,
                                            mesmo com nº de colunas coincidindo
                                            por acaso.

Os testes que revelam bug real do nucleo NAO consertam `tools/` -- ficam
`xfail` citando o item do TODO.md que vai consertar (regra da fatia CORP-0).
"""
import os
import random

import pytest

import todo_lib as L

CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _read(name):
    path = os.path.join(CORPUS_DIR, name)
    with open(path, encoding="utf-8", newline="") as fh:  # byte-exato: sem
        return fh.read()                                   # normalizar EOL


def _read_bytes(name):
    with open(os.path.join(CORPUS_DIR, name), "rb") as fh:
        return fh.read()


# ============================================================================
# 1. Corpus limpo -- controle negativo (zero falso positivo)
# ============================================================================

def test_clean_sem_falso_positivo():
    text = _read("clean.md")
    tbl = L.parse_table(text)
    assert tbl is not None
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#02", "#03", "#04", "#05", "#06", "#07"]
    assert tbl["ncols"] == 9
    # as 7 celulas de status cobrem o vocabulario inteiro, uma vez cada
    statuses = {it["status"] for it in tbl["items"]}
    assert statuses == {
        "✅ Concluído", "🔄 Em andamento", "🟡 Parcial", "⏳ Pendente",
        "💡 Decisão tomada", "🎨 Pendente design", "🔍 Pendente verificação",
    }
    # round-trip byte-exato antes de qualquer set_status_cell
    assert "\n".join(tbl["lines"]) == text


# ============================================================================
# 2. Defeitos isolados, um por arquivo
# ============================================================================

def test_id_duplicado_aparece_duas_vezes_no_parse_table():
    """parse_table em si NAO perde a duplicata -- items conserva as 2 linhas."""
    text = _read("defeito_id_duplicado.md")
    tbl = L.parse_table(text)
    dup = [it for it in tbl["items"] if it["id"] == "OPS.1.1"]
    assert len(dup) == 2
    assert {d["status"] for d in dup} == {"⏳ Pendente", "✅ Concluído"}
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["OPS.1.1", "OPS.1.2", "OPS.1.1", "OPS.1.3"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG-1' (TODO.md): 'by_id = {it[\"id\"]: it for it in tbl[\"items\"]}' "
        "em todo_sync.py:137 (e o dict comprehension equivalente atras de "
        "parse_status_map) deixa a ULTIMA linha de um ID duplicado vencer em "
        "silencio, perdendo a primeira ocorrencia sem nenhum aviso. Este teste "
        "documenta o comportamento CORRETO (preservar a 1a ocorrencia, ou ao "
        "menos nao a descartar silenciosamente) e falha hoje de proposito -- "
        "vira xpass quando BUG-1' for consertado."
    ),
)
def test_id_duplicado_nao_deveria_desaparecer_em_silencio_do_status_map():
    text = _read("defeito_id_duplicado.md")
    status_map = L.parse_status_map(text)
    tbl = L.parse_table(text)
    primeira_ocorrencia = next(
        it for it in tbl["items"] if it["id"] == "OPS.1.1")
    assert status_map["OPS.1.1"] == primeira_ocorrencia["status"]


def test_pipe_cru_nao_escapado_derruba_a_linha_em_silencio():
    """Comportamento ATUAL e por desenho (ADR-1 b.5): o nucleo descarta a
    linha malformada sem travar e sem escrever no lugar errado. A causa fica
    invisivel aqui de proposito -- expo-la e trabalho do futuro CHK-02/
    AUDIT-ENG, que ainda nao existe neste repo."""
    text = _read("defeito_pipe_cru_nao_escapado.md")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#03"]           # #02 (pipe cru) some, sem travar
    assert "\n".join(tbl["lines"]) == text  # nada foi corrompido no processo


def test_pipe_escapado_e_controle_positivo_parseia_normal():
    text = _read("defeito_pipe_escapado_ok.md")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#02"]
    it01 = next(i for i in tbl["items"] if i["id"] == "#01")
    line = tbl["lines"][it01["line_no"]]
    cells = L._cells(line)
    assert len(cells) == 9
    assert "\\|" in cells[3]               # pipe escapado sobrevive intacto


def test_fragmento_truncado_e_descartado_sem_derrubar_vizinhos():
    text = _read("defeito_fragmento_truncado.md")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#03"]           # #02 truncado nao aparece
    assert "\n".join(tbl["lines"]) == text


def test_tabela_fragmentada_encerra_no_1o_cabecalho_repetido():
    """Comportamento ATUAL e mantido (nao e bug): o nucleo para no 2o
    cabecalho ID+Status. Fechar o gap de deteccao do fragmento (relatar o
    span) e trabalho do futuro CHK-03/AUDIT-ENG, fora do nucleo."""
    text = _read("defeito_tabela_fragmentada.md")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#02"]           # a 2a metade (#03, #04) fica de fora


def test_tabela_legada_8_colunas_continua_legivel():
    text = _read("defeito_tabela_legada_8_colunas.md")
    tbl = L.parse_table(text)
    assert tbl["ncols"] == 8
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#02"]
    assert tbl["status_idx"] == 6
    # round-trip byte-exato tambem vale para o esquema legado
    assert "\n".join(tbl["lines"]) == text


def test_crlf_preservado_byte_exato():
    raw = _read_bytes("defeito_crlf.md")
    text = raw.decode("utf-8")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#02"]
    assert "\n".join(tbl["lines"]) == text
    # aplica set_status_cell no 2o item e confere que so aquela celula mudou
    it02 = next(i for i in tbl["items"] if i["id"] == "#02")
    lines = list(tbl["lines"])
    lines[it02["line_no"]] = L.set_status_cell(
        lines[it02["line_no"]], tbl["status_idx"], "🔍 Pendente verificação")
    novo_texto = "\n".join(lines)
    assert novo_texto.encode("utf-8").count(b"\r\n") == raw.count(b"\r\n")
    assert "🔍 Pendente verificação" in novo_texto
    assert "Ship the Windows build" in novo_texto  # #01 byte-intacto


def test_bom_tolerado_na_primeira_linha():
    raw = _read_bytes("defeito_bom.md")
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["REL.1.1", "REL.1.2"]
    assert "\n".join(tbl["lines"]) == text     # BOM preservado no round-trip


def test_sprawl_nao_engole_mais_a_tabela_de_outra_secao():
    """SPRAWL-1 consertado, sob a regra revisada D-12 (decisoes_lider.md):
    a tabela canonica encerra ao encontrar o comeco de uma tabela de OUTRO
    schema (aqui, "Metric/Baseline/Target/..." depois do heading "##
    Appendix"), mesmo com o nº de colunas coincidindo por acaso com o da
    canonica -- esse e o caso perigoso de verdade (linhas contadas como
    itens fantasmas se nao fosse detectado). Promovido de xfail(strict) para
    teste normal: XPASS confirmado e investigado (nao e falso sinal -- a
    contagem 116/215 das fixtures reais do CONTR-1 nao mudou, e o heading
    por si so NUNCA encerra -- so a estrutura de tabela alheia que segue)."""
    text = _read("defeito_sprawl.md")
    tbl = L.parse_table(text)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["#01", "#02", "#03"]


def test_parse_table_agora_expoe_malformed():
    """AUDIT-ENG/CHK-CORE, ADR-0001 (b).5: a chave ADITIVA 'malformed'
    (lista de {line_no, raw, expected_ncols, got_ncols}) nasceu em
    todo_lib.py -- toda linha descartada por celula a mais/a menos passa a
    deixar rastro. Promovido de xfail(strict) para teste normal: XPASS
    confirmado e investigado, nao falso sinal."""
    text = _read("defeito_pipe_cru_nao_escapado.md") + _read(
        "defeito_fragmento_truncado.md")
    tbl = L.parse_table(text)
    assert "malformed" in tbl
    assert len(tbl["malformed"]) >= 1


# ============================================================================
# 3. Property-based (a mao, sem hypothesis -- projeto e stdlib puro + pytest)
# ============================================================================
#
# Gerador deterministico: random.Random(seed) produz tabelas validas variando
# esquema de ID (#NN | XYZ.N.N), lingua da Descricao (ingles | uma 2a lingua
# latina generica), numero de colunas (8 | 9), terminador de linha (LF |
# CRLF) e presenca de BOM. Para cada tabela gerada:
#   - round-trip byte-exato ("\n".join(parse_table(text)["lines"]) == text);
#   - nº de itens parseados == nº de itens gerados;
#   - status lido de cada item == status escrito;
#   - nenhum ID valido gerado e perdido -- nem antes nem depois de reescrever
#     TODAS as celulas de Status via set_status_cell.

CANON_STATUSES = [
    "✅ Concluído", "🔄 Em andamento", "🟡 Parcial", "⏳ Pendente",
    "💡 Decisão tomada", "🎨 Pendente design", "🔍 Pendente verificação",
]

EN_DESCRIPTIONS = [
    "Ship release candidate {n}",
    "Refactor the payment gateway adapter",
    "Investigate a flaky checkout test",
    "Draft the incident postmortem",
    "Rotate the staging credentials",
]

# segunda "lingua": rotulos tecnicos genericos, deliberadamente NAO pt-br,
# so para exercitar a variacao de idioma que o AC-0 exige.
ALT_DESCRIPTIONS = [
    "Kalibriere den Sensor-Treiber neu ({n})",
    "Verifica la cola de mensajes pendientes",
    "Mettre a jour le pilote reseau",
    "Aggiorna la libreria di crittografia",
]

DOTTED_PREFIXES = ("XYZ", "ABC", "OPS", "REL")

N_CASES = 300
MASTER_SEED = 20260728


def _gen_id(scheme, rng, seq):
    if scheme == "hash":
        return f"#{seq:02d}"
    prefix = rng.choice(DOTTED_PREFIXES)
    return f"{prefix}.{rng.randint(1, 9)}.{seq}"


def _generate_table(rng):
    ncols = rng.choice((8, 9))
    n_items = rng.randint(3, 9)
    eol = rng.choice(("\n", "\r\n"))
    use_bom = rng.choice((True, False))
    id_scheme = rng.choice(("hash", "dotted"))
    descriptions = rng.choice((EN_DESCRIPTIONS, ALT_DESCRIPTIONS))

    if ncols == 9:
        header = ["ID", "Wave", "Group", "Description", "Priority",
                  "Blocked By", "Effort", "Status", "Reviewed"]
    else:
        header = ["ID", "Group", "Description", "Priority",
                  "Blocked By", "Effort", "Status", "Reviewed"]
    sep = [":---"] * ncols

    seen_ids = set()
    rows = []
    expected = []
    seq = 1
    while len(rows) < n_items:
        iid = _gen_id(id_scheme, rng, seq)
        seq += 1
        if iid in seen_ids:
            continue                       # descarta colisao, tenta o proximo
        seen_ids.add(iid)
        status = rng.choice(CANON_STATUSES)
        desc = rng.choice(descriptions).format(n=seq)
        if ncols == 9:
            cells = [iid, f"W{rng.randint(1, 5)}", "Team", desc, "Alta",
                     "-", "Media", status, "-"]
        else:
            cells = [iid, "Team", desc, "Alta", "-", "Media", status, "-"]
        rows.append("| " + " | ".join(cells) + " |")
        expected.append({"id": iid, "status": status})

    header_line = "| " + " | ".join(header) + " |"
    sep_line = "| " + " | ".join(sep) + " |"
    lines = [header_line, sep_line, *rows]
    text = eol.join(lines) + eol
    if use_bom:
        text = L.BOM + text
    return text, expected


def test_property_based_corpus_sintetico():
    master = random.Random(MASTER_SEED)
    for case_idx in range(N_CASES):
        seed = master.randrange(2 ** 32)
        rng = random.Random(seed)
        text, expected = _generate_table(rng)
        ctx = f"seed={seed} case={case_idx}"

        tbl = L.parse_table(text)
        assert tbl is not None, ctx
        # round-trip byte-exato ANTES de qualquer set_status_cell
        assert "\n".join(tbl["lines"]) == text, ctx

        exp_ids = {e["id"] for e in expected}
        got_ids = {it["id"] for it in tbl["items"]}
        assert got_ids == exp_ids, ctx                    # nenhum ID perdido
        assert len(tbl["items"]) == len(expected), ctx    # nenhum item a mais

        exp_status_by_id = {e["id"]: e["status"] for e in expected}
        for it in tbl["items"]:
            assert it["status"] == exp_status_by_id[it["id"]], ctx

        # reescreve TODAS as celulas de Status e reconfere round-trip + leitura
        lines = list(tbl["lines"])
        new_status_by_id = {}
        for it in tbl["items"]:
            pool = [s for s in CANON_STATUSES if s != it["status"]]
            new_status = rng.choice(pool)
            new_status_by_id[it["id"]] = new_status
            lines[it["line_no"]] = L.set_status_cell(
                lines[it["line_no"]], tbl["status_idx"], new_status)
        new_text = "\n".join(lines)

        eol = "\r\n" if "\r\n" in text else "\n"
        assert new_text.count(eol) == text.count(eol), ctx  # EOL preservado
        if text.startswith(L.BOM):
            assert new_text.startswith(L.BOM), ctx

        tbl2 = L.parse_table(new_text)
        assert tbl2 is not None, ctx
        got_ids2 = {it["id"] for it in tbl2["items"]}
        assert got_ids2 == exp_ids, ctx
        for it in tbl2["items"]:
            assert it["status"] == new_status_by_id[it["id"]], ctx
