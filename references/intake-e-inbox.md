# Intake e INBOX residual (`--add` / `--drain`)

> Referência operacional do pipeline de intake (ADR-0002), movida do `SKILL.md`
> em 21/08/2026 para reduzir o contexto carregado a cada invocação da skill.
> O `SKILL.md` mantém as proibições e os gates; o detalhe está aqui.
> Convenções de frescor e a forma do arquivo:
> [`frescor-da-tabela.md`](frescor-da-tabela.md) (§5.1 cobre a INBOX residual do
> ponto de vista do formato). Sinais `TAB_*`:
> [`sinais-de-frescor.md`](sinais-de-frescor.md).

## INBOX (exception queue -- nao e fila normal)

> **Historico (pre-intake):** versoes antigas da skill mandavam *toda* descoberta
> para a INBOX "na hora" e esperavam dreno humano/`--reorder`. Isso ficou
> obsoleto com o pipeline de intake (ADR-0002). A INBOX residual **nao** e a
> fila normal de descoberta.

Trabalho novo descoberto no meio do sprint **nao espera reordenar**: a thread
principal chama o **intake** (`--add` / `tools/todo_intake.py`). A cascata decide:

1. **Local (L0)** -- entra no `TODO.md` na hora (append).
2. **Escopado / fundacao** -- `SCOPED_REORDER` ou `FULL_REORDER` proporcional.
3. **Duplicata** -- nao cria linha; limpa residual relacionado se houver.
4. **Ambiguo / sem autoridade** -- so entao vira **INBOX residual** (exception
   queue) com metadado `[triage ...]`, sem Onda nem WSJF.

Workers/subagentes **nao** escrevem na INBOX: devolvem `DISCOVERED_WORK` e o
main chama o intake (ver secao **Fluxo agentivo de `--add`**).

- **Local da residual:** secao **ANTES da tabela** do `TODO.md` de projeto
  (ordem canonica acima; o formato legado -- INBOX depois -- ainda e lido,
  com aviso):
  ```markdown
  ## INBOX (descobertas não priorizadas)
  - <ID tentativo ou —>: [triage ...] descricao curta
  ```
- **Concorrência (worktrees/PRs paralelos, sem orquestrador comum):** fallback
  `inbox/` via `tools/concurrent_inbox.py` (arquivo por descoberta). Nao e
  backlog normal. Resolucao de conflito: **sempre uniao, NUNCA descartar linha**.
- **Dreno (secao residual `## INBOX` no `TODO.md`):** preferir `--drain`
  (classifiable com julgamento agentivo + residual envelhece por `cycles`
  **ou** idade em dias). `--create` e `--reorder` tambem drenam essa secao
  residual no TODO. O motor **nao** le nem apaga `inbox/*.md`.
- **Fallback `inbox/` (arquivos concurrent):** fluxo proprio entre sessoes --
  `concurrent_inbox.list_pending` / `read_discovery`, depois a thread principal
  processa cada `DISCOVERED_WORK` via bridge+intake. Nao confiar em `--drain`
  para esvaziar o diretorio. `TAB_TRIAGE_REQUIRED` e **acao obrigatoria**
  da thread principal (SessionStart/health), nao lembrete passivo. Sinais:
  secao **Sinais de frescor (`TAB_*`)** e `sinais-de-frescor.md`.

> **Dois tipos de `TODO.md`:** o de **projeto** (itens editaveis; item↔commit
> faz sentido; esta secao se aplica) e o **hub agregador** (contagens derivadas;
> NÃO marcar a mao nem usar INBOX -- regenerar por script; ver
> `hub-agregador.md` e guarda `hub_is_derived_readonly`). A
> convencao de frescor vale no de projeto.

## `--add`

Entrada de descoberta / item novo no pipeline de intake (ADR-0002). O núcleo
mecânico é `tools/todo_intake.py` (offline, stdlib, sem LLM): recebe um
`WorkCandidate` **já julgado** (flags booleanas de predicado preenchidas por
quem chama -- a skill/agente --, o núcleo **não** infere de prosa) e aplica a
cascata fixa de rota.

**Cascata** (primeiro que casa vence):

1. ID já **na tabela** **ou** descrição normalizada (strip + colapsa whitespace +
   casefold) igual a item da tabela/INBOX residual, com critérios de aceitação
   iguais se **ambos** tiverem o campo → `DUPLICATE` (não cria linha; limpa
   residual relacionado se houver). Fronteira: equivalência **além** de string
   normalizada é julgamento do agente (sem NLP no núcleo).
2. campos incompletos / dep inexistente / source inválido → `NEEDS_TRIAGE` (INBOX residual)
3. sem autoridade → `NEEDS_LEADER_DECISION` (INBOX residual)
4. fundação → `FULL_REORDER` (topo estável + ondas; `--apply` grava)
5. local (L0) → `LOCAL_INTEGRATION` (append puro de 1 linha no fim da tabela)
6. escopado → `SCOPED_REORDER` (subgrafo S; `--apply` grava com equivalência fora de S)
7. default → `FULL_REORDER`

P-dup por **id** **não** conta id só na INBOX residual: residual re-entra no
pipeline (ex.: após o líder decidir). P-dup por **descrição normalizada**
**sim** casa residual. Id só na residual + flags de integração → rota
L0/SCOPED/FULL e o núcleo remove a linha residual do mesmo id ao gravar.

**Contrato de L0:** zero células de linhas existentes mudam; marcador
recuperável `<!-- intake:CANDIDATE_ID -->` na descrição (para o journal
`recover_orphans`). Journal write-ahead antes de mutar (L0/residual/DUPLICATE);
`mark_done` após escrita validada. Working tree do `TODO.md` limpa é
pré-condição de `--apply`. Se a INBOX residual tiver item **classificável**
(sem `[triage ...]` válido), o apply aborta com `classifiable_inbox_present`
-- drain-first.

**Contrato SCOPED/FULL (TAB-ADD-005/006):** `item_id` obrigatório; W1
(Status de linhas pré-existentes nunca muda); FULL faz topological sort
estável + ondas `W1..` e insere o candidato com o marcador intake.
SCOPED calcula o menor subgrafo seguro `S` (deps abertas + ancestrais
não-done + descendentes + peers de onda); se `|S|/n` exceder
`scoped_reorder_max_fraction` (default 0.5; override via
`WorkCandidate.scoped_max_fraction`, env `TAB_INTAKE_SCOPED_MAX_FRACTION`
ou `.tab_pendencias.ini` `[intake]`) **ou** `S` tocar mais de um `Grupo`,
promove a FULL (`promoted_from=SCOPED_REORDER`). Fora de `S`, a linha
bruta de cada id existente permanece byte-a-byte idêntica; violação
aborta com `scoped_equivalence_failed` sem escrever. SCOPED/FULL montam
o texto em memória **antes** do journal (ciclo/equivalência não deixam
órfão NEW); journal imediatamente antes da escrita atômica.

**Após decisão do líder (TAB-ADD-007):** residual `needs-leader-decision`
não fica estacionado. A skill/agente (não o Python) apresenta 2–3 opções
com trade-offs. Quando o líder decide, a **thread chama de novo o intake**
com as flags de julgamento preenchidas (`fields_complete=True`, rota
`local` / `scoped` / `full` / fundação conforme o caso,
`authority_ok=True`). O núcleo integra e **remove da INBOX residual
qualquer linha com o mesmo `item_id`** (outras linhas da INBOX ficam;
heading vazio pode permanecer). Apresentar opções e colher a decisão é
dever da skill/agente; o strip do residual é mecânico no apply.

**Uso mecânico (CLI):**

```text
python3 tools/todo_intake.py --todo TODO.md \
  --candidate-id cand-1 --item-id F-12 \
  --description "..." --source agent \
  --fields-complete --local
# dry-run (exit 2 se a rota exigiria escrita)

python3 tools/todo_intake.py --todo TODO.md ... --apply
```

Gatilhos em linguagem natural ("adicione isto às pendências", "registra esta
feature", "isso precisa entrar no TODO") usam o mesmo pipeline. A skill
preenche o julgamento (local/escopado/fundação/autoridade/campos) e chama o
núcleo; não joga L0 na INBOX por conveniência.

## Fluxo agentivo de `--add` (agente julga, motor persiste)

Subagentes / workers **não** editam `TODO.md`. Devolvem descoberta no bloco:

```text
DISCOVERED_WORK
source_item: <ID atual>
description: <trabalho descoberto>
evidence: <arquivo:linha/teste/log>
known_dependencies: <IDs ou unknown>
blast_radius: <local/component/system/unknown>
```

A thread principal (único escritor lógico por orquestração):

1. Lê o bloco (prosa já julgada pelo agente).
2. Converte com `tools/intake_agent_bridge.py` (stdlib, **sem LLM**):
   `parse_discovered_work` + `judgment_from_discovered` mapeia
   `blast_radius` → flags (`local`→`is_local`, `component`→`is_scoped`,
   `system`→`is_foundation`, `unknown`→`fields_complete=False`).
3. Ou preenche as mesmas flags via CLI (`--local` / `--scoped` / …).
4. Chama `todo_intake.run_intake(..., apply=True)` -- o motor só **persiste**
   (com `TodoWriteLock` antes de mutar; timeout default 10s).

Fronteira: o agente **julga** (prosa, impacto, autoridade); o motor
**classifica por flags e grava**. Não há NLP no núcleo.

## Concorrência e `inbox/` (TAB-CONC)

- **Dentro de uma orquestração multi-agent:** só o `main` altera a tabela.
  Subagente devolve `DISCOVERED_WORK`; main chama bridge + intake.
- **Sessões / worktrees independentes (sem orquestrador comum):** usar
  `tools/concurrent_inbox.write_discovery(root, session_id, slug, body_md)`
  → `inbox/YYYYMMDD-HHMMSS-<session>-<slug>.md`. Não é backlog normal.
- **Próxima sessão principal:** se `todo_health` emitir
  `TAB_CONCURRENT_INBOX_PRESENT` / `TAB_TRIAGE_REQUIRED` por `inbox/`,
  processar cada arquivo (`list_pending` → `read_discovery` → bridge+intake)
  no próximo ponto seguro. `--drain` **nao** consome `inbox/*.md` -- so a
  secao residual `## INBOX` do `TODO.md`.
- **Escrita segura:** `run_intake`/`run_drain` em apply adquirem
  `tools/todo_lock.TodoWriteLock` (fcntl em POSIX; msvcrt em Windows;
  fallback exclusive-create com stale 120s). Lock reentrant no mesmo
  thread (drain aninha intake).
## `--drain` (TAB-INBOX-004)

Opera a secao residual `## INBOX` do `TODO.md` como **exception queue**.
Motor: `tools/todo_intake.py --drain`. **Nao** le nem apaga arquivos em
`inbox/` (fallback concurrent -- ver secao TAB-CONC acima).

```text
python3 tools/todo_intake.py --drain --todo PATH
python3 tools/todo_intake.py --drain --todo PATH --apply
python3 tools/todo_intake.py --drain --todo PATH --apply --judgments-json PATH
# ou --judgments-json -  (stdin) / --json com --drain
```

Comportamento:

1. Lê INBOX via `inbox_entries`.
2. **classifiable** (sem `[triage ...]` válido): dry-run lista e exit 2;
   `--apply` exige julgamento em `--judgments-json` (senão exit 1).
3. Residual com triage **válido**: em apply, incrementa `cycles` no metadado;
   `needs-leader-decision` **não** auto-integra (só envelhece).
4. Judgments (por id da linha INBOX):

```json
{
  "FIX-RISCO-1": {
    "action": "split",
    "items": [
      {"candidate_id":"...", "item_id":"FIX-RISCO-A", "description":"...",
       "source":"audit", "fields_complete": true, "is_local": true,
       "authority_ok": true}
    ]
  }
}
```

   `action`: `integrate` (1 item), `split` (N items), `keep` (+ `reason` de
   triage). Após integrate/split remove a linha original e chama `run_intake`
   apply por candidato (journal write-ahead por candidato).
5. Pós-condição de apply bem-sucedido: `classifiable_inbox_count == 0`
   (senão rc=1). Working tree do TODO limpa no início do apply.
   Contagem e strip referem-se só a bullets da secao residual no TODO --
   `inbox/*.md` permanece intacto mesmo com drain verde.

Health (`todo_health.py`) consome `session_signals.collect_signals` e imprime
as linhas `TAB_*` (ver secao **Sinais de frescor** e
`sinais-de-frescor.md`). `TAB_TRIAGE_REQUIRED` = classifiable **ou**
residual aged (cycles/idade) **ou** `inbox/` concorrente -- **nao**
`inbox_count>=3` so de leader frescos. Quando o gatilho e so `inbox/`, a
acao e o fluxo TAB-CONC (list_pending + bridge+intake), nao "apagar pasta
apos `--drain`". Contagem de `needs-leader-decision` fresco e separada;
so o aged emite `TAB_LEADER_DECISION_AGED` (+ TRIAGE).
