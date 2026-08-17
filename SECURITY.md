# Política de Segurança

## Como reportar uma vulnerabilidade

Se você encontrou uma falha de segurança neste projeto, por favor **não abra um issue público**. Reporte em sigilo por email:

**petrinhu@yahoo.com.br**

Inclua, se possível:

- Descrição da falha e o impacto.
- Passos para reproduzir (ou prova de conceito).
- Versão ou commit afetado (tag ou SHA).

Vou confirmar o recebimento assim que possível e trabalhar numa correção antes de qualquer divulgação pública. Obrigado por reportar de forma responsável.

## Superfície relevante (resumo)

Este produto roda **localmente** (git hooks + scripts Python stdlib). Pontos de atenção:

- Hooks executam código na máquina de quem instala -- use só a **instalação publicada**
  (pin de submódulo / tag), não um checkout de desenvolvimento (HOOKSRC-1).
- `--fix` / `--add` / `--drain` escrevem no `TODO.md` do usuário (working tree limpa +
  lock + escrita atômica).
- Journal de intake redige padrões óbvios de segredo na descrição (defesa em profundidade,
  não substitui scanner dedicado).
- Fixtures e corpus públicos são sintéticos; não reportar "segredo" que for só dado de teste
  fictício no repositório.

---

## Security Policy (English)

Found a security issue? Please do **not** open a public issue. Report it privately by email to **petrinhu@yahoo.com.br** with a description, reproduction steps, and the affected version or commit. I will acknowledge receipt and work on a fix before any public disclosure. Thank you for reporting responsibly.

Relevant surface (short): local git hooks and stdlib Python scripts; prefer a **published**
install for live hooks; write paths (`--fix`/`--add`/`--drain`) require a clean working tree
and use a write lock; intake journal best-effort redacts common secret patterns; public
fixtures are synthetic.
