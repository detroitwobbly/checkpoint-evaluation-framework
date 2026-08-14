from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


def build_review(
    run_root: Path,
    output_root: Path | None = None,
    manifest: Path | None = None,
    observer_indexes: list[Path] | None = None,
    summaries: list[Path] | None = None,
    routing_summaries: list[Path] | None = None,
) -> dict[str, Any]:
    run_root = run_root.resolve()
    output_root = (output_root or run_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    discovered_observers = observer_indexes or _discover_observer_indexes(run_root)
    discovered_summaries = summaries or _discover_summaries(run_root)
    discovered_routing = routing_summaries or _discover_routing_summaries(run_root)

    generation_index = _read_optional_json(run_root / "generation_index.json")
    provenance_index = _read_optional_json(run_root / "png_provenance_index.json")
    observer_sections = [_observer_section(path, output_root) for path in discovered_observers]
    summary_sections = [_summary_section(path, output_root) for path in discovered_summaries]
    routing_sections = [_summary_section(path, output_root) for path in discovered_routing]

    generation = _generation_section(run_root, output_root, generation_index, manifest)
    provenance = _provenance_section(run_root, output_root, provenance_index)
    human_review = _human_review_section(observer_sections, summary_sections, routing_sections)
    at_a_glance = _at_a_glance(run_root, generation, provenance, observer_sections, summary_sections, routing_sections, human_review)

    review = {
        "artifact_type": "run_pipeline_review",
        "schema_version": "0.1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_root": str(run_root),
        "output_root": str(output_root),
        "generation": generation,
        "provenance": provenance,
        "at_a_glance": at_a_glance,
        "observation": observer_sections,
        "extraction": _extraction_section(observer_sections),
        "summaries": summary_sections,
        "routing": routing_sections,
        "human_review": human_review,
        "doctrine": (
            "CEF must expose reasoning artifacts at every major pipeline stage: generation, observation, "
            "extraction, aggregation, routing, and dossier synthesis."
        ),
    }

    json_path = output_root / "run_pipeline_review.json"
    html_path = output_root / "run_pipeline_review.html"
    review["review_json"] = str(json_path)
    review["review_html"] = str(html_path)
    json_path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(_html(review, output_root), encoding="utf-8")
    return review


def _generation_section(run_root: Path, output_root: Path, generation_index: dict[str, Any] | None, manifest: Path | None) -> dict[str, Any]:
    records = generation_index.get("records", []) if generation_index else []
    contact_sheets = _existing_links(
        output_root,
        [
            run_root / "report_assets" / "contact_sheet.jpg",
            run_root / "report_assets" / "generation_contact_sheet.jpg",
            run_root / "contact_sheet.jpg",
        ],
    )
    checkpoints = Counter(str(record.get("checkpoint_id") or "unknown") for record in records)
    return {
        "status": "present" if generation_index else "missing",
        "generation_index": _link(output_root, run_root / "generation_index.json") if (run_root / "generation_index.json").exists() else "",
        "manifest": _link(output_root, manifest) if manifest and manifest.exists() else "",
        "record_count": len(records),
        "image_count": sum(len(record.get("image_paths", [])) for record in records),
        "checkpoint_counts": dict(sorted(checkpoints.items())),
        "contact_sheets": contact_sheets,
        "sample_tests": [
            {
                "test_id": record.get("test_id"),
                "checkpoint_id": record.get("checkpoint_id"),
                "image_count": len(record.get("image_paths", [])),
                "test_root": record.get("test_root"),
            }
            for record in records[:12]
        ],
    }


def _provenance_section(run_root: Path, output_root: Path, provenance_index: dict[str, Any] | None) -> dict[str, Any]:
    path = run_root / "png_provenance_index.json"
    if not provenance_index:
        return {"status": "missing", "provenance_index": _link(output_root, path) if path.exists() else ""}
    records = provenance_index.get("records", [])
    text_key_counts = Counter(key for record in records for key in record.get("png_text_keys", []))
    contributor_counts = Counter()
    for record in records:
        contributors = ((record.get("parsed_parameters") or {}).get("contributors") or {})
        for key, value in contributors.items():
            if value:
                contributor_counts[key] += 1
    return {
        "status": "present",
        "provenance_index": _link(output_root, path),
        "image_count": provenance_index.get("image_count", len(records)),
        "failure_count": provenance_index.get("failure_count", 0),
        "png_text_keys": dict(text_key_counts.most_common()),
        "contributor_counts": dict(sorted(contributor_counts.items())),
    }


def _observer_section(path: Path, output_root: Path) -> dict[str, Any]:
    data = _read_optional_json(path) or {}
    records = data.get("records", [])
    observer_root = path.parent
    fields = _field_coverage(records)
    failures = [record for record in records if record.get("observer_failure")]
    uncertainties = [
        {
            "test_id": record.get("test_id"),
            "prompt": record.get("prompt"),
            "confidence": record.get("observer_confidence"),
            "uncertainties": record.get("uncertainties") or record.get("sag_uncertainties") or [],
            "summary": record.get("summary"),
        }
        for record in records
        if _needs_review(record)
    ]
    return {
        "path": str(path),
        "href": _link(output_root, path),
        "artifact_type": data.get("artifact_type", "unknown"),
        "observer": data.get("observer", {}),
        "observer_schema": data.get("observer_schema", ""),
        "directive": data.get("directive", ""),
        "observed_images": data.get("observed_images", len(records)),
        "failures": data.get("failures", len(failures)),
        "record_count": len(records),
        "field_coverage": fields,
        "uncertainty_records": uncertainties[:40],
        "report_links": _existing_links(
            output_root,
            [
                observer_root / "ssp_report.html",
                observer_root / "basin_report.html",
                observer_root / "observer_report.html",
                observer_root / "behavioral_observation_records.json",
                observer_root / "behavioral_observation_records.jsonl",
                observer_root / "ssp_contact_sheet.jpg",
            ],
        ),
        "prototype_counts": _counts(records, "prototype_class"),
        "confidence_counts": _counts(records, "observer_confidence"),
    }


def _summary_section(path: Path, output_root: Path) -> dict[str, Any]:
    data = _read_optional_json(path) or {}
    root = path.parent
    return {
        "path": str(path),
        "href": _link(output_root, path),
        "artifact_type": data.get("artifact_type", "unknown"),
        "schema_version": data.get("schema_version", ""),
        "record_count": _summary_record_count(data),
        "key_counts": _top_level_counts(data),
        "dashboard": _summary_dashboard(data),
        "companion_links": _existing_links(
            output_root,
            [
                path.with_suffix(".md"),
                root / "semantic_agency_gradient_review.html",
                root / "semantic_entropy_summary.md",
                root / "phenotype_routing_summary.md",
                root / "phenotype_routing_recommendations.md",
            ],
        ),
    }


def _at_a_glance(
    run_root: Path,
    generation: dict[str, Any],
    provenance: dict[str, Any],
    observer_sections: list[dict[str, Any]],
    summary_sections: list[dict[str, Any]],
    routing_sections: list[dict[str, Any]],
    human_review: dict[str, Any],
) -> dict[str, Any]:
    observer_failures = sum(int(section.get("failures") or 0) for section in observer_sections)
    provenance_failures = int(provenance.get("failure_count") or 0)
    status = "Complete"
    if generation.get("status") != "present" or not observer_sections:
        status = "Incomplete"
    elif observer_failures or provenance_failures or human_review.get("records_needing_review"):
        status = "Complete; review recommended"

    dashboards = [
        section.get("dashboard", {})
        for section in [*summary_sections, *routing_sections]
        if section.get("dashboard")
    ]
    priority_dashboards = sorted(dashboards, key=lambda item: item.get("priority", 100))
    main_finding = next((item.get("main_finding") for item in priority_dashboards if item.get("main_finding")), "")
    if not main_finding:
        main_finding = _fallback_main_finding(observer_sections)

    key_signals = []
    for item in priority_dashboards:
        key_signals.extend(item.get("key_signals", []))
    if not key_signals:
        key_signals = [
            f"Images generated: {generation.get('image_count', 0)}",
            f"Observer records: {sum(section.get('record_count', 0) for section in observer_sections)}",
            f"Observer failures: {observer_failures}",
        ]

    route_labels = []
    for section in routing_sections:
        dashboard = section.get("dashboard", {})
        route_labels.extend(dashboard.get("run_next", []))

    return {
        "title": _title_from_run_root(run_root),
        "status": status,
        "images": generation.get("image_count", 0),
        "observers": [
            section.get("observer", {}).get("label") or section.get("observer", {}).get("id") or Path(section.get("path", "")).parent.name
            for section in observer_sections
        ],
        "protocol": next((item.get("protocol") for item in priority_dashboards if item.get("protocol")), "Run Pipeline Review"),
        "confidence": next((item.get("confidence") for item in priority_dashboards if item.get("confidence")), "descriptive"),
        "main_finding": main_finding,
        "key_signals": _dedupe(key_signals)[:10],
        "behavioral_interpretation": next((item.get("behavioral_interpretation") for item in priority_dashboards if item.get("behavioral_interpretation")), []),
        "evidence_basis": _evidence_basis(generation, observer_sections, priority_dashboards),
        "phenotype_abstract": next((item.get("phenotype_abstract") for item in priority_dashboards if item.get("phenotype_abstract")), ""),
        "routing_bars": next((item.get("routing_bars") for item in priority_dashboards if item.get("routing_bars")), []),
        "neighborhood_behaviors": next((item.get("neighborhood_behaviors") for item in priority_dashboards if item.get("neighborhood_behaviors")), []),
        "phenotype_meters": next((item.get("phenotype_meters") for item in priority_dashboards if item.get("phenotype_meters")), []),
        "what_to_inspect": _dedupe(_inspect_items(human_review, dashboards))[:10],
        "what_to_run_next": _dedupe(route_labels or human_review.get("suggestions", []))[:10],
        "transition_map": next((item.get("transition_map") for item in priority_dashboards if item.get("transition_map")), []),
        "transition_groups": next((item.get("transition_groups") for item in priority_dashboards if item.get("transition_groups")), {}),
    }


def _summary_dashboard(data: dict[str, Any]) -> dict[str, Any]:
    artifact_type = data.get("artifact_type")
    if artifact_type == "semantic_agency_gradient_summary":
        return _sag_dashboard(data)
    if artifact_type in {"phenotype_routing_summary", "phenotype_routing_recommendations"}:
        recommendations = data.get("recommendations") or data.get("recommended_sidecars") or []
        strong = [
            item for item in recommendations
            if str(item.get("evidence_strength") or item.get("recommendation") or "").lower() == "strong"
        ]
        return {
            "priority": 10,
            "main_finding": _routing_main_finding(str(data.get("checkpoint_id") or ""), recommendations),
            "key_signals": [
                f"Strong routes: {len(strong)}",
                f"Recommended investigations: {len(recommendations)}",
                *_routing_signal_lines(recommendations),
            ],
            "run_next": [
                str(item.get("recommended_investigation") or item.get("protocol_id") or item.get("sidecar_id") or item.get("id"))
                for item in recommendations[:8]
            ],
            "routing_bars": _routing_bars(recommendations),
        }
    if artifact_type == "semantic_neighborhood_entropy_summary":
        neighborhoods = data.get("neighborhoods") or []
        neighborhood_behaviors = _neighborhood_behavior_cards(neighborhoods)
        return {
            "priority": 80,
            "main_finding": "Semantic entropy summary is available for neighborhood-level dispersion review.",
            "key_signals": [f"Neighborhoods summarized: {len(neighborhoods)}"],
            "behavioral_interpretation": _entropy_interpretation_bullets(neighborhoods),
            "phenotype_abstract": _entropy_phenotype_abstract(data),
            "neighborhood_behaviors": neighborhood_behaviors,
            "transition_map": [
                f"{item.get('neighborhood_id')}: {item.get('behavior_label') or item.get('dominant_prototype') or 'summarized'}"
                for item in neighborhoods[:8]
            ],
        }
    return {}


def _routing_main_finding(checkpoint_id: str, recommendations: list[dict[str, Any]]) -> str:
    strong_names = {
        str(item.get("recommended_investigation") or item.get("protocol_id") or item.get("sidecar_id") or "")
        for item in recommendations
        if str(item.get("evidence_strength") or item.get("recommendation") or "").lower() == "strong"
    }
    if "Prompt Stability" in strong_names and "Human Default / Portrait Pull" in strong_names:
        return "Strong prompt-format instability with strong human/default-portrait pull under weak semantic prompts."
    if "Prompt Stability" in strong_names:
        return "Strong prompt-format instability under null, punctuation, whitespace, or function-word prompts."
    if "Human Default / Portrait Pull" in strong_names:
        return "Strong human/default-portrait pull under underspecified prompts."
    if "Semantic Stability" in strong_names and any(
        str(item.get("recommended_investigation") or "") == "Semantic Topology"
        for item in recommendations
    ):
        return "Semantic neighborhoods show conditional regimes: some collapse, some specialize, and some form structured manifolds."
    if "Semantic Stability" in strong_names:
        return "Semantic neighborhoods show high-entropy or fragmented behavior that warrants stability confirmation."
    if recommendations:
        return "Routing recommendations are available for follow-up investigations."
    return f"No routing recommendations found for {checkpoint_id or 'this run'}."


def _routing_signal_lines(recommendations: list[dict[str, Any]]) -> list[str]:
    lines = []
    for item in recommendations[:5]:
        label = str(item.get("recommended_investigation") or item.get("protocol_id") or item.get("sidecar_id") or "Investigation")
        strength = str(item.get("evidence_strength") or item.get("recommendation") or "unknown")
        count = item.get("evidence_count")
        lines.append(f"{label}: {strength}" + (f" ({count} evidence tests)" if count is not None else ""))
    return lines


def _routing_bars(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = {"strong": 10, "medium": 6, "weak": 3, "human_review": 4}
    bars = []
    for item in recommendations[:8]:
        strength = str(item.get("evidence_strength") or item.get("recommendation") or "weak").lower()
        value = values.get(strength, 3)
        bars.append(
            {
                "label": str(item.get("recommended_investigation") or item.get("protocol_id") or item.get("sidecar_id") or "Investigation"),
                "strength": strength,
                "value": value,
                "bar": "█" * value + "░" * (10 - value),
                "evidence_count": item.get("evidence_count"),
            }
        )
    return bars


def _neighborhood_behavior_cards(neighborhoods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = {
        "prototype_collapse": 10,
        "prototype_specialization": 7,
        "structured_manifold": 7,
        "prototype_neighborhood": 6,
        "mixed_or_ambiguous": 4,
        "prototype_fragmentation": 5,
    }
    return [
        {
            "neighborhood": str(item.get("neighborhood_id") or "UNKNOWN"),
            "behavior": str(item.get("behavior_label") or "unknown"),
            "value": values.get(str(item.get("behavior_label") or ""), 3),
            "dominant_prototype": str(item.get("dominant_prototype") or "unknown"),
            "entropy": item.get("prototype_entropy"),
            "note": str(item.get("structured_variation_note") or item.get("behavior_summary") or ""),
        }
        for item in neighborhoods
    ]


def _entropy_interpretation_bullets(neighborhoods: list[dict[str, Any]]) -> list[str]:
    by_id = {str(item.get("neighborhood_id") or "").upper(): item for item in neighborhoods}
    bullets: list[str] = []
    agent = by_id.get("AGENT")
    if agent and agent.get("behavior_label") == "prototype_collapse":
        bullets.append("Agent-related prompts strongly collapsed to recognizable human or role archetypes.")
    symbol = by_id.get("SYMBOL")
    if symbol:
        bullets.append("Symbolic concepts remained partially symbolic while often resolving through human representations.")
    place = by_id.get("PLACE")
    if place:
        bullets.append("Concrete place prompts largely retained environmental or architectural readings, though labels may require review.")
    thing = by_id.get("THING")
    if thing and thing.get("behavior_label") == "structured_manifold":
        bullets.append("Thing-like concepts split into multiple organized semantic families rather than random scatter.")
    circle = by_id.get("CIRCLE")
    if circle and circle.get("behavior_label") == "structured_manifold":
        bullets.append("Circle-related prompts formed a structured manifold across literal objects, symbolic forms, and polysemous cases.")
    if any(item.get("behavior_label") in {"prototype_collapse", "prototype_specialization", "structured_manifold", "prototype_neighborhood"} for item in neighborhoods):
        bullets.append("No evidence from this summary suggests globally random behavior across all neighborhoods.")
    return bullets


def _entropy_phenotype_abstract(data: dict[str, Any]) -> str:
    neighborhoods = data.get("neighborhoods") or []
    if not neighborhoods:
        return ""
    count = data.get("observed_images") or sum(int(item.get("record_count") or 0) for item in neighborhoods)
    neighborhood_count = len(neighborhoods)
    labels = {str(item.get("neighborhood_id") or "").upper(): str(item.get("behavior_label") or "") for item in neighborhoods}
    clauses = []
    if labels.get("AGENT") == "prototype_collapse":
        clauses.append("agent-related prompts collapsed toward human representations")
    if labels.get("THING") == "structured_manifold":
        clauses.append("thing-like prompts formed a structured manifold spanning multiple prototype families")
    if labels.get("CIRCLE") == "structured_manifold":
        clauses.append("circle prompts formed a structured manifold across literal and polysemous resolutions")
    if labels.get("SYMBOL"):
        clauses.append("symbol prompts showed symbolic or humanized resolution")
    if labels.get("PLACE"):
        clauses.append("place prompts remained comparatively literal or environmental")
    body = "; ".join(clauses) if clauses else "semantic neighborhoods showed distinct behavioral regimes"
    return (
        f"{count} sparse semantic probes across {neighborhood_count} neighborhoods suggest neighborhood-dependent behavior rather than a single checkpoint-wide phenotype. "
        f"In this run, {body}. These observations support follow-up Semantic Stability, Semantic Topology, and Attractor Confirmation work to test whether the observed regimes reproduce across seeds, prompts, and checkpoints."
    )


def _evidence_basis(
    generation: dict[str, Any],
    observer_sections: list[dict[str, Any]],
    priority_dashboards: list[dict[str, Any]],
) -> list[str]:
    observer_records = sum(int(section.get("record_count") or 0) for section in observer_sections)
    failures = sum(int(section.get("failures") or 0) for section in observer_sections)
    schemas = ", ".join(sorted({str(section.get("observer_schema") or "unspecified") for section in observer_sections}))
    neighborhoods = 0
    for dashboard in priority_dashboards:
        for line in dashboard.get("key_signals", []):
            if str(line).startswith("Neighborhoods summarized:"):
                try:
                    neighborhoods = int(str(line).split(":", 1)[1].strip())
                except ValueError:
                    pass
    basis = [
        f"{generation.get('image_count', 0)} generated images",
        f"{observer_records} observer records",
        f"{failures} observer failures",
    ]
    if neighborhoods:
        basis.append(f"{neighborhoods} semantic neighborhoods")
    if schemas:
        basis.append(f"Observer schema: {schemas}")
    return basis


def _sag_dashboard(data: dict[str, Any]) -> dict[str, Any]:
    overall = data.get("overall") or {}
    record_count = int(overall.get("record_count") or data.get("observed_images") or 0)
    embodiment = _normalized_counts(overall.get("embodiment_counts", {}), "embodiment_level")
    prototype = _normalized_counts(overall.get("prototype_counts", {}), "prototype_class")
    presentation = _normalized_counts(overall.get("presentation_grammar_counts", {}), "presentation_grammar")
    human_primary = _normalized_counts(overall.get("human_primary_counts", {}), "human_primary")
    object_retained = _normalized_counts(overall.get("functional_object_retained_counts", {}), "functional_object_retained")
    human_accompaniment = _normalized_counts(overall.get("human_accompaniment_counts", {}), "human_accompaniment")
    clothing = _normalized_counts(overall.get("clothing_state_leakage_counts", {}), "clothing_state_leakage")

    human_count = embodiment.get("human", 0) + prototype.get("human", 0)
    object_count = embodiment.get("object", 0) + prototype.get("artifact", 0)
    main = "Semantic Agency Gradient summary is available."
    if record_count:
        if human_primary.get("yes", 0) >= max(2, record_count * 0.5) or human_count >= record_count:
            main = "Weak agency/personhood prompts strongly resolved toward human or editorial-portrait basins."
        elif object_retained.get("yes", 0) >= max(2, record_count * 0.5) or object_count >= record_count:
            main = "Concrete object prompts mostly retained nonhuman/object-centered identity."
        elif human_count and object_count:
            main = "The run shows a mixed transition between object retention and human/agency resolution."

    key_signals = [
        _count_signal("Human primary", human_primary, record_count),
        _count_signal("Prototype human", prototype, record_count, key="human"),
        _count_signal("Embodiment human", embodiment, record_count, key="human"),
        _top_signal("Presentation grammar", presentation),
        _count_signal("Functional object retained", object_retained, record_count, key="yes"),
        _count_signal("Human accompaniment", human_accompaniment, record_count, key="yes"),
    ]
    if clothing:
        key_signals.append(_top_signal("Clothing-state leakage", clothing))

    return {
        "priority": 20,
        "protocol": "Semantic Agency Gradient",
        "confidence": "suggestive",
        "main_finding": main,
        "key_signals": [item for item in key_signals if item],
        "phenotype_meters": _sag_meters(
            record_count,
            prototype,
            embodiment,
            presentation,
            human_primary,
            object_retained,
            clothing,
            data,
        ),
        "transition_map": _sag_transition_map(data),
        "transition_groups": _sag_transition_groups(data),
        "inspect": _sag_inspect_items(data),
    }


def _sag_meters(
    record_count: int,
    prototype: dict[str, int],
    embodiment: dict[str, int],
    presentation: dict[str, int],
    human_primary: dict[str, int],
    object_retained: dict[str, int],
    clothing: dict[str, int],
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    human_value = _meter_value(max(human_primary.get("yes", 0), prototype.get("human", 0), embodiment.get("human", 0)), record_count)
    editorial_value = _meter_value(presentation.get("editorial_portrait", 0) + presentation.get("lifestyle_scene", 0), record_count)
    object_value = _meter_value(object_retained.get("yes", 0), record_count)
    creature_value = _meter_value(
        embodiment.get("creature", 0) + prototype.get("monster", 0) + prototype.get("animal", 0),
        record_count,
    )
    leakage_value = _meter_value(clothing.get("mild", 0) + clothing.get("moderate", 0) + clothing.get("strong", 0), record_count)
    stability_value = _semantic_stability_meter(data)
    return [
        _meter("Human Default Pull", human_value, f"{human_primary.get('yes', 0)} human-primary; {prototype.get('human', 0)} human prototypes"),
        _meter("Editorial Portrait Pull", editorial_value, f"{presentation.get('editorial_portrait', 0)} editorial-portrait presentations"),
        _meter("Object Retention", object_value, f"{object_retained.get('yes', 0)} / {record_count} functional-object retained"),
        _meter("Creature Manifold", creature_value, f"{embodiment.get('creature', 0)} creature embodiments"),
        _meter("Semantic Stability", stability_value, "Based on prompt-level prototype/embodiment persistence"),
        _meter("Clothing-State Leakage", leakage_value, f"{clothing.get('mild', 0) + clothing.get('moderate', 0) + clothing.get('strong', 0)} records with leakage labels"),
    ]


def _meter(name: str, value: int, evidence: str) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "label": _meter_label(value),
        "bar": "█" * value + "░" * (10 - value),
        "evidence": evidence,
    }


def _meter_value(count: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(10, round((count / total) * 10)))


def _meter_label(value: int) -> str:
    if value >= 7:
        return "Strong"
    if value >= 4:
        return "Moderate"
    if value >= 2:
        return "Weak"
    return "Low"


def _semantic_stability_meter(data: dict[str, Any]) -> int:
    prompts = data.get("prompt_persistence") or []
    if not prompts:
        return 0
    total = len(prompts)
    score = 0
    for item in prompts:
        labels = [item.get("prototype_persistence"), item.get("embodiment_persistence"), item.get("agency_persistence")]
        score += sum(1 for label in labels if label == "high") + 0.5 * sum(1 for label in labels if label == "moderate")
    return max(0, min(10, round((score / (total * 3)) * 10)))


def _sag_transition_map(data: dict[str, Any]) -> list[str]:
    prompts = data.get("prompt_persistence") or []
    items = []
    for item in prompts:
        embodiment = _normalized_counts(item.get("embodiment_counts", {}), "embodiment_level")
        agency = _normalized_counts(item.get("agency_counts", {}), "agency_level")
        presentation = _normalized_counts(item.get("presentation_grammar_counts", {}), "presentation_grammar")
        dominant = _dominant_label(embodiment) or _dominant_label(agency) or _dominant_label(presentation) or "unknown"
        items.append(f"{item.get('prompt')}: {dominant}")
    return items[:18]


def _sag_transition_groups(data: dict[str, Any]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for entry in _sag_transition_map(data):
        if ":" not in entry:
            continue
        prompt, target = entry.split(":", 1)
        groups.setdefault(target.strip(), []).append(prompt.strip())
    return dict(sorted(groups.items()))


def _sag_inspect_items(data: dict[str, Any]) -> list[str]:
    items = []
    for prompt in data.get("prompt_persistence") or []:
        if prompt.get("embodiment_persistence") == "low" or prompt.get("agency_persistence") == "low":
            items.append(f"Inspect `{prompt.get('prompt')}`: low embodiment/agency persistence.")
        human_accompaniment = _normalized_counts(prompt.get("human_accompaniment_counts", {}), "human_accompaniment")
        if human_accompaniment.get("yes", 0):
            items.append(f"Inspect `{prompt.get('prompt')}`: object may be retained with human accompaniment.")
    return items


def _fallback_main_finding(observer_sections: list[dict[str, Any]]) -> str:
    if not observer_sections:
        return "No observer output found yet."
    prototypes = Counter()
    for section in observer_sections:
        prototypes.update(section.get("prototype_counts", {}))
    if prototypes:
        label, count = prototypes.most_common(1)[0]
        return f"Dominant observed prototype: {label} ({count} records)."
    return "Observer output is present; inspect summaries for behavioral signals."


def _inspect_items(human_review: dict[str, Any], dashboards: list[dict[str, Any]]) -> list[str]:
    items = []
    for dashboard in dashboards:
        items.extend(dashboard.get("inspect", []))
    items.extend(human_review.get("suggestions", []))
    return items


def _extraction_section(observer_sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "observer_count": len(observer_sections),
        "schemas": dict(Counter(section.get("observer_schema") or "unspecified" for section in observer_sections)),
        "field_coverage_by_observer": [
            {
                "observer": section.get("observer", {}).get("id") or section.get("observer", {}).get("label") or Path(section.get("path", "")).parent.name,
                "field_coverage": section.get("field_coverage", {}),
            }
            for section in observer_sections
        ],
        "note": "Field coverage reports how many non-empty structured labels are visible in observer indexes.",
    }


def _human_review_section(
    observer_sections: list[dict[str, Any]],
    summary_sections: list[dict[str, Any]],
    routing_sections: list[dict[str, Any]],
) -> dict[str, Any]:
    review_records = [
        item
        for section in observer_sections
        for item in section.get("uncertainty_records", [])
    ]
    missing_prose_flags = [
        section
        for section in observer_sections
        if section.get("observer_schema") in ("", "sparse-semantic")
        and any(field in section.get("field_coverage", {}) for field in ("embodiment_level", "agency_level", "presentation_grammar"))
    ]
    return {
        "records_needing_review": len(review_records),
        "sample_review_records": review_records[:25],
        "observer_indexes_using_legacy_schema": [section.get("href") for section in missing_prose_flags],
        "summary_count": len(summary_sections),
        "routing_summary_count": len(routing_sections),
        "suggestions": _review_suggestions(review_records, observer_sections, routing_sections),
    }


def _review_suggestions(
    review_records: list[dict[str, Any]],
    observer_sections: list[dict[str, Any]],
    routing_sections: list[dict[str, Any]],
) -> list[str]:
    suggestions = []
    if review_records:
        suggestions.append("Inspect low-confidence or uncertain observer records before promoting phenotype claims.")
    if any(section.get("failures", 0) for section in observer_sections):
        suggestions.append("Resolve observer failures or mark them as excluded before dossier synthesis.")
    if not routing_sections:
        suggestions.append(
            "Recommended next step: run Phenotype Routing. This protocol measures one behavioral dimension; routing determines which additional investigations are supported by the current evidence."
        )
    return suggestions


def _field_coverage(records: list[dict[str, Any]]) -> dict[str, int]:
    interesting = [
        "prototype_class", "literalness", "animacy_resolution", "threat_bias", "observer_confidence",
        "embodiment_level", "agency_level", "presentation_grammar", "human_primary",
        "functional_object_retained", "human_accompaniment", "editorial_lifestyle_pull",
        "clothing_state_leakage",
    ]
    return {
        field: sum(1 for record in records if record.get(field) not in (None, "", [], "unknown"))
        for field in interesting
        if any(field in record for record in records)
    }


def _needs_review(record: dict[str, Any]) -> bool:
    if record.get("observer_failure"):
        return True
    if record.get("observer_confidence") == "low":
        return True
    if record.get("uncertainties") or record.get("sag_uncertainties"):
        return True
    return any(record.get(field) == "unknown" for field in ("prototype_class", "embodiment_level", "agency_level", "presentation_grammar"))


def _counts(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(record.get(key)) for record in records if record.get(key) not in (None, "", "unknown")).most_common())


def _summary_record_count(data: dict[str, Any]) -> int | None:
    if "overall" in data and isinstance(data["overall"], dict):
        return data["overall"].get("record_count")
    if "recommendations" in data:
        return len(data.get("recommendations") or [])
    if "records" in data:
        return len(data.get("records") or [])
    return None


def _top_level_counts(data: dict[str, Any]) -> dict[str, Any]:
    counts = {}
    overall = data.get("overall")
    if isinstance(overall, dict):
        for key, value in overall.items():
            if key.endswith("_counts") and isinstance(value, dict):
                counts[key] = value
    if "recommendations" in data:
        counts["recommendations"] = len(data.get("recommendations") or [])
    if "recommended_sidecars" in data:
        counts["recommended_sidecars"] = len(data.get("recommended_sidecars") or [])
    if "not_recommended" in data:
        counts["not_recommended"] = len(data.get("not_recommended") or [])
    if "not_recommended_sidecars" in data:
        counts["not_recommended_sidecars"] = len(data.get("not_recommended_sidecars") or [])
    return counts


def _normalized_counts(counts: dict[str, Any], field: str) -> dict[str, int]:
    normalized: Counter[str] = Counter()
    for raw, count in (counts or {}).items():
        normalized[_normalize_label(field, raw)] += int(count or 0)
    return dict(normalized.most_common())


def _normalize_label(field: str, value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace(" ", "_").replace("-", "_")
    if field == "embodiment_level":
        if "human" in text or "person" in text:
            return "human"
        if "creature" in text or "animal" in text or "monster" in text:
            return "creature"
        if "object" in text or "artifact" in text or "device" in text or "tool" in text:
            return "object"
        if "partial" in text:
            return "partial"
        if "mixed" in text:
            return "mixed"
        if "none" in text:
            return "none"
    if field == "agency_level":
        if "social_role" in text or "role" in text:
            return "social_role"
        if "person" in text or "human" in text:
            return "person"
        if "animal" in text or "creature" in text:
            return "animal"
        if "implicit" in text:
            return "implicit"
        if "mixed" in text:
            return "mixed"
        if "none" in text:
            return "none"
    if field == "presentation_grammar":
        if "editorial_portrait" in text:
            return "editorial_portrait"
        if "studio_object" in text:
            return "studio_object"
        if "product_render" in text:
            return "product_render"
        if "lifestyle" in text:
            return "lifestyle_scene"
        if "narrative" in text:
            return "narrative_scene"
        if any(token in text for token in ("media_layout", "poster", "card", "cover")):
            return "media_layout"
        if "symbolic" in text:
            return "symbolic_presentation"
        if "abstract" in text:
            return "abstract_field"
    if field == "editorial_lifestyle_pull":
        for level in ("strong", "moderate", "weak", "none"):
            if level in text:
                return level
    if field == "clothing_state_leakage":
        for level in ("strong", "moderate", "mild", "none", "not_applicable"):
            if level in text:
                return level
    if field in {"human_primary", "creature_primary", "functional_object_retained", "human_accompaniment"}:
        if text.startswith("yes") or text in {"true", "present"}:
            return "yes"
        if text.startswith("no") or text in {"false", "absent"}:
            return "no"
        if "partial" in text:
            return "partial"
        if "not_applicable" in text:
            return "not_applicable"
    return text or "unknown"


def _count_signal(label: str, counts: dict[str, int], total: int, key: str = "yes") -> str:
    if not counts:
        return ""
    count = counts.get(key, 0)
    return f"{label}: {count} / {total}" if total else f"{label}: {count}"


def _top_signal(label: str, counts: dict[str, int]) -> str:
    if not counts:
        return ""
    top, count = Counter(counts).most_common(1)[0]
    return f"{label}: mostly {top} ({count})"


def _dominant_label(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    return Counter(counts).most_common(1)[0][0]


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _title_from_run_root(run_root: Path) -> str:
    name = run_root.name
    if name.startswith("run_"):
        name = name[4:]
    return name.replace("_", " ").title()


def _discover_observer_indexes(run_root: Path) -> list[Path]:
    patterns = [
        "observer_runs/*/ssp_observer_index.json",
        "observer_runs/*/basin_observer_index.json",
        "observer_runs/*/observer_index.json",
    ]
    return _discover(run_root, patterns)


def _discover_summaries(run_root: Path) -> list[Path]:
    return [
        path for path in _discover(run_root, ["observer_runs/**/*.json"])
        if path.name in {
            "semantic_entropy_summary.json",
            "semantic_agency_gradient_summary.json",
        }
    ]


def _discover_routing_summaries(run_root: Path) -> list[Path]:
    return [
        path for path in _discover(run_root, ["observer_runs/**/*.json"])
        if path.name in {"phenotype_routing_summary.json", "phenotype_routing_recommendations.json"}
    ]


def _discover(root: Path, patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(set(found))


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _existing_links(output_root: Path, paths: list[Path]) -> list[dict[str, str]]:
    return [
        {"label": path.name, "path": str(path), "href": _link(output_root, path)}
        for path in paths
        if path and path.exists()
    ]


def _link(output_root: Path, path: Path | None) -> str:
    if not path:
        return ""
    try:
        return os.path.relpath(str(path.resolve()), str(output_root.resolve())).replace("\\", "/")
    except ValueError:
        return path.resolve().as_uri()


def _html(review: dict[str, Any], output_root: Path) -> str:
    generation = review["generation"]
    provenance = review["provenance"]
    glance = review["at_a_glance"]
    observer_cards = "".join(_observer_card(section) for section in review["observation"])
    summary_cards = "".join(_summary_card(section) for section in review["summaries"])
    routing_cards = "".join(_summary_card(section) for section in review["routing"])
    contact_links = "".join(_asset_link(item) for item in generation.get("contact_sheets", []))
    suggestions = "".join(f"<li>{escape(item)}</li>" for item in review["human_review"].get("suggestions", []))
    review_records = "".join(_review_record_row(item) for item in review["human_review"].get("sample_review_records", []))
    signal_items = "".join(f"<li>{escape(item)}</li>" for item in glance.get("key_signals", []))
    inspect_items = "".join(f"<li>{escape(item)}</li>" for item in glance.get("what_to_inspect", []))
    run_next_items = "".join(f"<li>{escape(item)}</li>" for item in glance.get("what_to_run_next", []))
    meter_cards = "".join(_meter_card(item) for item in glance.get("phenotype_meters", []))
    interpretation_items = "".join(f"<li>{escape(item)}</li>" for item in glance.get("behavioral_interpretation", []))
    evidence_items = "".join(f"<li>{escape(item)}</li>" for item in glance.get("evidence_basis", []))
    routing_bar_cards = "".join(_routing_bar_card(item) for item in glance.get("routing_bars", []))
    neighborhood_cards = "".join(_neighborhood_card(item) for item in glance.get("neighborhood_behaviors", []))
    transition_groups = _transition_group_html(glance.get("transition_groups", {}))
    transition_items = "".join(f"<li>{escape(item)}</li>" for item in glance.get("transition_map", []))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CEF Run Pipeline Review</title>
<style>
body{{font:14px Segoe UI,Arial,sans-serif;margin:24px;background:#f6f4ee;color:#20231f;line-height:1.45}}
h1,h2,h3{{margin-bottom:.25rem}} .muted{{color:#62675f}} code,pre{{white-space:pre-wrap}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.hero{{display:grid;grid-template-columns:2fr 1fr;gap:14px;margin:18px 0}}
.card{{background:#fff;border:1px solid #d7d2c5;border-radius:10px;padding:12px;box-shadow:0 1px 2px #0001}}
.finding{{font-size:18px;margin:.4rem 0 0}}
.snapshot{{display:grid;grid-template-columns:130px 1fr;gap:6px;margin-top:10px}} .snapshot dt{{font-weight:700;color:#514d43}} .snapshot dd{{margin:0}}
.meters{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:14px 0}}
.meter-name{{font-weight:700}} .meter-bar{{font-family:Consolas,monospace;font-size:18px;letter-spacing:1px;color:#315c8a}} .meter-label{{font-weight:700}}
.routing-bars{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}}
.route-bar{{font-family:Consolas,monospace;font-size:17px;color:#315c8a;letter-spacing:1px}}
.abstract{{font-size:15px;background:#fffefb;border-left:4px solid #315c8a}}
.transition{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}} .transition h3{{margin-top:0}} .transition ul{{margin-top:.25rem}}
table{{border-collapse:collapse;width:100%;background:#fff}} th,td{{border:1px solid #d7d2c5;padding:8px;vertical-align:top}} th{{background:#ece7da;text-align:left}}
a{{color:#315c8a}} .pill{{display:inline-block;background:#ece7da;border-radius:999px;padding:2px 8px;margin:2px}}
details{{margin-top:8px}} summary{{cursor:pointer;color:#315c8a;font-weight:600}} pre{{background:#fbfaf6;border:1px solid #e1ddd1;border-radius:8px;padding:10px;overflow:auto}}
.status{{font-weight:700}} .status.Complete{{color:#24633b}} .status.Incomplete{{color:#8a4a20}}
@media (max-width: 850px){{.hero{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>{escape(str(glance.get("title") or "CEF Run Pipeline Review"))}</h1>
<p class="muted">{escape(review["doctrine"])}</p>
<p><strong>Run root:</strong> <code>{escape(review["run_root"])}</code></p>

<section class="hero">
<div class="card">
<h2>Behavioral Snapshot</h2>
<p><strong>Status:</strong> <span class="status">{escape(str(glance.get("status")))}</span> |
<strong>Images:</strong> {escape(str(glance.get("images")))} |
<strong>Observer:</strong> {escape(", ".join(str(x) for x in glance.get("observers", [])) or "none")}</p>
<dl class="snapshot">
<dt>Checkpoint</dt><dd>{escape(str(glance.get("title") or ""))}</dd>
<dt>Protocol</dt><dd>{escape(str(glance.get("protocol") or ""))}</dd>
<dt>Confidence</dt><dd>{escape(str(glance.get("confidence") or ""))}</dd>
</dl>
<p class="finding"><strong>Phenotype signal:</strong> {escape(str(glance.get("main_finding") or "No main finding available yet."))}</p>
</div>
<div class="card">
<h2>Key signals</h2>
<ul>{signal_items or "<li>No key signals extracted yet.</li>"}</ul>
</div>
</section>

<h2>Behavioral Interpretation</h2>
<section class="grid">
<div class="card">
<h3>Observed phenotype</h3>
<ul>{interpretation_items or "<li>No behavioral interpretation layer available for this run type.</li>"}</ul>
</div>
<div class="card">
<h3>Evidence basis</h3>
<ul>{evidence_items or "<li>No evidence basis available.</li>"}</ul>
</div>
</section>

<h2>Recommended Investigations</h2>
<section class="routing-bars">{routing_bar_cards or '<div class="card">No routing bars available.</div>'}</section>

<h2>Neighborhood Behavior</h2>
<section class="routing-bars">{neighborhood_cards or '<div class="card">No neighborhood behavior cards available.</div>'}</section>

<h2>What did we learn?</h2>
<section class="meters">{meter_cards or '<div class="card">No phenotype meters available for this run type.</div>'}</section>

<section class="grid">
<div class="card"><h2>What should I inspect?</h2><ul>{inspect_items or "<li>No review-specific inspection items surfaced.</li>"}</ul></div>
<div class="card"><h2>What should I run next?</h2><ul>{run_next_items or "<li>No routing recommendations found yet.</li>"}</ul></div>
</section>

<h2>Transition map</h2>
<div class="card">{transition_groups or f'<ul>{transition_items or "<li>No transition map available for this run type.</li>"}</ul>'}</div>

<h2>Phenotype Abstract</h2>
<div class="card abstract">{escape(str(glance.get("phenotype_abstract") or "No phenotype abstract available for this run type."))}</div>

<h2>1. Generation</h2>
<div class="card">
<p><strong>Status:</strong> {escape(generation["status"])} | <strong>Records:</strong> {generation["record_count"]} | <strong>Images:</strong> {generation["image_count"]}</p>
<p>{_maybe_link("generation_index.json", generation.get("generation_index"))} {_maybe_link("manifest", generation.get("manifest"))}</p>
<p>{contact_links}</p>
<details><summary>Checkpoint counts</summary><pre>{escape(json.dumps(generation.get("checkpoint_counts", {}), indent=2, sort_keys=True))}</pre></details>
</div>

<h2>2. Provenance</h2>
<div class="card">
<p><strong>Status:</strong> {escape(provenance["status"])} | <strong>Images:</strong> {escape(str(provenance.get("image_count", "")))} | <strong>Failures:</strong> {escape(str(provenance.get("failure_count", "")))}</p>
<p>{_maybe_link("png_provenance_index.json", provenance.get("provenance_index"))}</p>
<details><summary>Provenance detail</summary><pre>{escape(json.dumps({"png_text_keys": provenance.get("png_text_keys", {}), "contributors": provenance.get("contributor_counts", {})}, indent=2, sort_keys=True))}</pre></details>
</div>

<h2>3. Observation</h2>
<div class="grid">{observer_cards or '<p>No observer indexes found.</p>'}</div>

<h2>4. Extraction</h2>
<div class="card"><p>Structured label coverage by observer. Use this to see whether data was captured as fields or only recoverable from prose.</p><details><summary>Extraction detail</summary><pre>{escape(json.dumps(review["extraction"], indent=2, sort_keys=True))}</pre></details></div>

<h2>5. Summaries</h2>
<div class="grid">{summary_cards or '<p>No aggregate summaries found.</p>'}</div>

<h2>6. Routing</h2>
<div class="grid">{routing_cards or '<p>No routing summaries found.</p>'}</div>

<h2>7. Human Review</h2>
<div class="card">
<p><strong>Records needing review:</strong> {review["human_review"].get("records_needing_review", 0)}</p>
<ul>{suggestions}</ul>
<table><thead><tr><th>Test</th><th>Prompt</th><th>Confidence</th><th>Uncertainties / Summary</th></tr></thead><tbody>{review_records}</tbody></table>
</div>
</body>
</html>"""


def _observer_card(section: dict[str, Any]) -> str:
    links = "".join(_asset_link(item) for item in section.get("report_links", []))
    prototype = _top_signal("Prototype", section.get("prototype_counts", {}))
    confidence = _top_signal("Confidence", section.get("confidence_counts", {}))
    return (
        "<article class=\"card\">"
        f"<h3>{escape(str(section.get('observer', {}).get('label') or section.get('observer', {}).get('id') or Path(section.get('path', '')).parent.name))}</h3>"
        f"<p>{_maybe_link('observer index', section.get('href'))}</p>"
        f"<p><span class=\"pill\">schema: {escape(str(section.get('observer_schema') or 'unspecified'))}</span> "
        f"<span class=\"pill\">records: {escape(str(section.get('record_count')))}</span> "
        f"<span class=\"pill\">failures: {escape(str(section.get('failures')))}</span></p>"
        f"<p>{escape(prototype)}<br>{escape(confidence)}</p>"
        f"<p>{links}</p>"
        f"<details><summary>Observer counts and field coverage</summary><pre>{escape(json.dumps({'prototypes': section.get('prototype_counts', {}), 'confidence': section.get('confidence_counts', {}), 'field_coverage': section.get('field_coverage', {})}, indent=2, sort_keys=True))}</pre></details>"
        "</article>"
    )


def _summary_card(section: dict[str, Any]) -> str:
    links = "".join(_asset_link(item) for item in section.get("companion_links", []))
    dashboard = section.get("dashboard", {})
    signals = "".join(f"<li>{escape(item)}</li>" for item in dashboard.get("key_signals", []))
    return (
        "<article class=\"card\">"
        f"<h3>{escape(str(section.get('artifact_type')))}</h3>"
        f"<p>{_maybe_link(Path(section.get('path', '')).name, section.get('href'))}</p>"
        f"<p><span class=\"pill\">records: {escape(str(section.get('record_count')))}</span> "
        f"<span class=\"pill\">schema: {escape(str(section.get('schema_version')))}</span></p>"
        f"<p>{escape(str(dashboard.get('main_finding') or 'Summary artifact available.'))}</p>"
        f"<ul>{signals}</ul>"
        f"<p>{links}</p>"
        f"<details><summary>Summary counts</summary><pre>{escape(json.dumps(section.get('key_counts', {}), indent=2, sort_keys=True))}</pre></details>"
        "</article>"
    )


def _meter_card(item: dict[str, Any]) -> str:
    return (
        "<article class=\"card\">"
        f"<div class=\"meter-name\">{escape(str(item.get('name')))}</div>"
        f"<div class=\"meter-bar\" aria-label=\"{escape(str(item.get('value')))} out of 10\">{escape(str(item.get('bar')))}</div>"
        f"<div class=\"meter-label\">{escape(str(item.get('label')))}</div>"
        f"<p class=\"muted\">Evidence: {escape(str(item.get('evidence') or ''))}</p>"
        "</article>"
    )


def _routing_bar_card(item: dict[str, Any]) -> str:
    evidence = item.get("evidence_count")
    evidence_text = f"Evidence tests: {evidence}" if evidence is not None else "Evidence count not provided"
    return (
        "<article class=\"card\">"
        f"<div class=\"meter-name\">{escape(str(item.get('label')))}</div>"
        f"<div class=\"route-bar\">{escape(str(item.get('bar')))}</div>"
        f"<div class=\"meter-label\">{escape(str(item.get('strength')).title())}</div>"
        f"<p class=\"muted\">{escape(evidence_text)}</p>"
        "</article>"
    )


def _neighborhood_card(item: dict[str, Any]) -> str:
    value = int(item.get("value") or 0)
    bar = "■" * value + "□" * max(0, 10 - value)
    return (
        "<article class=\"card\">"
        f"<h3>{escape(str(item.get('neighborhood')))}</h3>"
        f"<div class=\"route-bar\">{escape(bar)}</div>"
        f"<p><strong>{escape(str(item.get('behavior')).replace('_', ' ').title())}</strong></p>"
        f"<p class=\"muted\">Dominant prototype: {escape(str(item.get('dominant_prototype')))} | entropy: {escape(str(item.get('entropy')))}</p>"
        f"<p>{escape(str(item.get('note') or ''))}</p>"
        "</article>"
    )


def _transition_group_html(groups: dict[str, list[str]]) -> str:
    if not groups:
        return ""
    order = ["human", "person", "social_role", "object", "creature", "animal", "mixed", "unknown"]
    keys = sorted(groups, key=lambda key: (order.index(key) if key in order else len(order), key))
    cards = []
    for key in keys:
        prompts = "".join(f"<li>{escape(prompt)}</li>" for prompt in groups.get(key, []))
        cards.append(
            "<article>"
            f"<h3>{escape(str(key).replace('_', ' ').title())}</h3>"
            f"<ul>{prompts}</ul>"
            "</article>"
        )
    return f"<div class=\"transition\">{''.join(cards)}</div>"


def _asset_link(item: dict[str, str]) -> str:
    return _maybe_link(item.get("label", "artifact"), item.get("href"))


def _maybe_link(label: str, href: str | None) -> str:
    if not href:
        return ""
    return f"<a href=\"{escape(href)}\">{escape(label)}</a> "


def _review_record_row(item: dict[str, Any]) -> str:
    uncertainty = item.get("uncertainties") or []
    if isinstance(uncertainty, list):
        uncertainty_text = "; ".join(str(value) for value in uncertainty)
    else:
        uncertainty_text = str(uncertainty)
    summary = item.get("summary") or ""
    return (
        "<tr>"
        f"<td>{escape(str(item.get('test_id')))}</td>"
        f"<td>{escape(repr(item.get('prompt')))}</td>"
        f"<td>{escape(str(item.get('confidence')))}</td>"
        f"<td>{escape(uncertainty_text)}<br>{escape(str(summary))}</td>"
        "</tr>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a one-page CEF run pipeline review dashboard.")
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--observer-index", action="append", type=Path)
    parser.add_argument("--summary", action="append", type=Path)
    parser.add_argument("--routing-summary", action="append", type=Path)
    args = parser.parse_args()

    review = build_review(
        run_root=args.run_root,
        output_root=args.output_root,
        manifest=args.manifest,
        observer_indexes=args.observer_index,
        summaries=args.summary,
        routing_summaries=args.routing_summary,
    )
    print(json.dumps({"review_json": review["review_json"], "review_html": review["review_html"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
