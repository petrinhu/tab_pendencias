# Frescor da tabela de pendências (`TODO.md`)

> Documento normativo (Reference). Descreve o que a skill `tab_pendencias` EXIGE para uma
> tabela de pendências não ficar desatualizada durante o trabalho. Não depende de nenhum
> projeto, máquina, agente ou convenção específica de quem mantém este repositório --
> aplica-se a qualquer `TODO.md` de projeto que use esta skill. Racional histórico de como
> esta norma foi desenhada não está aqui: este documento descreve só a regra vigente.

## 1. Dois tipos de `TODO.md`

A norma abaixo vale só para um dos dois tipos. Não confundir:

| Tipo | O que é | A norma de frescor vale? |
|---|---|---|
| **De projeto** | Itens editáveis; cada item corresponde a um trabalho identificável, e a relação item-commit faz sentido. | Sim -- DoD de status (§2), separação sincronizar/reordenar (§3), regra do ID no commit (§4), ordem canônica do arquivo (§5) e INBOX (§5.1) valem aqui. |
| **Hub agregador** | Contagens derivadas de vários `TODO.md` de projeto (ex.: um painel que soma pendências de vários repositórios). | Não. Um hub agregador NÃO é editado à mão e NÃO usa INBOX. Ele é regenerado por script a partir dos `TODO.md` de projeto, que continuam sendo a fonte da verdade. |

## 2. Vocabulário de status e DoD de transição

A coluna `Status` usa sete valores fixos -- emoji + texto exato, em pt-br, por contrato:

| Status | Significado |
|---|---|
| ✅ Concluído | Tarefa finalizada |
| 🔄 Em andamento | Trabalho em progresso |
| 🟡 Parcial | Feito em parte |
| ⏳ Pendente | Não iniciado |
| 💡 Decisão tomada | Abordagem definida, implementação futura |
| 🎨 Pendente design | Aguarda spec/brainstorm |
| 🔍 Pendente verificação | Implementado, aguarda validação |

> **Nota de idioma:** só o vocabulário de status (os sete textos acima) é fixo em pt-br.
> Descrição do item, ID e mensagens de commit do usuário podem estar em qualquer língua.
> Nenhuma verificação automatizada -- própria ou de terceiro -- pode assumir português no
> conteúdo livre da tabela; só a célula de `Status` tem vocabulário fechado.

**Definition of Done da transição de status:**

- Ao entregar uma implementação, o status do item vira **`🔍 Pendente verificação`**.
  **Nunca `✅ Concluído` direto.**
- **`✅ Concluído`** só é atribuído **depois** que o teste e/ou a auditoria correspondente
  ao item rodaram e aprovaram (na skill, isso corresponde aos itens de fechamento
  `TST-*`/`AUD-*` daquele item).
- Tocar a coluna `Status` é um ato **mecânico**: nunca exige planejamento, replanejamento
  ou reordenação da tabela.

O estado intermediário `🔍 Pendente verificação` existe para tornar visível o trabalho
entregue-mas-ainda-não-validado. Sem ele, nada distingue um item testado/auditado de um
item que só foi implementado -- o board diria `✅` cedo demais.

## 3. Duas operações, dois custos: sincronizar vs. reordenar

A tabela de pendências combina duas operações de natureza diferente. Tratá-las com o
mesmo verbo genérico ("atualizar a tabela") é a causa mais comum de uma tabela ficar
desatualizada: a operação cara contamina a barata, e ninguém marca o que já terminou
porque parece exigir o mesmo esforço de replanejar.

| Operação | O que é | Custo | Quando acontece |
|---|---|---|---|
| **Sincronizar status** | Marcar um item existente como `🔍` ou `✅` (§2) | Barato, mecânico, determinístico | A cada commit/PR que entrega ou valida trabalho |
| **Reordenar** | Recalcular a ordem das linhas, a coluna `Onda`, ou inserir item novo com dependência/prioridade | Caro, exige julgamento | Só quando um input de priorização muda: nova dependência, item ficou urgente, ou a INBOX (§5.1) deixou de estar vazia |

**Regra:** sincronizar status nunca dispara reordenação. Reordenar é sempre um ato
consciente -- via `/tab_pendencias --reorder` --, nunca automático por passagem de tempo
nem por um processo contínuo de vigilância.

## 4. Citar o ID do item no commit

Ao fechar ou avançar o status de um item da tabela, cite o **ID que o projeto já usa
para aquele item** no corpo ou rodapé da mensagem de commit. O esquema de ID é arbitrário
(`V-12`, `F1.4`, `#37`, ou qualquer outro já em uso) -- use o que o projeto já tem; nunca
inventar esquema novo nem renumerar itens existentes.

Citar o ID é o que permite a qualquer mecanismo de sincronização automatizado (§6, se em
uso) reconhecer que aquele item foi entregue, sem precisar reler o histórico inteiro do
repositório. Um commit que cita o ID mas só toca a própria tabela (reordenação, correção
de digitação) não conta como entrega de trabalho: entrega é definida por tocar
código/conteúdo substantivo do item, não apenas por citar o ID na mensagem.

> Citar o ID não substitui tocar a célula de `Status` manualmente quando não há mecanismo
> automatizado disponível (§6). Citação e toque manual se reforçam; não são alternativas.

## 5. Ordem canônica do arquivo (INBOX antes, tabela por último)

Um `TODO.md` de projeto tem esta ordem, de cima para baixo:

| # | Bloco | Obrigatório? |
|---|---|---|
| 1 | Linha 1: título `#` do arquivo | Sim |
| 2 | Preâmbulo livre (prosa, blockquote, legenda, notas, WSJF, critérios) | Não |
| 3 | Seção `## INBOX (...)` -- a exception queue de §5.1, com seus bullets | Não (só existe quando há residual) |
| 4 | Mais prosa/seções livres | Não |
| 5 | **A tabela canônica** (cabeçalho com `ID` e `Status`, separador, linhas de dados) | Sim |
| 6 | **EOF logo após a última linha da tabela** (só o `\n` final) | Sim |

Três regras derivam disso:

- **UMA tabela no arquivo, e só uma** (o bloco 5). Sem qualificação:
  **qualquer segundo bloco `|...|` é violação**, tenha coluna `Status` ou não.
  Legenda, matriz, comparativo, sumário, índice, contagem e scoring **não
  viram tabela auxiliar** -- vão em **bullets ou lista**. Proibido junto:
  **linha em branco DENTRO da tabela** -- em Markdown ela encerra a tabela
  ali, e o que vem depois já é outro bloco: uma tabela vira duas sem ninguém
  ter escrito nada.
- **A INBOX vem ANTES da tabela** (mudou em 2026-08-19; a norma anterior a
  colocava depois).
- **Nada vem DEPOIS da tabela** (mudou em 2026-08-19). A tabela é o último
  bloco do arquivo.

**Por quê:** ferramentas e guards de consumidor (e a leitura humana) tratam
"fim da tabela = fim do arquivo" como invariante -- é o que permite acrescentar
linha no fim sem procurar onde a tabela termina, e o que faz um `TODO.md`
crescer sempre pelo mesmo lado. Com uma seção depois da tabela, essa invariante
era falsa por construção, e um guard que a exigisse recusaria qualquer edição
do arquivo. Pôr a INBOX no cabeçalho resolve na raiz e ainda a deixa visível:
descoberta não triada aparece antes do backlog, não enterrada no rodapé.

**Por quê a tabela única (mecânico, não estético):** a **leitura para no
primeiro cabeçalho repetido** -- ao encontrar um segundo cabeçalho com colunas
`ID` e `Status`, o parser encerra a tabela ali (é a defesa que impede contar
como itens as linhas de uma tabela alheia). Com duas tabelas de trabalho, tudo
o que está na segunda fica **invisível** para qualquer ferramenta e para
qualquer contagem, **sem erro nenhum na tela**: um backlog de centenas de itens
pode se apresentar como 1 ou 3 itens. A **linha em branco dentro da tabela** é
o caminho silencioso para chegar lá: parte a tabela em duas na renderização, e
a próxima edição que repetir o cabeçalho na metade de baixo fecha o buraco.

**Por quê nem tabela auxiliar "inofensiva":** a regra é literal -- *uma* tabela
-- justamente para não depender de julgamento sobre qual é a canônica. Toda
tabela a mais é uma candidata a ser eleita por engano por uma ferramenta, por
um agente ou por um leitor com pressa; quem decide por adivinhação erra (foi o
que aconteceu com o migrador de layout, que elegeu uma tabela de 3 itens no
lugar de uma de 339). Um critério que exige inspecionar colunas para saber se
aquele bloco "conta" é um critério que se degrada com a primeira exceção: hoje
a legenda não tem `Status`, amanhã alguém acrescenta uma coluna de progresso
nela. **Zero tabela auxiliar** é verificável de olho e por script, sem
interpretação -- e o custo é baixo, porque bullet e lista fazem o mesmo
trabalho de referência.

**Compatibilidade (leitura):** um arquivo no formato **legado** (INBOX depois
da tabela, ou qualquer texto após ela) continua **válido para leitura** --
nenhuma ferramenta desta skill o recusa, e os itens e entradas lidos são
exatamente os mesmos. O que ele recebe é um **aviso** de formato legado.
**Escrita e criação usam sempre a ordem nova.** A conversão é mecânica e
preserva byte a byte o conteúdo da tabela e da INBOX (só a ordem dos blocos
muda); ver o `README` deste repositório para o utilitário disponível na versão
que você está usando.

## 5.0.1. Uma tabela de checklist por PROJETO (não só por arquivo)

A regra de §5 é sobre o `TODO.md`. Ela tem uma irmã, de escopo maior: **o
projeto inteiro tem UMA tabela de checklist, e ela vive no `TODO.md`.** Nenhum
outro arquivo do projeto carrega fila de trabalho -- nada de `TODO_ARCHIVE.md`
com pendências vivas, `AUDIT_FIND.md` com achados a resolver, `PLANO.md` com
sua própria coluna `Status`. Checklist paralelo divide a fonte da verdade: dois
lugares para marcar a mesma coisa, e nenhum dos dois confiável.

**O que NÃO é violação:** tabela em outro documento que **não é fila de
trabalho** -- índice de ADR (`| ID | Título | Decisão | Status |` com `Status =
Aceito`), matriz de rotas, contagem de auditoria, comparativo. É documentação
de produto, e continua legítima.

**Como a diferença é medida** (é o critério que o `--audit` usa, e ele é
deliberadamente estreito porque falso positivo aqui é caro): a tabela só conta
como checklist quando tem, ao mesmo tempo, **coluna de identificador**, **coluna
`Status`** e **pelo menos uma linha cujo `Status` começa com um dos símbolos do
vocabulário fechado de §2**. O índice de ADR falha no terceiro critério e por
isso não é acusado. **Limitação declarada:** um checklist paralelo escrito sem
os símbolos (só "Pendente"/"Concluído" em texto) não é detectado -- falso
negativo aceito de propósito, para não acusar documento alheio.

**Ao absorver um checklist paralelo**, funda os itens na tabela do `TODO.md` e
deixe no lugar antigo, se precisar, só um ponteiro em prosa. O arquivo-modelo
da casa registra a absorção com uma seção de cabeçalho no estilo
`## Achados de auditoria (ex-ARQUIVO.md -- fundidos nesta única tabela)`, que
preserva a história sem recriar a fila.

## 5.1. INBOX -- exception queue (nao e a fila normal de descoberta)

> **Historico:** a formulacao antiga ("trabalho novo vai para a INBOX na hora")
> descrevia a epoca pre-intake. Mantida so como aviso: a norma vigente e a
> cascata abaixo. Detalhe operacional na skill e em `tools/todo_intake.py`.

Trabalho novo descoberto no meio do ciclo **nao espera** uma reordenacao completa
por default. O caminho normal e o **pipeline de intake** (descoberta -> main ->
`--add` / `todo_intake`):

1. item local com julgamento completo -> entra no `TODO.md` (L0);
2. impacto estrutural -> reorder proporcional (SCOPED/FULL);
3. so o **ambiguo** (campos incompletos, sem autoridade, needs-leader) vira
   **INBOX residual** -- exception queue, 1 linha, sem `Onda` nem WSJF.

- **Local padrao da residual:** secao `## INBOX (descobertas não priorizadas)`
  **antes da tabela** do `TODO.md` de projeto (ordem canonica, §5):
  ```markdown
  - <ID tentativo ou —>: [triage ...] descricao curta
  ```
- **Concorrencia** (sessoes/branches sem orquestrador comum): fallback
  arquivo-por-descoberta em `inbox/` (nao e backlog normal).
- **Regra de conflito:** ao resolver merge da INBOX (secao ou `inbox/`), sempre
  **unir** as descobertas. **Nunca descartar uma linha.**
- **Drenagem:** preferir `--drain`; `--create` e `--reorder` tambem esvaziam a
  INBOX (e o `inbox/`). Residual envelhecido ou classifiable emite
  `TAB_TRIAGE_REQUIRED` -- **acao da thread principal**, nao lembrete passivo.
- **Hub agregador:** nao usa INBOX; ver `references/hub-agregador.md`.

## 5.2. Forma do arquivo (o modelo que a casa escreve)

§5 é o contrato (que blocos, em que ordem). Esta seção é a **forma** que o
arquivo-modelo da casa dá a esse contrato -- é ela que se copia ao criar um
`TODO.md` novo. O modelo de referência é o `TODO.md` do projeto
**loucura_c_asm**, onde esta forma foi fixada em 2026-08-17. Nada aqui muda a leitura: um arquivo sem estes elementos
continua válido; o que eles fazem é deixar a regra **visível dentro do próprio
arquivo**, para quem editar não quebrar a tabela sem saber que existe regra.

**1. Linha 1 declara a estrutura** (uma linha, blockquote, antes do título):

```markdown
> **ESTRUTURA CANÔNICA DO ARQUIVO — NÃO QUEBRAR A TABELA:** (1) **Comentários e instruções** (só no cabeçalho, acima da tabela) · (2) **TABELA UNIFICADA** (exatamente uma tabela markdown de trabalho: `| ID | Onda | … | Status |`) · **EOF** imediatamente após a última linha da tabela. **Proibido:** segunda tabela; linha em branco **dentro** da tabela (o Markdown parte o arquivo em várias tabelas); qualquer seção de checklist/INBOX/WSJF **depois** da tabela (isso vai no cabeçalho).
```

Fica na **linha 1**, não no meio do arquivo: é a primeira coisa que qualquer
leitor (humano ou agente) lê antes de editar. O título `#` do arquivo vem logo
em seguida.

**2. A tabela tem um heading próprio, `## TABELA UNIFICADA`**, imediatamente
antes dela. O nome carrega a regra: *unificada* = uma só. É também o marcador
que separa, a olho nu, o cabeçalho (tudo que é comentário/instrução) do único
bloco de trabalho.

**3. Scoring WSJF, checklists e material de referência vão em BULLETS, no
cabeçalho** -- **nunca em tabela** (nem sem coluna `Status`), e nunca depois da
tabela. Quem precisar registrar scoring, sumário, contagem, legenda ou índice
usa **bullet ou lista**: é essa a razão de existir do formato em bullets do
modelo, não uma preferência estética. O arquivo inteiro tem **um** bloco
`|...|`.
O modelo usa este título e esta linha de escopo, literalmente:

```markdown
### Scoring WSJF (referência — **não** é tabela de trabalho)

Escala 1-10 · CoD = Valor + Criticidade + Redução de Risco/OE · WSJF = CoD ÷ Job Size.
Itens abaixo são **registro histórico de score**; o status de trabalho vive **só** na tabela única.

- **ID-DO-ITEM** · onda P1 · valor=6 crit=4 red=3 CoD=13 job=2 WSJF=6.5 rank=1
```

Os dois pedaços são intencionais: o **título** diz o que a seção não é
("**não** é tabela de trabalho"), e a **linha de escopo** diz onde o status
mora ("o status de trabalho vive **só** na tabela única"). Sem eles, a próxima
pessoa que precisar marcar progresso de um score transforma a lista numa tabela
com coluna `Status` -- e o arquivo passa a ter duas tabelas, exatamente o
defeito que §5 proíbe. Repare que no modelo o scoring é **lista de bullets**,
não tabela: o arquivo tem um único bloco `|...|`, o da tabela canônica.

**Esqueleto completo:**

```markdown
> **ESTRUTURA CANÔNICA DO ARQUIVO — NÃO QUEBRAR A TABELA:** (1) ... (2) ... EOF ...

# TODO — <projeto>

<prosa de cabeçalho: convenção de frescor, porte, legenda>

## INBOX (descobertas não priorizadas)

- —: [triage since=AAAA-MM-DD reason=missing-info] descoberta ainda não triada

## Material movido do rodapé (só no cabeçalho)

### Scoring WSJF (referência — **não** é tabela de trabalho)

- **ID-DO-ITEM** · onda P1 · ... WSJF=6.5 rank=1

## TABELA UNIFICADA

| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EX-1 | W1 | Base | ... | Alta | — | Baixa | ⏳ Pendente | — |
```

**Referência:** esta forma foi extraída do `TODO.md` que serve de **modelo da
casa** (um backlog real de centenas de itens, mantido pelo líder). O modelo é
citado aqui como exemplo de documentação; **nenhum nome de projeto, caminho ou
convenção de projeto específico entra no código deste produto** -- os checks
verificam a REGRA (uma tabela de trabalho, sem linha em branco no meio), nunca
a presença destes títulos.

## 6. Automação mecânica (opcional)

A parte mecânica das seções 2-5 pode ser acelerada por scripts complementares,
determinísticos e locais -- sem dependência de LLM/agente, sempre executados no seu
próprio ambiente. Quando presentes no repositório, seguem este contrato:

- **Sincronização de status**: avança itens `⏳`/`🔄` para `🔍` a partir dos IDs citados em
  commits que tocaram trabalho substantivo (§4). Nunca atribui `✅`. Nunca reordena nem
  toca a coluna `Onda`. A alteração real do arquivo exige confirmação explícita (ex.: uma
  flag do tipo `--apply`); sem ela, o script só mostra a proposta.
- **Relatório de frescor + sinais `TAB_*`**: reporta contagens por status, itens presos em
  `🔍`, tamanho da INBOX residual/classifiable, e emite identificadores estáveis
  (`TAB_TRIAGE_REQUIRED`, `TAB_STATUS_SYNC_RECOMMENDED`, ...). Contrato dos IDs em
  [`sinais-de-frescor.md`](sinais-de-frescor.md). `TAB_TRIAGE_REQUIRED` pede **dreno**
  (`--drain`), não full reorder por passagem de tempo.
- **Intake / dreno**: classifica e persiste trabalho novo (§5.1); journal write-ahead e lock
  de escrita no apply.
- **Aviso pós-commit**: quando ativado como hook local, opera sempre em modo *só aviso* --
  nunca bloqueia o commit, nunca falha a operação do git. **HOOKSRC:** o path vivo do hook
  deve ser a instalação **publicada** (pin de submódulo no consumidor), não um checkout
  de desenvolvimento do produto.

**Estes scripts são um acelerador, não um requisito.** Sem eles -- ou num ambiente sem a
linguagem/runtime necessário --, a norma continua valendo integralmente: quem entrega
trabalho toca a célula de `Status` manualmente no mesmo commit/PR (§2), cita o ID (§4), e
usa intake/INBOX residual (§5.1) à mão. Consulte o `README` deste repositório para a
disponibilidade e a invocação exata desses scripts na versão que você está usando.
