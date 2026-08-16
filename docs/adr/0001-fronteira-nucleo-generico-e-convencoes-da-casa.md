# ADR-0001: Fronteira nucleo generico x convencoes da casa, contrato do parser, e limites de `--audit`/`--fix`

**Status:** Aceito
**Data:** 2026-07-28
**Decisores:** petrus (lider), via `software-architect` (autor deste ADR)
**Itens do TODO.md cobertos:** ADR-1 (bloqueia BUG-5, SPRAWL-1, e indiretamente AUDIT-ENG/CHK-CORE)

## Contexto

O `tab_pendencias` deixa de ser uma skill de uso pessoal e passa a ser um **produto
distribuido** (`prompt_inicial.md` SS4.0, "PRINCIPIO-MESTRE: generica e agnostica a projeto").
Um terceiro que clona o repo com so `git` + `python3` tem de conseguir usar o nucleo (parser,
`--audit`, `--fix`, sync/health/freshness) sem nenhuma das dependencias hoje implicitas: a
constelacao de agents (`cosmo-coo`, `software-architect`, `tech-lead`, `product-manager`,
`engineering-manager`, `scrum-master` -- `SKILL.md:107,117-120,241`), os wikilinks `[[ORG]]`,
`[[AGILE]]`, `[[CONTRACT]]`, `[[TOOLING]]` que so resolvem no vault do autor (`SKILL.md:84,107,242`),
e a regra fixa de item de Wiki+doc-iniciante (CHK-14).

Ao mesmo tempo, o codigo real (`~/.claude/githooks/{todo_lib,todo_sync,todo_health,
todo_freshness}.py`, ainda nao absorvido -- `tools/` do repo so tem `.gitkeep`) tem varios
comportamentos que precisam de decisao explicita ANTES do conserto (SS3.2 do prompt): fim
implicito da tabela canonica (SPRAWL-1), descarte silencioso de linha malformada, e a ausencia
de qualquer mecanismo formal de "isto e uma convencao da casa, aquilo e nucleo". Sem fixar isso
agora, cada conserto subsequente (BUG-5, SPRAWL-1, AUDIT-ENG) reinventaria a fronteira de forma
inconsistente -- exatamente a classe de deriva que ja produziu o README documentando 8 colunas
enquanto o `SKILL.md` ja praticava 9 (SS2.1 do prompt).

As decisoes D-1..D-8 (`decisoes_lider.md`) ja fecham varios eixos (emoji-prefixo, licenca GPL-3,
monorepo, exit codes, fim de tabela no heading). Este ADR nao rediscute nenhuma delas; formaliza
COMO elas se materializam em codigo e preenche as lacunas de mecanismo que as decisoes nao
especificaram no nivel de implementacao.

## Decisao

### (a) Fronteira nucleo generico x convencoes da casa

**Mecanismo de declaracao: atributo obrigatorio no registro do check, mais separacao de
diretorio.**

`tools/todo_audit.py` define um registro central de checks como uma lista de instancias de uma
dataclass:

```python
@dataclass
class Check:
    id: str                  # "CHK-01".."CHK-14"
    title: str
    profile: Literal["core", "casa"]   # campo OBRIGATORIO, sem default
    severity_default: Literal["CRITICO", "IMPORTANTE", "COSMETICO"]
    run: Callable[[Context], list[Finding]]
```

`profile` sem valor-default forca toda nova adicao ao registro a declarar explicitamente de que
lado da fronteira o check esta -- omitir o campo e `TypeError` na importacao, nao um bug latente
descoberto em producao. Isso e deliberadamente mais forte que:

- **Alternativa rejeitada -- convencao de nome/faixa numerica** (ex.: "CHK-14+ e sempre casa"):
  nao enforcavel por ferramenta nenhuma, quebra na primeira vez que um novo check core ganhar
  numero na faixa errada, e e exatamente o tipo de acoplamento implicito que este projeto ja
  sofreu (README/SKILL.md fora de sincronia, SS2.1).
- **Alternativa rejeitada -- arquivo de config decide por check** (mapa externo
  `id -> profile`): duplica a informacao entre o codigo do check e o mapa; a mesma classe de
  deriva de duas fontes.

Reforco estrutural: a logica especifica de convencao da casa (hoje so CHK-14, Wiki+doc-iniciante)
mora num subpacote `tools/casa/`; os checks com `profile == "core"` NUNCA importam nada de
`tools.casa`. Um teste unitario itera `CHECKS`, filtra `profile == "core"` e usa
`inspect.getmodule(check.run).__name__` para garantir que nenhum modulo comeca com `tools.casa`
-- e o teste que torna a regra "nenhum check do nucleo pode depender do perfil casa" (o mandato
literal do item ADR-1 no TODO.md) verificavel em CI, nao so uma frase de doc.

**Mecanismo de ativacao/desativacao: arquivo de config no repo do USUARIO, com flag de CLI como
override pontual. Sem variavel de ambiente. (D-9, D-10, decisoes_lider.md)**

- **D-10 -- nome e local do arquivo, FECHADO:** `.tab_pendencias.ini` na raiz do repo onde a
  tabela vive (nao no repo da skill), junto do `TODO.md`. Secao `[profile]`, chave
  `name = casa`. Ausencia do arquivo, ou ausencia da chave, significa perfil `core` -- o default
  e sempre o mais restrito/generico, coerente com "OPT-IN" (SS4.0.3 do prompt: convencoes da
  casa "sao OPT-IN configuravel").
- **D-9 -- formato do arquivo, FECHADO:** INI, lido com `configparser` da stdlib (nao TOML).
  Motivo **historico** registrado na epoca: `tomllib` so existia na stdlib a partir do Python
  3.11, o que excluiria Ubuntu 22.04 LTS (3.10) e RHEL 9 (3.9). **Atualizacao PYFLOOR-2
  (16/08/2026):** o piso oficial do nucleo passou a ser **Python >= 3.11** (declarado em
  `pyproject.toml` e coberto pela matriz de CI). O formato **permanece INI** por decisao
  explicita -- trocar para TOML quebraria configs ja publicadas de consumidores sem ganho
  proporcional; a justificativa do formato e agora de compatibilidade/estabilidade de
  contrato, nao de piso de Python. `configparser` aceita comentario, e para as poucas chaves
  que este projeto precisa (`[profile] name`, `[audit.chk09] patterns`) o TOML seria peso
  morto. **Nao havera parser proprio de fallback**: `configparser` e a unica implementacao.
- Flag de CLI `--profile core|casa` sobrepoe o arquivo para uma execucao pontual (util em CI ou
  para o proprio autor testar o perfil core isoladamente sem editar o arquivo).
- **Sem variavel de ambiente.** Uma env var e estado implicito, global ao shell, que sobrevive
  entre repos e projetos nao-relacionados -- a mesma classe de acoplamento invisivel que a regra
  de memoria do lider ja identificou como fonte de bug (`~/.claude/docs/` acoplado a maquina).
  Arquivo versionado no proprio repo e diff-avel, greppavel, e viaja com o clone; flag de CLI e
  visivel na linha de comando/log de CI.
- Quando o perfil ativo e `"core"` e existem checks `profile == "casa"` no registro, `--audit`
  imprime uma linha por check pulado (regra "no silent caps" da SS4.2): `"CHK-14 (convencao da
  casa) nao executado -- perfil ativo = core. Habilite com --profile casa ou
  .tab_pendencias.ini [profile] name = casa."`

### (b) Contrato do parser (invariantes testaveis)

1. **Round-trip byte-exato.** `parse_table` opera sobre `text.split("\n")` (`todo_lib.py:112`);
   a copia usada para reconhecer cabecalho/celulas (`s = line.lstrip(BOM).strip()`,
   `todo_lib.py:116`) e local a analise -- a lista `lines` retornada NUNCA e mutada pelo parse.
   A escrita (`set_status_cell`, `todo_lib.py:188-199`) separa o terminador original
   (`\r\n`/`\n`/nenhum) ANTES de tocar a celula e o reanexa depois (`todo_lib.py:192-193`), e
   `todo_sync.py:163` grava com `"\n".join(lines)`. Invariante testavel: para qualquer TODO.md
   de entrada, `"\n".join(parse_table(text)["lines"]) == text` antes de qualquer `set_status_cell`,
   e depois de N chamadas a `set_status_cell` restritas as celulas de Status, todo o resto do
   arquivo (incluindo BOM na primeira linha e terminador CRLF de cada linha) permanece
   byte-identico.
2. **Compatibilidade de leitura 8/9 colunas.** O cabecalho e localizado por NOME
   (`_is_header`, `todo_lib.py:100-102`: exige celula `"id"` e alguma celula contendo
   `"status"`), e `ncols` deriva do numero de celulas daquele cabecalho real
   (`todo_lib.py:126`), nunca de uma constante 8 ou 9 hardcoded. Invariante: uma tabela legada de
   8 colunas (sem `Onda`) parseia corretamente contanto que tenha coluna `ID` e uma coluna cujo
   nome contenha `status`; nenhum codigo do nucleo pode assumir `ncols == 9`.
3. **Escape GFM `\|`.** `_SEP = re.compile(r"(?<!\\)\|")` (`todo_lib.py:74`) trata `\|` dentro de
   uma celula como pipe literal do CONTEUDO renderizado, nunca como fronteira de coluna -- vale
   inclusive dentro de code span, e este e o UNICO mecanismo de escape que o parser reconhece
   (nenhum outro escape GFM e tratado especialmente). Round-trip preserva o `\|` intacto
   (`todo_lib.py:80-83`).
4. **Fim da tabela canonica (D-6, muda o comportamento atual de `todo_lib.py:130`).** Hoje o
   parser so encerra a tabela no 2o cabecalho ID+Status (`todo_lib.py:130`), o que causa
   SPRAWL-1: linhas de 9 celulas centenas de linhas abaixo, atravessando secoes inteiras, sao
   "engolidas". A partir do conserto SPRAWL-1, a tabela canonica encerra no **primeiro** dos
   dois eventos, na ordem em que aparecem varrendo o arquivo: (i) uma segunda linha de cabecalho
   ID+Status (comportamento ja existente, mantido), ou (ii) a primeira linha que comece com `#`
   (qualquer nivel de heading Markdown, de `#` a `######` -- D-6 diz "proximo heading markdown"
   sem qualificar nivel, e este ADR fixa "qualquer nivel" como a leitura correta: uma tabela nao
   deve atravessar nenhum heading, superior ou subordinado). `--audit` (CHK-03) reporta o span
   resultante (linha de inicio/fim, gaps de linhas nao-tabela atravessadas).
5. **Politica de linha malformada -- dupla, por design.** O nucleo (`parse_table`) permanece
   conservador: nunca escreve no lugar errado, nunca adivinha uma celula faltando. HOJE ele
   descarta em silencio (`todo_lib.py:132`, comentario "linha malformada: ignora (seguro)") sem
   deixar nenhum rastro de que descartou -- essa auscencia de rastro e a causa-raiz do "93% de
   uma tabela invisivel" (SS0 da missao). O contrato do parser MUDA aqui: `parse_table` passa a
   retornar tambem uma lista `malformed` (`[{line_no, raw, expected_ncols, got_ncols}]`) com toda
   linha que comecava com `|`, nao era separador, nao era cabecalho, mas tinha `len(cells) !=
   ncols`. Esta e uma chave ADITIVA ao dict de retorno -- `todo_sync.py`, `todo_health.py`,
   `todo_freshness.py` continuam ignorando-a e seu comportamento atual (silencioso para eles) NAO
   MUDA. O DIAGNOSTICO da causa provavel (pipe cru nao escapado? celula faltando? fragmento
   truncado?) e responsabilidade do `todo_audit.py`/CHK-02, que consome `malformed` e aplica a
   heuristica -- o nucleo nao cresce logica de auditoria. Resumindo a politica: **descarte
   silencioso permanece o comportamento do nucleo (sync/health/freshness nunca travam por causa
   de uma linha malformada), mas deixa de ser INVISIVEL: `--audit` sempre relata cada linha em
   `malformed`, com severidade CRITICO** (uma linha de tabela some do inventario do usuario --
   isso e sempre grave, nunca cosmetico).

### (c) Limites de `--audit` e `--fix`

- `--audit` e **sempre read-only**: nunca abre o TODO.md em modo de escrita, nunca chama git em
  modo que mute estado (sem commit/checkout/branch/reset). O modulo `--audit=repo` (CHK-15..18)
  fica fora do escopo da v1 (D-5); quando existir, mesma regra: so leitura.
- `--fix` aplica **apenas** as **duas** classes mecanicas e byte-preserving que existem no
  motor e nos checks (FIX-ESCOPO-2, confirmado pelo lider em 16/08/2026): escapar `|` cru
  (`escapar_pipe_cru` / CHK-02) e remover fragmento duplicado/truncado apos mostrar o diff
  (`remover_fragmento_duplicado` / CHK-01). **Nao ha terceira nem quarta classe no escopo
  real:** consolidar tabelas fragmentadas (CHK-03/04) e reescrever claim na Descricao
  (CHK-09) **movem linhas** em arquivo de terceiro -- operacao de maior risco -- e ficam
  fora do auto-fix (julgamento humano / `--reorder` / edicao manual). Regra fixa: um check
  **nunca** emite `fixable=True` / `fix_ref` sem o corretor correspondente existir em
  `tools/todo_fix.py`. `--fix` **nunca** muda Status (papel do sync ou do humano), nunca
  reordena (e `--reorder`), nunca toca branch/commit (repo-level fica sempre como comando
  pronto para o lider rodar com `!`, nunca executado pela skill).
- **Exit codes (D-6), fixos em 3 valores** -- nenhum exit code novo e inventado por nenhum check:
  `0` = execucao ok e zero achados; `1` = erro de execucao (excecao nao tratada, TODO.md
  ilegivel, nao e repo git quando exigido); `2` = execucao ok e ha pelo menos um achado, **de
  qualquer severidade, inclusive so COSMETICO**. Um pipeline de CI que quer tolerar cosmetico
  filtra por severidade DENTRO do relatorio, nao pelo exit code.
- **Onde mora "isto e [auto-fixavel] vs [julgamento]": no proprio check que produz o achado, nao
  numa tabela central.** Cada `Finding` emitido por um `Check.run` carrega um campo
  `fixable: bool` e, quando `True`, um `fix_ref` apontando para a rotina correspondente em
  `tools/todo_fix.py`. Alternativa rejeitada -- tabela central `achado_id -> fixavel`: exigiria
  manter N checks e a tabela central sincronizados manualmente, a MESMA classe de bug que ja
  aconteceu neste projeto entre README e SKILL.md (SS2.1: schema documentado em dois lugares,
  um ficou obsoleto). Co-localizar a decisao no check que gera o achado elimina essa classe de
  deriva por construcao: nao ha segunda fonte para desalinhar.
- Pre-condicoes de `--fix` (SS4.3): working tree do TODO.md limpa (`git status --porcelain
  <path>` vazio) -- senao aborta com exit `1`, nunca mistura com edicao em voo de outro agente.
  Apos aplicar: re-parse do arquivo + prova de round-trip do restante + contagem de itens
  esperada antes/depois (exceto quando o proprio fix for remocao de duplicata/fragmento, caso em
  que a contagem nova e explicitada ANTES de aplicar, nao depois).

### (d) Idioma no conteudo livre

- O vocabulario de status (os 7 textos exatos, `SKILL.md:33-41`) e hardcoded em pt-br **por
  contrato** -- essa e uma camada diferente de "conteudo livre": e o vocabulario fechado que a
  skill IMPOE, nao algo que o usuario escreve livremente. O fallback substring/word-boundary de
  D-1 (para tabela legada sem emoji) tambem opera sobre essa MESMA celula de vocabulario
  controlado -- continuar hardcoded em pt-br ali e correto e nao viola a regra de idioma; este
  ADR deixa isso explicito para nao confundir as duas camadas.
- Qualquer check que precise reconhecer PADROES em conteudo livre do usuario (Descricao, IDs,
  mensagens de commit -- CHK-09 e o caso concreto hoje) **nunca hardcodeia string literal no
  corpo do check**. Le de uma lista de padroes carregada de config, com DEFAULT embutido no
  codigo contendo pt+en (ex.: `["nao pushado", "not pushed", "commit local", "local commit",
  "branch "]`), extensivel (nao substituivel, salvo flag explicita de override) via
  `.tab_pendencias.ini`, secao `[audit.chk09]`, chave `patterns = nao pushado, not pushed,
  commit local, local commit, branch ` (string unica separada por virgula, dividida e stripada
  em codigo -- `configparser` nao tem lista nativa como o TOML; mesmo arquivo de config usado em
  (a), secao diferente -- um unico mecanismo de config para o projeto inteiro, em vez de
  reinventar leitura de arquivo por feature). Garantia estrutural, nao boa intencao: teste
  unitario garante que a lista default tem >= 1 padrao pt-br e >= 1 padrao en-us; o corpus
  sintetico AC-0 (descricoes em ingles, SS4.0.5/SS7) exercita e prova que CHK-09 dispara mesmo
  fora do idioma do autor.
- `cited_ids` (`todo_lib.py:177-185`) e `touched_code` (`todo_lib.py:49-62`) ja sao agnosticos a
  idioma (regex de fronteira de palavra sobre ID arbitrario; comparacao de caminho de arquivo) --
  este ADR fixa isso como invariante MANTIDA, nao como mudanca.

### (e) Agnosticismo de sistema operacional (D-11, decisoes_lider.md)

Reforco literal do lider: *"a skill e Claude, agnostica a OS: Windows ou Linux"* -- ela roda
como skill do Claude Code em qualquer sistema onde o Claude Code roda, e o nucleo tem que
acompanhar. Tres consequencias fixadas como requisito de implementacao e de teste:

1. **Nenhum check ou caminho do nucleo pode assumir POSIX.** Nada de separador `/` hardcoded
   fora de chamadas git (o git usa `/` internamente por contrato do proprio git, isso e ok --
   `todo_lib.py` ja nao hardcoda separador de path em lugar nenhum hoje); nada de assumir
   permissao de arquivo estilo Unix (`os.chmod` com octal Unix, bits de execucao); nada de
   assumir que existe um shell `sh` disponivel para o nucleo chamar (o nucleo e Python puro
   chamando `subprocess.run(["git", ...])` diretamente, nunca via `sh -c "..."`). Isto e
   invariante testavel: a suite de testes roda (ou o CI matrixa) em ubuntu E windows (`CI-1`
   ja promete essa matrix) exercitando os mesmos casos.
2. **A excecao explicita e os shims de git hook** (`_chain.sh` + os 7 shims POSIX,
   `tools/hooks/`): esses SIM dependem de um shell -- no Windows, do shell que vem com o Git for
   Windows. Isto NAO e suposicao silenciosa: e **degradacao documentada** no README (matriz de
   dependencia/degradacao ja prevista em SS4.4 do prompt) -- quem usa Windows sem Git for
   Windows instalado perde o sync mecanico via hook (`todo_freshness` automatico a cada commit)
   e mantem integralmente a parte agent-driven da skill (`--audit`/`--fix`/`--create`/`--reorder`
   chamados diretamente, sem depender do hook).
3. **Leitura e escrita de arquivo explicitas em encoding e newline.** Todo `open()` do nucleo que
   toca o TODO.md declara `encoding="utf-8"` explicitamente (nunca a codificacao default do SO,
   que no Windows nao e UTF-8) e, quando o round-trip byte-exato importa (leitura para
   `set_status_cell`/escrita), `newline=""` para nao deixar o modo texto do Python normalizar
   `\r\n` -> `\n` na leitura ou `\n` -> `os.linesep` na escrita (`todo_sync.py:115,164` ja fazem
   isso; `todo_health.py:53` e `todo_freshness.py:79` leem SEM `newline=""` porque so consultam
   status, nunca escrevem -- correto para o uso deles, mas o ADR fixa que qualquer novo caminho
   de ESCRITA no nucleo, incluindo `todo_fix.py`, MANTEM `newline=""`). Isto e o que faz o
   invariante (b.1) (round-trip byte-exato) valer igualmente em Windows e Linux -- conversa
   direto com o item `ENC-1` da tabela (unificar politica de excecao/encoding).

## Consequencias

**Positivas:**
- A pergunta "este check pode rodar sem a constelacao de agents?" tem resposta mecanica
  (`profile` no registro), verificavel em CI, em vez de depender de disciplina de code review.
- O parser ganha uma superficie nova (`malformed`) que fecha exatamente a lacuna que causou o
  incidente real do projeto (linha invisivel sem rastro) sem quebrar nenhum consumidor existente
  (chave aditiva).
- A fronteira `--audit`/`--fix` fica precisa o bastante para dois implementers diferentes
  chegarem no mesmo comportamento sem se falar.
- Encoding e newline explicitos em todo caminho de escrita do nucleo (secao (e).3) fazem o
  invariante de round-trip byte-exato valer igualmente em Windows e Linux, fechando uma lacuna
  de portabilidade que o codigo hoje ja acerta parcialmente (`todo_sync.py:115,164`) mas nunca
  documentou como regra obrigatoria para novo codigo (ex.: `todo_fix.py`, ainda por escrever).

**Negativas / aceitas como custo:**
- Um arquivo de config novo (`.tab_pendencias.ini`) e uma peca de infraestrutura a mais para
  manter e documentar -- mitigado por usar so `configparser` da stdlib, sem parser proprio
  (D-9).
- O campo `malformed` aumenta a superficie do dict retornado por `parse_table`; qualquer
  consumidor futuro que faca `dict(**parse_table(...))` ingenuamente ganha uma chave a mais --
  mitigado por ja documentar isso como aditivo desde o inicio.

**Riscos / pontos de atencao:**
- A separacao `tools/casa/` so protege se o teste de import for escrito ANTES do primeiro check
  `profile == "casa"` ser codado (senao vira convencao sem enforcement, a mesma classe de risco
  rejeitada em (a)). Recomendo que o teste de fronteira nasca junto com `AUDIT-ENG`, nao depois.
- CHK-02 usando `malformed` para diagnostico e heuristica (pipe cru vs celula faltando vs
  fragmento truncado): heuristica erra; o relatorio deve declarar quando o diagnostico e uma
  suposicao, nao um fato (coerente com "no silent caps").
- Os shims de git hook so funcionam com um shell disponivel (Git for Windows no caso Windows);
  se o README nao deixar essa degradacao obvia (secao (e).2), o usuario Windows sem Git for
  Windows perde o sync mecanico sem entender por que -- responsabilidade explicita de `SS4.4`
  (matriz de dependencia/degradacao) cobrir este caso especifico, nao so os agents/wikilinks.

## Alternativas consideradas

1. **Um unico "modo estendido" via flag boolean simples** (`--with-casa-checks`), sem registro
   por check nem arquivo de config -- mais simples de implementar, mas nao da lugar para o check
   se declarar estruturalmente, e um novo check "casa" poderia ser esquecido fora do filtro por
   engano do implementer (nada obriga a declaracao). Rejeitada: nao enforcavel.
2. **Convencoes da casa como plugin externo carregado por caminho** (o nucleo nem sabe que
   `tools/casa/` existe; um `--casa-plugin=<path>` externo registra checks em runtime) --
   mais "puro" no sentido de zero acoplamento, mas adiciona complexidade de carregamento dinamico
   de codigo (superficie de seguranca: codigo de terceiro executado via import dinamico) sem
   benefico real hoje (so 1 check, CHK-14, e casa). Rejeitada por over-engineering agora;
   registrar como caminho de evolucao se a lista de checks "casa" crescer muito.
3. **Tabela central de fixabilidade** (ja descrita e rejeitada em (c)).
4. **Env var para o perfil** (ja descrita e rejeitada em (a)).

## Reversibilidade

Two-way door parcial: o **mecanismo de registro** (`profile` no dataclass `Check`) e barato de
mudar antes do primeiro `--fix`/`--audit` publico rodar contra dados de terceiros -- e so codigo
interno, sem formato de arquivo exposto. Ja o **formato e nome do arquivo de config**
(`.tab_pendencias.ini`, nomes de chave -- **D-9 e D-10, FECHADAS pelo lider**) vira contrato
externo assim que a v1.0 for taggeada e terceiros comecarem a versionar esse arquivo nos proprios
repos -- depois disso, mudar o nome ou o formato exige um caminho de migracao/deprecation, nao e
mais gratis. Como D-9/D-10 ja fecharam nome e formato ANTES da tag `v1.0.0`, este risco esta
mitigado: nao ha janela em que o contrato externo mude depois de publicado.

## Questoes em aberto para o lider

Nenhuma. As duas questoes que este ADR levantava (versao minima de Python / formato do arquivo
de config, e nome/local do arquivo) foram resolvidas pelo lider como **D-9** e **D-10**
(`decisoes_lider.md`) e estao incorporadas como decisao fechada na secao (a) acima. O reforco de
agnosticismo de SO (D-11) esta incorporado na secao (e).
