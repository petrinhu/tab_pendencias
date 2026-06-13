---
name: tab_pendencias
description: Cria e gerencia tabela de pendências/planejamento ORDENADA para minimizar retrabalho. No --create (e --reorder) orquestra um time de agents (Cosmo/COO coordena software-architect + tech-lead + product-manager + engineering-manager + scrum-master) para sequenciar por dependência (topological) e valor (WSJF), com coluna "Onda" sinalizando passos de igual valor paralelizáveis. Use sempre que o usuário pedir criar/mostrar/atualizar tabela de pendências, planejar passos, ordenar backlog, "o que falta", "em que ordem fazer", ou invocar /tab_pendencias. Argumentos: --create, --reorder, --show, --main.
argument-hint: --create | --reorder | --show | --main
allowed-tools: [Read, Write, Edit, Glob, Agent, TodoWrite]
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
- **Dificuldade**: Alta / Média / Baixa (usada como Job Size no WSJF).
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
| ID | Item | Valor (1-20) | Criticidade (1-20) | Redução de Risco (1-20) | CoD | Job Size (1-20) | WSJF | Rank |
```

`CoD = Valor + Criticidade + Redução de Risco`; `WSJF = CoD / Job Size`. Rank = ordem decrescente de WSJF. Em projeto pequeno (solo/early), o WSJF pode ser qualitativo (sem a tabela completa), respeitando o anti-OE.

### Testes e auditoria: ordem inviolavel (TDD + shift-left)

- **Teste unitario (T1) = TDD:** ride COM o item de implementacao (escrito antes/junto do codigo), garantido pelo hook de TDD (tdd_guard/tdd_runner). **NAO vira item** na tabela; nao criar "escrever testes unitarios" como passo solto.
- **Demais testes (T2-T15) sao downstream:** estatica, integracao, e2e, seguranca (secrets, SQLi, CVE), memoria, pre-CI. Nao existem antes do sistema; entram como itens de fechamento (`TST-*`) numa onda APOS a implementacao. Sao injetados pelo fluxo "Injecao automatica de testes e auditorias".
- **Auditoria e downstream de codigo+teste:** todo item `AUD-*` tem `Pre-requisito` = os itens de codigo+teste que audita; cai numa Onda POSTERIOR aos testes.
- **Invariante:** nunca agendar teste/auditoria antes do que ele cobre. Se a ordenacao produzir isso, a dependencia esta errada (corrigir o `Pre-requisito`).

---

## `--create` e `--reorder` (orquestrado)

### Gate anti over-engineering (sempre primeiro)

Calibrar pelo porte (ver `cosimo-chief-of-staff` / [[ORG]]):
- **Tabela pequena/simples** (até ~8 itens, projeto solo/pessoal): **NÃO** spawnar o time. A própria thread aplica o método (topological + WSJF + ondas) e escreve. Anti-OE.
- **Tabela grande/complexa** (muitos itens, dependências cruzadas, cross-funcional): orquestrar o time abaixo.

### Orquestração (tabela grande)

Cosmo (COO) coordena. A skill (thread principal) dispara os agents em paralelo, cada um com a lista bruta de itens, para sua lente:

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
3. Aplicar o gate anti-OE.
4. Ordenar pelo método (direto ou via time).
5. Escrever `TODO.md` com as 9 colunas, linhas em ordem de execução, Onda preenchida.

### `--reorder`

Reordena uma tabela existente (mesmo método e gate). Preserva IDs, Status e Estado Auditado; só recalcula ordem das linhas e a coluna Onda. Útil quando novas pendências entraram ou dependências mudaram.

### Gatilho de reordenação (proporcional ao tamanho e à repercussão)

Quando uma pendência NOVA entra, decidir entre **só anexar** ou **reordenar tudo**, proporcional ao tamanho da solicitação e ao impacto no projeto inteiro. Em caso dúbio ou grande, quem julga a repercussão é `cosmo-coo` (COO).

- **Só anexar** (sem reordenar): item pequeno, escopo local, sem criar dependência sobre itens já ordenados, não mexe em fundação nem one-way-door. Adicionar na Onda adequada (ou ao fim) e seguir.
- **Reordenar (`--reorder`, orquestra o time):** quando o item novo
  - cria ou altera dependência de itens existentes, ou
  - é fundação / decisão one-way-door (errar reordena tudo a jusante), ou
  - tem repercussão cross-módulo ou no projeto inteiro, ou
  - é grande o bastante para mudar o WSJF relativo de vários itens.

Regra de ouro: o custo de reordenar deve ser menor que o retrabalho que ele evita. Reordenação total NÃO é automática por padrão (anti-ruído); dispara pelos critérios acima ou sob comando explícito.

---

## `--show` / `--main`

- **`--show`**: localizar `TODO.md` na raiz (depois `PLANNING.md`, depois perguntar). Exibir tabela **completa**, incluindo `✅`.
- **`--main`**: mesma localização, **filtrar fora** `✅`. Mostrar só ⏳ 🔄 🟡 💡 🎨 🔍, preservando a ordem (Onda) das pendentes.

## Invocação sem argumento

- "mostrar pendências" / "o que falta" / "em que ordem" → `--main`
- "tabela completa" / "histórico" → `--show`
- "criar tabela" / "planejar passos" → `--create`
- "reordenar" / "minimizar retrabalho" / "sequenciar" → `--reorder`

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
