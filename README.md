# tab_pendencias

![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![Type](https://img.shields.io/badge/type-Claude%20Code%20Skill-blue)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Language](https://img.shields.io/badge/lang-pt--br%20%2F%20en-lightgrey)
![File](https://img.shields.io/badge/canonical-TODO.md-yellow)

---

## Português (pt-br)

Skill do Claude Code que gerencia a tabela de pendências/planejamento de projetos no
padrão `TODO.md` tabular: cabeçalho fixo, ordem de execução (dependência + valor),
símbolos de status visuais, auditoria opcional.

> **Sobre esta seção:** o que está aqui é o que já é comportamento fechado e
> verificado no código. O comando `--audit`/`--fix` (auditoria estrutural da própria
> tabela e correção mecânica de defeitos) está em implementação; a documentação
> detalhada dele entra quando as fatias que o constroem fecharem. Não documentamos
> aqui nada que ainda não foi verificado no código.

### Duas camadas: núcleo genérico e convenções da casa

Este projeto tem duas camadas com fronteira explícita (ver
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):

| Camada | O que é | Dependências |
|---|---|---|
| **Núcleo genérico** | Parser da tabela, `--audit`, `--fix`, sincronização/saúde/frescor (`tools/`) | Só `git` + `python3`. Funciona para qualquer usuário, qualquer projeto. |
| **Convenções da casa** | Orquestração da montagem/reordenação por um time de agents (`cosmo-coo`, `software-architect`, `tech-lead`, `product-manager`, `engineering-manager`, `scrum-master`), item fixo de Wiki + doc para iniciante ao fim de projeto, wikilinks (`[[ORG]]`, `[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]`) que só resolvem no vault de quem escreveu essas convenções | **Opt-in**, ativado por `.tab_pendencias.ini` na raiz do repo onde a tabela vive (seção `[profile]`, chave `name = casa`). Ausência do arquivo (ou da chave) = perfil `core`, sempre o mais restrito por padrão. |

Um terceiro que clona o repo com só `git` e `python3` usa o núcleo inteiro sem
precisar de nenhum agent, wikilink ou convenção específica de ninguém.

### Instalação

```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
git clone https://github.com/petrinhu/tab_pendencias.git
```

Auto-discovered pelo Claude Code. Trigger automático em frases como "criar tabela",
"mostrar pendências", "mostrar tarefas", "o que falta", "histórico completo",
"atualizar status".

Manual via tool `Skill`:
```
Skill: tab_pendencias
```

Ou comando slash: `/tab_pendencias [--create | --reorder | --show | --main | --add_tests_audit]`

### Matriz de instalação e degradação

Nem toda dependência é obrigatória. A tabela abaixo mostra o que você perde em cada
cenário, para nunca ficar surpreso em silêncio:

| Cenário | O que continua funcionando | O que se perde |
|---|---|---|
| Sem a constelação de agents (`cosmo-coo` e demais) | `--create`/`--reorder` rodam em thread direta, aplicando o mesmo método (topological + WSJF + ondas) sem orquestrar o time | Só a divisão de trabalho em lentes paralelas (arquitetura, valor, esforço, ondas) por agents distintos; o resultado (a tabela ordenada) é o mesmo objetivo, calculado por uma única thread |
| Sem os manuais do vault (`[[ORG]]`, `[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]`) | Todo o núcleo | Os wikilinks viram texto morto (não resolvem a nenhum documento); são referência de convenção da casa, não do núcleo |
| Sem `python3` | A parte agent-driven da skill (`--create`, `--reorder`, `--show`, `--main` via Claude Code) | Os scripts mecânicos de `tools/` (sync, health, freshness, e os hooks de git que os disparam) |
| Windows sem Git for Windows | A parte agent-driven da skill (não depende de shell) | O sync mecânico via git hook (`tools/hooks/`, shims POSIX que dependem de um shell, no Windows o que vem com o Git for Windows). O `--audit`/`--fix`/`--create`/`--reorder` continuam disponíveis chamados diretamente, sem depender do hook. |

### Multiplataforma (cross-platform)

O núcleo (`tools/`) é Python puro sem dependências fora da stdlib, sem hardcode de
separador de caminho POSIX e sem assumir encoding/newline padrão do sistema
operacional. A suíte roda no CI em **cinco ambientes**: Ubuntu e Windows nativos, mais
Debian, Fedora e Arch em container. Versões de Python medidas de fábrica nesses
ambientes: Debian 12 = 3.11.2, Fedora 41 = 3.13.9, Arch = 3.14.6. A configuração
opcional (`.tab_pendencias.ini`) usa o formato INI, lido com `configparser` da stdlib,
escolhido deliberadamente em vez de TOML para não exigir Python 3.11+ (`tomllib`
só existe a partir dessa versão) como pré-requisito do núcleo.

### Estrutura padrão da tabela (9 colunas)

```markdown
| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

A ordem das linhas (de cima para baixo) é a ordem de execução recomendada. A coluna
`Onda` agrupa passos de igual valor que podem rodar em paralelo. Tabelas legadas de
8 colunas (sem `Onda`) continuam sendo lidas corretamente por `--show`/`--main`; o
parser localiza o cabeçalho pelo nome das colunas, nunca por uma contagem fixa.

### Valores válidos

O símbolo de célula vazia é o travessão tipográfico (Unicode U+2014); ele aparece
literalmente nas células de `Onda`, `Pré-requisito` e `Estado Auditado` quando não
há valor a preencher.

| Coluna | Valores |
|---|---|
| **Onda** | `W1`, `W2`, `W3`, ... (leva de execução); célula vazia para itens concluídos ou fora do fluxo |
| **Prioridade** | Alta / Média / Baixa |
| **Pré-requisito** | célula vazia (nenhum) ou ID(s) (`F1.4`, `F2.1, F2.2`) |
| **Dificuldade** | Alta / Média / Baixa |
| **Estado Auditado** | célula vazia (não auditado) / `✓` (aprovado) / `⚠` (com ressalvas) |

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
| `--create` | Cria nova tabela em `TODO.md` na raiz do projeto, ordenada por dependência e valor |
| `--reorder` | Recalcula a ordem das linhas e a coluna `Onda` de uma tabela existente, preservando ID/Status/Estado Auditado |
| `--show` | Exibe tabela completa (incluindo `✅ Concluído`) |
| `--main` | Exibe só pendentes (filtra fora `✅`) |
| `--add_tests_audit` | Acrescenta itens de teste/auditoria aplicáveis ao stack, sem perguntar |

Sem argumento, usa linguagem natural: "mostrar pendências" para `--main`, "tabela
completa" para `--show`, "criar tabela" para `--create`, "reordenar"/"minimizar
retrabalho" para `--reorder`.

### `--audit` e `--fix` (em implementação)

Decisões já fechadas para estes dois comandos (ver ADR-0001 linkado acima):

- `--audit` é **sempre read-only**: nunca escreve no `TODO.md`, nunca muda estado de
  git.
- `--fix` aplica **só** correção mecânica e byte-preserving (ex.: escapar `|` cru,
  remover fragmento duplicado, consolidar tabela fragmentada preservando
  ID/Status/Estado Auditado). Nunca muda `Status`, nunca reordena, nunca toca
  branch/commit.
- **Exit codes fixos**: `0` = execução ok, zero achados; `1` = erro de execução;
  `2` = execução ok, com pelo menos um achado (de qualquer severidade).

O restante do comportamento (lista de checks, formato do relatório, opções de CLI)
ainda está sendo implementado e será documentado aqui quando fechar.

## Testes e auditorias automáticos

Em qualquer comando, a skill verifica se os testes não-unitários (T2-T15) e as
auditorias aplicáveis ao stack do projeto estão no planejamento. Se faltam, ela
pergunta (com recomendação alta) se deve acrescentar; recusando duas vezes, segue
sem eles e lembra do comando `--add_tests_audit` para incluir depois.

- O teste unitário (TDD) não entra na tabela: fica a cargo do hook de TDD.
- Os manuais `./TESTES.md` e `./AUDITORIAS.md` são criados na raiz do projeto
  (podados pro stack) quando faltam, e nunca sobrescritos se já existem.
- Os itens entram como `TST-*` (testes, após a implementação) e `AUD-*` (auditorias,
  nas ondas finais), de forma idempotente.

Comando dedicado: `/tab_pendencias --add_tests_audit` injeta direto, sem perguntar.

### Arquivo canônico

**`TODO.md` na raiz do projeto** é a única localização válida. Skill nunca cria
`PENDENCIAS.md`, `TAREFAS.md` ou `BACKLOG.md` paralelos.

### Sincronização mecânica (opcional, núcleo genérico)

Além da skill (planejamento via agent), o repo traz scripts locais e determinísticos
em [`tools/`](tools/README.md), sem LLM/agent, para manter o `TODO.md` sincronizado
durante o sprint:

- `python3 tools/todo_sync.py [--apply]`: avança itens `⏳`/`🔄` para `🔍` a partir
  dos IDs citados em commits que tocaram trabalho substantivo. Nunca atribui `✅`,
  nunca reordena.
- `python3 tools/todo_health.py`: relatório de itens presos em `🔍`, tamanho da
  INBOX e adesão à convenção de citar ID no commit.
- Hook de git em `tools/hooks/` (opcional, cross-platform): aviso pós-commit, nunca
  bloqueia. Detalhe de instalação e de degradação por sistema operacional em
  [`tools/README.md`](tools/README.md).

Estes scripts são um acelerador; sem eles a convenção de frescor continua valendo à
mão (ver [`references/frescor-da-tabela.md`](references/frescor-da-tabela.md)).

### Integração com `CLAUDE.md`

No primeiro uso num projeto, a skill verifica se o `CLAUDE.md` da raiz já referencia
`TODO.md`. Se não, acrescenta:

```markdown
## Pendências
A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz (ordenada
por execução, coluna Onda marca passos paralelizáveis).
```

### Layout do repositório

```
SKILL.md                -- definicao da skill (fonte canonica do schema e do fluxo)
TESTES.md                -- catalogo de testes deste proprio projeto
AUDITORIAS.md             -- catalogo de auditorias deste proprio projeto
docs/adr/                 -- Architecture Decision Records
references/               -- documentos normativos (frescor da tabela, catalogo de testes/auditorias)
tools/                    -- nucleo generico: parser, sync, health, freshness (so stdlib)
tools/hooks/               -- shims de git hook (POSIX sh) + script de encadeamento
tools/ci/                  -- guards usados pelo CI (mesmos scripts rodam localmente)
tests/                    -- suite pytest (inclui corpus sintetico de defeitos)
```

### Rodando a suíte de testes

```bash
python3 -m venv .venv && source .venv/bin/activate   # Linux/macOS
pip install -r requirements-dev.txt
python3 -m pytest tests/ -v
```

No Windows, ative o venv com `.venv\Scripts\activate` antes do `pip install`.

### Licença

[GPL-3.0-or-later](LICENSE): software livre, uso, modificação, compartilhamento e
uso comercial permitidos, desde que obras derivadas distribuídas mantenham a mesma
licença (copyleft).

### Autor

Petrus Silva Costa.

---

## English (en-intl)

Claude Code skill that manages the project pendencies/planning table in `TODO.md`
tabular standard: fixed header, execution order (dependency + value), visual status
symbols, optional audit column.

> **About this section:** what's documented here is behavior already closed and
> verified in code. The `--audit`/`--fix` command (structural audit of the table
> itself and mechanical defect fixing) is under implementation; detailed docs for it
> land once the slices that build it close. We never document behavior the code
> hasn't been verified to do.

### Two layers: generic core and house conventions

This project has two layers with an explicit boundary (see
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):

| Layer | What it is | Dependencies |
|---|---|---|
| **Generic core** | Table parser, `--audit`, `--fix`, sync/health/freshness (`tools/`) | Just `git` + `python3`. Works for any user, any project. |
| **House conventions** | Assembly/reorder orchestration by an agent team (`cosmo-coo`, `software-architect`, `tech-lead`, `product-manager`, `engineering-manager`, `scrum-master`), a fixed end-of-project Wiki + beginner-doc item, wikilinks (`[[ORG]]`, `[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]`) that only resolve in the vault of whoever wrote these conventions | **Opt-in**, enabled by `.tab_pendencias.ini` at the root of the repo where the table lives (`[profile]` section, `name = casa` key). Missing file (or key) means `core` profile, always the most restrictive default. |

A third party who clones the repo with just `git` and `python3` gets the whole core
without needing any agent, wikilink, or house-specific convention.

### Installation

```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
git clone https://github.com/petrinhu/tab_pendencias.git
```

Auto-discovered by Claude Code. Auto-triggers on phrases like "create table", "show
pendencies", "show tasks", "what's left", "full history", "update status".

Manual via `Skill` tool:
```
Skill: tab_pendencias
```

Or slash command: `/tab_pendencias [--create | --reorder | --show | --main | --add_tests_audit]`

### Installation and degradation matrix

Not every dependency is mandatory. The table below shows what you lose in each
scenario, so nothing degrades silently:

| Scenario | What still works | What's lost |
|---|---|---|
| Without the agent constellation (`cosmo-coo` and others) | `--create`/`--reorder` run in a direct thread, applying the same method (topological + WSJF + waves) without orchestrating the team | Only the split into parallel lenses (architecture, value, effort, waves) by distinct agents; the outcome (the ordered table) is the same goal, computed by a single thread |
| Without the vault manuals (`[[ORG]]`, `[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]`) | The entire core | The wikilinks become dead text (don't resolve to any document); they're a house-convention reference, not the core's |
| Without `python3` | The agent-driven part of the skill (`--create`, `--reorder`, `--show`, `--main` via Claude Code) | The mechanical scripts in `tools/` (sync, health, freshness, and the git hooks that trigger them) |
| Windows without Git for Windows | The agent-driven part of the skill (doesn't depend on a shell) | Mechanical sync via git hook (`tools/hooks/`, POSIX shims that depend on a shell, on Windows the one bundled with Git for Windows). `--audit`/`--fix`/`--create`/`--reorder` remain available when called directly, without depending on the hook. |

### Cross-platform

The core (`tools/`) is pure Python with no dependency outside the stdlib, no
hardcoded POSIX path separator, and no assumption about the operating system's
default encoding/newline. The test suite runs in CI across **five environments**:
native Ubuntu and Windows, plus Debian, Fedora, and Arch via container. Python
versions measured out of the box in those environments: Debian 12 = 3.11.2, Fedora
41 = 3.13.9, Arch = 3.14.6. The optional config file (`.tab_pendencias.ini`) uses the
INI format, read with the stdlib `configparser`, deliberately chosen over TOML so
the core doesn't require Python 3.11+ (`tomllib` only exists from that version on).

### Standard table structure (9 columns)

```markdown
| ID | Wave | Group | Technical Description | Priority | Prerequisite | Difficulty | Status | Audit State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

Row order (top to bottom) is the recommended execution order. The `Wave` column
groups steps of equal value that can run in parallel. Legacy 8-column tables
(without `Wave`) are still read correctly by `--show`/`--main`; the parser locates
the header by column name, never by a fixed count.

### Valid values

The empty-cell symbol is the typographic em-dash (Unicode U+2014); it appears
literally in the `Wave`, `Prerequisite`, and `Audit State` cells when there's no
value to fill in.

| Column | Values |
|---|---|
| **Wave** | `W1`, `W2`, `W3`, ... (execution tier); empty cell for completed or out-of-flow items |
| **Priority** | High / Medium / Low (Alta / Média / Baixa) |
| **Prerequisite** | empty cell (none) or ID(s) (`F1.4`, `F2.1, F2.2`) |
| **Difficulty** | High / Medium / Low |
| **Audit State** | empty cell (not audited) / `✓` (approved) / `⚠` (with caveats) |

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
| `--create` | Creates a new table at `TODO.md` in project root, ordered by dependency and value |
| `--reorder` | Recalculates row order and the `Wave` column of an existing table, preserving ID/Status/Audit State |
| `--show` | Displays full table (including `✅ Concluído`) |
| `--main` | Displays only pending items (filters out `✅`) |
| `--add_tests_audit` | Adds applicable test/audit items for the stack, without asking |

Without argument, uses natural language: "show pendencies" for `--main`, "full table"
for `--show`, "create table" for `--create`, "reorder"/"minimize rework" for
`--reorder`.

### `--audit` and `--fix` (under implementation)

Decisions already closed for these two commands (see ADR-0001 linked above):

- `--audit` is **always read-only**: never writes to `TODO.md`, never mutates git
  state.
- `--fix` applies **only** mechanical, byte-preserving corrections (e.g., escaping a
  raw `|`, removing a duplicated fragment, consolidating a fragmented table while
  preserving ID/Status/Audit State). Never changes `Status`, never reorders, never
  touches branch/commit.
- **Fixed exit codes**: `0` = ran ok, zero findings; `1` = execution error; `2` = ran
  ok, at least one finding (of any severity).

The rest of the behavior (check list, report format, CLI options) is still being
implemented and will be documented here once it closes.

## Automatic tests and audits

On any command, the skill checks whether the non-unit tests (T2-T15) and the audits
applicable to the project's stack are in the plan. If missing, it asks (with a
strong recommendation) whether to add them; declining twice, it proceeds without
them and reminds you of `--add_tests_audit` to add them later.

- The unit test (TDD) does not enter the table: it's the TDD hook's responsibility.
- The `./TESTES.md` and `./AUDITORIAS.md` manuals are created at the project root
  (pruned for the stack) when missing, and never overwritten if they already exist.
- Items enter as `TST-*` (tests, after implementation) and `AUD-*` (audits, in the
  final waves), idempotently.

Dedicated command: `/tab_pendencias --add_tests_audit` injects directly, without
asking.

### Canonical file

**`TODO.md` in project root** is the only valid location. Skill never creates
`PENDENCIAS.md`, `TAREFAS.md`, or `BACKLOG.md` parallels.

### Mechanical synchronization (optional, generic core)

Besides the skill itself (agent-driven planning), the repo ships local,
deterministic scripts in [`tools/`](tools/README.md), no LLM/agent involved, to keep
`TODO.md` synced during the sprint:

- `python3 tools/todo_sync.py [--apply]`: advances `⏳`/`🔄` items to `🔍` from IDs
  cited in commits that touched substantive work. Never assigns `✅`, never
  reorders.
- `python3 tools/todo_health.py`: report of items stuck in `🔍`, INBOX size, and
  adherence to citing the ID in commits.
- Git hook in `tools/hooks/` (optional, cross-platform): post-commit warning, never
  blocks. Installation detail and OS-specific degradation in
  [`tools/README.md`](tools/README.md).

These scripts are an accelerator; without them the freshness convention still holds
by hand (see [`references/frescor-da-tabela.md`](references/frescor-da-tabela.md)).

### `CLAUDE.md` integration

On first use in a project, the skill checks whether root `CLAUDE.md` already
references `TODO.md`. If not, appends:

```markdown
## Pendências
A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz (ordenada
por execução, coluna Onda marca passos paralelizáveis).
```

### Repository layout

```
SKILL.md                -- skill definition (canonical source for the schema and flow)
TESTES.md                -- this project's own test catalog
AUDITORIAS.md             -- this project's own audit catalog
docs/adr/                 -- Architecture Decision Records
references/               -- normative documents (table freshness, test/audit catalog)
tools/                    -- generic core: parser, sync, health, freshness (stdlib only)
tools/hooks/               -- git hook shims (POSIX sh) + chaining script
tools/ci/                  -- guards used by CI (same scripts run locally)
tests/                    -- pytest suite (includes a synthetic defect corpus)
```

### Running the test suite

```bash
python3 -m venv .venv && source .venv/bin/activate   # Linux/macOS
pip install -r requirements-dev.txt
python3 -m pytest tests/ -v
```

On Windows, activate the venv with `.venv\Scripts\activate` before `pip install`.

### License

[GPL-3.0-or-later](LICENSE): free software, use, modification, sharing, and
commercial use permitted, provided derivative works that are distributed remain
under the same license (copyleft).

### Author

Petrus Silva Costa.
