from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .analysis_client import QwenEvaluationClient
from .reporting import build_report


def run_analysis(
    run_root: Path,
    directive_path: Path,
    client: QwenEvaluationClient,
    overwrite: bool = False,
    compare_reference_assist: bool = False,
    test_ids: list[str] | None = None,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    index_path = run_root / "generation_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing generation index: {index_path}")
    directive = directive_path.read_text(encoding="utf-8-sig")
    index = json.loads(index_path.read_text(encoding="utf-8-sig"))
    records = _filtered_records(index.get("records", []), test_ids)
    analysis_records: list[dict[str, Any]] = []

    for record in records:
        test_root = Path(record["test_root"])
        generation_path = test_root / "generation.json"
        criteria_path = test_root / "criteria.json"
        if not generation_path.exists():
            raise FileNotFoundError(f"Missing generation metadata: {generation_path}")
        generation_metadata = json.loads(generation_path.read_text(encoding="utf-8-sig"))
        criteria = json.loads(criteria_path.read_text(encoding="utf-8-sig")) if criteria_path.exists() else []
        # References are stored with the per-test generation metadata so old runs remain reproducible.
        reference_images = _resolve_reference_images(generation_metadata, run_root)
        for image_path_value in record.get("image_paths", []):
            image_path = Path(image_path_value)
            image_stem = image_path.stem
            analysis_path = test_root / f"{image_stem}_analysis.json"
            if analysis_path.exists() and not overwrite:
                parsed = json.loads(analysis_path.read_text(encoding="utf-8-sig"))
            else:
                try:
                    parsed = client.evaluate_image(image_path, directive, generation_metadata, criteria, reference_images)
                except Exception as exc:
                    if not continue_on_error:
                        raise
                    parsed = _evaluator_failure_payload(generation_metadata, exc)
                payload = {
                    "analyzed_at": datetime.now().isoformat(timespec="seconds"),
                    "image_path": str(image_path),
                    "generation_path": str(generation_path),
                    "reference_images": reference_images,
                    "analysis": {key: value for key, value in parsed.items() if key != "_raw_response"},
                    "raw_response": parsed.get("_raw_response", {}),
                }
                _write_json(analysis_path, payload)
                parsed = payload
            if compare_reference_assist and reference_images:
                # For referenced tests, keep both assisted and unassisted Qwen outputs so the report can show deltas.
                parsed = _ensure_reference_comparison(
                    parsed,
                    analysis_path,
                    image_path,
                    directive,
                    generation_metadata,
                    criteria,
                    client,
                    overwrite=overwrite,
                )
            analysis_records.append(_summary_record(record, image_path, analysis_path, parsed, reference_images))

    report = _build_analysis_report(index.get("run_id", run_root.name), analysis_records)
    _write_json(run_root / "analysis_index.json", report)
    build_report(run_root)
    return report


def _filtered_records(records: list[dict[str, Any]], test_ids: list[str] | None) -> list[dict[str, Any]]:
    if not test_ids:
        return records
    wanted = {test_id.upper() for test_id in test_ids}
    filtered = [record for record in records if str(record.get("test_id", "")).upper() in wanted]
    missing = sorted(wanted - {str(record.get("test_id", "")).upper() for record in filtered})
    if missing:
        raise ValueError(f"Requested test IDs were not found in generation index: {', '.join(missing)}")
    return filtered


def _evaluator_failure_payload(generation_metadata: dict[str, Any], exc: Exception) -> dict[str, Any]:
    test = generation_metadata.get("test", {})
    return {
        "test_id": str(test.get("id") or ""),
        "overall_score": None,
        "criteria_scores": [],
        "visual_summary": "",
        "prompt_adherence": "Evaluator failed to return parseable analysis.",
        "strengths": [],
        "failures": [f"Evaluator failure: {type(exc).__name__}: {exc}"],
        "unexpected_priors": [],
        "style_notes": [],
        "warnings": ["This record describes evaluator failure, not image failure."],
        "wildcard_observations": [
            {
                "category": "other",
                "severity": "critical",
                "confidence": 1.0,
                "observation": "Evaluator did not return parseable JSON for this image.",
                "evidence": f"{type(exc).__name__}: {exc}",
                "suggested_new_criterion": "Track evaluator reliability and JSON compliance.",
            }
        ],
        "semantic_observations": [],
        "intent_failure_check": {
            "passes_human_intent": False,
            "confidence": 1.0,
            "failure_modes": ["other"],
            "explanation": "Evaluator output failed, so the image could not be scored by this evaluator.",
        },
        "rubric_scores": {},
        "pass_fail": "fail",
        "recommended_tags": ["evaluator_failure", "json_failure"],
        "evaluator_confidence": 0,
    }


def _summary_record(
    generation_record: dict[str, Any],
    image_path: Path,
    analysis_path: Path,
    payload: dict[str, Any],
    reference_images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    analysis = payload.get("analysis", payload)
    references = payload.get("reference_images", reference_images or [])
    return {
        "checkpoint_id": generation_record.get("checkpoint_id"),
        "checkpoint_title": generation_record.get("checkpoint_title"),
        "lora_profile_id": generation_record.get("lora_profile_id"),
        "test_id": generation_record.get("test_id"),
        "test_name": generation_record.get("test_name"),
        "image_path": str(image_path),
        "analysis_path": str(analysis_path),
        "overall_score": analysis.get("overall_score"),
        "criteria_scores": analysis.get("criteria_scores", []),
        "visual_summary": analysis.get("visual_summary", ""),
        "prompt_adherence": analysis.get("prompt_adherence", ""),
        "unexpected_priors": analysis.get("unexpected_priors", []),
        "style_notes": analysis.get("style_notes", []),
        "failures": analysis.get("failures", []),
        "warnings": analysis.get("warnings", []),
        "wildcard_observations": analysis.get("wildcard_observations", []),
        "semantic_observations": analysis.get("semantic_observations", []),
        "intent_failure_check": analysis.get("intent_failure_check", _default_intent_failure_check()),
        "rubric_scores": analysis.get("rubric_scores", {}),
        "pass_fail": analysis.get("pass_fail", ""),
        "recommended_tags": analysis.get("recommended_tags", []),
        "evaluator_confidence": analysis.get("evaluator_confidence"),
        "reference_used": bool(references),
        "reference_assisted": bool(references),
        "reference_ids": [str(reference.get("label") or reference.get("path") or "") for reference in references if isinstance(reference, dict)],
        "reference_images": references,
        "reference_comparison": payload.get("reference_comparison", {}),
    }


def _ensure_reference_comparison(
    assisted_payload: dict[str, Any],
    assisted_analysis_path: Path,
    image_path: Path,
    directive: str,
    generation_metadata: dict[str, Any],
    criteria: list[dict[str, Any]],
    client: QwenEvaluationClient,
    overwrite: bool,
) -> dict[str, Any]:
    unassisted_path = assisted_analysis_path.with_name(f"{image_path.stem}_unassisted_analysis.json")
    if unassisted_path.exists() and not overwrite:
        unassisted_payload = json.loads(unassisted_path.read_text(encoding="utf-8-sig"))
    else:
        unassisted = client.evaluate_image(image_path, directive, generation_metadata, criteria, [])
        unassisted_payload = {
            "analyzed_at": datetime.now().isoformat(timespec="seconds"),
            "image_path": str(image_path),
            "generation_path": assisted_payload.get("generation_path", ""),
            "reference_images": [],
            "analysis": {key: value for key, value in unassisted.items() if key != "_raw_response"},
            "raw_response": unassisted.get("_raw_response", {}),
        }
        _write_json(unassisted_path, unassisted_payload)
    assisted_analysis = assisted_payload.get("analysis", assisted_payload)
    unassisted_analysis = unassisted_payload.get("analysis", unassisted_payload)
    references = assisted_payload.get("reference_images", [])
    comparison = _reference_comparison(assisted_analysis, unassisted_analysis, references, unassisted_path)
    assisted_payload["reference_comparison"] = comparison
    _write_json(assisted_analysis_path, assisted_payload)
    return assisted_payload


def _reference_comparison(
    assisted_analysis: dict[str, Any],
    unassisted_analysis: dict[str, Any],
    references: list[dict[str, Any]],
    unassisted_path: Path,
) -> dict[str, Any]:
    assisted_score = _coerce_score(assisted_analysis.get("overall_score"))
    unassisted_score = _coerce_score(unassisted_analysis.get("overall_score"))
    score_delta = None
    if assisted_score is not None and unassisted_score is not None:
        score_delta = round(assisted_score - unassisted_score, 2)
    return {
        "reference_used": bool(references),
        "reference_id": _reference_id(references),
        "reference_ids": [
            str(reference.get("label") or reference.get("path") or "")
            for reference in references
            if isinstance(reference, dict)
        ],
        "unassisted_score": unassisted_score,
        "assisted_score": assisted_score,
        "score_delta": score_delta,
        "new_observations": _new_observations(assisted_analysis, unassisted_analysis),
        "unassisted_analysis_path": str(unassisted_path),
    }


def _reference_id(references: list[dict[str, Any]]) -> str:
    labels = [
        str(reference.get("label") or reference.get("path") or "")
        for reference in references
        if isinstance(reference, dict)
    ]
    return ", ".join(label for label in labels if label)


def _new_observations(assisted_analysis: dict[str, Any], unassisted_analysis: dict[str, Any]) -> list[str]:
    baseline = set(_observation_texts(unassisted_analysis))
    assisted = _observation_texts(assisted_analysis)
    new_items = []
    for normalized, text in assisted.items():
        if normalized and normalized not in baseline and text not in new_items:
            new_items.append(text)
    return new_items


def _observation_texts(analysis: dict[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    raw_items: list[Any] = []
    for key in ("failures", "warnings", "unexpected_priors", "style_notes"):
        value = analysis.get(key, [])
        if isinstance(value, list):
            raw_items.extend(value)
    for key in ("wildcard_observations", "semantic_observations"):
        value = analysis.get(key, [])
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    raw_items.append(item.get("observation", ""))
    for item in raw_items:
        text = str(item).strip()
        normalized = _normalize_observation(text)
        if normalized:
            texts.setdefault(normalized, text)
    return texts


def _normalize_observation(value: str) -> str:
    return " ".join(value.lower().split())


def _build_analysis_report(run_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    checkpoint_scores: dict[str, list[float]] = {}
    test_scores: dict[str, list[float]] = {}
    for record in records:
        score = _coerce_score(record.get("overall_score"))
        if score is None:
            continue
        checkpoint_scores.setdefault(str(record.get("checkpoint_id")), []).append(score)
        test_scores.setdefault(str(record.get("test_id")), []).append(score)
    return {
        "run_id": run_id,
        "analyzed_images": len(records),
        "records": records,
        "checkpoint_summary": _average_scores(checkpoint_scores),
        "test_summary": _average_scores(test_scores),
        "wildcard_summary": _wildcard_summary(records),
        "semantic_summary": _semantic_summary(records),
        "intent_failure_summary": _intent_failure_summary(records),
        "rubric_summary": _rubric_summary(records),
        "evaluator_confidence_summary": _evaluator_confidence_summary(records),
        "reference_assisted_summary": _reference_assisted_summary(records),
        "checkpoint_personality": _checkpoint_personality(records),
    }


def _resolve_reference_images(generation_metadata: dict[str, Any], run_root: Path) -> list[dict[str, Any]]:
    test = generation_metadata.get("test", {})
    references = test.get("reference_images", [])
    if not isinstance(references, list):
        raise TypeError("test.reference_images must be a list.")
    resolved = []
    for index, reference in enumerate(references, start=1):
        if isinstance(reference, str):
            item = {"label": f"reference_{index:02d}", "path": reference, "purpose": ""}
        elif isinstance(reference, dict):
            item = {
                "label": str(reference.get("label") or f"reference_{index:02d}"),
                "path": str(reference.get("path") or ""),
                "purpose": str(reference.get("purpose") or ""),
            }
        else:
            raise TypeError(f"Reference image {index} must be a string or object.")
        path_text = item["path"].strip()
        if not path_text:
            raise ValueError(f"Reference image {index} is missing a path.")
        path = Path(path_text)
        # Relative paths may be authored from the repo root, copied beside a run, or made run-local.
        candidates = [path] if path.is_absolute() else [Path.cwd() / path, run_root.parent / path, run_root / path]
        resolved_path = next((candidate for candidate in candidates if candidate.exists()), None)
        if resolved_path is None:
            candidate_text = ", ".join(str(candidate) for candidate in candidates)
            raise FileNotFoundError(f"Reference image not found for {item['label']}: {path_text}. Tried: {candidate_text}")
        item["resolved_path"] = str(resolved_path)
        resolved.append(item)
    return resolved


def _average_scores(groups: dict[str, list[float]]) -> dict[str, dict[str, float | int]]:
    return {
        key: {"average_score": round(sum(values) / len(values), 2), "count": len(values)}
        for key, values in sorted(groups.items())
        if values
    }


def _coerce_score(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _wildcard_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    major_issues: list[dict[str, Any]] = []
    suggested_new_criteria: list[dict[str, str]] = []
    for record in records:
        for observation in record.get("wildcard_observations", []):
            if not isinstance(observation, dict):
                continue
            category = str(observation.get("category") or "other")
            severity = str(observation.get("severity") or "info")
            by_category[category] = by_category.get(category, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
            if severity in {"major", "critical"}:
                major_issues.append(
                    {
                        "test_id": str(record.get("test_id", "")),
                        "category": category,
                        "severity": severity,
                        "observation": str(observation.get("observation", "")),
                        "evidence": str(observation.get("evidence", "")),
                    }
                )
            suggested = str(observation.get("suggested_new_criterion", "")).strip()
            if suggested:
                suggested_new_criteria.append(
                    {
                        "test_id": str(record.get("test_id", "")),
                        "category": category,
                        "suggested_new_criterion": suggested,
                    }
                )
    return {
        "total_observations": sum(by_category.values()),
        "by_category": dict(sorted(by_category.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "major_issues": major_issues,
        "suggested_new_criteria": suggested_new_criteria,
    }


def _semantic_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    major_issues: list[dict[str, Any]] = []
    suggested_new_criteria: list[dict[str, str]] = []
    for record in records:
        for observation in record.get("semantic_observations", []):
            if not isinstance(observation, dict):
                continue
            category = str(observation.get("category") or "other")
            severity = str(observation.get("severity") or "info")
            by_category[category] = by_category.get(category, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
            if severity in {"major", "critical"}:
                major_issues.append(
                    {
                        "test_id": str(record.get("test_id", "")),
                        "category": category,
                        "severity": severity,
                        "observation": str(observation.get("observation", "")),
                        "evidence": str(observation.get("evidence", "")),
                    }
                )
            suggested = str(observation.get("suggested_new_criterion", "")).strip()
            if suggested:
                suggested_new_criteria.append(
                    {
                        "test_id": str(record.get("test_id", "")),
                        "category": category,
                        "suggested_new_criterion": suggested,
                    }
                )
    return {
        "total_observations": sum(by_severity.values()),
        "by_category": dict(sorted(by_category.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "major_issues": major_issues,
        "suggested_new_criteria": suggested_new_criteria,
    }


def _intent_failure_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    failure_modes: dict[str, int] = {}
    failed_records: list[dict[str, Any]] = []
    for record in records:
        check = record.get("intent_failure_check", _default_intent_failure_check())
        if not isinstance(check, dict):
            check = _default_intent_failure_check()
        passes = bool(check.get("passes_human_intent", True))
        modes = [str(mode) for mode in check.get("failure_modes", []) if mode]
        for mode in modes:
            failure_modes[mode] = failure_modes.get(mode, 0) + 1
        if not passes:
            failed_records.append(
                {
                    "test_id": str(record.get("test_id", "")),
                    "confidence": check.get("confidence"),
                    "failure_modes": modes,
                    "explanation": str(check.get("explanation", "")),
                }
            )
    return {
        "failed_intent_count": len(failed_records),
        "passed_intent_count": max(len(records) - len(failed_records), 0),
        "failure_modes": dict(sorted(failure_modes.items())),
        "failed_records": failed_records,
    }


def _rubric_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    scores: dict[str, list[float]] = {}
    for record in records:
        rubric_scores = record.get("rubric_scores", {})
        if not isinstance(rubric_scores, dict):
            continue
        for key, value in rubric_scores.items():
            score = _coerce_score(value)
            if score is not None:
                scores.setdefault(str(key), []).append(score)
    return _average_scores(scores)


def _evaluator_confidence_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    confidences = []
    high_confidence_low_scores = []
    for record in records:
        confidence = _coerce_score(record.get("evaluator_confidence"))
        if confidence is None:
            continue
        confidences.append(confidence)
        score = _coerce_score(record.get("overall_score"))
        if score is not None and score <= 4 and confidence >= 0.8:
            high_confidence_low_scores.append(
                {
                    "test_id": str(record.get("test_id", "")),
                    "overall_score": score,
                    "evaluator_confidence": confidence,
                }
            )
    average = round(sum(confidences) / len(confidences), 2) if confidences else None
    return {
        "average_confidence": average,
        "count": len(confidences),
        "high_confidence_low_scores": high_confidence_low_scores,
    }


def _reference_assisted_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_reference: dict[str, int] = {}
    assisted_records = []
    deltas = []
    for record in records:
        references = record.get("reference_images", [])
        if not references:
            continue
        assisted_records.append(str(record.get("test_id", "")))
        for reference in references:
            if not isinstance(reference, dict):
                continue
            label = str(reference.get("label") or reference.get("path") or "reference")
            by_reference[label] = by_reference.get(label, 0) + 1
        comparison = record.get("reference_comparison", {})
        if isinstance(comparison, dict):
            delta = _coerce_score(comparison.get("score_delta"))
            if delta is not None:
                deltas.append(delta)
    return {
        "assisted_image_count": len(assisted_records),
        "assisted_test_ids": assisted_records,
        "by_reference": dict(sorted(by_reference.items())),
        "comparison_count": len(deltas),
        "average_score_delta": round(sum(deltas) / len(deltas), 2) if deltas else None,
    }


def _checkpoint_personality(records: list[dict[str, Any]]) -> dict[str, Any]:
    conceptual_records = [
        record
        for record in records
        if str(record.get("test_id", "")).startswith(("HALLUCINATION_", "CONCEPT_"))
    ]
    source_records = conceptual_records or records
    return {
        "default_subject": _rank_personality_axis(source_records, _PERSONALITY_SUBJECTS),
        "default_mood": _rank_personality_axis(source_records, _PERSONALITY_MOODS),
        "default_visual_language": _rank_personality_axis(source_records, _PERSONALITY_VISUAL_LANGUAGE),
        "source_record_count": len(source_records),
        "conceptual_record_count": len(conceptual_records),
    }


def _rank_personality_axis(records: list[dict[str, Any]], keywords: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    text_by_record = [_personality_text(record) for record in records]
    ranked = []
    for label, terms in keywords.items():
        count = sum(1 for text in text_by_record if any(term in text for term in terms))
        if count:
            ranked.append({"label": label, "count": count})
    ranked.sort(key=lambda item: (-int(item["count"]), str(item["label"])))
    return ranked[:5]


def _personality_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "test_id",
        "test_name",
        "visual_summary",
        "prompt_adherence",
        "failures",
        "warnings",
        "unexpected_priors",
        "style_notes",
        "recommended_tags",
    ):
        parts.append(_flatten_text(record.get(key)))
    for key in ("wildcard_observations", "semantic_observations"):
        for item in record.get(key, []):
            if isinstance(item, dict):
                parts.extend(
                    [
                        str(item.get("category", "")),
                        str(item.get("observation", "")),
                        str(item.get("evidence", "")),
                    ]
                )
    return " ".join(parts).lower()


def _flatten_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    return str(value or "")


_PERSONALITY_SUBJECTS = {
    "solitary human": ("solitary", "lone", "single person", "woman", "man", "portrait subject", "human figure"),
    "portrait": ("portrait", "face", "headshot", "centered subject", "beauty"),
    "group": ("group", "multiple people", "two figures", "crowd", "reunion"),
    "wildlife": ("animal", "bear", "monster", "creature", "wildlife", "griffin", "bird"),
    "landscape": ("landscape", "terrain", "mountain", "desert", "river", "horizon", "ocean"),
    "object or artifact": ("object", "camera", "screen", "skull", "text", "poster", "symbol"),
}

_PERSONALITY_MOODS = {
    "contemplative": ("contemplative", "reflective", "stillness", "quiet", "introspective", "solitary"),
    "romantic": ("romantic", "intimate", "sensual", "beauty", "soft lighting"),
    "dramatic": ("dramatic", "theatrical", "cinematic", "storm", "lightning", "ritual"),
    "melancholic": ("melancholy", "loneliness", "loss", "fog", "regret", "shame", "sad"),
    "documentary": ("documentary", "realistic", "photographic", "studio", "stock photo"),
    "ominous": ("ominous", "danger", "dark", "gothic", "monster", "threatening"),
}

_PERSONALITY_VISUAL_LANGUAGE = {
    "photography": ("photographic", "photo", "portrait photography", "studio", "stock photo"),
    "illustration": ("illustration", "illustrative", "drawing", "painted"),
    "fantasy": ("fantasy", "guardian", "monster", "armor", "angelic", "mythic", "ritual"),
    "cinematic": ("cinematic", "dramatic lighting", "film", "atmospheric"),
    "commercial": ("commercial", "stock photo", "beauty", "poster", "promotional"),
    "sci-fi": ("sci-fi", "science fiction", "cosmic", "space", "astronaut", "galaxy"),
    "text/poster": ("text", "literal text", "poster", "logo", "word", "typography"),
}


def _default_intent_failure_check() -> dict[str, Any]:
    return {
        "passes_human_intent": True,
        "confidence": 0.0,
        "failure_modes": [],
        "explanation": "",
    }


def _write_json(path: Path, data: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
