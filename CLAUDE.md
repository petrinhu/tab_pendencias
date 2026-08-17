# CLAUDE.md -- tab_pendencias (produto v1.2+)

Produto distribuível: skill Claude Code + toolkit de frescor (Python stdlib) +
testes + CI multi-OS + releases. Comandos públicos: `--create`, `--reorder`,
`--show`, `--main`, `--add_tests_audit`, `--audit`, `--fix`, `--add`, `--drain`.

## Pendências

A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz
(ordenada por execução, coluna Onda marca passos paralelizáveis). **Dogfooding**:
usa a própria skill que este repositório distribui.

## Documentos canônicos

| Documento | Papel |
|---|---|
| [`SKILL.md`](SKILL.md) | Contrato da skill (schema, fluxos, intake, sinais) -- fonte operacional |
| [`docs/adr/0001-...`](docs/adr/0001-fronteira-nucleo-generico-e-convencoes-da-casa.md) | Fronteira núcleo genérico × convenções da casa |
| [`docs/adr/0002-...`](docs/adr/0002-maquina-de-estados-de-intake-e-inbox-como-fila-de-excecao.md) | Máquina de intake; INBOX = **exception queue** |
| [`references/`](references/) | Normas vivas: frescor, sinais `TAB_*`, hub, bus, cutover |
| [`decisoes_lider.md`](decisoes_lider.md) | Decisões **D-1..D-8** (e posteriores) fechadas pelo líder -- não rediscutir |
| [`TESTES.md`](TESTES.md) / [`AUDITORIAS.md`](AUDITORIAS.md) | Manuais podados para o stack (Python stdlib + sh + Markdown) |
| [`.bigtech-porte`](.bigtech-porte) | Porte classificado (early / Pipeline-Lean) |
| [`docs/campanha/`](docs/campanha/) | **Histórico** do plano de melhoria 2026-08-16 -- não é doc vivo de produto |
| [`prompts_legados/`](prompts_legados/) | Briefs legados de bootstrap -- não reabrir como fonte |

## INBOX = exception queue (não é fila normal)

Trabalho novo **não** "vai para a INBOX" como norma. O caminho normal é o
**pipeline de intake** (`--add` / `tools/todo_intake.py`):

- L0 / SCOPED / FULL / DUPLICATE conforme flags de julgamento;
- residual INBOX só para ambíguo / sem autoridade (`NEEDS_TRIAGE`,
  `NEEDS_LEADER_DECISION`);
- dreno com `--drain` + judgments JSON; pós-apply `classifiable_inbox_count == 0`;
- workers devolvem `DISCOVERED_WORK` → `tools/intake_agent_bridge.py` → intake
  (workers **não** editam `TODO.md`).

Detalhe: ADR-0002, `SKILL.md` (seções intake/drain), `references/frescor-da-tabela.md`.

## Requisito canônico do produto (ordem do líder, 2026-07-28)

> *"a skill deve ser agnóstica a projeto e rodar em windows e linux"*

Vale sobre qualquer decisão de implementação. **Agnóstica a projeto**: zero nome
de projeto, zero caminho de máquina, zero suposição sobre o `TODO.md` além do
contrato (schema 9/8 colunas, os 7 status com emoji, INBOX residual); esquema de
ID é arbitrário -- usar o que o projeto já tem, nunca impor; o vocabulário de
status é pt-br por contrato, mas descrição, ID e mensagem de commit do usuário
podem estar em qualquer língua, e nenhum check pode assumir português no
conteúdo livre; as convenções da casa são opt-in via `.tab_pendencias.ini` e
degradam com aviso limpo.
**Cross-platform**: nada de assumir POSIX, separador `/`, permissão Unix ou shell
`sh`; `encoding` e `newline` sempre explícitos (senão o round-trip byte-exato
quebra no Windows); a única exceção são os shims de git hook, que no Windows
dependem do Git for Windows -- degradação **documentada**, nunca suposição
silenciosa.

Verificado pelo corpus sintético em `tests/corpus/` e pela matrix CI: Ubuntu +
Windows nativos + Debian/Fedora/Arch em container. Detalhe formal no ADR-0001,
seções (a), (d) e (e).

## Regras de execução

- Toda alteração de código é feita por **agente especialista**, nunca inline pelo
  orquestrador. Implementer ≠ reviewer ≠ orquestrador; o review adversarial
  **executa** (mutation testing).
- **TDD**: teste escrito antes, visto falhando pelo motivo certo, depois verde.
  T1 unitário ride com a implementação e nunca vira item da tabela.
- **Commit por fatia** citando o ID do item no Conventional Commit (pt-br) e
  tocando o `Status` no mesmo commit: implementação entregue →
  `🔍 Pendente verificação`, nunca `✅` direto.
- **Push ao fim de onda completa**; merge em `main` via PR e tag pedem confirmação
  do líder. A mensagem do push mente -- confirmar por `git ls-remote`.
- Idioma: chat e docs em pt-br; identificadores de código em inglês. Em-dash
  (U+2014) é célula vazia canônica do schema (MDASH-2); exceção deste repo via
  `.tab_pendencias.allow_emdash`. Em prosa livre preferir `--`.
- Piso Python: **>= 3.11** (`pyproject.toml`, PYFLOOR-2). Config continua INI.
- **HOOKSRC-1:** ganchos vivos (`core.hooksPath`) apontam para a **instalação
  publicada** (submódulo pinado no consumidor), nunca para o checkout de
  desenvolvimento deste produto.
- **FIX-ESCOPO-2:** `--fix` tem **2** classes reais (`escapar_pipe_cru`,
  `remover_fragmento_duplicado`), não 4.
- Hub com `[hub] derived=true` é read-only no apply de intake/drain; gerador
  TAB-HUB-GEN **cancelado** (anti-OE).
- Backlog legado na tabela pode estar **cancelado** (`💡`) por anti-OE pós-v1.2 --
  não tratar o roadmap antigo da campanha como plano ainda vigente.
