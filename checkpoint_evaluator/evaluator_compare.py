from __future__ import annotations

import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


def snapshot_analysis(
    run_root: Path,
    analysis_id: str,
    label: str | None = None,
    model_name: str | None = None,
    endpoint: str | None = None,
    directive_used: str | None = None,
) -> Path:
    source = run_root / "analysis_index.json"
    if not source.exists():
        raise FileNotFoundError(f"Missing analysis index: {source}")
    out_dir = run_root / "analysis_runs" / _safe_id(analysis_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "analysis_index.json"
    shutil.copy2(source, target)
    report_source = run_root / "report.json"
    if report_source.exists():
        shutil.copy2(report_source, out_dir / "report.json")
    metadata = {
        "analysis_id": _safe_id(analysis_id),
        "label": label or analysis_id,
        "model_name": model_name or "",
        "endpoint": endpoint or "",
        "directive_used": directive_used or "",
        "analysis_timestamp": datetime.now().isoformat(timespec="seconds"),
        "source_analysis_index": str(source),
        "snapshot_analysis_index": str(target),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return target


def build_evaluator_comparison(
    run_root: Path,
    analyses: list[tuple[str, str, Path]],
    output_name: str = "evaluator_comparison.html",
) -> Path:
    loaded = [(analysis_id, label, _load_analysis(path), _load_metadata(path)) for analysis_id, label, path in analyses]
    if not loaded:
        raise ValueError("At least one analysis is required.")
    records_by_test = {
        analysis_id: {str(record.get("test_id")): record for record in analysis.get("records", [])}
        for analysis_id, _label, analysis, _metadata in loaded
    }
    test_ids = _ordered_test_ids([analysis for _analysis_id, _label, analysis, _metadata in loaded])
    rows = "\n".join(_test_section(test_id, loaded, records_by_test, run_root) for test_id in test_ids)
    summary = "\n".join(_summary_column(analysis_id, label, analysis, metadata) for analysis_id, label, analysis, metadata in loaded)
    aggregate = _aggregate_section(loaded, records_by_test, test_ids)
    personality = _personality_section(loaded)
    legend = ", ".join(escape(label) for _analysis_id, label, _analysis, _metadata in loaded)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CEF Evaluator Comparison</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #202522;
      --muted: #67716d;
      --line: #d8ddd7;
      --accent: #2f6f67;
      --warn: #9a5b00;
      --fail: #a43737;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Segoe UI, system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 22px clamp(18px, 4vw, 46px);
      background: #eef2ef;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; }}
    main {{
      padding: 20px clamp(18px, 4vw, 46px) 40px;
      display: grid;
      gap: 18px;
    }}
    .summary, .aggregate, .profile, .test {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .evaluator {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfbfa;
    }}
    .image-row {{
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 14px;
      align-items: start;
    }}
    .thumb {{
      width: 180px;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #e6e8e5;
    }}
    .columns {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .metric {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .score {{ color: var(--accent); font-weight: 700; }}
    .bad {{ color: var(--fail); font-weight: 700; }}
    .warn {{ color: var(--warn); font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ font-size: 11px; color: var(--muted); text-transform: uppercase; }}
    ul {{ margin: 6px 0 0 18px; padding: 0; }}
    li {{ margin: 3px 0; }}
    .small {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 760px) {{
      .image-row {{ grid-template-columns: 1fr; }}
      .thumb {{ width: 100%; max-width: 320px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>CEF Evaluator Comparison</h1>
    <div class="small">{escape(str(run_root))}</div>
    <div class="small">Evaluators: {legend}</div>
  </header>
  <main>
    <section class="summary">
      <h2>Summary</h2>
      <div class="summary-grid">{summary}</div>
    </section>
    {aggregate}
    {rows}
    {personality}
  </main>
</body>
</html>"""
    out = run_root / output_name
    out.write_text(html, encoding="utf-8")
    return out


def build_judge_auditor_review(
    run_root: Path,
    primary: tuple[str, str, Path],
    auditor: tuple[str, str, Path],
    output_stem: str = "judge_auditor_review_queue",
) -> tuple[Path, Path]:
    primary_id, primary_label, primary_path = primary
    auditor_id, auditor_label, auditor_path = auditor
    primary_analysis = _load_analysis(primary_path)
    auditor_analysis = _load_analysis(auditor_path)
    primary_records = {str(record.get("test_id")): record for record in primary_analysis.get("records", [])}
    auditor_records = {str(record.get("test_id")): record for record in auditor_analysis.get("records", [])}
    records = []
    for test_id in _ordered_test_ids([primary_analysis]):
        if test_id not in auditor_records:
            continue
        records.append(_judge_auditor_record(test_id, primary_records[test_id], auditor_records[test_id]))
    records.sort(key=lambda record: (_tier_order(record["review_tier"]), -(_coerce_float(record["score_delta"]) or 0), record["test_id"]))
    summary = _judge_auditor_summary(primary_label, auditor_label, primary_analysis, records)
    payload = {
        "summary": summary,
        "primary": {"analysis_id": primary_id, "label": primary_label, "analysis_path": str(primary_path)},
        "auditor": {"analysis_id": auditor_id, "label": auditor_label, "analysis_path": str(auditor_path)},
        "records": records,
    }
    json_path = run_root / f"{output_stem}.json"
    md_path = run_root / f"{output_stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_judge_auditor_markdown(summary, records), encoding="utf-8")
    return json_path, md_path


def parse_analysis_spec(value: str) -> tuple[str, str, Path]:
    parts = value.split("=", 2)
    if len(parts) == 2:
        analysis_id, path = parts
        label = analysis_id
    elif len(parts) == 3:
        analysis_id, label, path = parts
    else:
        raise ValueError("Analysis spec must be id=path or id=label=path.")
    return _safe_id(analysis_id), label, Path(path)


def _judge_auditor_record(test_id: str, primary: dict[str, Any], auditor: dict[str, Any]) -> dict[str, Any]:
    primary_score = _coerce_float(primary.get("overall_score"))
    auditor_score = _coerce_float(auditor.get("overall_score"))
    score_delta = None if primary_score is None or auditor_score is None else round(abs(primary_score - auditor_score), 2)
    state_delta = abs(_state_value(primary.get("pass_fail")) - _state_value(auditor.get("pass_fail")))
    primary_intent = _passes_intent(primary)
    auditor_intent = _passes_intent(auditor)
    primary_notes = {_note_key(note) for note in _major_notes(primary)}
    auditor_only_notes = [note for note in _major_notes(auditor) if _note_key(note) not in primary_notes]
    score_pass_warnings = _score_pass_warnings(primary, "primary") + _score_pass_warnings(auditor, "auditor")
    hard_disagreement = state_delta >= 2
    shared_intent_failure = not primary_intent and not auditor_intent
    auditor_critical = any(note["severity"] == "critical" for note in auditor_only_notes)
    auditor_note_review = bool(auditor_only_notes)
    calibration_review = state_delta == 1 or (score_delta is not None and score_delta >= 2.0) or bool(score_pass_warnings)
    if hard_disagreement or shared_intent_failure or auditor_critical:
        tier = "A_REVIEW_REQUIRED"
    elif auditor_note_review:
        tier = "B_AUDITOR_NOTE_REVIEW"
    elif calibration_review:
        tier = "C_CALIBRATION_REVIEW"
    else:
        tier = "NONE"
    return {
        "test_id": test_id,
        "test_name": str(primary.get("test_name") or test_id),
        "image_path": str(primary.get("image_path") or ""),
        "primary_score": primary_score,
        "primary_pass_fail": primary.get("pass_fail"),
        "primary_intent_pass": primary_intent,
        "primary_image_quality_score": _image_quality_score(primary),
        "primary_intent_success_score": _intent_success_score(primary),
        "auditor_score": auditor_score,
        "auditor_pass_fail": auditor.get("pass_fail"),
        "auditor_intent_pass": auditor_intent,
        "auditor_image_quality_score": _image_quality_score(auditor),
        "auditor_intent_success_score": _intent_success_score(auditor),
        "score_delta": score_delta,
        "state_delta": state_delta,
        "hard_disagreement": hard_disagreement,
        "shared_intent_failure": shared_intent_failure,
        "auditor_note_review": auditor_note_review,
        "score_pass_warnings": score_pass_warnings,
        "review_tier": tier,
        "auditor_only_major_notes": auditor_only_notes,
    }


def _judge_auditor_summary(primary_label: str, auditor_label: str, primary_analysis: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "primary_evaluator": primary_label,
        "auditor_evaluator": auditor_label,
        "tests_compared": len(records),
        "official_average_score": _official_average(primary_analysis),
        "tier_a_review_required": sum(1 for record in records if record["review_tier"] == "A_REVIEW_REQUIRED"),
        "tier_b_auditor_note_review": sum(1 for record in records if record["review_tier"] == "B_AUDITOR_NOTE_REVIEW"),
        "tier_c_calibration_review": sum(1 for record in records if record["review_tier"] == "C_CALIBRATION_REVIEW"),
        "no_review": sum(1 for record in records if record["review_tier"] == "NONE"),
        "hard_pass_fail_disagreements": sum(1 for record in records if record["hard_disagreement"]),
        "shared_intent_failures": sum(1 for record in records if record["shared_intent_failure"]),
        "auditor_major_note_items": sum(1 for record in records if record["auditor_note_review"]),
        "score_pass_warning_items": sum(1 for record in records if record["score_pass_warnings"]),
    }


def _judge_auditor_markdown(summary: dict[str, Any], records: list[dict[str, Any]]) -> str:
    lines = [
        "# CEF Judge/Auditor Review Queue",
        "",
        f"Official judge: {summary['primary_evaluator']}",
        f"Auditor: {summary['auditor_evaluator']}",
        "",
        "Tier A: pass vs fail, shared intent failure, or auditor critical note.",
        "Tier B: auditor-only major/critical notes.",
        "Tier C: pass vs conditional, score delta >= 2, or score/pass consistency warning.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in summary.items())
    lines.extend([
        "",
        "## Queue",
        "",
        "| Tier | Test | Official | Auditor | Delta | Quality / Intent | Auditor Notes |",
        "|---|---|---:|---:|---:|---|---:|",
    ])
    for record in records:
        if record["review_tier"] == "NONE":
            continue
        quality_intent = f"{_format_number(record['primary_image_quality_score'])} / {_format_number(record['primary_intent_success_score'])}"
        lines.append(
            f"| {record['review_tier']} | {record['test_id']} ({record['test_name']}) | "
            f"{_format_number(record['primary_score'])} / {record['primary_pass_fail']} | "
            f"{_format_number(record['auditor_score'])} / {record['auditor_pass_fail']} | "
            f"{_format_number(record['score_delta'])} | {quality_intent} | {len(record['auditor_only_major_notes'])} |"
        )
    lines.extend(["", "## Details", ""])
    for record in records:
        if record["review_tier"] == "NONE":
            continue
        lines.extend(
            [
                f"### {record['test_id']} - {record['test_name']}",
                f"- Tier: {record['review_tier']}",
                f"- Official: {_format_number(record['primary_score'])} / {record['primary_pass_fail']} / intent {record['primary_intent_pass']}",
                f"- Auditor: {_format_number(record['auditor_score'])} / {record['auditor_pass_fail']} / intent {record['auditor_intent_pass']}",
                f"- Score delta: {_format_number(record['score_delta'])}; state_delta: {record['state_delta']}",
                f"- Quality / intent split: {_format_number(record['primary_image_quality_score'])} / {_format_number(record['primary_intent_success_score'])}",
            ]
        )
        if record["score_pass_warnings"]:
            lines.append("- Score/pass consistency warnings:")
            lines.extend(f"  - {warning}" for warning in record["score_pass_warnings"])
        if record["auditor_only_major_notes"]:
            lines.append("- Auditor-only major/critical notes:")
            for note in record["auditor_only_major_notes"]:
                evidence = f" Evidence: {note['evidence']}" if note.get("evidence") else ""
                lines.append(f"  - {note['category']}/{note['severity']}: {note['observation']}{evidence}")
        else:
            lines.append("- Auditor-only major/critical notes: none")
        lines.append("")
    return "\n".join(lines)


def _load_analysis(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Analysis index root must be an object: {path}")
    return loaded


def _load_metadata(analysis_path: Path) -> dict[str, Any]:
    metadata_path = analysis_path.parent / "metadata.json"
    if not metadata_path.exists():
        return {}
    loaded = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    return loaded if isinstance(loaded, dict) else {}


def _ordered_test_ids(analyses: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for analysis in analyses:
        for record in analysis.get("records", []):
            test_id = str(record.get("test_id") or "")
            if test_id and test_id not in seen:
                seen.add(test_id)
                ordered.append(test_id)
    return ordered


def _summary_column(analysis_id: str, label: str, analysis: dict[str, Any], metadata: dict[str, Any]) -> str:
    records = analysis.get("records", [])
    avg = _overall_average(records)
    intent = analysis.get("intent_failure_summary", {})
    refs = analysis.get("reference_assisted_summary", {})
    confidence = analysis.get("evaluator_confidence_summary", {})
    wildcard = analysis.get("wildcard_summary", {})
    semantic = analysis.get("semantic_summary", {})
    return f"""<div class="evaluator">
  <h3>{escape(label)}</h3>
  <div class="metric">ID: {escape(analysis_id)}</div>
  <div class="metric">Model: {escape(str(metadata.get("model_name") or "n/a"))}</div>
  <div class="metric">Endpoint: {escape(str(metadata.get("endpoint") or "n/a"))}</div>
  <div class="metric">Directive: {escape(str(metadata.get("directive_used") or "n/a"))}</div>
  <div class="metric">Snapshot: {escape(str(metadata.get("analysis_timestamp") or "n/a"))}</div>
  <div class="metric">Average score: <span class="score">{escape(avg)}</span></div>
  <div class="metric">Images: {escape(str(analysis.get("analyzed_images", len(records))))}</div>
  <div class="metric">Intent failures: {escape(str(intent.get("failed_intent_count", 0)))}</div>
  <div class="metric">Avg confidence: {escape(str(confidence.get("average_confidence", "n/a")))}</div>
  <div class="metric">Reference delta: {escape(str(refs.get("average_score_delta", "n/a")))}</div>
  <div class="metric">Wildcards: {escape(str(wildcard.get("total_observations", 0)))}</div>
  <div class="metric">Semantic observations: {escape(str(semantic.get("total_observations", 0)))}</div>
</div>"""


def _test_section(
    test_id: str,
    loaded: list[tuple[str, str, dict[str, Any], dict[str, Any]]],
    records_by_test: dict[str, dict[str, dict[str, Any]]],
    run_root: Path,
) -> str:
    first_record = next((records_by_test[analysis_id].get(test_id) for analysis_id, _label, _analysis, _metadata in loaded if records_by_test[analysis_id].get(test_id)), {})
    test_name = str(first_record.get("test_name") or test_id)
    image_path = _relative_to(run_root, str(first_record.get("image_path") or ""))
    disagreement = _test_disagreement(test_id, loaded, records_by_test)
    columns = "\n".join(
        _record_column(label, records_by_test[analysis_id].get(test_id))
        for analysis_id, label, _analysis, _metadata in loaded
    )
    return f"""<section class="test">
  <h2>{escape(test_id)} - {escape(test_name)}</h2>
  <div class="metric">{disagreement}</div>
  <div class="image-row">
    <img class="thumb" src="{escape(image_path)}" alt="{escape(test_id)}">
    <div class="columns">{columns}</div>
  </div>
</section>"""


def _record_column(label: str, record: dict[str, Any] | None) -> str:
    if not record:
        return f'<div class="evaluator"><h3>{escape(label)}</h3><div class="bad">Missing analysis</div></div>'
    rubric = record.get("rubric_scores", {})
    intent = record.get("intent_failure_check", {})
    ref = record.get("reference_comparison", {})
    failures = _list_items(record.get("failures", []), limit=4)
    wildcards = _observation_items(record.get("wildcard_observations", []), limit=3)
    semantics = _observation_items(record.get("semantic_observations", []), limit=3)
    strengths = _list_items(record.get("strengths", []), limit=3)
    tags = ", ".join(str(tag) for tag in record.get("recommended_tags", [])[:8])
    return f"""<div class="evaluator">
  <h3>{escape(label)}</h3>
  <div class="metric">Score: <span class="score">{escape(str(record.get("overall_score", "n/a")))}</span> / pass: {escape(str(record.get("pass_fail", "")))}</div>
  <div class="metric">Confidence: {escape(str(record.get("evaluator_confidence", "n/a")))}</div>
  <div class="metric">Prompt: {escape(str(rubric.get("prompt_adherence", "n/a")))} | Anatomy: {escape(str(rubric.get("anatomy", "n/a")))} | Artifacts: {escape(str(rubric.get("artifact_severity", "n/a")))}</div>
  <div class="metric">Identity: {escape(str(rubric.get("identity_retention", "n/a")))} | LoRA: {escape(str(rubric.get("lora_integration", "n/a")))}</div>
  <div class="metric">Reference delta: {escape(str(ref.get("score_delta", "n/a")))}</div>
  <div class="metric">Intent: {escape(str(intent.get("passes_human_intent", "n/a")))} - {escape(str(intent.get("explanation", "")))}</div>
  <div class="metric">Tags: {escape(tags)}</div>
  <div class="metric"><strong>Strengths</strong>{strengths}</div>
  <div class="metric"><strong>Failures</strong>{failures}</div>
  <div class="metric"><strong>Wildcards</strong>{wildcards}</div>
  <div class="metric"><strong>Semantic</strong>{semantics}</div>
</div>"""


def _aggregate_section(
    loaded: list[tuple[str, str, dict[str, Any], dict[str, Any]]],
    records_by_test: dict[str, dict[str, dict[str, Any]]],
    test_ids: list[str],
) -> str:
    metrics = [_evaluator_metrics(analysis_id, label, analysis) for analysis_id, label, analysis, _metadata in loaded]
    strictness = {
        item["analysis_id"]: rank
        for rank, item in enumerate(sorted(metrics, key=lambda value: _sort_number(value["average_score"])), start=1)
    }
    disagreement_count = _pass_fail_disagreement_count(loaded, records_by_test, test_ids)
    rows = "\n".join(
        f"""<tr>
  <td>{escape(str(item["label"]))}</td>
  <td>{escape(_format_number(item["average_score"]))}</td>
  <td>{escape(_format_number(item["score_variance"]))}</td>
  <td>{escape(str(strictness[item["analysis_id"]]))}</td>
  <td>{escape(str(item["pass_count"]))}/{escape(str(item["conditional_count"]))}/{escape(str(item["fail_count"]))}</td>
  <td>{escape(str(item["wildcard_count"]))}</td>
  <td>{escape(str(item["semantic_count"]))}</td>
  <td>{escape(str(item["intent_failure_count"]))}</td>
  <td>{escape(_format_number(item["reference_delta"]))}</td>
  <td>{escape(str(item["score_pass_conflicts"]))}</td>
  <td>{escape(str(item["nudity_penalty_bias"]))}</td>
  <td>{escape(str(item["label_drift"]))}</td>
  <td>{escape(_format_number(item["observation_density"]))}</td>
</tr>"""
        for item in metrics
    )
    return f"""<section class="aggregate">
  <h2>Evaluator Metrics</h2>
  <div class="metric">Pass/fail disagreement count across tests: <span class="warn">{escape(str(disagreement_count))}</span></div>
  <table>
    <thead>
      <tr>
        <th>Evaluator</th>
        <th>Average Score</th>
        <th>Score Variance</th>
        <th>Strictness Rank</th>
        <th>Pass/Conditional/Fail</th>
        <th>Wildcards</th>
        <th>Semantic</th>
        <th>Intent Fails</th>
        <th>Reference Delta</th>
        <th>Score/Pass Conflicts</th>
        <th>Nudity Bias Flags</th>
        <th>Label Drift</th>
        <th>Obs/Image</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def _personality_section(loaded: list[tuple[str, str, dict[str, Any], dict[str, Any]]]) -> str:
    metrics = [_evaluator_metrics(analysis_id, label, analysis) for analysis_id, label, analysis, _metadata in loaded]
    if not metrics:
        return ""
    strictest = min(metrics, key=lambda value: _sort_number(value["average_score"]))
    most_wildcard = max(metrics, key=lambda value: int(value["wildcard_count"]))
    most_semantic = max(metrics, key=lambda value: int(value["semantic_count"]))
    most_intent = max(metrics, key=lambda value: int(value["intent_failure_count"]))
    rows = "\n".join(f"<li>{escape(_profile_sentence(item, strictest, most_wildcard, most_semantic, most_intent))}</li>" for item in metrics)
    return f"""<section class="profile">
  <h2>Evaluator Personality Profile</h2>
  <div class="small">Generated from scoring behavior and observation counts in this comparison run.</div>
  <ul>{rows}</ul>
</section>"""


def _profile_sentence(
    item: dict[str, Any],
    strictest: dict[str, Any],
    most_wildcard: dict[str, Any],
    most_semantic: dict[str, Any],
    most_intent: dict[str, Any],
) -> str:
    traits = []
    if item["analysis_id"] == strictest["analysis_id"]:
        traits.append("strictest by average score")
    if item["analysis_id"] == most_wildcard["analysis_id"] and int(item["wildcard_count"]) > 0:
        traits.append("most wildcard-heavy")
    if item["analysis_id"] == most_semantic["analysis_id"] and int(item["semantic_count"]) > 0:
        traits.append("most semantic/interpretive")
    if item["analysis_id"] == most_intent["analysis_id"] and int(item["intent_failure_count"]) > 0:
        traits.append("most likely to call intent failures")
    if not traits:
        traits.append("comparatively balanced or quiet")
    avg = _format_number(item["average_score"])
    variance = _format_number(item["score_variance"])
    return f"{item['label']}: {', '.join(traits)}. Average score {avg}, variance {variance}, pass/fail split {item['pass_count']}/{item['conditional_count']}/{item['fail_count']}."


def _evaluator_metrics(analysis_id: str, label: str, analysis: dict[str, Any]) -> dict[str, Any]:
    records = analysis.get("records", [])
    scores = [_coerce_float(record.get("overall_score")) for record in records]
    numeric_scores = [score for score in scores if score is not None]
    pass_fail = [str(record.get("pass_fail") or "").lower() for record in records]
    refs = analysis.get("reference_assisted_summary", {})
    return {
        "analysis_id": analysis_id,
        "label": label,
        "average_score": _average_float(numeric_scores),
        "score_variance": _variance(numeric_scores),
        "pass_count": pass_fail.count("pass"),
        "conditional_count": pass_fail.count("conditional_pass"),
        "fail_count": pass_fail.count("fail"),
        "wildcard_count": _count_observations(records, "wildcard_observations"),
        "semantic_count": _count_observations(records, "semantic_observations"),
        "intent_failure_count": _intent_failure_count(records),
        "reference_delta": _coerce_float(refs.get("average_score_delta")),
        "score_pass_conflicts": _score_pass_conflicts(records),
        "nudity_penalty_bias": _nudity_penalty_bias(records),
        "label_drift": _label_drift(records),
        "observation_density": _observation_density(records),
    }


def _state_value(value: Any) -> int:
    return {"fail": 0, "conditional_pass": 1, "pass": 2}.get(str(value or "").lower(), -1)


def _tier_order(value: str) -> int:
    return {"A_REVIEW_REQUIRED": 0, "B_AUDITOR_NOTE_REVIEW": 1, "C_CALIBRATION_REVIEW": 2, "NONE": 3}.get(value, 4)


def _passes_intent(record: dict[str, Any]) -> bool:
    check = record.get("intent_failure_check")
    return bool(check.get("passes_human_intent", True)) if isinstance(check, dict) else True


def _major_notes(record: dict[str, Any]) -> list[dict[str, str]]:
    output = []
    for key in ("wildcard_observations", "semantic_observations"):
        for item in record.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity") or "info")
            observation = str(item.get("observation") or "").strip()
            if severity not in {"major", "critical"} or not observation:
                continue
            category = str(item.get("category") or "other")
            if category == "unprompted_nudity" and severity == "major":
                severity = "minor"
            output.append(
                {
                    "source": key,
                    "category": category,
                    "severity": severity,
                    "observation": observation,
                    "evidence": str(item.get("evidence") or "").strip(),
                }
            )
    return [note for note in output if note["severity"] in {"major", "critical"}]


def _note_key(note: dict[str, str]) -> str:
    return " ".join(str(note.get("observation") or "").lower().split())


def _score_pass_warnings(record: dict[str, Any], role: str) -> list[str]:
    score = _coerce_float(record.get("overall_score"))
    pass_fail = str(record.get("pass_fail") or "").lower()
    if score is None:
        return []
    if score >= 7 and pass_fail == "fail":
        return [f"{role}: score {score:.1f} with fail"]
    if score < 6 and pass_fail == "pass":
        return [f"{role}: score {score:.1f} with pass"]
    return []


def _image_quality_score(record: dict[str, Any]) -> float | None:
    rubric = record.get("rubric_scores", {})
    if not isinstance(rubric, dict):
        return _coerce_float(record.get("overall_score"))
    keys = ["composition", "anatomy", "environment_quality", "face_quality", "hand_quality", "foot_quality", "object_interaction"]
    values = [_coerce_float(rubric.get(key)) for key in keys]
    values = [value for value in values if value is not None]
    artifact = _coerce_float(rubric.get("artifact_severity"))
    if artifact is not None:
        values.append(max(0.0, 10.0 - artifact))
    return round(sum(values) / len(values), 2) if values else _coerce_float(record.get("overall_score"))


def _intent_success_score(record: dict[str, Any]) -> float | None:
    prompt = None
    rubric = record.get("rubric_scores", {})
    if isinstance(rubric, dict):
        prompt = _coerce_float(rubric.get("prompt_adherence"))
    overall = _coerce_float(record.get("overall_score"))
    base = prompt if prompt is not None else overall
    if base is None:
        return None
    if not _passes_intent(record):
        base = min(base, 5.0)
    return round(base, 2)


def _official_average(analysis: dict[str, Any]) -> float | None:
    for summary in analysis.get("checkpoint_summary", {}).values():
        if isinstance(summary, dict) and "average_score" in summary:
            return _coerce_float(summary.get("average_score"))
    return _average_float([score for score in (_coerce_float(record.get("overall_score")) for record in analysis.get("records", [])) if score is not None])


def _test_disagreement(
    test_id: str,
    loaded: list[tuple[str, str, dict[str, Any], dict[str, Any]]],
    records_by_test: dict[str, dict[str, dict[str, Any]]],
) -> str:
    scores = []
    pass_fail_values = []
    for analysis_id, label, _analysis, _metadata in loaded:
        record = records_by_test[analysis_id].get(test_id)
        if not record:
            continue
        score = _coerce_float(record.get("overall_score"))
        if score is not None:
            scores.append((label, score))
        pass_fail = str(record.get("pass_fail") or "").lower()
        if pass_fail:
            pass_fail_values.append(pass_fail)
    if not scores and not pass_fail_values:
        return "Evaluator disagreement: n/a"
    spread = max(score for _label, score in scores) - min(score for _label, score in scores) if len(scores) > 1 else 0.0
    high = max(scores, key=lambda item: item[1]) if scores else ("n/a", 0.0)
    low = min(scores, key=lambda item: item[1]) if scores else ("n/a", 0.0)
    pass_fail_disagreement = len(set(pass_fail_values)) > 1
    flag = "pass/fail disagreement" if pass_fail_disagreement else "pass/fail agreement"
    return (
        f"Evaluator disagreement: score spread {_format_number(spread)} "
        f"(high {high[0]} {_format_number(high[1])}, low {low[0]} {_format_number(low[1])}); {flag}."
    )


def _pass_fail_disagreement_count(
    loaded: list[tuple[str, str, dict[str, Any], dict[str, Any]]],
    records_by_test: dict[str, dict[str, dict[str, Any]]],
    test_ids: list[str],
) -> int:
    count = 0
    for test_id in test_ids:
        values = []
        for analysis_id, _label, _analysis, _metadata in loaded:
            record = records_by_test[analysis_id].get(test_id)
            if record:
                value = str(record.get("pass_fail") or "").lower()
                if value:
                    values.append(value)
        if len(set(values)) > 1:
            count += 1
    return count


def _count_observations(records: list[dict[str, Any]], key: str) -> int:
    return sum(len(record.get(key, [])) for record in records if isinstance(record.get(key, []), list))


def _intent_failure_count(records: list[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        check = record.get("intent_failure_check", {})
        if isinstance(check, dict) and not bool(check.get("passes_human_intent", True)):
            count += 1
    return count


def _score_pass_conflicts(records: list[dict[str, Any]]) -> int:
    conflicts = 0
    for record in records:
        score = _coerce_float(record.get("overall_score"))
        pass_fail = str(record.get("pass_fail") or "").lower()
        if score is None:
            continue
        if score >= 7 and pass_fail == "fail":
            conflicts += 1
        elif score < 6 and pass_fail == "pass":
            conflicts += 1
        elif score >= 8 and pass_fail == "conditional_pass":
            conflicts += 1
    return conflicts


def _nudity_penalty_bias(records: list[dict[str, Any]]) -> int:
    flags = 0
    for record in records:
        text = _record_text(record).lower()
        if "nud" not in text:
            continue
        pass_fail = str(record.get("pass_fail") or "").lower()
        intent = record.get("intent_failure_check", {})
        intent_fails = isinstance(intent, dict) and not bool(intent.get("passes_human_intent", True))
        if pass_fail in {"fail", "conditional_pass"} or intent_fails:
            flags += 1
    return flags


def _label_drift(records: list[dict[str, Any]]) -> int:
    drift = 0
    for record in records:
        intent = record.get("intent_failure_check", {})
        if not isinstance(intent, dict):
            continue
        explanation = str(intent.get("explanation") or "").lower()
        modes = [str(mode).lower() for mode in intent.get("failure_modes", [])]
        if not explanation or not modes:
            continue
        if "species_mismatch" in modes and not any(token in explanation for token in ("species", "creature", "animal", "human-like", "fairy", "insect")):
            drift += 1
        elif "wrong_scale" in modes and "scale" not in explanation and "size" not in explanation:
            drift += 1
        elif "subject_identity" in modes and not any(token in explanation for token in ("subject", "identity", "person", "creature", "dog", "horse", "cart")):
            drift += 1
    return drift


def _observation_density(records: list[dict[str, Any]]) -> float | None:
    if not records:
        return None
    observations = _count_observations(records, "wildcard_observations") + _count_observations(records, "semantic_observations")
    return round(observations / len(records), 4)


def _record_text(record: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("failures", "warnings", "recommended_tags"):
        value = record.get(key, [])
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
    intent = record.get("intent_failure_check", {})
    if isinstance(intent, dict):
        chunks.append(str(intent.get("explanation") or ""))
        chunks.extend(str(mode) for mode in intent.get("failure_modes", []))
    for key in ("wildcard_observations", "semantic_observations"):
        value = record.get(key, [])
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    chunks.extend(str(item.get(field) or "") for field in ("category", "observation", "evidence"))
                else:
                    chunks.append(str(item))
    return " ".join(chunks)


def _average_float(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _variance(values: list[float]) -> float | None:
    if not values:
        return None
    average = sum(values) / len(values)
    return round(sum((value - average) ** 2 for value in values) / len(values), 4)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_number(value: Any) -> float:
    coerced = _coerce_float(value)
    return coerced if coerced is not None else 999999.0


def _format_number(value: Any) -> str:
    number = _coerce_float(value)
    if number is None:
        return "n/a"
    return f"{number:.2f}"


def _list_items(items: list[Any], limit: int) -> str:
    values = [str(item).strip() for item in items if str(item).strip()][:limit]
    if not values:
        return '<div class="small">None</div>'
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _observation_items(items: list[Any], limit: int) -> str:
    values = []
    for item in items:
        if isinstance(item, dict):
            category = str(item.get("category") or "other")
            severity = str(item.get("severity") or "info")
            observation = str(item.get("observation") or "").strip()
            if observation:
                values.append(f"{category}/{severity}: {observation}")
        elif str(item).strip():
            values.append(str(item).strip())
    return _list_items(values, limit)


def _overall_average(records: list[dict[str, Any]]) -> str:
    scores = []
    for record in records:
        try:
            scores.append(float(record.get("overall_score")))
        except (TypeError, ValueError):
            continue
    return f"{sum(scores) / len(scores):.2f}" if scores else "n/a"


def _relative_to(run_root: Path, value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        return path.relative_to(run_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_id(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in safe.split("_") if part) or "analysis"
