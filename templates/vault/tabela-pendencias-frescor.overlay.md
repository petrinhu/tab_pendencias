# Overlay da casa: frescor da tabela de pendencias (TAB-VAULT-002)

> Documento de **vault** (overlay). Explica o racional da casa e a
> integracao com agents/bus. A **norma generica e agnostica a projeto**
> mora no produto:
>
> `skills/tab_pendencias/references/frescor-da-tabela.md`
>
> Nao duplique parser, CLI, schema de colunas ou catalogo de checks aqui.
> Quando a norma do produto e a politica da casa divergirem no detalhe
> mecanico, vence o produto; este overlay so adiciona limiares e
> integracoes.

## O que este overlay cobre

1. **Racional** -- por que a casa separa sincronizar (barato) de reordenar
   (caro) e por que a INBOX deixou de ser a fila normal de descoberta.
2. **Ponte para a skill** -- caminho relativo no clone de memoria:
   `skills/tab_pendencias/` (submodulo do produto publicado).
3. **Limiares da casa** (opt-in via `.tab_pendencias.ini` no projeto):
   - `[signals] triage_max_cycles` / `triage_max_age_days` (defaults do
     produto se ausentes);
   - perfil `casa` em `[profile] name = casa` so quando o projeto adota as
     convencoes extras (CHK-12..14).
4. **Agents** -- implementers devolvem `DISCOVERED_WORK`; main + skill
   julgam e persistem. Ver
   `skills/tab_pendencias/templates/agents/implementer-discovery-contract.md`.
5. **Bus** -- transporte de fatos entre projetos; prioridade retorica do
   remetente **nao** pontua. Ver
   `skills/tab_pendencias/references/bus-versus-inbox.md`.
6. **Hub agregador** -- view derivada read-only; nunca fila editavel. Ver
   `skills/tab_pendencias/references/hub-agregador.md`.

## O que NAO fica neste overlay

- Vocabulario de Status, DoD de transicao, regra do ID no commit -- no
  reference do produto.
- Cascata de intake, journal, lock, WSJF -- no `SKILL.md` / `tools/` do
  produto.
- Caminhos absolutos de maquina do autor ou segredos.

## Pipeline de descoberta (resumo)

```text
worker descobre
  -> DISCOVERED_WORK (sem editar TODO)
  -> main + intake
  -> L0 / SCOPED / FULL / residual INBOX / DUPLICATE
```

INBOX residual e exception queue. `TAB_TRIAGE_REQUIRED` e obrigacao da
thread principal no SessionStart/health, nao lembrete cosmetico.
