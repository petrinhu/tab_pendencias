"""tests/test_bus_contract.py -- TAB-BUS-001..004 (fatos, nao ranking).

Corpus em tests/corpus/bus/ (consumer-a, prosa EN). claimed_priority /
"urgente" nunca pontuam; time_criticality so com int fib explicito.
"""
from __future__ import annotations

import json
import os

import bus_contract as B

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "tests", "corpus", "bus")


def _load(name: str) -> dict:
    path = os.path.join(CORPUS, name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_fib_scale_literal_in_module():
    assert B.FIB_SCALE == (1, 2, 3, 5, 8, 13, 20)


def test_extract_facts_ignores_claimed_priority_urgente():
    data = _load("consumer_a_urgent_rhetoric.json")
    facts = B.extract_facts(data)
    assert facts["need"] == "add pagination to the list endpoint"
    assert facts["claimed_priority"] == "urgente"
    assert facts["rhetorical_priority_ignored"] is True
    assert facts["time_criticality"] is None
    assert facts["sender"] == "consumer-a"


def test_extract_facts_accepts_explicit_fib_tc():
    data = _load("consumer_a_explicit_fib_tc.json")
    facts = B.extract_facts(data)
    assert facts["time_criticality"] == 8
    assert facts["business_value"] == 5
    assert facts["risk_reduction"] == 3
    assert facts["job_size"] == 2
    # claimed "high" still ignored for scoring path
    assert facts["rhetorical_priority_ignored"] is True
    assert facts["dependencies"] == ["API-40"]


def test_extract_facts_rejects_rhetorical_tc_string():
    data = _load("consumer_a_missing_fields.json")
    facts = B.extract_facts(data)
    assert facts["time_criticality"] is None
    # "urgente" as tc string never becomes fib
    assert B._as_fib_int("urgente") is None
    assert B._as_fib_int(4) is None
    assert B._as_fib_int(8) == 8


def test_candidate_from_bus_source_and_empty_prioridade():
    data = _load("consumer_a_urgent_rhetoric.json")
    cand = B.candidate_from_bus(data)
    assert cand["source"] == "bus"
    assert cand["prioridade"] == ""
    assert cand["candidate_id"] == "bus-ca-001"
    assert cand["item_id"] == "API-42"
    assert "urgente" not in (cand["prioridade"] or "").casefold()
    assert cand["time_criticality"] is None
    assert "pagination" in cand["description"].casefold()


def test_candidate_from_bus_carries_explicit_scores_only():
    data = _load("consumer_a_explicit_fib_tc.json")
    cand = B.candidate_from_bus(data, is_local=True)
    assert cand["source"] == "bus"
    assert cand["time_criticality"] == 8
    assert cand["bv"] == 5
    assert cand["prioridade"] == ""  # not "high"
    assert cand["is_local"] is True
    kwargs = B.work_candidate_kwargs(cand)
    assert "source" in kwargs and kwargs["source"] == "bus"
    assert "_bus_message_id" not in kwargs


def test_archive_allowed_trackable_routes():
    assert B.archive_allowed("DUPLICATE") is True
    assert B.archive_allowed("LOCAL_INTEGRATION", applied=True) is True
    assert B.archive_allowed("LOCAL_INTEGRATION", applied=False) is False
    assert B.archive_allowed("NEEDS_TRIAGE", applied=True) is True
    assert B.archive_allowed("NEEDS_LEADER_DECISION", applied=True) is True
    assert B.archive_allowed("FULL_REORDER", applied=False) is False
    assert B.archive_allowed(None) is False
    assert B.archive_allowed("LOCAL_INTEGRATION", applied=True, error="x") is False
    assert B.archive_allowed(None, requires_work=False) is True


def test_bus_message_from_dict_and_dataclass_roundtrip():
    data = _load("consumer_a_explicit_fib_tc.json")
    msg = B.bus_message_from_dict(data)
    assert msg.message_id == "ca-2026-08-02-014"
    facts = B.extract_facts(msg)
    assert facts["time_criticality"] == 8
