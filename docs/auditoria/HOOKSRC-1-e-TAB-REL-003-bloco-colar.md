# Bloco colavel -- pin Claude skill + githooks publicados (HOOKSRC-1 / TAB-REL-003)

**Estado na maquina do lider apos sessao 16/08 (local):**
- Produto e skill Claude em `5d42412`
- `~/.claude/githooks` -> `~/.claude/skills/tab_pendencias/tools/hooks` (publicado)
- `git config --global core.hooksPath` = `~/.claude/githooks`
- **Gitlink no repo `claude-memory` ainda pode apontar SHA antigo** ate commit+push no consumidor

## 1) Atualizar working tree da skill (ja feito localmente; re-rodavel)

```bash
cd ~/.claude/skills/tab_pendencias
git fetch origin
git checkout -f 5d424123e7636c975f3bfe4002befefbb403d15b
git rev-parse HEAD
# esperado: 5d424123e7636c975f3bfe4002befefbb403d15b
```

## 2) Commit do gitlink no claude-memory (PRECISA autorizacao do lider)

```bash
cd ~/.claude
git status skills/tab_pendencias
git add skills/tab_pendencias
git commit -m "chore(submodule): pin tab_pendencias 5d42412 (TAB-REL-003 / HOOKSRC-1)"
# SO com autorizacao:
# git push github main
# git ls-remote github refs/heads/main
git submodule status skills/tab_pendencias
```

## 3) Githooks (local; sem push)

```bash
ln -sfn "$HOME/.claude/skills/tab_pendencias/tools/hooks" "$HOME/.claude/githooks"
git config --global core.hooksPath "$HOME/.claude/githooks"
readlink -f ~/.claude/githooks
# esperado: .../.claude/skills/tab_pendencias/tools/hooks
git config --global core.hooksPath
```

## 4) Nota nested clone

O path `~/.claude/skills/tab_pendencias` e um checkout do submodulo (gitlink no
`.gitmodules`). Se `git submodule status` mostrar SHA diferente do `rev-parse`
dentro do dir, o **gitlink commitado** ainda nao foi atualizado -- o runtime
local ja usa o checkout novo, mas clone fresco do vault so pega o pin apos
passo 2.
