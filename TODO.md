# TODO -- tab_pendencias v2 (skill + toolkit distribuíveis)

> Tabela canônica de pendências. **A ordem das linhas É a ordem de execução recomendada**;
> a coluna `Onda` marca os passos de igual valor que podem rodar em paralelo.
> Fonte dos fatos: `prompt_inicial.md`. Decisões fechadas: `decisoes_lider.md`.
> Manuais: `TESTES.md`, `AUDITORIAS.md`. Porte: **early / Pipeline-Lean**, kanban, **WIP = 1 onda**.
>
> **Dogfooding**: este arquivo usa a própria skill que o projeto constrói (schema de 9 colunas,
> INBOX, ondas de teste/auditoria downstream, item de Wiki como última onda pós-tag).

| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| W0-DEC | — | Governança | Kickoff `/bigtech`: porte early classificado por Cósimo, mapa de ativação aprovado, e as 8 decisões **D-1..D-8** resolvidas pelo líder (registro em `decisoes_lider.md`). Gate anti-OE do `--create` decidido por Cósimo: **thread direta** + 1 passe de ADR. | Alta | — | Baixa | ✅ Concluído | — |
| ADR-1 | W1 | Arquitetura | ADR da fronteira **núcleo genérico × convenções da casa** (nenhum check do núcleo pode depender do perfil "casa"), do contrato do parser (round-trip byte-exato, compat 8/9 colunas) e dos limites de `--audit`/`--fix`. Executor: `software-architect`. É o risco arquitetural real do projeto e precisa existir ANTES dos consertos, não como auditoria tardia. | Alta | — | Média | ⏳ Pendente | — |
| SCAF-1 | W1 | Scaffold | Clonar o repo em `Projects/tab_pendencias/`, montar o layout monorepo da D-4 (`tools/`, `tools/hooks/`, `tests/`, `references/`) preservando os 21 commits, **e relicenciar o repo inteiro para GPL-3.0-or-later** (D-3): trocar `LICENSE`, cabeçalhos dos fontes, purgar menção residual à PolyForm no README/SKILL.md. Publicação de licença é irreversível na prática. | Alta | — | Média | 🔍 Pendente verificação | — |
| ABS-1 | W2 | Scaffold | Absorver de `~/.claude/githooks/`: os 4 scripts (`todo_lib`, `todo_sync`, `todo_health`, `todo_freshness`) para `tools/`, e `_chain.sh` + os 7 shims POSIX para `tools/hooks/`; mover a suíte pytest (**41 testes**) para `tests/` e deixá-la 100% verde no novo layout. Atômico: absorver os `.py` sem os testes deixa o repo vermelho. | Alta | SCAF-1 | Média | ⏳ Pendente | — |
| DOC-FRESH | W2 | Docs | Internalizar em `references/` a parte NORMATIVA das regras de frescor (D-2), hoje só em `~/.claude/docs/tabela-pendencias-frescor.md`; o vault fica com o histórico/racional. Sem isto, quem clona não recebe a norma que a skill exige. | Média | SCAF-1 | Baixa | ⏳ Pendente | — |
| CONTR-1 | W3 | Testes | Testes de **contrato** com as fixtures reais (consumidor A **116** itens, consumidor B **215**), mantidas apenas LOCALMENTE e nunca commitadas sem anonimização. Vem ANTES dos consertos de propósito: é a rede de segurança que prova que nenhuma mudança quebra os consumidores vivos. | Alta | ABS-1 | Baixa | ⏳ Pendente | — |
| CORP-0 | W3 | Testes | Corpus **sintético** de aceitação (AC-0): outra língua, outro esquema de ID (`#NN`, `XYZ.9.9`), outra estrutura de seções; property-based sobre IDs gerados. Cap anti-OE do Cósimo: **no máximo 2 alfabetos e 2 formatos de ID**. É o que prova que a skill é agnóstica a projeto. | Alta | ABS-1 | Média | ⏳ Pendente | — |
| CI-1 | W3 | CI | Workflow único do GitHub Actions com jobs: pytest em **matrix ubuntu + windows** (a promessa de Git-for-Windows não se sustenta só com ubuntu), `shellcheck` + smoke dos shims, lint de Markdown, `gitleaks` (secrets), guard "**nenhum import fora da stdlib**" e guard **anti-vazamento de fixture real** (repo público). Actions pinadas por SHA. | Alta | ABS-1 | Média | ⏳ Pendente | — |
| BUG-5 | W4 | Consertos | Classificação de status por **emoji-prefixo** (D-1), com fallback word-boundary só para tabela legada sem emoji + aviso no `--audit`. Hoje `is_awaiting_verification` casa "VERIFICADO" e `is_done` casa "inconclusivo" (`todo_lib.py:169-174`); cobre também SUB-1 (`"🔴 Bloqueado (dependente de X)"` → pendente) e SUB-2 (`"⏳ Pendente (verificar disponibilidade)"` → bloqueia flip legítimo). Afeta todos os repos do líder. | Alta | ABS-1, ADR-1, CONTR-1 | Média | ⏳ Pendente | — |
| CLI-1 | W4 | Consertos | Contrato de CLI da D-6 nos 3 scripts: `argparse` + `--help`; exit `0`=ok, `1`=erro de execução, `2`=achados; **flag desconhecida = erro** (hoje `--aply` é ignorado em silêncio e `todo_sync.main` devolve 0 até quando nem é repo git). | Média | ABS-1 | Média | ⏳ Pendente | — |
| GAP-1 | W4 | Testes | Suíte do `todo_health.py` do zero -- é o único módulo hoje sem nenhum teste. | Média | ABS-1 | Baixa | ⏳ Pendente | — |
| GAP-2 | W4 | Testes | Teste e2e de `todo_freshness.main()` (o caminho real, com `diff-tree`), hoje sem cobertura nenhuma. | Média | ABS-1 | Média | ⏳ Pendente | — |
| SPRAWL-1 | W5 | Consertos | Fim explícito da tabela canônica: **encerrar no próximo heading markdown** (D-6). Hoje (`todo_lib.py:130`) a tabela engole linhas de 9 células centenas de linhas abaixo, atravessando seções inteiras. Muda o contrato de parse: exige `CONTR-1` verde antes e depois. | Alta | ABS-1, ADR-1, CONTR-1 | Média | ⏳ Pendente | — |
| BUG-1' | W5 | Consertos | ID duplicado passa em silêncio: `parse_status_map` deixa a última linha vencer (`todo_lib.py:144-147`) e `by_id` idem (`todo_sync.py:122`); nenhum teste detecta. A instância foi removida do dado, a CLASSE segue aberta. | Alta | ABS-1 | Baixa | ⏳ Pendente | — |
| PRED-FIX | W5 | Consertos | Três predicados de uma linha, um commit citando os 3 IDs: **CIT-1** `cited_ids("fechei V-12.")` → `[]` (ponto final cai no lookahead, `todo_lib.py:177-185`); **TCH-1** `touched_code(["src/inbox/parser.py"])` → False (substring `/inbox/` em path de código, `todo_lib.py:49-62`) -- restringir ao `inbox/` do topo; **HDR-1** `_is_header` dispara com qualquer célula contendo "status" (`todo_lib.py:100-102`). | Alta | ABS-1 | Baixa | ⏳ Pendente | — |
| ENC-1 | W5 | Consertos | Unificar a política de exceção/encoding: `todo_freshness.main` engole QUALQUER exceção de leitura (`todo_freshness.py:81`) enquanto `todo_sync`/`todo_health` crasham cru em `UnicodeDecodeError`; logar o que foi engolido (flag verbose). Não é polimento: **CRLF/BOM é o Windows do claim cross-platform**. | Alta | ABS-1 | Baixa | ⏳ Pendente | — |
| AUDIT-ENG | W6 | Audit | `tools/todo_audit.py`: motor dos checks + CLI própria (D-6). Relatório numerado por check com severidade CRÍTICO/IMPORTANTE/COSMÉTICO, evidência `linha:`, marcação **[auto-fixável]** vs **[julgamento]**, saída legível no chat + arquivo opcional em scratchpad (nunca no repo), e a regra **"no silent caps"**: todo descarte ou limitação do próprio audit é declarado no relatório. | Alta | CLI-1, SPRAWL-1, BUG-5 | Alta | ⏳ Pendente | — |
| BUS-1 | W6 | Relay | Relay ao consumidor B pelo bus `<bus-interno>` (thread `higiene-repo`): comunicar a decisão **D-1** (emoji-prefixo) e o cronograma do conserto. Ele está **bloqueado esperando isto** para os dois repos não divergirem. Barato e desbloqueia terceiro -- por isso sobe na fila. | Alta | BUG-5 | Baixa | ⏳ Pendente | — |
| CHK-CORE | W7 | Audit | Integridade de tabela e vocabulário: **CHK-01** ID duplicado (listar as N linhas com diff resumido); **CHK-02** nº de células ≠ ncols, com DIAGNÓSTICO da causa provável (pipe cru? célula faltando? fragmento truncado?) e conserto sugerido; **CHK-03** múltiplos cabeçalhos ID+Status + relatório do SPAN da canônica; **CHK-04** ncols divergente entre tabelas (pré-condição de consolidação); **CHK-08** status fora do vocabulário; **CHK-11** reconciliar o total do `todo_health` com contagem independente (ele já reportou 14 num arquivo de 215 sem avisar). | Alta | AUDIT-ENG | Alta | ⏳ Pendente | — |
| CHK-GRAPH | W7 | Audit | Um walk no grafo de dependências: **CHK-05** pré-requisito citando ID inexistente; **CHK-06** ciclo (reportar o ciclo inteiro); **CHK-07** Onda inconsistente (item na mesma onda de um pré-requisito seu, ou posicionado antes dele na ordem das linhas). | Alta | AUDIT-ENG | Média | ⏳ Pendente | — |
| CHK-09 | W7 | Audit | Claims obsoletas na Descrição ("não pushado", "commit local", "branch X") **verificadas contra o git real** (`git ls-remote`, `cat-file -e`, `diff main --`). Padrões configuráveis com defaults pt+en -- nenhum check pode assumir português no conteúdo livre. | Média | AUDIT-ENG | Média | ⏳ Pendente | — |
| CHK-10 | W7 | Audit | Rodar `todo_sync.py` **sem** `--apply` e anexar a proposta ao relatório, com o aviso canônico (citar ID ≠ entregar; ler com desconfiança) e o estado do baseline `todo-sync-ref`. | Média | AUDIT-ENG | Baixa | ⏳ Pendente | — |
| SKILL-AUDIT | W8 | Audit | Integrar `--audit` na `SKILL.md` (contrato, formato de saída, exit codes) e atualizar o `argument-hint` do frontmatter (D-7). | Alta | CHK-CORE, CHK-GRAPH, CHK-09, CHK-10 | Média | ⏳ Pendente | — |
| AC-REAL | W8 | Testes | Aceitação em corpus real, localizando **pelo conteúdo, não pelo número da linha**: **AC-1** consumidor B -- achar o `TODO-PARSER-BUG` invisível por pipe cru no próprio texto, o fragmento truncado de `ATOM-3`, e o sprawl da canônica; **AC-2** consumidor A -- reconciliar 116=116 com zero CRÍTICO (ou achados listados e explicados, nunca "passou" por omissão). | Alta | CHK-CORE, CHK-GRAPH | Média | ⏳ Pendente | — |
| CHK-CASA | W8 | Audit | Camada de **convenção da casa** (opt-in, desligada por default): **CHK-12** TST-*/AUD-* agendados antes do que cobrem; **CHK-13** INBOX (IDs duplicando a tabela, formato); **CHK-14** item fixo de Wiki+doc-iniciante como última onda. Fora do perfil "casa" nem aparecem no relatório -- é o teste vivo da separação núcleo × casa. **Pode escorregar para v1.1 se W8 apertar.** | Baixa | CHK-CORE | Média | ⏳ Pendente | — |
| FIX-ENG | W9 | Fix | `tools/todo_fix.py`: aplica APENAS o mecânico e byte-preserving -- escapar `\|` cru, remover fragmento truncado após mostrar o diff, consolidar tabelas fragmentadas (só com ncols idênticos, preservando ID/Status/Estado Auditado, **sem reordenar e sem recalcular WSJF**), corrigir claim obsoleta mostrando o texto novo antes. **NUNCA** muda status, reordena ou deleta branch/commit. Pré-condição: working tree do TODO.md limpa (aborta senão); depois de aplicar, re-parsear provando round-trip + contagem. Confirmação separada por classe de fix. Inclui a regra fixa do líder: ao final de todo `--audit`, sugerir o `--fix` listando o que faria. | Alta | AUDIT-ENG, CHK-CORE | Alta | ⏳ Pendente | — |
| AC-FIX | W10 | Testes | Aceitação **AC-4**: `--fix` sobre uma **cópia** do corpus do consumidor B conserta os 2 defeitos vivos, mantém round-trip byte-exato no resto, e o `--audit` seguinte sai limpo desses checks. Gate obrigatório: o `--fix` reescreve arquivo do usuário e o erro aqui é irreversível do lado de fora. | Alta | FIX-ENG | Média | ⏳ Pendente | — |
| README-1 | W10 | Docs | README bilíngue corrigido para **9 colunas** (hoje documenta 8 em `README.md:34-37` e no espelho en `:131-134`), com matriz de instalação, as duas camadas (núcleo genérico × convenções da casa), as dependências externas hoje não declaradas, e os modos degradados (sem agents → thread direta; sem vault → wikilinks mortos; sem python3 → só a parte agent-driven). **DoD inclui o check de consistência README × SKILL.md** -- o gate que teria pegado o schema obsoleto. | Alta | SKILL-AUDIT, FIX-ENG | Média | ⏳ Pendente | — |
| TST-T15 | W10 | Testes | Pre-CI local: `scripts/preci.sh` espelhando o workflow (pytest + ruff + shellcheck + consistência README×SKILL.md) na mesma ordem, para o vermelho não aparecer só no servidor. Ver `TESTES.md`. | Média | CI-1, FIX-ENG | Baixa | ⏳ Pendente | — |
| AUD-FINAL | W11 | Auditoria | Auditoria adversarial **única** por `qa-engineer` independente (≠ implementer, ≠ orquestrador), consolidando o que em projeto maior seriam 7 auditorias: mutation testing de cada guard, cobertura significativa, meia-página de superfície de ameaça do hook (código de terceiro executando na máquina alheia), SAST + secrets, e **conformidade de licença pós-GPL-3**. Arquitetura não vira item aqui porque virou ADR-1. Ver `AUDITORIAS.md`. | Alta | AC-REAL, AC-FIX, TST-T15 | Alta | ⏳ Pendente | — |
| REL-1 | W12 | Release | CHANGELOG do zero (referenciando os consertos de 27-28/07 já feitos no toolkit: `4471888`, `e0f4da6`, `8f5c0e0`) + tag **v1.0.0** + release no GitHub. **A tag exige confirmação do líder no contexto.** | Alta | AUD-FINAL, README-1 | Baixa | ⏳ Pendente | — |
| MIG-1 | W13 | Migração | Migração da máquina do líder (D-8): `~/.claude/githooks` vira **symlink** para `tools/hooks/` do clone, e a skill instalada passa a apontar para o clone. Passo de verificação obrigatório (`git config --global --get core.hooksPath` + commit de teste em repo sacrificável). Não pode deixar os hooks mortos nem duplicados. | Alta | REL-1 | Média | ⏳ Pendente | — |
| WIKI-1 | W14 | Docs | Wiki do repo (GitHub wiki-native) + documentação `.md` extensa em registro didático para **iniciante em computação** (explica todo jargão, passo a passo, sem assumir conhecimento), derivada de `docs/` -- linka, não duplica. Regra da casa: último item, pós-tag, executado por `technical-writer`, **nunca inline**. | Baixa | REL-1 | Alta | ⏳ Pendente | — |

## INBOX (descobertas não priorizadas)

<!-- 1 linha por descoberta: `- <ID tentativo ou —>: descrição curta`. Drenada por --create/--reorder. -->

_(vazia)_

---

## Notas de montagem (o que foi fundido, cortado e por quê)

Registrado aqui porque **truncar em silêncio faz a tabela parecer completa quando não é**.
Gate anti-OE decidido por Cósimo (Chief of Staff): **thread direta**, não o time de 5 lentes --
o `--create` é artefato mecânico de planejamento e as decisões já estavam fechadas. A única
exceção que ele exigiu é o passe de ADR (`ADR-1`) antes dos consertos.

**Fundidos** (viraram sub-bullets dentro de um item, não sumiram): `LIC-1` → `SCAF-1`;
`ABS-2` → `ABS-1`; `CI-2`, `CI-3`, `TST-T2` (estática), `TST-T8` (secrets) e `TST-GAP-3`
(shims) → jobs do `CI-1`; `CIT-1`+`TCH-1`+`HDR-1` → `PRED-FIX`; `CHK-01..04`+`CHK-08`+`CHK-11`
→ `CHK-CORE`; `CHK-05..07` → `CHK-GRAPH`; `CHK-12`+`CHK-13`+`CHK-14` → `CHK-CASA`;
`FIX-SUGGEST` → `FIX-ENG`; `CHANGELOG-1`+`TAG-1` → `REL-1`.

**Cortados, com o que os substitui**: `TST-T5` (deps), `TST-T12` (CVE) e `AUD-DEPS` -- o runtime
é stdlib puro, não há superfície; substituídos por um guard de 3 linhas no `CI-1` ("nenhum import
fora da stdlib") e pela verificação de licença dentro do `AUD-FINAL`. `TST-T14` (integração) --
já coberto por `GAP-2` + `CONTR-1`. `AUD-DISC/ARCH/SEC/QUALITY/COV/LANG/REPORT` -- 7 itens
consolidados em `AUD-FINAL` (o conteúdo permanece; o que sumiu foi a burocracia de 7 linhas).
`CI-4` (consistência README×SKILL.md) -- vira linha do DoD de `README-1`, porque o README só
nasce em W10 e um check sem objeto é infra vazia. `CHK-15..18` (`--audit=repo`) -- **v1.1** por
decisão D-5; higiene de disco fica fora da skill.

**Ondas**: 14 ondas para 33 itens (32 pendentes + 1 concluído) porque as dependências são reais,
não decorativas. Itens da mesma onda são paralelizáveis **logicamente**; quando dois deles tocam
o mesmo arquivo (caso de W5, toda ela em `todo_lib.py`), o orquestrador serializa fatia a fatia --
disputa de arquivo não é dependência, mas impede paralelismo de verdade. WIP = 1 onda.

**Verificação desta tabela** (rodada na montagem, com script escape-aware -- é o que `CHK-05/06/07`
vão automatizar): 33 linhas de 9 células, **zero ID duplicado**, **zero pré-requisito inexistente**,
**zero ciclo**. Um defeito real foi encontrado e corrigido aqui: `AC-FIX` estava na mesma onda do
seu pré-requisito `FIX-ENG` -- exatamente o `CHK-07`, achado na primeira aplicação. O
`todo_health.py` não roda ainda porque `Projects/tab_pendencias/` não é repositório git até o
`SCAF-1`; ele saiu com a mensagem "Nao e um repositorio git" **e exit code 0**, que é o `CLI-1`
se manifestando ao vivo.

**WSJF qualitativo** (porte early; a tabela de scoring completa da [[AGILE]] §17.2 é exigida em
scale/bigtech, aqui seria cerimônia). O critério que ordenou: fundação e one-way-door primeiro
(`ADR-1`, `SCAF-1` com a licença), **rede de segurança antes dos consertos** (`CONTR-1` precede
todo conserto de parser de propósito -- é o que prova 116=116 e 215=215 depois de mexer), e
desbloqueio de terceiro cedo (`BUS-1` sobe assim que `BUG-5` fecha, porque o consumidor B está
parado esperando).

**Não pode ser cortado** (Cósimo, risco de subdimensionar): `CORP-0` e `CONTR-1` (sem eles não
há contrato, há esperança); os invariantes de round-trip byte-exato e "sync nunca seta ✅"
(quebrados, corrompem TODO.md de terceiro); `ENC-1`; o gate `AC-FIX`; e o mutation testing por
`qa-engineer` independente -- implementer ≠ reviewer não é cerimônia, é o único mecanismo que
pega teste que passa sem verificar nada.

**Ordem inviolável respeitada**: T1 unitário ride com a implementação e nunca vira item;
`TST-T15` e `AUD-FINAL` são downstream do que cobrem. Nota de dogfooding: os itens de lacuna de
teste foram nomeados `GAP-*`, não `TST-*`, justamente para não colidirem com o namespace do
catálogo e disparar um falso positivo do futuro `CHK-12`.

⚠️ **Hook de TDD**: este projeto ainda não tem `.claude/tdd-guard.json`. O TDD dos itens de
implementação depende de disciplina do implementer até o hook ser ativado.
