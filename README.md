# tab_pendencias

![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![Type](https://img.shields.io/badge/type-Claude%20Code%20Skill-blue)
![Grok](https://img.shields.io/badge/Grok-compatible-black)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Language](https://img.shields.io/badge/lang-pt--br%20%2F%20en-lightgrey)
![File](https://img.shields.io/badge/canonical-TODO.md-yellow)

---

## Português (pt-br)

Skill do Claude Code (e **compatível com Grok**: mesmo `SKILL.md`, toolkit em
`tools/` e hooks) que gerencia a tabela de pendências/planejamento de projetos no
padrão `TODO.md` tabular: cabeçalho fixo, ordem de execução (dependência + valor),
símbolos de status visuais, auditoria, auto-fix mecânico e **pipeline de intake**
(trabalho novo classificado na hora; INBOX só como fila de exceção residual).

> **Sobre esta seção:** o que está aqui é comportamento fechado e verificado
> executando o código -- nunca descrito por antecipação. Se um comando ainda
> não existir, isso é dito explicitamente, nunca omitido.
>
> **Versão documentada:** alinhada ao motor **v1.2** (tag `v1.2.0` + main).
> ADR de intake: [`docs/adr/0002-...`](docs/adr/0002-maquina-de-estados-de-intake-e-inbox-como-fila-de-excecao.md).

### Duas camadas: núcleo genérico e convenções da casa

Este projeto tem duas camadas com fronteira explícita (ver
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):

| Camada | O que é | Dependências |
|---|---|---|
| **Núcleo genérico** | Parser da tabela, `--audit`, `--fix`, `--add`/`--drain` (intake), WSJF Fibonacci, sinais `TAB_*`, sync/health/frescor, lock de escrita (`tools/`) | Só `git` + `python3` (>= 3.11). Funciona para qualquer usuário, qualquer projeto. |
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

Ou comando slash: `/tab_pendencias [--create | --reorder | --show | --main | --add_tests_audit | --audit | --fix | --add | --drain]`

### Matriz de instalação e degradação

Nem toda dependência é obrigatória. A tabela abaixo mostra o que você perde em cada
cenário, para nunca ficar surpreso em silêncio:

| Cenário | O que continua funcionando | O que se perde |
|---|---|---|
| Sem a constelação de agents (`cosmo-coo` e demais) | `--create`/`--reorder` rodam em thread direta, aplicando o mesmo método (topological + WSJF + ondas) sem orquestrar o time | Só a divisão de trabalho em lentes paralelas (arquitetura, valor, esforço, ondas) por agents distintos; o resultado (a tabela ordenada) é o mesmo objetivo, calculado por uma única thread |
| Sem os manuais do vault (`[[ORG]]`, `[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]`) | Todo o núcleo | Os wikilinks viram texto morto (não resolvem a nenhum documento); são referência de convenção da casa, não do núcleo |
| Sem `python3` | A parte agent-driven da skill (`--create`, `--reorder`, `--show`, `--main` via Claude Code) | Os scripts mecânicos de `tools/` (intake, audit, fix, sync, health, freshness, sinais, e os hooks de git que os disparam) |
| Windows sem Git for Windows | A parte agent-driven da skill (não depende de shell) | O sync mecânico via git hook (`tools/hooks/`, shims POSIX que dependem de um shell, no Windows o que vem com o Git for Windows). `--audit`/`--fix`/`--add`/`--drain`/`--create`/`--reorder` continuam disponíveis chamados diretamente, sem depender do hook. |

### Multiplataforma (cross-platform)

O núcleo (`tools/`) é Python puro sem dependências fora da stdlib, sem hardcode de
separador de caminho POSIX e sem assumir encoding/newline padrão do sistema
operacional. **Piso oficial: Python >= 3.11** (declarado em `pyproject.toml`,
exercitado na matriz de CI em 3.11 e 3.12 nativos + distros em container). A
suíte roda no CI em **cinco ambientes**: Ubuntu e Windows nativos, mais Debian,
Fedora e Arch em container. Versões de Python medidas de fábrica nesses
ambientes: Debian 12 = 3.11.2, Fedora 41 = 3.13.9, Arch = 3.14.6. A configuração
opcional (`.tab_pendencias.ini`) usa o formato INI, lido com `configparser` da
stdlib -- escolha **histórica** (D-9; na época o motivo era não exigir 3.11+ via
`tomllib`); o formato **permanece INI** por compatibilidade com configs já
publicadas, não porque o piso ainda seja inferior a 3.11.

### Estrutura padrão da tabela (9 colunas)

```markdown
| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

A ordem das linhas (de cima para baixo) é a ordem de execução recomendada. A coluna
`Onda` agrupa passos de igual valor que podem rodar em paralelo. Tabelas legadas de
8 colunas (sem `Onda`) continuam sendo lidas corretamente por `--show`/`--main`; o
parser localiza o cabeçalho pelo nome das colunas, nunca por uma contagem fixa.

### Ordem canônica do arquivo (INBOX antes, tabela por último)

Normativo em [`references/frescor-da-tabela.md`](references/frescor-da-tabela.md) §5:

1. linha 1: título `#` do arquivo;
2. preâmbulo livre (prosa, legenda, critérios, notas);
3. seção **`## INBOX (...)`** -- exception queue, **antes** da tabela;
4. (opcional) mais prosa/seções livres;
5. **a tabela canônica**;
6. **EOF logo após a última linha da tabela** -- nada vem depois dela.

**UMA tabela no arquivo, e só uma** -- sem qualificação: **qualquer segundo bloco
`|...|` é violação**, tenha coluna `Status` ou não. Legenda, matriz, comparativo,
sumário, índice, contagem e scoring vão em **bullets ou lista**, nunca em tabela
auxiliar. Proibido junto: **linha em branco dentro da tabela** (em Markdown ela
encerra a tabela ali e abre outro bloco). Motivo mecânico, não estético: a leitura
**para no primeiro cabeçalho repetido**, então o que estiver numa segunda tabela
com `Status` fica **invisível** para qualquer ferramenta e para qualquer contagem,
sem erro nenhum na tela; e a regra não admite exceção para "tabela auxiliar
inofensiva" porque toda tabela a mais é candidata a ser eleita por engano.

**Forma do arquivo (o modelo da casa)** -- detalhe em
[`references/frescor-da-tabela.md`](references/frescor-da-tabela.md) §5.2: a **linha
1** declara a estrutura em uma linha (blockquote `> **ESTRUTURA CANÔNICA DO ARQUIVO
— NÃO QUEBRAR A TABELA:** ...`), antes do título `#`; a tabela ganha o heading
próprio **`## TABELA UNIFICADA`** logo acima dela; e **scoring WSJF, checklists, sumários e
material de referência vão em bullets no cabeçalho** (nunca em tabela), sob
`### Scoring WSJF (referência — **não** é tabela de trabalho)` com a linha de escopo
*"Itens abaixo são registro histórico de score; o status de trabalho vive só na
tabela única."*. É **forma**, não leitura: arquivo sem esses elementos continua
válido; eles existem para a regra ficar visível dentro do próprio arquivo.

**Mudou em 2026-08-19** (antes a INBOX ficava depois da tabela). Motivo: "fim da
tabela = fim do arquivo" é a invariante que ferramentas e guards de consumidor
usam para acrescentar linha sem procurar onde a tabela acaba; uma seção depois da
tabela a tornava falsa por construção.

**Compatibilidade:** arquivo no formato **legado** (INBOX depois, ou qualquer texto
após a tabela) continua **válido para LEITURA** -- mesmos itens, mesmas entradas --,
só recebe um **aviso** de formato (`todo_lib.legacy_layout_warning`). **Escrita e
criação usam sempre a ordem nova.** A conversão é mecânica, idempotente e preserva
byte a byte o conteúdo da tabela e da INBOX (só a ordem dos blocos muda):

```bash
python3 tools/todo_migrate_inbox.py --check           # diagnostica (exit 2 = legado)
python3 tools/todo_migrate_inbox.py --apply           # converte o TODO.md do repo
python3 tools/todo_migrate_inbox.py CAMINHO/TODO.md --apply
```

### Valores válidos

O símbolo de célula vazia é o travessão tipográfico (Unicode U+2014, `—`); ele
aparece literalmente nas células de `Onda`, `Pré-requisito` e `Estado Auditado`
quando não há valor a preencher. **Exceção MDASH-2:** este repositório usa o
caractere de propósito (é o contrato do schema). Marcador
[`.tab_pendencias.allow_emdash`](.tab_pendencias.allow_emdash) + checklist para o
hook anti-mdash do consumidor isentar o path `tab_pendencias`.

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
| `--fix` | Aplica correções mecânicas marcadas `[auto-fixável]` pelo audit (2 classes); dry-run por padrão |
| `--add` | Pipeline de intake: classifica descoberta/item novo e persiste L0, SCOPED, FULL ou residual |
| `--drain` | Drena a INBOX residual (exception queue) com julgamentos; pós-apply `classifiable_inbox_count == 0` |

Sem argumento, usa linguagem natural: "mostrar pendências" para `--main`, "tabela
completa" para `--show`, "criar tabela" para `--create`, "reordenar"/"minimizar
retrabalho" para `--reorder`, "auditar a tabela" para `--audit`, "corrigir a tabela"
para `--fix`, "adicionar pendência"/"registra isto" para `--add`, "drenar INBOX"
para `--drain`.

### Intake e INBOX (exception queue -- não é fila normal)

> **Histórico:** versões antigas mandavam *toda* descoberta para a seção INBOX
> "na hora" e esperavam dreno humano ou `--reorder`. Isso ficou **obsoleto** com
> o motor de intake (v1.2 / [ADR-0002](docs/adr/0002-maquina-de-estados-de-intake-e-inbox-como-fila-de-excecao.md)).
> A INBOX residual **não** é a fila normal de descoberta.

Trabalho novo descoberto no meio do sprint **não espera reordenar por default**.
O caminho normal é o intake (`/tab_pendencias --add` ou `tools/todo_intake.py`):

1. **Local (L0)** -- append de uma linha no `TODO.md` (marcador recuperável).
2. **Escopado / fundação** -- `SCOPED_REORDER` ou `FULL_REORDER` proporcional.
3. **Duplicata** -- não cria linha; limpa residual relacionado se houver.
4. **Ambíguo / sem autoridade** -- só então vira **INBOX residual** (exception
   queue) com metadado `[triage ...]`, sem Onda nem WSJF.

Workers/subagentes **não** editam `TODO.md`: devolvem o bloco `DISCOVERED_WORK`;
a thread principal converte via `tools/intake_agent_bridge.py` e chama o intake.
Hub com `[hub] derived=true` é **read-only** para apply de intake/drain (ver
[`references/hub-agregador.md`](references/hub-agregador.md)).

**CLI mecânica** (offline, stdlib, sem LLM -- o agente preenche as flags de julgamento):

```bash
# dry-run de um candidato local
python3 tools/todo_intake.py --todo TODO.md \
  --candidate-id cand-1 --item-id F-12 \
  --description "..." --source agent --fields-complete --local

# persistir
python3 tools/todo_intake.py --todo TODO.md ... --apply

# dreno da INBOX residual
python3 tools/todo_intake.py --drain --todo TODO.md
python3 tools/todo_intake.py --drain --todo TODO.md --apply --judgments-json path.json
```

Sinais de sessão (`TAB_*`): motor `tools/session_signals.py`, impressos por
`todo_health.py` e pelo adapter `tools/hooks/tab_pendencias_reminder.py`.
`TAB_TRIAGE_REQUIRED` pede **`--drain`**, não full reorder por relógio. O adapter
atende **SessionStart** e **UserPromptSubmit** e roteia por evento: sinal de estado
do repositório sai no SessionStart, sinal reativo ao turno sai no UserPromptSubmit,
nenhum sai nos dois (e o evento por-turno deduplica por `session_id`). Contrato:
[`references/sinais-de-frescor.md`](references/sinais-de-frescor.md).

### `--audit` (auditoria estrutural da tabela)

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
  `configparser` da stdlib -- escolha histórica D-9; piso atual Python >= 3.11).
  O perfil `core` é o default. **A camada casa é aditiva, nunca substitutiva**:
  sob `casa` rodam os 13 checks do núcleo **mais** os 3 da casa (16 no total);
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

Catálogo de checks (13 do núcleo + 3 da camada casa, opt-in):

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
| `CHK-19` | Mais de uma tabela no arquivo | Crítico / Importante | core |
| `CHK-20` | Linha em branco dentro da tabela | Importante | core |
| `CHK-12` | TST-\*/AUD-\* agendado antes do que cobre | Crítico | **casa** |
| `CHK-13` | INBOX: ID duplicado da tabela ou formato inválido | Importante | **casa** |
| `CHK-14` | Item de Wiki + doc para iniciante ausente na última onda | Cosmético | **casa** |

### `--fix` (correção mecânica byte-preserving)

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
- **Duas classes de correção (escopo real, FIX-ESCOPO-2)**: `escapar_pipe_cru`
  (de `CHK-02`: escapa um `|` cru localizado sem ambiguidade dentro de um code
  span) e `remover_fragmento_duplicado` (de `CHK-01`: remove a ocorrência de um
  ID duplicado que a heurística reconhece como fragmento/lixo óbvio). Não há
  terceira nem quarta classe: consolidar tabela fragmentada e reescrever claim
  na Descrição **movem linhas** em arquivo de terceiro e ficaram **fora** do
  auto-fix (julgamento humano / `--reorder` / edição manual). Regra fixa: a
  auditoria **nunca** marca `fixable=True` sem o corretor correspondente
  existir no motor. Mesmo dentro de `escapar_pipe_cru` o motor é mais
  conservador que o check -- recusa aplicar (marcando `[NÃO APLICÁVEL]` no
  relatório, com o motivo) sempre que a posição do pipe cru não é inequívoca.
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

**Concorrência (v1.2):** o caminho `--apply` adquire `TodoWriteLock`
(`tools/todo_lock.py`, o mesmo lock de intake/drain) **antes** de re-checar a
working tree limpa e escrever -- serializa dois `--fix --apply` no mesmo TODO
(timeout default 10s; falha de lock = exit 1). Dry-run **não** pede lock.
Residual de plataforma: no Windows, `os.replace` contra destino somente-leitura
não tem prova empírica na matrix (handling genérico de `OSError` coberto por
mock). Detalhe em [`tools/README.md`](tools/README.md).

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

### Núcleo mecânico (`tools/`, opcional em uso diário, genérico)

Além da skill (planejamento via agent), o repo traz scripts locais e determinísticos
em [`tools/`](tools/README.md), sem LLM/agent:

| Script | Papel |
|---|---|
| `todo_intake.py` | `--add` / `--drain` (cascata L0/SCOPED/FULL/residual) |
| `intake_agent_bridge.py` | `DISCOVERED_WORK` -> flags de julgamento |
| `intake_journal.py` | journal write-ahead + recuperação de órfãos |
| `todo_audit.py` / `todo_fix.py` | auditoria estrutural e auto-fix (2 classes) |
| `todo_migrate_inbox.py` | migra layout legado (INBOX depois da tabela) para a ordem canônica |
| `todo_sync.py` / `todo_health.py` | sync de status e relatório + linhas `TAB_*` |
| `session_signals.py` | predicados de frescor (`TAB_*`) |
| `todo_lock.py` | lock de escrita (intake/drain/fix apply) |
| `wsjf.py` | WSJF Fibonacci (topo **antes** de score) |
| `bus_contract.py` | contrato de mensagem de bus (remetente não pontua) |
| `concurrent_inbox.py` | fallback `inbox/*.md` entre sessões |
| `todo_freshness.py` + `hooks/` | aviso pós-commit (warn-only) |
| `submodule_pin_drift.py` | drift do pin de submódulo (read-only) |

**HOOKSRC-1:** `core.hooksPath` global deve apontar para a **instalação publicada**
(submódulo pinado no consumidor), **nunca** para o checkout de desenvolvimento
deste produto. Detalhe e degradação por SO em [`tools/README.md`](tools/README.md).

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
SKILL.md                 -- definicao da skill (schema, fluxo, intake, sinais)
TESTES.md / AUDITORIAS.md -- catalogos deste proprio projeto
docs/adr/                -- ADRs (0001 nucleo/casa; 0002 intake + INBOX exception)
docs/para-iniciantes.md  -- guia didatico (parte do zero)
docs/campanha/           -- plano historico da campanha v1.2 (nao e doc vivo)
references/              -- normas: frescor, sinais TAB_*, hub, bus, cutover
tools/                   -- nucleo generico (intake, audit, fix, sync, lock, wsjf, ...)
tools/hooks/             -- shims de git hook + reminder de sessao
tools/ci/                -- guards do CI
tests/                   -- suite pytest + corpus sintetico
templates/               -- fragmentos de vault e contrato de discovery
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

Claude Code skill (**Grok-compatible**: same `SKILL.md`, `tools/` toolkit, and hooks)
that manages the project pendencies/planning table in `TODO.md` tabular standard:
fixed header, execution order (dependency + value), visual status symbols, structural
audit, mechanical auto-fix, and an **intake pipeline** (new work classified immediately;
INBOX only as a residual exception queue).

**Canonical file order (changed 2026-08-19):** title -> free preamble -> `## INBOX`
section -> optional prose -> **the canonical table** -> **EOF right after the table's
last line**. The INBOX now comes **before** the table, and nothing comes after it:
"end of table = end of file" is the invariant consumer tools and guards rely on to
append a row without hunting for where the table ends. **Legacy files (INBOX after
the table, or any text past it) stay VALID FOR READING** -- same items, same entries,
plus a format warning; **writing and creation always use the new order**. Convert with
`python3 tools/todo_migrate_inbox.py --apply` (idempotent; table and INBOX content
preserved byte for byte, only block order changes).

> **About this section:** what's documented here is behavior already closed
> and verified by running the code -- never described ahead of time. If a
> command doesn't exist yet, that's stated explicitly, never left out.
>
> **Documented version:** aligned with the **v1.2** motor (tag `v1.2.0` + main).
> Intake ADR: [`docs/adr/0002-...`](docs/adr/0002-maquina-de-estados-de-intake-e-inbox-como-fila-de-excecao.md).

### Two layers: generic core and house conventions

This project has two layers with an explicit boundary (see
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):

| Layer | What it is | Dependencies |
|---|---|---|
| **Generic core** | Table parser, `--audit`, `--fix`, `--add`/`--drain` (intake), Fibonacci WSJF, `TAB_*` signals, sync/health/freshness, write lock (`tools/`) | Just `git` + `python3` (>= 3.11). Works for any user, any project. |
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

Or slash command: `/tab_pendencias [--create | --reorder | --show | --main | --add_tests_audit | --audit | --fix | --add | --drain]`

### Installation and degradation matrix

Not every dependency is mandatory. The table below shows what you lose in each
scenario, so nothing degrades silently:

| Scenario | What still works | What's lost |
|---|---|---|
| Without the agent constellation (`cosmo-coo` and others) | `--create`/`--reorder` run in a direct thread, applying the same method (topological + WSJF + waves) without orchestrating the team | Only the split into parallel lenses (architecture, value, effort, waves) by distinct agents; the outcome (the ordered table) is the same goal, computed by a single thread |
| Without the vault manuals (`[[ORG]]`, `[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]`) | The entire core | The wikilinks become dead text (don't resolve to any document); they're a house-convention reference, not the core's |
| Without `python3` | The agent-driven part of the skill (`--create`, `--reorder`, `--show`, `--main` via Claude Code) | The mechanical scripts in `tools/` (intake, audit, fix, sync, health, freshness, signals, and the git hooks that trigger them) |
| Windows without Git for Windows | The agent-driven part of the skill (doesn't depend on a shell) | Mechanical sync via git hook (`tools/hooks/`, POSIX shims that depend on a shell, on Windows the one bundled with Git for Windows). `--audit`/`--fix`/`--add`/`--drain`/`--create`/`--reorder` remain available when called directly, without depending on the hook. |

### Cross-platform

The core (`tools/`) is pure Python with no dependency outside the stdlib, no
hardcoded POSIX path separator, and no assumption about the operating system's
default encoding/newline. **Official floor: Python >= 3.11** (declared in
`pyproject.toml`, exercised in CI on 3.11 and 3.12 natively plus distro
containers). The test suite runs in CI across **five environments**: native
Ubuntu and Windows, plus Debian, Fedora, and Arch via container. Python versions
measured out of the box in those environments: Debian 12 = 3.11.2, Fedora 41 =
3.13.9, Arch = 3.14.6. The optional config file (`.tab_pendencias.ini`) uses the
INI format, read with the stdlib `configparser` -- a **historical** choice (D-9;
originally to avoid requiring 3.11+ via `tomllib`); the format **stays INI** for
compatibility with already-published configs, not because the floor is still
below 3.11.

### Standard table structure (9 columns)

```markdown
| ID | Wave | Group | Technical Description | Priority | Prerequisite | Difficulty | Status | Audit State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
```

Row order (top to bottom) is the recommended execution order. The `Wave` column
groups steps of equal value that can run in parallel. Legacy 8-column tables
(without `Wave`) are still read correctly by `--show`/`--main`; the parser locates
the header by column name, never by a fixed count.

### Canonical file order (exactly one work table)

Normative in [`references/frescor-da-tabela.md`](references/frescor-da-tabela.md) §5:

1. line 1: the file `#` title;
2. free preamble (prose, legend, criteria, notes);
3. **`## INBOX (...)`** section -- exception queue, **before** the table;
4. (optional) more free prose/sections;
5. **the canonical table**;
6. **EOF right after the table's last line** -- nothing comes after it.

**Exactly ONE table in the file** -- no qualification: **any second `|...|` block
is a violation**, with or without a `Status` column. Legend, matrix, comparison,
summary, index, count and scoring go in **bullets or lists**, never in an auxiliary
table. Also forbidden: a **blank line inside the table** (in Markdown it ends the
table right there and opens another block). Mechanical reason, not cosmetic:
reading **stops at the first repeated header**, so whatever sits in a second table
with `Status` becomes **invisible** to every tool and every count, with no error on
screen; and the rule admits no "harmless auxiliary table" exception, because every
extra table is a candidate to be picked by mistake.

**File shape (the house model)** -- detail in
[`references/frescor-da-tabela.md`](references/frescor-da-tabela.md) §5.2 (pt-br):
**line 1** states the structure in a single blockquote line, before the `#` title;
the table gets its own heading (**"unified table"**) right above it; and WSJF
scoring, checklists, summaries and reference material go in **bullets in the header**
(never in a table: the file has a single `|...|` block), under a
title that says what the section is *not* ("reference -- **not** a work table") plus
a scope line ("the work status lives **only** in the single table"). This is
**shape**, not reading: a file without those elements is still valid; they exist so
the rule stays visible inside the file itself, and so nobody adds a `Status` column
to a reference block.

**Legacy compatibility:** a file in the legacy layout (INBOX after the table, or
any text after it) is still **valid for READING** -- same items, same entries --,
it only gets a format **warning** (`todo_lib.legacy_layout_warning`). **Writing
and creation always use the new order.**

### Valid values

The empty-cell symbol is the typographic em-dash (Unicode U+2014, `—`); it appears
literally in `Wave`, `Prerequisite` and `Audit State` cells when there is no value to
fill. **MDASH-2 exception:** this repository uses the character on purpose (schema
contract). Marker [`.tab_pendencias.allow_emdash`](.tab_pendencias.allow_emdash) + consumer hook
checklist to exempt the `tab_pendencias` path.

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
| `--fix` | Applies mechanical fixes marked `[auto-fixable]` by audit (2 classes); dry-run by default |
| `--add` | Intake pipeline: classifies a new discovery/item and persists L0, SCOPED, FULL, or residual |
| `--drain` | Drains residual INBOX (exception queue) with judgments; post-apply `classifiable_inbox_count == 0` |

Without argument, uses natural language: "show pendencies" for `--main`, "full table"
for `--show`, "create table" for `--create`, "reorder"/"minimize rework" for
`--reorder`, "audit the table" for `--audit`, "fix the table" for `--fix`,
"add this pendency" for `--add`, "drain INBOX" for `--drain`.

### Intake and INBOX (exception queue -- not the normal queue)

> **History:** older versions sent *every* discovery to the INBOX section
> immediately and waited for human drain or `--reorder`. That is **obsolete**
> with the intake motor (v1.2 / [ADR-0002](docs/adr/0002-maquina-de-estados-de-intake-e-inbox-como-fila-de-excecao.md)).
> Residual INBOX is **not** the normal discovery queue.

New work found mid-sprint does **not** wait for a full reorder by default.
The normal path is intake (`/tab_pendencias --add` or `tools/todo_intake.py`):

1. **Local (L0)** -- append one row to `TODO.md` (recoverable marker).
2. **Scoped / foundation** -- proportional `SCOPED_REORDER` or `FULL_REORDER`.
3. **Duplicate** -- no new row; related residual cleaned if present.
4. **Ambiguous / no authority** -- only then becomes **residual INBOX**
   (exception queue) with `[triage ...]` metadata, no Wave and no WSJF.

Workers/subagents do **not** edit `TODO.md`: they return a `DISCOVERED_WORK`
block; the main thread converts it via `tools/intake_agent_bridge.py` and calls
intake. A hub with `[hub] derived=true` is **read-only** for intake/drain apply
(see [`references/hub-agregador.md`](references/hub-agregador.md)).

**Mechanical CLI** (offline, stdlib, no LLM -- the agent fills judgment flags):

```bash
python3 tools/todo_intake.py --todo TODO.md \
  --candidate-id cand-1 --item-id F-12 \
  --description "..." --source agent --fields-complete --local

python3 tools/todo_intake.py --todo TODO.md ... --apply

python3 tools/todo_intake.py --drain --todo TODO.md
python3 tools/todo_intake.py --drain --todo TODO.md --apply --judgments-json path.json
```

Session signals (`TAB_*`): motor `tools/session_signals.py`, printed by
`todo_health.py` and adapter `tools/hooks/tab_pendencias_reminder.py`.
`TAB_TRIAGE_REQUIRED` means run **`--drain`**, not a clock-driven full reorder.
The adapter serves **SessionStart** and **UserPromptSubmit** and routes by event:
repository-state signals fire on SessionStart, turn-reactive ones on
UserPromptSubmit, none on both (and the per-turn event dedupes by `session_id`).
Contract: [`references/sinais-de-frescor.md`](references/sinais-de-frescor.md).

### `--audit` (structural table audit)

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
  with the stdlib `configparser` -- historical D-9 choice; floor is now Python >= 3.11).
  `core` is the default profile. **The house layer is additive, never
  substitutive**: under `casa`, the 13 core checks run **plus** the 3 house
  checks (16 total); not enabling `casa` never removes a core check, it just
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

Check catalog (13 core + 3 opt-in house-layer checks):

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
| `CHK-19` | More than one table in the file | Critical / Important | core |
| `CHK-20` | Blank line inside the table | Important | core |
| `CHK-12` | TST-\*/AUD-\* scheduled before what it covers | Critical | **house** |
| `CHK-13` | INBOX: duplicate table ID or invalid format | Important | **house** |
| `CHK-14` | Missing Wiki + beginner-doc item in the last wave | Cosmetic | **house** |

### `--fix` (byte-preserving mechanical fix)

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
- **Two correction classes (real scope, FIX-ESCOPO-2)**: `escapar_pipe_cru`
  (from `CHK-02`: escapes a raw `|` found unambiguously inside a code span) and
  `remover_fragmento_duplicado` (from `CHK-01`: removes the occurrence of a
  duplicate ID the heuristic recognizes as an obvious fragment/leftover). There
  is no third or fourth class: consolidating a fragmented table and rewriting a
  claim in the Description **move rows** in a third-party file and stay **out**
  of auto-fix (human judgment / `--reorder` / manual edit). Fixed rule: the
  audit **never** sets `fixable=True` without a matching fixer in the engine.
  Even within `escapar_pipe_cru` the engine is more conservative than the check
  -- it refuses to apply (flagging `[NOT APPLICABLE]` in the report, with the
  reason) whenever the raw pipe's position isn't unambiguous.
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

**Concurrency (v1.2):** the `--apply` path acquires `TodoWriteLock`
(`tools/todo_lock.py`, same lock as intake/drain) **before** re-checking a clean
working tree and writing -- serializes two `--fix --apply` on the same TODO
(default timeout 10s; lock failure = exit 1). Dry-run does **not** take the lock.
Platform residual: Windows `os.replace` against a read-only destination has no
empirical proof in the matrix (generic `OSError` handling covered by mocks).
Detail in [`tools/README.md`](tools/README.md).

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

### Mechanical core (`tools/`, optional day-to-day, generic)

Besides the skill itself (agent-driven planning), the repo ships local,
deterministic scripts in [`tools/`](tools/README.md), no LLM/agent involved:

| Script | Role |
|---|---|
| `todo_intake.py` | `--add` / `--drain` (L0/SCOPED/FULL/residual cascade) |
| `intake_agent_bridge.py` | `DISCOVERED_WORK` -> judgment flags |
| `intake_journal.py` | write-ahead journal + orphan recovery |
| `todo_audit.py` / `todo_fix.py` | structural audit and auto-fix (2 classes) |
| `todo_migrate_inbox.py` | migrates legacy layout (INBOX after the table) to canonical order |
| `todo_sync.py` / `todo_health.py` | status sync and report + `TAB_*` lines |
| `session_signals.py` | freshness predicates (`TAB_*`) |
| `todo_lock.py` | write lock (intake/drain/fix apply) |
| `wsjf.py` | Fibonacci WSJF (topology **before** score) |
| `bus_contract.py` | bus message contract (sender never scores) |
| `concurrent_inbox.py` | `inbox/*.md` fallback across sessions |
| `todo_freshness.py` + `hooks/` | post-commit warning (warn-only) |
| `submodule_pin_drift.py` | submodule pin drift (read-only) |

**HOOKSRC-1:** global `core.hooksPath` must point at a **published install**
(pinned submodule in the consumer), **never** at this product's development
checkout. Detail and OS degradation in [`tools/README.md`](tools/README.md).

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
SKILL.md                 -- skill definition (schema, flow, intake, signals)
TESTES.md / AUDITORIAS.md -- this project's own catalogs
docs/adr/                -- ADRs (0001 core/house; 0002 intake + INBOX exception)
docs/para-iniciantes.md  -- beginner guide (starts from zero)
docs/campanha/           -- historical campaign plan (not living product doc)
references/              -- norms: freshness, TAB_* signals, hub, bus, cutover
tools/                   -- generic core (intake, audit, fix, sync, lock, wsjf, ...)
tools/hooks/             -- git hook shims + session reminder
tools/ci/                -- CI guards
tests/                   -- pytest suite + synthetic corpus
templates/               -- vault fragments and discovery contract
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
