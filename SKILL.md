---
name: tab_pendencias
description: Cria e gerencia tabela de pendências/planejamento ORDENADA para minimizar retrabalho. No --create (e --reorder) orquestra um time de agents (Cosmo/COO coordena software-architect + tech-lead + product-manager + engineering-manager + scrum-master) para sequenciar por dependência (topological) e valor (WSJF), com coluna "Onda" sinalizando passos de igual valor paralelizáveis. Use sempre que o usuário pedir criar/mostrar/atualizar tabela de pendências, planejar passos, ordenar backlog, "o que falta", "em que ordem fazer", auditar a tabela (--audit), aplicar auto-fix mecânico (--fix), capturar item novo (--add), drenar INBOX residual (--drain), ou invocar /tab_pendencias. Em qualquer comando, garante (com dupla-confirmacao) testes nao-unitarios e auditorias aplicaveis ao stack como itens de fechamento; cria ./TESTES.md e ./AUDITORIAS.md do projeto quando faltam. Argumentos: --create, --reorder, --show, --main, --add_tests_audit, --audit, --fix, --add, --drain.
argument-hint: --reorder | --create | --show | --main | --add_tests_audit | --audit | --fix | --add | --drain
allowed-tools: [Read, Write, Edit, Glob, Grep, Agent, TodoWrite]
---

# tab_pendencias

Cria, ordena e exibe tabelas de planejamento. O diferencial: a tabela sai **ordenada de cima para baixo na ordem de execução que minimiza retrabalho**, com a coluna **Onda** marcando os passos de igual valor que podem rodar em paralelo.

O usuário invocou com: $ARGUMENTS

---

## Schema canônico (9 colunas)

```markdown
| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

A ordem das linhas (de cima para baixo) É a ordem de execução recomendada. A coluna `Onda` agrupa passos paralelizáveis.

### Valores por coluna

- **Onda**: `W1`, `W2`, `W3`, ... (leva de execução). Itens da mesma Onda não dependem entre si e têm valor comparável: **podem rodar em paralelo (igual valor)**. `—` para itens concluídos ou fora do fluxo.
- **Prioridade**: Alta / Média / Baixa.
- **Pré-requisito**: `—` (nenhum) ou ID(s) que precisam estar concluídos antes (ex: `F1.4`, `F2.1, F2.2`).
- **Dificuldade**: Alta / Média / Baixa (atalho qualitativo de Job Size no WSJF early; o motor usa a régua fib `1,2,3,5,8,13,20`).
- **Status**: símbolo + texto.

| Status | Significado |
|:---|:---|
| ✅ Concluído | finalizada |
| 🔄 Em andamento | em progresso |
| 🟡 Parcial | feito em parte |
| ⏳ Pendente | não iniciado |
| 💡 Decisão tomada | abordagem definida, implementação futura |
| 🎨 Pendente design | aguarda spec/brainstorm |
| 🔍 Pendente verificação | implementado, aguarda validação |

- **Estado Auditado**: `—` (não auditado) | `✓` (aprovado) | `⚠` (com ressalvas).

> Compatibilidade: tabelas legadas de 8 colunas (sem Onda) continuam válidas para `--show`/`--main`. Ao rodar `--reorder` numa tabela de 8 colunas, a skill adiciona a coluna Onda.

---

## Frescor: manter a tabela viva no sprint

Para a tabela não apodrecer durante o sprint, separe SEMPRE duas operações de naturezas opostas (detalhe canônico em `references/frescor-da-tabela.md`):

- **Sincronizar status** (barato, frequente, no commit): ao fechar trabalho, toque a coluna `Status` do item no MESMO PR, com o ID que o projeto JÁ tem (não renumerar). Implementação entregue vira `🔍 Pendente verificação` (NUNCA `✅` direto); `✅ Concluído` só após a onda `TST-*`/`AUD-*` correspondente. **Marcar status nunca dispara o time de agents.**
- **Reordenar** (caro, raro, julgamento): só via `--reorder`, e só quando um input de priorização muda (nova dependência, item ficou urgente, INBOX não-vazia). Nunca por passagem de tempo, loop ou monitor contínuo.

A parte mecânica (sincronizar status) tem executores LOCAIS e determinísticos, **offline, sem agents/LLM** (rodam fora desta skill, no próprio repo do projeto que usa a skill): `python3 tools/todo_sync.py [--apply]` avança itens entregues `⏳`/`🔄` → `🔍` a partir dos IDs citados nos commits (nunca `✅`, nunca reordena); `python3 tools/todo_health.py` reporta presos em `🔍`, INBOX e adesão. Esta skill cobre o **planejamento** (`--reorder`, julgamento); a sincronização mecânica vive nesses scripts. Ver `tools/README.md`.

### INBOX (exception queue -- nao e fila normal)

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

- **Local da residual:** secao no FIM do `TODO.md` de projeto:
  ```markdown
  ## INBOX (descobertas não priorizadas)
  - <ID tentativo ou —>: [triage ...] descricao curta
  ```
- **Concorrência (worktrees/PRs paralelos, sem orquestrador comum):** fallback
  `inbox/` via `tools/concurrent_inbox.py` (arquivo por descoberta). Nao e
  backlog normal. Resolucao de conflito: **sempre uniao, NUNCA descartar linha**.
- **Dreno:** preferir `--drain` (classifiable com julgamento agentivo + residual
  envelhece por `cycles` **ou** idade em dias). `--create` e `--reorder` tambem
  esvaziam a INBOX (e o `inbox/`). `TAB_TRIAGE_REQUIRED` e **acao obrigatoria**
  da thread principal (SessionStart/health), nao lembrete passivo. Sinais:
  secao **Sinais de frescor (`TAB_*`)** e `references/sinais-de-frescor.md`.

> **Dois tipos de `TODO.md`:** o de **projeto** (itens editaveis; item↔commit
> faz sentido; esta secao se aplica) e o **hub agregador** (contagens derivadas;
> NÃO marcar a mao nem usar INBOX -- regenerar por script; ver
> `references/hub-agregador.md` e guarda `hub_is_derived_readonly`). A
> convencao de frescor vale no de projeto.

### Sinais de frescor (`TAB_*`)

Motor: `tools/session_signals.py` (read-only, offline, sem LLM). Adapter de
hook Claude Code: `tools/hooks/tab_pendencias_reminder.py` (stdin JSON ->
stdout `{continue:true, additionalContext?}`; exit sempre 0; zero regra de
negocio propria). Health imprime as mesmas linhas `TAB_*`.

Contrato completo: [`references/sinais-de-frescor.md`](references/sinais-de-frescor.md).

| Sinal | Gatilho resumido | Acao da thread |
|---|---|---|
| `TAB_TODO_CREATE_REQUIRED` | git sem `TODO.md` | `--create` |
| `TAB_STATUS_SYNC_RECOMMENDED` | ha ⏳/🔄 e tabela defasada (commits/dias) | `todo_sync.py` (barato) |
| `TAB_TRIAGE_REQUIRED` | classifiable **ou** residual aged **ou** `inbox/` | `--drain` (nao full reorder por relogio) |
| `TAB_CONCURRENT_INBOX_PRESENT` | `inbox/*.md` pendente | dreno do fallback |
| `TAB_LEADER_DECISION_AGED` | residual `needs-leader-decision` envelhecido | 2-3 opcoes + re-intake |
| `TAB_VERIFICATION_AGING` | muitos 🔍 ou 🔍 + dias sem tocar TODO | onda TST-*/AUD-* |
| `TAB_INTAKE_RECOVERY_REQUIRED` | orfaos no journal de intake | recuperacao idempotente |

**Envelhecimento residual (INTAKE-AGE-1):** `cycles >= triage_max_cycles`
(default 2) **ou** idade desde `since` >= `triage_max_age_days` (default 1).
A idade de calendario avanca mesmo sem `--drain` (liveness). Leader fresco
**nao** polui `TAB_TRIAGE_REQUIRED`; leader aged dispara `TAB_LEADER_DECISION_AGED`
e entra no TRIAGE. Limiares em `.tab_pendencias.ini` secao `[signals]`.

---

## Método de ordenação (anti-retrabalho)

Aplicado no `--create` e `--reorder`:

1. **Topological sort por `Pré-requisito`.** Nada aparece antes do que ele depende. Quebra ciclo se houver (sinaliza).
2. **Dentro de cada nível topológico, ordena por WSJF** (Weighted Shortest Job First):
   `WSJF = Custo de Atraso / Job Size`, onde Custo de Atraso = valor de negócio + criticidade temporal + redução de risco/viabilização; Job Size ~ `Dificuldade`. Maior WSJF primeiro.
   Efeito anti-retrabalho: **fundação e decisões one-way-door sobem ao topo** (errar nelas é o retrabalho mais caro).
3. **Agrupa em Ondas.** Itens no mesmo nível topológico, sem dependência mútua e com WSJF comparável = mesma Onda (`W1`, `W2`, ...). Sinaliza o que é paralelizável (igual valor).

### Tabela de scoring WSJF (obrigatória em scale/bigtech, conforme [[AGILE]] §17.2)

Em contexto SAFe (porte scale-up/bigtech, definido por Cósimo), NÃO apresentar a priorização sem a tabela de scoring que justifica cada WSJF (AGILE §17.2 é taxativo). Emitir junto:

```markdown
| ID | Item | Valor (1,2,3,5,8,13,20) | Criticidade (1,2,3,5,8,13,20) | Redução de Risco (1,2,3,5,8,13,20) | CoD | Job Size (1,2,3,5,8,13,20) | WSJF | Rank |
```

`CoD = Valor + Criticidade + Redução de Risco`; `WSJF = CoD / Job Size`. Rank = ordem decrescente de WSJF **dentro do nível topológico** (dependência sempre vence). A régua do motor é a Fibonacci modificada `(1,2,3,5,8,13,20)` -- o intervalo "1-20" antigo era só o min/max, não escala linear. Em early o motor aceita rótulos Alta/Média/Baixa só como atalho para fib 8/5/2 no candidato; peers só entram com ints explícitos. Remetente `bus` nunca pontua por rótulo. Em projeto pequeno (early), o WSJF pode ser qualitativo (sem a tabela completa de cerimônia SAFe), respeitando o anti-OE.

### Testes e auditoria: ordem inviolavel (TDD + shift-left)

- **Teste unitario (T1) = TDD:** ride COM o item de implementacao (escrito antes/junto do codigo), garantido pelo hook de TDD (tdd_guard/tdd_runner). **NAO vira item** na tabela; nao criar "escrever testes unitarios" como passo solto.
- **Demais testes (T2-T15) sao downstream:** estatica, integracao, e2e, seguranca (secrets, SQLi, CVE), memoria, pre-CI. Nao existem antes do sistema; entram como itens de fechamento (`TST-*`) numa onda APOS a implementacao. Sao injetados pelo fluxo "Injecao automatica de testes e auditorias".
- **Auditoria e downstream de codigo+teste:** todo item `AUD-*` tem `Pre-requisito` = os itens de codigo+teste que audita; cai numa Onda POSTERIOR aos testes.
- **Invariante:** nunca agendar teste/auditoria antes do que ele cobre. Se a ordenacao produzir isso, a dependencia esta errada (corrigir o `Pre-requisito`).

---

## `--create` e `--reorder` (orquestrado)

### Gate anti over-engineering (sempre primeiro)

**Quem decide a abordagem de montagem (em `--create` e `--reorder`) é o Cosimo (Chief of Staff)**: ele classifica a complexidade da tabela (número de itens, dependências cruzadas, criticidade) e determina thread direta (simples) vs orquestrar o time (complexa). Calibrar pelo porte/complexidade (ver `cosimo-chief-of-staff` / [[ORG]]).
- **Tabela pequena/simples** (até ~8 itens, baixa complexidade e poucas dependencias cruzadas): **NÃO** spawnar o time. A própria thread aplica o método (topological + WSJF + ondas) e escreve. Anti-OE por complexidade da tabela, nao por porte "solo" (que nao existe: a constelacao esta sempre disponivel).
- **Tabela grande/complexa** (muitos itens, dependências cruzadas, cross-funcional): orquestrar o time abaixo.

### Orquestração (tabela grande)

Quando o Cosimo determina "via time", o **Cosmo (COO) coordena a montagem**: a skill (thread principal) dispara os agents em paralelo, cada um com a lista bruta de itens, para sua lente:

| Agent | Lente que devolve |
|---|---|
| `software-architect` + `tech-lead` | grafo de dependência técnica + flags de fundação / one-way-door |
| `product-manager` | Custo de Atraso por item (valor + urgência + risco) |
| `engineering-manager` | Job Size / esforço / capacity por item |
| `scrum-master` | topological sort + agrupamento em ondas + limite de WIP |

Depois a skill dispara `cosmo-coo` com os quatro retornos para **consolidar** na tabela final: ordem de linha (execução) + coluna Onda. Cosmo resolve conflito de lente (ex: valor alto x dependência não resolvida vence a dependência).

Subagent não dispara subagent: quem dispara cada agent é a thread principal (a skill); os agents devolvem dados, a skill/Cosmo consolidam.

### Passos do `--create`

1. Coletar os itens (do usuário; se vier de um doc, ler).
2. Perguntar só o essencial: caminho (sugerir `TODO.md` na raiz) e título do projeto.
3. Aplicar o gate anti-OE: **o Cosimo decide a abordagem** (thread direta vs time) pela complexidade.
4. Montar a tabela: thread direta (simples) OU **time coordenado pelo Cosmo** (complexa), conforme a decisão do Cosimo.
5. Escrever `TODO.md` com as 9 colunas, linhas em ordem de execução, Onda preenchida. Se houver INBOX / `inbox/`, drená-la (integrar os itens e esvaziar).

### `--reorder`

Reordena uma tabela existente (mesmo método e gate). Preserva IDs, Status e Estado Auditado; só recalcula ordem das linhas e a coluna Onda. **Drena a INBOX** (e `inbox/`): integra cada descoberta na ordenação e a remove da INBOX. Útil quando novas pendências entraram ou dependências mudaram.

### Gatilho de reordenação (proporcional ao tamanho e à repercussão)

Quando uma pendência NOVA entra, decidir entre **só anexar** ou **reordenar tudo**, proporcional ao tamanho da solicitação e ao impacto no projeto inteiro. **O Cosimo (Chief of Staff) decide a abordagem** (só anexar vs reordenar) pela complexidade/repercussão; quando reordena via time, **o Cosmo (COO) coordena a montagem** (dispara as lentes e consolida). Em caso dúbio sobre a repercussão, o Cosmo (COO) julga.

- **Só anexar** (sem reordenar): item pequeno, escopo local, sem criar dependência sobre itens já ordenados, não mexe em fundação nem one-way-door. Adicionar na Onda adequada (ou ao fim) e seguir.
- **Reordenar (`--reorder`, orquestra o time):** quando o item novo
  - cria ou altera dependência de itens existentes, ou
  - é fundação / decisão one-way-door (errar reordena tudo a jusante), ou
  - tem repercussão cross-módulo ou no projeto inteiro, ou
  - é grande o bastante para mudar o WSJF relativo de vários itens.

Regra de ouro: o custo de reordenar deve ser menor que o retrabalho que ele evita. Reordenação total NÃO é automática por padrão (anti-ruído); dispara pelos critérios acima ou sob comando explícito.

---

## Injecao automatica de testes e auditorias

Executa no INICIO de TODO comando (--create, --reorder, --show, --main), antes de
exibir/escrever a tabela. Garante que os testes nao-unitarios e auditorias aplicaveis
estejam planejados. Catalogo e regras: `references/catalogo-testes-auditorias.md`.

### Passos

1. **Detectar stack + caracteristicas**: Glob na raiz para sinais de arquivo; Grep/Read de deps e imports para sinais de conteudo (rede/API, protocolo, framework). Ver o reference.
2. **Calcular itens aplicaveis**: TST-* (T2-T15 podados; T1 SEMPRE fora) + AUD-* (podados).
3. **Garantir manuais do projeto**: se `./TESTES.md` ou `./AUDITORIAS.md` faltam, marca-los para criacao (do reference, podados). Nunca sobrescrever manual existente.
4. **Conferir a tabela** `TODO.md`: quais TST-*/AUD- ja existem (por ID).
5. Se **nada falta** (itens presentes e manuais existem): idempotente, NAO pergunta, NAO escreve. Segue o comando.
6. Se **falta algo**: rodar o fluxo de confirmacao abaixo.

### Fluxo de confirmacao (nunca silencioso)

PERGUNTA 1 (AskUserQuestion, recomendacao ALTA a favor):
> "Faltam testes/auditorias no planejamento deste projeto. Acrescentar agora?"
> Opcoes: [Acrescentar (fortemente recomendado)] | [Nao acrescentar]

- Acrescentar -> aplicar (secao "Aplicar") + avisar o que mudou. Segue o comando.
- Nao -> PERGUNTA 2 (reforco):
  > "Testes e auditoria sao Definition of Done: previnem retrabalho, vulnerabilidades
  >  (secrets, SQLi, CVE) e regressoes. Seguir mesmo assim sem eles?"
  > Opcoes: [Acrescentar agora (recomendado)] | [Seguir sem testes]
  - Acrescentar -> aplicar + avisar. Segue o comando.
  - Seguir sem -> executa o comando SEM testes; avisar:
    "OK. Pode acrescentar depois com: /tab_pendencias --add_tests_audit"

### Aplicar (criar manuais + injetar itens)

- Criar `./TESTES.md` e/ou `./AUDITORIAS.md` se faltarem (podados pro stack).
- Injetar na tabela apenas os IDs AUSENTES (idempotente):
  - **TST-*** -> `Grupo` = `Testes`; `Onda` = uma apos a ultima de implementacao; `Pre-requisito` = itens de implementacao cobertos (na pratica, a ultima onda funcional); `Status` = ⏳; `Estado Auditado` = `—`; `Descricao` referencia `TESTES.md`.
  - **AUD-*** -> `Grupo` = `Auditoria`; `Onda` = final, apos os testes; `Pre-requisito` = os TST-* + ultima onda de implementacao; `Status` = ⏳; `Estado Auditado` = `—`; `Descricao` referencia `AUDITORIAS.md`.
- Reaplicar a ordenacao (topological + WSJF + ondas) para encaixar os novos itens respeitando a ordem inviolavel.
- Avisar: "criei <arquivos>; injetei N testes + M auditorias nas ondas <...>".

### --add_tests_audit

Comando dedicado: pula as PERGUNTAS (o usuario ja pediu); roda "Aplicar" direto;
idempotente; avisa o que fez (ou "nada a fazer" se ja completo).

### Hook de TDD ausente

T1 sempre fora. Se o projeto NAO tem `.claude/tdd-guard.json`, avisar uma vez:
"TDD nao esta sob hook neste projeto; ative o hook ou inclua testes unitarios
manualmente." (nao bloqueia).

### Modo nao-interativo

Sem humano para responder o AskUserQuestion (ex.: invocacao por workflow/agente):
NAO injeta (respeita "nao silencioso"); executa o comando e emite aviso proeminente
recomendando `/tab_pendencias --add_tests_audit`.

---

## `--show` / `--main`

- **`--show`**: localizar `TODO.md` na raiz (depois `PLANNING.md`, depois perguntar). Exibir tabela **completa**, incluindo `✅`.
- **`--main`**: mesma localização, **filtrar fora** `✅`. Mostrar só ⏳ 🔄 🟡 💡 🎨 🔍, preservando a ordem (Onda) das pendentes.

### `--add`

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

### Fluxo agentivo de `--add` (agente julga, motor persiste)

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

### Concorrência e `inbox/` (TAB-CONC)

- **Dentro de uma orquestração multi-agent:** só o `main` altera a tabela.
  Subagente devolve `DISCOVERED_WORK`; main chama bridge + intake.
- **Sessões / worktrees independentes (sem orquestrador comum):** usar
  `tools/concurrent_inbox.write_discovery(root, session_id, slug, body_md)`
  → `inbox/YYYYMMDD-HHMMSS-<session>-<slug>.md`. Não é backlog normal.
- **Próxima sessão principal:** se `todo_health` emitir
  `TAB_CONCURRENT_INBOX_PRESENT` / `TAB_TRIAGE_REQUIRED` por `inbox/`,
  executar `--drain` (ou bridge+intake por arquivo) no próximo ponto seguro.
- **Escrita segura:** `run_intake`/`run_drain` em apply adquirem
  `tools/todo_lock.TodoWriteLock` (fcntl em POSIX; msvcrt em Windows;
  fallback exclusive-create com stale 120s). Lock reentrant no mesmo
  thread (drain aninha intake).
### `--drain` (TAB-INBOX-004)

Opera a INBOX como **exception queue**. Motor: `tools/todo_intake.py --drain`.

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

Health (`todo_health.py`) consome `session_signals.collect_signals` e imprime
as linhas `TAB_*` (ver secao **Sinais de frescor** e
`references/sinais-de-frescor.md`). `TAB_TRIAGE_REQUIRED` = classifiable **ou**
residual aged (cycles/idade) **ou** `inbox/` concorrente -- **nao**
`inbox_count>=3` so de leader frescos. Contagem de `needs-leader-decision`
fresco e separada; so o aged emite `TAB_LEADER_DECISION_AGED` (+ TRIAGE).

## `--audit`

Motor de auditoria estrutural do próprio `TODO.md` (`tools/todo_audit.py`, camada
núcleo genérico, decisão em
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):
roda offline, sem LLM/rede, sem orquestrar nenhum agent. Executa sob demanda; **não** faz parte da Injeção
automática de testes e auditorias acima (aquela cobre o *planejamento* do projeto
que usa a skill; `--audit` cobre a *integridade da própria tabela*).

- **Sempre read-only.** Nenhum caminho de código abre o `TODO.md` em modo de
  escrita, nem muta estado de git. A única escrita possível é a de `--output`
  (relatório opcional em arquivo à parte), e ela é bloqueada com erro (`exit 1`) se o
  caminho resolver para dentro do repositório auditado.
- **`--todo <caminho>`**: audita um arquivo fora do repositório corrente (não
  precisa estar no `cwd` nem no mesmo repositório git de quem invoca). Restrição
  fixa: o arquivo precisa se chamar exatamente `TODO.md` (mesma convenção de
  `todo_lib.find_todo`); qualquer outro nome sai com `exit 1` e mensagem explicando
  a restrição. Sem a flag, o comportamento é o mesmo de sempre: descoberta
  automática a partir do `cwd`, que precisa ser um repositório git.
- **`--profile core|casa`** e o arquivo `.tab_pendencias.ini` na raiz do repo
  auditado (seção `[profile]`, chave `name = casa`): perfil `core` é o default
  (ausência de arquivo ou de chave); `--profile` na linha de comando sobrepõe o
  arquivo para uma execução pontual. Config lido com `configparser` da stdlib
  (D-9/D-10 -- INI, escolha histórica; piso oficial Python >= 3.11, PYFLOOR-2).
  **A camada casa é aditiva, nunca substitutiva**: sob `casa` rodam os 11 checks
  do núcleo **mais** os 3 da casa (14 no total); quem não ativa `casa` não perde
  nenhum check do núcleo, só não ganha os 3 extras. Medido ao vivo: sob `core`
  (default), os 11
  checks do núcleo executam e cada check `profile = casa` é **declarado como não
  executado** nos avisos do motor (`"CHK-12 (convencao da casa) nao executado --
  perfil ativo = core. Habilite com --profile casa ou .tab_pendencias.ini
  [profile] name = casa."`, um por check pulado) -- nunca silenciado. Sob
  `--profile casa`, os 14 checks executam e nenhum aviso de check pulado
  aparece.
- **`--max-per-check N`** (default 5; `N<=0` = sem limite): amostra no máximo N
  achados por check no relatório impresso. Achados de severidade **CRÍTICO nunca
  são truncados**; o corte incide só sobre IMPORTANTE/COSMÉTICO, e o que ficou de
  fora é sempre contado e declarado na própria seção do check (nunca só
  descartado -- "no silent caps").
- **`--output <arquivo>`**: também grava o relatório nesse arquivo (além de
  imprimir no terminal). Nunca pode resolver para dentro do repositório auditado
  (aborta com `exit 1` se apontar para lá); use um caminho de scratchpad.
- **`-v` / `--verbose`**: acrescenta traceback completo quando um check ou a
  leitura do `TODO.md` falha (default: só tipo + mensagem da exceção).
- **Exit codes** (fixos, nenhum check inventa um novo): `0` = execução ok e zero
  achados; `1` = erro de execução (não é repositório git quando exigido, `TODO.md`
  ilegível, flag inválida ou desconhecida); `2` = execução ok e há 1+ achado, **de
  qualquer severidade, inclusive só COSMÉTICO**. Isto é o que permite usar
  `--audit` em automação/CI: um pipeline que quer tolerar cosmético filtra por
  severidade dentro do relatório, não pelo exit code.
- **Catálogo de checks hoje** (11 do núcleo + 3 da casa = 14 registrados;
  severidade indicada é o default do registro -- alguns checks emitem achados
  com severidade diferente conforme o caso concreto, ex.: `CHK-08` cobre tanto
  COSMÉTICO quanto IMPORTANTE). A coluna `Perfil` diz se o check roda sempre
  (`core`) ou só quando `casa` está ativo:

  | Check | Título | Severidade (default) | Perfil |
  |---|---|---|---|
  | `CHK-01` | ID duplicado | CRÍTICO | core |
  | `CHK-02` | nº de células ≠ cabeçalho (diagnóstico) | CRÍTICO | core |
  | `CHK-03` | Tabela fragmentada + span da canônica | CRÍTICO | core |
  | `CHK-04` | ncols divergente entre tabelas ID+Status | CRÍTICO | core |
  | `CHK-05` | Pré-requisito citando ID inexistente | IMPORTANTE | core |
  | `CHK-06` | Ciclo de dependência | CRÍTICO | core |
  | `CHK-07` | Onda inconsistente com a dependência | IMPORTANTE | core |
  | `CHK-08` | Status fora do vocabulário canônico | IMPORTANTE | core |
  | `CHK-09` | Claims obsoletas na Descrição (contra o git real) | IMPORTANTE | core |
  | `CHK-10` | Proposta do `todo_sync.py` (sem `--apply`) anexada | COSMÉTICO | core |
  | `CHK-11` | Reconciliação de contagem (`todo_health`) | CRÍTICO | core |
  | `CHK-12` | TST-*/AUD-* agendado antes do que cobre | CRÍTICO | **casa** |
  | `CHK-13` | INBOX: ID duplicado da tabela ou formato inválido | IMPORTANTE | **casa** |
  | `CHK-14` | Item de Wiki + doc para iniciante ausente na última onda | COSMÉTICO | **casa** |

  Os 3 checks de perfil `casa` moram em `tools/casa/chk_casa.py` (não mais
  vazio) e implementam, respectivamente, a ordem inviolável de teste/auditoria
  (ver "Testes e auditoria: ordem inviolavel" acima), a higiene da seção INBOX,
  e a regra da casa de item fixo de Wiki+doc-iniciante como última onda
  pós-tag.

  Alvo (`--todo`) fora de qualquer repositório git resolvível: `CHK-09`/`CHK-10`
  (os únicos que dependem de `git`) degradam sozinhos por achado
  ("desconhecido"/erro), e o motor soma um aviso sistêmico único explicando a
  causa comum, em vez de N achados soltos sem contexto.

### `--fix` (`tools/todo_fix.py`)

Motor do `--fix` (FIX-ENG, ADR-0001 seção c, FIX-ESCOPO-2): aplica **só** as
**duas** classes mecânicas e byte-preserving do escopo real --
`escapar_pipe_cru` (CHK-02) e `remover_fragmento_duplicado` (CHK-01) -- marcadas
`[auto-fixável]` pelos checks. Consolidar tabela (CHK-03/04) e reescrever claim
(CHK-09) ficam **fora** do auto-fix (movem linhas em arquivo de terceiro).
Regra: audit nunca marca `fixable=True` sem corretor no motor. **Nunca** muda
`Status`, nunca reordena, nunca toca branch/commit do repositório.

- **Default é dry-run.** Sem `--apply`, só mostra o plano (o que faria, com
  diff das linhas envolvidas) e nunca escreve.
- **`--apply <classe...>`**: aplica só as classes nomeadas (`escapar_pipe_cru`,
  `remover_fragmento_duplicado`), ou `--apply all` para todas as detectadas
  nesta execução -- confirmação sempre **separada por classe**, nunca um "sim"
  global implícito.
- **Precondição obrigatória**: a working tree do `TODO.md` tem que estar
  limpa (`git status --porcelain` vazio para o arquivo) antes de qualquer
  `--apply`; working tree suja, ou ausência de repositório git resolvível,
  aborta com `exit 1` sem tocar o arquivo.
- **Escrita sempre atômica**: arquivo temporário no mesmo diretório, prova de
  round-trip (linhas não tocadas byte-a-byte) e de contagem de itens
  ANTES de trocar o arquivo real (`os.replace`); qualquer falha na prova ou
  na escrita aborta sem deixar o `TODO.md` tocado.
- Uma correção marcada `[auto-fixável]` pelo `--audit`, mas cuja posição exata
  o motor de fix não consegue localizar sem ambiguidade (ex.: pipe cru fora
  de qualquer *code span*), aparece no plano como **não aplicável**, com o
  motivo -- o motor nunca escreve adivinhando.
- Exit codes (D-6): `0` = nada a corrigir; `1` = erro de execução (não é
  repositório git, `TODO.md` ilegível, working tree suja ao aplicar, falha de
  escrita); `2` = há 1+ correção disponível (mostrada em dry-run ou aplicada).

Regra fixa do líder: ao final de todo `--audit`, sugerir o `--fix` listando o
que faria. O engate conversacional (a sugestão automática dentro do relatório
de `--audit`) é de outra fatia; o motor (`todo_fix.build_plan`) já expõe o
hook necessário.

## Invocação sem argumento

- "mostrar pendências" / "o que falta" / "em que ordem" → `--main`
- "tabela completa" / "histórico" → `--show`
- "criar tabela" / "planejar passos" → `--create`
- "reordenar" / "minimizar retrabalho" / "sequenciar" → `--reorder`
- "acrescentar testes" / "adicionar auditoria" / "faltam testes" → `--add_tests_audit`
- "auditar a tabela" / "achar defeito na tabela" / "checar integridade do TODO" → `--audit`
- "corrigir a tabela" / "aplicar auto-fix" / "consertar pipes/duplicatas" → `--fix`

---

## Arquivo canônico

**A tabela é sempre `TODO.md` na raiz do projeto.** Única localização válida. Toda leitura e escrita em `TODO.md`. Se não existir, criar sem perguntar. Nunca usar `PLANNING.md` como destino.

## Registro no CLAUDE.md

Ao criar/confirmar o `TODO.md` num projeto, verificar se o `CLAUDE.md` da raiz já referencia o `TODO.md`. Se não, acrescentar (sem duplicar):

```
## Pendências
A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz (ordenada por execução, coluna Onda marca passos paralelizáveis).
```

## Integração

- Agents: `cosmo-coo` (orquestra), `software-architect`, `tech-lead`, `product-manager`, `engineering-manager`, `scrum-master`. Constelação em [[ORG]].
- Manuais: [[AGILE]] (WSJF, fluxo, WIP), [[CONTRACT]]. Ferramentas por agent: [[TOOLING]].
- Linguagem: pt-br.
