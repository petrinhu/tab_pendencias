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


# ---------------------------------------------------------------------------
# CT-INBOX-PARSE (ADR-0002, secao f/j): inbox_items() nao pode confundir a
# INBOX de planejamento com um heading alheio que so contem a palavra
# "inbox" em prosa/mixed-case (ex.: "## Inbox do bus (mensagens
# recebidas)", TAB-BUS-003). Defeito medido no nucleo: `in_inbox = "inbox"
# in s.lower()` casava por substring, em qualquer caixa.
# ---------------------------------------------------------------------------

def test_inbox_items_nao_engole_heading_alheio_com_a_palavra_inbox():
    txt = (
        "# T\n"
        "## Inbox do bus (mensagens recebidas)\n"
        "- msg-1: mensagem de transporte, NAO e item de planejamento\n"
        "## INBOX (descobertas não priorizadas)\n"
        "- achou X: descricao real\n"
        "## Outra secao\n"
        "- nao conta\n"
    )
    assert L.inbox_items(txt) == ["achou X: descricao real"]


def test_inbox_items_heading_alheio_sozinho_nao_captura_nada():
    """Sem nenhuma INBOX de planejamento real no documento, nenhuma linha
    sob '## Inbox do bus (...)' pode vazar para o resultado -- prova de que
    a secao alheia nunca liga in_inbox=True, isolada do caso anterior."""
    txt = (
        "## Inbox do bus (mensagens recebidas)\n"
        "- msg-1: nao conta\n"
        "- msg-2: nao conta\n"
    )
    assert L.inbox_items(txt) == []


def test_inbox_items_token_precisa_ser_maiuscula_exata():
    """'inbox' minusculo ou 'Inbox' mixed-case nao sao o token de contrato
    (references/frescor-da-tabela.md SS5.1 usa literalmente 'INBOX' -- mesmo
    principio de 'ID'/'Status' como tokens de cabecalho nunca traduzidos,
    ADR-0001 secao d, mas aqui a caixa importa porque e o unico sinal que
    distingue o token do substantivo comum em prosa)."""
    txt = "## inbox (minusculo, nao e o token)\n- x: nao conta\n"
    assert L.inbox_items(txt) == []


# ---------------------------------------------------------------------------
# Metadado de item residual [triage ...] (ADR-0002 secao f)
# ---------------------------------------------------------------------------

def test_format_triage_metadata_roundtrip_minimo():
    meta = L.format_triage_metadata(since="2026-08-16", reason="needs-leader-decision")
    linha = meta + "descricao livre em qualquer lingua"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["present"] is True
    assert parsed["valid"] is True
    assert parsed["errors"] == []
    assert parsed["fields"] == {"since": "2026-08-16",
                                "reason": "needs-leader-decision"}
    assert parsed["description"] == "descricao livre em qualquer lingua"


def test_format_triage_metadata_roundtrip_completo():
    meta = L.format_triage_metadata(
        since="2026-08-16", reason="needs-leader-decision", source="agent",
        cycles=1, ref="FIX-ESCOPO-1")
    linha = meta + "descricao com : dois pontos tambem, sem quebrar o parser"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["valid"] is True
    assert parsed["fields"] == {
        "since": "2026-08-16", "reason": "needs-leader-decision",
        "source": "agent", "cycles": "1", "ref": "FIX-ESCOPO-1"}
    assert parsed["description"] == (
        "descricao com : dois pontos tambem, sem quebrar o parser")


def test_parse_triage_metadata_ausente_nunca_e_valido():
    """ADR-0002 (f): ausencia de token valido = classificavel por
    definicao -- 'valid' e SEMPRE False quando 'present' e False."""
    parsed = L.parse_triage_metadata("descricao qualquer sem metadado")
    assert parsed["present"] is False
    assert parsed["valid"] is False
    assert parsed["fields"] == {}
    assert parsed["description"] == "descricao qualquer sem metadado"


def test_parse_triage_metadata_reason_fora_do_vocabulario_e_invalido():
    linha = "[triage since=2026-08-16 reason=preguica] descricao"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["present"] is True
    assert parsed["valid"] is False
    assert any("reason" in e for e in parsed["errors"])


def test_parse_triage_metadata_chave_desconhecida_e_invalida():
    linha = "[triage since=2026-08-16 reason=missing-info urgencia=alta] descricao"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["valid"] is False
    assert any("desconhecida" in e for e in parsed["errors"])


def test_parse_triage_metadata_falta_chave_obrigatoria():
    linha = "[triage reason=missing-info] descricao"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["valid"] is False
    assert any("since" in e for e in parsed["errors"])


def test_parse_triage_metadata_since_fora_do_formato_iso():
    linha = "[triage since=16-08-2026 reason=missing-info] descricao"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["valid"] is False


def test_parse_triage_metadata_cycles_nao_inteiro_e_invalido():
    linha = "[triage since=2026-08-16 reason=missing-info cycles=um] descricao"
    parsed = L.parse_triage_metadata(linha)
    assert parsed["valid"] is False


def test_parse_triage_metadata_todos_os_7_reasons_do_vocabulario_sao_validos():
    for reason in sorted(L.TRIAGE_REASONS):
        linha = f"[triage since=2026-08-16 reason={reason}] descricao"
        parsed = L.parse_triage_metadata(linha)
        assert parsed["valid"], (reason, parsed["errors"])


# ---------------------------------------------------------------------------
# inbox_entries() -- inbox_items() decomposto com classificacao de triagem
# ---------------------------------------------------------------------------

def test_inbox_entries_linha_legada_sem_metadado_e_classificavel():
    txt = ("## INBOX (descobertas não priorizadas)\n"
           "- FIX-ESCOPO-1: descricao legada sem metadado\n")
    entries = L.inbox_entries(txt)
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == "FIX-ESCOPO-1"
    assert e["description"] == "descricao legada sem metadado"
    assert e["classifiable"] is True
    assert e["triage"]["present"] is False


def test_inbox_entries_residual_valido_nao_e_classificavel():
    meta = L.format_triage_metadata(since="2026-08-16",
                                    reason="needs-leader-decision",
                                    source="agent", cycles=0)
    txt = ("## INBOX (descobertas não priorizadas)\n"
           f"- SKILL-DESC-1: {meta}decisao pendente do lider\n")
    e = L.inbox_entries(txt)[0]
    assert e["classifiable"] is False
    assert e["triage"]["fields"]["reason"] == "needs-leader-decision"


def test_inbox_entries_metadado_malformado_e_classificavel():
    """ADR-0002 (f): metadado malformado (reason fora do vocabulario) NUNCA
    e descartado em silencio -- a linha e tratada como classificavel."""
    txt = ("## INBOX (descobertas não priorizadas)\n"
           "- X-1: [triage since=2026-08-16 reason=nao-existe] descricao\n")
    e = L.inbox_entries(txt)[0]
    assert e["classifiable"] is True
    assert e["triage"]["present"] is True
    assert e["triage"]["valid"] is False


def test_inbox_entries_linha_sem_dois_pontos_tem_id_none_e_e_classificavel():
    txt = "## INBOX (descobertas não priorizadas)\n- descricao sem id nem dois pontos\n"
    e = L.inbox_entries(txt)[0]
    assert e["id"] is None
    assert e["classifiable"] is True


def test_inbox_entries_raw_preserva_texto_integral_igual_a_inbox_items():
    txt = ("## INBOX (descobertas não priorizadas)\n"
           "- achei bug X\n- falta Y\n")
    items = L.inbox_items(txt)
    entries = L.inbox_entries(txt)
    assert [e["raw"] for e in entries] == items
