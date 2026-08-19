# Sinais de frescor (`TAB_*`)

> Contrato dos identificadores emitidos pelo motor `tools/session_signals.py`
> (Fase 6 / TAB-HOOK-001..004 + INTAKE-AGE-1). Read-only, offline, sem LLM.
> Consumidores: `todo_health.py` e o adapter de hook
> `tools/hooks/tab_pendencias_reminder.py`.

## Principios

1. **Deterministico.** Predicados so leem disco/git local; relogio injetavel
   (`now=date`) para testes.
2. **Sem reordenacao por relogio (TAB-HOOK-003).** Idade/ciclos pedem
   **triagem** (`--drain`), nunca `--reorder` automatico.
3. **Fail-open no hook.** Adapter sempre sai 0 e `continue: true`.
4. **Uma fonte de regra.** Adapter e health so formatam; a logica mora em
   `session_signals.collect_signals`.

## Config (`.tab_pendencias.ini` secao `[signals]`)

| Chave | Default | Uso |
|---|---|---|
| `triage_max_cycles` | 2 | residual envelhece se `cycles >= N` |
| `triage_max_age_days` | 1 | residual envelhece se idade desde `since` >= N dias |
| `verification_aging_min_count` | 5 | `TAB_VERIFICATION_AGING` se n de 🔍 >= N |
| `verification_aging_min_days` | 7 | ou se n de 🔍 >= 1 e dias sem tocar TODO >= N |
| `status_sync_min_commits` | 5 | sync se commits desde ultimo toque no TODO >= N |
| `status_sync_min_days` | 3 | ou dias desde ultimo toque >= N |

Lido por `todo_lib.load_signals_config(todo_path)`. Ausencia do arquivo ou
da secao devolve defaults (fail-open).

## Predicado de envelhecimento (INTAKE-AGE-1)

`todo_lib.residual_is_aged(entry, *, now, max_cycles=2, max_age_days=1)`:

- so avalia residual com `[triage ...]` **valido**;
- envelhece por **OU**:
  - `cycles >= max_cycles` (avanca no `--drain`), **ou**
  - `(now - since).days >= max_age_days` (avanca pelo calendario mesmo
    quando ninguem drena -- fecha a falha de liveness do contador so-no-drain).

Decisao do lider (ADR-0002): apresentacao **hibrida** -- silencio enquanto
fresco; interrupcao quando envelhece.

## Catalogo de IDs

| ID | Ativo quando | Acao esperada da thread |
|---|---|---|
| `TAB_TODO_CREATE_REQUIRED` | repo git sem `TODO.md` na raiz | `/tab_pendencias --create` |
| `TAB_STATUS_SYNC_RECOMMENDED` | ha ⏳ ou 🔄 **e** (commits_since_todo_touch >= min_commits **ou** days_since_todo_touch >= min_days) | `python3 tools/todo_sync.py` (barato; nunca reordena) |
| `TAB_TRIAGE_REQUIRED` | `classifiable > 0` **ou** residual aged **ou** `inbox/*.md` pendente | `--drain` no proximo ponto seguro |
| `TAB_CONCURRENT_INBOX_PRESENT` | count de `inbox/*.md` > 0 | dreno do fallback entre sessoes |
| `TAB_LEADER_DECISION_AGED` | residual `reason=needs-leader-decision` **e** `residual_is_aged` | apresentar 2-3 opcoes (AskUserQuestion); re-chamar intake apos decisao |
| `TAB_VERIFICATION_AGING` | n_verif >= min_count **ou** (n_verif >= 1 e days_since_todo_touch >= min_days) | planejar onda TST-*/AUD-* |
| `TAB_INTAKE_RECOVERY_REQUIRED` | journal de intake com orfaos (`state != DONE`) | recuperacao idempotente antes de novo intake |

### O que **nao** dispara `TAB_TRIAGE_REQUIRED`

- so `needs-leader-decision` **frescos** (cycles baixo e since recente),
  mesmo que sejam 5+ (ADR-0002 F9: breaker de `inbox_count >= 3` com
  residuais de lider vira ruido permanente);
- tabela so com ⏳/🔄 sem INBOX/classifiable/aged/concurrent (isso e
  `TAB_STATUS_SYNC_RECOMMENDED` se a defasagem de commits/dias bater).

## Roteamento por evento de hook (TAB-HOOK-005)

O mesmo adapter e ligado a **dois** eventos do harness (`SessionStart` e
`UserPromptSubmit`). Cada sinal e emitido em **exatamente um** deles -- a
particao e exaustiva e disjunta sobre `SIGNAL_IDS`, garantida por teste. Um
sinal nos dois eventos repetiria a mesma mensagem ao usuario, que e
exatamente o defeito que este roteamento fecha.

Criterio: **estado do repositorio** (granularidade de commit, dia ou ciclo de
drain) vai para `SessionStart`, porque reavaliar a cada prompt so gera ruido;
**reativo ao turno** (o que outra sessao/agent produz enquanto esta roda, e
cuja acao esperada acontece dentro do turno) vai para `UserPromptSubmit`.

| ID | Evento | Por que |
|---|---|---|
| `TAB_TODO_CREATE_REQUIRED` | `SessionStart` | so muda quando alguem cria o `TODO.md` |
| `TAB_STATUS_SYNC_RECOMMENDED` | `SessionStart` | defasagem em commits/dias, nao em prompts |
| `TAB_TRIAGE_REQUIRED` | `SessionStart` | "planejar um `--drain`" e decisao de uma vez por sessao; a parcela rapida (`inbox/`) tem sinal proprio por turno |
| `TAB_LEADER_DECISION_AGED` | `SessionStart` | envelhece em dias/ciclos de drain |
| `TAB_VERIFICATION_AGING` | `SessionStart` | contagem de 🔍 + dias sem tocar a tabela; planejamento de onda |
| `TAB_INTAKE_RECOVERY_REQUIRED` | `SessionStart` | orfao no journal de intake; decisao do lider em 19/08/2026 (nota abaixo) |
| `TAB_CONCURRENT_INBOX_PRESENT` | `UserPromptSubmit` | `inbox/*.md` e escrito por OUTRA sessao enquanto esta roda |

### Nota: `TAB_INTAKE_RECOVERY_REQUIRED` (decidido em 19/08/2026)

Este sinal cabe nas duas leituras do criterio. O orfao **e** estado durado do
repositorio -- o journal sobrevive ao fim da sessao --, mas tambem pode
**nascer no meio da sessao**, quando um intake morre entre o write-ahead e a
integracao. A primeira implementacao pos o sinal no `UserPromptSubmit` pela
segunda leitura, contrariando a letra do plano de campanha
(`docs/campanha/PLANO-MELHORIA-TAB-PENDENCIAS-CLAUDE-CODE-2026-08-16.md`,
regra 4 do journal write-ahead e tick 3 da revisao final, que atribuem a
deteccao ao `SessionStart`).

**O lider decidiu pelo `SessionStart`**, alinhando o codigo ao plano. Criterio
de desempate: **zero repeticao** ao usuario. **Trade-off aceito e explicito:**
um orfao criado no meio da sessao **so aparece na sessao seguinte**. A
recuperacao continua disponivel na hora por `todo_health.py`, que imprime as
mesmas linhas `TAB_*` sob demanda, sem depender do hook.

### `hook_event_name` ausente ou desconhecido

- **Ausente/vazio** (invocacao manual, harness de terceiro, payload
  truncado) -> assume `SessionStart`. E o lado que **nao repete** (assumir
  `UserPromptSubmit` emitiria a cada turno, o defeito original), e e o
  conjunto informativo para um consumidor manual. Emitir nada deixaria o
  hook indistinguivel de "nenhum sinal ativo".
- **Desconhecido** (`PreToolUse`, `Stop`, nome futuro) -> nao casa nenhuma
  chave e **nao emite nada**. Evento para o qual ninguem projetou o conteudo
  merece silencio, nao ruido.
- Comparacao **case-insensitive**, com `strip()`.

### Deduplicacao por sessao

Somente no evento por-turno (`UserPromptSubmit`): um sinal com as **mesmas
reasons** nao se repete no mesmo `session_id`. Se o fato mudar
(`inbox_files=1` -> `inbox_files=2`), o sinal volta a ser emitido -- dedup
nunca silencia informacao nova.

- Estado: um arquivo JSON por sessao no diretorio temporario do SO
  (`tempfile.gettempdir()`), **nunca** dentro do repositorio do usuario. O
  `session_id` vira digest hex (sem travessia de caminho); escrita atomica
  por `os.replace`; limpeza por TTL de 7 dias e teto de arquivos.
- `SessionStart` **nao** e deduplicado de proposito: dispara poucas vezes por
  sessao e cada disparo (`startup`/`resume`/`clear`/`compact`) segue um reset
  de contexto -- suprimir ali apagaria a injecao quando ela mais importa.
- Sem `session_id`, ou com estado ilegivel: **fail-open**, emite.

## Formatos de saida

- **Maquina** (`format_machine`): uma linha por sinal ativo
  `TAB_ID reason1,reason2`.
- **Humano** (`format_human`): prosa curta por sinal, com reasons entre
  parenteses.
- **Hook adapter**: JSON
  `{"continue": true, "additionalContext": "<machine>\\n<human>"}`
  (sem `additionalContext` se nenhum sinal ativo).

## Fronteiras

- Nao chama `run_intake`, WSJF, LLM nem rede.
- Nao escreve `TODO.md` nem muta journal.
- Nao implica full reorder: tempo/idade -> triagem, nao reordenacao cega.
