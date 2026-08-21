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

## Schema canônico (10 colunas)

```markdown
| WSJF | ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

A ordem das linhas (de cima para baixo) É a ordem de execução recomendada. A coluna `Onda` agrupa passos paralelizáveis.

### Ordem canônica do arquivo (INBOX antes, tabela por último)

O `TODO.md` tem esta ordem, de cima para baixo -- contrato de FORMA, detalhe normativo em `references/frescor-da-tabela.md` §5:

1. linha 1: título `#` do arquivo;
2. preâmbulo livre (prosa, legenda, critérios, notas de montagem);
3. seção **`## INBOX (...)`** -- a exception queue, **antes** da tabela;
4. (opcional) mais prosa/seções livres;
5. **a tabela canônica**;
6. **EOF logo após a última linha da tabela** -- nada vem depois dela.

**UMA tabela no arquivo, e só uma** -- sem qualificação: **qualquer segundo bloco `|...|` é violação**, tenha coluna `Status` ou não. Legenda, matriz, sumário, índice, contagem e scoring vão em **bullets ou lista**, nunca em tabela auxiliar. Proibido junto: **linha em branco dentro da tabela** -- em Markdown ela encerra a tabela ali (e cria um bloco novo). Motivo mecânico: a leitura **para no primeiro cabeçalho repetido**, então tudo que estiver numa segunda tabela com `Status` fica invisível para qualquer contagem, sem erro na tela (um backlog de 491 itens já se apresentou como 1); e a regra é literal, sem exceção para "tabela auxiliar inofensiva", porque toda tabela a mais é candidata a ser eleita por engano -- critério que exige inspecionar coluna se degrada na primeira exceção.

**Uma tabela de checklist por PROJETO**, e ela vive no `TODO.md` (contrato §5.0.1): nenhum outro arquivo do projeto carrega fila de trabalho (`TODO_ARCHIVE.md`, `AUDIT_FIND.md`, `PLANO.md` com coluna `Status`). Tabela em documento que **não é fila de trabalho** (índice de ADR com `Status = Aceito`, matriz de rotas, contagem) continua legítima -- o `--audit` (CHK-21) só acusa tabela com **ID + Status + status do vocabulário fechado**, e é desligável por `.tab_pendencias.ini` (`[audit] checklist_scan = off`).

**Forma do arquivo (o modelo da casa, detalhe em `references/frescor-da-tabela.md` §5.2):** a **linha 1** declara a estrutura em uma linha (`> **ESTRUTURA CANÔNICA DO ARQUIVO — NÃO QUEBRAR A TABELA:** ... **EOF** ... **Proibido:** segunda tabela; linha em branco **dentro** da tabela ...`), antes do título `#`; a tabela tem o heading próprio **`## TABELA UNIFICADA`** logo acima dela (o nome carrega a regra: unificada = uma só); e **checklists/sumários/material de referência vão em bullets no cabeçalho** (nunca em tabela: o arquivo tem um bloco `|...|` só). **O WSJF é a exceção:** o **valor calculado de cada item vive na coluna `WSJF`**, a primeira da tabela, e **não** em bullet no cabeçalho; o que fica no cabeçalho é só a **fórmula** (como se calcula), sob `### Scoring WSJF (referência — **não** é tabela de trabalho)` com a linha de escopo *"o status de trabalho vive só na tabela única"*. Isso é **forma**, não leitura: arquivo sem esses elementos continua válido -- eles existem para a regra ficar visível dentro do próprio arquivo, e para ninguém acrescentar coluna `Status` num bloco de referência.

**Mudou em 2026-08-19:** a INBOX ficava DEPOIS da tabela. Ela subiu porque "fim da tabela = fim do arquivo" é a invariante que ferramentas e guards de consumidor usam para acrescentar linha sem procurar onde a tabela acaba -- uma seção depois da tabela a tornava falsa por construção.

**Compatibilidade:** arquivo no formato **legado** (INBOX depois, ou qualquer texto após a tabela) continua **válido para LEITURA**, com aviso (`todo_lib.legacy_layout_warning`); os itens e entradas lidos são os mesmos. **Escrita e criação usam sempre a ordem nova.** Conversão mecânica, idempotente e byte-preserving:

```bash
python3 tools/todo_migrate_inbox.py --check    # diagnostica (exit 2 = legado)
python3 tools/todo_migrate_inbox.py --apply    # converte
```

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

A INBOX residual **nao** e a fila normal de descoberta: trabalho novo vai ao
intake (`--add`), e so o ambiguo / sem autoridade vira residual `[triage ...]`,
sem Onda nem WSJF. Proibicoes que valem sempre, sem abrir a referencia:
workers/subagentes **nao** escrevem na INBOX (devolvem `DISCOVERED_WORK` e o
main chama o intake); conflito de INBOX resolve **sempre por uniao, NUNCA
descartando linha**; **hub agregador** nao usa INBOX nem marcacao a mao (view
derivada -- `references/hub-agregador.md`); e `--drain` opera so a secao
`## INBOX` do `TODO.md`, nunca os arquivos `inbox/*.md`.

> Cascata de rota, local e formato do bullet residual, dreno e a fronteira entre
> `## INBOX` e o fallback `inbox/`: [`references/intake-e-inbox.md`](references/intake-e-inbox.md).

### Sinais de frescor (`TAB_*`)

Motor read-only `tools/session_signals.py`; adapter de hook
`tools/hooks/tab_pendencias_reminder.py`; `todo_health.py` imprime as mesmas
linhas sob demanda. Sinal `TAB_*` emitido e **acao obrigatoria da thread
principal**, nunca lembrete passivo -- e nenhum deles autoriza reordenar por
relogio.

> Os 7 sinais (`TODO_CREATE_REQUIRED`, `STATUS_SYNC_RECOMMENDED`,
> `TRIAGE_REQUIRED`, `CONCURRENT_INBOX_PRESENT`, `LEADER_DECISION_AGED`,
> `VERIFICATION_AGING`, `INTAKE_RECOVERY_REQUIRED`) com gatilho, acao da thread,
> roteamento SessionStart/UserPromptSubmit e envelhecimento residual:
> [`references/sinais-de-frescor.md`](references/sinais-de-frescor.md).

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
5. Escrever `TODO.md` com as 10 colunas, linhas em ordem de execução, Onda preenchida. Se houver secao residual `## INBOX` no TODO, drená-la (integrar e limpar residual). Se houver `inbox/*.md` concurrent, processar em fluxo proprio (`list_pending` + bridge+intake por arquivo) -- o motor de `--drain`/`--create`/`--reorder` **nao** apaga esses arquivos.

### `--reorder`

Reordena uma tabela existente (mesmo método e gate). Preserva IDs, Status e Estado Auditado; só recalcula ordem das linhas e a coluna Onda. **Drena a secao residual `## INBOX` do TODO**: integra cada descoberta na ordenação e remove as linhas residual. Arquivos em `inbox/` **nao** sao esvaziados pelo reorder/drain automatico; exigem fluxo de fallback (`list_pending` + main processa `DISCOVERED_WORK` via bridge+intake). Útil quando novas pendências entraram ou dependências mudaram.

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

Entrada de item novo no pipeline de intake (ADR-0002). Motor
`tools/todo_intake.py` (offline, stdlib, **sem LLM**). Fronteira fixa: **o
agente julga** (prosa, impacto, autoridade) e preenche flags booleanas; **o
nucleo nao infere de prosa**, so classifica por flag e grava. Cascata, primeiro
que casa vence: `DUPLICATE` -> `NEEDS_TRIAGE` -> `NEEDS_LEADER_DECISION` ->
`FULL_REORDER` (fundacao) -> `LOCAL_INTEGRATION` (L0) -> `SCOPED_REORDER` ->
`FULL_REORDER` (default). Nunca jogar L0 na INBOX por conveniencia.

Gates que abortam o `--apply` sem escrever: working tree do `TODO.md` suja;
INBOX residual com item **classificavel** (`classifiable_inbox_present` --
drain-first); equivalencia fora do subgrafo violada (`scoped_equivalence_failed`).
`Status` de linha pre-existente nunca muda.

> Contratos de L0/SCOPED/FULL, regra de duplicata, journal write-ahead,
> `scoped_reorder_max_fraction`, retomada apos decisao do lider e a CLI:
> [`references/intake-e-inbox.md`](references/intake-e-inbox.md).

### Fluxo agentivo de `--add` (agente julga, motor persiste)

Subagentes/workers **nao editam `TODO.md`**: devolvem o bloco `DISCOVERED_WORK`
(`source_item` / `description` / `evidence` / `known_dependencies` /
`blast_radius`) e a thread principal converte com `tools/intake_agent_bridge.py`
(stdlib, sem LLM) e chama o intake.

> Formato do bloco e mapa `blast_radius` -> flags: secao "Fluxo agentivo" de
> [`references/intake-e-inbox.md`](references/intake-e-inbox.md).

### Concorrência e `inbox/` (TAB-CONC)

Dentro de uma orquestracao multi-agent, **so o `main` altera a tabela**.
Sessoes/worktrees independentes escrevem em `inbox/*.md` via
`tools/concurrent_inbox.py`: nao e backlog normal, e o `--drain` **nao** le nem
apaga esses arquivos. Escrita em apply sempre sob `tools/todo_lock.TodoWriteLock`.

> Receita de processamento por arquivo e detalhe do lock: secao "Concorrencia"
> de [`references/intake-e-inbox.md`](references/intake-e-inbox.md).

### `--drain` (TAB-INBOX-004)

Opera **somente** a secao residual `## INBOX` do `TODO.md`
(`tools/todo_intake.py --drain`). Item classificavel sem julgamento nao e
adivinhado: dry-run lista e sai `2`; `--apply` sem `--judgments-json` sai `1`.
`needs-leader-decision` **nunca** auto-integra, so envelhece. Pos-condicao de
apply verde: `classifiable_inbox_count == 0`.

> CLI, schema dos judgments (`integrate` / `split` / `keep`) e ciclo de
> envelhecimento: secao "`--drain`" de
> [`references/intake-e-inbox.md`](references/intake-e-inbox.md).

## `--audit`

Auditoria estrutural do proprio `TODO.md` (`tools/todo_audit.py`): offline, sem
LLM/rede, sem orquestrar agent; **nao** faz parte da Injecao automatica de testes
e auditorias acima. **Sempre read-only** -- nenhum caminho abre o `TODO.md` para
escrita nem muta estado de git; `--output` e a unica escrita possivel e e
**bloqueada (`exit 1`) se resolver para dentro do repositorio auditado**.

Exit codes fixos, nenhum check inventa outro: `0` = ok e zero achados; `1` = erro
de execucao; `2` = ok e ha 1+ achado, **de qualquer severidade, inclusive so
COSMETICO** (por isso automacao filtra por severidade no relatorio, nunca pelo
exit code). Achado CRITICO **nunca** e truncado por `--max-per-check`, e o que
ficou de fora e sempre contado e declarado ("no silent caps"). O perfil `casa` e
**aditivo, nunca substitutivo** (14 checks do nucleo + 3 da casa); sob `core`
cada check `casa` e declarado como nao executado, nunca silenciado.

> Catalogo dos 17 checks (CHK-01..14, CHK-19..21) com severidade e perfil, flags
> (`--todo`, `--profile`, `--max-per-check`, `--output`, `-v`) e degradacao fora
> de repositorio git: [`references/audit-e-fix.md`](references/audit-e-fix.md).

### `--fix` (`tools/todo_fix.py`)

Aplica **so** as duas classes mecanicas e byte-preserving do escopo real:
`escapar_pipe_cru` (CHK-02) e `remover_fragmento_duplicado` (CHK-01). **Nunca**
muda `Status`, nunca reordena, nunca toca branch/commit. **Default e dry-run**;
`--apply` e confirmado **classe a classe**, nunca por um "sim" global implicito.
Precondicao obrigatoria: working tree do `TODO.md` limpa (suja, ou sem repo git
resolvivel, aborta com `exit 1` sem tocar o arquivo). Escrita sempre atomica, com
prova de round-trip antes do `os.replace`; correcao cuja posicao o motor nao
localiza sem ambiguidade sai no plano como **nao aplicavel** -- o motor nunca
escreve adivinhando. Regra fixa do lider: todo `--audit` termina sugerindo o
`--fix` com o que faria.

> Fora do auto-fix por desenho: consolidar tabela (CHK-03/04) e reescrever claim
> (CHK-09). Exit codes e detalhe do plano:
> [`references/audit-e-fix.md`](references/audit-e-fix.md).

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
