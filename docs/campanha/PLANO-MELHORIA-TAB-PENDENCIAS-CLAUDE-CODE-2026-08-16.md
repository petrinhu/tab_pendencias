# Plano mestre de melhoria da `tab_pendencias`

## Redesign de intake, priorização, frescor e sincronização do vault

**Data-base:** 2026-08-16  
**Destinatário:** Claude Code operando o ecossistema `petrinhu/tab_pendencias` + `petrinhu/claude-memory`  
**Objetivo primário:** eliminar a INBOX como fila normal de trabalho e transformá-la em fila excepcional de triagem, com integração imediata de trabalho classificável no `TODO.md`, preservando dependências, WSJF/SAFe, WIP, concorrência e autoridade do líder.  
**Objetivo adicional obrigatório:** reconciliar e atualizar o repositório GitHub `petrinhu/tab_pendencias`, que o líder suspeita estar desatualizado em relação à instalação viva. Essa suspeita é **alegada, ainda não verificada contra a máquina local** e deve ser medida antes de qualquer migração.

---

# 0. Como usar este documento

Este documento é um **runbook executável**, não uma lista de ideias. O Claude Code que executar a campanha deve obedecer à ordem de dependências, aos gates e aos critérios de pronto descritos aqui.

Regra central:

> **Relatório de agente não é prova. O orquestrador mede o artefato real.**

Uma etapa só está concluída quando o gate objetivo correspondente passa. Quantidade de commits, agentes acionados, documentos produzidos ou mensagens de “entregue” não contam como progresso se a métrica-alvo não se moveu.

A campanha deve preservar os princípios atuais que ainda são válidos:

1. sincronização de status é barata, mecânica e não deve disparar replanejamento;
2. dependência topológica vence prioridade econômica;
3. WSJF ordena apenas itens que são simultaneamente executáveis no mesmo nível de dependência;
4. `TODO.md` de projeto é fonte de verdade editável; hub agregador é view derivada;
5. implementação entregue vira `🔍 Pendente verificação`, nunca `✅ Concluído` diretamente;
6. `✅ Concluído` exige validação correspondente;
7. pedido recebido pelo bus é priorizado pelo projeto receptor, não pelo remetente;
8. trabalho em andamento não deve ser preemptado por uma descoberta pequena apenas porque ela obteve WSJF alto;
9. decisões de arquitetura, stack, escopo irreversível e outras one-way doors continuam pertencendo ao líder;
10. nenhuma automação pode perder uma descoberta silenciosamente.

---

# Escopo e não-objetivos

Esta campanha é deliberadamente estreita. Ela melhora o ciclo de vida de trabalho novo e a distribuição da própria skill. **Não** autoriza, por si só:

- migrar a fonte de verdade de `TODO.md` para GitHub Issues/Projects;
- criar daemon ou agente LLM continuamente ativo para vigiar prioridade;
- reordenar a tabela inteira a cada prompt;
- aplicar SAFe formal em projeto que não satisfaz critério de escala;
- transformar o bus em backlog ou fonte de prioridade;
- permitir que subagentes concorrentes editem livremente o mesmo `TODO.md`;
- remover compatibilidade com tabelas existentes sem uma migração medida;
- apagar cópias locais antigas antes de provar que o repo publicado é superset comportamental;
- usar a suspeita do líder de que o GitHub está desatualizado como prova. A suspeita é o gatilho para medir, não o resultado da medição.

A eventual migração para Issues/Projects continua sendo uma decisão separada e de alto custo de reversão. Este plano deve funcionar mantendo `TODO.md` como backlog canônico.

---

# Roteamento de modelos Anthropic

Sempre que este plano mencionar um modelo, a nomenclatura obrigatória é a definida pelo líder:

- **[Fable] 5 ou mais recente**
- **[Opus] 5 ou mais recente**
- **[Sonnet] 5 ou mais recente**

## Papéis

| Papel | Modelo | Responsabilidade |
|---|---|---|
| Orquestrador principal / `main` | **[Opus] 5 ou mais recente** | coordena a campanha, lê resultados, repete medições, executa gates, integra diffs, faz commits locais e controla publicação |
| Implementação normal | **[Sonnet] 5 ou mais recente** | código Python, testes, documentação, migrações mecânicas, hooks, parsers, CLI, fixtures e CI |
| Planejamento simples e médio | **[Opus] 5 ou mais recente** | decomposição de fatias, critérios de aceitação, análise de regressão, decisão de escopo local |
| Implementação excepcionalmente difícil | **[Opus] 5 ou mais recente** | concorrência, transações de escrita, migração de fonte de verdade, algoritmo de reorder parcial, bugs de parsing com alto blast radius |
| Arquitetura muito complexa | **[Fable] 5 ou mais recente** | desenho da máquina de estados, reconciliação multi-fonte e arquitetura de priorização incremental |
| Auditoria adversarial de marco crítico | **[Fable] 5 ou mais recente** | tentar refutar que o novo fluxo fecha o ciclo e que repo/vault estão sincronizados |

## Trabalhos reservados a [Fable] 5 ou mais recente

### ARCH-EXTREME-01 - Arquitetura da máquina de estados de intake

Entregar uma especificação formal de:

`captura -> normalização -> deduplicação -> dependências -> impacto -> scoring -> decisão de rota -> integração -> validação`

A especificação deve provar que cada descoberta termina em exatamente um estado terminal válido e que nenhum item classificável pode permanecer indefinidamente na INBOX.

### SOT-EXTREME-01 - Arquitetura de fonte de verdade e distribuição

Mapear e decidir a fronteira entre:

- `petrinhu/tab_pendencias`;
- instalação viva em `~/.claude/skills/tab_pendencias`;
- `petrinhu/claude-memory`;
- hooks Claude Code;
- scripts git-hook/toolkit;
- documentação global do vault;
- configuração por projeto;
- submódulo e rotina de recuperação.

Objetivo: eliminar lógica normativa duplicada e impedir nova divergência repo-vivo.

### AUD-EXTREME-01 - Auditoria adversarial final

Agente novo, sem ter implementado as mudanças, recebe os artefatos finais e a instrução:

> “Assuma que a equipe está errada. Tente provar que a INBOX ainda pode crescer indefinidamente, que um item pode ser perdido, que um pedido pode ser priorizado pelo remetente, que um reorder pode violar dependência topológica, ou que o GitHub e o vault ainda podem divergir sem alarme.”

Nenhuma das três tarefas acima deve ser substituída por implementação direta de **[Fable] 5 ou mais recente**. A função é produzir ou auditar arquitetura. Código cotidiano continua com **[Sonnet] 5 ou mais recente**, salvo escalação explícita para **[Opus] 5 ou mais recente**.

---

# Política de agentes, commits e pushes

## Subagentes

Subagentes podem:

- ler arquivos;
- editar sua worktree;
- escrever testes;
- executar testes;
- gerar diffs;
- gerar medições;
- propor decisões.

Subagentes não podem:

- fazer push;
- criar tag;
- publicar release;
- fazer merge remoto;
- declarar um gate aprovado com base apenas no próprio trabalho.

Commit local por subagente também deve ser evitado por padrão. O fluxo preferido é entrega de diff/worktree para o `main`.

## `main`

O `main`, executado por **[Opus] 5 ou mais recente**, deve:

1. receber a entrega;
2. inspecionar `git diff`;
3. repetir testes relevantes;
4. repetir contadores e auditorias;
5. rejeitar auto-relato não reproduzível;
6. só então fazer commit local.

Push continua sujeito à política global do vault: exige autorização explícita do líder naquele contexto, salvo se o líder tiver concedido modo autônomo amplo que inclua pushes. Quando a publicação desta campanha for autorizada, somente o `main` publica.

Ordem de publicação obrigatória:

1. `petrinhu/tab_pendencias` canônico;
2. confirmar SHA remoto e CI;
3. atualizar o gitlink/submódulo em `petrinhu/claude-memory`;
4. atualizar bindings/docs/hooks do vault;
5. validar recuperação em clone limpo;
6. só então publicar `claude-memory`.

---

# I. Falhas históricas

## I.1. O problema original que a INBOX tentou resolver

Em 2026-06-20, a arquitetura de frescor separou corretamente duas operações que estavam acopladas:

- sincronizar status: mecânico, barato e frequente;
- replanejar: julgamento, caro e raro.

Isso resolveu um defeito real: marcar trabalho entregue parecia exigir replanejamento completo e, por consequência, `TODO.md` ficava defasado.

O mecanismo escolhido para novas descobertas foi:

`descoberta -> INBOX -> futura execução de --create/--reorder -> integração no TODO`

A decisão foi razoável para reduzir custo de captura. O erro não foi criar um buffer; o erro foi **não garantir liveness do consumidor desse buffer**.

## I.2. Mecanismo de falha atual: fila durável, consumidor voluntário

A regra atual diz que toda descoberta nova vai para INBOX e que `--create`/`--reorder` drenam a fila. O hook global apenas lembra; não garante consumo.

Portanto a máquina de estados efetiva possui uma transição dependente de memória humana:

```text
novo trabalho
   -> INBOX
   -> espera
   -> alguém lembra de rodar --reorder
   -> TODO priorizado
```

Isso viola uma propriedade básica de liveness: trabalho preservado não é trabalho processado.

## I.3. A documentação já previa a falha

A documentação global de frescor registra explicitamente o risco residual “INBOX vira lixeira” caso não seja drenada regularmente. O problema observado pelo líder em 2026-08-16 é, portanto, a materialização de um risco já conhecido, não um caso inesperado.

## I.4. Contradição interna na própria skill

A skill possui duas regras que não fecham entre si:

1. seção de frescor: todo trabalho novo vai primeiro para INBOX;
2. seção de gatilho de reordenação: item pequeno/local pode ser “só anexado” diretamente na onda adequada, enquanto item de alto impacto dispara `--reorder`.

A segunda regra é conceitualmente mais próxima do comportamento desejado, mas a primeira virou o default operacional. O redesign deve remover a ambiguidade e tornar a integração direta o caminho normal.

## I.5. O hook mede defasagem, mas não fecha o ciclo

`tab_pendencias_reminder.py` mede commits/dias desde o último toque e tempo de sessão. Ele é deliberadamente fail-open e warning-only. Isso é correto para evitar bloqueio do Claude Code, porém insuficiente para garantir drenagem da INBOX.

O novo desenho não deve transformar o hook em um replanejador LLM. Ele deve continuar determinístico, mas passar a emitir um **sinal operacional acionável** quando uma fila residual excede limites, de forma que a thread principal trate o sinal automaticamente.

## I.6. Divergência entre produto distribuído e instalação viva já aconteceu

O histórico do próprio projeto registra uma divergência de comportamento entre toolkit no repo e toolkit vivo, com diferença de centenas de linhas, exigindo uma prova de “superset comportamental” antes de substituir a instalação viva.

Também houve documentação de instalação publicada que não funcionava ao ser seguida literalmente; o defeito só apareceu quando a receita foi testada por um commit real em repo descartável.

Mecanismo repetível:

> lógica vive em dois lugares -> ambos evoluem -> documentação ou testes cobrem só um -> instalação real diverge do produto distribuído.

Este mecanismo deve ser eliminado, não apenas consertado outra vez.

## I.7. Gitlink/submódulo comprovadamente atrás da `main` do produto

Estado remoto medido em 2026-08-16:

- `petrinhu/tab_pendencias/main`: `896ff56a071a2a4e07812edb34073e93156fbe3a`;
- `petrinhu/claude-memory` aponta `skills/tab_pendencias` para `196f03d8b5d356dca77fc2037a77d4230b93524c`.

Logo, independentemente de qualquer estado local ainda não observado, o backup `claude-memory` não restaura a revisão mais recente publicada da skill.

Isso é uma falha objetiva de distribuição.

## I.8. A alegação de que o próprio repo GitHub está desatualizado precisa de medição local

O líder informou em 2026-08-16 que acredita que `petrinhu/tab_pendencias` também está desatualizado em relação ao ambiente vivo.

Classificação:

> **ALEGADO PELO LÍDER, NÃO VERIFICADO NESTA AUDITORIA REMOTA.**

O Claude Code executando este runbook tem acesso à máquina e deve medir isso no primeiro gate, antes de tocar a arquitetura.

## I.9. Inconsistência de scoring WSJF

Há uma deriva normativa entre camadas do vault:

- a skill documenta scoring numérico genérico de 1 a 20 para Valor, Criticidade, Redução de Risco e Job Size;
- a norma global de Agile/SAFe do vault define a escala Fibonacci modificada `(1, 2, 3, 5, 8, 13, 20)`.

Isso cria duas réguas para a mesma decisão. O redesign deve manter o núcleo genérico agnóstico e, no perfil da casa/SAFe, usar uma única régua consistente com a norma global.

## I.10. O bus já possui uma regra de ownership de prioridade que deve ser preservada

No `gusworld_ia_autocomm`, pedidos comuns via bus não carregam classificação de importância. Quem recebe decide a posição na própria fila porque conhece roadmap, custo e dependências.

A `tab_pendencias` redesenhada não pode inferir prioridade a partir de frases do remetente como “urgente”, “quando der” ou “bloqueia X” em pedidos comuns. Ela deve usar fato de uso, dependências reais, criticidade temporal factual e contexto do projeto receptor.

Exceções explícitas do protocolo, como o fluxo de ideias do Gus com sua prioridade própria, continuam sendo exceções de domínio e não devem contaminar o core genérico.

---

# II. Estado atual, medido agora

## II.1. `petrinhu/tab_pendencias`

Snapshot remoto verificado em 2026-08-16:

- `main`: `896ff56a071a2a4e07812edb34073e93156fbe3a`;
- changelog mais recente publicado no repositório: `1.0.2`, datado de 2026-07-29;
- skill atual contém INBOX, `--create`, `--reorder`, `--show`, `--main`, injeção de testes/auditorias e toolkit local;
- repo possui parser, `todo_sync`, `todo_health`, `todo_freshness`, `todo_audit`, `todo_fix`, CI e testes;
- `TODO.md` atual do próprio produto contém **2 itens na INBOX residual** no snapshot consultado;
- o próprio `TODO.md` registra WIP = 1 onda.

## II.2. `petrinhu/claude-memory`

Estado remoto verificado:

- `skills/tab_pendencias` é submódulo;
- gitlink aponta para `196f03d8...`, anterior à `main` atual do produto;
- `CLAUDE.md` global referencia a política de frescor;
- `docs/tabela-pendencias-frescor.md` ainda define INBOX como Camada 1 normal;
- `hooks/tab_pendencias_reminder.py` é uma implementação separada de reminder/staleness;
- `settings.sanitized.json` liga esse hook em `SessionStart` e `UserPromptSubmit`;
- runbook de recuperação `AGENTS.md` restaura os submódulos, portanto um gitlink velho propaga uma skill velha para uma máquina nova.

## II.3. Vault

A documentação versionada declara um vault com hierarquia global -> projeto, cinco manuais canônicos e estrutura PARA. Para este redesign, as responsabilidades relevantes são:

- regras universais: `claude-memory/CLAUDE.md` e `docs/`;
- skill distribuível: `tab_pendencias`;
- regras específicas de um projeto: `CLAUDE.md`, `.tab_pendencias.ini` e `TODO.md` do projeto;
- hub agregador: view derivada, nunca fila editável;
- bus: transporte de pedidos entre projetos, não dono da prioridade.

## II.4. Limitação desta medição

Esta auditoria remota não vê o filesystem vivo da máquina do líder. Não foi possível medir:

- se `~/.claude/skills/tab_pendencias` contém commits não publicados;
- se há modificações locais não commitadas;
- se scripts em `~/.claude/githooks/` ou outro path vivo são mais novos que o repo;
- se `settings.json` real diverge do template sanitizado;
- se alguma sessão criou patches fora dos repositórios.

O primeiro marco da execução existe exatamente para fechar essa lacuna.

---

# III. Plano de melhoria e prevenção

# Meta arquitetural

Substituir:

```text
NOVA DESCOBERTA
    -> INBOX obrigatória
    -> espera humana
    -> --reorder futuro
    -> TODO
```

por:

```text
NOVA DESCOBERTA
    -> normalizar + deduplicar
    -> avaliar dependências e impacto
    -> escolher uma rota
       A. integrar localmente no TODO
       B. reordenar somente o componente afetado
       C. reordenar a tabela inteira
       D. INBOX residual, somente se não classificável agora
    -> validar invariantes
    -> atualizar view/hub quando aplicável
```

## Invariante principal

> **INBOX saudável = zero itens classificáveis.**

Não significa necessariamente zero itens absolutos. Um item pode permanecer na INBOX se falta informação real, existe conflito de decisão ou depende de autoridade do líder. Nesse caso precisa carregar motivo explícito e prazo/sinal de nova triagem.

---

# Fase 0 - Congelar escrita e reconciliar fontes de verdade

**Modelo de planejamento:** **[Fable] 5 ou mais recente** em `SOT-EXTREME-01`.  
**Execução:** **[Sonnet] 5 ou mais recente**.  
**Verificação:** `main` em **[Opus] 5 ou mais recente**.

Esta fase precede qualquer redesign. Não implementar intake novo sobre uma cópia possivelmente antiga.

## TAB-SOT-000 - Janela de manutenção do auto-snapshot

O `claude-memory` possui `systemd/claude-memory-push.service` que executa `bin/auto_push.sh`; o script faz `git add -A`, cria commit de snapshot e faz push de `main` quando encontra mudanças. Isso pode publicar acidentalmente um estado intermediário enquanto o submódulo e os bindings estão sendo reconciliados.

Antes de editar `~/.claude`:

1. medir se o timer real está ativo;
2. registrar seu estado anterior;
3. se ativo, suspender temporariamente o timer durante a janela de reconciliação;
4. não alterar o arquivo da unit apenas para fazer manutenção;
5. ao final, restaurar exatamente o estado anterior e verificar o próximo disparo;
6. inspecionar `backups/auto_push.log` para garantir que nenhum snapshot parcial ocorreu durante a janela.

Comandos devem ser escolhidos conforme o ambiente real. Em Linux/systemd, exemplos de inspeção são:

```bash
systemctl --user is-active claude-memory-push.timer
systemctl --user list-timers | grep claude-memory || true
```

Se outro mecanismo de auto-snapshot estiver ativo na máquina real, aplicar a mesma regra.

## TAB-SOT-001 - Inventário local obrigatório

No filesystem vivo, registrar sem alterar nada:

```bash
pwd
git -C ~/.claude status --short
git -C ~/.claude rev-parse HEAD
git -C ~/.claude submodule status skills/tab_pendencias
git -C ~/.claude/skills/tab_pendencias status --short
git -C ~/.claude/skills/tab_pendencias rev-parse HEAD
git -C ~/.claude/skills/tab_pendencias remote -v
```

Em um clone fresco separado de `petrinhu/tab_pendencias`, medir `origin/main`.

Também localizar cópias candidatas:

```bash
find ~/.claude -type f \( \
  -name 'SKILL.md' -o \
  -name 'todo_lib.py' -o \
  -name 'todo_sync.py' -o \
  -name 'todo_health.py' -o \
  -name 'todo_freshness.py' -o \
  -name 'tab_pendencias_reminder.py' \
\) -print
```

Não assumir que paths históricos continuam válidos.

## TAB-SOT-002 - Matriz de divergência

Produzir uma tabela com:

| Artefato | Local vivo | Repo `tab_pendencias` | `claude-memory` | Igual? | Mais novo onde? | Ação |
|---|---|---|---|---|---|---|
| `SKILL.md` | SHA/hash | SHA/hash | gitlink | sim/não | ... | ... |
| `todo_lib.py` | ... | ... | ... | ... | ... | ... |
| `todo_sync.py` | ... | ... | ... | ... | ... | ... |
| `todo_health.py` | ... | ... | ... | ... | ... | ... |
| `todo_freshness.py` | ... | ... | ... | ... | ... | ... |
| Claude hook | ... | candidato no repo | ... | ... | ... | ... |
| norma de frescor | ... | `references/...` | `docs/...` | ... | ... | ... |
| config | ... | defaults | template | ... | ... | ... |

Comparar comportamento, não apenas número de linhas.

## TAB-SOT-003 - Preservação antes de migração

Se existir qualquer alteração viva não publicada:

1. salvar `git diff` em `/var/tmp/tab-pendencias-reconcile/`;
2. registrar hashes;
3. criar branch local de preservação se o repo permitir;
4. não resetar, apagar ou sobrescrever a cópia viva;
5. executar testes contra a versão viva e a publicada para criar baseline comparável.

## TAB-SOT-004 - Definir fonte canônica

Decisão-alvo:

### `petrinhu/tab_pendencias`

Deve possuir:

- skill genérica;
- parser e toolkit;
- máquina de intake genérica;
- auditoria/fix;
- documentação normativa distribuível;
- testes;
- CI;
- hook Claude reutilizável, se for implementado como produto genérico.

### `petrinhu/claude-memory`

Deve possuir apenas:

- gitlink/submódulo;
- configuração e bindings da casa;
- política global que chama/usa a skill;
- overlay de contexto do vault;
- `settings.sanitized.json`;
- adaptações específicas da constelação de agents e do bus.

Regra:

> **Comportamento genérico não pode ter duas implementações independentes.**

## TAB-SOT-005 - Atualizar primeiro o repo `tab_pendencias`

Após portar toda melhoria viva ainda ausente no GitHub:

1. rodar suíte completa;
2. rodar `scripts/preci.sh` ou equivalente atual;
3. rodar auditoria dogfood contra o próprio `TODO.md`;
4. instalar em repo descartável e executar a receita documentada literalmente;
5. testar em clone limpo;
6. verificar que nenhuma funcionalidade viva foi perdida;
7. produzir changelog da atualização.

Se a mudança da semântica de intake for incompatível com comportamento anterior, tratar como mudança de produto e aplicar SemVer corretamente. A decisão final de versão é do release manager/líder após medir o diff; não inventar número antes.

## TAB-SOT-006 - Só depois atualizar `claude-memory`

Após o repo canônico estar publicado e validado:

1. avançar `skills/tab_pendencias` para o SHA publicado;
2. atualizar `CLAUDE.md` e docs globais;
3. alterar hook/binding para consumir a implementação canônica;
4. remover apenas duplicações comprovadamente substituídas;
5. não apagar fallback vivo antes de teste de paridade;
6. rodar recuperação completa em clone descartável:

```bash
git clone --recursive <claude-memory> /var/tmp/claude-memory-recovery-test
```

7. provar que a skill restaurada é a versão esperada;
8. executar smoke real da skill nesse clone.

## TAB-SOT-007 - Prevenir nova defasagem do submódulo

Criar um mecanismo de **detecção**, não de atualização automática, para o pin do submódulo:

- gêmeo local: script read-only que obtém o SHA pinado e consulta o remoto/tag estável quando há rede;
- gêmeo CI: job warning-only em `claude-memory` que acusa quando existe release estável de `tab_pendencias` não propagada para o gitlink;
- sem rede: o check declara capacidade limitada, nunca finge frescor;
- nunca fazer `git submodule update --remote` silencioso em hook;
- nunca auto-commit/auto-push do bump;
- o alerta deve incluir `pinned_sha`, `latest_release_sha` e quantos commits/releases de diferença foram detectados.

Contrato de propagação:

> Toda release de `tab_pendencias` que altera comportamento usado pelo vault cria uma obrigação rastreável de revisar e, se aprovada, atualizar o gitlink de `claude-memory` no mesmo ciclo de release.

O objetivo é tornar drift visível antes de uma restauração de máquina descobrir o problema.

## Gate SOT-0

A fase termina apenas se:

- [ ] foi medido se o repo GitHub estava ou não desatualizado;
- [ ] toda divergência tem dono e decisão;
- [ ] nenhuma melhoria viva foi perdida;
- [ ] `tab_pendencias` é fonte canônica do produto;
- [ ] `claude-memory` aponta para a revisão canônica correta;
- [ ] clone `--recursive` restaura versão correta;
- [ ] não há duas cópias ativas da mesma lógica de frescor/intake.
- [ ] existe detector warning-only de drift do submódulo, com gêmeo local e CI.
- [ ] auto-snapshot do vault não pode publicar estado intermediário da reconciliação.

---

# Fase 1 - ADR do novo modelo de intake

**Planejamento:** `ARCH-EXTREME-01` por **[Fable] 5 ou mais recente**.  
**Refino:** **[Opus] 5 ou mais recente**.  
**Código nesta fase:** nenhum, exceto testes de contrato que congelem o comportamento antigo para comparação.

## TAB-ADR-001 - Estados formais

Toda descoberta vira um `WorkCandidate` conceitual com:

- descrição;
- origem;
- evidência;
- projeto receptor;
- dependências conhecidas;
- impacto estimado;
- status de decisão;
- possível relação com item existente.

Estados:

```text
NEW
 -> DUPLICATE
 -> LOCAL_INTEGRATION
 -> SCOPED_REORDER
 -> FULL_REORDER
 -> NEEDS_TRIAGE
 -> NEEDS_LEADER_DECISION
```

`DUPLICATE`, `LOCAL_INTEGRATION`, `SCOPED_REORDER`, `FULL_REORDER` e `NEEDS_LEADER_DECISION` são saídas controladas. `NEEDS_TRIAGE` é a única rota que gera INBOX residual.

## TAB-ADR-002 - Propriedade de exatamente um destino

Ao final de qualquer intake:

```text
count(destinos_validos) == 1
```

É proibido:

- item simultaneamente no TODO e INBOX;
- item perdido sem registro;
- duas linhas novas representando a mesma descoberta;
- item estrutural parado na INBOX sem motivo;
- item “resolvido mentalmente” mas não persistido.

## TAB-ADR-003 - Semântica nova da INBOX

A INBOX deixa de significar “trabalho novo ainda não priorizado”.

Passa a significar:

> **fila excepcional de candidatos que não podem ser integrados com segurança no momento atual.**

Motivos válidos, por exemplo:

- requisito ambíguo;
- falta de evidência mínima;
- conflito de dependência;
- decisão de arquitetura/escopo reservada ao líder;
- conflito entre duas solicitações;
- origem concorrente que não consegue adquirir ownership do `TODO.md`.

Motivos inválidos:

- “não quis reordenar agora”;
- “depois vemos”; 
- “é mais barato colocar aqui”;
- “a tabela está grande”; 
- “o agente está terminando a sessão”.

## TAB-ADR-004 - Metadados mínimos da INBOX residual

Preservar compatibilidade com a linha `- ID: descrição`, acrescentando metadados dentro da descrição em formato parseável e opcional, por exemplo:

```markdown
- <ID-ou-vazio>: [triage since=2026-08-16 reason=missing-context source=bus] descrição
```

O formato final deve ser decidido pelo ADR e testado contra o parser atual. Não introduzir YAML complexo ou banco paralelo sem necessidade.

No mínimo deve ser possível medir:

- data de entrada;
- razão;
- origem;
- número de ciclos de triagem em que sobreviveu.

## TAB-ADR-005 - WIP não é prioridade

Se um item já está `🔄 Em andamento`, uma descoberta de WSJF superior não o interrompe automaticamente.

Preempção só é válida se:

- defeito crítico impede continuação;
- segurança/integridade exige parada;
- dependência descoberta prova que o trabalho em curso está construído sobre base inválida;
- líder manda preemptar.

Isso evita priority thrashing.

## Gate ADR-1

- [ ] máquina de estados aprovada;
- [ ] INBOX redefinida como exception queue;
- [ ] critérios de rota são objetivos;
- [ ] WIP protegido;
- [ ] autoridade do líder preservada;
- [ ] regra do bus preservada;
- [ ] compatibilidade e migração documentadas.

---

# Fase 2 - Implementar `--add` / intake agentivo

**Implementação:** **[Sonnet] 5 ou mais recente**.  
**Casos difíceis:** escalação para **[Opus] 5 ou mais recente**.  
**Verificação:** `main` em **[Opus] 5 ou mais recente**.

## TAB-ADD-000 - Write-ahead journal de intake

Antes de qualquer classificação agentiva que possa terminar em alteração persistente, registrar o candidato num journal local e barato. Isso é **captura durável**, não INBOX de planejamento.

Local recomendado: dentro do git common dir, obtido por `git rev-parse --git-common-dir`, por exemplo:

```text
<GIT_COMMON_DIR>/tab-pendencias/intake-journal/<candidate-id>.json
```

Vantagens:

- não polui `TODO.md`;
- não vira backlog versionado;
- é compartilhável entre worktrees do mesmo repositório quando o git common dir é comum;
- sobrevive a crash da sessão/processo;
- não depende da memória humana ou do transcript.

Registro mínimo:

```json
{
  "candidate_id": "...",
  "created_at": "...",
  "source": "user|bus|agent|audit|test",
  "description": "...",
  "source_item": "...",
  "state": "NEW"
}
```

Regras:

1. journal é gravado atomicamente antes da mutação do TODO;
2. após integração persistida e validada, o registro vira `DONE` ou é removido de forma segura;
3. crash deixa registro órfão;
4. `SessionStart`/health detecta órfãos e emite `TAB_INTAKE_RECOVERY_REQUIRED`;
5. recuperação é idempotente: primeiro deduplica contra TODO/INBOX antes de repetir;
6. conteúdo sensível/segredo nunca entra no journal; sanitizar ou referenciar a origem em vez de copiar segredo;
7. o journal não substitui `inbox/` versionado usado como fallback entre sessões/branches realmente independentes.

A escolha exata de path/formato deve ser validada em Linux e Windows e não pode assumir `.git` como diretório físico simples em worktree.

## TAB-ADD-001 - Novo modo de entrada

Adicionar um modo explícito de skill equivalente a:

```text
/tab_pendencias --add
```

Ele pode receber o candidato pela conversa corrente ou por documento/fonte que a thread principal indique.

Natural language triggers como “adicione isto às pendências”, “registra esta feature”, “isso precisa entrar no TODO” devem usar o mesmo pipeline.

## TAB-ADD-002 - Normalização e deduplicação

Antes de criar linha:

1. procurar ID explícito;
2. procurar descrição semanticamente equivalente;
3. procurar item no TODO;
4. procurar item na INBOX residual;
5. procurar item concluído que possa estar sendo reaberto;
6. se for bus, usar thread/assunto/origem como evidência auxiliar;
7. nunca deduplicar apenas por string idêntica se os critérios de aceitação diferirem.

Se duplicata verdadeira:

- enriquecer evidência/contexto do item existente se necessário;
- não criar nova linha.

## TAB-ADD-003 - Classificação de impacto

Classificar o candidato em quatro níveis operacionais:

### L0 - local

- escopo isolado;
- dependências já satisfeitas ou triviais;
- não altera fundação;
- não muda APIs/contratos;
- não muda outros itens;
- cabe no nível topológico atual.

Ação: `LOCAL_INTEGRATION`.

### L1 - impacto de componente

- cria dependência de poucos itens;
- muda ranking de um nível topológico;
- afeta um pequeno componente conectado do grafo.

Ação: `SCOPED_REORDER`.

### L2 - estrutural

- fundação;
- one-way door;
- cross-módulo;
- muda contrato;
- torna itens existentes prematuros;
- altera vários caminhos do grafo.

Ação: `FULL_REORDER` ou `NEEDS_LEADER_DECISION` se a decisão exceder autoridade do agente.

### L3 - não classificável

- dados insuficientes ou conflito real.

Ação: `NEEDS_TRIAGE`.

## TAB-ADD-004 - Integração local

Para L0:

1. determinar pré-requisitos;
2. encontrar nível topológico;
3. avaliar prioridade apenas contra peers relevantes;
4. inserir na posição adequada;
5. recalcular Onda apenas no segmento afetado;
6. preservar byte/order das regiões não afetadas;
7. validar grafo.

É proibido jogar L0 na INBOX por conveniência.

## TAB-ADD-005 - Reorder parcial

Para L1, calcular o menor subgrafo seguro:

- candidato;
- predecessores necessários;
- dependentes downstream que podem mudar de posição;
- peers no mesmo nível topológico cujo ranking relativo pode ser alterado.

Reordenar somente esse conjunto, preservando o restante.

Critério de promoção para full reorder:

- subgrafo afetado excede limite configurado de proporção da tabela;
- mudança atinge mais de um macrogrupo/épico;
- nova fundação altera múltiplas ondas;
- ranking não pode ser decidido sem recalcular muitos peers.

O limite numérico deve ser configurável e validado com corpus real. Não inventar uma porcentagem rígida sem medição.

## TAB-ADD-006 - Full reorder

Para L2:

1. recalcular grafo completo;
2. validar ciclos e IDs;
3. topological sort;
4. WSJF somente dentro de níveis executáveis;
5. ondas;
6. preservar IDs/status/estado auditado;
7. não renumerar itens existentes;
8. gerar resumo objetivo das mudanças de ordem.

## TAB-ADD-007 - Decisão do líder

Se o novo pedido exigir decisão de alto valor:

- registrar candidato como `NEEDS_LEADER_DECISION`;
- apresentar 2 a 3 opções e trade-offs;
- após a decisão, executar o intake imediatamente;
- não deixar a decisão aprovada estacionada na INBOX.

## Gate ADD-2

- [ ] todo candidato classificável entra no TODO na mesma operação;
- [ ] local não dispara reorder global;
- [ ] estrutural não espera uma lembrança futura;
- [ ] exatamente um destino final;
- [ ] journal órfão é recuperável após crash;
- [ ] deduplicação idempotente;
- [ ] topologia sempre válida;
- [ ] regiões não afetadas permanecem estáveis no scoped reorder.

---

# Fase 3 - WSJF/SAFe coerente e proporcional

**Planejamento:** **[Opus] 5 ou mais recente**.  
**Implementação:** **[Sonnet] 5 ou mais recente**.  
**Revisão de matemática/algoritmo:** **[Opus] 5 ou mais recente**.

## TAB-WSJF-001 - Corrigir dupla régua

No perfil da casa quando SAFe estiver realmente aplicável, usar a régua canônica do vault:

`1, 2, 3, 5, 8, 13, 20`

para:

- Valor de Negócio;
- Criticidade Temporal;
- Redução de Risco / Habilitação;
- Job Size.

Calcular:

```text
CoD = Valor + Criticidade Temporal + Redução de Risco/Habilitação
WSJF = CoD / Job Size
```

O core distribuível pode permitir outra estratégia/scorer configurável, mas não deve ter uma tabela 1-20 fixa contradizendo a convenção da casa.

## TAB-WSJF-002 - Não aplicar SAFe onde não cabe

A norma global já diz que SAFe completo não deve ser aplicado a time único/estrutura pequena sem escala real.

Portanto:

- early / tabela pequena: scoring qualitativo ou local simplificado;
- scale/bigtech real: tabela WSJF formal;
- nunca mobilizar cinco agentes apenas para posicionar um typo ou fix trivial.

O gate anti-over-engineering de Cósimo continua válido.

## TAB-WSJF-003 - Dependência antes de WSJF

Exemplo obrigatório em teste:

```text
A: WSJF 4, sem prereq
B: WSJF 20, depende de A
```

Resultado obrigatório:

```text
A antes de B
```

WSJF não pode furar topologia.

## TAB-WSJF-004 - Scoring de novo item sem repriorizar o universo

Para integração local, avaliar:

- candidato;
- peers do mesmo nível topológico;
- itens diretamente afetados.

Não recalcular todos os itens se o ranking global não puder mudar.

Para tabela SAFe que já materializa scoring, reutilizar o último scoring válido dos peers e recalcular somente o necessário, marcando scoring stale quando input material tiver mudado.

## TAB-WSJF-005 - Estabilidade contra priority thrashing

Dentro de um mesmo nível topológico, o algoritmo deve ser **estável**:

- empate de score preserva a ordem relativa anterior;
- scores considerados comparáveis preservam a ordem relativa anterior, salvo novo fato material;
- diferença pequena não deve causar churn repetitivo entre duas linhas a cada intake;
- o limiar de “comparável” deve ser definido/testado no perfil aplicável, não inventado ad hoc por execução;
- mudança de dependência sempre pode mover item mesmo com score semelhante.

Se não houver score persistido para itens antigos, o intake local deve comparar apenas o candidato e peers necessários e usar a ordem existente como tie-breaker.

## TAB-WSJF-006 - Explicabilidade de movimento

Toda operação que alterar a ordem de item existente deve produzir um resumo verificável:

```text
ITEM X: W4 -> W2
causa: prerequisito Y concluido + WSJF 13.0 > peers executaveis
input_material_que_mudou: <fato>
```

Para full reorder em contexto SAFe, atualizar também a tabela de scoring exigida pela norma do vault. Para early, uma justificativa qualitativa curta basta.

É proibido reportar apenas “reordenado por WSJF” sem mostrar os inputs que justificaram os movimentos materiais.

## TAB-WSJF-007 - Criticidade factual, não retórica do remetente

Bus comum:

- ignorar auto-classificação do remetente;
- usar data factual, bloqueio técnico comprovado, risco e uso real;
- projeto receptor calcula CoD.

A origem do Gus segue o protocolo especial existente e deve ser tratada como regra de domínio da casa, não do core.

## Gate WSJF-3

- [ ] uma única régua da casa;
- [ ] SAFe scale-aware;
- [ ] topologia vence score;
- [ ] score local não causa churn global;
- [ ] remetente comum não controla prioridade;
- [ ] empates/scores comparáveis usam ordenação estável;
- [ ] movimentos materiais têm causa reproduzível.

---

# Fase 4 - Redefinir a INBOX como exception queue

**Implementação:** **[Sonnet] 5 ou mais recente**.  
**Verificação de fluxo:** **[Opus] 5 ou mais recente**.

## TAB-INBOX-001 - Migrar a INBOX existente

Antes de apagar ou renomear qualquer coisa:

1. ler todos os itens atuais;
2. classificar cada um pelo novo pipeline;
3. integrar os classificáveis;
4. manter somente os realmente bloqueados;
5. acrescentar metadata de triagem aos remanescentes;
6. provar que `n_antes == integrados + remanescentes + duplicatas_explicitamente_fundidas`.

Nenhum item some.

## TAB-INBOX-002 - Circuit breaker

Tamanho não é o gatilho primário, mas é defesa secundária.

Default inicial recomendado para o perfil da casa, sujeito a teste:

- `INBOX >= 3`, ou
- item com idade >24h, ou
- item sobrevivendo a 2 ciclos de `/tab_pendencias`,

gera `TRIAGE_REQUIRED`.

O sinal não roda WSJF sozinho. Ele exige que a thread principal execute a triagem agentiva no próximo ponto seguro.

## TAB-INBOX-003 - Invariante mais forte que o limite

Independentemente do threshold:

```text
classifiable_inbox_count == 0
```

após qualquer execução de `--add`, `--reorder` ou `--drain`.

Se o agente consegue classificar um item, mantê-lo na INBOX é bug.

## TAB-INBOX-004 - Novo `--drain`

Adicionar operação explícita de triagem residual:

```text
/tab_pendencias --drain
```

Ela:

1. lê INBOX residual;
2. tenta resolver contexto com o estado atual;
3. integra o que agora ficou classificável;
4. mantém somente bloqueios reais;
5. atualiza metadata/idade;
6. não força reorder global se itens forem locais.

`--reorder` deixa de ser o único mecanismo de dreno.

## Gate INBOX-4

- [ ] INBOX não é caminho normal;
- [ ] limite numérico é fallback, não lógica principal;
- [ ] itens classificáveis não sobrevivem;
- [ ] backlog residual tem motivo e idade;
- [ ] migração não perde nenhuma descoberta.

---

# Fase 5 - Concorrência, worktrees e sessões paralelas

**Arquitetura local:** **[Opus] 5 ou mais recente**.  
**Implementação:** **[Sonnet] 5 ou mais recente**.  
**Partes de transação/locking difíceis:** **[Opus] 5 ou mais recente**.

A INBOX original também reduzia conflitos entre worktrees. Eliminar o uso normal dela sem resolver concorrência seria regressão.

## TAB-CONC-001 - Um único escritor lógico do TODO por orquestração

Dentro de uma execução multi-agent:

- subagente não edita `TODO.md` para registrar descoberta;
- subagente retorna descoberta estruturada ao `main`;
- `main` invoca o pipeline de intake;
- apenas `main` altera a tabela canônica.

Formato de handoff recomendado:

```text
DISCOVERED_WORK
source_item: <ID atual>
description: <trabalho descoberto>
evidence: <arquivo:linha/teste/log>
known_dependencies: <IDs ou unknown>
blast_radius: <local/component/system/unknown>
```

O subagente não atribui WSJF final.

## TAB-CONC-002 - Sessões independentes concorrentes

Quando não existe um orquestrador comum e duas sessões podem descobrir itens em branches/worktrees diferentes, usar arquivo-por-descoberta como journal seguro:

```text
inbox/YYYYMMDD-HHMMSS-<session>-<slug>.md
```

Isso continua sendo fallback de concorrência, não backlog normal.

Cada arquivo deve conter metadata suficiente para triagem automática posterior.

## TAB-CONC-003 - Próxima sessão principal faz auto-triage

`SessionStart` detecta `inbox/` residual e injeta contexto `TRIAGE_REQUIRED` quando critérios forem atendidos.

A política global deve dizer ao `main`:

> ao receber `TRIAGE_REQUIRED`, executar `/tab_pendencias --drain` no próximo ponto seguro sem depender de o líder lembrar.

Isso preserva event-driven e evita daemon LLM contínuo.

## TAB-CONC-004 - Escrita segura

Para componentes determinísticos que editarem `TODO.md`:

- recusar working tree suja quando necessário;
- escrever em temporário;
- validar parse/invariantes;
- `os.replace` atômico quando aplicável;
- considerar lock por arquivo/OS se houver dois writers locais possíveis;
- testar TOCTOU e concorrência real.

Não reutilizar automaticamente o desenho de `todo_fix.py`; medir as necessidades do intake.

## Gate CONC-5

- [ ] workers não disputam TODO;
- [ ] sessões independentes não perdem descoberta;
- [ ] residual concorrente é drenado sem memória humana;
- [ ] escrita é idempotente ou falha visivelmente;
- [ ] corrida é testada, não apenas documentada.

---

# Fase 6 - Redesenhar o hook de frescor

**Planejamento:** **[Opus] 5 ou mais recente**.  
**Implementação:** **[Sonnet] 5 ou mais recente**.

## TAB-HOOK-001 - Continuar determinístico

O hook não chama modelo e não calcula WSJF. Ele mede fatos:

- TODO ausente;
- commits/dias sem sincronização;
- INBOX residual count;
- idade do item residual mais antigo;
- presença de `inbox/` concorrente;
- itens presos em `🔍` se barato calcular.

## TAB-HOOK-002 - Sinais claros

Em vez de prosa genérica “considere reordenar”, emitir categorias:

```text
TAB_STATUS_SYNC_RECOMMENDED
TAB_TRIAGE_REQUIRED
TAB_TODO_CREATE_REQUIRED
TAB_VERIFICATION_AGING
```

A mensagem humana pode acompanhar, mas a thread principal deve conseguir distinguir ação mecânica de ação agentiva.

## TAB-HOOK-003 - Nunca full reorder por relógio

Tempo/idade pode exigir **triagem**, não reordenação completa automática.

A decisão de reorder surge do conteúdo/impacto encontrado pela triagem.

## TAB-HOOK-004 - Eliminar duplicação de implementação

Preferência arquitetural:

- lógica genérica do hook no repo `tab_pendencias`;
- `claude-memory/settings.sanitized.json` aponta para a implementação do submódulo, ou usa adapter mínimo;
- não manter uma segunda cópia inteira de `tab_pendencias_reminder.py` no vault se o produto pode fornecê-la.

Se um adapter for necessário, ele deve conter wiring, não regra de negócio.

## Gate HOOK-6

- [ ] hook é local/offline;
- [ ] nenhum LLM em hook;
- [ ] sinal residual fecha o ciclo com política do main;
- [ ] nenhum reorder temporal cego;
- [ ] lógica não está duplicada repo/vault.

---

# Fase 7 - Integração com o vault e políticas globais

**Planejamento:** **[Opus] 5 ou mais recente**.  
**Implementação documental/config:** **[Sonnet] 5 ou mais recente**.

## TAB-VAULT-001 - Atualizar `CLAUDE.md`

Substituir regra antiga “trabalho novo vai para INBOX” por:

1. descoberta de worker -> handoff ao main;
2. main chama intake;
3. local -> TODO imediato;
4. estrutural -> reorder proporcional;
5. ambíguo -> INBOX residual;
6. `TRIAGE_REQUIRED` é ação obrigatória da thread principal, não lembrete ao humano.

## TAB-VAULT-002 - Reduzir duplicação em `docs/tabela-pendencias-frescor.md`

O doc global deve virar overlay da casa:

- explicar o racional e integração do vault;
- apontar norma genérica para `skills/tab_pendencias/references/...`;
- definir thresholds da casa;
- definir integração com agents e bus;
- não duplicar detalhes de parser/CLI que pertencem ao produto.

## TAB-VAULT-003 - Atualizar agentes

Agents de implementação devem parar de “registrar na INBOX” por conta própria.

Nova regra:

- registrar achado no retorno estruturado;
- citar item de origem;
- deixar prioridade para `main` + skill;
- não editar ranking do TODO.

Cósimo continua decidindo complexidade da orquestração. Cosmo continua coordenando execução quando necessário.

## TAB-VAULT-004 - Atualizar `settings.sanitized.json`

Garantir que bindings reais e sanitizados coincidam em estrutura, sem vazar segredos.

Adicionar testes/config check que detectem se o hook registrado aponta para arquivo inexistente.

## TAB-VAULT-005 - Recovery drill

Após alterações:

1. clone recursivo de `claude-memory` em `/var/tmp`;
2. restaurar settings a partir do sanitizado sem segredos reais;
3. rodar smoke do hook com stdin sintético;
4. invocar skill do submódulo;
5. provar que não busca arquivo antigo fora do repo;
6. provar que a versão restaurada tem a semântica nova.

## Gate VAULT-7

- [ ] nenhuma regra global ainda manda todo trabalho novo para INBOX;
- [ ] agents entregam discoveries ao main;
- [ ] submodule está atual;
- [ ] settings apontam para implementação existente;
- [ ] recovery drill funciona do zero.

---

# Fase 8 - Integração com o bus cross-project

**Planejamento:** **[Opus] 5 ou mais recente**.  
**Implementação:** **[Sonnet] 5 ou mais recente**.

## TAB-BUS-001 - Bus transporta fatos, não ranking

Ao receber mensagem comum:

1. ler pedido;
2. extrair necessidade, uso concreto, prazo factual e evidência;
3. não importar prioridade retórica do remetente;
4. gerar WorkCandidate;
5. executar `--add` no projeto receptor;
6. responder/arquivar conforme protocolo do bus.

## TAB-BUS-002 - Pedido recebido deve se tornar rastreável no mesmo ciclo

A regra do ecossistema é que pedido do consumidor vira item rastreável no projeto fornecedor. O redesign deve tornar isso mais forte:

> mensagem processada não pode ser arquivada como “agida” se o pedido que exige trabalho futuro não terminou em item do TODO, duplicata explicitamente ligada a item existente, decisão do líder ou INBOX residual com motivo.

## TAB-BUS-003 - Não misturar inbox do bus com INBOX do TODO

São conceitos diferentes:

- `gusworld_ia_autocomm/inbox/<slug>` = transporte de mensagens;
- `TODO.md ## INBOX` = exception queue de planejamento.

Nome igual não significa semântica igual. Documentar explicitamente.

## TAB-BUS-004 - Watcher do bus não é o anti-padrão de reorder contínuo

O `watch-inbox.sh` do bus pode continuar existindo. Ele observa **chegada de mensagem**, isto é, transporte/evento. Ele não recalcula prioridade nem reordena `TODO.md` periodicamente.

A proibição deste plano é contra vigilância LLM que reprioriza backlog sem input novo, não contra um watcher barato que detecta mensagem nova. Ao chegar mensagem, o evento gera candidato e só então o intake decide a ação proporcional.

## TAB-BUS-005 - Fluxo especial do Gus

Preservar a exceção de domínio existente. Não generalizar sua prioridade explícita para outros remetentes.

## Gate BUS-8

- [ ] mensagem comum não controla prioridade;
- [ ] pedido arquivado tem rastreabilidade;
- [ ] inbox do bus e INBOX de planejamento não são confundidas;
- [ ] exceções de domínio ficam fora do core genérico.

---

# Fase 9 - Hub agregador e múltiplos projetos

**Planejamento:** **[Opus] 5 ou mais recente**.  
**Implementação se houver gerador existente:** **[Sonnet] 5 ou mais recente**.

## TAB-HUB-001 - Hub continua read-only derivado

Nunca inserir candidato diretamente no hub.

Fluxo:

```text
pedido -> TODO do projeto fonte -> regeneração do hub -> view atualizada
```

## TAB-HUB-002 - Regeneração após mudança

Descobrir o mecanismo real atual de geração do hub antes de implementar qualquer hook.

Se existir gerador determinístico:

- rodar após mudanças relevantes em TODO de projeto;
- ou marcar view stale de forma objetiva.

Se não existir, registrar como item separado. Não inventar um segundo backlog manual.

## Gate HUB-9

- [ ] hub nunca vira fonte concorrente;
- [ ] nenhuma INBOX no hub;
- [ ] freshness da view tem mecanismo mensurável.

---

# Fase 10 - Testes de contrato e regressão

**Implementação:** **[Sonnet] 5 ou mais recente**.  
**Revisão:** **[Opus] 5 ou mais recente**.  
**Auditoria final:** `AUD-EXTREME-01` por **[Fable] 5 ou mais recente**.

## TAB-TST-001 - Corpus sintético mínimo obrigatório

Criar cenários para:

1. item local sem prereq;
2. item local com prereq satisfeito;
3. item com WSJF alto mas prereq não concluído;
4. item estrutural que muda várias ondas;
5. item ambíguo;
6. duplicata textual;
7. duplicata semântica;
8. reabertura de item concluído;
9. item recebido do bus comum com “urgente” no texto;
10. item especial do fluxo Gus;
11. work item já em andamento;
12. bug crítico que exige preempção;
13. dois workers descobrindo o mesmo item;
14. duas sessões independentes;
15. TODO dirty;
16. cycle de dependência introduzido;
17. ID inexistente;
18. tabela legada de 8 colunas;
19. BOM/CRLF;
20. INBOX com 1 item ambíguo;
21. INBOX com 3 itens;
22. item residual >24h;
23. item residual sobrevivendo 2 triagens;
24. scoped reorder afetando somente um componente;
25. full reorder necessário;
26. hub agregador;
27. recuperação via submodule;
28. hook apontando para path inexistente;
29. clone sem vault;
30. perfil casa com SAFe.

## TAB-TST-002 - Propriedades

Testes devem afirmar:

```text
no_lost_work
crash_recovery_idempotent
exactly_one_terminal_state
no_duplicate_persistence
topology_valid
wip_stable_unless_preemption_valid
classifiable_inbox_count == 0
unaffected_rows_stable_on_scoped_reorder
sender_does_not_set_priority
recovery_gets_expected_version
```

## TAB-TST-003 - Contract snapshots reais

Usar snapshots anonimizados/locais conforme política atual do projeto para provar compatibilidade com TODOs grandes reais.

Não usar arquivo vivo como fixture de teste. Congelar snapshot imutável por SHA/hash e regenerar explicitamente.

## TAB-TST-004 - Mutation/adversarial tests

Mutar deliberadamente:

- comparador topológico;
- decisão LOCAL vs FULL;
- dedupe;
- threshold de INBOX;
- parser de metadata;
- regra sender-priority;
- atualização de submodule;
- path de hook.

A suíte deve pegar as mutações.

## TAB-TST-005 - Teste E2E de instalação

A receita publicada deve ser executada literalmente em repo descartável, como já se aprendeu com o incidente anterior.

Testar:

- clone direto da skill;
- instalação como submódulo de `claude-memory`;
- SessionStart hook;
- UserPromptSubmit hook;
- `--add`;
- `--drain`;
- `--reorder`;
- `--audit`;
- recovery clone.

## TAB-SEC-001 - Fronteira pública x privada

O redesign cruza informação do vault e do bus, mas `petrinhu/tab_pendencias` é produto distribuível. Portanto:

- nenhum corpo real de mensagem do bus privado entra em fixture versionada;
- nenhum nome de projeto privado, path absoluto da máquina, segredo/token ou dado pessoal desnecessário entra no repo público;
- contract snapshots reais continuam locais/anonimizados conforme a política existente;
- exemplos publicados usam `consumer-a`, `consumer-b`, `project-x` ou corpus sintético;
- o guard anti-vazamento existente deve ser ampliado para novos arquivos/metadata de intake;
- logs de teste devem mascarar conteúdo sensível;
- o write-ahead journal local deve rejeitar/mascarar segredo conhecido e preferir referência à origem.

O agente deve varrer **conteúdo e path**, não apenas nomes de arquivo, antes da publicação.

## TAB-SEC-002 - Licença e headers

Toda nova implementação incorporada a `tab_pendencias` deve seguir a licença vigente medida no repo na época da execução. No snapshot desta auditoria, o projeto declara GPL-3.0-or-later. Não copiar código de hooks locais sem reconciliar licença/proveniência.

## TAB-COMPAT-001 - Compatibilidade e degradação

Provar explicitamente:

- tabelas de 8 e 9 colunas continuam legíveis;
- INBOX antiga continua drenável durante a janela de migração;
- clone sem vault continua tendo core utilizável;
- ausência de agents degrada para fluxo mais simples, nunca perda silenciosa;
- core mecânico continua offline quando a operação não exige julgamento LLM;
- Windows e Linux preservam encoding/EOL;
- nenhum novo requisito de rede é introduzido para `audit`, `health`, `sync` e parsing.

## Gate TST-10

- [ ] propriedades passam;
- [ ] corpus real não regride;
- [ ] mutation testing pega falhas críticas;
- [ ] instalação real funciona;
- [ ] concorrência testada;
- [ ] submodule/recovery testados.
- [ ] guard anti-vazamento cobre novos artefatos de intake;
- [ ] licença/proveniência de novo código conferidas;
- [ ] modos offline/sem-vault e compatibilidade 8/9 colunas testados.

---

# Fase 11 - Migração e cutover

**Planejamento:** **[Opus] 5 ou mais recente**.  
**Execução:** **[Sonnet] 5 ou mais recente**.  
**Gate:** `main` em **[Opus] 5 ou mais recente**.

## TAB-CUT-001 - Compatibilidade inicial

Durante uma janela curta:

- aceitar formato antigo de INBOX;
- `--drain` migra linhas antigas;
- emitir aviso de semântica antiga quando detectada;
- não exigir edição manual de todos os TODOs existentes.

## TAB-CUT-002 - Dogfood primeiro no próprio `tab_pendencias`

O produto usa sua nova lógica no próprio `TODO.md`.

Critério:

- os 2 itens residuais atuais são classificados;
- nenhum classificável permanece na INBOX;
- novo achado durante o dogfood passa pelo pipeline novo.

## TAB-CUT-003 - Canary no vault

Escolher poucos projetos com perfis diferentes:

- projeto pequeno;
- projeto com TODO grande;
- projeto com bus ativo;
- projeto com múltiplas worktrees/sessões, se houver.

Não migrar todos de uma vez.

## TAB-CUT-004 - Métricas antes/depois

Medir por projeto:

- `inbox_total`;
- `inbox_classificable`;
- `oldest_inbox_age`;
- `discoveries_integrated_same_cycle_pct`;
- `full_reorders_per_10_discoveries`;
- `scoped_reorders_per_10_discoveries`;
- conflitos de merge em TODO;
- tempo médio descoberta -> item priorizado;
- duplicatas criadas;
- itens perdidos = deve ser 0.

## TAB-CUT-005 - Rollback

Se novo intake corromper ordem ou perder trabalho:

1. parar escrita automática;
2. preservar journal/inbox files;
3. voltar temporariamente para captura conservadora;
4. nunca apagar candidatos já coletados;
5. corrigir causa e repetir canary.

Rollback não deve restaurar permanentemente a dependência de memória humana; é modo de contenção.

## Gate CUT-11

- [ ] dogfood verde;
- [ ] canaries verdes;
- [ ] 0 work lost;
- [ ] merge conflicts não pioraram de forma material;
- [ ] same-cycle integration aumentou;
- [ ] full reorder não virou rotina para pedido trivial.

---

# Fase 12 - Publicação do repo GitHub e atualização do `claude-memory`

Esta fase é explicitamente obrigatória por decisão do líder.

**Executor principal:** `main` em **[Opus] 5 ou mais recente**.  
**Preparação de docs/changelog:** **[Sonnet] 5 ou mais recente**.

## TAB-REL-001 - Estado remoto antes do push

Medir:

```bash
git fetch --all --prune
git status --short
git log --oneline --decorate -n 20
git rev-parse HEAD
git rev-parse origin/main
```

Nunca presumir que o remoto continua no SHA medido neste documento.

## TAB-REL-002 - Publicar `tab_pendencias`

Quando autorizado:

1. push da branch/revisão aprovada;
2. verificar SHA remoto por `git ls-remote` ou API;
3. observar CI real;
4. não confiar apenas em `git push` retornando 0;
5. produzir release/changelog se SemVer exigir;
6. testar instalação usando o remoto publicado, não checkout local.

## TAB-REL-003 - Atualizar submódulo

No `claude-memory`:

1. `git submodule update --remote` somente se política permitir e ref estiver clara; preferir pin explícito no SHA validado;
2. conferir `git diff --submodule`;
3. atualizar docs/bindings;
4. commit separado do bump;
5. rodar recovery drill.

## TAB-REL-004 - Prova de que o GitHub é fonte recuperável

Um computador novo deve conseguir:

```text
clone claude-memory --recursive
 -> obter tab_pendencias correta
 -> restaurar bindings
 -> executar hook
 -> executar skill
 -> processar um candidato
```

Sem copiar manualmente um arquivo de uma instalação antiga.

## Gate REL-12

- [ ] `tab_pendencias` remoto contém toda evolução viva necessária;
- [ ] CI remoto verde;
- [ ] submodule aponta para o SHA certo;
- [ ] recovery remoto funciona;
- [ ] instalação viva não possui patch secreto indispensável fora do GitHub.

---

# Fase 13 - Auditoria adversarial final

Executar `AUD-EXTREME-01` com **[Fable] 5 ou mais recente** em contexto limpo.

O auditor deve tentar responder negativamente às seguintes perguntas:

1. É possível criar trabalho novo e ele ficar para sempre na INBOX sem sinal obrigatório?
2. É possível um item classificável permanecer na INBOX depois de `--add`/`--drain`?
3. É possível um item desaparecer entre inbox concorrente e TODO?
4. É possível duas sessões gerarem duplicata silenciosa?
5. É possível WSJF colocar dependente antes do prerequisito?
6. É possível pedido do bus influenciar ranking por retórica do remetente?
7. É possível full reorder acontecer por simples passagem do tempo?
8. É possível um item em andamento ser preemptado por feature pequena?
9. É possível o repo GitHub ficar atrás da instalação viva sem que recovery test acuse?
10. É possível `claude-memory` fixar submódulo velho e ainda passar todos os gates?
11. É possível hook global e produto terem regras diferentes de frescor?
12. É possível o hub virar fonte concorrente?
13. É possível o teste ficar verde porque uma fixture viva mudou silenciosamente?
14. É possível a migração apagar uma linha antiga da INBOX?
15. É possível um agent declarar “integrado” sem o `main` repetir a prova?

Qualquer “sim” mantém a campanha aberta.

---

# Definição global de pronto

A melhoria completa só pode ser declarada concluída quando todos estes critérios forem verdadeiros simultaneamente:

## Fonte de verdade

- [ ] repo `petrinhu/tab_pendencias` medido contra instalação viva;
- [ ] toda diferença útil absorvida ou explicitamente rejeitada;
- [ ] produto genérico existe em um único lugar;
- [ ] `claude-memory` contém integração, não fork invisível;
- [ ] submodule aponta para release/SHA correto;
- [ ] clone recursivo reproduz a instalação funcional.

## Intake

- [ ] pedido novo classificável entra imediatamente no TODO;
- [ ] local -> integração local;
- [ ] componente -> scoped reorder;
- [ ] estrutural -> full reorder ou decisão do líder;
- [ ] ambíguo -> INBOX residual com motivo;
- [ ] exatamente um destino por descoberta.

## INBOX

- [ ] deixou de ser fila normal;
- [ ] `classifiable_inbox_count == 0` após operações de intake;
- [ ] threshold/aging dispara triagem obrigatória;
- [ ] líder não precisa lembrar manualmente de drenar;
- [ ] concorrência continua sem perda.

## Prioridade

- [ ] dependência topológica sempre vence;
- [ ] WSJF é proporcional ao porte;
- [ ] perfil SAFe da casa usa uma régua coerente;
- [ ] WIP é estável;
- [ ] bus comum não injeta prioridade externa.

## Qualidade

- [ ] tests completos verdes;
- [ ] testes de contrato reais/snapshots verdes;
- [ ] mutation/adversarial tests pegam violações;
- [ ] E2E de instalação verde;
- [ ] auditoria final por **[Fable] 5 ou mais recente** não encontra caminho de perda/liveness quebrada.

---

# Métricas permanentes pós-migração

O projeto deve acompanhar, pelo menos:

| Métrica | Meta |
|---|---|
| itens classificáveis na INBOX | **0** |
| trabalho perdido | **0** |
| descobertas integradas no mesmo ciclo | tendência para **~100% das classificáveis** |
| idade máxima de INBOX sem bloqueio explícito | **0** |
| full reorder causado por pedido trivial | **0** |
| violações topológicas | **0** |
| duplicatas silenciosas | **0** |
| recovery clone usando skill velha | **0** |
| lógica genérica duplicada repo/vault | **0** |

A taxa de full reorder não deve ser minimizada artificialmente. O objetivo é evitar replanejamento desnecessário, não impedir full reorder quando uma mudança estrutural realmente o exige.

---

# Regras anti-regressão de processo

1. **Toda feature nova da própria `tab_pendencias` deve usar a própria `tab_pendencias` redesenhada.** Dogfooding obrigatório.
2. **Nenhuma mudança normativa apenas no vault.** Se é comportamento genérico, entra primeiro no repo do produto.
3. **Nenhuma mudança normativa apenas no repo sem atualizar o binding do vault quando necessário.**
4. **Toda receita de instalação é testada literalmente.**
5. **Todo bump de submodule exige recovery smoke.**
6. **Toda descoberta de divergência repo-vivo vira falha de distribuição, não “ajuste local”.**
7. **Todo hook é testado via evento real/sintético equivalente ao Claude Code.**
8. **Todo item novo precisa terminar em estado persistido e rastreável.**
9. **Nenhum agent worker decide prioridade global sozinho.**
10. **Nenhum relatório de agent substitui a medição do main.**

---

# Ordem operacional resumida

```text
0. MEDIR E RECONCILIAR REPO x INSTALAÇÃO VIVA x CLAUDE-MEMORY
   |
   v
1. SOT-EXTREME-01: fonte de verdade/distribuição
   |
   v
2. ATUALIZAR O REPO CANÔNICO COM QUALQUER EVOLUÇÃO VIVA FALTANTE
   |
   v
3. ARCH-EXTREME-01: arquitetura de intake
   |
   v
4. implementar --add + classificação de impacto
   |
   v
5. implementar scoped/full reorder proporcional
   |
   v
6. corrigir WSJF/SAFe
   |
   v
7. transformar INBOX em exception queue + --drain
   |
   v
8. resolver concorrência/worktrees
   |
   v
9. redesenhar hook determinístico
   |
   v
10. atualizar vault/agents/settings
   |
   v
11. integrar bus + hub
   |
   v
12. testes, mutation, E2E, dogfood, canary
   |
   v
13. publicar tab_pendencias
   |
   v
14. bump claude-memory + recovery drill
   |
   v
15. AUD-EXTREME-01 auditoria adversarial
```

---

# Prompts-base para delegação

## Prompt de implementador

> Você é o implementador desta fatia do plano da `tab_pendencias`. Modelo: **[Sonnet] 5 ou mais recente**. Leia o item e seus gates. Não altere arquitetura fora do escopo. Não edite `TODO.md` para registrar descobertas novas; devolva-as no bloco `DISCOVERED_WORK`. Escreva/ajuste testes antes ou junto do código conforme TDD. Execute os testes que cobrem sua fatia. Não faça push, tag ou release. Ao terminar, informe arquivos alterados, comandos executados, resultados e qualquer descoberta. Não declare a etapa global concluída.

## Prompt de planejador

> Você é o planejador desta fatia. Modelo: **[Opus] 5 ou mais recente**. Transforme o item em contrato de implementação estreito: inputs, outputs, invariantes, arquivos prováveis, riscos, testes, DoD e forbidden shortcuts. Não implemente se a tarefa for de planejamento. Dependência topológica é anterior a preferência. Diferencie fato medido de hipótese.

## Prompt de arquiteto extremo

> Você está executando um trabalho reservado a **[Fable] 5 ou mais recente**. Não escreva código cotidiano. Produza arquitetura verificável, máquina de estados, invariantes, failure modes, migration path, gates e critérios de falsificação. Assuma que as implementações existentes podem estar erradas. Reduza ambiguidades para que implementadores de **[Sonnet] 5 ou mais recente** possam executar fatias estreitas sem reinterpretar decisões fundamentais.

## Prompt de auditor adversarial

> Você é um auditor novo em **[Fable] 5 ou mais recente**. Não confie em relatórios dos agentes anteriores. Reexecute testes e medições, procure caminhos de perda de trabalho, starvation de INBOX, violação topológica, duplicação de prioridade, divergência repo-vault e recovery quebrado. Para cada claim, marque `confirmado`, `refutado` ou `alegado/não verificado`, com evidência reproduzível.

---

# Evidências-base que o executor deve reler

Antes da implementação, reler no estado real da época de execução:

## `petrinhu/tab_pendencias`

- `SKILL.md`
- `references/frescor-da-tabela.md`
- `TODO.md`
- `CHANGELOG.md`
- `docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`
- `tools/todo_lib.py`
- `tools/todo_sync.py`
- `tools/todo_health.py`
- `tools/todo_freshness.py`
- `tools/todo_audit.py`
- `tools/todo_fix.py`
- `tools/README.md`
- `.github/workflows/ci.yml`
- testes relacionados a INBOX, status, parser, hook e instalação

## `petrinhu/claude-memory`

- `.gitmodules`
- `CLAUDE.md`
- `AGENTS.md`
- `docs/tabela-pendencias-frescor.md`
- `docs/agile-methodology.md`
- `docs/vault.md`
- `hooks/tab_pendencias_reminder.py`
- `settings.sanitized.json`
- agents `cosimo-chief-of-staff` e `cosmo-coo`

## Bus/ecossistema

- `petrinhu/gusworld_ia_autocomm/PROTOCOL.md`
- TODOs dos projetos canary escolhidos
- relatório de ecossistema de 2026-08-16 apenas como contexto histórico, nunca como substituto de medição atual.

---

# Registro das 7 revisões finais

Antes de liberar este artefato, foram executados sete ticks de revisão com a pergunta fixa **“devo acrescentar mais algum detalhe aqui?”**. O registro abaixo mostra somente o resultado verificável de cada passe, não raciocínio privado.

| Tick | Foco | Lacuna encontrada | Alteração incorporada |
|---|---|---|---|
| 1 | escopo e integridade | risco de a campanha desviar para Issues/Projects, daemon LLM ou SAFe indiscriminado | seção de não-objetivos e separação explícita entre suspeita e fato medido |
| 2 | fonte de verdade | submódulo já está atrás e não havia detector de nova defasagem | contrato de propagação de release + drift detector local/CI warning-only |
| 3 | liveness/crash | candidato poderia ser perdido entre entendimento e persistência | write-ahead journal local + recovery idempotente em SessionStart |
| 4 | WSJF/WIP | reorder parcial ainda poderia gerar priority thrashing | stable sort para score comparável + explicabilidade de movimentos |
| 5 | vault/concorrência | auto-snapshot de `claude-memory` pode publicar estado intermediário | janela de manutenção do timer + distinção watcher do bus vs reorder contínuo |
| 6 | segurança/compatibilidade | integração com vault/bus aumenta risco de vazamento no repo público | fronteira pública/privada, guards, licença, offline e compatibilidade 8/9 colunas |
| 7 | consistência final | nomenclatura, gates e obrigação de atualizar o GitHub precisavam ser checados em conjunto | varredura final de termos, estrutura I/II/III, repo-update, submodule, DoD e referências cruzadas |

Resultado do tick 7: nenhum nome de modelo aparece como recomendação fora do formato exigido pelo líder; referências a comportamento antigo de INBOX aparecem apenas em descrição histórica/alvo de substituição; atualização do repo GitHub e do submódulo está presente como fase, gate e Definition of Done.

---

# Nota final de arquitetura

A solução não é “abolir fila” e nem “reordenar tudo a cada prompt”.

A solução é fechar o ciclo:

> **capturar barato, classificar imediatamente quando possível, replanejar proporcionalmente ao impacto e deixar em fila apenas aquilo que realmente não pode ser decidido agora.**

O antigo desenho otimizou o custo da captura e aceitou dívida de liveness. O novo desenho deve preservar a captura segura, mas remover a dependência de memória humana para transformar descoberta em trabalho priorizado.

