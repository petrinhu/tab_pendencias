"""tests/test_bug1_duplicado_w5.py -- BUG-1' (W5): ID duplicado passa em
silencio hoje. `parse_status_map` deixa a ULTIMA linha vencer
(`todo_lib.py:178`) e nenhum teste detectava a instancia (ja removida do
dado real; a CLASSE seguia aberta).

Politica (ADR-0001 (b).5, mesma estrategia da chave aditiva `malformed`): o
nucleo NAO TRAVA -- `parse_status_map`/`parse_table["items"]` continuam
exatamente como estao (o `--audit`/CHK-01 e quem decide o que fazer com a
duplicata). `parse_table` passa a expor, ADITIVAMENTE, a chave
`duplicate_ids`: {id: [{line_no, status}, ...]} SO para IDs com 2+
ocorrencias -- nenhum consumidor existente (todo_sync/todo_health/
todo_freshness, que so leem `items`/`id_idx`/`status_idx`/`ncols`/`lines`)
muda de comportamento."""
import todo_lib as L


TODO_DUP = """# P

| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :- | :- | :- | :- | :- | :- | :- | :- | :- |
| V-01 | W1 | Core | Fund | Alta | — | Média | ✅ Concluído | ✓ |
| V-12 | W2 | Auth | Login (1a linha) | Alta | V-01 | Média | ⏳ Pendente | — |
| V-14 | W3 | UI | Perfil | Baixa | V-12 | Baixa | 🔍 Pendente verificação | — |
| V-12 | W2 | Auth | Login (2a linha, duplicata) | Alta | V-01 | Média | ✅ Concluído | ✓ |
"""


def test_bug1_duplicate_ids_e_aditiva_e_vazia_quando_nao_ha_duplicata():
    t = L.parse_table("""| ID | Status |
| :- | :- |
| V-01 | ⏳ Pendente |
""")
    assert "duplicate_ids" in t
    assert t["duplicate_ids"] == {}


def test_bug1_duplicate_ids_lista_todas_as_ocorrencias_do_id_repetido():
    t = L.parse_table(TODO_DUP)
    assert set(t["duplicate_ids"].keys()) == {"V-12"}
    occs = t["duplicate_ids"]["V-12"]
    assert len(occs) == 2
    assert [o["status"] for o in occs] == ["⏳ Pendente", "✅ Concluído"]
    assert occs[0]["line_no"] < occs[1]["line_no"]


def test_bug1_items_continua_com_todas_as_linhas_sem_perder_nenhuma():
    # O nucleo NAO trava/filtra -- items preserva as 2 ocorrencias de V-12,
    # exatamente como hoje (nao e este teste que muda esse comportamento).
    t = L.parse_table(TODO_DUP)
    ids = [it["id"] for it in t["items"]]
    assert ids.count("V-12") == 2
    assert len(ids) == 4


def test_bug1_parse_status_map_continua_ultima_linha_vence_sem_travar():
    # Comportamento EXISTENTE preservado (ADR: nucleo nao trava por
    # duplicata) -- quem quer o rastro usa parse_table()["duplicate_ids"].
    m = L.parse_status_map(TODO_DUP)
    assert m["V-12"] == "✅ Concluído"
