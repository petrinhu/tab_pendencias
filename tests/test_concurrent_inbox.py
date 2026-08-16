"""tests/test_concurrent_inbox.py -- TAB-CONC-002 inbox/ concorrente."""
from __future__ import annotations

import os

import concurrent_inbox as CI


def test_write_discovery_path_shape(tmp_path):
    body = (
        "DISCOVERED_WORK\n"
        "source_item: A\n"
        "description: Hatch latch found in review\n"
        "evidence: x.py:1\n"
        "known_dependencies: unknown\n"
        "blast_radius: local\n"
    )
    path = CI.write_discovery(
        str(tmp_path),
        session_id="sess/1",
        slug="hatch latch!",
        body_md=body,
        timestamp="20260816-120000",
    )
    assert path.endswith(".md")
    name = os.path.basename(path)
    assert name.startswith("20260816-120000-")
    assert "sess-1" in name or "sess_1" in name or "sess" in name
    assert "hatch" in name
    assert "!" not in name
    assert os.path.isfile(path)
    text = open(path, encoding="utf-8").read()
    assert "Hatch latch" in text
    assert text.endswith("\n")


def test_sanitize_slug_reserved_and_empty():
    assert CI.sanitize_slug("CON") == "CON_"
    assert CI.sanitize_slug("  ") == "item"
    assert CI.sanitize_slug("a/b:c") == "a-b-c"


def test_list_pending_and_count(tmp_path):
    assert CI.list_pending(str(tmp_path)) == []
    assert CI.count_pending(str(tmp_path)) == 0
    CI.write_discovery(str(tmp_path), "s1", "one", "a\n", timestamp="20260101-010101")
    CI.write_discovery(str(tmp_path), "s2", "two", "b\n", timestamp="20260101-010102")
    # lixo
    (tmp_path / "inbox" / "note.txt").write_text("x", encoding="utf-8")
    (tmp_path / "inbox" / ".hidden.md").write_text("x", encoding="utf-8")
    pending = CI.list_pending(str(tmp_path))
    assert len(pending) == 2
    assert CI.count_pending(str(tmp_path)) == 2
    assert all(p.endswith(".md") for p in pending)
    assert pending == sorted(pending)


def test_write_collision_suffix(tmp_path):
    p1 = CI.write_discovery(
        str(tmp_path), "s", "slug", "one\n", timestamp="20260101-000000"
    )
    p2 = CI.write_discovery(
        str(tmp_path), "s", "slug", "two\n", timestamp="20260101-000000"
    )
    assert p1 != p2
    assert os.path.isfile(p1) and os.path.isfile(p2)


def test_read_discovery_with_discovered_work(tmp_path):
    body = (
        "DISCOVERED_WORK\n"
        "source_item: #01\n"
        "description: Wire concurrent inbox\n"
        "evidence: plan:1\n"
        "known_dependencies: unknown\n"
        "blast_radius: component\n"
    )
    path = CI.write_discovery(
        str(tmp_path), "main", "wire", body, timestamp="20260816-180000"
    )
    info = CI.read_discovery(path)
    assert info["path"] == os.path.abspath(path)
    assert len(info["discovered"]) == 1
    assert "Wire concurrent" in info["discovered"][0]["description"]
    assert info["discovered"][0]["blast_radius"] == "component"


def test_read_discovery_frontmatter(tmp_path):
    body = (
        "---\n"
        "session: abc\n"
        "source: agent\n"
        "---\n"
        "DISCOVERED_WORK\n"
        "description: With frontmatter\n"
        "blast_radius: unknown\n"
    )
    path = CI.write_discovery(
        str(tmp_path), "abc", "fm", body, timestamp="20260816-190000"
    )
    info = CI.read_discovery(path)
    assert info["frontmatter"].get("session") == "abc"
    assert len(info["discovered"]) == 1
