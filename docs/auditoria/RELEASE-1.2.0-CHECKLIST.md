# Checklist Fase 12 — release 1.2.0

**Status:** prep local fechada. **AGUARDANDO AUTORIZAÇÃO DO LÍDER** para push/tag remota
e pin no consumidor (se ainda não estiverem no remoto que você confere).

Medido na sessão de fechamento da campanha (remeça antes de autorizar).

## TAB-REL-001 — medir (pode repetir)

```bash
cd /home/petrus/IDrive/Documentos/projetos_claudebrain/Projects/tab_pendencias
git fetch --all --prune
git status --short
git log --oneline --decorate -n 20
git rev-parse HEAD
git rev-parse origin/main
git ls-remote origin refs/heads/main refs/tags/v1.2.0
```

Critério: nunca presumir SHA do plano; só o `ls-remote` conta.

## TAB-REL-002 — publicar produto

**AGUARDANDO AUTORIZAÇÃO DO LÍDER.**

Quando autorizar:

1. `git push origin main` (se local à frente do remoto)
2. `git ls-remote origin refs/heads/main` == `git rev-parse HEAD`
3. Observar CI multi-OS 9/9 no SHA
4. Se tag ainda não no remoto ou quiser retag de patch: `git push origin v1.2.0` / release notes
5. Testar instalação a partir do **remoto**, não só checkout local

## TAB-REL-003 — pin submodule claude-memory

**AGUARDANDO AUTORIZAÇÃO DO LÍDER.** Este repo **não** edita o consumidor sozinho.

Bloco pronto para colar (ajuste SHA se `main` avançou):

```bash
# SHA do produto a pinar (exemplo da campanha; remeça):
# git -C /path/to/tab_pendencias rev-parse HEAD

cd ~/.claude   # ou clone de claude-memory
cd skills/tab_pendencias
git fetch origin --tags
git checkout -f <SHA_OU_TAG_v1.2.x>
cd ../..
git add skills/tab_pendencias
git commit -m "chore(submodule): pin tab_pendencias <tag/SHA> (TAB-REL-003)"
git push github main
git ls-remote github refs/heads/main
git submodule status skills/tab_pendencias
```

Depois: recovery drill / SessionStart apontando para
`skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py`.

## TAB-REL-004 — clone fresco

**Depende de REL-003.** Quando autorizado:

```bash
rm -rf /var/tmp/claude-memory-fresh-test
git clone --recursive git@github.com:petrinhu/claude-memory.git /var/tmp/claude-memory-fresh-test
# provar: skill + toolkit + hook + dry-run intake
```

Se rede/credencial falhar: reportar honesto, não inventar PASS.
