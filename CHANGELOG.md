# Changelog

<!-- markdownlint-disable MD024 -->
<!-- O formato Keep a Changelog repete os mesmos titulos de secao
     (Adicionado, Corrigido, Alterado, Seguranca) em CADA versao, por
     definicao. A MD024 proibe titulos iguais no mesmo documento, o que e
     incompativel com o formato adotado. -->

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.2.0] - 2026-08-16

Entrega o **motor de intake** (ADR-0002 deixou de ser só arquitetura: vira comportamento
publicado) e as Fases 2-11 do plano de melhoria no *produto* público: captura, WSJF Fibonacci,
dreno da INBOX residual, sinais de sessão, templates de vault, contrato de bus, guarda de hub,
corpus de regressão e cutover/dogfood. **Não** inclui bump do pin de submódulo no `claude-memory`
nem migração de vaults externos -- isso é trabalho do repositório consumidor (Fase 12 / TAB-REL),
fora deste pacote.

### Adicionado

- **`--add` / núcleo de intake** (`tools/todo_intake.py`, TAB-ADD-000..007): cascata fixa
  DUPLICATE -> NEEDS_TRIAGE -> NEEDS_LEADER_DECISION -> FULL (fundação) -> LOCAL (L0) -> SCOPED ->
  FULL (default). `WorkCandidate` com flags de julgamento preenchidas por quem chama (a skill/
  agente); o núcleo **não** infere prosa. Persistência L0 (append puro + marcador
  `<!-- intake:id -->`), SCOPED (subgrafo `S` com equivalência byte-a-byte fora de `S` e
  promoção a FULL se fração/multi-Grupo) e FULL (topo estável + ondas). Pré-condição de working
  tree limpa no `--apply`; abort se houver INBOX classificável (drain-first).
- **Journal write-ahead** (`tools/intake_journal.py`): grava antes de mutar L0/residual/DUPLICATE;
  `mark_done` após escrita validada; recuperação de órfãos (`TAB_INTAKE_RECOVERY_REQUIRED`).
- **`--drain` e INBOX como exception queue** (TAB-INBOX-001..004, TAB-CUT-001): dry-run lista;
  apply com `--judgments-json` (`integrate` / `split` / `keep`); residual com triage válido só
  incrementa `cycles`; `needs-leader-decision` não auto-integra. Pós-condição de apply:
  `classifiable_inbox_count == 0`. Linhas legadas sem `[triage ...]` saem como
  `legacy_inbox_line` no dry-run (compat sem editar todos os TODOs à mão).
- **Metadado de triagem** (Fase 2A): linhas residual com `[triage ...]` (reason, cycles, since);
  `classifiable_inbox_count` separado de residual válido.
- **Dedup por texto** (TAB-ADD-002): descrição normalizada (strip, colapsa whitespace, casefold)
  contra tabela e residual; critérios de aceitação iguais se ambos tiverem o campo; sem NLP.
- **Bridge agentivo** (`tools/intake_agent_bridge.py`, TAB-CONC-001): bloco `DISCOVERED_WORK` ->
  flags; subagentes não editam `TODO.md`.
- **Motor WSJF Fibonacci** (`tools/wsjf.py`, TAB-WSJF-001..007): régua `(1,2,3,5,8,13,20)`;
  topologia **antes** de WSJF; rank estável com pin de WIP; profiles `early`/`safe`;
  `source=bus` ignora rótulos retóricos (só ints fib explícitos).
- **Sinais de frescor e adapter de sessão** (`tools/session_signals.py`,
  `tools/hooks/tab_pendencias_reminder.py`, TAB-HOOK-001..004, INTAKE-AGE-1): sinais `TAB_*`
  (CREATE / SYNC / TRIAGE / CONCURRENT / LEADER_AGED / VERIF / RECOVERY); residual aged =
  `cycles >= triage_max_cycles` **ou** idade em dias; adapter só wiring (stdin JSON fail-open,
  exit 0); regra de negócio no motor, não no hook. Contrato em
  `references/sinais-de-frescor.md`.
- **Concorrência** (TAB-CONC-001..004): `tools/todo_lock.TodoWriteLock` (fcntl / msvcrt /
  exclusive-create + stale); `tools/concurrent_inbox.py` grava `inbox/*.md` entre sessões sem
  orquestrador comum; health emite `TAB_CONCURRENT_INBOX_PRESENT`.
- **Templates de vault + recovery** (TAB-VAULT-001..005): fragmentos em `templates/vault/` e
  contrato de discovery em `templates/agents/`; `scripts/recovery_drill.py` monta vault sintético
  e prova que o path do hook resolve **dentro** do dest. Templates são artefatos do *produto*;
  copiar/aplicar no vault vivo do líder **não** é desta release.
- **Contrato de bus** (`tools/bus_contract.py`, TAB-BUS-001..003): `BusMessage`, `extract_facts`,
  `candidate_from_bus` (sempre `source=bus`), `archive_allowed` só com rastro; prosa "urgente"/
  `claimed_priority` nunca pontuam. Corpus sintético `tests/corpus/bus/`; reference
  `references/bus-versus-inbox.md`.
- **Guarda de hub derivado** (TAB-HUB-001): `hub_is_derived_readonly` em `run_intake`/`run_drain`
  apply quando `[hub] derived=true`. Reference `references/hub-agregador.md`. Gerador do hub
  (`TAB-HUB-GEN`) **ainda não existe** -- anti-OE, não inventado nesta fatia.
- **Corpus e propriedades Fase 10** (TAB-TST-001..005, TAB-SEC-001, TAB-COMPAT-001): F10-01..26,
  propriedades (`no_lost_work`, `classifiable_zero_after_apply`, topologia, WIP, sender sem
  prioridade), mutação em cópia `/var/tmp`, e2e de instalação, compat 8/9 colunas + offline/stdlib.
- **Cutover / dogfood** (TAB-CUT-002..005): `scripts/dogfood_metrics.py` (exit 0 se
  `classifiable==0`, senão 2); `references/cutover-and-rollback.md` (canaries, métricas,
  rollback que preserva journal/`inbox/`). Neste repositório, INBOX classificável drenada
  (FIX-RISCO -> itens de investigação; dogfood `classifiable==0`).
- **Roteamento da skill (SKILL-DESC-2):** `description:` do frontmatter anuncia `--audit`,
  `--fix`, `--add` e `--drain` sem inverter o destaque histórico de `--create`/`--reorder`.

### Alterado

- **Semântica da INBOX no `SKILL.md` (corpo):** deixa de ser fila normal de descoberta; vira
  exception queue residual do pipeline de intake. Norma antiga marcada como histórica.
  `references/frescor-da-tabela.md` alinhado.
- **Health** (`todo_health.py`): consome `session_signals`; `TAB_TRIAGE_REQUIRED` = classifiable
  **ou** residual aged **ou** `inbox/` concorrente -- não contagem bruta de residual de líder
  fresco.
- **Guard anti-fixture:** `LIMITE_LINHAS_DADOS` 100 -> 150 (tabela canônica do produto passou o
  teto antigo sem ser fixture vazada).

### Corrigido

- Lint Markdown do `TODO.md` (linha em branco extra que quebrava o job, TAB-CONC-004).
- Testes que montavam "segredos" falsos em pedaços (TAB-ADD-000) para não disparar o gitleaks.

### Segurança

- Nenhuma CVE/segredo novo nesta faixa. Fronteira pública x privada reafirmada no corpus F10
  (fixtures sintéticas, guards stdlib + no-real-fixtures, sem corpo de bus privado versionado).
- **Fora de escopo desta tag:** avançar o pin `skills/tab_pendencias` no `claude-memory`, force
  de push, ou declarar o remoto "fonte recuperável" sem a Fase 12 executada no consumidor.

### Limitações conhecidas nesta versão

- O pin de submódulo no repositório consumidor **não** foi atualizado aqui; quem clona só o
  `claude-memory` antigo ainda não recebe o motor 1.2.0 até o TAB-REL-003 do lado consumidor.
- `TAB-HUB-GEN` (gerador determinístico do hub) permanece pendente.
- Escopo do `--fix` continua com **2** classes auto-aplicáveis (sem mudança desde 1.1.0).
- Decisões do líder ainda em fila de produto (piso Python 3.11, exceção anti-mdash do repo,
  hooks da instalação publicada, verbo-só em status legado, etc.) **não** fecham nesta tag.

## [1.1.0] - 2026-08-16

### Adicionado

- **Detector de drift do pin de submódulo** (`tools/submodule_pin_drift.py`, TAB-SOT-007): fecha
  o buraco de distribuição que motivou a Fase 0 do plano de melhoria -- o gitlink de
  `skills/tab_pendencias` em `claude-memory` ficou 67 commits atrás da revisão publicada sem que
  nada acusasse, e um `clone --recursive` restaurava a skill sem o toolkit inteiro. Read-only,
  warning-only e offline-first: lê o SHA pinado por `git ls-tree HEAD` (não `git submodule
  status`, que falha quando o submódulo nunca foi inicializado), consulta o remoto só por
  `git ls-remote` (nunca `git fetch`, mesma política do CHK-09) e, sem rede, declara
  `nao_verificavel` -- nunca `atualizado`: fingir frescor quando não deu para consultar nada é
  pior que não ter detector. Distingue as **cinco posições relativas** entre o pin e a última
  release (igual, atrás, à frente, divergente em outra linha de história, indeterminado) em vez
  de tratar qualquer diferença como atraso -- a primeira versão do detector, corrigida antes de
  chegar a este lançamento, disparava aviso também para um pin à frente da tag, que é o estado
  normal de um repositório entre duas releases; alarme que dispara sempre é alarme que se aprende
  a ignorar. Caminho e URL do submódulo são parâmetros, com `.gitmodules` como único fallback --
  zero nome de projeto embutido, conforme o requisito canônico de ser agnóstico a projeto. Nunca
  faz `git submodule update --remote`, auto-commit ou auto-push; o código de saída é sinal, não
  bloqueio. Documentado em `tools/README.md`, com um snippet de job do GitHub Actions
  deliberadamente não ligado a nenhum workflow deste repositório -- o gêmeo de CI pertence ao
  repositório consumidor, fora do escopo desta fatia.
- **ADR-0002 aceito** (`docs/adr/0002-maquina-de-estados-de-intake-e-inbox-como-fila-de-excecao.md`):
  desenha uma máquina de estados de intake -- cascata ordenada de guardas com default -- que
  substitui "toda descoberta nova vai para a INBOX e alguém drena depois" e define a INBOX como
  fila de exceção residual. **É arquitetura aprovada pelo líder, não comportamento entregue**:
  nenhum código de intake foi tocado nesta release nem em nenhuma anterior. A superfície de
  comando do produto continua sendo só `--audit`, `--fix`, `--create` e `--reorder`; não existe
  `--add` nem drenagem automática da INBOX.
- **`--fix` alcançável por linguagem natural** (SKILL-DESC-1): o comando já existia, implementado
  e documentado no corpo do `SKILL.md`, mas faltava no `argument-hint` e na linha de roteamento.
  Num clone limpo, quem pedia "corrigir a tabela" não era roteado para ele -- funcionalidade
  pronta e inalcançável. Corrigido só o roteamento; a reescrita da `description:` do frontmatter
  que decide *se* a skill é invocada ficou fora de propósito, por mudar comportamento de disparo
  sem revisão dedicada (registrada para decisão do líder).

### Corrigido

- **`todo_sync.py` crashava de verdade no Windows (ENC-WIN-1), em versão já publicada.** O script
  imprime emoji direto em stdout sem nunca reconfigurar o stream para UTF-8; no console padrão do
  Windows (codepage cp1252) isso não degrada, crasha com `UnicodeEncodeError` e traceback cru,
  violando também o contrato de exit code -- e é justamente o script que escreve na `TODO.md` do
  usuário. `todo_health.py` e `todo_freshness.py` já tinham o guard; faltava no irmão que mais
  precisava dele.
- **Varredura sistemática de encoding e caminho no Windows** (WIN-CLI-1, WIN-GITMOD-1), feita por
  enumeração AST dos 55 call sites de `subprocess` do repositório, não por grep: 37 chamadas em
  modo texto sem `encoding=` fixado, todas corrigidas. Dois defeitos de produto encontrados na
  varredura, os dois em versão já publicada:
  - `chk_frescor.py` invocava `todo_sync.py` por subprocesso sem fixar encoding; no Windows a
    saída do filho (já UTF-8 correto) decodificava com a codepage local, o erro morria numa
    thread daemon da stdlib, `stdout` virava `None` em silêncio, e a proposta do CHK-10
    simplesmente não chegava ao relatório -- relatório incompleto sem sinalizar nada.
  - `todo_audit.py` e `todo_fix.py` nunca reconfiguravam stdout/stderr para UTF-8, apesar de
    texto não-ASCII no próprio fonte; os outros quatro entrypoints já tinham o guard.

  Também corrigidos, no mesmo levantamento: `todo_lib.py`, `submodule_pin_drift.py` e
  `guard_no_real_fixtures.py` capturavam saída de `git` em modo texto sem encoding. Os 15 testes
  de `test_submodule_pin_drift.py` que falhavam no Windows não eram defeito do módulo novo: a
  fixture gravava a URL do remoto no `.gitmodules` com separador nativo do SO, e o `git config`
  trata barra invertida como escape (`bad config line`) -- o produto se comportava corretamente,
  capturando o erro e devolvendo mensagem graciosa em vez de crashar; a fixture foi corrigida
  para normalizar a barra. Dois testes adicionais de permissão/substituição de arquivo, que
  codificavam semântica POSIX que o Windows não compartilha, foram pulados com motivo explícito
  em vez de terem a asserção relaxada (ver "Cobertura conhecida" abaixo).

  Não verificado por execução real em Windows nesta release: a máquina de desenvolvimento é
  Linux. Os mecanismos foram reproduzidos aqui com git e Python reais -- inclusive o texto de
  erro idêntico ao do CI, byte a byte -- mas o silêncio específico do Windows (a exceção que
  morre na thread leitora em vez de propagar) não é reproduzível fora dele; a prova final foi a
  volta de CI verde no job `windows-latest`.

- **Classificação de status em tabela legada promovia sozinha item de design (PRED-FALLBACK-2),
  defeito de integridade de dado presente desde a v1.0.2.** No fallback de tabela sem emoji, o
  predicado de elegibilidade a flip reconhecia os compostos "pendente design"/"andamento design"
  só por adjacência exata de string; qualquer separador diferente de espaço simples, palavra
  intercalada, ou o radical "andamento" caíam de volta na regra de posição, onde o radical vence
  o qualificador. Como quem consome esse predicado é `todo_sync.py` -- o script que escreve na
  `TODO.md` do usuário --, um item de design em tabela legada podia ser promovido sozinho a
  "Pendente verificação", em silêncio, num arquivo de terceiro; a regra D-1 proíbe flip de item
  de design sem exceção. Trocado por co-ocorrência restrita de radical mais qualificador, em vez
  da prioridade fixa do formato legado (que resolveria este caso mas ressuscitaria outros quatro
  já corrigidos). Auditoria por matriz enumerada de 216 combinações: 90 divergiam do
  comportamento esperado antes do conserto, 0 depois.

- **CI vermelho desde 28/07 -- as duas releases anteriores, v1.0.1 e v1.0.2, foram publicadas
  nesse estado -- volta a ficar verde nas nove tarefas** pela primeira vez desde então. Causa
  comum às cinco plataformas da matriz (CI-BRANCH-1): a fixture que fabrica repositórios git de
  teste herdava o `init.defaultBranch` do ambiente -- "main" na máquina de desenvolvimento,
  "master" nos runners --, quebrando uma asserção do CHK-09 que dependia do nome do branch. Não
  era defeito do produto: era suposição implícita de ambiente na própria fixture, o tipo exato
  de suposição que o requisito de agnosticismo de plataforma proíbe. Mais duas falhas exclusivas
  do job `archlinux` (CI-ROOT-1), reproduzidas em container real: `git` recusando o repositório
  por "dubious ownership" (checkout populado com o UID do runner-host, passos rodando como root
  do container) -- resolvido registrando `safe.directory` só para o workspace do job, nunca
  `*` -- e um teste que esperava falha de escrita sem permissão, inalcançável porque root ignora
  bits de permissão POSIX.

### Cobertura conhecida

- **Dois testes de `test_todo_fix.py`, os únicos que provam o comportamento do `--fix` diante de
  arquivo/diretório sem permissão de escrita, ficam sem exercício em parte da matriz de CI.**
  `test_apply_arquivo_somente_leitura_e_substituido_via_rename_atomico` é pulado no Windows
  (`MoveFileEx` recusa destino somente-leitura, ao contrário de `os.replace` no POSIX, cujo
  comportamento o teste assume). `test_apply_diretorio_sem_permissao_de_escrita_falha_limpo` é
  pulado tanto no Windows (`os.chmod` não implementa bits de escrita de diretório lá) quanto sob
  root (que ignora bits de permissão POSIX) -- e é a única prova de que `--fix` falha limpo, sem
  corromper o `TODO.md` original, quando não consegue escrever. Nenhum dos skips relaxa a
  asserção original: os dois documentam divergência real de modelo de permissão entre
  plataformas, com motivo explícito e visível em `-rs`. Registrado como cobertura perdida, não
  como decisão silenciosa.

## [1.0.2] - 2026-07-29

### Corrigido

- **Classificacao de status em tabela legada (sem emoji) decidia por
  "contem o radical" em vez de "o status e este".** Consequencias medidas:
  uma celula como `Pendente (verificar disponibilidade)` nao era reconhecida
  como pendente nem ficava elegivel a sincronizacao, porque a anotacao entre
  parenteses mencionava outro vocabulo; e `Concluido e verificado` saia com
  `is_done` e `is_awaiting_verification` **ambos verdadeiros** -- dois dos
  sete status canonicos, mutuamente exclusivos por contrato, o que faria o
  relatorio de saude contar o mesmo item em duas colunas.

  Agora o vocabulo canonico que aparece **primeiro** na celula decide a
  categoria, com os compostos (`Pendente design`, `Pendente verificacao`)
  tratados antes da regra de posicao. A exclusividade mutua passa a ser
  garantida por construcao.

  **Impacto:** nenhum em tabela que usa o vocabulario com emoji -- essa
  camada nao foi tocada e continua identica. O alvo e a tabela de quem
  chega sem o vocabulario desta casa, que e justamente o primeiro contato
  de quem adota a ferramenta.

## [1.0.1] - 2026-07-28

### Corrigido

- **A receita de instalacao "por projeto" do hook local nao funcionava.** A
  seção correspondente de `tools/README.md` mandava copiar os shims e o
  script para dentro de uma mesma pasta, mas o shim procura o script um
  nivel acima (o layout do repositorio separa `tools/hooks/` de `tools/`), e
  a receita nao mandava copiar o modulo que o script importa. Seguindo o
  passo a passo ao pe da letra, o hook falhava com "arquivo nao encontrado".
  Era a primeira coisa que um usuario novo executava. A receita agora
  preserva a relacao de pastas que o shim espera, e ha teste automatizado
  (`tests/test_install_recipe_e2e.py`) que executa **as duas** receitas
  literalmente e faz um commit de verdade -- os testes anteriores chamavam o
  script direto, sem passar pelo shim, que era exatamente onde o defeito
  vivia. A receita de instalacao global ja funcionava e agora tambem tem
  teste.

### Adicionado

- **Documentacao para iniciante em computacao** (`docs/para-iniciantes.md`):
  guia do zero, sem assumir conhecimento de terminal, git ou Markdown, com
  entrada e saida reais de cada comando e um glossario.
- **Wiki do repositorio** publicada, com paginas de comandos, conceitos e
  solucao de problemas.

## [1.0.0] - 2026-07-28

Primeira versão estável do toolkit `tab_pendencias`: skill + scripts de
linha de comando distribuíveis, agora vivendo dentro do próprio repositório.

### Alterado

- **Relicenciamento para GPL-3.0-or-later.** A versão anterior era distribuída
  sob PolyForm-Noncommercial. Esta é a mudança de maior impacto para quem já
  usava o projeto: revise os termos antes de atualizar, especialmente se o uso
  era comercial (o que a licença anterior restringia e a atual permite, dentro
  das obrigações do GPL). `LICENSE` na raiz contém o texto oficial completo;
  os módulos do núcleo trazem cabeçalho GPL completo, os shims de hook em
  `tools/hooks/` usam `SPDX-License-Identifier: GPL-3.0-or-later`.
- **Absorção do toolkit para dentro do repositório.** Os 4 scripts
  (`todo_lib.py`, `todo_sync.py`, `todo_health.py`, `todo_freshness.py`), os
  7 shims POSIX de hook (`tools/hooks/`) e a suíte de testes que antes viviam
  fora do repositório agora fazem parte dele, em `tools/` e `tests/`. Quem
  instalava a partir do local antigo precisa apontar para o novo caminho (ver
  `README.md`, seção de instalação e matriz de degradação).
- **Classificação de status por emoji-prefixo.** O critério de reconhecimento
  de status mudou: antes, a checagem de "pendente verificação", "concluído"
  etc. casava por substring crua em qualquer parte do texto da célula (o que
  produzia falsos positivos, ex.: a palavra "inconclusivo" sendo lida como
  "concluído"); agora a classificação exige o emoji canônico no início da
  célula, com um fallback por palavra-inteira (não substring) só para tabelas
  legadas sem emoji. **Quem usava células fora do vocabulário canônico pode
  ver uma classificação diferente da versão anterior** ao atualizar; rode
  `--audit` (novo nesta versão, veja abaixo) para revisar como cada linha é
  lida hoje.
- **Fim de tabela revisado.** A regra de onde a tabela canônica termina foi
  reforçada: ela atravessa um heading quando o que segue é continuação do
  mesmo esquema de colunas, e encerra ao encontrar um segundo cabeçalho
  ID+Status, uma tabela de esquema diferente, ou o fim do documento. Tabelas
  grandes que antes eram cortadas prematuramente agora são lidas por inteiro.
- **`git diff-tree` do `todo_freshness.py` ganhou `--root`.** No primeiro
  commit de um repositório (sem pai), o comando antigo devolvia saída vazia e
  o aviso de "tocou código mas não citou ID" nunca disparava nesse commit.

### Adicionado

- **Comando `--audit`** (`tools/todo_audit.py`): auditoria estrutural
  read-only do `TODO.md`, offline e sem depender de LLM ou agent. Catálogo de
  14 checks (11 do perfil núcleo + 3 do perfil "casa", opt-in via
  `.tab_pendencias.ini`): integridade de tabela e vocabulário, grafo de
  dependências (ID inexistente, ciclo, onda inconsistente), claims obsoletas
  na Descrição verificadas contra o git real, e reconciliação de contagem.
  Relatório ordenado por severidade, com agrupamento de achados repetitivos e
  truncamento configurável (`--max-per-check`, achados Crítico nunca
  truncados). Suporta auditar um `TODO.md` fora do repositório corrente
  (`--todo <caminho>`). Exit codes `0` (sem achados), `1` (erro de execução),
  `2` (1 ou mais achados, de qualquer severidade).
- **Comando `--fix`** (`tools/todo_fix.py`): correção mecânica byte-preserving
  para achados que o `--audit` já marcou como auto-fixáveis. Dry-run por
  padrão; `--apply` escreve de fato, de forma atômica (arquivo temporário +
  substituição), e recusa rodar se a working tree do `TODO.md` estiver suja.
  Antes de gravar, prova os invariantes de round-trip byte-a-byte nas linhas
  não tocadas. Nunca muda `Status`, reordena linhas ou toca branch/commit.
  Exit codes na mesma convenção do `--audit`.
- **CI em 5 ambientes**: Ubuntu e Windows nativos, mais Debian, Fedora e Arch
  via container. Inclui guard de "nenhum import fora da stdlib", guard
  anti-vazamento de fixture real, `shellcheck` e smoke dos shims POSIX,
  lint de Markdown e varredura de segredos. Actions de terceiro pinadas por
  SHA de commit; imagens de container pinadas por tag+digest.
- **Contrato de CLI** (`argparse`, `--help`, exit codes `0`/`1`/`2`) nos três
  scripts com interface de linha de comando (`todo_sync.py`, `todo_audit.py`,
  `todo_fix.py`). Flag desconhecida agora é erro, não é mais ignorada em
  silêncio.
- `scripts/preci.sh`: pré-CI local que espelha os jobs do workflow do GitHub
  Actions na mesma ordem, para o vermelho não aparecer só no servidor.
- Suíte de testes própria para `todo_health.py` (único módulo que não tinha
  nenhuma cobertura) e teste end-to-end de `todo_freshness.main()` contra um
  `diff-tree` real.
- `references/`: versão internalizada da norma de frescor da tabela, para
  quem clona o repositório sem acesso ao vault do autor.
- ADR (`docs/adr/0001-*.md`) fixando a fronteira entre núcleo genérico e
  convenções da casa: nenhum check do núcleo pode depender do perfil "casa".

### Corrigido

- **ID duplicado exposto.** Antes, quando duas linhas da tabela citavam o
  mesmo ID, a última ocorrência vencia em silêncio (`parse_status_map` e o
  índice `by_id` de `todo_sync.py`) e nenhum teste detectava. Agora o
  duplicado é exposto de forma aditiva, sem travar a leitura.
- **Três predicados de fronteira** do parser: citação de ID em fim de frase
  (o ponto final não engolia mais o ID no lookahead), detecção de "tocou
  código" restrita a caminhos que começam por `inbox/` (antes, qualquer
  substring `/inbox/` em qualquer lugar do caminho disparava o predicado), e
  reconhecimento de cabeçalho de tabela que não dispara mais só por conter a
  palavra "status" em qualquer célula.
- **Falso positivo do guard "nenhum import fora da stdlib".** O guard de CI
  não reconhecia um subpacote real deste próprio repositório
  (`tools/checks/`) como módulo local, e o acusava como dependência externa.
  A resolução agora segue a mesma lógica de busca de módulo do interpretador
  Python (pacote com `__init__.py` ou módulo `.py`), não uma lista fixa.
- **Política de exceção e encoding unificada** entre os três scripts.
  `todo_freshness.py` engolia qualquer exceção de leitura em silêncio;
  `todo_sync.py`/`todo_health.py` encerravam de forma crua em erro de
  decodificação. Agora `todo_freshness.py` continua saindo com código 0
  (avisa e não bloqueia o commit) mas não mais em silêncio, e os outros dois
  scripts mostram mensagem clara e saem com código 1, com uma flag
  `-v`/`--verbose` comum para traceback completo. Comportamento exercitado
  ponta a ponta contra BOM e CRLF.

### Segurança

- **Bypass de escrita via link simbólico no `--output` do `--audit`.** A
  checagem que impede o `--output` de escrever dentro do repositório
  auditado normalizava o caminho sem resolver links simbólicos; um link
  apontando de fora para dentro do repositório contornava a proteção e
  permitia escrita onde o contrato promete somente leitura. Corrigido antes
  do lançamento, com prova de reprodução do ataque e da correção.
- **Incidente de privacidade.** Arquivos internos de planejamento foram
  versionados por engano num momento em que o repositório já era público,
  expondo dados internos do processo de desenvolvimento (não dados de
  usuários finais do toolkit). O histórico foi reescrito duas vezes para
  remover o resíduo por completo (uma reescrita inicial e uma segunda,
  motivada por uma auditoria de segurança que confirmou resquício ainda
  visível em commits antigos após a primeira correção), com force-push
  autorizado e verificação por clone limpo do remoto. Guard automatizado de
  CI reforçado com uma camada adicional que também varre conteúdo de
  arquivo (comentários e docstrings), não só nome de caminho.

## Limitações conhecidas nesta versão

- **`--fix` cobre 2 das 4 classes de correção previstas no ADR.** O desenho
  original antecipava também consolidar tabelas fragmentadas e corrigir
  claims obsoletas na Descrição; nenhuma das duas existe ainda porque nenhum
  check do catálogo marca esses achados como auto-fixáveis -- decisão
  registrada (mover linha de arquivo de terceiro é a operação de maior risco
  do produto), não uma lacuna esquecida.
- **Dois processos de `--fix --apply` simultâneos no mesmo repositório se
  sobrescrevem** sem aviso. A checagem de working tree limpa protege contra
  editar sobre uma mudança já commitada, mas não contra uma corrida entre
  dois processos que passam pela checagem quase ao mesmo tempo; não há trava
  de sistema operacional.
- **Janela entre leitura e escrita sem trava de sistema operacional** em
  qualquer fluxo de ler-modificar-escrever do `--fix`; a pré-condição de
  árvore limpa mitiga, não elimina.
- **Comportamento do `--fix` em Windows contra um destino somente-leitura não
  tem prova empírica** nesta versão; a matriz de CI não exercita esse
  caminho específico.
- **O piso mínimo de versão de Python não é garantido por teste.** A escolha
  de usar `configparser` (INI) em vez de um formato que exigisse Python
  3.11+ foi deliberada para não excluir distribuições com versões mais
  antigas, mas nada no projeto hoje declara ou testa esse piso: a matriz de
  CI testa apenas versões acima dele.

[1.2.0]: https://github.com/petrinhu/tab_pendencias/releases/tag/v1.2.0
[1.1.0]: https://github.com/petrinhu/tab_pendencias/releases/tag/v1.1.0
[1.0.2]: https://github.com/petrinhu/tab_pendencias/releases/tag/v1.0.2
[1.0.1]: https://github.com/petrinhu/tab_pendencias/releases/tag/v1.0.1
[1.0.0]: https://github.com/petrinhu/tab_pendencias/releases/tag/v1.0.0
