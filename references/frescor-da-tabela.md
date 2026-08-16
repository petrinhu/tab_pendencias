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
| **De projeto** | Itens editáveis; cada item corresponde a um trabalho identificável, e a relação item-commit faz sentido. | Sim -- DoD de status (§2), separação sincronizar/reordenar (§3), regra do ID no commit (§4) e INBOX (§5) valem aqui. |
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
| **Reordenar** | Recalcular a ordem das linhas, a coluna `Onda`, ou inserir item novo com dependência/prioridade | Caro, exige julgamento | Só quando um input de priorização muda: nova dependência, item ficou urgente, ou a INBOX (§5) deixou de estar vazia |

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

## 5. INBOX -- exception queue (nao e a fila normal de descoberta)

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

- **Local padrao da residual:** secao `## INBOX (descobertas não priorizadas)` no
  fim do `TODO.md` de projeto:
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

## 6. Automação mecânica (opcional)

A parte mecânica das seções 2-4 pode ser acelerada por scripts complementares,
determinísticos e locais -- sem dependência de LLM/agente, sempre executados no seu
próprio ambiente. Quando presentes no repositório, seguem este contrato:

- **Sincronização de status**: avança itens `⏳`/`🔄` para `🔍` a partir dos IDs citados em
  commits que tocaram trabalho substantivo (§4). Nunca atribui `✅`. Nunca reordena nem
  toca a coluna `Onda`. A alteração real do arquivo exige confirmação explícita (ex.: uma
  flag do tipo `--apply`); sem ela, o script só mostra a proposta.
- **Relatório de frescor**: reporta contagens por status, itens presos em `🔍` por muito
  tempo, e o tamanho da INBOX.
- **Aviso pós-commit**: quando ativado como hook local, opera sempre em modo *só aviso* --
  nunca bloqueia o commit, nunca falha a operação do git.

**Estes scripts são um acelerador, não um requisito.** Sem eles -- ou num ambiente sem a
linguagem/runtime necessário --, a norma continua valendo integralmente: quem entrega
trabalho toca a célula de `Status` manualmente no mesmo commit/PR (§2), cita o ID (§4), e
usa a INBOX (§5) à mão. Consulte o `README` deste repositório para a disponibilidade e a
invocação exata desses scripts na versão que você está usando.
