# BUS-1 — Relay D-1 (emoji-prefixo) para o consumidor B

**Status:** bloco colável pronto. Se o consumidor B / bus não estiver
acessível nesta máquina, o item permanece `⏳` até o relay ser entregue.

## Mensagem pronta para colar (bus / sessão do consumidor)

```text
Assunto: D-1 emoji-prefixo — classificação de status (tab_pendencias)

Decisão D-1 (casa): predicados de status usam emoji-prefixo canônico
(⏳ 🔄 🔍 ✅ etc.). Fallback legada é word-boundary / classificação por
precedência, sem ressuscitar BUG-5 (substring "verificado"/"inconclusivo").

Ação no consumidor B:
1. Não reimplementar classificadores locais de status que casem substring.
2. Preferir a versão publicada do toolkit (pin do submódulo / tag v1.2+).
3. Se a tabela legada não tiver emoji, o audit aponta; não auto-flipear.

Referência: tab_pendencias tools/todo_lib.py (is_*/_classify_legacy) +
tests/test_bug5_predicados_emoji.py. Release: v1.2.0+.
```

## Quando marcar 🔍

Após o relay ser efetivamente enviado (ou o consumidor confirmar leitura).
