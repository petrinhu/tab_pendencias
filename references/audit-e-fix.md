# `--audit` e `--fix` (motores de integridade da tabela)

> Referência operacional movida do `SKILL.md` em 21/08/2026 para reduzir o
> contexto carregado a cada invocação da skill. O `SKILL.md` mantém as
> proibições, os gates e os exit codes; o catálogo e as flags estão aqui.
> Fronteira núcleo genérico x convenções da casa:
> [`../docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](../docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md).

## `--audit` (`tools/todo_audit.py`)

Motor de auditoria estrutural do próprio `TODO.md` (`tools/todo_audit.py`, camada
núcleo genérico, decisão em
[`docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md`](../docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md)):
roda offline, sem LLM/rede, sem orquestrar nenhum agent. Executa sob demanda; **não** faz parte da Injeção
automática de testes e auditorias acima (aquela cobre o *planejamento* do projeto
que usa a skill; `--audit` cobre a *integridade da própria tabela*).

- **Sempre read-only.** Nenhum caminho de código abre o `TODO.md` em modo de
  escrita, nem muta estado de git. A única escrita possível é a de `--output`
  (relatório opcional em arquivo à parte), e ela é bloqueada com erro (`exit 1`) se o
  caminho resolver para dentro do repositório auditado.
- **`--todo <caminho>`**: audita um arquivo fora do repositório corrente (não
  precisa estar no `cwd` nem no mesmo repositório git de quem invoca). Restrição
  fixa: o arquivo precisa se chamar exatamente `TODO.md` (mesma convenção de
  `todo_lib.find_todo`); qualquer outro nome sai com `exit 1` e mensagem explicando
  a restrição. Sem a flag, o comportamento é o mesmo de sempre: descoberta
  automática a partir do `cwd`, que precisa ser um repositório git.
- **`--profile core|casa`** e o arquivo `.tab_pendencias.ini` na raiz do repo
  auditado (seção `[profile]`, chave `name = casa`): perfil `core` é o default
  (ausência de arquivo ou de chave); `--profile` na linha de comando sobrepõe o
  arquivo para uma execução pontual. Config lido com `configparser` da stdlib
  (D-9/D-10 -- INI, escolha histórica; piso oficial Python >= 3.11, PYFLOOR-2).
  **A camada casa é aditiva, nunca substitutiva**: sob `casa` rodam os 14 checks
  do núcleo **mais** os 3 da casa (17 no total); quem não ativa `casa` não perde
  nenhum check do núcleo, só não ganha os 3 extras. Medido ao vivo: sob `core`
  (default), os 11
  checks do núcleo executam e cada check `profile = casa` é **declarado como não
  executado** nos avisos do motor (`"CHK-12 (convencao da casa) nao executado --
  perfil ativo = core. Habilite com --profile casa ou .tab_pendencias.ini
  [profile] name = casa."`, um por check pulado) -- nunca silenciado. Sob
  `--profile casa`, os 14 checks executam e nenhum aviso de check pulado
  aparece.
- **`--max-per-check N`** (default 5; `N<=0` = sem limite): amostra no máximo N
  achados por check no relatório impresso. Achados de severidade **CRÍTICO nunca
  são truncados**; o corte incide só sobre IMPORTANTE/COSMÉTICO, e o que ficou de
  fora é sempre contado e declarado na própria seção do check (nunca só
  descartado -- "no silent caps").
- **`--output <arquivo>`**: também grava o relatório nesse arquivo (além de
  imprimir no terminal). Nunca pode resolver para dentro do repositório auditado
  (aborta com `exit 1` se apontar para lá); use um caminho de scratchpad.
- **`-v` / `--verbose`**: acrescenta traceback completo quando um check ou a
  leitura do `TODO.md` falha (default: só tipo + mensagem da exceção).
- **Exit codes** (fixos, nenhum check inventa um novo): `0` = execução ok e zero
  achados; `1` = erro de execução (não é repositório git quando exigido, `TODO.md`
  ilegível, flag inválida ou desconhecida); `2` = execução ok e há 1+ achado, **de
  qualquer severidade, inclusive só COSMÉTICO**. Isto é o que permite usar
  `--audit` em automação/CI: um pipeline que quer tolerar cosmético filtra por
  severidade dentro do relatório, não pelo exit code.
- **Catálogo de checks hoje** (14 do núcleo + 3 da casa = 17 registrados;
  severidade indicada é o default do registro -- alguns checks emitem achados
  com severidade diferente conforme o caso concreto, ex.: `CHK-08` cobre tanto
  COSMÉTICO quanto IMPORTANTE). A coluna `Perfil` diz se o check roda sempre
  (`core`) ou só quando `casa` está ativo:

  | Check | Título | Severidade (default) | Perfil |
  |---|---|---|---|
  | `CHK-01` | ID duplicado | CRÍTICO | core |
  | `CHK-02` | nº de células ≠ cabeçalho (diagnóstico) | CRÍTICO | core |
  | `CHK-03` | Tabela fragmentada + span da canônica | CRÍTICO | core |
  | `CHK-04` | ncols divergente entre tabelas ID+Status | CRÍTICO | core |
  | `CHK-05` | Pré-requisito citando ID inexistente | IMPORTANTE | core |
  | `CHK-06` | Ciclo de dependência | CRÍTICO | core |
  | `CHK-07` | Onda inconsistente com a dependência | IMPORTANTE | core |
  | `CHK-08` | Status fora do vocabulário canônico | IMPORTANTE | core |
  | `CHK-09` | Claims obsoletas na Descrição (contra o git real) | IMPORTANTE | core |
  | `CHK-10` | Proposta do `todo_sync.py` (sem `--apply`) anexada | COSMÉTICO | core |
  | `CHK-11` | Reconciliação de contagem (`todo_health`) | CRÍTICO | core |
  | `CHK-19` | Mais de uma tabela no arquivo | CRÍTICO / IMPORTANTE | core |
  | `CHK-20` | Linha em branco dentro da tabela | IMPORTANTE | core |
  | `CHK-21` | Tabela de checklist fora do TODO.md (projeto) | IMPORTANTE | core |
  | `CHK-12` | TST-*/AUD-* agendado antes do que cobre | CRÍTICO | **casa** |
  | `CHK-13` | INBOX: ID duplicado da tabela ou formato inválido | IMPORTANTE | **casa** |
  | `CHK-14` | Item de Wiki + doc para iniciante ausente na última onda | COSMÉTICO | **casa** |

  Os 3 checks de perfil `casa` moram em `tools/casa/chk_casa.py` (não mais
  vazio) e implementam, respectivamente, a ordem inviolável de teste/auditoria
  (ver "Testes e auditoria: ordem inviolavel" acima), a higiene da seção INBOX,
  e a regra da casa de item fixo de Wiki+doc-iniciante como última onda
  pós-tag.

  Alvo (`--todo`) fora de qualquer repositório git resolvível: `CHK-09`/`CHK-10`
  (os únicos que dependem de `git`) degradam sozinhos por achado
  ("desconhecido"/erro), e o motor soma um aviso sistêmico único explicando a
  causa comum, em vez de N achados soltos sem contexto.

## `--fix` (`tools/todo_fix.py`)

Motor do `--fix` (FIX-ENG, ADR-0001 seção c, FIX-ESCOPO-2): aplica **só** as
**duas** classes mecânicas e byte-preserving do escopo real --
`escapar_pipe_cru` (CHK-02) e `remover_fragmento_duplicado` (CHK-01) -- marcadas
`[auto-fixável]` pelos checks. Consolidar tabela (CHK-03/04) e reescrever claim
(CHK-09) ficam **fora** do auto-fix (movem linhas em arquivo de terceiro).
Regra: audit nunca marca `fixable=True` sem corretor no motor. **Nunca** muda
`Status`, nunca reordena, nunca toca branch/commit do repositório.

- **Default é dry-run.** Sem `--apply`, só mostra o plano (o que faria, com
  diff das linhas envolvidas) e nunca escreve.
- **`--apply <classe...>`**: aplica só as classes nomeadas (`escapar_pipe_cru`,
  `remover_fragmento_duplicado`), ou `--apply all` para todas as detectadas
  nesta execução -- confirmação sempre **separada por classe**, nunca um "sim"
  global implícito.
- **Precondição obrigatória**: a working tree do `TODO.md` tem que estar
  limpa (`git status --porcelain` vazio para o arquivo) antes de qualquer
  `--apply`; working tree suja, ou ausência de repositório git resolvível,
  aborta com `exit 1` sem tocar o arquivo.
- **Escrita sempre atômica**: arquivo temporário no mesmo diretório, prova de
  round-trip (linhas não tocadas byte-a-byte) e de contagem de itens
  ANTES de trocar o arquivo real (`os.replace`); qualquer falha na prova ou
  na escrita aborta sem deixar o `TODO.md` tocado.
- Uma correção marcada `[auto-fixável]` pelo `--audit`, mas cuja posição exata
  o motor de fix não consegue localizar sem ambiguidade (ex.: pipe cru fora
  de qualquer *code span*), aparece no plano como **não aplicável**, com o
  motivo -- o motor nunca escreve adivinhando.
- Exit codes (D-6): `0` = nada a corrigir; `1` = erro de execução (não é
  repositório git, `TODO.md` ilegível, working tree suja ao aplicar, falha de
  escrita); `2` = há 1+ correção disponível (mostrada em dry-run ou aplicada).

Regra fixa do líder: ao final de todo `--audit`, sugerir o `--fix` listando o
que faria. O engate conversacional (a sugestão automática dentro do relatório
de `--audit`) é de outra fatia; o motor (`todo_fix.build_plan`) já expõe o
hook necessário.
