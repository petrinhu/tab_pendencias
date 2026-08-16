# Bus versus INBOX de planejamento (TAB-BUS-003)

> Reference do produto. Dois conceitos com nome parecido e semântica
> **diferente**. Mistura-los reintroduz a fila unica que o redesign matou.

## Tabela

| | Inbox do **bus** | INBOX do **TODO.md** |
|---|---|---|
| O que e | Transporte de mensagens entre projetos (ex.: pasta de um protocolo de mensagem) | Exception queue de **planejamento** do proprio projeto |
| Quem escreve | Remetente / watcher de chegada | Intake residual (triagem / leader decision) ou fallback `inbox/` entre sessoes |
| Quem decide prioridade | **Ninguem no transporte** -- o receptor julga no proprio TODO | Ninguem: residual nao tem Onda/WSJF ate o dreno |
| O que transporta | Fatos: necessidade, evidencia, prazo factual | Metadado `[triage ...]` + descricao curta |
| Anti-padrao | Importar "urgente" do remetente como rank | Usar como backlog normal de descoberta |

## Fluxo correto

```text
mensagem chega no bus
  -> extract_facts (tools/bus_contract.py)
  -> candidate_from_bus (source=bus; claimed_priority ignorado)
  -> todo_intake.run_intake no TODO do projeto RECEPTOR
  -> so entao archive_allowed (rastro no TODO)
```

O watcher do bus (se existir no ecossistema) observa **chegada de
mensagem**. Isso e evento de transporte. **Nao** e monitor LLM que
recalcula ranking do `TODO.md` por relogio (proibido pela norma de
frescor).

## Regras de score (TAB-BUS-001 / TAB-WSJF-007)

- `claimed_priority` e prosa ("urgente", "ASAP", "alta") **nunca** pontuam.
- `time_criticality` / BV / RR / Job Size so entram com **int Fibonacci
  explicito** `(1,2,3,5,8,13,20)`.
- Remetente `source=bus` no motor WSJF tambem ignora rotulos early.

## Rastreabilidade antes de arquivar (TAB-BUS-002)

Mensagem processada **nao** arquiva como "agida" se o pedido de trabalho
futuro nao terminou em um de:

1. item no `TODO.md` (L0 / SCOPED / FULL aplicado);
2. `DUPLICATE` ligado a item existente;
3. residual INBOX com motivo de triagem;
4. residual `needs-leader-decision`.

Ver `archive_allowed` em `tools/bus_contract.py`.

## Excecoes de dominio

Fluxos especiais de um remetente concreto (prioridade propria de um
protocolo de produto) **nao** entram neste nucleo generico. O caller
decide depois de `extract_facts`; o contrato do bus permanece agnostico.
