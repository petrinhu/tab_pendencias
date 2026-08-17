# BUS-1 -- Relay D-1 (emoji-prefixo) para o consumidor B

**Status:** **entregue** 2026-08-16. Item da tabela em `🔍 Pendente verificação`.

## Entrega no bus

| Campo | Valor |
| :--- | :--- |
| Destinatario | consumidor B (inbox do bus) |
| Thread | `higiene-repo` |
| Arquivo | `inbox/<consumidor-B>/20260816-2110-tab_pendencias-d1-emoji-prefixo.md` |
| Commit bus | `c284edeb5261273039647e1e00e1d3cc4cbbd943` |
| Remoto | repositorio do bus do consumidor B (main); commit c284edeb5261273039647e1e00e1d3cc4cbbd943 |

## Conteudo (resumo)

Decisao D-1: predicados de status por emoji-prefixo; fallback legada sem
substring solta; consumidor deve usar toolkit pinado (v1.2+) e nao
reclassificar por prosa ambigua.

## Mensagem enviada (corpo)

Ver o arquivo no bus (fonte de verdade da entrega). Copia de trabalho:

```text
Assunto: D-1 emoji-prefixo -- classificacao de status (tab_pendencias)

Decisao D-1 (casa): predicados de status usam emoji-prefixo canonico
(⏳ 🔄 🔍 ✅ etc.). Fallback legada e word-boundary / classificacao por
precedencia, sem ressuscitar BUG-5 (substring "verificado"/"inconclusivo").

Acao no consumidor B:
1. Nao reimplementar classificadores locais de status que casem substring.
2. Preferir a versao publicada do toolkit (pin do submodulo / tag v1.2+).
3. Se a tabela legada nao tiver emoji, o audit aponta; nao auto-flipear.

Referencia: tab_pendencias tools/todo_lib.py (is_*/_classify_legacy) +
tests/test_bug5_predicados_emoji.py. Release: v1.2.0+.
```

## DoD de fechamento desta fatia

- [x] Mensagem escrita no bus
- [x] Commit + push no remoto do bus
- [x] Status BUS-1 na TODO.md do produto -> 🔍
- [ ] Confirmacao de leitura pelo destinatario (opcional; nao bloqueia 🔍)
