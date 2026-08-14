from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import TestSuite


def load_suite(path: Path) -> TestSuite:
    data = _load_mapping(path)
    suite = TestSuite.from_mapping(data)
    if not suite.checkpoints:
        raise ValueError("Manifest must define at least one checkpoint.")
    if not suite.tests:
        raise ValueError("Manifest must define at least one test.")
    return suite


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("YAML manifests require PyYAML. Use JSON or install PyYAML.") from exc
        loaded = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    else:
        raise ValueError("Manifest must be .json, .yaml, or .yml.")
    if not isinstance(loaded, dict):
        raise TypeError("Manifest root must be an object.")
    return loaded
