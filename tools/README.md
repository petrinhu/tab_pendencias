# tools/ -- frescor da TODO.md (Camada 2 local)

Git hook **local, cross-platform e warn-only** que ajuda a manter a tabela de
pendências (`TODO.md`) sincronizada durante o sprint, **sem CI nem servidor**,
o gêmeo local da Camada 2. Detalhe canônico da convenção em
[`../references/`](../references/) (regras de frescor internalizadas, D-2).

Layout monorepo (D-4): os scripts Python ficam aqui em `tools/`; os shims
POSIX + `_chain.sh` ficam em [`hooks/`](hooks/); a suíte pytest fica em
[`../tests/`](../tests/).

## O que faz

No `post-commit` (já depois do commit, então **nunca bloqueia**), avisa em dois
casos, e só quando há lacuna acionável (silencioso caso contrário):

1. O commit **tocou código mas não citou nenhum ID** do `TODO.md`: sugere citar
   o ID (ex.: `V-12`) na mensagem, para rastrear o status. Bootstrapa o hábito.
2. O commit **cita um ID cujo Status ainda é "Pendente" / "Em andamento"**:
   lembra de atualizar o Status (implementação entregue, "Pendente
   verificação"; "Concluído" só após a onda de teste/auditoria).

Nunca edita o `TODO.md`, nunca aborta o commit. Registra uma linha em
`.git/todo-freshness.log` (local, não versionado) para **medir adesão** antes de
qualquer automação, a Camada 2 só escala com evidência, nunca de prontidão.

## Sincronização e saúde (scripts offline, sem LLM)

Dois scripts locais e **determinísticos** (Python stdlib; nem precisam de sessão Claude) complementam o hook. São a "metade mecânica" do frescor; o `--reorder` (julgamento) continua na skill:

- **`python3 tools/todo_sync.py`**: lê os commits desde o último sync (`.git/todo-sync-ref`), acha os IDs citados e propõe avançar itens `⏳ Pendente`/`🔄 Em andamento` para `🔍 Pendente verificação` (NUNCA `✅`; nunca reordena). Por padrão **só propõe**; `--apply` escreve. Preserva o resto da linha e o EOL (CRLF/LF), e ignora linha malformada. `--since <ref>` força uma janela.
- **`python3 tools/todo_health.py`**: relatório de itens presos em `🔍` (falso-done residual), tamanho da INBOX, e a % de adesão a citar ID (do `todo-freshness.log`). Dá o dado para "medir antes de escalar".

Podem ser rodados à mão, por um alias, pelo git hook, ou por um agendador local (systemd/launchd/Task Scheduler). Robustez verificada por `qa-engineer` + `code-reviewer` (CRLF, BOM, múltiplas tabelas, célula deslocada).

## Drift do pin de submódulo (`submodule_pin_drift.py`)

Detector **read-only, offline-first e warn-only** (TAB-SOT-007): quando este
toolkit é distribuído como submódulo git dentro de outro repositório, o
gitlink gravado na árvore do superprojeto pode ficar preso num commit antigo
sem que ninguém perceba -- foi exatamente o que aconteceu num consumidor real
(gitlink 67 commits atrás da tag publicada mais recente; `git clone
--recursive` numa máquina nova restaurava a skill sem o toolkit inteiro).

```sh
python3 tools/submodule_pin_drift.py --path caminho/do/submodulo [--url <remoto>] [--branch <nome>]
```

- **Agnóstico a projeto** (AGN-1): `--path` e `--url` são sempre parâmetros
  -- nenhum nome de projeto/submódulo vem embutido no código. Sem `--url`, o
  único fallback é o `.gitmodules` do próprio superprojeto (mecanismo padrão
  do git, não convenção deste projeto).
- **Nunca muta nada**: sem `git submodule update --remote`, sem
  commit/push, sem `git fetch` (mesma política de `checks/chk_frescor.py`
  para CHK-09 -- `git ls-remote` consulta o remoto sem gravar nada local).
  Exit code é sinal, não bloqueio: quem decide se isso falha um pipeline é o
  job de CI que consome a ferramenta.
- **Sem rede nunca vira "OK"**: se `git ls-remote` falhar/expirar, ou se o
  remoto não tiver nenhuma tag `vX.Y.Z`, o relatório sai com
  `status: nao_verificavel` -- nunca `atualizado`. `commits_behind` e
  `commits_ahead` só são calculáveis quando os objetos do submódulo já
  estão localmente disponíveis (checkout prévio); do contrário ficam
  `nao calculavel offline`, com o motivo explícito.
- **`status` enumera a posição relativa inteira, não só "bate ou não bate"**
  (TAB-SOT-007-BIS, 16/08/26 -- um pin *à frente* da última release, o
  estado normal de um consumidor que segue a `main` entre releases, chegou
  a sair como `desatualizado` mesmo com `commits_behind: 0` no próprio
  relatório contradizendo o veredito):
  - `atualizado` -- pin == última release (e == branch pedido, se houver);
  - `a_frente` -- pin é descendente da última release (comum entre
    releases, **não** é drift pra trás);
  - `desatualizado` -- pin é ancestral da última release (ou, sem checkout
    local pra confirmar a direção, sha diferente presume `atras` -- a
    mesma política conservadora do incidente histórico de 67 commits);
  - `divergente` -- pin e última release estão em linhas de história
    diferentes (nem ancestral nem descendente) -- a situação genuinamente
    perigosa, nunca conflada com `desatualizado`;
  - `nao_verificavel` -- sem rede, sem tag semver no remoto, ou branch
    pedido não resolvido.
- Contrato de exit code (D-6/CLI-1): `0` = `status` em `atualizado` **ou**
  `a_frente` (nenhum dos dois é drift -- `a_frente` sai silencioso de
  propósito, pra não virar alarme permanente entre releases, mesmo
  raciocínio anti-fadiga-de-alerta do ADR-0002); `1` = erro de execução
  (path inválido, `.gitmodules` sem URL resolvível, flag desconhecida);
  `2` = `status` em `desatualizado`, `divergente` ou `nao_verificavel`.

## Write-ahead journal de intake (`intake_journal.py`, TAB-ADD-000)

Captura **durável e barata** de um candidato a item de `TODO.md`, gravada
ATOMICAMENTE em disco **antes** de qualquer classificação agentiva que
possa terminar em mutação persistente da tabela. Fecha a janela entre "a
descoberta foi entendida" e "a descoberta foi persistida" -- se a sessão
morrer nessa janela, a descoberta some em silêncio sem este journal.
Implementa a metade mecânica descrita no ADR-0002, seção (c)/T2.

```python
import intake_journal as J

path = J.write_candidate(
    J.new_candidate_id(), source="agent",
    description="testes cobrem X mas não Y", source_item="V-12")
# ... depois de integrar e VALIDAR a integração no TODO.md ...
J.mark_done(J.journal_dir_for(), candidate_id)
```

- **Onde mora**: `<git-common-dir>/tab-pendencias/intake-journal/`, obtido
  via `git rev-parse --git-common-dir` (nunca `.git` como diretório físico
  -- em `git worktree`, `.git` é um ARQUIVO que aponta pro repo principal).
  Fica fora do `TODO.md`, fora do versionamento, e é **compartilhado**
  entre todos os worktrees do mesmo repositório.
- **Registro mínimo** (JSON, um arquivo por candidato): `candidate_id`,
  `created_at`/`updated_at`, `source` (`user|bus|agent|audit|test`),
  `description` (sanitizada, ver abaixo), `source_item`, `state`
  (`NEW`/`DONE`).
- **Nome de arquivo**: `candidate_id` nunca vira nome de arquivo sem
  `sanitize_filename_component` -- remove os caracteres proibidos no
  Windows (`< > : " / \ | ? *` e controle), corta espaço/ponto nas pontas,
  evita nome de dispositivo reservado (`CON`, `COM1`..`9`, `LPT1`..`9`) e
  soma um sufixo hash do `candidate_id` original pra dois IDs diferentes
  que sanitizam igual nunca colidirem em disco.
- **Ciclo de vida**: `write_candidate` grava `state=NEW`; depois da
  integração persistida e validada, `mark_done` (mantém em disco,
  `state=DONE`) ou `remove_candidate` (apaga) -- as duas idempotentes
  (chamar de novo não é erro, só devolve `False`).
- **Recuperação de órfão**: `list_orphans` lista todo registro
  `state != DONE`; `recover_orphans(journal_dir, todo_text=...)` resolve
  cada órfão contra o texto atual do `TODO.md` por dedup mecânica de ID
  exato -- se o `candidate_id` já aparece lá (contrato: quem integra grava
  o `candidate_id` num marcador recuperável na linha), marca `DONE` sem
  criar nada; senão continua pendente sem nenhum efeito colateral. Rodar
  duas vezes seguidas nunca duplica (a única escrita possível é
  `mark_done`, que já é idempotente).
- **Journal corrompido/parcial nunca quebra a leitura**: `list_corrupted`
  reporta arquivo `*.json` ilegível separado de `list_orphans` (que nunca
  faz `mark_done` às cegas sobre algo que não deu pra interpretar);
  arquivo temporário de uma gravação atômica interrompida (`*.tmp`) é
  ignorado por não ter a extensão `.json`.
- **Segredo nunca entra no journal**: `redact_secrets` filtra
  `description` (chave AWS, bloco de chave privada PEM, atribuição
  `senha=`/`token=`/`api_key=`, bearer token, JWT) antes de gravar --
  best-effort, defesa em profundidade, não substitui revisão humana nem
  scanner dedicado.
- **Fora de escopo aqui** (fica pra `TAB-ADD-001`+): `--add`,
  classificação de impacto (L0..L3), reorder. Este módulo só oferece
  captura e recuperação; quem classifica e integra é outra camada.

CLI mínima de diagnóstico (leitura, nunca muta o `TODO.md`):

```sh
python3 tools/intake_journal.py --list-orphans [--journal-dir <caminho>]
```

## Como ativar

Os arquivos são `hooks/post-commit` (shim POSIX) + `todo_freshness.py`
(lógica, só stdlib). Escolha um modo:

### Por projeto (recomendado)

Versiona o hook junto do repo e vale também nos worktrees dos agents. O shim
(`post-commit`) procura `todo_freshness.py` **um nível acima** de onde ele
mesmo está (mesmo layout monorepo de `tools/hooks/` + `tools/` descrito
acima), e `todo_freshness.py` por sua vez precisa de `todo_lib.py` na
**mesma pasta** que ele -- por isso os scripts Python vão em `.githooks/` e
só os shims em `.githooks/hooks/` (não os dois juntos na mesma pasta):

```sh
mkdir -p .githooks/hooks
cp tools/hooks/post-commit tools/hooks/_chain.sh .githooks/hooks/
cp tools/todo_freshness.py tools/todo_lib.py .githooks/
chmod +x .githooks/hooks/post-commit    # Unix; no Windows o exec bit e irrelevante
git config core.hooksPath .githooks/hooks
```

### Global (todos os repositórios da máquina)

Aplica a todos os repos; faz **no-op silencioso** onde não há `TODO.md`.

**HOOKSRC-1 (obrigatório):** os ganchos **vivos** (`core.hooksPath` global ou por
usuário) devem apontar para uma **instalação PUBLICADA** -- tipicamente o
**submódulo pinado** (gitlink de uma tag/`vX.Y.Z` já testada) no repositório
consumidor, **nunca** para o checkout de desenvolvimento deste produto. Se
`core.hooksPath` apontar para a árvore de dev, código ainda não commitado
executa a cada commit do líder em qualquer projeto da máquina.

```sh
# CORRETO: path da instalacao publicada / submodulo pinado no consumidor
git config --global core.hooksPath /caminho/para/submodulo-pinado/tools/hooks

# ERRADO: checkout de desenvolvimento deste repo (nao faca)
# git config --global core.hooksPath /caminho/para/clone-dev/tab_pendencias/tools/hooks
```

Custo aceito: mudança em gancho só vale após publicar e **avançar o pin** do
submódulo. Não altere o symlink global da máquina sem ordem explícita do líder.
Detector de pin atrasado: `python3 tools/submodule_pin_drift.py` (ver seção
acima).

## Coexistência com hooks locais (encadeamento)

Um `core.hooksPath` global normalmente **sombrearia** o `.git/hooks/` próprio de
cada repo, desativando silenciosamente git-lfs, o framework pre-commit, husky
etc. Para evitar isso, `hooks/` traz **shims de pass-through** (`pre-commit`,
`prepare-commit-msg`, `commit-msg`, `post-checkout`, `post-merge`, `pre-push`)
que **delegam ao hook local** do repo (`.git/hooks/<nome>`, resolvido por
`git rev-parse --git-common-dir`, via `_chain.sh`). O `post-commit` roda o aviso
de frescor **e depois** encadeia o local.

Resultado: o aviso de frescor vale em todos os repos **e** os hooks locais
continuam funcionando. Hooks que **bloqueiam** (ex.: um `pre-commit` que falha)
continuam bloqueando: `exec` preserva args, stdin e exit code. Repos que já
definem o próprio `core.hooksPath` (ex.: husky) ignoram o global e seguem como
estão.

## Exceção anti-mdash deste repositório (MDASH-2)

O travessão tipográfico (U+2014) é célula vazia canônica do schema. Este repo
versiona o marcador [`.tab_pendencias.allow_emdash`](../.tab_pendencias.allow_emdash)
na raiz. **Checklist para o consumidor do hook `no_mdash` (vault /
`~/.claude/hooks/`):** isentar paths cujo basename de repositório seja
`tab_pendencias`, ou que contenham esse marcador na raiz. A proteção segue em
todos os outros projetos.

## Cross-platform

- **Python >= 3.11** (piso oficial, `pyproject.toml` / PYFLOOR-2).
- **Linux / macOS:** `sh` nativo executa o shim; `python3` faz o trabalho.
- **Windows:** requer o Git for Windows (traz o `bash` que roda hooks `#!/bin/sh`)
  e `python`/`python3` no PATH. O shim tenta `python3` e depois `python`.
- O output é texto puro (sem emoji) e o stderr é reconfigurado para UTF-8 com
  `errors="replace"`, então não quebra em console com encoding legado.
- Sem dependências externas (só stdlib). Onde não houver Python, o shim sai com
  código 0 e não atrapalha o commit.

## Equivalentes locais das outras camadas (referência)

- **Camada 3 local** (faxina periódica desassistida): agendador nativo do OS
  com payload Python portável: `systemd --user` timer (Linux), `launchd`
  (macOS), Task Scheduler (Windows), ou `cron`. Só necessária no caso raro
  "rodar mesmo sem commit nem sessão"; faz só higiene mecânica, **não** reordena.
- **Camada 4 local** (fonte-da-verdade offline): `git-bug` (issues em refs git,
  sem servidor) em vez de Issues do GitHub.

## Concorrencia e escrita do `--fix` (`todo_fix.py`)

- **Dry-run** (sem `--apply`): so le; **nao** pede lock.
- **`--apply`**: adquire `TodoWriteLock` (`todo_lock.py`, mesmo lock de
  intake/drain) **antes** de re-checar working tree limpa e escrever.
  Serializa dois `--fix --apply` no mesmo TODO (FIX-RISCO-A/B). Timeout
  default 10s; falha de lock = exit 1, nada escrito. Reentrante no mesmo
  thread.
- **Escrita atomica**: temp no mesmo dir + `os.replace` + tratamento
  generico de `OSError` (inclui `PermissionError`). Residual
  **FIX-RISCO-C**: no Windows, `os.replace`/MoveFileEx pode recusar
  destino com atributo somente-leitura; o CI da matrix **nao** exercita
  esse path real de plataforma -- a suíte cobre o handling generico via
  mock de `os.replace` (`test_apply_interrupcao_no_replace_*`,
  `test_apply_oserror_generico_permission_error`). Em POSIX, bits 0o444
  no arquivo-alvo **nao** bloqueiam rename (so o diretorio precisa de
  escrita).

## Testes

```sh
cd /caminho/para/este/clone && python3 -m pytest tests/ -q
```

## Pre-CI local (TST-T15)

`scripts/preci.sh`, na raiz do repo, roda localmente -- na mesma ordem dos jobs de
`.github/workflows/ci.yml` -- tudo que dá para reproduzir fora do GitHub Actions
(pytest, `shellcheck` + smoke dos shims, `markdownlint-cli2`, `gitleaks`, os guards
de `tools/ci/`), para o vermelho não aparecer só no servidor. Detalhe completo,
diferenças declaradas vs. o CI, e contrato de exit code em `TESTES.md` (TST-T15).

**Cross-platform:** é `sh` POSIX, mesma família dos shims acima (degradação
documentada, não suposição escondida, D-11/ADR-1 seção (e)) -- roda nativo em
Linux/macOS; no Windows requer Git for Windows ou WSL (o mesmo shell que os shims
já exigem). As etapas de `shellcheck` e do smoke dos shims já são Linux-only dentro
do próprio `ci.yml` (job `shellcheck-and-smoke`); este script não introduz
degradação nova, só herda a que já existe.

```sh
cd /caminho/para/este/clone && sh scripts/preci.sh
```

## Licença

GPL-3.0-or-later (ver `../LICENSE`).
