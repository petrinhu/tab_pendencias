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
