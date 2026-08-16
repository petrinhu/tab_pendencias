"""tests/test_recovery_drill.py -- TAB-VAULT-005 recovery drill mock vault."""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "recovery_drill.py")


def _load_mod():
    spec = importlib.util.spec_from_file_location("recovery_drill", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_run_drill_ok_under_tmp(tmp_path):
    RD = _load_mod()
    dest = tmp_path / "vault-mock"
    report = RD.run_drill(dest=str(dest), product_root=REPO, clean=True)
    assert report["ok"] is True
    dest_res = os.path.realpath(report["dest"])
    assert dest_res.startswith(os.path.realpath(str(tmp_path)))
    # settings + hook dentro do dest
    settings = os.path.join(dest_res, "settings.sanitized.json")
    assert os.path.isfile(settings)
    data = json.loads(open(settings, encoding="utf-8").read())
    blob = json.dumps(data)
    assert "/home/" not in blob
    assert "$HOME" not in blob
    assert "skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py" in blob
    hook = os.path.join(
        dest_res,
        "skills",
        "tab_pendencias",
        "tools",
        "hooks",
        "tab_pendencias_reminder.py",
    )
    assert os.path.isfile(hook)
    assert os.path.realpath(hook).startswith(dest_res)
    assert report["hook_continue"] is True


def test_settings_absolute_path_rejected(tmp_path):
    RD = _load_mod()
    dest = tmp_path / "bad"
    dest.mkdir()
    skill = dest / "skills" / "tab_pendencias"
    skill.mkdir(parents=True)
    # plant minimal product copies via real drill first would work; here
    # unit-test the assert helper with a forged settings file.
    hook_rel = "skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py"
    hook = dest / hook_rel
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("# fake\n", encoding="utf-8")
    settings = dest / "settings.sanitized.json"
    settings.write_text(
        json.dumps({
            "hooks": {
                "SessionStart": [{
                    "hooks": [{
                        "type": "command",
                        "command": "python3 /home/someone/.claude/hooks/x.py",
                    }]
                }]
            }
        }),
        encoding="utf-8",
    )
    with pytest.raises(RD.RecoveryDrillError):
        RD._assert_settings_paths_relative(settings, dest.resolve())


def test_cli_main_exit_0(tmp_path):
    RD = _load_mod()
    dest = tmp_path / "cli-dest"
    rc = RD.main(["--dest", str(dest), "--product-root", REPO, "--json"])
    assert rc == 0
