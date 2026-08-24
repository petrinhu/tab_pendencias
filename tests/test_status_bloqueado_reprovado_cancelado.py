"""tests/test_status_bloqueado_reprovado_cancelado.py -- os 3 status novos
(ordem do lider, 2026-08-24): ⛔ Bloqueado, ❌ Reprovado, 🚫 Cancelado.

Cobre tres garantias do contrato:
  1. casam por emoji-prefixo (D-1) como os outros 7 kinds -- via
     `todo_lib.status_classification_via` == "emoji";
  2. NENHUM dos tres e `is_flip_eligible` -- nunca auto-avancam por sync
     mecanico (`todo_sync.py`);
  3. o CHK-08 nao os acusa mais (nao caem em "unknown", severidade
     IMPORTANTE) quando usados via emoji.

Tambem prova a decisao registrada de is_pending() ficar de fora nesta fatia,
e que o fallback textual legado NAO reconhece os tres por radical (celula
sem o emoji cai em "unknown", nao em "fallback").
"""
import todo_lib as L

_NOVOS = {
    "⛔ Bloqueado": "bloqueado",
    "❌ Reprovado": "reprovado",
    "🚫 Cancelado": "cancelado",
}


def test_emoji_kind_reconhece_os_3_novos():
    for status, kind in _NOVOS.items():
        assert L._status_kind(status) == kind


def test_classification_via_emoji_para_os_3_novos():
    for status in _NOVOS:
        assert L.status_classification_via(status) == "emoji"


def test_nenhum_dos_3_e_flip_eligible():
    for status in _NOVOS:
        assert L.is_flip_eligible(status) is False


def test_nenhum_dos_3_e_awaiting_verification_nem_done():
    for status in _NOVOS:
        assert L.is_awaiting_verification(status) is False
        assert L.is_done(status) is False


def test_texto_livre_apos_o_emoji_nao_muda_a_classificacao():
    # Mesma garantia BUG-5/SUB-1/SUB-2: o emoji decide, nao o texto livre
    # que vem depois (aqui incluindo notas que citam "pendente"/"verificar",
    # que sao substring das OUTRAS categorias).
    assert L._status_kind(
        "⛔ Bloqueado (pendente de autorizacao do lider, verificar amanha)"
    ) == "bloqueado"
    assert L._status_kind(
        "❌ Reprovado -- pendente de retrabalho, ver revisao adversarial"
    ) == "reprovado"
    assert L._status_kind(
        "🚫 Cancelado -- pendente nao, decidido nao fazer"
    ) == "cancelado"
    assert L.is_flip_eligible(
        "⛔ Bloqueado (pendente de autorizacao do lider, verificar amanha)"
    ) is False


def test_cancelado_usa_seu_proprio_emoji_nunca_o_de_reprovado():
    # O emoji de Cancelado e 🚫, NUNCA ❌ (❌ ja e Reprovado) -- decisao
    # explicita do lider por causa do casamento por emoji-prefixo.
    assert L._status_kind("❌ Cancelado") == "reprovado"
    assert L._status_kind("🚫 Cancelado") == "cancelado"


def test_is_pending_deliberadamente_nao_inclui_os_3_novos():
    # Decisao registrada (nao default silencioso): mudar is_pending() e
    # mudanca de contrato observavel para ~20 projetos consumidores, fica
    # para o lider decidir. Nesta fatia, nenhum dos 3 conta como pendencia.
    for status in _NOVOS:
        assert L.is_pending(status) is False


def test_fallback_textual_legado_nao_reconhece_bloqueado_nem_cancelado():
    # Decisao deliberada: sem o emoji, "bloqueado"/"cancelado" ficam
    # "unknown" (CHK-08 aponta), porque sao palavras comuns de nota livre
    # dentro de OUTRA celula de status (mesma classe de risco corrigida
    # para "verificar" por VERB-STATUS-2).
    assert L._classify_legacy("Bloqueado") is None
    assert L._classify_legacy("Cancelado") is None
    assert L._classify_legacy("Reprovado") is None
    assert L.status_classification_via("Bloqueado") == "unknown"
    assert L.status_classification_via("Cancelado") == "unknown"
    assert L.status_classification_via("Reprovado") == "unknown"


def test_emoji_desconhecido_nao_vira_um_dos_3_novos_por_engano():
    # 🔴 (fora do vocabulario controlado) continua "sem emoji reconhecido" --
    # nao vira um dos 3 novos por engano. Cai em "unknown", nao "fallback",
    # porque "bloqueado" nao ganhou radical no fallback textual (decisao
    # deliberada desta fatia, ver teste
    # test_fallback_textual_legado_nao_reconhece_bloqueado_nem_cancelado).
    assert L._status_kind("🔴 Bloqueado") is None
    assert L.status_classification_via("🔴 Bloqueado") == "unknown"
