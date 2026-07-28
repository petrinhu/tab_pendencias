import todo_lib as L


TODO_9 = """# P

| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :- | :- | :- | :- | :- | :- | :- | :- | :- |
| V-01 | W1 | Core | Fund | Alta | — | Média | ✅ Concluído | ✓ |
| V-12 | W2 | Auth | Login | Alta | V-01 | Média | ⏳ Pendente | — |
| V-14 | W3 | UI | Perfil | Baixa | V-12 | Baixa | 🔍 Pendente verificação | — |
"""

TODO_8 = """| ID | Grupo | Descrição | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :- | :- | :- | :- | :- | :- | :- | :- |
| ORG-3 | Infra | CI | Alta | — | Média | ⏳ Pendente | — |
"""


def test_parse_table_9col_indices_e_itens():
    t = L.parse_table(TODO_9)
    assert t["id_idx"] == 0 and t["status_idx"] == 7
    ids = [it["id"] for it in t["items"]]
    assert ids == ["V-01", "V-12", "V-14"]
    v12 = next(it for it in t["items"] if it["id"] == "V-12")
    assert "Pendente" in v12["status"] and isinstance(v12["line_no"], int)


def test_parse_table_8col_status_index():
    t = L.parse_table(TODO_8)
    assert t["status_idx"] == 6
    assert t["items"][0]["id"] == "ORG-3"


def test_parse_table_sem_tabela():
    assert L.parse_table("# nada\n texto") is None


TODO_MALFORMED = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
    "| V-01 | W1 | Core | Fund | Alta | — | Média | ✅ Concluído | ✓ |\n"
    "| V-02 | W1 | Core | Truncado | Alta\n"
    "| V-03 | W2 | Auth | Login | Alta | — | Média | ⏳ Pendente | — |\n"
)


def test_parse_table_expoe_malformed_para_linha_com_ncols_errado():
    """ADR-0001 (b).5: chave ADITIVA -- 'items'/'ncols'/etc. continuam
    exatamente como hoje (V-02 nao aparece em 'items', descartada pela
    guarda de ncols de sempre), mas a linha descartada agora deixa rastro
    em 'malformed' em vez de sumir em silencio."""
    t = L.parse_table(TODO_MALFORMED)
    ids = [it["id"] for it in t["items"]]
    assert ids == ["V-01", "V-03"]          # comportamento pre-existente mantido
    assert "malformed" in t
    assert len(t["malformed"]) == 1
    m = t["malformed"][0]
    assert m["line_no"] == 3                # 0-based, "V-02 | ... | Alta"
    assert m["expected_ncols"] == 9
    assert m["got_ncols"] == 5
    assert "V-02" in m["raw"]


def test_parse_table_malformed_vazio_quando_tabela_bem_formada():
    t = L.parse_table(TODO_9)
    assert t["malformed"] == []


def test_set_status_cell_preserva_resto_e_troca_so_status():
    t = L.parse_table(TODO_9)
    v12 = next(it for it in t["items"] if it["id"] == "V-12")
    line = t["lines"][v12["line_no"]]
    novo = L.set_status_cell(line, t["status_idx"], "🔍 Pendente verificação")
    # reparse a linha isolada como tabela de 1 dado nao da; checa por celulas:
    cells = [c.strip() for c in novo.strip().strip("|").split("|")]
    assert cells[0] == "V-12"                       # ID intacto
    assert cells[7] == "🔍 Pendente verificação"    # status trocado
    assert cells[8] == "—"                          # estado auditado intacto
    assert cells[3] == "Login"                      # descricao intacta


def test_set_status_cell_preserva_newline():
    assert L.set_status_cell("| a | ⏳ Pendente |\n", 1, "X").endswith("|\n")
    assert not L.set_status_cell("| a | ⏳ Pendente |", 1, "X").endswith("\n")


def test_predicados_de_status():
    assert L.is_pending("⏳ Pendente") and L.is_pending("🔄 Em andamento")
    assert not L.is_pending("🔍 Pendente verificação")
    assert L.is_awaiting_verification("🔍 Pendente verificação")
    assert L.is_done("✅ Concluído")
    assert not L.is_done("⏳ Pendente")


def test_cited_ids_fronteira():
    ids = ["V-1", "V-12", "F1.4"]
    assert set(L.cited_ids("fecha V-12 e F1.4", ids)) == {"V-12", "F1.4"}
    assert L.cited_ids("V-120", ids) == []
    assert L.cited_ids("F1.45", ids) == []


def test_inbox_items():
    txt = TODO_9 + "\n## INBOX (descobertas não priorizadas)\n- achei bug X\n- falta Y\n## Outra\n- nao conta\n"
    assert L.inbox_items(txt) == ["achei bug X", "falta Y"]
