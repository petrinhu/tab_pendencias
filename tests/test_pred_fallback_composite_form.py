"""tests/test_pred_fallback_composite_form.py -- GEMEO-DESIGN (2026-08-16):
forma de separacao entre radical e qualificador no composto do fallback
legado (achado por comparacao comportamental produto x toolkit anterior,
is_flip_eligible, 4 divergencias reproduzidas -- ver brief da fatia).

O composto PRED-FALLBACK (W15, d5f34c0) so reconhecia a forma adjacente
exata "pendente\\s+design" (radical fixo "pendente", separador so espaco).
Isso deixava passar, em silencio, para is_flip_eligible():

  - separador hifen:              "Pendente-design"
  - palavra intercalada:          "Pendente depois design"
  - radical "andamento" (nao so "pendente"):
      "andamento design", "andamento depois design", "Em andamento design"

D-1 e absoluto: 🎨 Pendente design NUNCA e flip-eligible, independente de
COMO a tabela legada escreveu o composto. O mesmo defeito de FORMA (nao de
vocabulario) tem gemeo simetrico no outro composto do contrato, "Pendente
verificação" -- por isso a mesma matriz (radical x separador x caixa) e
coberta para os dois qualificadores, com o radical variando entre
"pendente" e "andamento".

Conserto: a decisao passa a ser por CO-OCORRENCIA (radical em qualquer
posicao/forma + qualificador em qualquer posicao/forma), nao por adjacencia
regex -- exceto para o qualificador "verifica", que preserva a exclusao do
infinitivo "verificar" (verbo em nota livre, ex.: "Pendente (verificar
disponibilidade)"), squad guardada pelos testes de regressao no fim deste
arquivo E pelos 6 testes originais de tests/test_pred_fallback_w15.py.
"""
import todo_lib as L


# ---------------------------------------------------------------------------
# Matriz: radical x separador x qualificador "design", forma "normal"
# (radical antes do qualificador -- a ordem em que a tabela legada realmente
# escreve, ex.: "Pendente - design" nunca "Design - pendente").
# ---------------------------------------------------------------------------

_DESIGN_CASES = [
    "Pendente-design",
    "Pendente - design",
    "Pendente  design",              # multiplos espacos
    "Pendente depois design",        # palavra intercalada
    "Em andamento design",           # radical "andamento", separador espaco
    "Em andamento-design",           # radical "andamento", separador hifen
    "Em andamento   design",         # radical "andamento", multiplos espacos
    "Em andamento depois design",    # radical "andamento", palavra intercalada
    "andamento design",              # radical "andamento" sem "Em"
    "andamento-design",
    "andamento depois design",
]


def test_design_nao_flipa_qualquer_forma_de_separador_ou_radical():
    for status in _DESIGN_CASES:
        assert L.is_flip_eligible(status) is False, status
        assert L.is_pending(status) is True, status   # design ainda conta como nao-entregue


def test_design_nao_flipa_case_insensitive():
    for status in _DESIGN_CASES:
        assert L.is_flip_eligible(status.upper()) is False, status.upper()
        assert L.is_flip_eligible(status.lower()) is False, status.lower()


# ---------------------------------------------------------------------------
# Mesma matriz para o outro composto do contrato: "Pendente verificação".
# ---------------------------------------------------------------------------

_VERIF_CASES = [
    "Pendente-verificação",
    "Pendente - verificação",
    "Pendente  verificação",
    "Pendente depois verificação",
    "Em andamento verificação",
    "Em andamento-verificação",
    "Em andamento   verificação",
    "Em andamento depois verificação",
    "andamento verificação",
    "andamento-verificação",
    "andamento depois verificação",
    # sem acento (Windows/copy-paste legado, ADR-0001 (d))
    "Pendente-verificacao",
    "andamento depois verificacao",
]


def test_verificacao_nao_flipa_e_e_reconhecida_qualquer_forma():
    for status in _VERIF_CASES:
        assert L.is_flip_eligible(status) is False, status
        assert L.is_awaiting_verification(status) is True, status
        assert L.is_pending(status) is False, status  # ja entregue, aguardando -- nao "pendente"


def test_verificacao_nao_flipa_case_insensitive():
    for status in _VERIF_CASES:
        assert L.is_flip_eligible(status.upper()) is False, status.upper()
        assert L.is_flip_eligible(status.lower()) is False, status.lower()


# ---------------------------------------------------------------------------
# Guarda de regressao: o achado NAO pode reverter os 6 testes W15 que dependem
# de "verificar" (infinitivo, nota livre) cair na regra de posicao -- nunca no
# composto. Repetidos aqui, explicitos, para que uma regressao aponte
# exatamente para este arquivo tambem (nao so para test_pred_fallback_w15.py).
# ---------------------------------------------------------------------------

def test_regressao_verificar_infinitivo_em_nota_livre_continua_flipavel():
    assert L.is_flip_eligible("Pendente (verificar disponibilidade)") is True
    assert L.is_flip_eligible("Em andamento (verificar com o time)") is True


def test_regressao_so_verbo_nao_classifica():
    # VERB-STATUS-2: infinitivo sozinho nao e vocabulario canonico.
    assert L.is_awaiting_verification("A verificar") is False
    assert L.is_awaiting_verification("Verificar disponibilidade") is False
    assert L.status_classification_via("Verificar disponibilidade") == "unknown"


def test_regressao_concluido_e_verificado_continua_coerente():
    # 'conclu'@0 continua vencendo 'verifica'@N por posicao -- nenhum radical
    # (pendente/andamento) presente aqui, entao a co-ocorrencia nao dispara.
    assert L.is_done("Concluído e verificado") is True
    assert L.is_awaiting_verification("Concluído e verificado") is False
