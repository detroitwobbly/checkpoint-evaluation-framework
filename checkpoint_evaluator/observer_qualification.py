from __future__ import annotations

import json
import math
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


def build_observer_qualification(
    analyses: list[tuple[str, str, Path]],
    output_root: Path,
    reference_set: Path | None = None,
    title: str = "CEF Observer Qualification Report",
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    loaded = _merge_observers([_load_observer(analysis_id, label, path) for analysis_id, label, path in analyses])
    reference = _load_reference_set(reference_set) if reference_set else {}
    observation_sets = {item["analysis_id"]: _observation_keys(item["records"]) for item in loaded}
    cards = [_observer_card(item, observation_sets) for item in loaded]
    report = {
        "title": title,
        "schema_version": "1.0",
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "reference_set": reference,
        "summary": _summary(cards),
        "observer_cards": cards,
        "production_roster": _production_roster(cards),
        "methodology": {
            "professions": {
                "observer": "Answers what is visibly present, with evidence and uncertainty. Does not set the official score.",
                "judge": "Assigns score/pass/confidence against the test specification. Must obey numeric scales.",
                "review_auditor": "Reviews observer/judge reports without seeing the image and flags unsupported claims or process failures.",
            },
            "scale_contract": {
                "overall_score": "0-10",
                "evaluator_confidence": "0-1",
            },
            "qualification_principle": "Models receive role licenses and restrictions rather than a single winner/ranking.",
        },
    }
    (output_root / "observer_qualification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "observer_qualification.md").write_text(_markdown(report), encoding="utf-8")
    (output_root / "observer_qualification.html").write_text(_html(report), encoding="utf-8")
    return report


def _load_observer(analysis_id: str, label: str, path: Path) -> dict[str, Any]:
    analysis = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(analysis, dict):
        raise TypeError(f"Analysis index root must be an object: {path}")
    records = analysis.get("records", [])
    if not isinstance(records, list):
        raise TypeError(f"Analysis records must be a list: {path}")
    metadata_path = path.parent / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        loaded_metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if isinstance(loaded_metadata, dict):
            metadata = loaded_metadata
    return {
        "analysis_id": _safe_id(analysis_id),
        "label": label,
        "paths": [str(path)],
        "metadata": metadata,
        "analysis": analysis,
        "records": records,
    }


def _merge_observers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        analysis_id = item["analysis_id"]
        if analysis_id not in merged:
            merged[analysis_id] = item
            continue
        target = merged[analysis_id]
        if item["label"] and item["label"] != analysis_id:
            target["label"] = item["label"]
        target["paths"].extend(item["paths"])
        target["records"].extend(item["records"])
        if not target.get("metadata") and item.get("metadata"):
            target["metadata"] = item["metadata"]
    return list(merged.values())


def _load_reference_set(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Reference set root must be an object: {path}")
    loaded.setdefault("path", str(path))
    return loaded


def _observer_card(item: dict[str, Any], observation_sets: dict[str, set[str]]) -> dict[str, Any]:
    records = item["records"]
    total = len(records)
    numeric_scores = [_to_float(record.get("overall_score")) for record in records]
    numeric_scores = [score for score in numeric_scores if score is not None]
    confidences = [_to_float(record.get("evaluator_confidence")) for record in records]
    confidences = [confidence for confidence in confidences if confidence is not None]
    score_compliance = _range_compliance(numeric_scores, 0, 10)
    confidence_compliance = _range_compliance(confidences, 0, 1)
    pass_counts = _pass_counts(records)
    observation_count = sum(_observation_count(record) for record in records)
    wildcard_count = sum(len(record.get("wildcard_observations", []) or []) for record in records)
    semantic_count = sum(len(record.get("semantic_observations", []) or []) for record in records)
    conflicts = _score_pass_conflicts(records)
    evaluator_failures = _evaluator_failure_count(records)
    conditional_rate = pass_counts.get("conditional_pass", 0) / total if total else 0
    observer_set = observation_sets.get(item["analysis_id"], set())
    other_sets = set().union(*(values for key, values in observation_sets.items() if key != item["analysis_id"]))
    novel = observer_set - other_sets
    restrictions = _restrictions(score_compliance, confidence_compliance, conflicts, total, conditional_rate, evaluator_failures)
    qualified_roles = _qualified_roles(
        total=total,
        score_compliance=score_compliance,
        confidence_compliance=confidence_compliance,
        observation_density=_density(observation_count, total),
        score_pass_conflict_rate=_density(conflicts, total),
        evaluator_failure_rate=_density(evaluator_failures, total),
        conditional_rate=conditional_rate,
    )
    return {
        "analysis_id": item["analysis_id"],
        "label": item["label"],
        "model_name": item["metadata"].get("model_name", ""),
        "endpoint": item["metadata"].get("endpoint", ""),
        "directive_used": item["metadata"].get("directive_used", ""),
        "analysis_paths": item["paths"],
        "records": total,
        "raw_average_score": _average(numeric_scores),
        "normalized_average_score": _normalized_average(numeric_scores),
        "average_confidence": _average(confidences),
        "scale_compliance": {
            "overall_score_0_10": score_compliance,
            "evaluator_confidence_0_1": confidence_compliance,
        },
        "pass_fail_counts": pass_counts,
        "conditional_pass_rate": round(conditional_rate, 4),
        "observation_density": {
            "all": _density(observation_count, total),
            "wildcard": _density(wildcard_count, total),
            "semantic": _density(semantic_count, total),
        },
        "score_pass_conflicts": conflicts,
        "evaluator_failures": evaluator_failures,
        "independence": {
            "novel_observation_count": len(novel),
            "observation_count": len(observer_set),
            "novel_observation_rate": round(len(novel) / len(observer_set), 4) if observer_set else 0,
            "supported_novel_observation_rate": None,
            "note": "Supported novelty requires human or panel acceptance; v1 only measures lexical uniqueness.",
        },
        "qualified_roles": qualified_roles,
        "not_qualified": _not_qualified(qualified_roles),
        "restrictions": restrictions,
        "observer_character": _observer_character(score_compliance, confidence_compliance, conditional_rate, _density(observation_count, total)),
    }


def _summary(cards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "observer_count": len(cards),
        "judge_qualified": [card["label"] for card in cards if "judge" in card["qualified_roles"]],
        "observer_qualified": [card["label"] for card in cards if "observer" in card["qualified_roles"]],
        "restricted_scoring": [card["label"] for card in cards if any("score" in item.lower() for item in card["restrictions"])],
    }


def _production_roster(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roster = []
    for card in cards:
        role = "Advisory observer"
        if "judge" in card["qualified_roles"]:
            role = "Candidate judge"
        elif "technical_observer" in card["qualified_roles"]:
            role = "Technical observer"
        elif "observer" in card["qualified_roles"]:
            role = "Grounding observer"
        roster.append(
            {
                "observer_id": card["analysis_id"],
                "label": card["label"],
                "role": role,
                "restrictions": card["restrictions"],
            }
        )
    return roster


def _qualified_roles(
    *,
    total: int,
    score_compliance: float,
    confidence_compliance: float,
    observation_density: float,
    score_pass_conflict_rate: float,
    evaluator_failure_rate: float,
    conditional_rate: float,
) -> list[str]:
    roles = []
    if total and evaluator_failure_rate <= 0.05 and observation_density >= 0.2:
        roles.append("observer")
    if total and observation_density >= 0.35:
        roles.append("technical_observer")
    if (
        total
        and score_compliance >= 0.98
        and confidence_compliance >= 0.98
        and score_pass_conflict_rate <= 0.1
        and evaluator_failure_rate <= 0.02
        and conditional_rate <= 0.65
    ):
        roles.append("judge")
    if not roles:
        roles.append("advisory_only")
    return roles


def _not_qualified(qualified_roles: list[str]) -> list[str]:
    options = {"observer", "technical_observer", "judge"}
    return sorted(options - set(qualified_roles))


def _restrictions(
    score_compliance: float,
    confidence_compliance: float,
    conflicts: int,
    total: int,
    conditional_rate: float,
    evaluator_failures: int,
) -> list[str]:
    restrictions = []
    if score_compliance < 0.98:
        restrictions.append("No official scoring until overall_score scale compliance is fixed.")
    if confidence_compliance < 0.98:
        restrictions.append("Do not use evaluator_confidence quantitatively until confidence scale compliance is fixed.")
    if total and conflicts / total > 0.1:
        restrictions.append("Score/pass calibration requires review before judge use.")
    if conditional_rate > 0.65:
        restrictions.append("High conditional_pass bias; treat pass/fail state as advisory.")
    if total and evaluator_failures / total > 0.02:
        restrictions.append("Evaluator failure rate is too high for unattended production use.")
    if not restrictions:
        restrictions.append("No v1 restrictions.")
    return restrictions


def _observer_character(score_compliance: float, confidence_compliance: float, conditional_rate: float, observation_density: float) -> list[str]:
    traits = []
    if score_compliance < 0.98:
        traits.append("scale_noncompliant")
    if confidence_compliance < 0.98:
        traits.append("confidence_scale_noncompliant")
    if conditional_rate > 0.65:
        traits.append("conditional_pass_biased")
    if observation_density >= 0.75:
        traits.append("observation_dense")
    elif observation_density < 0.25:
        traits.append("observation_sparse")
    if not traits:
        traits.append("procedure_compliant")
    return traits


def _range_compliance(values: list[float], low: float, high: float) -> float:
    if not values:
        return 0
    return round(sum(1 for value in values if low <= value <= high) / len(values), 4)


def _normalized_average(values: list[float]) -> float | None:
    if not values:
        return None
    high = max(values)
    if high <= 10:
        return _average(values)
    if high <= 100:
        return round(sum(value / 10 for value in values) / len(values), 2)
    return None


def _pass_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "conditional_pass": 0, "fail": 0, "unknown": 0}
    for record in records:
        raw = str(record.get("pass_fail") or "").lower().replace("-", "_").replace(" ", "_")
        if "conditional" in raw:
            key = "conditional_pass"
        elif "fail" in raw:
            key = "fail"
        elif "pass" in raw:
            key = "pass"
        else:
            key = "unknown"
        counts[key] += 1
    return counts


def _score_pass_conflicts(records: list[dict[str, Any]]) -> int:
    conflicts = 0
    for record in records:
        score = _to_float(record.get("overall_score"))
        if score is None:
            continue
        normalized_score = score / 10 if score > 10 and score <= 100 else score
        state = str(record.get("pass_fail") or "").lower()
        if normalized_score >= 7 and state == "fail":
            conflicts += 1
        elif normalized_score < 6 and state == "pass":
            conflicts += 1
        elif normalized_score >= 8 and "conditional" in state:
            conflicts += 1
    return conflicts


def _evaluator_failure_count(records: list[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        tags = [str(tag).lower() for tag in record.get("recommended_tags", []) or []]
        text = " ".join(str(item).lower() for item in record.get("warnings", []) or [])
        if "evaluator_failure" in tags or "json_failure" in tags or "evaluator output failed" in text:
            count += 1
    return count


def _observation_count(record: dict[str, Any]) -> int:
    return len(record.get("wildcard_observations", []) or []) + len(record.get("semantic_observations", []) or [])


def _observation_keys(records: list[dict[str, Any]]) -> set[str]:
    keys = set()
    for record in records:
        for field in ("wildcard_observations", "semantic_observations"):
            for item in record.get(field, []) or []:
                if not isinstance(item, dict):
                    continue
                category = str(item.get("category") or "other")
                observation = _normalize_text(str(item.get("observation") or ""))
                if observation:
                    keys.add(f"{category}:{observation}")
    return keys


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", value.lower())).strip()


def _density(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _safe_id(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in safe.split("_") if part) or "observer"


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"- schema_version: {report['schema_version']}",
        f"- built_at: {report['built_at']}",
        f"- observer_count: {report['summary']['observer_count']}",
        "",
        "## Production Roster",
        "",
    ]
    for item in report["production_roster"]:
        lines.extend(
            [
                f"### {item['label']}",
                f"- observer_id: {item['observer_id']}",
                f"- role: {item['role']}",
                "- restrictions:",
            ]
        )
        lines.extend(f"  - {restriction}" for restriction in item["restrictions"])
        lines.append("")
    lines.append("## Observer Cards")
    lines.append("")
    for card in report["observer_cards"]:
        lines.extend(
            [
                f"### {card['label']}",
                f"- qualified_roles: {', '.join(card['qualified_roles'])}",
                f"- not_qualified: {', '.join(card['not_qualified'])}",
                f"- raw_average_score: {card['raw_average_score']}",
                f"- normalized_average_score: {card['normalized_average_score']}",
                f"- average_confidence: {card['average_confidence']}",
                f"- score_scale_compliance: {card['scale_compliance']['overall_score_0_10']}",
                f"- confidence_scale_compliance: {card['scale_compliance']['evaluator_confidence_0_1']}",
                f"- conditional_pass_rate: {card['conditional_pass_rate']}",
                f"- observation_density: {card['observation_density']['all']}",
                f"- novel_observation_rate: {card['independence']['novel_observation_rate']}",
                f"- observer_character: {', '.join(card['observer_character'])}",
                "- restrictions:",
            ]
        )
        lines.extend(f"  - {restriction}" for restriction in card["restrictions"])
        lines.append("")
    return "\n".join(lines)


def _html(report: dict[str, Any]) -> str:
    cards = "\n".join(_card_html(card) for card in report["observer_cards"])
    roster = "\n".join(
        f"<tr><td>{escape(item['label'])}</td><td>{escape(item['role'])}</td><td>{escape('; '.join(item['restrictions']))}</td></tr>"
        for item in report["production_roster"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(report['title'])}</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, system-ui, sans-serif; background: #f7f7f4; color: #202522; }}
    header {{ padding: 24px clamp(18px, 4vw, 48px); background: #eef2ef; border-bottom: 1px solid #d8ddd7; }}
    main {{ padding: 22px clamp(18px, 4vw, 48px) 42px; display: grid; gap: 18px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; letter-spacing: 0; }}
    .meta {{ color: #68716d; font-size: 13px; }}
    section, .card {{ background: #fff; border: 1px solid #d8ddd7; border-radius: 8px; padding: 14px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; border-bottom: 1px solid #d8ddd7; text-align: left; vertical-align: top; }}
    th {{ color: #68716d; font-size: 12px; text-transform: uppercase; }}
    .metrics {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .metric {{ border: 1px solid #d8ddd7; border-radius: 6px; padding: 8px; background: #fbfcfb; }}
    .metric span {{ display: block; color: #68716d; font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 18px; }}
    ul {{ margin: 6px 0 0 18px; padding: 0; }}
    li {{ margin: 3px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(report['title'])}</h1>
    <div class="meta">Schema {escape(report['schema_version'])} | Built {escape(report['built_at'])}</div>
  </header>
  <main>
    <section>
      <h2>Production Roster</h2>
      <table><thead><tr><th>Observer</th><th>Role</th><th>Restrictions</th></tr></thead><tbody>{roster}</tbody></table>
    </section>
    <section>
      <h2>Observer Cards</h2>
      <div class="cards">{cards}</div>
    </section>
  </main>
</body>
</html>"""


def _card_html(card: dict[str, Any]) -> str:
    restrictions = "".join(f"<li>{escape(item)}</li>" for item in card["restrictions"])
    traits = ", ".join(card["observer_character"])
    return f"""<div class="card">
  <h3>{escape(card['label'])}</h3>
  <div class="meta">{escape(card['analysis_id'])} | {escape(str(card.get('model_name') or 'model n/a'))}</div>
  <div class="metrics">
    <div class="metric"><span>Roles</span><strong>{escape(', '.join(card['qualified_roles']))}</strong></div>
    <div class="metric"><span>Raw Avg</span><strong>{escape(str(card['raw_average_score']))}</strong></div>
    <div class="metric"><span>Norm Avg</span><strong>{escape(str(card['normalized_average_score']))}</strong></div>
    <div class="metric"><span>Conf Avg</span><strong>{escape(str(card['average_confidence']))}</strong></div>
    <div class="metric"><span>Score Scale</span><strong>{escape(str(card['scale_compliance']['overall_score_0_10']))}</strong></div>
    <div class="metric"><span>Conf Scale</span><strong>{escape(str(card['scale_compliance']['evaluator_confidence_0_1']))}</strong></div>
    <div class="metric"><span>Cond Rate</span><strong>{escape(str(card['conditional_pass_rate']))}</strong></div>
    <div class="metric"><span>Obs/Image</span><strong>{escape(str(card['observation_density']['all']))}</strong></div>
    <div class="metric"><span>Novel Obs</span><strong>{escape(str(card['independence']['novel_observation_rate']))}</strong></div>
    <div class="metric"><span>Traits</span><strong>{escape(traits)}</strong></div>
  </div>
  <h3>Restrictions</h3>
  <ul>{restrictions}</ul>
</div>"""
