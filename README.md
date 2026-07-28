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

> **Sobre esta seção:** o que está aqui é comportamento fechado e verificado
> executando o código -- nunca descrito por antecipação. Se um comando ainda
> não existir, isso é dito explicitamente, nunca omitido.

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

Ou comando slash: `/tab_pendencias [--create | --reorder | --show | --main | --add_tests_audit | --audit]`

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
| `--audit` | Audita a integridade estrutural do próprio `TODO.md` (read-only); ver seção dedicada abaixo |

Sem argumento, usa linguagem natural: "mostrar pendências" para `--main`, "tabela
completa" para `--show`, "criar tabela" para `--create`, "reordenar"/"minimizar
retrabalho" para `--reorder`, "auditar a tabela" para `--audit`.

### `--audit`

Motor de auditoria estrutural do próprio `TODO.md` (`tools/todo_audit.py`, camada
núcleo genérico, decisão de arquitetura em
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):
roda offline, sem LLM/rede e sem orquestrar nenhum agent. Chame via `/tab_pendencias
--audit` ou diretamente:

```bash
python3 tools/todo_audit.py [--profile core|casa] [--todo <caminho>] \
  [--max-per-check N] [--output <arquivo>] [-v]
```

- **Sempre read-only.** Nenhum caminho de código abre o `TODO.md` em modo de
  escrita, nem muta estado de git. A única escrita possível é a de `--output`
  (relatório opcional em arquivo à parte), e ela é bloqueada com erro se o
  caminho resolver para dentro do repositório auditado.
- **`--todo <caminho>`**: audita um arquivo fora do repositório corrente (não
  precisa estar no diretório atual nem no mesmo repositório git de quem invoca).
  O arquivo precisa se chamar exatamente `TODO.md`; qualquer outro nome sai com
  erro explicando a restrição.
- **`--profile core|casa`** e o arquivo `.tab_pendencias.ini` na raiz do repo
  auditado (seção `[profile]`, chave `name = casa`; formato INI lido com
  `configparser` da stdlib, escolhido para não exigir Python 3.11+). O perfil
  `core` é o default. **A camada casa é aditiva, nunca substitutiva**: sob
  `casa` rodam os 11 checks do núcleo **mais** os 3 da casa (14 no total);
  quem não ativa `casa` não perde nenhum check do núcleo, só não ganha os 3
  extras.
- **`--max-per-check N`** (default 5; `N<=0` = sem limite): amostra no máximo N
  achados por check no relatório. Achados **CRÍTICO nunca são truncados**; o
  corte incide só sobre severidade menor, e o que ficou de fora é sempre
  contado e declarado.
- **`--output <arquivo>`**: também grava o relatório nesse arquivo. Nunca pode
  apontar para dentro do repositório auditado.
- **Exit codes**: `0` = execução ok e zero achados; `1` = erro de execução (não
  é repositório git quando exigido, `TODO.md` ilegível, flag inválida); `2` =
  execução ok e há 1+ achado, de qualquer severidade, inclusive só cosmético.

Catálogo de checks (11 do núcleo + 3 da camada casa, opt-in):

| Check | Título | Severidade (default) | Perfil |
|---|---|---|---|
| `CHK-01` | ID duplicado | Crítico | core |
| `CHK-02` | nº de células ≠ cabeçalho (diagnóstico) | Crítico | core |
| `CHK-03` | Tabela fragmentada + span da canônica | Crítico | core |
| `CHK-04` | ncols divergente entre tabelas ID+Status | Crítico | core |
| `CHK-05` | Pré-requisito citando ID inexistente | Importante | core |
| `CHK-06` | Ciclo de dependência | Crítico | core |
| `CHK-07` | Onda inconsistente com a dependência | Importante | core |
| `CHK-08` | Status fora do vocabulário canônico | Importante | core |
| `CHK-09` | Claims obsoletas na Descrição (contra o git real) | Importante | core |
| `CHK-10` | Proposta do `todo_sync.py` (sem `--apply`) anexada | Cosmético | core |
| `CHK-11` | Reconciliação de contagem (`todo_health`) | Crítico | core |
| `CHK-12` | TST-\*/AUD-\* agendado antes do que cobre | Crítico | **casa** |
| `CHK-13` | INBOX: ID duplicado da tabela ou formato inválido | Importante | **casa** |
| `CHK-14` | Item de Wiki + doc para iniciante ausente na última onda | Cosmético | **casa** |

### `--fix`

Motor de correção mecânica (`tools/todo_fix.py`), consumindo só o que os checks
do `--audit` já marcaram `[auto-fixável]` -- nunca redecide o que é seguro
corrigir. Chame direto:

```bash
python3 tools/todo_fix.py [--apply CLASSE [CLASSE ...]] [-v]
```

- **Dry-run por padrão.** Sem `--apply`, só mostra o plano de correção (com o
  diff de cada mudança proposta) e nunca escreve no arquivo.
- **`--apply <classe...>`** aplica só as classes nomeadas, ou `--apply all`
  para todas as detectadas naquela execução.
- **Duas classes de correção existem hoje**: `escapar_pipe_cru` (de `CHK-02`:
  escapa um `|` cru localizado sem ambiguidade dentro de um code span) e
  `remover_fragmento_duplicado` (de `CHK-01`: remove a ocorrência de um ID
  duplicado que a heurística reconhece como fragmento/lixo óbvio). **O
  `ADR-0001` previa quatro classes** (as outras duas seriam consolidar tabela
  fragmentada e corrigir claim obsoleta na Descrição) -- elas **não existem**
  porque nenhum check do catálogo hoje marca `CHK-03`/`CHK-04`/`CHK-09` como
  `[auto-fixável]`. Isso é decisão registrada, não lacuna esquecida: o motor
  só aplica o que o `--audit` já decidiu ser seguro, e mesmo dentro de
  `escapar_pipe_cru` o motor é mais conservador que o check -- recusa aplicar
  (marcando `[NÃO APLICÁVEL]` no relatório, com o motivo) sempre que a posição
  do pipe cru não é inequívoca.
- **Proteções, na ordem em que agem**: (1) `--apply` aborta com erro **antes de
  qualquer escrita** se a working tree do `TODO.md` não estiver limpa
  (`git status --porcelain` não-vazio) -- nunca mistura com edição em voo de
  outra sessão/agente; (2) escrita **atômica** (arquivo temporário no mesmo
  diretório + `os.replace`), então uma falha no meio do processo não deixa o
  `TODO.md` pela metade; (3) antes de gravar, o motor **prova os invariantes**
  (round-trip byte-a-byte de toda linha não tocada, e a contagem de itens
  resultante bate com o valor calculado antes de aplicar) contra o texto novo
  em memória -- se a prova falhar, aborta sem tocar o arquivo real.
- **O que `--fix` nunca faz**: mudar `Status`, reordenar linhas, tocar
  branch/commit do repositório.
- **Exit codes**: `0` = execução ok, nada a corrigir; `1` = erro de execução
  (não é repositório git, `TODO.md` ilegível, working tree suja ao aplicar,
  falha de escrita); `2` = execução ok, há 1+ correção disponível (mostrada em
  dry-run ou aplicada).

**Riscos conhecidos (declarados, não escondidos):** dois processos de
`--fix --apply` rodando ao mesmo tempo no mesmo repositório se sobrescreveriam
sem aviso -- a checagem de working tree limpa protege contra editar em cima de
uma mudança já commitada ou pendente no início da execução, mas não contra uma
corrida entre dois processos que passam por essa checagem quase simultaneamente
(não há trava de sistema operacional). Existe uma janela inerente entre ler e
escrever o arquivo sem lock de SO. O comportamento em Windows contra um destino
somente-leitura não tem prova empírica nesta fatia (não testado nessa
plataforma).

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

> **About this section:** what's documented here is behavior already closed
> and verified by running the code -- never described ahead of time. If a
> command doesn't exist yet, that's stated explicitly, never left out.

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

Or slash command: `/tab_pendencias [--create | --reorder | --show | --main | --add_tests_audit | --audit]`

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
| `--audit` | Audits the structural integrity of the `TODO.md` itself (read-only); see the dedicated section below |

Without argument, uses natural language: "show pendencies" for `--main`, "full table"
for `--show`, "create table" for `--create`, "reorder"/"minimize rework" for
`--reorder`, "audit the table" for `--audit`.

### `--audit`

Structural audit engine for the `TODO.md` itself (`tools/todo_audit.py`,
generic-core layer, architecture decision in
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):
runs offline, no LLM/network, no agent orchestration. Call it via
`/tab_pendencias --audit` or directly:

```bash
python3 tools/todo_audit.py [--profile core|casa] [--todo <path>] \
  [--max-per-check N] [--output <file>] [-v]
```

- **Always read-only.** No code path opens `TODO.md` in write mode, nor
  mutates git state. The only possible write is `--output` (an optional
  report file), and it's blocked with an error if the path resolves inside
  the audited repository.
- **`--todo <path>`**: audits a file outside the current repository (doesn't
  need to be in the current directory nor in the same git repository as the
  caller). The file must be named exactly `TODO.md`; any other name exits
  with an error explaining the restriction.
- **`--profile core|casa`** and the `.tab_pendencias.ini` file at the root of
  the audited repo (`[profile]` section, `name = casa` key; INI format read
  with the stdlib `configparser`, chosen so it doesn't require Python 3.11+).
  `core` is the default profile. **The house layer is additive, never
  substitutive**: under `casa`, the 11 core checks run **plus** the 3 house
  checks (14 total); not enabling `casa` never removes a core check, it just
  skips the 3 extras.
- **`--max-per-check N`** (default 5; `N<=0` = no limit): samples at most N
  findings per check in the report. **CRITICAL findings are never
  truncated**; the cut only applies to lower severities, and whatever is left
  out is always counted and declared.
- **`--output <file>`**: also writes the report to this file. Can never point
  inside the audited repository.
- **Exit codes**: `0` = ran ok, zero findings; `1` = execution error (not a
  git repository when required, unreadable `TODO.md`, invalid flag); `2` =
  ran ok, 1+ finding of any severity, including cosmetic-only.

Check catalog (11 core + 3 opt-in house-layer checks):

| Check | Title | Severity (default) | Profile |
|---|---|---|---|
| `CHK-01` | Duplicate ID | Critical | core |
| `CHK-02` | Cell count != header (diagnosis) | Critical | core |
| `CHK-03` | Fragmented table + canonical span | Critical | core |
| `CHK-04` | ncols diverges between ID+Status tables | Critical | core |
| `CHK-05` | Prerequisite citing a nonexistent ID | Important | core |
| `CHK-06` | Dependency cycle | Critical | core |
| `CHK-07` | Wave inconsistent with the dependency | Important | core |
| `CHK-08` | Status outside the canonical vocabulary | Important | core |
| `CHK-09` | Stale claims in the Description (against real git) | Important | core |
| `CHK-10` | `todo_sync.py` proposal (without `--apply`) attached | Cosmetic | core |
| `CHK-11` | Count reconciliation (`todo_health`) | Critical | core |
| `CHK-12` | TST-\*/AUD-\* scheduled before what it covers | Critical | **house** |
| `CHK-13` | INBOX: duplicate table ID or invalid format | Important | **house** |
| `CHK-14` | Missing Wiki + beginner-doc item in the last wave | Cosmetic | **house** |

### `--fix`

Mechanical-correction engine (`tools/todo_fix.py`), consuming only what the
`--audit` checks already marked `[auto-fixable]` -- it never re-decides what's
safe to fix. Call it directly:

```bash
python3 tools/todo_fix.py [--apply CLASS [CLASS ...]] [-v]
```

- **Dry-run by default.** Without `--apply`, it only shows the fix plan (with
  a diff for each proposed change) and never writes to the file.
- **`--apply <class...>`** applies only the named classes, or `--apply all`
  for every class detected in that run.
- **Two correction classes exist today**: `escapar_pipe_cru` (from `CHK-02`:
  escapes a raw `|` found unambiguously inside a code span) and
  `remover_fragmento_duplicado` (from `CHK-01`: removes the occurrence of a
  duplicate ID the heuristic recognizes as an obvious fragment/leftover).
  **ADR-0001 anticipated four classes** (the other two would be consolidating
  a fragmented table and fixing a stale claim in the Description) -- they
  **don't exist** because no check in the catalog currently marks
  `CHK-03`/`CHK-04`/`CHK-09` as `[auto-fixable]`. This is a recorded decision,
  not a forgotten gap: the engine only applies what `--audit` already decided
  is safe, and even within `escapar_pipe_cru` the engine is more conservative
  than the check -- it refuses to apply (flagging `[NOT APPLICABLE]` in the
  report, with the reason) whenever the raw pipe's position isn't
  unambiguous.
- **Protections, in the order they act**: (1) `--apply` aborts with an error
  **before any write** if the `TODO.md` working tree isn't clean
  (`git status --porcelain` non-empty) -- it never mixes with an edit in
  flight from another session/agent; (2) **atomic** write (temp file in the
  same directory + `os.replace`), so a mid-process failure never leaves
  `TODO.md` half-written; (3) before writing, the engine **proves the
  invariants** (byte-exact round-trip of every untouched line, and the
  resulting item count matches the value computed before applying) against
  the new in-memory text -- if the proof fails, it aborts without touching the
  real file.
- **What `--fix` never does**: change `Status`, reorder rows, touch the
  repository's branch/commit.
- **Exit codes**: `0` = ran ok, nothing to fix; `1` = execution error (not a
  git repository, unreadable `TODO.md`, dirty working tree when applying,
  write failure); `2` = ran ok, 1+ correction available (shown in dry-run or
  applied).

**Known risks (disclosed, not hidden):** two `--fix --apply` processes
running at the same time on the same repository would overwrite each other
without warning -- the clean-working-tree check protects against writing over
a change already committed or pending at the start of the run, but not
against a race between two processes that both pass that check nearly
simultaneously (there's no OS-level lock). There's an inherent window between
reading and writing the file with no OS lock. Behavior on Windows against a
read-only destination has no empirical proof in this slice (not tested on
that platform).

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
