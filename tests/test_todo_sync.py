import os
import subprocess

import todo_sync as S


def _sha1(root):
    return subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                          cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace"
                          ).stdout.split()[0]


def _repo(tmp_path, status_v12="⏳ Pendente"):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def g(*a):
        subprocess.run(["git", *a], cwd=tmp_path, env=env,
                       capture_output=True, check=True)

    g("init", "-q")
    todo = tmp_path / "TODO.md"
    todo.write_text(
        "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
        "Dificuldade | Status | Estado Auditado |\n"
        "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
        f"| V-12 | W2 | Auth | Login | Alta | — | Média | {status_v12} | — |\n"
        "| V-20 | W3 | UI | Tela | Baixa | — | Baixa | ⏳ Pendente | — |\n",
        encoding="utf-8")
    g("add", "TODO.md")
    g("commit", "-qm", "tabela")
    return tmp_path, g, todo, _sha1(tmp_path)


def test_apply_flipa_item_citado_e_entregue(tmp_path):
    root, g, todo, base = _repo(tmp_path)
    (tmp_path / "auth.py").write_text("x")
    g("add", "auth.py")
    g("commit", "-qm", "feat: termina login V-12")
    # --since <base>: a 1a execucao sem ref semeia a base em HEAD (E2), logo a
    # janela precisa ser pedida de proposito para conter a entrega.
    rc, flip, applied = S.run(["--apply", "--since", base], root=str(root))
    assert rc == 0 and applied and flip == ["V-12"]
    txt = todo.read_text(encoding="utf-8")
    assert "🔍 Pendente verificação" in txt
    # V-20 (nao citado) intacto; nenhum ✅ injetado
    assert "| V-20 |" in txt and "⏳ Pendente" in txt
    assert "✅" not in txt


def test_propor_nao_escreve(tmp_path):
    root, g, todo, base = _repo(tmp_path)
    (tmp_path / "a.py").write_text("x")
    g("add", "a.py")
    g("commit", "-qm", "feat V-12")
    antes = todo.read_text(encoding="utf-8")
    rc, flip, applied = S.run(["--since", base], root=str(root))  # sem --apply
    assert rc == 0 and flip == ["V-12"] and not applied
    assert todo.read_text(encoding="utf-8") == antes  # nao mudou


def test_nao_flipa_item_ja_entregue(tmp_path):
    root, g, todo, base = _repo(tmp_path, status_v12="🔍 Pendente verificação")
    (tmp_path / "a.py").write_text("x")
    g("add", "a.py")
    g("commit", "-qm", "ajuste V-12")
    rc, flip, applied = S.run(["--apply", "--since", base], root=str(root))
    assert flip == []  # 🔍 ja entregue, nao re-flipa


def test_idempotente_via_ref(tmp_path):
    root, g, todo, base = _repo(tmp_path)
    (tmp_path / "a.py").write_text("x")
    g("add", "a.py")
    g("commit", "-qm", "feat V-12")
    # 1a: janela explicita -> flipa V-12 e grava o ref em HEAD
    _, flip1, _ = S.run(["--apply", "--since", base], root=str(root))
    assert flip1 == ["V-12"]
    # 2a: usa o ref, range vazio. E2 (2026-07-27): antes o range vazio caia no
    # fallback de "ref invalida" e varria o historico inteiro -- passava por
    # motivo errado (V-12 ja estava 🔍). Agora a ref e validada por rev-parse.
    rc, flip, _ = S.run(["--apply"], root=str(root))
    assert flip == []


# ---- E2: bookkeeping da tabela NAO e entrega; 1a execucao semeia baseline ----
#
# Achado no consumidor A (2026-07-27): o sync propos flipar 5 itens NAO
# entregues (L1.7-BACKENDS, L2-COMPONENTS, WM-VSYNC, GH-ONLY-GOLDEN,
# AUD-CI-RUNNER) porque commits `docs(todo)` que CRIARAM/REORDENARAM o item
# citam o ID -- indistinguivel de entrega. Duas causas somadas: (1) qualquer
# commit citante contava; (2) sem ref de sync, a 1a execucao varria os 423
# commits do historico e ressuscitava mencao de semanas atras.

def test_sync_ignora_commit_so_de_bookkeeping(tmp_path):
    """Commit que toca SO a TODO.md cita o ID mas nao entregou nada."""
    root, g, todo, base = _repo(tmp_path)
    todo.write_text(todo.read_text(encoding="utf-8") + "\n<!-- nota -->\n",
                    encoding="utf-8")
    g("add", "TODO.md")
    g("commit", "-qm", "docs(todo): cria V-12 e reordena a tabela")
    rc, flip, _ = S.run(["--since", base], root=str(root))
    assert rc == 0 and flip == [], flip


def test_sync_flipa_quando_o_commit_toca_trabalho_substantivo(tmp_path):
    """Mesmo commit, mesma citacao, mas tocando codigo -> flipa."""
    root, g, todo, base = _repo(tmp_path)
    (tmp_path / "auth.py").write_text("x")
    g("add", "auth.py")
    g("commit", "-qm", "feat: termina login V-12")
    rc, flip, _ = S.run(["--since", base], root=str(root))
    assert flip == ["V-12"], flip


def test_sync_primeira_execucao_nao_varre_o_historico(tmp_path):
    """Sem ref de sync, a linha de base e HEAD -- nao ressuscita o passado."""
    root, g, todo, _ = _repo(tmp_path)
    (tmp_path / "auth.py").write_text("x")
    g("add", "auth.py")
    g("commit", "-qm", "feat: termina login V-12")
    rc, flip, _ = S.run([], root=str(root))
    assert rc == 0 and flip == [], flip


def test_sync_apos_semear_baseline_flipa_o_que_vem_depois(tmp_path):
    """--apply na 1a execucao grava a baseline; entrega POSTERIOR flipa."""
    root, g, todo, _ = _repo(tmp_path)
    (tmp_path / "old.py").write_text("x")
    g("add", "old.py")
    g("commit", "-qm", "feat: entrega antiga V-12")
    S.run(["--apply"], root=str(root))              # semeia baseline, nada flipa
    assert "🔍" not in todo.read_text(encoding="utf-8")
    (tmp_path / "ui.py").write_text("y")
    g("add", "ui.py")
    g("commit", "-qm", "feat: termina a tela V-20")
    rc, flip, applied = S.run(["--apply"], root=str(root))
    assert flip == ["V-20"] and applied, flip


def test_sync_since_explicito_ainda_varre_o_passado(tmp_path):
    """A valvula de escape continua: --since <ref> le o passado de proposito."""
    root, g, todo, base = _repo(tmp_path)
    (tmp_path / "auth.py").write_text("x")
    g("add", "auth.py")
    g("commit", "-qm", "feat: termina login V-12")
    S.run(["--apply"], root=str(root))              # baseline em HEAD
    rc, flip, _ = S.run(["--since", base], root=str(root))
    assert flip == ["V-12"], flip


def test_range_vazio_nao_cai_no_fallback_de_historico(tmp_path):
    """Range vazio (o caso comum) nao pode ser confundido com ref invalida.

    Lacuna achada por teste de mutacao (2026-07-27): reverter a validacao por
    rev-parse passava a suite inteira, porque o test_idempotente_via_ref da o
    mesmo resultado nos dois mundos (o item ja estava 🔍). Aqui V-20 e entregue
    por commit de codigo mas o Status NAO e sincronizado, e a base fica em HEAD:
    o comportamento certo (range vazio) nao flipa nada; o fallback varrendo o
    historico fliparia V-20.
    """
    root, g, todo, base = _repo(tmp_path)
    (tmp_path / "ui.py").write_text("x")
    g("add", "ui.py")
    g("commit", "-qm", "feat: termina a tela V-20")
    _, flip1, _ = S.run(["--apply"], root=str(root))   # 1a: semeia base em HEAD
    assert flip1 == [] and "🔍" not in todo.read_text(encoding="utf-8")
    # ref gravada, nada novo desde ela -> janela vazia, nada a propor
    rc, flip, _ = S.run([], root=str(root))
    assert flip == [], f"caiu no fallback e varreu o historico: {flip}"
