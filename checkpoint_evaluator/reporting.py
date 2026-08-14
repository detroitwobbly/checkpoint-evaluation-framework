from __future__ import annotations

import json
import shutil
import subprocess
from html import escape
from pathlib import Path
from typing import Any


def build_report(run_root: Path) -> dict[str, Any]:
    analysis_path = run_root / "analysis_index.json"
    generation_path = run_root / "generation_index.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"Missing analysis index: {analysis_path}")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8-sig"))
    generation = json.loads(generation_path.read_text(encoding="utf-8-sig")) if generation_path.exists() else {}
    report = {
        "run_id": analysis.get("run_id", run_root.name),
        "analyzed_images": analysis.get("analyzed_images", 0),
        "generated_images": sum(len(record.get("image_paths", [])) for record in generation.get("records", [])),
        "checkpoint_summary": analysis.get("checkpoint_summary", {}),
        "test_summary": analysis.get("test_summary", {}),
        "wildcard_summary": analysis.get("wildcard_summary", _wildcard_summary(analysis.get("records", []))),
        "semantic_summary": analysis.get("semantic_summary", _semantic_summary(analysis.get("records", []))),
        "intent_failure_summary": analysis.get(
            "intent_failure_summary",
            _intent_failure_summary(analysis.get("records", [])),
        ),
        "rubric_summary": analysis.get("rubric_summary", _rubric_summary(analysis.get("records", []))),
        "evaluator_confidence_summary": analysis.get(
            "evaluator_confidence_summary",
            _evaluator_confidence_summary(analysis.get("records", [])),
        ),
        "reference_assisted_summary": analysis.get(
            "reference_assisted_summary",
            _reference_assisted_summary(analysis.get("records", [])),
        ),
        "checkpoint_personality": analysis.get(
            "checkpoint_personality",
            _checkpoint_personality(analysis.get("records", [])),
        ),
        "records": analysis.get("records", []),
    }
    report["executive_summary"] = analysis.get("executive_summary", _executive_summary(report))
    # Contact sheets are optional: report generation should still succeed without Pillow.
    contact_sheet = build_contact_sheet(report, run_root)
    if contact_sheet:
        report["contact_sheet"] = _relative_path(contact_sheet, run_root)
    (run_root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (run_root / "report.html").write_text(build_html_report(report, run_root), encoding="utf-8")
    return report


def build_contact_sheet(report: dict[str, Any], run_root: Path) -> Path | None:
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError:
        return None

    records = report.get("records", [])
    if not records:
        return None

    columns = 4
    thumb_size = 240
    label_h = 92
    pad = 18
    header_h = 74
    rows = (len(records) + columns - 1) // columns
    width = pad + columns * (thumb_size + pad)
    height = header_h + pad + rows * (thumb_size + label_h + pad)

    sheet = Image.new("RGB", (width, height), (248, 248, 246))
    draw = ImageDraw.Draw(sheet)
    title_font = _pil_font(ImageFont, 28, bold=True)
    label_font = _pil_font(ImageFont, 17)
    small_font = _pil_font(ImageFont, 13)

    draw.text((pad, 18), f"CEF Contact Sheet - {report.get('run_id', run_root.name)}", fill=(25, 25, 30), font=title_font)
    draw.text((width - pad - 180, 28), f"{len(records)} images", fill=(95, 95, 95), font=small_font)

    for index, record in enumerate(records):
        row = index // columns
        col = index % columns
        x = pad + col * (thumb_size + pad)
        y = header_h + pad + row * (thumb_size + label_h + pad)
        image_path = Path(str(record.get("image_path", "")))
        tile = Image.new("RGB", (thumb_size, thumb_size), (232, 235, 232))
        try:
            # Missing images should degrade into a labeled tile, not break the whole report.
            with Image.open(image_path) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                tx = (thumb_size - image.width) // 2
                ty = (thumb_size - image.height) // 2
                tile.paste(image, (tx, ty))
        except (OSError, ValueError):
            draw.text((x + 12, y + 12), "image unavailable", fill=(140, 40, 40), font=small_font)
        sheet.paste(tile, (x, y))
        draw.rectangle((x, y, x + thumb_size - 1, y + thumb_size - 1), outline=(195, 195, 190))

        score = _format_score(record.get("overall_score"))
        pass_fail = str(record.get("pass_fail") or "")
        label = str(record.get("test_id") or "")
        score_color = _score_color(record.get("overall_score"))
        _draw_wrapped_pil_text(draw, label, (x, y + thumb_size + 8), small_font, (25, 25, 30), thumb_size, max_lines=2)
        draw.text((x, y + thumb_size + 42), f"Score {score}", fill=score_color, font=label_font)
        draw.text((x + 108, y + thumb_size + 46), pass_fail, fill=(95, 95, 95), font=small_font)
        if record.get("reference_used"):
            draw.text((x, y + thumb_size + 69), "reference-assisted", fill=(47, 111, 103), font=small_font)

    out = run_root / "report_assets" / "contact_sheet.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=92)
    return out


def _pil_font(ImageFont: Any, size: int, bold: bool = False) -> Any:
    names = ["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _format_score(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "n/a"


def _score_color(value: Any) -> tuple[int, int, int]:
    score = _coerce_float(value)
    if score is None:
        return (95, 95, 95)
    if score >= 8:
        return (35, 112, 74)
    if score >= 6:
        return (145, 92, 0)
    return (160, 55, 55)


def _draw_wrapped_pil_text(
    draw: Any,
    text: str,
    position: tuple[int, int],
    font: Any,
    fill: tuple[int, int, int],
    width: int,
    max_lines: int,
) -> None:
    words = text.split("_")
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line}_{word}" if line else word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    x, y = position
    for index, wrapped_line in enumerate(lines[:max_lines]):
        draw.text((x, y + index * 16), wrapped_line, fill=fill, font=font)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_html_report(report: dict[str, Any], run_root: Path) -> str:
    records = report.get("records", [])
    # HTML is intentionally static so reports can be served by any simple local file server.
    rows = "\n".join(_record_card(record, run_root) for record in records)
    checkpoint_rows = _summary_rows(report.get("checkpoint_summary", {}), "Checkpoint")
    test_rows = _summary_rows(report.get("test_summary", {}), "Test")
    wildcard_summary = report.get("wildcard_summary", {})
    semantic_summary = report.get("semantic_summary", {})
    intent_summary = report.get("intent_failure_summary", {})
    confidence_summary = report.get("evaluator_confidence_summary", {})
    reference_summary = report.get("reference_assisted_summary", {})
    personality = report.get("checkpoint_personality", {})
    executive_summary = report.get("executive_summary", {})
    contact_sheet_link = _contact_sheet_link(report)
    rubric_rows = _summary_rows(report.get("rubric_summary", {}), "Rubric")
    wildcard_rows = _count_rows(wildcard_summary.get("by_category", {}), "category")
    wildcard_severity_rows = _count_rows(wildcard_summary.get("by_severity", {}), "severity")
    suggested_rows = _suggested_criteria_rows(wildcard_summary.get("suggested_new_criteria", []))
    semantic_category_rows = _count_rows(semantic_summary.get("by_category", {}), "semantic category")
    semantic_severity_rows = _count_rows(semantic_summary.get("by_severity", {}), "semantic severity")
    semantic_major_rows = _issue_rows(semantic_summary.get("major_issues", []), include_category=True)
    semantic_suggested_rows = _suggested_criteria_rows(semantic_summary.get("suggested_new_criteria", []))
    intent_mode_rows = _count_rows(intent_summary.get("failure_modes", {}), "intent failure mode")
    intent_failure_rows = _intent_failure_rows(intent_summary.get("failed_records", []))
    executive_summary_section = _executive_summary_section(executive_summary)
    personality_section = _personality_section(personality)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CEF Report - {escape(str(report.get("run_id", "")))}</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --ink: #1f2523;
      --muted: #68716d;
      --line: #d8ddd7;
      --panel: #ffffff;
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
      padding: 24px clamp(18px, 4vw, 48px);
      border-bottom: 1px solid var(--line);
      background: #eef2ef;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    main {{
      padding: 22px clamp(18px, 4vw, 48px) 40px;
      display: grid;
      gap: 22px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .metric, .section, .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric {{
      padding: 14px 16px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 6px;
      font-size: 24px;
    }}
    .section {{
      padding: 16px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 420px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      font-weight: 700;
    }}
    .cards {{
      display: grid;
      gap: 16px;
    }}
    .card {{
      display: grid;
      grid-template-columns: minmax(180px, 280px) 1fr;
      gap: 16px;
      padding: 14px;
    }}
    .thumb {{
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #e5e8e4;
    }}
    .card h3 {{
      margin: 0 0 8px;
      font-size: 17px;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 10px;
    }}
    .score {{
      color: var(--accent);
      font-weight: 700;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }}
    .personality-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 12px;
    }}
    .personality-axis {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfb;
    }}
    .personality-axis h3 {{
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }}
    .personality-axis ul {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 6px;
    }}
    .personality-axis li {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    .personality-axis li strong {{
      color: var(--ink);
      font-weight: 600;
    }}
    .executive-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .executive-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fbfcfb;
    }}
    .executive-item span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      margin-bottom: 5px;
    }}
    .executive-item strong {{
      display: block;
      font-size: 15px;
      line-height: 1.35;
    }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      color: var(--muted);
      background: #fafafa;
    }}
    .criterion {{
      margin: 8px 0;
      padding: 8px 10px;
      border-left: 3px solid var(--accent);
      background: #f8faf8;
    }}
    .wildcard {{
      margin: 8px 0;
      padding: 8px 10px;
      border-left: 3px solid var(--warn);
      background: #fffaf0;
    }}
    .semantic {{
      margin: 8px 0;
      padding: 8px 10px;
      border-left: 3px solid var(--fail);
      background: #fff5f5;
    }}
    .criterion strong {{
      display: block;
      margin-bottom: 3px;
    }}
    .wildcard strong {{
      display: block;
      margin-bottom: 3px;
      color: var(--warn);
    }}
    .semantic strong {{
      display: block;
      margin-bottom: 3px;
      color: var(--fail);
    }}
    .issues {{
      color: var(--fail);
    }}
    a {{ color: var(--accent); }}
    @media (max-width: 760px) {{
      .card {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>CEF Report</h1>
    <div class="meta">{escape(str(report.get("run_id", "")))}</div>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><span>Generated</span><strong>{escape(str(report.get("generated_images", 0)))}</strong></div>
      <div class="metric"><span>Analyzed</span><strong>{escape(str(report.get("analyzed_images", 0)))}</strong></div>
      <div class="metric"><span>Avg Score</span><strong>{_overall_average(records)}</strong></div>
      <div class="metric"><span>Wildcard</span><strong>{escape(str(wildcard_summary.get("total_observations", 0)))}</strong></div>
      <div class="metric"><span>Semantic</span><strong>{escape(str(semantic_summary.get("total_observations", 0)))}</strong></div>
      <div class="metric"><span>Intent Fails</span><strong>{escape(str(intent_summary.get("failed_intent_count", 0)))}</strong></div>
      <div class="metric"><span>Eval Conf</span><strong>{escape(str(confidence_summary.get("average_confidence", "n/a")))}</strong></div>
      <div class="metric"><span>Reference Assisted</span><strong>{escape(str(reference_summary.get("assisted_image_count", 0)))}</strong></div>
      <div class="metric"><span>Reference Delta</span><strong>{escape(str(reference_summary.get("average_score_delta", "n/a")))}</strong></div>
    </section>
    {executive_summary_section}
    {contact_sheet_link}
    {personality_section}
    <section class="section">
      <h2>By Checkpoint</h2>
      <table><thead><tr><th>Checkpoint</th><th>Average Score</th><th>Images</th></tr></thead><tbody>{checkpoint_rows}</tbody></table>
    </section>
    <section class="section">
      <h2>By Test</h2>
      <table><thead><tr><th>Test</th><th>Average Score</th><th>Images</th></tr></thead><tbody>{test_rows}</tbody></table>
    </section>
    <section class="section">
      <h2>Rubric Averages</h2>
      <table><thead><tr><th>Rubric Field</th><th>Average Score</th><th>Images</th></tr></thead><tbody>{rubric_rows}</tbody></table>
    </section>
    <section class="section">
      <h2>Wildcard Observations</h2>
      <table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>{wildcard_rows}</tbody></table>
      <table><thead><tr><th>Severity</th><th>Count</th></tr></thead><tbody>{wildcard_severity_rows}</tbody></table>
      <h2>Suggested Criteria</h2>
      <table><thead><tr><th>Test</th><th>Category</th><th>Suggested Criterion</th></tr></thead><tbody>{suggested_rows}</tbody></table>
    </section>
    <section class="section">
      <h2>Semantic Observations</h2>
      <table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>{semantic_category_rows}</tbody></table>
      <table><thead><tr><th>Severity</th><th>Count</th></tr></thead><tbody>{semantic_severity_rows}</tbody></table>
      <h2>Major Semantic Issues</h2>
      <table><thead><tr><th>Test</th><th>Category</th><th>Severity</th><th>Observation</th><th>Evidence</th></tr></thead><tbody>{semantic_major_rows}</tbody></table>
      <h2>Semantic Suggested Criteria</h2>
      <table><thead><tr><th>Test</th><th>Category</th><th>Suggested Criterion</th></tr></thead><tbody>{semantic_suggested_rows}</tbody></table>
    </section>
    <section class="section">
      <h2>Intent Failure Check</h2>
      <table><thead><tr><th>Failure Mode</th><th>Count</th></tr></thead><tbody>{intent_mode_rows}</tbody></table>
      <h2>Intent Failures</h2>
      <table><thead><tr><th>Test</th><th>Confidence</th><th>Failure Modes</th><th>Explanation</th></tr></thead><tbody>{intent_failure_rows}</tbody></table>
    </section>
    <section>
      <h2>Images</h2>
      <div class="cards">{rows}</div>
    </section>
  </main>
</body>
</html>"""


def _summary_rows(summary: dict[str, Any], label: str) -> str:
    if not summary:
        return f'<tr><td colspan="3">No {escape(label.lower())} scores yet.</td></tr>'
    return "\n".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(str(value.get('average_score', '')))}</td><td>{escape(str(value.get('count', '')))}</td></tr>"
        for key, value in summary.items()
    )


def _contact_sheet_link(report: dict[str, Any]) -> str:
    path = str(report.get("contact_sheet") or "")
    if not path:
        return ""
    return f"""<section class="section">
      <h2>Contact Sheet</h2>
      <a href="{escape(path)}">Open score contact sheet</a>
    </section>"""


def _executive_summary_section(summary: dict[str, Any]) -> str:
    if not isinstance(summary, dict) or not summary:
        return ""
    ordered_keys = [
        ("checkpoint", "Checkpoint"),
        ("overall", "Overall"),
        ("reliability", "Reliability"),
        ("photorealism", "Photorealism"),
        ("anatomy", "Anatomy"),
        ("animal_priors", "Animal Priors"),
        ("environmental_realism", "Environmental Realism"),
        ("creativity", "Creativity"),
        ("dominant_latent_attractors", "Dominant Latent Attractors"),
        ("failure_personality", "Failure Personality"),
        ("recommended_use", "Recommended Use"),
        ("caution", "Caution"),
    ]
    items = []
    for key, label in ordered_keys:
        value = summary.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            text = ", ".join(str(item) for item in value if item)
        else:
            text = str(value)
        items.append(
            f"""<div class="executive-item"><span>{escape(label)}</span><strong>{escape(text)}</strong></div>"""
        )
    if not items:
        return ""
    return f"""<section class="section">
      <h2>Executive Summary</h2>
      <div class="executive-grid">
        {''.join(items)}
      </div>
    </section>"""


def _personality_section(personality: dict[str, Any]) -> str:
    if not isinstance(personality, dict) or not personality:
        return ""
    subject = _personality_axis_html("Default Subject", personality.get("default_subject", []))
    mood = _personality_axis_html("Default Mood", personality.get("default_mood", []))
    language = _personality_axis_html("Default Visual Language", personality.get("default_visual_language", []))
    if not any((subject, mood, language)):
        return ""
    source_count = personality.get("source_record_count", 0)
    conceptual_count = personality.get("conceptual_record_count", 0)
    return f"""<section class="section">
      <h2>Checkpoint Personality</h2>
      <div class="meta">Derived from {escape(str(source_count))} analyzed images; conceptual/hallucination records: {escape(str(conceptual_count))}.</div>
      <div class="personality-grid">
        {subject}
        {mood}
        {language}
      </div>
    </section>"""


def _personality_axis_html(title: str, items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""
    rows = "".join(
        f'<li><strong>{escape(str(item.get("label", "")))}</strong><span>{escape(str(item.get("count", "")))}</span></li>'
        for item in items
        if isinstance(item, dict)
    )
    if not rows:
        return ""
    return f"""<div class="personality-axis">
          <h3>{escape(title)}</h3>
          <ul>{rows}</ul>
        </div>"""


def _record_card(record: dict[str, Any], run_root: Path) -> str:
    image_src = _relative_path(_display_image_path(record.get("image_path"), run_root), run_root)
    analysis_src = _relative_path(record.get("analysis_path"), run_root)
    criteria = "\n".join(_criterion_block(item) for item in record.get("criteria_scores", []))
    rubric_scores = _rubric_score_block(record.get("rubric_scores", {}), record.get("pass_fail", ""))
    wildcard_observations = "\n".join(_wildcard_block(item) for item in record.get("wildcard_observations", []))
    semantic_observations = "\n".join(_semantic_block(item) for item in record.get("semantic_observations", []))
    intent_failure = _intent_failure_block(record.get("intent_failure_check", {}))
    references = _reference_block(record.get("reference_images", []), run_root)
    reference_comparison = _reference_comparison_block(record.get("reference_comparison", {}), run_root)
    failures = _chip_list(record.get("failures", []), "issues")
    warnings = _chip_list(record.get("warnings", []), "")
    return f"""<article class="card">
  <div><img class="thumb" src="{escape(image_src)}" alt="{escape(str(record.get("test_id", "image")))}"></div>
  <div>
    <h3>{escape(str(record.get("test_name") or record.get("test_id") or ""))}</h3>
    <div class="meta">
      {escape(str(record.get("checkpoint_id", "")))} / {escape(str(record.get("lora_profile_id", "")))} / {escape(str(record.get("test_id", "")))}
      &middot; <span class="score">Score {escape(str(record.get("overall_score", "")))}</span>
      &middot; confidence {escape(str(record.get("evaluator_confidence", "")))}
    </div>
    {criteria}
    {rubric_scores}
    {references}
    {reference_comparison}
    {intent_failure}
    {wildcard_observations}
    {semantic_observations}
    {failures}
    {warnings}
    <div class="meta"><a href="{escape(analysis_src)}">analysis.json</a></div>
  </div>
</article>"""


def _criterion_block(item: dict[str, Any]) -> str:
    return f"""<div class="criterion">
  <strong>{escape(str(item.get("criterion", "")))}: {escape(str(item.get("score", "")))}</strong>
  <div>{escape(str(item.get("evidence", "")))}</div>
</div>"""


def _rubric_score_block(scores: dict[str, Any], pass_fail: Any) -> str:
    if not isinstance(scores, dict) or not scores:
        return ""
    items = "".join(
        f'<span class="chip">{escape(str(key))}: {escape(str(value))}</span>'
        for key, value in scores.items()
    )
    return f'<div class="chips"><span class="chip">pass_fail: {escape(str(pass_fail))}</span>{items}</div>'


def _wildcard_block(item: dict[str, Any]) -> str:
    label = f"{item.get('category', 'other')} / {item.get('severity', 'info')}"
    return f"""<div class="wildcard">
  <strong>{escape(str(label))}</strong>
  <div>{escape(str(item.get("observation", "")))}</div>
  <div class="meta">{escape(str(item.get("evidence", "")))}</div>
</div>"""


def _semantic_block(item: dict[str, Any]) -> str:
    label = f"semantic:{item.get('category', 'other')} / {item.get('severity', 'info')}"
    return f"""<div class="semantic">
  <strong>{escape(str(label))}</strong>
  <div>{escape(str(item.get("observation", "")))}</div>
  <div class="meta">{escape(str(item.get("evidence", "")))}</div>
</div>"""


def _intent_failure_block(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    passes = bool(item.get("passes_human_intent", True))
    css_class = "intent-pass" if passes else "intent-fail"
    label = "passes human intent" if passes else "fails human intent"
    modes = ", ".join(str(mode) for mode in item.get("failure_modes", []))
    return f"""<div class="{css_class}">
  <strong>{escape(label)} / confidence {escape(str(item.get("confidence", "")))}</strong>
  <div>{escape(str(item.get("explanation", "")))}</div>
  <div class="meta">{escape(modes)}</div>
</div>"""


def _reference_block(items: list[dict[str, Any]], run_root: Path) -> str:
    if not items:
        return ""
    chips = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("path") or "reference")
        path = _relative_path(item.get("resolved_path") or item.get("path"), run_root)
        purpose = str(item.get("purpose") or "")
        if path:
            chips.append(
                f'<span class="chip">reference: <a href="{escape(path)}">{escape(label)}</a>{escape(" - " + purpose if purpose else "")}</span>'
            )
        else:
            chips.append(f'<span class="chip">reference: {escape(label)}</span>')
    if not chips:
        return ""
    return f'<div class="chips">{"".join(chips)}</div>'


def _reference_comparison_block(item: dict[str, Any], run_root: Path) -> str:
    if not isinstance(item, dict) or not item:
        return ""
    unassisted_path = _relative_path(item.get("unassisted_analysis_path"), run_root)
    score_text = (
        f"unassisted {item.get('unassisted_score')} / assisted {item.get('assisted_score')} / "
        f"delta {item.get('score_delta')}"
    )
    observations = item.get("new_observations", [])
    observation_chips = ""
    if isinstance(observations, list) and observations:
        observation_chips = "".join(f'<span class="chip">new: {escape(str(observation))}</span>' for observation in observations)
    link = f' <a href="{escape(unassisted_path)}">unassisted analysis</a>' if unassisted_path else ""
    return f'<div class="chips"><span class="chip">reference comparison: {escape(score_text)}</span>{observation_chips}<span class="chip">{link}</span></div>'


def _chip_list(items: list[Any], css_class: str) -> str:
    if not items:
        return ""
    chips = "".join(f'<span class="chip">{escape(str(item))}</span>' for item in items)
    return f'<div class="chips {escape(css_class)}">{chips}</div>'


def _relative_path(value: Any, run_root: Path) -> str:
    if not value:
        return ""
    path = Path(str(value))
    try:
        return path.relative_to(run_root).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(run_root.resolve()).as_posix()
        except (ValueError, OSError):
            return path.as_posix()


def _display_image_path(value: Any, run_root: Path) -> str:
    if not value:
        return ""
    source = Path(str(value))
    if not source.exists():
        return str(source)
    thumbnail = _ensure_thumbnail(source, run_root)
    return str(thumbnail or source)


def _ensure_thumbnail(source: Path, run_root: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        relative = source.resolve().relative_to(run_root.resolve())
    except (ValueError, OSError):
        relative = Path(source.name)
    thumb_root = run_root / "report_assets" / "thumbnails"
    thumbnail = thumb_root / relative.with_suffix(".jpg")
    if thumbnail.exists() and thumbnail.stat().st_mtime >= source.stat().st_mtime:
        return thumbnail
    thumbnail.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        "scale=512:512:force_original_aspect_ratio=decrease",
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(thumbnail),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except (subprocess.SubprocessError, OSError):
        return None
    return thumbnail


def _overall_average(records: list[dict[str, Any]]) -> str:
    scores = []
    for record in records:
        try:
            scores.append(float(record.get("overall_score")))
        except (TypeError, ValueError):
            pass
    if not scores:
        return "n/a"
    return str(round(sum(scores) / len(scores), 2))


def _count_rows(counts: dict[str, Any], label: str) -> str:
    if not counts:
        return f'<tr><td colspan="2">No wildcard {escape(label)} counts yet.</td></tr>'
    return "\n".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>"
        for key, value in counts.items()
    )


def _suggested_criteria_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="3">No suggested criteria yet.</td></tr>'
    return "\n".join(
        _suggested_criterion_row(item)
        for item in items
    )


def _suggested_criterion_row(item: dict[str, Any]) -> str:
    return f"<tr><td>{escape(str(item.get('test_id', '')))}</td><td>{escape(str(item.get('category', '')))}</td><td>{escape(str(item.get('suggested_new_criterion', '')))}</td></tr>"


def _issue_rows(items: list[dict[str, Any]], include_category: bool) -> str:
    if not items:
        colspan = 5 if include_category else 4
        return f'<tr><td colspan="{colspan}">No major issues yet.</td></tr>'
    rows = []
    for item in items:
        category = f"<td>{escape(str(item.get('category', '')))}</td>" if include_category else ""
        rows.append(
            f"<tr><td>{escape(str(item.get('test_id', '')))}</td>{category}<td>{escape(str(item.get('severity', '')))}</td><td>{escape(str(item.get('observation', '')))}</td><td>{escape(str(item.get('evidence', '')))}</td></tr>"
        )
    return "\n".join(rows)


def _intent_failure_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="4">No human-intent failures yet.</td></tr>'
    return "\n".join(
        f"<tr><td>{escape(str(item.get('test_id', '')))}</td><td>{escape(str(item.get('confidence', '')))}</td><td>{escape(', '.join(str(mode) for mode in item.get('failure_modes', [])))}</td><td>{escape(str(item.get('explanation', '')))}</td></tr>"
        for item in items
    )


def _executive_summary(report: dict[str, Any]) -> dict[str, Any]:
    records = [record for record in report.get("records", []) if isinstance(record, dict)]
    overall = _numeric_overall_average(records)
    pass_fail = _pass_fail_counts(records)
    personality = report.get("checkpoint_personality", {})
    wildcard_summary = report.get("wildcard_summary", {})
    semantic_summary = report.get("semantic_summary", {})

    return {
        "checkpoint": _executive_checkpoint_name(report),
        "overall": f"{overall:.2f} / 10" if overall is not None else "n/a",
        "reliability": _reliability_label(overall, pass_fail, len(records)),
        "photorealism": _capability_label(_record_score_average(records, _PHOTOREALISM_TEST_HINTS)),
        "anatomy": _capability_label(_record_score_average(records, _ANATOMY_TEST_HINTS)),
        "animal_priors": _capability_label(_record_score_average(records, _ANIMAL_TEST_HINTS)),
        "environmental_realism": _capability_label(_record_score_average(records, _ENVIRONMENT_TEST_HINTS)),
        "creativity": _creativity_label(records),
        "dominant_latent_attractors": _latent_attractors(personality),
        "failure_personality": _failure_personality(records, wildcard_summary, semantic_summary),
        "recommended_use": _recommended_use(records),
        "caution": _caution_note(records, wildcard_summary, semantic_summary),
    }


def _executive_checkpoint_name(report: dict[str, Any]) -> str:
    summary = report.get("checkpoint_summary", {})
    if isinstance(summary, dict) and summary:
        key = next(iter(summary.keys()))
        return Path(str(key)).stem or str(key)
    for record in report.get("records", []):
        if not isinstance(record, dict):
            continue
        for key in ("checkpoint", "checkpoint_id", "checkpoint_name"):
            value = str(record.get(key) or "").strip()
            if value:
                return Path(value).stem
    return str(report.get("run_id", "Checkpoint"))


def _numeric_overall_average(records: list[dict[str, Any]]) -> float | None:
    scores = [
        score
        for score in (_coerce_float(record.get("overall_score")) for record in records)
        if score is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _pass_fail_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "conditional_pass": 0, "fail": 0, "unknown": 0}
    for record in records:
        state = _pass_fail_state(record)
        counts[state] = counts.get(state, 0) + 1
    return counts


def _pass_fail_state(record: dict[str, Any]) -> str:
    raw = str(record.get("pass_fail") or record.get("pass_fail_status") or "").lower()
    normalized = raw.replace("-", "_").replace(" ", "_")
    if "conditional" in normalized:
        return "conditional_pass"
    if "fail" in normalized:
        return "fail"
    if "pass" in normalized:
        return "pass"
    return "unknown"


def _reliability_label(overall: float | None, counts: dict[str, int], total: int) -> str:
    if overall is None or total <= 0:
        return "Not assessed"
    fail_rate = counts.get("fail", 0) / total
    soft_fail_rate = (counts.get("fail", 0) + counts.get("conditional_pass", 0) * 0.5) / total
    if overall >= 8 and fail_rate <= 0.1 and soft_fail_rate <= 0.25:
        return "High"
    if overall >= 7 and fail_rate <= 0.2:
        return "Good"
    if overall >= 6 and fail_rate <= 0.35:
        return "Mixed"
    return "Low"


def _record_score_average(records: list[dict[str, Any]], hints: tuple[str, ...]) -> float | None:
    scores = []
    for record in records:
        text = _record_identity_text(record)
        if not any(hint in text for hint in hints):
            continue
        score = _coerce_float(record.get("overall_score"))
        if score is not None:
            scores.append(score)
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _capability_label(score: float | None) -> str:
    if score is None:
        return "Not targeted"
    if score >= 8.5:
        return "Excellent"
    if score >= 7.5:
        return "Strong"
    if score >= 6:
        return "Moderate"
    return "Weak"


def _creativity_label(records: list[dict[str, Any]]) -> str:
    conceptual = [
        record
        for record in records
        if str(record.get("test_id", "")).startswith(("CONCEPT_", "HALLUCINATION_"))
    ]
    if not conceptual:
        return "Not targeted"
    score = _numeric_overall_average(conceptual)
    label = _capability_label(score)
    if len(conceptual) < 6 and label != "Not targeted":
        return f"{label} limited sample"
    return label


def _latent_attractors(personality: Any) -> str:
    if not isinstance(personality, dict):
        return "Not enough signal"
    labels: list[str] = []
    for axis in ("default_subject", "default_mood", "default_visual_language"):
        for item in personality.get(axis, [])[:2]:
            if isinstance(item, dict):
                label = str(item.get("label") or "").strip()
                if label and label not in labels:
                    labels.append(label)
    if not labels:
        return "Not enough signal"
    return ", ".join(labels[:5])


def _failure_personality(records: list[dict[str, Any]], wildcard_summary: Any, semantic_summary: Any) -> str:
    failed = [record for record in records if _pass_fail_state(record) == "fail"]
    low = sorted(
        (record for record in records if (_coerce_float(record.get("overall_score")) or 10) < 6),
        key=lambda record: _coerce_float(record.get("overall_score")) or 99,
    )
    categories = _summary_categories(wildcard_summary, semantic_summary)
    if _has_test_hint(failed + low, ("mirror", "reflection", "bathroom")):
        if any(category in categories for category in ("clothing_bias", "body_bias", "prompt_conflict")):
            return "Mirror/reflection prompts can pull the model toward glamour or clothing leakage."
        return "Mirror/reflection prompts are the clearest weak spot."
    if any(category in categories for category in ("clothing_bias", "body_bias", "age_bias", "prior_leakage")):
        named = ", ".join(category.replace("_", " ") for category in categories[:3])
        return f"Most visible failures come from prior leakage: {named}."
    if low:
        return f"Lowest-scoring behavior centers on {str(low[0].get('test_id', 'one test')).replace('_', ' ').lower()}."
    return "No strong failure pattern emerged in this run."


def _recommended_use(records: list[dict[str, Any]]) -> str:
    uses = []
    if (_record_score_average(records, _PHOTOREALISM_TEST_HINTS) or 0) >= 8:
        uses.append("photorealistic humans")
    if (_record_score_average(records, _SKIN_FACE_TEST_HINTS) or 0) >= 8:
        uses.append("faces and skin")
    if (_record_score_average(records, _ANATOMY_TEST_HINTS) or 0) >= 8:
        uses.append("body/anatomy reference")
    if (_record_score_average(records, _ANIMAL_TEST_HINTS) or 0) >= 8:
        uses.append("animals")
    if (_record_score_average(records, _ENVIRONMENT_TEST_HINTS) or 0) >= 8:
        uses.append("realistic environments")
    if not uses:
        return "Review detailed results before relying on this checkpoint."
    return ", ".join(uses[:5])


def _caution_note(records: list[dict[str, Any]], wildcard_summary: Any, semantic_summary: Any) -> str:
    categories = _summary_categories(wildcard_summary, semantic_summary)
    cautions = []
    if any(
        _pass_fail_state(record) == "fail"
        and any(hint in _record_identity_text(record) for hint in ("mirror", "reflection", "bathroom"))
        for record in records
    ):
        cautions.append("mirror/reflection prompts need review")
    if "clothing_bias" in categories or "body_bias" in categories:
        cautions.append("clothing or body-prior leakage may appear")
    if "age_bias" in categories:
        cautions.append("age cues may be softened")
    if "physics_failure" in categories:
        cautions.append("physics/object behavior needs checking")
    if not cautions:
        return "No major caution pattern surfaced."
    return "; ".join(cautions[:3]) + "."


def _summary_categories(*summaries: Any) -> list[str]:
    categories: list[str] = []
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        by_category = summary.get("by_category", {})
        if not isinstance(by_category, dict):
            continue
        for category, count in sorted(by_category.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
            name = str(category)
            if name not in categories:
                categories.append(name)
    return categories


def _has_test_hint(records: list[dict[str, Any]], hints: tuple[str, ...]) -> bool:
    return any(any(hint in _record_identity_text(record) for hint in hints) for record in records)


def _record_identity_text(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key, ""))
        for key in ("test_id", "test_name", "category", "prompt_summary", "purpose")
    ).lower()


def _wildcard_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    suggested_new_criteria: list[dict[str, str]] = []
    for record in records:
        for observation in record.get("wildcard_observations", []):
            if not isinstance(observation, dict):
                continue
            category = str(observation.get("category") or "other")
            severity = str(observation.get("severity") or "info")
            by_category[category] = by_category.get(category, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
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
        check = record.get("intent_failure_check", {})
        if not isinstance(check, dict):
            check = {}
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
            try:
                scores.setdefault(str(key), []).append(float(value))
            except (TypeError, ValueError):
                pass
    return {
        key: {"average_score": round(sum(values) / len(values), 2), "count": len(values)}
        for key, values in sorted(scores.items())
        if values
    }


def _evaluator_confidence_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    confidences = []
    high_confidence_low_scores = []
    for record in records:
        try:
            confidence = float(record.get("evaluator_confidence"))
        except (TypeError, ValueError):
            continue
        confidences.append(confidence)
        try:
            score = float(record.get("overall_score"))
        except (TypeError, ValueError):
            score = None
        if score is not None and score <= 4 and confidence >= 0.8:
            high_confidence_low_scores.append(
                {
                    "test_id": str(record.get("test_id", "")),
                    "overall_score": score,
                    "evaluator_confidence": confidence,
                }
            )
    return {
        "average_confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
        "count": len(confidences),
        "high_confidence_low_scores": high_confidence_low_scores,
    }


def _reference_assisted_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_reference: dict[str, int] = {}
    assisted_test_ids = []
    deltas = []
    for record in records:
        references = record.get("reference_images", [])
        if not references:
            continue
        assisted_test_ids.append(str(record.get("test_id", "")))
        for reference in references:
            if not isinstance(reference, dict):
                continue
            label = str(reference.get("label") or reference.get("path") or "reference")
            by_reference[label] = by_reference.get(label, 0) + 1
        comparison = record.get("reference_comparison", {})
        if isinstance(comparison, dict):
            try:
                deltas.append(float(comparison.get("score_delta")))
            except (TypeError, ValueError):
                pass
    return {
        "assisted_image_count": len(assisted_test_ids),
        "assisted_test_ids": assisted_test_ids,
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

_PHOTOREALISM_TEST_HINTS = (
    "real_",
    "photoreal",
    "face",
    "skin",
    "body",
    "clothing",
    "bathroom",
    "bedroom",
)

_SKIN_FACE_TEST_HINTS = (
    "face",
    "skin",
    "portrait",
    "closeup",
)

_ANATOMY_TEST_HINTS = (
    "body",
    "anatomy",
    "hands",
    "feet",
    "pose",
    "cross",
    "kneeling",
    "reclining",
    "overhead",
    "male",
    "female",
    "chest",
)

_ANIMAL_TEST_HINTS = (
    "dog",
    "horse",
    "animal",
    "canine",
    "conformation",
)

_ENVIRONMENT_TEST_HINTS = (
    "environment",
    "bedroom",
    "bathroom",
    "beach",
    "gym",
    "kitchen",
    "workshop",
    "street",
)
