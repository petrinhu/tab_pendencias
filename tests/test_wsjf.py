"""tests/test_wsjf.py -- motor WSJF (TAB-WSJF-001..007 / Gate WSJF-3).

Fixtures sintéticas, IDs #NN, prosa EN. Asserções de escala usam o literal
(1, 2, 3, 5, 8, 13, 20) no teste, nunca W.FIB_SCALE (mutation).
"""
from __future__ import annotations

import os

import pytest

import wsjf as W


# ---------------------------------------------------------------------------
# escala + normalize + fórmula
# ---------------------------------------------------------------------------

def test_fib_scale_is_vault_canonical():
    assert W.FIB_SCALE == (1, 2, 3, 5, 8, 13, 20)


def test_normalize_reject_keeps_fib_and_drops_linear():
    for n in (1, 2, 3, 5, 8, 13, 20):
        assert W.normalize_score(n, mode="reject") == n
        assert W.normalize_score(str(n), mode="reject") == n
    for n in (4, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19):
        assert W.normalize_score(n, mode="reject") is None


def test_normalize_snap_nearest_and_tie_goes_down():
    assert W.normalize_score(4, mode="snap") == 3
    assert W.normalize_score(6, mode="snap") == 5
    assert W.normalize_score(10, mode="snap") == 8
    assert W.normalize_score(16, mode="snap") == 13
    for bad in (0, 21, -1, None, True, "urgente"):
        assert W.normalize_score(bad, mode="snap") is None
    assert W.normalize_score(False, mode="snap") is None


def test_cost_of_delay_sum():
    assert W.cost_of_delay(8, 5, 3) == 16


def test_wsjf_divides():
    assert W.wsjf(16, 8) == 2.0
    assert W.wsjf(16, 5) == 3.2


def test_wsjf_rejects_non_positive_job_size():
    with pytest.raises(ValueError, match="job_size must be > 0"):
        W.wsjf(16, 0)
    with pytest.raises(ValueError, match="job_size must be > 0"):
        W.wsjf(16, -1)


# ---------------------------------------------------------------------------
# labels, profiles, bus, score_row
# ---------------------------------------------------------------------------

def test_early_label_map_alta_media_baixa():
    assert W.label_to_fib("Alta") == 8
    assert W.label_to_fib("Média") == 5
    assert W.label_to_fib("Media") == 5
    assert W.label_to_fib("Baixa") == 2
    assert W.label_to_fib("High") == 8
    assert W.label_to_fib("Medium") == 5
    assert W.label_to_fib("Low") == 2
    assert W.label_to_fib("urgente") is None
    assert W.label_to_fib("quando der") is None


def test_safe_profile_ignores_labels():
    row = W.score_row(
        W.WsjfInputs(
            item_id="#01",
            priority_label="Alta",
            difficulty_label="Baixa",
            time_criticality=5,
            risk_reduction=3,
        ),
        profile="safe",
    )
    assert row["scored"] is False
    assert row["bv"] is None
    assert row["job_size"] is None


def test_bus_source_ignores_rhetorical_labels():
    for lab in ("Alta", "urgente"):
        row = W.score_row(
            W.WsjfInputs(
                item_id="#b",
                priority_label=lab,
                difficulty_label="Baixa",
                source="bus",
            ),
            profile="early",
        )
        assert row["scored"] is False
        assert row["bv"] is None


def test_bus_source_accepts_explicit_fib_ints():
    row = W.score_row(
        W.WsjfInputs(
            item_id="#b",
            business_value=8,
            time_criticality=5,
            risk_reduction=3,
            job_size=5,
            source="bus",
        ),
        profile="early",
    )
    assert row["scored"] is True
    assert row["cod"] == 16
    assert row["wsjf"] == pytest.approx(3.2)


def test_score_row_absent_when_tc_missing_even_in_early():
    row = W.score_row(
        W.WsjfInputs(
            item_id="#01",
            business_value=8,
            risk_reduction=3,
            job_size=5,
            priority_label="Alta",
        ),
        profile="early",
    )
    assert row["scored"] is False
    assert row["tc"] is None
    assert row["wsjf"] is None


# ---------------------------------------------------------------------------
# topologia + rank estável + explain
# ---------------------------------------------------------------------------

def test_topology_before_wsjf_a_before_b():
    levels = {"A": 0, "B": 1}
    prev = ["A", "B"]
    assert W.topology_before_wsjf(levels, prev) == ["A", "B"]
    # even if previous put B first, level 0 wins
    assert W.topology_before_wsjf(levels, ["B", "A"]) == ["A", "B"]


def test_order_levels_then_wsjf_does_not_promote_across_levels():
    levels = {"A": 0, "C": 0, "B": 1}
    prev = ["A", "B", "C"]
    scores = {
        "A": {"id": "A", "wsjf": 4.0, "scored": True},
        "C": {"id": "C", "wsjf": 1.0, "scored": True},
        "B": {"id": "B", "wsjf": 100.0, "scored": True},
    }
    ordered = W.order_levels_then_wsjf(levels, prev, scores, 0.0)
    # level 0 (A, C) before level 1 (B); within L0 A before C by score
    assert ordered.index("A") < ordered.index("B")
    assert ordered.index("C") < ordered.index("B")
    assert ordered == ["A", "C", "B"]


def test_stable_rank_tie_preserves_previous_order():
    items = [
        {"id": "X", "wsjf": 5.0, "scored": True},
        {"id": "Y", "wsjf": 5.0, "scored": True},
    ]
    assert W.stable_rank_within_level(items, ["X", "Y"], 0.0) == ["X", "Y"]


def test_stable_rank_comparable_epsilon_no_churn():
    items = [
        {"id": "X", "wsjf": 8.2, "scored": True},
        {"id": "Y", "wsjf": 8.6, "scored": True},
    ]
    assert W.stable_rank_within_level(items, ["X", "Y"], 0.5) == ["X", "Y"]


def test_stable_rank_material_delta_swaps():
    items = [
        {"id": "X", "wsjf": 2.0, "scored": True},
        {"id": "Y", "wsjf": 13.0, "scored": True},
    ]
    assert W.stable_rank_within_level(items, ["X", "Y"], 0.5) == ["Y", "X"]


def test_stable_rank_missing_score_keeps_previous():
    items = [
        {"id": "X", "wsjf": 13.0, "scored": True},
        {"id": "Y", "wsjf": None, "scored": False},
    ]
    assert W.stable_rank_within_level(items, ["X", "Y"], 0.0) == ["X", "Y"]


def test_stable_rank_pinned_wip_not_overtaken():
    items = [
        {"id": "Y", "wsjf": 2.0, "scored": True},
        {"id": "X", "wsjf": 20.0, "scored": True},
    ]
    # Y pinado na frente; X com WSJF maior nao ultrapassa
    out = W.stable_rank_within_level(
        items, ["Y", "X"], 0.0, pinned={"Y"},
    )
    assert out == ["Y", "X"]


def test_stable_rank_is_deterministic():
    items = [
        {"id": "A", "wsjf": 8.0, "scored": True},
        {"id": "B", "wsjf": 13.0, "scored": True},
        {"id": "C", "wsjf": 5.0, "scored": True},
    ]
    prev = ["A", "B", "C"]
    first = W.stable_rank_within_level(items, prev, 0.5)
    for _ in range(19):
        assert W.stable_rank_within_level(items, prev, 0.5) == first


def test_explain_move_exact_format():
    text = W.explain_move(
        "#B", "W2", "W1",
        "WSJF 13.0 > peer #A 2.0",
        "peer_scores fornecidos para #A,#B",
    )
    lines = text.splitlines()
    assert len(lines) == 3
    assert lines[0] == "ITEM #B: W2 -> W1"
    assert lines[1].startswith("causa: ")
    assert lines[2].startswith("input_material_que_mudou: ")


def test_resolve_wsjf_config_ini_and_default(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# x\n", encoding="utf-8")
    prof, eps, origin = W.resolve_wsjf_config(todo_path=str(todo))
    assert prof == "early"
    assert eps == 0.5
    assert "default" in origin

    ini = tmp_path / ".tab_pendencias.ini"
    ini.write_text(
        "[wsjf]\nprofile = safe\ncomparable_epsilon = 0.0\n",
        encoding="utf-8",
    )
    prof2, eps2, origin2 = W.resolve_wsjf_config(todo_path=str(todo))
    assert prof2 == "safe"
    assert eps2 == 0.0
    assert "ini" in origin2

    prof3, eps3, origin3 = W.resolve_wsjf_config(
        profile="early", comparable_epsilon=0.25, todo_path=str(todo),
    )
    assert prof3 == "early"
    assert eps3 == 0.25
    assert "arg" in origin3

    prof4, _, origin4 = W.resolve_wsjf_config(profile="bogus")
    assert prof4 == "early"
    assert "invalid" in origin4 or "degraded" in origin4
