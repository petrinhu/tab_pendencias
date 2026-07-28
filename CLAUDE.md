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

## Regras de execução

- Toda alteração de código é feita por **agente especialista**, nunca inline pelo orquestrador.
  Implementer ≠ reviewer ≠ orquestrador; o review adversarial **executa** (mutation testing).
- **TDD**: teste escrito antes, visto falhando pelo motivo certo, depois verde. T1 unitário ride
  com a implementação e nunca vira item da tabela.
- **Commit por fatia** citando o ID do item no Conventional Commit (pt-br) e tocando o `Status`
  no mesmo commit: implementação entregue → `🔍 Pendente verificação`, nunca `✅` direto.
- **Push ao fim de onda completa**; merge em `main` via PR e tag pedem confirmação do líder.
  A mensagem do push mente -- confirmar por `git ls-remote`.
- Idioma: chat e docs em pt-br; identificadores de código em inglês. Evitar em-dash nos arquivos
  (usar `--`).
- As 12 armadilhas operacionais estão na seção 8 do `prompt_inicial.md` -- colar nos briefs dos
  agents implementadores.
