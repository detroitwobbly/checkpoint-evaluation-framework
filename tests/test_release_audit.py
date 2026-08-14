from pathlib import Path

from scripts.release_audit import audit


def test_release_tree_has_no_audit_errors():
    root = Path(__file__).resolve().parents[1]

    result = audit(root)

    assert result["errors"] == []
    assert result["warnings"] == []
