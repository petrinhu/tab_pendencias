import os
import sys

# Permite `import todo_lib` / `import todo_sync` / etc. ao rodar pytest de
# qualquer cwd: os modulos moram em tools/ (layout monorepo), um nivel acima
# de tests/, nao no mesmo diretorio (diferenca do antigo ~/.claude/githooks/,
# onde tudo ficava plano no mesmo dir das tests).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
