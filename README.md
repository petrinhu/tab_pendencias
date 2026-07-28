# tab_pendencias

![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![Type](https://img.shields.io/badge/type-Claude%20Code%20Skill-blue)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Language](https://img.shields.io/badge/lang-pt--br%20%2F%20en-lightgrey)
![File](https://img.shields.io/badge/canonical-TODO.md-yellow)

---

## Português (pt-br)

Skill do Claude Code que gerencia a tabela de pendências/planejamento de projetos no padrão `TODO.md` tabular: cabeçalho fixo, símbolos de status visuais, dependências por ID, auditoria opcional.

### Instalação

```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
git clone https://github.com/petrinhu/tab_pendencias.git
```

Auto-discovered pelo Claude Code. Trigger automático em frases como "criar tabela", "mostrar pendências", "mostrar tarefas", "o que falta", "histórico completo", "atualizar status".

Manual via tool `Skill`:
```
Skill: tab_pendencias
```

Ou comando slash: `/tab_pendencias [--create | --show | --main]`

### Estrutura padrão da tabela

```markdown
| ID | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

### Valores válidos

| Coluna | Valores |
|---|---|
| **Prioridade** | Alta / Média / Baixa |
| **Pré-requisito** | `—` ou ID(s) (`F1.4`, `F2.1, F2.2`) |
| **Dificuldade** | Alta / Média / Baixa |
| **Estado Auditado** | `—` (não auditado) / `✓` (aprovado) / `⚠` (com ressalvas) |

### Status (símbolo + texto)

| Valor | Significado |
|---|---|
| ✅ Concluído | Tarefa finalizada |
| 🔄 Em andamento | Trabalho em progresso |
| 🟡 Parcial | Feito em parte |
| ⏳ Pendente | Não iniciado |
| 💡 Decisão tomada | Abordagem definida, implementação futura |
| 🎨 Pendente design | Aguarda spec/brainstorm |
| 🔍 Pendente verificação | Implementado, aguarda validação |

### Argumentos

| Argumento | Comportamento |
|---|---|
| `--create` | Cria nova tabela vazia em `TODO.md` na raiz do projeto |
| `--show` | Exibe tabela completa (incluindo `✅ Concluído`) |
| `--main` | Exibe só pendentes (filtra fora `✅`) |

Sem argumento, usa linguagem natural: "mostrar pendências" → `--main`, "tabela completa" → `--show`, "criar tabela" → `--create`.

## Testes e auditorias automaticos

Em qualquer comando, a skill verifica se os testes nao-unitarios (T2-T15) e as
auditorias aplicaveis ao stack do projeto estao no planejamento. Se faltam, ela
pergunta (com recomendacao alta) se deve acrescentar; recusando duas vezes, segue
sem eles e lembra do comando `--add_tests_audit` para incluir depois.

- O teste unitario (TDD) NAO entra na tabela: fica a cargo do hook de TDD.
- Os manuais `./TESTES.md` e `./AUDITORIAS.md` sao criados na raiz do projeto
  (podados pro stack) quando faltam, e nunca sobrescritos se ja existem.
- Os itens entram como `TST-*` (testes, apos a implementacao) e `AUD-*` (auditorias,
  nas ondas finais), de forma idempotente.

Comando dedicado: `/tab_pendencias --add_tests_audit` injeta direto, sem perguntar.

### Arquivo canônico

**`TODO.md` na raiz do projeto** é a única localização válida. Skill nunca cria `PENDENCIAS.md`, `TAREFAS.md` ou `BACKLOG.md` paralelos.

### Integração com `CLAUDE.md`

No primeiro uso num projeto, a skill verifica se o `CLAUDE.md` da raiz já referencia `TODO.md`. Se não, acrescenta:

```markdown
## Pendências
A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz.
```

### Licença

[GPL-3.0-or-later](LICENSE): software livre -- uso, modificação, compartilhamento e uso comercial permitidos, desde que obras derivadas distribuídas mantenham a mesma licença (copyleft).

### Autor

Petrus Silva Costa.

---

## English (en-intl)

Claude Code skill that manages the project pendencies/planning table in `TODO.md` tabular standard: fixed header, visual status symbols, ID-based dependencies, optional audit column.

### Installation

```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
git clone https://github.com/petrinhu/tab_pendencias.git
```

Auto-discovered by Claude Code. Auto-triggers on phrases like "create table", "show pendencies", "show tasks", "what's left", "full history", "update status".

Manual via `Skill` tool:
```
Skill: tab_pendencias
```

Or slash command: `/tab_pendencias [--create | --show | --main]`

### Standard table structure

```markdown
| ID | Group | Technical Description | Priority | Prerequisite | Difficulty | Status | Audit State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

### Valid values

| Column | Values |
|---|---|
| **Priority** | High / Medium / Low (Alta / Média / Baixa) |
| **Prerequisite** | `—` or ID(s) (`F1.4`, `F2.1, F2.2`) |
| **Difficulty** | High / Medium / Low |
| **Audit State** | `—` (not audited) / `✓` (approved) / `⚠` (with caveats) |

### Status (symbol + text, in pt-br)

| Value | Meaning |
|---|---|
| ✅ Concluído | Task completed |
| 🔄 Em andamento | Work in progress |
| 🟡 Parcial | Partially done |
| ⏳ Pendente | Not started |
| 💡 Decisão tomada | Approach defined, implementation deferred |
| 🎨 Pendente design | Awaiting spec/brainstorm |
| 🔍 Pendente verificação | Implemented, awaiting validation |

### Arguments

| Argument | Behavior |
|---|---|
| `--create` | Creates empty table at `TODO.md` in project root |
| `--show` | Displays full table (including `✅ Concluído`) |
| `--main` | Displays only pending items (filters out `✅`) |

Without argument, uses natural language: "show pendencies" → `--main`, "full table" → `--show`, "create table" → `--create`.

### Canonical file

**`TODO.md` in project root** is the only valid location. Skill never creates `PENDENCIAS.md`, `TAREFAS.md`, or `BACKLOG.md` parallels.

### `CLAUDE.md` integration

On first use in a project, the skill checks whether root `CLAUDE.md` already references `TODO.md`. If not, appends:

```markdown
## Pendências
A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz.
```

### License

[GPL-3.0-or-later](LICENSE): free software -- use, modification, sharing, and commercial use permitted, provided derivative works that are distributed remain under the same license (copyleft).

### Author

Petrus Silva Costa.
