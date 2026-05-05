---
name: tab_pendencias
description: Gerencia tabela de pendências/planejamento de projetos. Use esta skill sempre que o usuário pedir para criar tabela de pendências, mostrar pendências, mostrar tabela completa, mostrar tarefas, listar pendências, atualizar status de tarefa, ou invocar com /tab_pendencias. Argumentos: --create, --show, --main.
argument-hint: --create | --show | --main
allowed-tools: [Read, Write, Edit, Glob]
---

# tab_pendencias

Skill para criar e exibir tabelas de planejamento/pendências de projetos.

## Argumentos

O usuário invocou com: $ARGUMENTS

## Estrutura padrão da tabela

```markdown
| ID | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

### Valores válidos por coluna

- **Prioridade**: Alta / Média / Baixa
- **Pré-requisito**: `—` (nenhum) ou ID(s) de tarefa(s) que precisam estar concluídas antes desta (ex: `F1.4`, `F2.1, F2.2`)
- **Dificuldade**: Alta / Média / Baixa
- **Status** (usar sempre símbolo + texto, ex: `✅ Concluído`):

| Valor na célula | Significado |
|:---|:---|
| ✅ Concluído | Tarefa finalizada |
| 🔄 Em andamento | Trabalho em progresso |
| 🟡 Parcial | Feito em parte |
| ⏳ Pendente | Não iniciado |
| 💡 Decisão tomada | Abordagem definida, implementação futura |
| 🎨 Pendente design | Aguarda spec/brainstorm |
| 🔍 Pendente verificação | Implementado, aguarda validação |

- **Estado Auditado**: `—` (não auditado) | `✓` (auditado e aprovado) | `⚠` (auditado com ressalvas)

## Comportamento por argumento

### `--create`

Cria uma nova tabela vazia com o cabeçalho padrão. Perguntar ao usuário:
1. Onde salvar o arquivo (caminho) — sugerir `TODO.md` na raiz do projeto se não especificado
2. Qual o título do projeto para o cabeçalho `# Projeto — Planejamento`

Depois criar o arquivo com o cabeçalho e a tabela vazia pronta para receber itens.

### `--show`

Localizar o arquivo de tabela do projeto atual (procurar `TODO.md` na raiz, depois `PLANNING.md`, depois perguntar ao usuário). Exibir a tabela **completa** — incluindo tarefas com Status `Concluído`.

### `--main`

Localizar o arquivo de tabela (mesma lógica do `--show`). Exibir a tabela **filtrando fora** as linhas com Status `✅`. Mostrar apenas: ⏳ 🔄 🟡 💡 🎨 🔍.

## Invocação sem argumento

Se invocado sem argumento (`/tab_pendencias` puro) ou com linguagem natural sem especificação clara:
- "mostrar pendências" / "mostrar tarefas" / "o que falta" → comportamento de `--main`
- "tabela completa" / "mostrar tudo" / "histórico completo" → comportamento de `--show`
- "criar tabela" / "nova tabela de pendências" → comportamento de `--create`

## Ao adicionar itens à tabela

Quando o usuário pedir para adicionar um item, usar o formato:
```
| ID | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
```

O ID deve seguir o padrão do projeto (ex: NL-26 se os anteriores são NL-XX).

## Arquivo canônico

**O arquivo de tabela é sempre `TODO.md` na raiz do projeto.** Esta é a única localização válida.

- Toda leitura lê de `TODO.md`
- Toda escrita (criação, adição de itens, atualização de status) salva em `TODO.md`
- Se `TODO.md` não existir, criá-lo automaticamente sem perguntar
- Nunca usar `PLANNING.md` ou outro arquivo como destino

## Registro no CLAUDE.md

Sempre que criar ou confirmar o uso do `TODO.md` num projeto (via `--create` ou primeiro uso de `--show`/`--main`), verificar se o `CLAUDE.md` da raiz do projeto já contém uma referência ao `TODO.md`. Se não contiver, acrescentar a seguinte linha na seção mais adequada (ou ao final):

```
## Pendências
A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz.
```

Nunca duplicar — verificar antes de escrever.
