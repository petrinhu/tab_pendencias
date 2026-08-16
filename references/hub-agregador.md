# Hub agregador (TAB-HUB-001)

> Reference do produto. O hub e **view derivada read-only**. Nao e
> backlog, nao e INBOX, nao recebe `--add` / `--drain`.

## O que e

Um `TODO.md` (ou painel) que **agrega contagens** de varios `TODO.md` de
projeto. A fonte da verdade continua sendo cada projeto.

```text
pedido / descoberta
  -> TODO do projeto fonte (intake)
  -> regeneracao do hub (script externo, se existir)
  -> view atualizada
```

## O que NAO e

- Fila editavel de trabalho.
- Destino de `DISCOVERED_WORK` ou de mensagem de bus.
- Lugar para secao `## INBOX (descobertas não priorizadas)`.
- Substituto do `TODO.md` de um projeto.

## Protecao mecanica no produto

Se o diretorio do `TODO.md` tiver `.tab_pendencias.ini` com:

```ini
[hub]
derived = true
```

entao `todo_intake.run_intake` e `todo_intake.run_drain` em **`--apply`**
recusam a escrita com erro `hub_is_derived_readonly`. Dry-run ainda pode
classificar (diagnostico), mas nao grava.

Funcoes: `todo_intake.is_derived_hub(todo_path)`.

## Gerador

Este produto **nao** embute gerador de hub (anti-OE). Se o ecossistema
tiver um script deterministico, ele roda **depois** da mudanca no TODO
de projeto, ou marca a view como stale de forma objetiva.

Item de backlog do proprio produto: `TAB-HUB-GEN` (gerador, se algum dia
for necessario). Ate la, hub e documentacao + guarda de escrita.

## Como marcar um hub

1. Crie o arquivo de view (pode ser Markdown com contagens).
2. Coloque `.tab_pendencias.ini` ao lado com `[hub] derived = true`.
3. Nao anexe INBOX. Nao rode intake com `--apply` ali.
