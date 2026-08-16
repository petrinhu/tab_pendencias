# CLAUDE.md -- tab_pendencias v2

Projeto: transformar `https://github.com/petrinhu/tab_pendencias.git` num pacote distribuível
completo (skill + toolkit de frescor + testes + CI + releases + comandos `--audit`/`--fix`).

## Pendências

A tabela de pendências e planejamento do projeto está em `TODO.md` na raiz (ordenada por
execução, coluna Onda marca passos paralelizáveis). **Dogfooding**: ela usa a própria skill que
este projeto constrói.

## Documentos canônicos deste projeto

- `prompt_inicial.md` -- brief auditado (todo fato tem evidência `arquivo:linha` ou SHA). É a fonte.
- `decisoes_lider.md` -- decisões **D-1..D-8** fechadas pelo líder. Não rediscutir.
- `TESTES.md` / `AUDITORIAS.md` -- manuais podados para o stack (Python stdlib + sh + Markdown).
- `.bigtech-porte` -- porte classificado (early / Pipeline-Lean).

## Requisito canônico do produto (ordem do líder, 2026-07-28)

> *"a skill deve ser agnóstica a projeto e rodar em windows e linux"*

Vale sobre qualquer decisão de implementação. **Agnóstica a projeto**: zero nome de projeto, zero
caminho de máquina, zero suposição sobre o `TODO.md` além do contrato (schema 9/8 colunas, os 7
status com emoji, INBOX); esquema de ID é arbitrário -- usar o que o projeto já tem, nunca impor;
o vocabulário de status é pt-br por contrato, mas descrição, ID e mensagem de commit do usuário
podem estar em qualquer língua, e nenhum check pode assumir português no conteúdo livre; as
convenções da casa são opt-in via `.tab_pendencias.ini` e degradam com aviso limpo.
**Cross-platform**: nada de assumir POSIX, separador `/`, permissão Unix ou shell `sh`; `encoding`
e `newline` sempre explícitos (senão o round-trip byte-exato quebra no Windows); a única exceção
são os shims de git hook, que no Windows dependem do Git for Windows -- degradação **documentada**,
nunca suposição silenciosa.

Isto não é boa intenção: é verificado pelo corpus sintético em `tests/corpus/` (outra língua,
outros esquemas de ID) e pela matrix `ubuntu` + `windows` do CI. Requisito sem teste que o
exercite é promessa, não requisito. Detalhe formal no ADR-0001, seções (a), (d) e (e).

## Regras de execução

- Toda alteração de código é feita por **agente especialista**, nunca inline pelo orquestrador.
  Implementer ≠ reviewer ≠ orquestrador; o review adversarial **executa** (mutation testing).
- **TDD**: teste escrito antes, visto falhando pelo motivo certo, depois verde. T1 unitário ride
  com a implementação e nunca vira item da tabela.
- **Commit por fatia** citando o ID do item no Conventional Commit (pt-br) e tocando o `Status`
  no mesmo commit: implementação entregue → `🔍 Pendente verificação`, nunca `✅` direto.
- **Push ao fim de onda completa**; merge em `main` via PR e tag pedem confirmação do líder.
  A mensagem do push mente -- confirmar por `git ls-remote`.
- Idioma: chat e docs em pt-br; identificadores de código em inglês. Em-dash
  (U+2014) e celula vazia canonica do schema (MDASH-2); excecao deste repo via
  `.tab_pendencias.allow_emdash`. Em prosa livre preferir `--`.
- Piso Python: **>= 3.11** (`pyproject.toml`, PYFLOOR-2). Config continua INI.
- As 12 armadilhas operacionais estão na seção 8 do `prompt_inicial.md` -- colar nos briefs dos
  agents implementadores.
