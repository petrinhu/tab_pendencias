import todo_freshness as t


TODO_9COL = """# Projeto

| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| V-01 | W1 | Core | Fundação | Alta | — | Média | ✅ Concluído | ✓ |
| V-12 | W2 | Auth | Login OAuth | Alta | V-01 | Média | ⏳ Pendente | — |
| V-13 | W2 | Auth | Refresh token | Média | V-01 | Baixa | 🔄 Em andamento | — |
| V-14 | W3 | UI | Tela de perfil | Baixa | V-12 | Baixa | 🔍 Pendente verificação | — |
"""

TODO_8COL = """| ID | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ORG-3 | Infra | Setup CI | Alta | — | Média | ⏳ Pendente | — |
"""


# ------------------------------- parse ---------------------------------------

def test_parse_9col():
    items = t.parse_todo(TODO_9COL)
    assert items["V-01"].startswith("✅")
    assert "Pendente" in items["V-12"]
    assert items["V-14"] == "🔍 Pendente verificação"
    assert "—" not in items  # placeholder de pre-requisito nao vira item


def test_parse_8col_legado():
    items = t.parse_todo(TODO_8COL)
    assert "ORG-3" in items and "Pendente" in items["ORG-3"]


def test_parse_sem_tabela():
    assert t.parse_todo("# So texto, sem tabela\n") == {}


# ------------------------------- is_pending ----------------------------------

def test_is_pending_distingue_verificacao():
    assert t.is_pending("⏳ Pendente") is True
    assert t.is_pending("🔄 Em andamento") is True
    assert t.is_pending("🔍 Pendente verificação") is False   # ja entregue
    assert t.is_pending("✅ Concluído") is False
    assert t.is_pending("🎨 Pendente design") is True  # ainda nao entregue


# ------------------------------- cited_ids -----------------------------------

def test_cited_ids_fronteira():
    ids = ["V-1", "V-12", "F1.4"]
    assert set(t.cited_ids("fecha V-12 e F1.4", ids)) == {"V-12", "F1.4"}
    # V-1 NAO casa dentro de V-12; F1.4 NAO casa em F1.45
    assert t.cited_ids("trabalho em V-120", ids) == []
    assert t.cited_ids("rev F1.45", ids) == []
    assert t.cited_ids("so V-1 aqui", ids) == ["V-1"]


# ------------------------------- touched_code --------------------------------

def test_touched_code():
    assert t.touched_code(["src/auth.py"]) is True
    assert t.touched_code(["TODO.md"]) is False
    assert t.touched_code(["inbox/2026-06-20-x.md"]) is False
    assert t.touched_code(["TODO.md", "src/x.py"]) is True


# ------------------------------- build_warnings ------------------------------

def test_warn_codigo_sem_id():
    items = t.parse_todo(TODO_9COL)
    warns, cited = t.build_warnings("feat: login", ["src/auth.py"], items)
    assert cited == []
    assert len(warns) == 1 and "nao citou" in warns[0]


def test_warn_cita_id_pendente():
    items = t.parse_todo(TODO_9COL)
    warns, cited = t.build_warnings("feat: login V-12", ["src/auth.py"], items)
    assert cited == ["V-12"]
    assert len(warns) == 1 and "V-12" in warns[0] and "Status" in warns[0]


def test_sem_warn_quando_id_ja_entregue():
    items = t.parse_todo(TODO_9COL)
    # cita V-14 que ja esta em "Pendente verificação" -> nada a avisar
    warns, cited = t.build_warnings("polish V-14", ["src/perfil.py"], items)
    assert cited == ["V-14"] and warns == []


def test_sem_warn_em_commit_so_de_bookkeeping():
    items = t.parse_todo(TODO_9COL)
    warns, cited = t.build_warnings("chore: marca status", ["TODO.md"], items)
    assert warns == []  # so tocou TODO.md, nao avisa nada


def test_silencioso_quando_cita_e_status_ok():
    items = t.parse_todo(TODO_9COL)
    warns, _ = t.build_warnings("done V-01", ["src/core.py"], items)
    assert warns == []  # V-01 ja Concluído -> nenhum aviso
