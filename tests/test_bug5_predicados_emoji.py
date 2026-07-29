"""tests/test_bug5_predicados_emoji.py -- BUG-5 (+ SUB-1, SUB-2): predicados de
status classificam pelo EMOJI-PREFIXO da celula (D-1, decisoes_lider.md), nao
por substring crua no texto livre que vem depois do emoji. Fallback
substring/word-boundary so para tabela LEGADA sem nenhum dos 7 emojis
(ADR-0001 secao (d)).

Os 4 casos abaixo sao os falsos-positivo/negativo confirmados em
`python3 -c` antes do conserto (colados no relatorio da fatia):

  1. is_awaiting_verification('✅ Concluído ... VERIFICADO ...') == True
     (deveria ser False -- o emoji ✅ ja diz que esta pronto).
  2. is_done('inconclusivo') == True (deveria ser False -- 'conclu' e
     substring de 'inconclusivo').
  3. is_pending('🔴 Bloqueado (dependente de X)') == True (deveria ser False
     -- 'pendente' e substring de 'dependente').
  4. is_flip_eligible('⏳ Pendente (verificar disponibilidade)') == False
     (deveria ser True -- o emoji ⏳ ja diz que e elegivel; 'verificar' no
     texto livre nao pode bloquear o flip).
"""
import todo_lib as L


def test_bug5_verificado_no_texto_livre_nao_bloqueia_classificacao_done():
    # Caso 1: emoji ✅ (done) com a palavra "VERIFICADO" livre na descricao.
    status = "✅ Concluído -- revisado e VERIFICADO em produção"
    assert L.is_done(status) is True
    assert L.is_awaiting_verification(status) is False


def test_bug5_inconclusivo_nao_e_done_substring_de_conclu():
    # Caso 2: "conclu" e substring crua de "inconclusivo".
    assert L.is_done("inconclusivo") is False


def test_bug5_dependente_nao_e_pending_substring_de_pendente():
    # Caso 3 (SUB-1): "pendente" e substring crua de "dependente"; o emoji
    # 🔴 nao faz parte do vocabulario dos 7 status (nao e reconhecido), logo
    # cai no fallback, que tem de usar fronteira de palavra.
    assert L.is_pending("🔴 Bloqueado (dependente de X)") is False


def test_bug5_pendente_com_verificar_no_texto_e_flip_eligivel():
    # Caso 4 (SUB-2): emoji ⏳ (pendente) com a palavra "verificar" livre na
    # descricao nao pode bloquear o flip -- a classificacao e pelo emoji, nao
    # pela substring do texto que vem depois.
    assert L.is_flip_eligible("⏳ Pendente (verificar disponibilidade)") is True


def test_bug5_fallback_tabela_legada_sem_emoji_continua_funcionando():
    # Tabela legada sem NENHUM dos 7 emojis: o fallback substring/word-
    # boundary do ADR-0001 (d) precisa continuar reconhecendo o vocabulario
    # de texto puro (comportamento pre-existente preservado), corrigindo
    # so os falsos-positivo de substring crua (dependente/inconclusivo).
    assert L.is_pending("Pendente") is True
    assert L.is_pending("Em andamento") is True
    assert L.is_pending("Dependente de outro item") is False       # nao substring crua
    assert L.is_flip_eligible("Pendente") is True
    # 2026-07-29 (PRED-FALLBACK): expectativa TROCADA de False para True.
    # O fallback antigo bloqueava o flip so por 'verifica' aparecer em
    # QUALQUER lugar do texto livre, um falso-negativo medido pela sessao
    # de um consumidor (relato interno, prompt_fallback_legado.md) -- e o
    # mesmo fallback deixava
    # 'Concluído e verificado' com is_done() e is_awaiting_verification()
    # ambos True ao mesmo tempo, incoerencia que motivou reabrir a decisao.
    # A nova regra (precedencia por POSICAO, ver test_pred_fallback_w15.py)
    # resolve os dois: aqui 'pendente'@0 vence 'verifica'@10 porque a
    # anotacao entre parenteses nao e o composto 'pendente verificacao'.
    assert L.is_flip_eligible("Pendente (verificar disponibilidade)") is True
    assert L.is_done("Concluído") is True
    assert L.is_done("Inconclusivo") is False
    assert L.is_awaiting_verification("Pendente verificação") is True


def test_bug5_emoji_nao_reconhecido_ainda_cai_no_fallback():
    # Emoji presente mas FORA do vocabulario fechado dos 7 (ex.: 🔴) tambem
    # e tratado como "sem emoji reconhecido" -- cai no mesmo fallback, nao
    # em um terceiro caminho.
    assert L.is_done("🔴 Bloqueado, já concluído por engano") is True
