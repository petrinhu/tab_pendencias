# ADR-0002: Maquina de estados de intake e INBOX como fila de excecao

**Status:** Aceito em 2026-08-16 pelo lider (gate ADR-1 do plano de melhoria). Ver "Decisao do lider" ao final.
**Data:** 2026-08-16
**Decisores:** petrus (lider), via `software-architect` executando `ARCH-EXTREME-01` (autor deste ADR)
**Itens cobertos:** TAB-ADR-001..TAB-ADR-005 do `PLANO-MELHORIA-TAB-PENDENCIAS-CLAUDE-CODE-2026-08-16.md` (Fase 1)
**Nao rediscute:** ADR-0001 (fronteira nucleo x casa, contrato do parser, limites de `--audit`/`--fix`), D-1..D-12 (`decisoes_lider.md`)

## Contexto

O desenho vigente manda toda descoberta nova para a INBOX (`SKILL.md:60`: "Trabalho novo
descoberto no meio do sprint NAO espera reordenar: vai para a INBOX na hora") e a INBOX so e
drenada por `--create`/`--reorder` (`SKILL.md:68`), que rodam quando alguem lembra. Isso e uma
fila duravel com **consumidor voluntario**: o trabalho e preservado, mas nada garante que seja
processado. A propria norma da casa ja previa o risco ("INBOX vira lixeira",
`~/.claude/docs/tabela-pendencias-frescor.md`, secao "Riscos residuais").

Ha ainda uma contradicao interna na skill: a secao de frescor manda tudo para a INBOX
(`SKILL.md:60`), enquanto a secao "Gatilho de reordenacao" (`SKILL.md:140-149`) diz que item
pequeno/local pode ser "so anexado" direto na onda adequada. A segunda regra esta mais perto do
comportamento desejado; a primeira virou o default operacional.

Fatos medidos nesta arvore em 2026-08-16 (nao os numeros desatualizados do plano):

- `TODO.md` deste repo: **48 itens** na tabela, **7 linhas na INBOX** (`TODO.md:66-72`:
  `FIX-ESCOPO-1`, `FIX-RISCO-1`, `PYFLOOR-1`, `MDASH-1`, `MIG-DIFF`, `FREEZE-GITHOOKS`,
  `SKILL-DESC-1`). O plano registra "2 itens" (secoes II.1 e TAB-CUT-002): esta desatualizado.
- `tools/todo_health.py`: **43 itens presos em 🔍 Pendente verificacao**. E uma segunda fila
  com consumidor voluntario, da mesma familia -- tratada na secao (k) deste ADR (fora do
  escopo da maquina de intake, com justificativa e trabalho descoberto registrado).
- Adesao a citar ID nos commits: 95% (57/60). A metade mecanica do frescor funciona; o que
  falta e liveness do consumo das filas.

Os 7 itens reais da INBOX sao o corpus deste desenho. Leitura relevante: **5 dos 7 dependem de
decisao do lider** (`PYFLOOR-1`, `MDASH-1`, `FREEZE-GITHOOKS`, `SKILL-DESC-1`, e a confirmacao
retroativa dentro de `FIX-ESCOPO-1`). Ou seja: a INBOX real ja converge para "fila de excecao";
o que falta nao e reclassificar o conteudo, e **(i)** impedir que o caminho normal despeje
trabalho classificavel ali e **(ii)** dar aos residuais legitimos um sinal de saida que nao
dependa de memoria humana.

## Decisao

### (a) Modelo: `WorkCandidate` e o pipeline de nove etapas

Toda descoberta e representada por um `WorkCandidate` conceitual com os campos de TAB-ADR-001:
descricao, origem (`user|bus|agent|audit|test`), evidencia, projeto receptor, dependencias
conhecidas, impacto estimado, status de decisao, e possivel relacao com item existente.

O pipeline e:

```text
captura -> normalizacao -> deduplicacao -> dependencias -> impacto -> scoring
        -> decisao de rota -> integracao -> validacao
```

Divisao mecanico x julgamento (o nucleo mecanico permanece offline, sem LLM e sem rede):

| Etapa | Natureza | Quem executa |
|---|---|---|
| captura (journal duravel) | mecanica | nucleo (Fase 2, TAB-ADD-000) |
| normalizacao (preencher campos) | julgamento | thread principal/agente |
| deduplicacao por ID exato | mecanica | nucleo |
| deduplicacao semantica | julgamento | thread principal/agente |
| grafo de dependencias (dado o declarado) | mecanica | nucleo |
| medicao de impacto (subgrafo S) | mecanica | nucleo |
| scoring (posicao entre peers) | julgamento com insumos mecanicos | thread principal |
| decisao de rota (cascata da secao (d)) | mecanica (regras sobre fatos medidos) | nucleo |
| integracao (escrita) | mecanica | nucleo |
| validacao (invariantes) | mecanica | nucleo |

Regra do bus preservada (principio 7 do plano): a normalizacao **registra** o texto do
remetente como evidencia, mas marca qualquer retorica de prioridade ("urgente", "bloqueia X")
como **nao-normativa**. Scoring usa apenas fatos do projeto receptor: dependencias reais,
criticidade temporal factual, uso concreto. Nenhum criterio deste ADR le prioridade do
remetente. Excecoes de dominio (fluxo especial do Gus) ficam fora do core, como hoje.

Scoring **nunca decide rota**: a rota e decidida pelo impacto (antes), e o scoring apenas
posiciona o candidato dentro do conjunto ja delimitado pela rota. Dependencia topologica vence
prioridade economica em todos os pontos; WSJF so ordena itens simultaneamente executaveis no
mesmo nivel de dependencia.

### (b) Maquina de estados formal

Estados de processamento (transientes) em MAIUSCULA_TRANSIENTE; estados terminais de uma
execucao de intake em negrito. Nomes em ingles por serem identificadores de codigo.

```text
                         +--> DUPLICATE            (terminal: enriquece item existente,
                         |                          zero linha nova)
NEW --norm--> NORMALIZED-+--> UNIQUE --deps/impacto--+--> LOCAL_INTEGRATION   (terminal: L0)
                         |                           +--> SCOPED_REORDER      (terminal: L1)
                         |                           +--> FULL_REORDER        (terminal: L2)
                         |                           +--> NEEDS_LEADER_DECISION (terminal: L2
                         |                                sem autoridade; INBOX residual com
                         |                                reason=needs-leader-decision)
                         +--> NEEDS_TRIAGE           (terminal: L3; INBOX residual com reason)
```

- `NEW` so existe **depois** da captura duravel (journal write-ahead da Fase 2/TAB-ADD-000
  gravado atomicamente antes de qualquer classificacao). Candidato sem registro duravel nao e
  um estado da maquina: e o bug que a maquina existe para impedir.
- `DUPLICATE`, `LOCAL_INTEGRATION`, `SCOPED_REORDER`, `FULL_REORDER` e `NEEDS_LEADER_DECISION`
  sao saidas controladas. `NEEDS_TRIAGE` e a unica rota que gera INBOX residual **por falta de
  classificabilidade**; `NEEDS_LEADER_DECISION` tambem persiste na INBOX residual, mas por
  **falta de autoridade** com classificacao completa -- ver secao (f) e a nota de
  inconsistencia do plano na secao "Consequencias".
- Terminal significa "terminal desta execucao de intake", nao "fim da vida do item":
  `NEEDS_TRIAGE` re-entra no pipeline a cada `--drain`/`--add`/`--reorder` (regra
  drain-first, secao (c), T3); `NEEDS_LEADER_DECISION` re-entra imediatamente apos a decisao
  do lider (TAB-ADD-007: decisao aprovada nunca estaciona na INBOX).
- Estados do journal por candidato: `NEW -> <rota terminal> -> DONE`, com `DONE` gravado
  somente **apos** a validacao da secao (c) passar. Falha de validacao = rollback da escrita
  (arquivo temporario descartado, `TODO.md` intocado) e candidato preservado no journal em
  estado retriavel com nota de erro -- nunca perda, nunca meio-escrito.

Toda transicao e computada sobre um **snapshot congelado** do par (candidato, tabela): a
classificacao nao le a tabela duas vezes em momentos diferentes (protecao TOCTOU no nivel
logico; o locking fisico e da Fase 5).

### (c) Prova de destino unico e de liveness

**T1 -- unicidade (`count(destinos_validos) == 1`).**

1. A decisao de rota e uma **cascata ordenada de guardas com default** (secao (d)):
   primeiro-que-casa vence. Uma cascata ordenada e, por construcao, uma funcao: para qualquer
   entrada, no maximo uma guarda decide.
2. A cascata tem **default obrigatorio** (`NEEDS_TRIAGE`): para qualquer entrada, no minimo
   uma guarda decide. Logo a funcao e total e univoca: exatamente uma rota por candidato.
3. Cada rota tem **exatamente uma primitiva de persistencia**, e as primitivas sao mutuamente
   exclusivas em efeito: linha nova na tabela (LOCAL/SCOPED/FULL) **xor** edicao da linha
   existente sem linha nova (DUPLICATE) **xor** linha na INBOX residual (NEEDS_TRIAGE /
   NEEDS_LEADER_DECISION). A validacao pos-escrita **verifica** a exclusao mutua em vez de
   supo-la: o mesmo item nao pode existir simultaneamente na tabela e na INBOX (checagem
   propria do intake, no nucleo -- independente do perfil `casa`/CHK-13).
4. Proibicoes de TAB-ADR-002, cobertas: item nos dois lugares (verificado em 3); item perdido
   sem registro (impossivel apos captura duravel -- T2); duas linhas para a mesma descoberta
   (deduplicacao antes da rota + validacao de contagem); item estrutural parado na INBOX sem
   motivo (formato da secao (f): linha residual sem reason valida e, por definicao,
   classificavel e drena no proximo intake); item "resolvido mentalmente" sem persistir
   (nenhum estado terminal existe sem escrita validada + journal `DONE`).

**T2 -- nenhuma descoberta se perde (crash em qualquer ponto).**

Pontos de crash possiveis e o resultado, dado que o journal e write-ahead e a escrita da
tabela e atomica (temporario + `os.replace`, padrao ja usado por `todo_fix.py`):

| Crash em | Estado em disco | Recuperacao (`SessionStart`/health detecta orfao) |
|---|---|---|
| antes do journal | nada persistido | fora da maquina; e o risco que a captura barata minimiza -- a regra operacional e "journal primeiro, classificacao depois" |
| apos journal, antes da rota | journal `NEW`, tabela intacta | re-executa o intake do zero (idempotente: deduplica primeiro) |
| durante escrita (temp) | journal com rota, tabela intacta (temp descartado) | re-executa; `os.replace` garante que a tabela nunca fica meio-escrita |
| apos `os.replace`, antes de `DONE` | tabela nova, journal sem `DONE` | re-executa; a deduplicacao encontra o proprio item ja integrado, classifica `DUPLICATE` contra ele e marca `DONE` -- convergencia idempotente |
| apos `DONE` | consistente | nada a fazer |

Logo, para todo candidato capturado: ou ha estado terminal validado, ou ha registro duravel
retriavel + sinal de recuperacao (`TAB_INTAKE_RECOVERY_REQUIRED`, Fase 2). Nenhum caminho
termina em perda silenciosa.

**T3 -- liveness: nenhum item classificavel fica indefinidamente na INBOX.**

Definicao: um item da INBOX e **classificavel** quando o pipeline, executado agora, o levaria
a uma rota diferente de `NEEDS_TRIAGE`/`NEEDS_LEADER_DECISION` -- ou quando a linha nao tem
metadado de triagem valido (formato legado ou reason invalida), caso em que e classificavel
por definicao.

1. **Drain-first:** toda operacao de intake (`--add`, `--drain`, `--create`, `--reorder`)
   comeca reclassificando todas as linhas da INBOX e termina com a assercao mecanica
   `classifiable_inbox_count == 0`. A assercao falhando **falha a operacao** (nao e aviso).
   Portanto um item classificavel nao sobrevive a nenhuma operacao de intake.
2. **Sinal obrigatorio:** o hook deterministico (Fase 6) emite `TAB_TRIAGE_REQUIRED` quando ha
   linha classificavel/legada, ou item residual com idade/ciclos acima do limiar; a politica
   da thread principal (Fase 7) converte o sinal em execucao de `--drain` no proximo ponto
   seguro, sem depender de memoria humana. E o consumidor deixa de ser voluntario: continua
   event-driven (nunca daemon), mas a acao e obrigacao da thread, nao lembranca do lider.
3. **Residencia limitada por reason** (vocabulario fechado, secao (f)). Cada reason tem
   condicao de saida e gatilho que forca a reavaliacao:

   | reason | sai quando | forca a saida | residencia maxima |
   |---|---|---|---|
   | `missing-info` | a informacao aparece | cada drain re-tenta; com `cycles >= triage_max_cycles` (default 2), converte-se em **item de investigacao** na tabela (a investigacao em si e sempre classificavel, L0/L1) ou vira decisao do lider | limitada |
   | `conflicting-evidence` | conflito resolvido | idem `missing-info` | limitada |
   | `dependency-conflict` | grafo consertado | o conserto do grafo e ele mesmo um item classificavel que entra na tabela no mesmo drain; o candidato sai no drain seguinte | limitada |
   | `ownership-unavailable` | proxima sessao com ownership do `TODO.md` | drain da sessao dona | limitada (1 sessao) |
   | `blocked-external` | fato externo ocorre | re-checagem factual a cada drain; se o bloqueio se provar permanente, vira decisao do lider (descartar ou manter) | limitada ate a conversao |
   | `needs-leader-decision` | lider decide | **obrigacao de apresentacao**: no proximo drain/sessao, apresentar 2-3 opcoes prontas com trade-offs (TAB-ADD-007); decisao tomada dispara o intake imediatamente | **ilimitada por desenho** -- gated no humano |

4. **Caso de fronteira deliberado:** `needs-leader-decision` e o unico estado com residencia
   potencialmente ilimitada, porque a alternativa (o agente decidir pelo lider) violaria a
   restricao de autoridade. O que o desenho garante e que o item **nunca fica invisivel**: ele
   carrega reason + ciclos, o sinal do hook conta os "aguardando lider" separadamente dos
   "classificaveis" (nao polui `TAB_TRIAGE_REQUIRED` -- ver secao (f), nota sobre o circuit
   breaker), e cada ciclo renova a apresentacao de opcoes. Starvation silenciosa fica
   impossivel; espera visivel e deliberada continua possivel, e e a semantica correta.
5. **Fronteiras enumeradas:** (i) dois workers descobrem o mesmo item -- o escritor logico
   unico (Fase 5) serializa; o segundo candidato deduplica contra a linha recem-integrada
   pelo primeiro e sai `DUPLICATE`; (ii) candidato duplicado de linha da INBOX -- funde na
   linha residual existente (`DUPLICATE`), preservando a reason e somando evidencia; (iii)
   reabertura de item `✅ Concluido` -- **nao** e `DUPLICATE`: e candidato novo com
   referencia cruzada ao item concluido (nunca renumerar, nunca reabrir a linha antiga);
   (iv) tabela ilegivel/ausente no momento do intake -- o candidato fica no journal em estado
   retriavel; a operacao reporta erro (exit 1); nada se perde; (v) grafo da tabela quebrado
   (ciclo, prereq inexistente -- achados CHK-05/CHK-06) -- rota `NEEDS_TRIAGE` com
   `dependency-conflict` + o conserto vira item classificavel no mesmo drain, como em 3;
   (vi) linha da INBOX em formato legado (sem metadado) -- classificavel por definicao,
   drena no proximo intake (e a janela de migracao de TAB-CUT-001).

### (d) Criterios objetivos de rota: a cascata L0..L3

Predicados, todos definidos por medicao sobre o snapshot (nenhum le conteudo livre em nenhuma
lingua; nenhum le retorica do remetente):

- **P-dup**: existe item na **tabela canonica** com o mesmo ID explicito (dedup mecanica por
  string de ID exato). **Emenda 2026-08-16 (campanha Fase 2 / TAB-ADD-007):** ID presente
  **apenas** na INBOX residual **nao** e `DUPLICATE` -- e reentrada apos decisao do lider
  (strip da linha residual + integracao L0/SCOPED/FULL). Residual e exception queue, nao
  inventário de "ja integrado". Equivalencia semantica (mesma evidencia-alvo e criterios de
  aceitacao) continua julgamento agentivo, fora do nucleo (TAB-ADD-002.7: empate por string
  de descricao **nao** basta quando os criterios diferem).
- **P-campos**: os campos minimos do `WorkCandidate` estao preenchidos com evidencia
  (descricao, origem, evidencia, projeto receptor), e toda dependencia declarada por ID
  resolve na tabela.
- **P-autoridade**: nenhuma acao exigida pela integracao pertence a classe reservada ao
  lider. Classe reservada default do nucleo (extensivel via `.tab_pendencias.ini`, secao
  `[intake]`, chave `leader_reserved`): remover ou fundir item existente que nao seja
  duplicata explicita; alterar o schema da tabela; contrariar decisao registrada (arquivo de
  decisoes/ADR apontado na config -- deteccao agentiva, o nucleo so bloqueia quando
  informado); descartar candidato definitivamente; qualquer acao irreversivel fora do
  `TODO.md`.
- **P-fundacao** (define L2): a integracao exige **editar linhas existentes de forma
  estrutural**: criar pre-requisito novo para 2+ itens existentes de `Grupo`s distintos, ou
  invalidar premissa de item existente (torna-lo prematuro/errado), ou alterar contrato
  documentado. Um unico sinal basta.
- **P-local** (define L0): a integracao e **append puro**: exatamente uma linha nova; zero
  celulas de linhas existentes mudam; zero linhas existentes mudam de posicao ou de `Onda`;
  os pre-requisitos do candidato ou nao existem ou ja estao todos em estado que nao exige
  reposicionamento (o candidato entra na onda seguinte a do seu ultimo pre-requisito, ou numa
  onda nova ao fim).
- **P-escopado** (define L1): o menor subgrafo seguro `S` e computavel e limitado:
  `S = {candidato} U ancestrais-nao-satisfeitos U descendentes-que-podem-mudar-de-posicao U
  peers-de-onda-cujo-ranking-relativo-ao-candidato-precisa-ser-decidido` (definicao de
  TAB-ADD-005, mecanica dado o grafo); `|S| / n <= scoped_reorder_max_fraction` (secao (e));
  `S` nao contem item marcado por P-fundacao; `S` nao atravessa mais de um `Grupo` no
  reposicionamento (a coluna `Grupo` e o proxy objetivo de "macrogrupo/epico" do plano).

Cascata (primeiro-que-casa vence; ordem e parte do contrato):

```text
1. P-dup                          -> DUPLICATE
2. nao P-campos                   -> NEEDS_TRIAGE   (L3)
3. nao P-autoridade               -> NEEDS_LEADER_DECISION
4. P-fundacao                     -> FULL_REORDER    (L2)
5. P-local                        -> LOCAL_INTEGRATION (L0)
6. P-escopado                     -> SCOPED_REORDER  (L1)
7. default (S grande demais etc.) -> FULL_REORDER    (promocao L1->L2)
```

Teste de objetividade (e o criterio de aceitacao desta secao): dois implementadores
diferentes, lendo so este ADR, classificam o mesmo caso do corpus na mesma rota. Isso vira
experimento na Fase 10 (dupla classificacao independente do corpus TAB-TST-001; qualquer
divergencia e defeito **dos predicados**, a corrigir aqui, nao caso omisso a improvisar).

Proibicoes que a cascata torna estruturais: jogar L0 na INBOX por conveniencia e impossivel
(P-local casa antes do default); item estrutural esperar lembranca futura e impossivel
(P-fundacao roteia na hora); disparar full reorder para typo e impossivel (P-local casa
primeiro).

### (e) Limite SCOPED -> FULL: protocolo de calibracao, nao numero inventado

O limite `scoped_reorder_max_fraction` (`.tab_pendencias.ini`, secao `[intake]`) e uma
**heuristica de eficiencia, nunca o mecanismo de correcao**. A correcao vem de um invariante
independente do numero: o resultado de um `SCOPED_REORDER` deve ser **equivalente-restrito**
ao de um `FULL_REORDER` -- identico fora de `S` byte a byte, e com grafo valido dentro e
fora. Se a validacao pos-escrita detectar divergencia fora de `S`, a operacao aborta e
promove a FULL. Um limite mal calibrado custa desempenho, nunca corretude.

Protocolo de calibracao (pre-registrado aqui, ANTES de existir o dado -- disciplina da casa
de 2026-08-01 para estudos por medicao):

1. **Corpus:** fixtures reais locais (consumidor A, 116 itens; consumidor B, 215 itens),
   corpus sintetico AC-0, e o replay das descobertas historicas deste repo (as 7 linhas da
   INBOX atual + descobertas reconstruiveis do `git log`). Minimo pre-registrado: 30
   candidatos, cobrindo os 30 cenarios de TAB-TST-001.
2. **Medicao por candidato:** `|S|/n` do menor subgrafo seguro, e o veredicto binario de
   equivalencia-restrita (scoped == full fora de S?).
3. **Criterio pre-registrado:** o default e a maior fracao observada com **zero** violacoes
   de equivalencia no corpus inteiro, com margem de seguranca de um degrau (o proximo valor
   observado abaixo). Se houver violacao em qualquer fracao, o default e `0` (SCOPED nunca
   ativa) ate o algoritmo de `S` ser consertado -- nunca "afrouxar o criterio depois de ver o
   dado".
4. **O que reportar:** distribuicao de `|S|/n` no corpus, contagem de violacoes (**inclusive
   quando zero** -- zero declarado difere de nao-medido), e o valor default resultante com o
   dataset e o comando que o reproduz.

### (f) Semantica nova da INBOX e metadados do item residual

A INBOX deixa de significar "trabalho novo ainda nao priorizado" e passa a significar:

> **fila excepcional de candidatos que nao podem ser integrados com seguranca agora.**

Motivos validos = o vocabulario fechado de reason da secao (c)/T3 (`missing-info`,
`conflicting-evidence`, `dependency-conflict`, `needs-leader-decision`,
`ownership-unavailable`, `blocked-external`). Tokens em ingles (sao identificadores de
contrato, como os nomes de estado; o conteudo livre da linha continua em qualquer lingua --
nenhum check le o idioma da descricao).

Motivos invalidos (TAB-ADR-003) **nao ganham token**: "nao quis reordenar agora", "depois
vemos", "e mais barato colocar aqui", "a tabela esta grande", "o agente esta terminando a
sessao". A ausencia de token valido e o proprio mecanismo de rejeicao: linha sem metadado
valido = classificavel por definicao = drena no proximo intake. Nao ha como "estacionar de
preguica" de forma persistente.

**Formato do item residual** -- compativel com a linha atual `- ID: descricao`; o metadado
vive DENTRO da descricao, imediatamente apos o `: `:

```markdown
- <ID-ou-travessao>: [triage since=2026-08-16 reason=needs-leader-decision source=agent cycles=1] descricao livre em qualquer lingua
```

Gramatica: `[triage` + 1 ou mais pares ` chave=valor` + `] `. Chaves obrigatorias: `since`
(data ISO `YYYY-MM-DD` de entrada) e `reason` (token do vocabulario). Opcionais: `source`
(`user|bus|agent|audit|test`), `cycles` (inteiro >= 0, default 0; incrementado a cada drain
que reavalia e mantem o item), `ref` (ID/rota de origem). Valores sao tokens sem espaco e sem
`]` -- parseaveis por regex simples, sem YAML, sem banco paralelo. Regex de referencia:
`^\[triage( [a-z_]+=[A-Za-z0-9._:\-]+)+\] `.

Compatibilidade provada contra o parser existente (a testar como contrato, secao (j)):
`todo_lib.inbox_items()` (`tools/todo_lib.py:431-442`) devolve a linha inteira apos o `- ` e
nao interpreta o conteudo -- o metadado atravessa intacto; a forma `- ID: ...` e preservada,
entao CHK-13 (perfil casa) continua valido sem mudanca; round-trip byte-exato inalterado (o
metadado e texto comum da linha). Metadado malformado (chave desconhecida, reason fora do
vocabulario) **nunca** e descartado em silencio: a linha e tratada como legada/classificavel
e o `--audit` reporta o defeito de formato.

O metadado permite medir, mecanicamente e offline, tudo que TAB-ADR-004 exige: data de
entrada (`since`), razao (`reason`), origem (`source`) e ciclos de triagem sobrevividos
(`cycles`). Nota: o exemplo do plano omite `cycles`, mas o proprio plano exige medi-lo; este
ADR o inclui no formato.

**Circuit breaker refinado** (correcao ao default de TAB-INBOX-002): o gatilho
`TAB_TRIAGE_REQUIRED` conta apenas linhas **classificaveis ou legadas** e itens cujo
`cycles`/idade excedeu o limiar -- **nao** conta residuais validos aguardando lider. Motivo,
medido neste repo: com 5 de 7 itens legitimamente aguardando decisao, um breaker de
`INBOX >= 3` dispararia permanentemente e viraria ruido (fadiga de alerta, risco ja
documentado na norma da casa). Itens `needs-leader-decision` alimentam um sinal proprio
(contagem de decisoes pendentes de apresentar), distinto de triagem.

### (g) Protecao de WIP: preempcao formalizada

Invariantes mecanicos (testaveis por diff):

- **W1**: nenhuma operacao de intake escreve na celula `Status` de linha pre-existente. A
  superficie de escrita do intake e: inserir linha nova; editar `Pre-requisito`/`Onda`/posicao
  de linhas dentro de `S` (SCOPED) ou da tabela (FULL); editar a descricao da linha-alvo em
  `DUPLICATE`; escrever/remover linhas da INBOX. `Status` de item existente fica fora da
  superficie por construcao -- logo o intake e **incapaz** de preemptar via tabela.
- **W2**: em SCOPED/FULL reorder, item `🔄 Em andamento` e **pinado**: preserva posicao
  relativa aos peers do seu nivel topologico, salvo violacao topologica nova (um pre-requisito
  novo descoberto acima dele). Empates e scores comparaveis preservam a ordem anterior
  (ordenacao estavel, TAB-WSJF-005).

Preempcao -- parar o trabalho em curso -- e ato de orquestracao/humano, **fora** da tabela.
Predicado de validade (TAB-ADR-005): `PREEMPT(I)` e valido sse pelo menos um:

1. **base invalida**: o intake registrou em `I` (via SCOPED/FULL) um pre-requisito novo `P`
   com `P` nao concluido -- o trabalho em curso esta construido sobre base que o fato novo
   invalida;
2. **defeito critico / seguranca-integridade**: continuar `I` arrisca perda/corrupcao (classe
   CRITICO);
3. **ordem do lider**.

WSJF superior, sozinho, **nunca** satisfaz o predicado (anti priority-thrashing). Nos casos 1
e 2 o intake apenas persiste o fato e emite o aviso com a causa; quem para `I` e o
orquestrador ou o lider, nunca a maquina de intake.

### (h) Migracao das 7 linhas atuais da INBOX

Contrato (executado na Fase 4, TAB-INBOX-001; este ADR fixa o criterio de aceitacao):

1. Ler as `n_antes = 7` linhas (`TODO.md:66-72`), congelar snapshot.
2. Passar cada uma pelo pipeline novo; produzir **tabela de disposicao** persistida
   (linha -> rota -> IDs-alvo criados/enriquecidos ou reason residual).
3. Verificar mecanicamente a identidade de conservacao, contando **linhas de origem**:

```text
n_antes == integrados + remanescentes + duplicatas_explicitamente_fundidas
```

   Uma linha que gera mais de um item na tabela conta **uma vez** (como integrada), com todos
   os IDs-alvo na tabela de disposicao. Identidade violada = migracao aborta sem escrever.
4. Remanescentes ganham o metadado da secao (f) com `since` = data da migracao e `cycles=0`.

Classificacao de referencia (expectativa deste ADR; o migrador pode divergir registrando a
justificativa na tabela de disposicao -- a identidade e inviolavel, a classificacao por linha
nao e):

| Linha | Rota esperada | Racional |
|---|---|---|
| `FIX-ESCOPO-1` | NEEDS_LEADER_DECISION | contem decisao autonoma a confirmar retroativamente + decisao de escopo v1.1; a parte documental (ajustar ADR-0001/README ao escopo real do `--fix`) e L0 e pode ser destacada como item proprio na mesma migracao |
| `FIX-RISCO-1` | LOCAL_INTEGRATION ou SCOPED | riscos conhecidos viram itens de investigacao/mitigacao rastreaveis (registrar trabalho nunca e decisao de lider; so descartar/aceitar risco em definitivo e) |
| `PYFLOOR-1` | NEEDS_LEADER_DECISION | as 3 opcoes ja estao enunciadas na linha; uma delas reabre D-9 (decisao fechada do lider) |
| `MDASH-1` | NEEDS_LEADER_DECISION | excecao de hook da maquina do lider e config dele |
| `MIG-DIFF` | SCOPED_REORDER | cria pre-requisito para `MIG-1` (edita linha existente): assinatura exata de L1 |
| `FREEZE-GITHOOKS` | NEEDS_LEADER_DECISION | a propria linha diz "Decisao do lider" |
| `SKILL-DESC-1` | NEEDS_LEADER_DECISION | as opcoes (a)/(b)/(c) ja estao enunciadas; a separacao foi decisao do lider em 16/08 |

Expectativa da identidade: `7 == 2 + 5 + 0`. Cada `needs-leader-decision` remanescente entra
na fila de apresentacao obrigatoria (secao (c)/T3.6): a proxima sessao apresenta as opcoes
prontas em vez de esperar o lider lembrar. Este e o teste vivo do desenho: se a migracao
terminar com item classificavel remanescente, ou com a identidade quebrada, o desenho
falhou (ver (i)).

### (i) Modos de falha e criterios de falsificacao

O que teria de ser observado para provar este desenho errado -- cada um especifico o
bastante para virar teste (Fase 10):

| # | Modo de falha | Falsificador observavel | Teste que o materializa |
|---|---|---|---|
| F1 | Starvation disfarcada de excecao | item residual com reason valida excede `triage_max_cycles` sem conversao nem apresentacao registrada | simular N drains; asserir que `cycles >= 2` dispara conversao (investigacao) ou apresentacao (lider) |
| F2 | Criterios de rota nao-objetivos | dupla classificacao independente do corpus diverge em qualquer caso | experimento de dupla classificacao (secao (d)); divergencia = defeito de predicado |
| F3 | SCOPED nao e seguro | resultado scoped difere do full fora de `S`, ou linhas fora de `S` mudam byte | propriedade `unaffected_rows_stable_on_scoped_reorder` + equivalencia-restrita no corpus |
| F4 | Destino duplo | mesmo item na tabela e na INBOX apos operacao; ou duas linhas novas para uma descoberta | injetar crash entre integracao e remocao da INBOX; recovery tem de convergir a um destino |
| F5 | Intake preempta via tabela | diff mostra celula `Status` de linha pre-existente alterada por operacao de intake | propriedade W1 (diff de celulas de Status vazio) em todo cenario do corpus |
| F6 | Perda de descoberta | journal orfao nao recuperado; identidade de conservacao da migracao falha | kill do processo em cada ponto de crash da tabela de T2; `no_lost_work` |
| F7 | Integracao-por-default piora o sistema | nas metricas de TAB-CUT-004: `duplicatas criadas > 0` sustentado, ou conflitos de merge materialmente piores que o baseline pre-migracao | comparacao antes/depois no dogfood + canaries |
| F8 | Suposicao de lingua escondida | qualquer predicado da cascata muda de resultado quando o corpus AC-0 traduz o conteudo livre | rodar a cascata sobre AC-0 (outra lingua, outro esquema de ID) e comparar rotas |
| F9 | Circuit breaker vira ruido | `TAB_TRIAGE_REQUIRED` disparando com INBOX composta so de residuais validos aguardando lider | fixture com 5 itens `needs-leader-decision`: sinal de triagem NAO dispara; sinal de decisoes pendentes dispara |

Qualquer falsificador confirmado reabre este ADR (e o gate ADR-1) antes de qualquer
implementacao subsequente.

### (j) Testes de contrato que congelam o comportamento antigo (especificacao; unico codigo permitido na Fase 1)

1. **CT-INBOX-PARSE**: `inbox_items()` sobre o snapshot atual da INBOX (7 linhas) devolve 7
   entradas com o texto integral; a mesma funcao sobre linhas com metadado `[triage ...]`
   devolve a linha com o metadado intacto (prova de que o formato novo atravessa o parser
   velho sem mudanca).
2. **CT-HEALTH-COUNTS**: `todo_health` sobre o snapshot congelado reporta
   `itens=48, inbox=7, aguardando_verificacao=43` (baseline para a identidade de conservacao
   e para as metricas antes/depois de TAB-CUT-004).
3. **CT-ROUNDTRIP**: round-trip byte-exato do `TODO.md` atual inalterado (este ADR nao muda o
   parser; o teste congela essa promessa).
4. **CT-STATUS-SURFACE**: harness de propriedade que, dado qualquer par (tabela-antes,
   tabela-depois) produzido por uma operacao de intake, extrai as celulas de `Status` das
   linhas pre-existentes e asserta igualdade (materializa W1 desde o primeiro dia da Fase 2).

Snapshots imutaveis por hash, nunca o arquivo vivo (regra ja canonizada em
`BASELINE-FRAGIL`).

### (k) O que este ADR NAO decide, e por que

- **Os 43 itens presos em `🔍 Pendente verificacao`.** Mesma familia de falha (fila duravel,
  consumidor voluntario), mas **outra maquina**: o ciclo de vida de status
  (implementacao -> verificacao -> `✅`), cujo consumidor e a onda `TST-*`/`AUD-*`, nao o
  intake. Acopla-los num unico desenho dobraria o escopo do ADR e misturaria dois escritores
  com invariantes diferentes (o intake e proibido de tocar `Status`; o ciclo de verificacao
  existe exatamente para toca-lo). O padrao comum -- toda fila precisa de sinal forcado e
  consumidor designado -- fica estabelecido aqui e aplicado ao intake; a aplicacao ao `🔍` e
  o sinal `TAB_VERIFICATION_AGING` (Fase 6) mais um item proprio de re-verificacao,
  registrado como trabalho descoberto no retorno desta tarefa.
- **CLI e formato do journal** (`--add`, `--drain`, path do write-ahead, validacao
  Linux/Windows do git common dir): Fase 2 (TAB-ADD-000/001), dentro do contrato daqui.
- **Regua WSJF unificada** (Fibonacci da casa vs 1-20 da skill): Fase 3 (TAB-WSJF-001). Este
  ADR so fixa que scoring nao decide rota e nao fura topologia.
- **Locking fisico / escrita concorrente** (dois writers, TOCTOU de filesystem): Fase 5. Este
  ADR fixa o requisito logico (snapshot congelado, escrita atomica, escritor logico unico) e
  a rota `ownership-unavailable`.
- **Nomes e wiring definitivos dos sinais do hook**: Fase 6; este ADR usa os nomes do plano
  como referencia.
- **O numero do limite SCOPED->FULL**: sai do protocolo da secao (e), nunca deste texto.
- **Versionamento SemVer da mudanca de semantica**: decisao do release manager/lider apos
  medir o diff (TAB-SOT-005); a mudanca de significado da INBOX e mudanca de produto.
- **As 5 decisoes de lider enfileiradas** (`PYFLOOR-1`, `MDASH-1`, `FREEZE-GITHOOKS`,
  `SKILL-DESC-1`, confirmacao de `FIX-ESCOPO-1`): o desenho as torna apresentaveis; nao as
  toma.
- **Migracao dos demais projetos da maquina**: canary da Fase 11, um por vez, com as metricas
  de TAB-CUT-004.

## Consequencias

**Positivas:**
- Liveness deixa de depender de memoria humana: classificavel integra no mesmo ciclo;
  residual carrega reason/idade/ciclos e tem saida forcada; decisao de lider vira fila de
  apresentacao, nao poeira.
- A contradicao interna da skill (INBOX obrigatoria vs anexar direto) e resolvida a favor da
  integracao imediata, com a INBOX preservada no papel que o corpus real ja mostra: excecao.
- Corretude nunca depende do numero calibrado: equivalencia-restrita e validada por
  invariante; o limite so poupa custo.
- O formato de metadado e aditivo e atravessa o parser atual sem mudanca de codigo do nucleo.

**Negativas / aceitas como custo:**
- Toda operacao de intake fica mais cara que "anotar 1 linha": paga classificacao +
  validacao. Mitigado pela captura barata continuar existindo (journal) e pela rota L0 ser
  append puro.
- O vocabulario de reason e mais um contrato a documentar e manter.
- `needs-leader-decision` acumulando e possivel por desenho; o custo e visibilidade
  permanente (sinal proprio), nao integracao forcada.

**Riscos / pontos de atencao:**
- **Inconsistencia do plano, resolvida aqui:** TAB-ADR-001 diz que `NEEDS_TRIAGE` e a unica
  rota que gera INBOX residual, mas TAB-ADR-003 lista "decisao reservada ao lider" como
  motivo valido de INBOX e TAB-ADD-007 manda registrar o candidato como
  `NEEDS_LEADER_DECISION` sem dizer onde ele persiste. Este ADR fixa: ambos persistem na
  INBOX residual, com reasons distintas, sinais distintos e condicoes de saida distintas. Se
  o lider preferir outra persistencia para `NEEDS_LEADER_DECISION` (ex.: linha na tabela com
  status `🎨 Pendente design`), isso muda a secao (f) e deve ser decidido antes da Fase 2 --
  a alternativa foi rejeitada abaixo.
- A cascata depende de o julgamento agentivo preencher os fatos (dependencias declaradas,
  equivalencia semantica) honestamente; a mecanica valida estrutura, nao verdade semantica. O
  experimento F2 e a rede para isso.
- O breaker refinado (nao contar residual valido) pode mascarar acumulo real de decisoes de
  lider se o sinal proprio nao for implementado junto -- os dois nascem na mesma fatia da
  Fase 6, nunca um sem o outro.

## Alternativas consideradas

1. **Abolir a INBOX** (integracao sempre imediata) -- rejeitada: elimina a captura barata e o
   fallback de concorrencia (Fase 5) e forca o agente a decidir pelo lider quando falta
   autoridade -- exatamente o que 5 das 7 linhas reais mostram ser necessario.
2. **`NEEDS_LEADER_DECISION` como linha da tabela com status `🎨 Pendente design`** --
   rejeitada: inserir na tabela exige posicao, e a posicao e frequentemente o proprio objeto
   da decisao pendente (caso `PYFLOOR-1`); alem de sobrecarregar um status que hoje significa
   "aguarda spec", nao "aguarda autoridade".
3. **Metadado da INBOX em YAML/frontmatter ou arquivo sidecar** -- rejeitada: quebra a linha
   `- ID: descricao`, exige parser novo (contra D-9/anti-dependencia) e cria segunda fonte de
   verdade ao lado da linha; o plano ja veta banco paralelo.
4. **Threshold SCOPED->FULL fixado neste ADR** -- rejeitada: numero sem corpus e opiniao; o
   plano exige calibracao com corpus real, e a secao (e) a pre-registra.
5. **Preempcao automatica por WSJF acima de um limiar** -- rejeitada: priority thrashing; o
   custo de troca de contexto do WIP nao aparece no score, e a regra da casa (WIP = 1 onda)
   ja encode a decisao contraria.
6. **Daemon/watcher LLM garantindo liveness** -- rejeitada: nao-objetivo explicito do plano;
   o desenho fica event-driven (hook deterministico + obrigacao da thread principal).

## Reversibilidade

Hibrida. A **maquina de estados e a cascata** sao two-way door ate a Fase 2 publicar
comportamento (`--add`/`--drain` em release): mudar guardas e barato enquanto so este ADR e os
testes de contrato existem. O **formato do metadado `[triage ...]`** vira contrato externo
assim que uma release o gravar em `TODO.md` de terceiros -- depois disso, mudanca exige
migracao/deprecation (mesma classe do `.tab_pendencias.ini` no ADR-0001). A **mudanca de
semantica da INBOX** e one-way door de produto no sentido de SemVer: reverte-la apos adocao
por terceiros e quebra de contrato -- por isso o gate ADR-1 exige a aprovacao explicita do
lider antes de qualquer implementacao.

## Decisao do lider (2026-08-16)

O gate ADR-1 foi submetido ao lider com as questoes abaixo. Respostas, na ordem:

1. **Maquina, cascata e semantica nova da INBOX: APROVADAS.** `NEEDS_LEADER_DECISION`
   persiste na **INBOX residual** com reason propria, como recomendado. A alternativa
   (linha na tabela com status de pendencia de design) foi rejeitada pelo motivo dado
   na secao (f): inserir na tabela exige escolher posicao, e a posicao e frequentemente
   o proprio objeto da decisao pendente.
2. **Lista default de `leader_reserved`: ACEITA como esta**, na forma minima da secao (d).
   Segue extensivel por projeto via `.tab_pendencias.ini`, secao `[intake]`. Comecar
   minimo nao fecha porta, e evita transformar toda operacao em pedido de permissao.
3. **Politica de apresentacao: HIBRIDA.** Nem automatica em todo inicio de sessao, nem
   apenas sob demanda -- as duas opcoes que este ADR previa. A decisao pendente e
   apresentada **quando envelhece**, isto e, quando sobrevive ao numero configurado de
   ciclos de triagem (`triage_max_cycles`, default 2) ou excede a idade configurada.
   Racional do lider: no caso normal o fluxo fica silencioso, e a interrupcao acontece
   sem depender da memoria dele -- que e exatamente a falha que esta campanha existe
   para corrigir.

   **Consequencia para a implementacao:** a apresentacao deixa de ser uma escolha binaria
   de politica e passa a ser derivada do metadado `cycles=` do item residual, que ja
   estava previsto na secao (f). O sinal de decisao pendente so e emitido quando o
   predicado de envelhecimento e verdadeiro. Isto **nao** foi desenhado em detalhe por
   este ADR e precisa de especificacao propria antes da implementacao: qual predicado
   exato, onde e avaliado, e como o contador avanca sem que uma sessao que nao roda
   `--drain` congele o envelhecimento.

## Questoes em aberto para o lider

1. **Aprovar a maquina, a cascata e a semantica nova da INBOX** (gate ADR-1) -- inclui a
   resolucao da inconsistencia do plano: `NEEDS_LEADER_DECISION` persiste na INBOX residual
   com reason propria (recomendado) ou em outra persistencia.
2. **Confirmar a lista default de acoes reservadas ao lider** (secao (d), P-autoridade) --
   proposta minima; o lider pode ampliar por config ou por norma.
3. **Politica de apresentacao**: as decisoes pendentes (`needs-leader-decision`) devem ser
   apresentadas automaticamente no inicio de sessao (AskUserQuestion, uma por vez), ou apenas
   quando o lider pedir o estado da fila? O desenho suporta ambas; a primeira fecha o ciclo
   mais rapido, a segunda interrompe menos.
4. **As 5 decisoes ja enfileiradas** (`PYFLOOR-1`, `MDASH-1`, `FREEZE-GITHOOKS`,
   `SKILL-DESC-1`, confirmacao retroativa de `FIX-ESCOPO-1`) continuam aguardando; a
   migracao (h) as apresentara com opcoes prontas.
