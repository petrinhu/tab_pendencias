"""tests/test_sprawl1_w5.py -- SPRAWL-1 (W5), sob a regra REVISADA D-12
(decisoes_lider.md): a D-6 original ("encerra no proximo heading markdown",
QUALQUER nivel) destruia 201 dos 215 itens de um consumidor real que
organiza a MESMA tabela canonica sob ~20 subtitulos -- recriando o incidente
fundador do projeto ("93% de tabela invisivel") por outro caminho.

D-12: a tabela canonica ATRAVESSA um heading quando o que vem depois e
CONTINUACAO da mesma tabela (nenhum novo cabecalho ID+Status, e nenhuma
tabela de OUTRO schema comeca ali); ela ENCERRA quando aparece: (a) um 2o
cabecalho ID+Status (regra antiga, mantida), ou (b) uma tabela de schema
DIFERENTE (header+separador reconheciveis, sem coluna id+status, mesmo
quando o nº de colunas COINCIDE por acaso com o da canonica -- o caso real
do SPRAWL-1 original: `defeito_sprawl.md`), ou (c) fim do documento.

O heading em si NUNCA encerra a tabela -- so a ESTRUTURA de tabela que vem
depois dele (ou em qualquer outro ponto do arquivo) decide. Isso e o que
permite atravessar headings de organizacao visual (consumidor B real) sem
reabrir a porta para engolir uma tabela alheia que so colide em nº de
colunas (o bug original)."""
import todo_lib as L


def test_d12_atravessa_heading_quando_o_que_vem_depois_e_a_mesma_tabela():
    text = """| ID | Status |
| :- | :- |
| A-1 | ⏳ Pendente |

## Secao de organizacao visual (nao e fim de tabela)

| A-2 | ✅ Concluído |
| A-3 | 🔍 Pendente verificação |
"""
    t = L.parse_table(text)
    assert [it["id"] for it in t["items"]] == ["A-1", "A-2", "A-3"]


def test_d12_atravessa_varios_headings_de_niveis_diferentes():
    text = """| ID | Status |
| :- | :- |
| A-1 | ⏳ Pendente |

## Nivel 2

### Nivel 3

#### Nivel 4

| A-2 | ⏳ Pendente |
"""
    t = L.parse_table(text)
    assert [it["id"] for it in t["items"]] == ["A-1", "A-2"]


def test_d12_atravessa_tabela_de_schema_diferente_com_ncols_nao_coincidente():
    # Consumidor B real: apos um heading, uma mini-tabela de 2 colunas (sem
    # Status) aparece -- nao colide em ncols com a canonica (aqui 3), entao
    # suas linhas sao ignoradas pela guarda de ncols de sempre, SEM encerrar
    # a canonica -- a tabela continua depois dela.
    text = """| ID | Onda | Status |
| :- | :- | :- |
| A-1 | W1 | ⏳ Pendente |

### Bloqueados (tabela de outro schema, 2 colunas)

| ID | Por que espera |
| :- | :- |
| X | motivo |
| Y | outro motivo |

### Retomando a tabela canonica

| A-2 | W1 | ✅ Concluído |
"""
    t = L.parse_table(text)
    assert [it["id"] for it in t["items"]] == ["A-1", "A-2"]


def test_d12_encerra_ao_encontrar_tabela_de_schema_diferente_com_ncols_coincidente():
    # O SPRAWL-1 original de verdade: uma tabela ALHEIA que por acaso tem o
    # MESMO numero de colunas da canonica (sem ser header ID+Status) e a
    # unica coisa que ainda deve encerrar a canonica -- e o caso perigoso
    # (linhas contadas como itens fantasmas se nao for detectado).
    text = """| ID | Status |
| :- | :- |
| A-1 | ⏳ Pendente |

## Apendice de outra tabela (mesmo nº de colunas, schema diferente)

| Metric | Target |
| :- | :- |
| Throughput | 150 |
| Latency | 60 |
"""
    t = L.parse_table(text)
    assert [it["id"] for it in t["items"]] == ["A-1"]


def test_d12_segundo_cabecalho_id_status_continua_encerrando():
    text = """| ID | Status |
| :- | :- |
| A-1 | ⏳ Pendente |
| ID | Status |
| :- | :- |
| B-1 | ⏳ Pendente |
"""
    t = L.parse_table(text)
    assert [it["id"] for it in t["items"]] == ["A-1"]


def test_d12_titulo_antes_do_primeiro_cabecalho_nao_encerra_nada():
    text = """# TODO -- projeto X

> nota qualquer

| ID | Status |
| :- | :- |
| A-1 | ⏳ Pendente |
"""
    t = L.parse_table(text)
    assert [it["id"] for it in t["items"]] == ["A-1"]


def test_d12_expoe_headings_cruzados_para_o_futuro_audit_chk03():
    text = """| ID | Status |
| :- | :- |
| A-1 | ⏳ Pendente |

## Secao 1

### Sub 1

| A-2 | ⏳ Pendente |
"""
    t = L.parse_table(text)
    assert "headings_crossed" in t
    assert [h["line_no"] for h in t["headings_crossed"]] == [4, 6]
    assert t["headings_crossed"][0]["text"] == "## Secao 1"


def test_d12_headings_crossed_vazio_quando_tabela_nao_atravessa_nenhum():
    t = L.parse_table("| ID | Status |\n| :- | :- |\n| A-1 | ⏳ Pendente |\n")
    assert t["headings_crossed"] == []
