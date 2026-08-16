# Contrato de descoberta para agents implementers (TAB-VAULT-003)

> Template de produto. Agents de implementacao **nao** registram na INBOX
> nem editam ranking do `TODO.md`. Devolvem achados ao main.

## Regras

1. **Nao editar** `TODO.md`, secao INBOX, nem `inbox/` por conta propria.
2. **Nao** atribuir prioridade, Onda ou WSJF ao achado.
3. **Citar** o item de origem (`source_item`) quando a descoberta nasceu
   de um item em curso.
4. Devolver o bloco estruturado abaixo no retorno final (alem do relatorio
   de trabalho).
5. Prioridade e rota (L0 / SCOPED / FULL / residual) ficam com
   **main + skill** (`intake_agent_bridge` + `todo_intake`).

## Bloco obrigatorio

```text
DISCOVERED_WORK
source_item: <ID atual ou unknown>
description: <trabalho descoberto, 1 linha>
evidence: <arquivo:linha / teste / log>
known_dependencies: <IDs separados por virgula, ou unknown>
blast_radius: <local|component|system|unknown>
```

### Campos

| Campo | Obrigatorio | Notas |
|---|---|---|
| `source_item` | sim | ID do item que o agent estava executando, ou `unknown` |
| `description` | sim | Fato, nao prioridade retorica ("urgente") |
| `evidence` | sim | Pista reproduzivel |
| `known_dependencies` | sim | IDs ja existentes ou `unknown` |
| `blast_radius` | sim | Heuristica para o bridge: local->L0, component->SCOPED, system->FULL, unknown->triagem |

## Multiplos achados

Repetir o bloco uma vez por descoberta. Nao agregar em prosa livre sem o
marcador `DISCOVERED_WORK`.

## O que o main faz

1. `parse_discovered_work` + `judgment_from_discovered` (sem LLM no nucleo).
2. `todo_intake.run_intake(..., apply=True)` sob lock.
3. Se residual / leader decision: apresentar 2-3 opcoes ao lider quando
   for o caso; re-chamar intake apos a decisao.

## Fora de escopo deste contrato

- Cosimo decide complexidade da orquestracao; Cosmo coordena execucao
  quando necessario -- inalterado.
- Sessões sem orquestrador comum usam `concurrent_inbox.write_discovery`
  (fallback entre sessoes), nao este bloco.
