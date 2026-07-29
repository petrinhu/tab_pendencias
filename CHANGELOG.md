# Changelog

<!-- markdownlint-disable MD024 -->
<!-- O formato Keep a Changelog repete os mesmos titulos de secao
     (Adicionado, Corrigido, Alterado, Seguranca) em CADA versao, por
     definicao. A MD024 proibe titulos iguais no mesmo documento, o que e
     incompativel com o formato adotado. -->

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

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

[1.0.0]: https://github.com/petrinhu/tab_pendencias/releases/tag/v1.0.0
