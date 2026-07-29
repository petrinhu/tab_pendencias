"""tests/test_pred_fallback_w15.py -- PRED-FALLBACK (W15): precedencia por
POSICAO no fallback de tabela legada sem emoji (prompt_fallback_legado.md,
achado da sessão de um consumidor em 2026-07-29 ao comparar comportamentalmente este
`todo_lib.py` contra o toolkit anterior, 80 casos, 4 divergentes).

O fallback antigo decidia por "a celula CONTEM a palavra X?" (uma pergunta
por predicado, cada um checando seu proprio vocabulo). Isso produzia UMA
incoerencia grave -- 'Concluído e verificado' saia com is_done() == True E
is_awaiting_verification() == True ao mesmo tempo, dois dos 7 status
canonicos que sao mutuamente exclusivos por contrato -- e TRES falsos-
negativo (celulas legitimas que deveriam classificar mas nao classificavam
como esperado).

O conserto: uma UNICA funcao de decisao (`_classify_legacy`) devolve UMA
categoria por celula, com precedencia por POSICAO -- o vocabulario canonico
de MENOR indice na celula vence. Os compostos ('Pendente design', 'Pendente
verificacao') sao casados ANTES da regra de posicao, porque sao status
canonicos compostos, nao 'pendente' com anotacao livre; sem isso, por
posicao pura 'pendente' venceria e 'Pendente design' viraria flipavel --
ressuscitando o caso grave do BUG-5 no proprio fallback que o corrigiu.
"""
import todo_lib as L


def test_predfallback_pendente_com_verificar_no_texto_agora_e_flipavel():
    # Divergente 1 (doc secao 1): 'pendente'@0 vence 'verifica'@10 por
    # posicao -- a anotacao entre parenteses NAO e o composto 'pendente
    # verificacao' (falta o "\s+" direto: ha "(verificar" no meio).
    assert L.is_pending("Pendente (verificar disponibilidade)") is True
    assert L.is_flip_eligible("Pendente (verificar disponibilidade)") is True


def test_predfallback_a_verificar_e_reconhecido_como_aguardando():
    # Divergente 2: unico vocabulo presente e 'verifica' -> verificacao.
    assert L.is_awaiting_verification("A verificar") is True


def test_predfallback_em_andamento_com_verificar_no_texto_e_flipavel():
    # Divergente 3: 'andamento'@3 vence 'verifica'@15 por posicao.
    assert L.is_flip_eligible("Em andamento (verificar com o time)") is True


def test_predfallback_concluido_e_verificado_nao_e_mais_incoerente():
    # Divergente 4, o mais grave: 'conclu'@0 vence 'verifica'@12 por posicao
    # -> exatamente UM kind (done), nunca os dois predicados True ao mesmo
    # tempo.
    assert L.is_done("Concluído e verificado") is True
    assert L.is_awaiting_verification("Concluído e verificado") is False


def test_predfallback_compostos_vencem_independente_da_posicao():
    # 'Pendente design' e 'Pendente verificacao' sao status CANONICOS
    # compostos (SKILL.md), nao "pendente" com anotacao -- tem de vencer
    # mesmo com 'pendente' aparecendo antes na string. Sem este caso, o
    # BUG-5 grave (item de design auto-flipando) ressuscitaria no fallback.
    assert L.is_flip_eligible("Pendente design") is False
    assert L.is_pending("Pendente design") is True  # design ainda conta como nao-entregue
    assert L.is_awaiting_verification("Pendente verificação") is True
    assert L.is_flip_eligible("Pendente verificação") is False


def test_predfallback_nao_regride_dependente_nem_inconclusivo():
    # Colisoes que ja funcionavam (BUG-5/SUB-1) nao podem voltar: substring
    # crua sem fronteira de palavra continua sem casar.
    assert L.is_pending("Bloqueado (dependente de X)") is False
    assert L.is_done("Parcial (resultado inconclusivo)") is False


def test_predfallback_exclusividade_mutua_done_e_awaiting():
    # A incoerencia que motivou a fatia inteira: para qualquer celula do
    # fallback, no maximo um entre is_done/is_awaiting_verification pode
    # ser True -- garantido por construcao (uma so categoria por celula).
    for status in ("Concluído e verificado", "Pendente verificação", "A verificar"):
        assert not (L.is_done(status) and L.is_awaiting_verification(status))


def test_predfallback_emoji_continua_tendo_prioridade_absoluta_sobre_fallback():
    # A camada de emoji (D-1/BUG-5) nao pode ser tocada por este conserto:
    # com emoji reconhecido, a decisao e so pelo emoji, nunca pelo texto
    # livre que vem depois -- reconfirmando os 4 casos do BUG-5 original
    # apos a mudanca no fallback.
    assert L.is_done("✅ Concluído -- revisado e VERIFICADO em produção") is True
    assert L.is_awaiting_verification("✅ Concluído -- revisado e VERIFICADO em produção") is False
    assert L.is_pending("🔴 Bloqueado (dependente de X)") is False
    assert L.is_flip_eligible("⏳ Pendente (verificar disponibilidade)") is True
