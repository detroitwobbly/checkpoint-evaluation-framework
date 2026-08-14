from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


DOSSIER_SCHEMA_VERSION = "1.0"


def build_checkpoint_dossier(
    run_roots: list[Path],
    output_root: Path,
    title: str | None = None,
    checkpoint_id: str | None = None,
    schema_version: str = DOSSIER_SCHEMA_VERSION,
    interpretation_mode: str | None = None,
    interpretation_mode_note: str | None = None,
    ssp_indexes: list[Path] | None = None,
) -> dict[str, Any]:
    if not run_roots:
        raise ValueError("At least one --run-root is required.")
    suites = [_load_suite_bundle(path) for path in run_roots]
    resolved_checkpoint_id = checkpoint_id or _infer_checkpoint_id(suites)
    dossier = {
        "schema_version": schema_version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "title": title or f"{_display_checkpoint_name(resolved_checkpoint_id)} Evaluation Dossier",
        "checkpoint_id": resolved_checkpoint_id,
        "scope_and_limits": _scope_and_limits(schema_version),
        "summary": _summary(suites),
        "behavioral_phenotype_card": _behavioral_phenotype_card(
            suites,
            interpretation_mode=interpretation_mode,
            interpretation_mode_note=interpretation_mode_note,
        ),
        "conditions": _conditions(suites),
        "suite_overview": [_suite_overview_item(suite, output_root) for suite in suites],
        "capability_profile": _capability_profile(suites),
        "behavioral_signals": _behavioral_signals(suites),
        "characteristic_tensions": _characteristic_tensions(suites),
        "working_characterization": _working_characterization(suites),
        "characterization_confidence": _characterization_confidence(suites),
        "known_unknowns": _known_unknowns(suites),
        "evaluator_agreement": _evaluator_agreement(suites),
        "representative_gallery": _representative_gallery(suites, output_root),
        "observation_blocks": _observation_blocks(suites, output_root),
        "appendix": _appendix(suites, output_root),
        "exploratory_artifacts": _exploratory_artifacts(resolved_checkpoint_id, output_root),
        "sparse_semantic_profiles": _sparse_semantic_profiles(ssp_indexes or [], output_root),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "dossier.json").write_text(json.dumps(dossier, indent=2, sort_keys=True), encoding="utf-8")
    (output_root / "dossier.html").write_text(_html(dossier, output_root), encoding="utf-8")
    handoff = _chatgpt_meta_handoff(dossier, suites, output_root)
    (output_root / "chatgpt_meta_handoff.json").write_text(
        json.dumps(handoff, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_root / "chatgpt_meta_handoff.md").write_text(_handoff_markdown(handoff), encoding="utf-8")
    return dossier


def _sparse_semantic_profiles(index_paths: list[Path], output_root: Path) -> list[dict[str, Any]]:
    profiles = []
    for path in index_paths:
        index = _read_json(path)
        if index.get("artifact_type") != "sparse_semantic_observer_index":
            raise ValueError(f"Not an SSP observer index: {path}")
        profiles.append({
            "observer": index.get("observer", {}),
            "observed_images": index.get("observed_images", 0),
            "failures": index.get("failures", 0),
            "methodological_justification": index.get("methodological_justification", ""),
            "semantic_phenotype": index.get("semantic_phenotype", {}),
            "index_href": _relative(output_root, path),
            "report_href": _optional_relative(output_root, path.parent / "ssp_report.html"),
            "contact_sheet_href": _optional_relative(output_root, path.parent / "ssp_contact_sheet.jpg"),
            "behavioral_records_href": _optional_relative(output_root, path.parent / "behavioral_observation_records.json"),
        })
    return profiles


def _load_suite_bundle(run_root: Path) -> dict[str, Any]:
    report_path = run_root / "report.json"
    generation_path = run_root / "generation_index.json"
    manifest_path = run_root / "run_manifest.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing report.json for dossier input: {report_path}")
    report = _read_json(report_path)
    generation = _read_json(generation_path) if generation_path.exists() else {}
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    judge_path = run_root / "judge_auditor_qwen3_minicpm45_review_queue.json"
    judge = _read_json(judge_path) if judge_path.exists() else {}
    auditor_report_path = run_root / "analysis_runs" / "minicpm_auditor" / "report.json"
    auditor_report = _read_json(auditor_report_path) if auditor_report_path.exists() else {}
    return {
        "run_root": run_root,
        "report": report,
        "generation": generation,
        "manifest": manifest,
        "judge_auditor": judge,
        "auditor_report": auditor_report,
    }


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return loaded


def _scope_and_limits(schema_version: str) -> dict[str, str]:
    return {
        "title": "Scope of this dossier",
        "text": (
            "This dossier characterizes observed checkpoint behavior under the tested conditions. "
            "It does not claim to measure intrinsic capability, hidden representations, or all possible behaviors. "
            "Conclusions apply only to the checkpoint version, generation settings, evaluator roster, and prompt suites "
            "documented in Layer 0."
        ),
        "schema_version": schema_version,
    }


def _summary(suites: list[dict[str, Any]]) -> dict[str, Any]:
    records = _all_records(suites)
    counts = _pass_fail_counts(records)
    suite_count = len(suites)
    image_count = len(records)
    return {
        "suite_count": suite_count,
        "image_count": image_count,
        "average_score": _average([_float(record.get("overall_score")) for record in records]),
        "pass_count": counts["pass"],
        "conditional_pass_count": counts["conditional_pass"],
        "fail_count": counts["fail"],
        "evaluator_roster": _evaluator_roster(suites),
        "overall_characterization": _overall_characterization(suites),
    }


def _conditions(suites: list[dict[str, Any]]) -> dict[str, Any]:
    checkpoint_titles = sorted(
        {
            str(record.get("checkpoint_title"))
            for record in _all_records(suites)
            if record.get("checkpoint_title")
        }
    )
    hashes = sorted(
        {
            str(record.get("checkpoint_hash"))
            for suite in suites
            for record in suite.get("generation", {}).get("records", [])
            if record.get("checkpoint_hash")
        }
    )
    manifests = []
    for suite in suites:
        manifest = suite.get("manifest", {})
        defaults = manifest.get("defaults", {})
        manifests.append(
            {
                "run_id": suite["run_root"].name,
                "suite_id": manifest.get("suite_id") or suite.get("report", {}).get("run_id"),
                "name": manifest.get("name") or suite["run_root"].name,
                "defaults": defaults,
                "tests": len(manifest.get("tests", [])),
            }
        )
    return {
        "checkpoint_titles": checkpoint_titles,
        "checkpoint_hashes": hashes,
        "manifests": manifests,
        "primary_evaluator": "Qwen3-VL-8B primary where available in suite snapshots",
        "auditor": "MiniCPM-V 4.5 auditor where comparison artifacts are present",
    }


def _suite_overview_item(suite: dict[str, Any], output_root: Path) -> dict[str, Any]:
    run_root = suite["run_root"]
    report = suite["report"]
    records = report.get("records", [])
    counts = _pass_fail_counts(records)
    judge = suite.get("judge_auditor", {}).get("summary", {})
    return {
        "run_id": report.get("run_id") or run_root.name,
        "suite_name": suite.get("manifest", {}).get("name") or _suite_label(run_root.name),
        "images": len(records),
        "average_score": _average([_float(record.get("overall_score")) for record in records]),
        "pass": counts["pass"],
        "conditional_pass": counts["conditional_pass"],
        "fail": counts["fail"],
        "tier_a": judge.get("tier_a_review_required"),
        "tier_b": judge.get("tier_b_auditor_note_review"),
        "tier_c": judge.get("tier_c_calibration_review"),
        "report_href": _relative(output_root, run_root / "report.html"),
        "contact_sheet_href": _optional_relative(output_root, run_root / "report_assets" / "contact_sheet.jpg"),
        "comparison_href": _optional_relative(output_root, run_root / "evaluator_comparison_qwen3_minicpm45.html"),
        "review_href": _optional_relative(output_root, run_root / "judge_auditor_qwen3_minicpm45_review_queue.md"),
    }


def _capability_profile(suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = _all_records(suites)
    categories = [
        ("Photographic realism", ("face", "skin", "photoreal", "realistic", "photo"), ("face_quality", "environment_quality")),
        ("Human anatomy", ("anatomy", "body", "hands", "feet", "pose", "chest"), ("anatomy", "hand_quality", "foot_quality")),
        ("Age persistence", ("age_sweep", "older", "senior", "middle-aged", "50s", "70s", "adult age"), ("face_quality",)),
        ("Body diversity", ("body_type", "build", "slender", "curvy", "plus-size", "heavyset", "average build"), ("anatomy",)),
        ("Animal anatomy", ("horse", "dog", "animal", "conformation"), ("anatomy",)),
        ("Composition", ("composition", "perspective", "overhead", "mirror"), ("composition",)),
        ("Conceptual prior", ("concept", "hallucination", "prior"), ("prompt_adherence", "style_adherence")),
        ("LoRA robustness", ("lora", "adapter", "trigger", "weight", "identity"), ("identity_retention", "lora_integration")),
        ("Constraint fidelity", ("clothing", "integrity", "prompt", "object", "interaction"), ("prompt_adherence", "object_interaction")),
        ("Environmental realism", ("environment", "ecology", "kitchen", "street", "library", "jungle"), ("environment_quality",)),
    ]
    profile = []
    for label, hints, rubrics in categories:
        matched = [record for record in records if any(hint in _record_text(record) for hint in hints)]
        score = _average([_float(record.get("overall_score")) for record in matched])
        rubric_score = _average(
            [
                _float(record.get("rubric_scores", {}).get(rubric))
                for record in matched
                for rubric in rubrics
                if isinstance(record.get("rubric_scores"), dict)
            ]
        )
        effective = score if score is not None else rubric_score
        profile.append(
            {
                "label": label,
                "score": effective,
                "rating": _rating(effective),
                "evidence_count": len(matched),
            }
        )
    return profile


def _behavioral_signals(suites: list[dict[str, Any]]) -> dict[str, Any]:
    records = _all_records(suites)
    conceptual = [record for record in records if str(record.get("test_id", "")).startswith(("HALLUCINATION_", "CONCEPT_"))]
    return {
        "default_subject": _rank_terms(conceptual or records, _SUBJECT_TERMS),
        "default_mood": _rank_terms(conceptual or records, _MOOD_TERMS),
        "default_visual_language": _rank_terms(conceptual or records, _VISUAL_TERMS),
        "latent_attractors": _top_observation_categories(records),
        "failure_personality": _failure_personality(records),
        "lora_compatibility_profile": _lora_profile(records),
        "recovery_tendencies": _recovery_tendencies(records),
    }


def _behavioral_phenotype_card(
    suites: list[dict[str, Any]],
    interpretation_mode: str | None = None,
    interpretation_mode_note: str | None = None,
) -> dict[str, Any]:
    profile = {item["label"]: item for item in _capability_profile(suites)}
    records = _all_records(suites)
    conceptual = [record for record in records if str(record.get("test_id", "")).startswith(("HALLUCINATION_", "CONCEPT_"))]
    symbolic = [record for record in conceptual if any(term in _observation_text(record) for term in ("symbol", "metaphor", "atmospheric", "solitude", "cosmic", "ritual", "threshold"))]
    poster = [record for record in conceptual if any(term in _observation_text(record) for term in ("poster", "literal text", "typography"))]
    conceptual_score = _average([_float(record.get("overall_score")) for record in conceptual])
    return {
        "title": "Behavioral Phenotype Card",
        "display_title": "Checkpoint Behavioral Profile",
        "personality_summary": _checkpoint_personality_summary(
            profile,
            records,
            conceptual,
            symbolic,
            poster,
            suites,
            interpretation_mode=interpretation_mode,
            interpretation_mode_note=interpretation_mode_note,
        ),
        "natural_attractors": _phenotype_attractors(profile, records, symbolic, poster, conceptual_score),
        "resistances": _phenotype_resistances(profile, records),
        "best_prompt_families": _recommended_roles({"capability_profile": list(profile.values()), "characteristic_tensions": []}),
        "weakness_triggers": _not_recommended_for({"capability_profile": list(profile.values()), "characteristic_tensions": _characteristic_tensions(suites)}),
        "distinctive_traits": _distinctive_traits(profile, symbolic, poster),
        "recommended_role": _recommended_roles({"capability_profile": list(profile.values()), "characteristic_tensions": []}),
        "not_recommended_without_review": _not_recommended_for({"capability_profile": list(profile.values()), "characteristic_tensions": _characteristic_tensions(suites)}),
    }


def _checkpoint_personality_summary(
    profile: dict[str, dict[str, Any]],
    records: list[dict[str, Any]],
    conceptual: list[dict[str, Any]],
    symbolic: list[dict[str, Any]],
    poster: list[dict[str, Any]],
    suites: list[dict[str, Any]],
    interpretation_mode: str | None = None,
    interpretation_mode_note: str | None = None,
) -> dict[str, Any]:
    literal_terms = ("literal", "stock photo", "commercial", "straightforward", "documentary", "typography", "poster")
    literal_count = sum(1 for record in conceptual if any(term in _observation_text(record) for term in literal_terms))
    literal_count = max(literal_count, len(poster))
    symbolic_count = len(symbolic)
    initiative, initiative_note = _aesthetic_initiative(records, _prompt_by_test_id(suites))
    inferred_mode, inferred_mode_note = _mode_of_interpretation(records, _prompt_by_test_id(suites))
    resolved_mode = interpretation_mode or inferred_mode
    resolved_mode_note = interpretation_mode_note or inferred_mode_note
    mode_basis = "Human/contact-sheet adjudication" if interpretation_mode else "Evaluator-observation synthesis"
    return {
        "realism_bias": _qualitative_axis(profile.get("Photographic realism", {}).get("score")),
        "literalness": _balance_axis(literal_count, symbolic_count),
        "prompt_obedience": _qualitative_axis(profile.get("Constraint fidelity", {}).get("score")),
        "interpretive_tendency": _balance_axis(symbolic_count, literal_count),
        "mode_of_interpretation": resolved_mode,
        "mode_of_interpretation_note": resolved_mode_note,
        "mode_of_interpretation_basis": mode_basis,
        "aesthetic_initiative": initiative,
        "aesthetic_initiative_note": initiative_note,
        "conceptual_resolutions": _conceptual_resolutions(conceptual),
        "failure_style": _personality_failure_style(records),
        "basis": "Qualitative synthesis derived from the recorded suites; these labels are not additional scores.",
    }


def _mode_of_interpretation(records: list[dict[str, Any]], prompts: dict[str, str] | None = None) -> tuple[str, str]:
    """Describe the checkpoint's recurring visual language without scoring it."""
    if not records:
        return "Undetermined", "No observational evidence was available."
    families = {
        "Editorial / documentary": (
            "documentary",
            "editorial",
            "magazine",
            "reportage",
            "photojournal",
            "candid",
            "lifestyle photograph",
            "observational photograph",
        ),
        "Photographic / literal": (
            "literal photograph",
            "literal photo",
            "stock photo",
            "stock image",
            "straightforward photograph",
            "conventional photograph",
            "literal depiction",
        ),
        "Cinematic realism": (
            "cinematic",
            "film still",
            "movie still",
            "dramatic lighting",
            "dramatically lit",
        ),
        "Painterly / symbolic": (
            "painterly",
            "symbolic",
            "metaphor",
            "allegory",
            "surreal",
            "watercolor",
            "oil painting",
            "brushwork",
        ),
        "Graphic / typographic": (
            "graphic design",
            "graphic novel",
            "poster",
            "typography",
            "comic",
            "cel-shaded",
        ),
    }
    family_records: dict[str, set[int]] = {label: set() for label in families}
    family_signals: dict[str, Counter[str]] = {label: Counter() for label in families}
    prompt_map = prompts or {}
    for index, record in enumerate(records):
        observed = _observation_text(record)
        prompt = prompt_map.get(str(record.get("test_id") or ""), "").lower()
        for label, terms in families.items():
            matched = [term for term in terms if term in observed and term not in prompt]
            if matched:
                family_records[label].add(index)
                family_signals[label].update(matched)
    ranked = sorted(families, key=lambda label: (len(family_records[label]), label), reverse=True)
    winner = ranked[0]
    evidence_count = len(family_records[winner])
    if not evidence_count:
        return "Undetermined", "No recurring interpretive-language signal was detected in evaluator observations."
    runner_up_count = len(family_records[ranked[1]]) if len(ranked) > 1 else 0
    confidence = "High" if evidence_count >= 12 and evidence_count >= runner_up_count * 1.5 else "Medium" if evidence_count >= 5 else "Low"
    signals = ", ".join(term for term, _count in family_signals[winner].most_common(3))
    note = f"{evidence_count} of {len(records)} records carried {winner.lower()} signals"
    if signals:
        note += f" (most often: {signals})"
    note += f". Categorical synthesis confidence: {confidence}; this is not a score or an obedience judgment."
    return winner, note


def _aesthetic_initiative(records: list[dict[str, Any]], prompts: dict[str, str]) -> tuple[str, str]:
    if not records:
        return "Undetermined", "No prompt-relative evidence was available."
    families = {
        "painterly or illustrative treatment": (
            ("painterly", "illustration", "watercolor", "charcoal", "ink drawing", "oil painting", "brushwork"),
            ("painterly", "illustration", "illustrated", "watercolor", "charcoal", "ink", "oil painting", "painting", "drawing"),
        ),
        "atmospheric or cinematic staging": (
            ("atmospheric", "cinematic", "dramatic lighting", "moody", "dreamy", "ethereal"),
            ("atmospheric", "cinematic", "dramatic lighting", "moody", "dreamy", "ethereal", "mood"),
        ),
        "symbolic or surreal interpretation": (
            ("symbolic", "metaphor", "allegory", "surreal"),
            ("symbol", "symbolic", "metaphor", "allegory", "surreal"),
        ),
        "graphic, comic, or poster treatment": (
            ("comic", "graphic novel", "cel-shaded", "poster", "typography"),
            ("comic", "graphic novel", "cel-shaded", "poster", "typography", "text"),
        ),
    }
    initiative_records: list[dict[str, Any]] = []
    volunteered_families: Counter[str] = Counter()
    for record in records:
        observed = _observation_text(record)
        prompt = prompts.get(str(record.get("test_id") or ""), "").lower()
        volunteered = []
        for label, (observed_terms, prompt_terms) in families.items():
            if any(term in observed for term in observed_terms) and not any(term in prompt for term in prompt_terms):
                volunteered.append(label)
        if volunteered:
            initiative_records.append(record)
            volunteered_families.update(volunteered)
    share = len(initiative_records) / len(records)
    label = "High" if share >= 0.3 else "Moderate" if share >= 0.12 else "Low"
    tensions = sum(1 for record in initiative_records if _pass_fail_state(record) != "pass")
    note = (
        f"Prompt-relative aesthetic additions appeared in {len(initiative_records)} of {len(records)} analyzed records."
    )
    if volunteered_families:
        families_text = ", ".join(label for label, _count in volunteered_families.most_common(3))
        note += f" Most frequent additions: {families_text}."
    if tensions:
        note += f" {tensions} of those records were fail/conditional outcomes, so initiative may sometimes compete with the test contract."
    return label, note


def _prompt_by_test_id(suites: list[dict[str, Any]]) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for suite in suites:
        for test in suite.get("manifest", {}).get("tests", []) or []:
            if isinstance(test, dict) and test.get("id"):
                prompts[str(test["id"])] = str(test.get("prompt") or "")
    return prompts


def _qualitative_axis(score: Any) -> str:
    value = _float(score)
    if value is None:
        return "Undetermined"
    if value >= 8.5:
        return "High"
    if value >= 7.0:
        return "Moderate"
    return "Low"


def _balance_axis(positive: int, countervailing: int) -> str:
    total = positive + countervailing
    if not total:
        return "Undetermined"
    share = positive / total
    if share >= 0.67:
        return "High"
    if share >= 0.34:
        return "Moderate"
    return "Low"


def _conceptual_resolutions(conceptual: list[dict[str, Any]]) -> list[str]:
    families = {
        "Human interactions": ("couple", "family", "reunion", "embrace", "people", "human interaction"),
        "Commercial portraiture": ("portrait", "headshot", "studio", "fashion", "editorial", "commercial"),
        "Domestic environments": ("home", "kitchen", "bedroom", "living room", "domestic", "household"),
        "Painterly symbolism": ("painterly", "symbol", "metaphor", "ritual", "allegory"),
        "Atmospheric landscapes": ("landscape", "atmospheric", "mist", "horizon", "wilderness"),
        "Poster or typographic graphics": ("poster", "typography", "literal text", "slogan"),
    }
    ranked = _rank_observation_terms(conceptual, families)
    return [str(item["label"]) for item in ranked[:3]] or ["No stable conceptual resolution family derived yet"]


def _personality_failure_style(records: list[dict[str, Any]]) -> str:
    failed = [record for record in records if _pass_fail_state(record) == "fail"]
    if not failed:
        return "No stable failure style observed under tested conditions."
    families = {
        "Literal stock imagery replaces abstraction": ("stock photo", "commercial", "literal", "generic photo"),
        "Mood or style overwhelms prompt specificity": ("mood", "atmospheric", "prompt specificity", "style dominates"),
        "Anatomy or interaction geometry collapses": ("anatomy", "limb", "hand", "feet", "interaction", "merged"),
        "Clothing-state constraints leak": ("unprompted nudity", "clothing", "wardrobe", "exposure"),
        "External identity or LoRA signal is diluted": ("identity", "lora", "trigger", "likeness"),
        "Output retreats to a generic familiar solution": ("generic", "default", "stereotyp", "conventional"),
    }
    ranked = _rank_observation_terms(failed, families)
    return str(ranked[0]["label"]) if ranked else _failure_personality(failed)


def _rank_observation_terms(records: list[dict[str, Any]], terms: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    counts = []
    texts = [_observation_text(record) for record in records]
    for label, needles in terms.items():
        count = sum(1 for text in texts if any(needle in text for needle in needles))
        if count:
            counts.append({"label": label, "count": count})
    counts.sort(key=lambda item: (-int(item["count"]), str(item["label"])))
    return counts[:5]


def _observation_text(record: dict[str, Any]) -> str:
    """Flatten evaluator findings while excluding rubric/prompt wording."""
    values: list[Any] = [
        record.get("visual_summary"),
        record.get("prompt_adherence"),
        record.get("style_notes"),
        record.get("failures"),
        record.get("unexpected_priors"),
        record.get("warnings"),
        record.get("observation"),
    ]
    intent = record.get("intent_failure_check")
    if isinstance(intent, dict):
        values.extend((intent.get("explanation"), intent.get("failure_modes")))
    for item in record.get("criteria_scores", []) or []:
        if isinstance(item, dict):
            values.append(item.get("evidence"))
    for key in ("semantic_observations", "wildcard_observations"):
        for item in record.get(key, []) or []:
            if isinstance(item, dict):
                values.extend((item.get("category"), item.get("observation"), item.get("evidence")))
    return _flatten(values).lower()


def _phenotype_attractors(
    profile: dict[str, dict[str, Any]],
    records: list[dict[str, Any]],
    symbolic: list[dict[str, Any]],
    poster: list[dict[str, Any]],
    conceptual_score: float | None,
) -> list[str]:
    attractors = []
    if (_float(profile.get("Photographic realism", {}).get("score")) or 0) >= 8:
        attractors.append("credible realism attractor")
    if (_float(profile.get("Age persistence", {}).get("score")) or 0) >= 8:
        attractors.append("age persistence")
    if (_float(profile.get("Body diversity", {}).get("score")) or 0) >= 8:
        attractors.append("body diversity stability")
    if symbolic and (len(symbolic) > len(poster) or (conceptual_score or 0) >= 7.5):
        attractors.append("symbolic realism")
    if any(_has_observed_nudity(record) for record in records):
        attractors.append("glamour/nudity default under weak constraints")
    return attractors or ["no dominant attractor derived yet"]


def _phenotype_resistances(profile: dict[str, dict[str, Any]], records: list[dict[str, Any]]) -> list[str]:
    resistances = []
    if (_float(profile.get("LoRA robustness", {}).get("score")) or 10) < 8:
        resistances.append("resistant latent identity under some LoRA/style stacks")
    if (_float(profile.get("Conceptual prior", {}).get("score")) or 10) < 8:
        resistances.append("uneven abstract concept resolution")
    if any("species" in _flatten(record).lower() and _pass_fail_state(record) != "pass" for record in records):
        resistances.append("species identity can collapse toward human or generic creature priors")
    return resistances or ["no strong resistance pattern derived yet"]


def _distinctive_traits(
    profile: dict[str, dict[str, Any]],
    symbolic: list[dict[str, Any]],
    poster: list[dict[str, Any]],
) -> list[str]:
    traits = []
    if symbolic and len(symbolic) > len(poster):
        traits.append("abstract prompts often become believable symbolic scenes rather than poster/text artifacts")
    if (_float(profile.get("Age persistence", {}).get("score")) or 0) >= 8:
        traits.append("adult life-stage cues persist across older male and female prompts")
    if (_float(profile.get("Body diversity", {}).get("score")) or 0) >= 8:
        traits.append("body-type prompts show less collapse toward a single ideal than many glamour-biased checkpoints")
    return traits or ["distinctiveness requires comparison against additional dossiers"]


def _characteristic_tensions(suites: list[dict[str, Any]]) -> list[dict[str, str]]:
    overview = [_suite_overview_item(suite, Path(".")) for suite in suites]
    tensions: list[dict[str, str]] = []
    high = [item for item in overview if _float(item.get("average_score")) is not None and float(item["average_score"]) >= 8.5]
    low = [item for item in overview if _float(item.get("average_score")) is not None and float(item["average_score"]) < 8.0]
    if high and low:
        tensions.append(
            {
                "title": "High native realism vs weaker transfer/abstraction zones",
                "observation": f"{len(high)} suites scored at or above 8.5, while {', '.join(item['suite_name'] for item in low[:2])} scored lower.",
                "interpretation": "The checkpoint appears strongest when prompts align with its native realism priors and less uniform when external identity/style or abstract interpretation is required.",
            }
        )
    records = _all_records(suites)
    nudity = [record for record in records if _has_observed_nudity(record)]
    if nudity:
        tensions.append(
            {
                "title": "Realism strength vs clothing-state leakage",
                "observation": f"Unprompted nudity or nudity-related notes appear in {len(nudity)} analyzed records.",
                "interpretation": "Some prompt families may activate adult/body priors even when the main image quality remains high.",
            }
        )
    return tensions


def _has_observed_nudity(record: dict[str, Any]) -> bool:
    for key in ("wildcard_observations", "semantic_observations"):
        for item in record.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            text = " ".join(
                str(item.get(field) or "")
                for field in ("category", "observation", "evidence")
            ).lower()
            if "unprompted_nudity" in text or "subject is nude" in text or "depicted nude" in text:
                return True
    return False


def _working_characterization(suites: list[dict[str, Any]]) -> str:
    summary = _summary(suites)
    capabilities = {item["label"]: item for item in _capability_profile(suites)}
    lora = capabilities.get("LoRA robustness", {})
    conceptual = capabilities.get("Conceptual prior", {})
    realism = capabilities.get("Photographic realism", {})
    anatomy = capabilities.get("Human anatomy", {})
    return (
        f"Under this dossier's tested conditions, the checkpoint showed {_lower_rating(realism.get('rating'))} photographic realism "
        f"and {_lower_rating(anatomy.get('rating'))} human-anatomy behavior, with an overall Qwen3 primary average of "
        f"{_fmt(summary.get('average_score'))} across {summary.get('image_count')} images. "
        f"LoRA robustness was {_lower_rating(lora.get('rating'))}, and conceptual-prior behavior was "
        f"{_lower_rating(conceptual.get('rating'))}. This characterization is provisional and should be read as a "
        "behavioral summary of the recorded artifacts, not as a permanent claim about the checkpoint outside these suites."
    )


def _characterization_confidence(suites: list[dict[str, Any]]) -> dict[str, Any]:
    suite_count = len(suites)
    image_count = len(_all_records(suites))
    dual = sum(1 for suite in suites if suite.get("judge_auditor"))
    reasons = []
    cautions = []
    if suite_count >= 5:
        reasons.append(f"{suite_count} complementary suites")
    if image_count >= 150:
        reasons.append(f"{image_count} analyzed images")
    if dual >= 3:
        reasons.append(f"{dual} suites with two-evaluator comparison")
    cautions.append("No replicated reruns under alternate seeds")
    cautions.append("Single checkpoint version")
    if not any("anime" in suite["run_root"].name.lower() for suite in suites):
        cautions.append("Anime sidecar not included")
    level = "High" if suite_count >= 6 and image_count >= 200 and dual >= 5 else "Medium" if suite_count >= 3 else "Low"
    if cautions:
        level = "Medium" if level == "High" else level
    return {"overall": level, "reasons": reasons, "cautions": cautions}


def _known_unknowns(suites: list[dict[str, Any]]) -> list[str]:
    names = " ".join(suite["run_root"].name.lower() for suite in suites)
    unknowns = []
    if "anime" not in names:
        unknowns.append("Anime behavior was not evaluated in this dossier.")
    if any(str(record.get("test_id", "")).startswith("HALLUCINATION_") for record in _all_records(suites)):
        unknowns.append(
            "Blank-prompt latent-bias probes are descriptive; generic automated intent-failure checks may penalize the presence or absence of generated content and require human adjudication."
        )
    unknowns.extend(
        [
            "No replicated reruns across alternate seeds or generation settings were included.",
            "No ControlNet, inpainting, upscaling, or reference-control workflow tests were included.",
            "No video, temporal consistency, or long-sequence composition tests were included.",
            "Evaluator conclusions were not manually adjudicated beyond generated review queues.",
        ]
    )
    return unknowns


def _evaluator_agreement(suites: list[dict[str, Any]]) -> dict[str, Any]:
    compared = [suite for suite in suites if suite.get("judge_auditor")]
    totals = Counter()
    for suite in compared:
        summary = suite["judge_auditor"].get("summary", {})
        totals["tests_compared"] += int(summary.get("tests_compared") or 0)
        totals["tier_a"] += int(summary.get("tier_a_review_required") or 0)
        totals["tier_b"] += int(summary.get("tier_b_auditor_note_review") or 0)
        totals["tier_c"] += int(summary.get("tier_c_calibration_review") or 0)
        totals["hard_disagreements"] += int(summary.get("hard_pass_fail_disagreements") or 0)
    reviewed = totals["tier_a"] + totals["tier_b"] + totals["tier_c"]
    agreement = None
    if totals["tests_compared"]:
        agreement = round(100 * (totals["tests_compared"] - totals["tier_a"]) / totals["tests_compared"], 1)
    return {
        "suites_compared": len(compared),
        "tests_compared": totals["tests_compared"],
        "tier_a": totals["tier_a"],
        "tier_b": totals["tier_b"],
        "tier_c": totals["tier_c"],
        "hard_disagreements": totals["hard_disagreements"],
        "non_tier_a_agreement_percent": agreement,
        "review_items": reviewed,
    }


def _representative_gallery(suites: list[dict[str, Any]], output_root: Path) -> list[dict[str, Any]]:
    records = _all_records_with_suite(suites)
    scored = [item for item in records if _float(item["record"].get("overall_score")) is not None]
    if not scored:
        return []
    selected: list[tuple[str, dict[str, Any]]] = []
    selected.append(("Highest scoring evidence", max(scored, key=lambda item: float(item["record"].get("overall_score")))))
    selected.append(("Lowest scoring evidence", min(scored, key=lambda item: float(item["record"].get("overall_score")))))
    lora = [item for item in scored if "lora" in item["suite"]["run_root"].name.lower() or "lora" in _record_text(item["record"])]
    if lora:
        selected.append(("Most diagnostic LoRA result", min(lora, key=lambda item: float(item["record"].get("overall_score")))))
    conceptual = [item for item in scored if str(item["record"].get("test_id", "")).startswith(("HALLUCINATION_", "CONCEPT_"))]
    if conceptual:
        selected.append(("Most revealing conceptual result", min(conceptual, key=lambda item: float(item["record"].get("overall_score")))))
    failures = [item for item in scored if _pass_fail_state(item["record"]) == "fail"]
    if failures:
        selected.append(("Representative failure", min(failures, key=lambda item: float(item["record"].get("overall_score")))))

    seen: set[str] = set()
    gallery = []
    for role, item in selected:
        record = item["record"]
        key = str(record.get("image_path"))
        if key in seen:
            continue
        seen.add(key)
        gallery.append(_gallery_item(role, item, output_root))
    return gallery


def _gallery_item(role: str, item: dict[str, Any], output_root: Path) -> dict[str, Any]:
    record = item["record"]
    run_root = item["suite"]["run_root"]
    image_path = Path(str(record.get("image_path") or ""))
    return {
        "role": role,
        "suite": _suite_label(run_root.name),
        "test_id": record.get("test_id"),
        "test_name": record.get("test_name"),
        "score": record.get("overall_score"),
        "pass_fail": record.get("pass_fail"),
        "summary": record.get("visual_summary") or record.get("prompt_adherence") or "",
        "image_href": _relative(output_root, image_path),
        "suite_report_href": _relative(output_root, run_root / "report.html"),
    }


def _observation_blocks(suites: list[dict[str, Any]], output_root: Path) -> list[dict[str, Any]]:
    blocks = []
    overview = [_suite_overview_item(suite, output_root) for suite in suites]
    best = sorted(overview, key=lambda item: _float(item.get("average_score")) or 0, reverse=True)[:2]
    weakest = sorted(overview, key=lambda item: _float(item.get("average_score")) or 99)[:2]
    if best:
        blocks.append(
            {
                "title": "Strong native image quality",
                "observation": "The strongest suite averages are high and concentrated in realism/anatomy-oriented suites.",
                "evidence": [f"{item['suite_name']}: average {_fmt(item['average_score'])}, {item['images']} images" for item in best],
                "interpretation": "The checkpoint appears most reliable when prompts align with grounded photographic and anatomical rendering.",
                "confidence": _confidence_label(len(best), True),
            }
        )
    if weakest:
        blocks.append(
            {
                "title": "Localized weaker zones",
                "observation": "The lowest suite averages identify where additional review is most useful.",
                "evidence": [f"{item['suite_name']}: average {_fmt(item['average_score'])}, fail count {item['fail']}" for item in weakest],
                "interpretation": "Weaknesses appear more localized by prompt family than systemic across all tested behavior.",
                "confidence": _confidence_label(len(weakest), True),
            }
        )
    agreement = _evaluator_agreement(suites)
    if agreement["tests_compared"]:
        blocks.append(
            {
                "title": "Evaluator disagreement as review signal",
                "observation": f"Qwen3 and MiniCPM produced {agreement['tier_a']} Tier A review items across {agreement['tests_compared']} compared tests.",
                "evidence": [f"Hard pass/fail disagreements: {agreement['hard_disagreements']}", f"Tier B/C review items: {agreement['tier_b'] + agreement['tier_c']}"],
                "interpretation": "The dossier should preserve evaluator disagreement as evidence of ambiguous or evaluator-sensitive cases, not collapse it into noise.",
                "confidence": _confidence_label(agreement["tests_compared"], True),
            }
        )
    return blocks


def _appendix(suites: list[dict[str, Any]], output_root: Path) -> list[dict[str, Any]]:
    return [_suite_overview_item(suite, output_root) for suite in suites]


def _exploratory_artifacts(checkpoint_id: str, output_root: Path) -> list[dict[str, Any]]:
    roots = [
        Path("cef_runs") / "cef_semantic_basins" / checkpoint_id,
        Path("cef_semantic_basins") / checkpoint_id,
    ]
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*/semantic_basin_probe.json")):
            data = _read_json(path)
            key = f"{data.get('anchor_concept')}::{data.get('date')}"
            if key in seen:
                continue
            seen.add(key)
            artifact_root = path.parent
            artifacts.append(
                {
                    "artifact_type": data.get("artifact_type") or "semantic_basin_probe",
                    "title": f"Semantic Basin Probe: {str(data.get('anchor_concept') or '').title()}",
                    "anchor_concept": data.get("anchor_concept"),
                    "date": data.get("date"),
                    "confidence": data.get("confidence"),
                    "working_interpretation": data.get("working_interpretation"),
                    "observed_clusters": data.get("observed_clusters", [])[:8],
                    "comparison_hooks": data.get("comparison_hooks", {}),
                    "markdown_href": _optional_relative(output_root, artifact_root / "semantic_basin_probe.md"),
                    "json_href": _optional_relative(output_root, artifact_root / "semantic_basin_probe.json"),
                    "contact_sheet_href": _optional_relative(output_root, artifact_root / "contact_sheet.jpg"),
                }
            )
    return artifacts


def _html(dossier: dict[str, Any], output_root: Path) -> str:
    nav = [
        ("scope", "Scope"),
        ("summary", "Executive Summary"),
        ("phenotype", "Behavioral Profile"),
        ("ssp", "Sparse Semantics"),
        ("layer0", "Layer 0"),
        ("layer1", "Layer 1"),
        ("layer2", "Layer 2"),
        ("layer25", "Layer 2.5"),
        ("layer3", "Layer 3"),
        ("agreement", "Evaluator Agreement"),
        ("gallery", "Gallery"),
        ("exploratory", "Exploratory Artifacts"),
        ("unknowns", "Known Unknowns"),
        ("appendix", "Appendix"),
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(str(dossier["title"]))}</title>
  <style>
    :root {{
      --bg: #f6f7f4;
      --panel: #ffffff;
      --ink: #202522;
      --muted: #66706b;
      --line: #d8ddd6;
      --accent: #2f6f67;
      --warn: #9a6400;
      --fail: #a43737;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Segoe UI, system-ui, sans-serif; background: var(--bg); color: var(--ink); }}
    header {{ padding: 24px clamp(18px, 4vw, 48px); background: #edf2ee; border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }}
    nav {{ position: sticky; top: 0; z-index: 2; display: flex; gap: 8px; flex-wrap: wrap; padding: 10px clamp(18px, 4vw, 48px); background: rgba(246,247,244,.96); border-bottom: 1px solid var(--line); }}
    nav a {{ color: var(--accent); text-decoration: none; font-size: 13px; padding: 5px 8px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }}
    main {{ padding: 22px clamp(18px, 4vw, 48px) 44px; display: grid; gap: 18px; }}
    section, details {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    summary {{ cursor: pointer; font-weight: 700; font-size: 18px; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfb; }}
    .metric span {{ display:block; color: var(--muted); font-size: 12px; text-transform: uppercase; margin-bottom: 5px; }}
    .metric strong {{ font-size: 22px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); padding: 9px 7px; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .bar {{ height: 9px; border-radius: 999px; background: #e4e8e2; overflow: hidden; }}
    .bar i {{ display:block; height:100%; background: var(--accent); }}
    .cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfb; }}
    .thumb {{ width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 6px; border: 1px solid var(--line); background: #e4e8e2; }}
    .oei {{ display:grid; gap: 10px; }}
    .oei div {{ border-left: 3px solid var(--accent); background:#fbfcfb; padding: 9px 11px; }}
    .warn {{ color: var(--warn); }}
    .fail {{ color: var(--fail); }}
    a {{ color: var(--accent); }}
    ul {{ margin: 8px 0 0 20px; padding: 0; }}
    li {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(str(dossier["title"]))}</h1>
    <div class="meta">Checkpoint: {escape(str(dossier["checkpoint_id"]))} | Dossier schema {escape(str(dossier["schema_version"]))} | Built {escape(str(dossier["built_at"]))}</div>
  </header>
  <nav>{''.join(f'<a href="#{anchor}">{escape(label)}</a>' for anchor, label in nav)}</nav>
  <main>
    {_scope_html(dossier)}
    {_summary_html(dossier)}
    {_phenotype_html(dossier)}
    {_ssp_html(dossier)}
    {_conditions_html(dossier)}
    {_suite_overview_html(dossier)}
    {_layer2_html(dossier)}
    {_tensions_html(dossier)}
    {_working_html(dossier)}
    {_agreement_html(dossier)}
    {_gallery_html(dossier)}
    {_exploratory_html(dossier)}
    {_unknowns_html(dossier)}
    {_appendix_html(dossier)}
  </main>
</body>
</html>"""


def _chatgpt_meta_handoff(dossier: dict[str, Any], suites: list[dict[str, Any]], output_root: Path) -> dict[str, Any]:
    metadata = _handoff_metadata(dossier, suites)
    strengths = _handoff_strengths(dossier, suites)
    weaknesses = _handoff_weaknesses(dossier, suites)
    examples = _handoff_examples(dossier)
    comparison_hooks = _comparison_hooks(dossier, strengths, weaknesses)
    bottom_line = _bottom_line(dossier, strengths, weaknesses)
    return {
        "metadata": metadata,
        "behavioral_phenotype_card": dossier["behavioral_phenotype_card"],
        "sparse_semantic_profiles": dossier.get("sparse_semantic_profiles", []),
        "executive_characterization": {
            "summary": dossier["working_characterization"],
            "strongest_observed_capabilities": [item["label"] for item in sorted(dossier["capability_profile"], key=lambda value: _float(value.get("score")) or 0, reverse=True)[:4]],
            "weakest_observed_areas": [item["label"] for item in sorted(dossier["capability_profile"], key=lambda value: _float(value.get("score")) or 99)[:3]],
            "most_diagnostic_failure_mode": dossier["behavioral_signals"]["failure_personality"],
            "recommended_use_cases": _recommended_roles(dossier),
            "cautions": dossier["known_unknowns"][:3],
        },
        "suite_summaries": [_handoff_suite_summary(suite, output_root) for suite in suites],
        "cross_suite_strengths": strengths,
        "cross_suite_weaknesses": weaknesses,
        "characteristic_tensions": dossier["characteristic_tensions"],
        "evaluator_agreement": dossier["evaluator_agreement"],
        "representative_examples": examples,
        "exploratory_artifacts": dossier.get("exploratory_artifacts", []),
        "methodology_notes": _methodology_notes(dossier, suites),
        "comparison_hooks": comparison_hooks,
        "open_questions": _open_questions(dossier),
        "bottom_line": bottom_line,
    }


def _handoff_metadata(dossier: dict[str, Any], suites: list[dict[str, Any]]) -> dict[str, Any]:
    conditions = dossier["conditions"]
    return {
        "checkpoint_id": dossier["checkpoint_id"],
        "checkpoint_title": conditions["checkpoint_titles"][0] if conditions["checkpoint_titles"] else "",
        "checkpoint_hash": conditions["checkpoint_hashes"][0] if conditions["checkpoint_hashes"] else "",
        "dossier_schema_version": dossier["schema_version"],
        "cef_code_version": "",
        "date_generated": dossier["built_at"],
        "suites_included": [item["suite_name"] for item in dossier["suite_overview"]],
        "total_images_generated": dossier["summary"]["image_count"],
        "total_images_analyzed": dossier["summary"]["image_count"],
        "evaluator_roster": dossier["summary"]["evaluator_roster"],
        "primary_evaluator": "Qwen3-VL-8B Primary",
        "auditor_evaluator": "MiniCPM-V-4.5 Auditor where available",
        "generation_settings_summary": [_settings_text(item.get("defaults", {})) for item in conditions["manifests"]],
        "loras_used_or_tested": _loras_used(suites),
        "known_missing_suites": [item for item in dossier["known_unknowns"] if "not evaluated" in item.lower()],
    }


def _handoff_suite_summary(suite: dict[str, Any], output_root: Path) -> dict[str, Any]:
    item = _suite_overview_item(suite, output_root)
    auditor_records = suite.get("auditor_report", {}).get("records", [])
    records = suite.get("report", {}).get("records", [])
    return {
        "suite_name": item["suite_name"],
        "run_root": str(suite["run_root"]),
        "images": item["images"],
        "primary_average_score": item["average_score"],
        "auditor_average_score": _average([_normalized_score(record.get("overall_score")) for record in auditor_records]) if auditor_records else None,
        "pass_conditional_fail": {
            "pass": item["pass"],
            "conditional_pass": item["conditional_pass"],
            "fail": item["fail"],
        },
        "top_strengths": _top_tags(records, positive=True),
        "top_weaknesses": _top_tags(records, positive=False),
        "suite_report": item["report_href"],
        "contact_sheet": item["contact_sheet_href"],
        "evaluator_comparison": item["comparison_href"],
    }


def _handoff_strengths(dossier: dict[str, Any], suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strengths = []
    for item in sorted(dossier["capability_profile"], key=lambda value: _float(value.get("score")) or 0, reverse=True):
        score = _float(item.get("score"))
        if score is None or score < 8.0:
            continue
        records = _records_matching_capability(suites, str(item["label"]))
        strengths.append(
            {
                "observation": f"{item['label']} was a {str(item['rating']).lower()} observed capability.",
                "evidence": f"Aggregate score {_fmt(score)} across {item['evidence_count']} matched records.",
                "suites": sorted({suite["run_root"].name for suite, _record in records})[:5],
                "evaluator_agreement": _agreement_phrase(dossier),
                "representative_tests": [str(record.get("test_id")) for _suite, record in records[:6]],
                "confidence": _confidence_label(int(item.get("evidence_count") or 0), bool(dossier["evaluator_agreement"]["tests_compared"])),
            }
        )
    return strengths[:6]


def _handoff_weaknesses(dossier: dict[str, Any], suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weaknesses = []
    for item in sorted(dossier["capability_profile"], key=lambda value: _float(value.get("score")) or 99):
        score = _float(item.get("score"))
        if score is None or score >= 8.0:
            continue
        records = _records_matching_capability(suites, str(item["label"]))
        low = [record for _suite, record in records if (_float(record.get("overall_score")) or 10) < 7 or _pass_fail_state(record) != "pass"]
        weaknesses.append(
            {
                "observation": f"{item['label']} was more review-sensitive than the strongest native capabilities.",
                "evidence": f"Aggregate score {_fmt(score)} across {item['evidence_count']} matched records; {len(low)} matched records were fail/conditional or below 7.",
                "suites": sorted({suite["run_root"].name for suite, _record in records})[:5],
                "evaluator_agreement": _agreement_phrase(dossier),
                "representative_tests": [str(record.get("test_id")) for record in low[:6]],
                "confidence": _confidence_label(int(item.get("evidence_count") or 0), bool(dossier["evaluator_agreement"]["tests_compared"])),
                "likely_interpretation": "This is a localized behavioral signal under these suites, not a global capability claim.",
            }
        )
    for tension in dossier["characteristic_tensions"]:
        if "nudity" in tension["observation"].lower() or "leakage" in tension["title"].lower():
            weaknesses.append(
                {
                    "observation": tension["title"],
                    "evidence": tension["observation"],
                    "suites": [item["suite_name"] for item in dossier["suite_overview"]],
                    "evaluator_agreement": _agreement_phrase(dossier),
                    "representative_tests": _nudity_tests(suites),
                    "confidence": "Medium within tested conditions",
                    "likely_interpretation": tension["interpretation"],
                }
            )
    return weaknesses[:7]


def _handoff_examples(dossier: dict[str, Any]) -> list[dict[str, Any]]:
    examples = []
    for item in dossier["representative_gallery"]:
        examples.append(
            {
                "test_id": item.get("test_id"),
                "suite": item.get("suite"),
                "image_path": item.get("image_href"),
                "score": item.get("score"),
                "why_selected": item.get("role"),
                "relevant_evaluator_notes": item.get("summary"),
            }
        )
    return examples[:12]


def _methodology_notes(dossier: dict[str, Any], suites: list[dict[str, Any]]) -> list[str]:
    notes = [
        "The dossier is a Layer 2 characterization artifact; suite reports remain the evidence appendices.",
        "Qwen3-14B was not included as a candidate image judge because the local LM Studio model did not support images.",
    ]
    if not any("prelim" in suite["run_root"].name and suite.get("judge_auditor") for suite in suites):
        notes.append("The preliminary suite has Qwen3 primary results but no MiniCPM auditor comparison in this dossier.")
    if dossier["characterization_confidence"]["overall"] != "High":
        notes.append("Characterization confidence is not high because replication and/or missing-suite caveats remain.")
    notes.extend(dossier["known_unknowns"][:3])
    return notes


def _comparison_hooks(dossier: dict[str, Any], strengths: list[dict[str, Any]], weaknesses: list[dict[str, Any]]) -> dict[str, Any]:
    signals = dossier["behavioral_signals"]
    return {
        "default_subjects": signals["default_subject"],
        "default_visual_language": signals["default_visual_language"],
        "default_mood": signals["default_mood"],
        "latent_attractors": signals["latent_attractors"],
        "failure_attractors": [item["observation"] for item in weaknesses[:5]],
        "strength_profile": [item["observation"] for item in strengths[:5]],
        "weakness_profile": [item["observation"] for item in weaknesses[:5]],
        "recommended_role": _recommended_roles(dossier),
        "not_recommended_for": _not_recommended_for(dossier),
    }


def _open_questions(dossier: dict[str, Any]) -> list[str]:
    return [
        "Are the observed LoRA weaknesses localized to specific LoRAs or indicative of broader checkpoint resistance?",
        "Do the conceptual-prior outputs show a meaningful checkpoint personality or mostly generic realism?",
        "Which Tier A judge/auditor disagreements require human adjudication before publishing conclusions?",
        "Should mirror/reflection or clothing-state prompts be expanded based on the observed leakage signals?",
        "Which prior checkpoint is the best behavioral comparator for this dossier: NightVision, Artaix, Juggernaut, or Araminta?",
        "Are any suite prompts too ambiguous, causing evaluator disagreement rather than checkpoint failure?",
        "Should the full-strength NectarGrove isolated test become a standard LoRA sidecar control?",
    ]


def _bottom_line(dossier: dict[str, Any], strengths: list[dict[str, Any]], weaknesses: list[dict[str, Any]]) -> str:
    role = ", ".join(_recommended_roles(dossier)[:3]) or "the strongest observed use cases"
    weak = ", ".join(_not_recommended_for(dossier)[:2]) or "the weaker observed areas"
    return (
        f"Bottom line: Under the tested conditions, {dossier['checkpoint_id']} appears most useful for {role}, "
        f"weaker for {weak}, and most worth comparing against prior realism-oriented checkpoints with known LoRA "
        "and conceptual-prior behavior. The most important follow-up is human review of Tier A disagreement and "
        "the LoRA/conceptual weak zones."
    )


def _handoff_markdown(handoff: dict[str, Any]) -> str:
    metadata = handoff["metadata"]
    lines = [
        "# CEF ChatGPT Meta-Handoff",
        "",
        "## 1. Metadata",
        "",
        f"- checkpoint id: {metadata['checkpoint_id']}",
        f"- checkpoint title: {metadata['checkpoint_title']}",
        f"- checkpoint hash: {metadata['checkpoint_hash']}",
        f"- dossier schema version: {metadata['dossier_schema_version']}",
        f"- date generated: {metadata['date_generated']}",
        f"- total images analyzed: {metadata['total_images_analyzed']}",
        f"- evaluator roster: {', '.join(metadata['evaluator_roster'])}",
        f"- primary evaluator: {metadata['primary_evaluator']}",
        f"- auditor evaluator: {metadata['auditor_evaluator']}",
        f"- LoRAs used/tested: {', '.join(metadata['loras_used_or_tested']) or 'none detected'}",
        f"- known missing suites: {', '.join(metadata['known_missing_suites']) or 'none recorded'}",
        "",
        "## Checkpoint Behavioral Profile",
        "",
        "Formal CEF schema term: Behavioral Phenotype Card.",
        "",
        _phenotype_markdown(handoff["behavioral_phenotype_card"]),
        "",
        "## Sparse Semantic Profile",
        "",
        _ssp_handoff_markdown(handoff.get("sparse_semantic_profiles", [])),
        "",
        "## 2. Executive Characterization",
        "",
        handoff["executive_characterization"]["summary"],
        "",
        f"- strongest observed capabilities: {', '.join(handoff['executive_characterization']['strongest_observed_capabilities'])}",
        f"- weakest observed areas: {', '.join(handoff['executive_characterization']['weakest_observed_areas'])}",
        f"- most diagnostic failure mode: {handoff['executive_characterization']['most_diagnostic_failure_mode']}",
        f"- recommended use cases: {', '.join(handoff['executive_characterization']['recommended_use_cases'])}",
        "",
        "## 3. Suite Summary Table",
        "",
        "| Suite | Images | Primary Avg | Auditor Avg | Pass / Conditional / Fail | Links |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for suite in handoff["suite_summaries"]:
        counts = suite["pass_conditional_fail"]
        links = " / ".join(
            value
            for value in (suite.get("suite_report"), suite.get("contact_sheet"), suite.get("evaluator_comparison"))
            if value
        )
        lines.append(
            f"| {suite['suite_name']} | {suite['images']} | {_fmt(suite['primary_average_score'])} | {_fmt(suite['auditor_average_score'])} | "
            f"{counts['pass']} / {counts['conditional_pass']} / {counts['fail']} | {links} |"
        )
    lines.extend(["", "## 4. Cross-Suite Strengths", ""])
    lines.extend(_oei_markdown(item, include_interpretation=False) for item in handoff["cross_suite_strengths"])
    lines.extend(["", "## 5. Cross-Suite Weaknesses / Failure Attractors", ""])
    lines.extend(_oei_markdown(item, include_interpretation=True) for item in handoff["cross_suite_weaknesses"])
    lines.extend(["", "## 6. Characteristic Tensions", ""])
    for item in handoff["characteristic_tensions"]:
        lines.extend([f"### {item['title']}", "", f"- Signals: {item['observation']}", f"- Why it matters: {item['interpretation']}", "- Confidence: Medium within tested conditions", ""])
    agreement = handoff["evaluator_agreement"]
    lines.extend(
        [
            "## 7. Evaluator Agreement Summary",
            "",
            f"- suites with dual evaluation: {agreement['suites_compared']}",
            f"- tests compared: {agreement['tests_compared']}",
            f"- Tier A review items: {agreement['tier_a']}",
            f"- Tier B review items: {agreement['tier_b']}",
            f"- Tier C review items: {agreement['tier_c']}",
            f"- hard disagreements: {agreement['hard_disagreements']}",
            "",
            "## 8. Representative Examples For Human Review",
            "",
        ]
    )
    for item in handoff["representative_examples"]:
        lines.extend(
            [
                f"### {item['why_selected']}",
                f"- Test ID: {item['test_id']}",
                f"- Suite: {item['suite']}",
                f"- Image path: {item['image_path']}",
                f"- Score: {item['score']}",
                f"- Relevant notes: {item['relevant_evaluator_notes']}",
                "",
            ]
        )
    lines.extend(["## 9. Exploratory Artifacts", ""])
    if handoff.get("exploratory_artifacts"):
        for item in handoff["exploratory_artifacts"]:
            lines.extend(
                [
                    f"### {item.get('title')}",
                    f"- Anchor concept: {item.get('anchor_concept')}",
                    f"- Date: {item.get('date')}",
                    f"- Confidence: {item.get('confidence')}",
                    f"- Working interpretation: {item.get('working_interpretation')}",
                    f"- Markdown: {item.get('markdown_href')}",
                    f"- Contact sheet: {item.get('contact_sheet_href')}",
                    "",
                ]
            )
    else:
        lines.extend(["No exploratory artifacts archived for this checkpoint.", ""])
    lines.extend(["## 10. Methodology Notes", ""])
    lines.extend(f"- {item}" for item in handoff["methodology_notes"])
    hooks = handoff["comparison_hooks"]
    lines.extend(["", "## 11. Comparison Hooks", "", "```json", json.dumps(hooks, indent=2), "```", "", "## 12. Open Questions For ChatGPT", ""])
    lines.extend(f"- {item}" for item in handoff["open_questions"])
    lines.extend(["", "## 13. Bottom Line", "", handoff["bottom_line"], ""])
    return "\n".join(lines)


def _oei_markdown(item: dict[str, Any], include_interpretation: bool) -> str:
    lines = [
        f"### {item['observation']}",
        "",
        f"- Observation: {item['observation']}",
        f"- Evidence: {item['evidence']}",
        f"- Suites: {', '.join(item['suites'])}",
        f"- Evaluator agreement: {item['evaluator_agreement']}",
        f"- Representative tests: {', '.join(item['representative_tests'])}",
        f"- Confidence: {item['confidence']}",
    ]
    if include_interpretation:
        lines.append(f"- Likely interpretation: {item['likely_interpretation']}")
    lines.append("")
    return "\n".join(lines)


def _phenotype_markdown(card: dict[str, Any]) -> str:
    personality = card.get("personality_summary", {})
    conceptual = personality.get("conceptual_resolutions", []) or ["Not enough signal."]
    lines = [
        f"- Realism bias: {personality.get('realism_bias', 'Undetermined')}",
        f"- Literalness: {personality.get('literalness', 'Undetermined')}",
        f"- Prompt obedience: {personality.get('prompt_obedience', 'Undetermined')}",
        f"- Interpretive tendency: {personality.get('interpretive_tendency', 'Undetermined')}",
        f"- Mode of interpretation: {personality.get('mode_of_interpretation', 'Undetermined')}",
        f"- Mode of interpretation note: {personality.get('mode_of_interpretation_note', 'Not enough signal.')}",
        f"- Mode of interpretation basis: {personality.get('mode_of_interpretation_basis', 'Undetermined')}",
        f"- Aesthetic initiative: {personality.get('aesthetic_initiative', 'Undetermined')}",
        f"- Aesthetic initiative note: {personality.get('aesthetic_initiative_note', 'Not enough signal.')}",
        f"- Conceptual resolutions: {', '.join(str(value) for value in conceptual)}",
        f"- Failure style: {personality.get('failure_style', 'Undetermined')}",
        "- Note: These are qualitative memory aids, not additional scores.",
    ]
    labels = [
        ("Natural attractors", "natural_attractors"),
        ("Resists / weak zones", "resistances"),
        ("Best prompt families", "best_prompt_families"),
        ("Weakness triggers", "weakness_triggers"),
        ("Distinctive traits", "distinctive_traits"),
        ("Recommended role", "recommended_role"),
        ("Not recommended without review", "not_recommended_without_review"),
    ]
    for label, key in labels:
        values = card.get(key, []) or ["Not enough signal."]
        lines.append(f"- {label}: {', '.join(str(value) for value in values)}")
    return "\n".join(lines)


def _ssp_handoff_markdown(profiles: list[dict[str, Any]]) -> str:
    if not profiles:
        return "No score-free SSP observer index was attached to this dossier."
    blocks = []
    for profile in profiles:
        observer = profile.get("observer", {})
        phenotype = profile.get("semantic_phenotype", {})
        blocks.extend([
            f"### {observer.get('label', 'SSP observer')}",
            f"- Images / failures: {profile.get('observed_images', 0)} / {profile.get('failures', 0)}",
            f"- Methodological justification: {profile.get('methodological_justification', '')}",
            f"- Semantic phenotype: `{json.dumps(phenotype, sort_keys=True)}`",
            f"- SSP report: {profile.get('report_href') or 'not available'}",
            f"- CPF-ready records: {profile.get('behavioral_records_href') or 'not available'}",
            "- Interpretation limit: descriptive sampled behavior only; no correctness score or mechanism claim.",
            "",
        ])
    return "\n".join(blocks).rstrip()


def _scope_html(dossier: dict[str, Any]) -> str:
    scope = dossier["scope_and_limits"]
    return f"""<section id="scope">
      <h2>Scope &amp; Limits</h2>
      <p>{escape(scope["text"])}</p>
    </section>"""


def _summary_html(dossier: dict[str, Any]) -> str:
    summary = dossier["summary"]
    confidence = dossier["characterization_confidence"]
    return f"""<section id="summary">
      <h2>Executive Summary</h2>
      <div class="grid">
        <div class="metric"><span>Suites</span><strong>{summary["suite_count"]}</strong></div>
        <div class="metric"><span>Images</span><strong>{summary["image_count"]}</strong></div>
        <div class="metric"><span>Average Score</span><strong>{_fmt(summary["average_score"])}</strong></div>
        <div class="metric"><span>Pass / Conditional / Fail</span><strong>{summary["pass_count"]} / {summary["conditional_pass_count"]} / {summary["fail_count"]}</strong></div>
        <div class="metric"><span>Characterization Confidence</span><strong>{escape(str(confidence["overall"]))}</strong></div>
      </div>
      <p>{escape(str(summary["overall_characterization"]))}</p>
      <h3>Confidence of Characterization</h3>
      <ul>{''.join(f'<li>{escape(reason)}</li>' for reason in confidence["reasons"])}</ul>
      <ul>{''.join(f'<li class="warn">{escape(caution)}</li>' for caution in confidence["cautions"])}</ul>
    </section>"""


def _phenotype_html(dossier: dict[str, Any]) -> str:
    card = dossier["behavioral_phenotype_card"]
    personality = card.get("personality_summary", {})
    conceptual = ", ".join(str(value) for value in personality.get("conceptual_resolutions", [])) or "Undetermined"
    personality_rows = [
        ("Realism Bias", personality.get("realism_bias", "Undetermined")),
        ("Literalness", personality.get("literalness", "Undetermined")),
        ("Prompt Obedience", personality.get("prompt_obedience", "Undetermined")),
        ("Interpretive Tendency", personality.get("interpretive_tendency", "Undetermined")),
        ("Mode of Interpretation", personality.get("mode_of_interpretation", "Undetermined")),
        ("Mode of Interpretation Note", personality.get("mode_of_interpretation_note", "Not enough signal.")),
        ("Mode of Interpretation Basis", personality.get("mode_of_interpretation_basis", "Undetermined")),
        ("Aesthetic Initiative", personality.get("aesthetic_initiative", "Undetermined")),
        ("Aesthetic Initiative Note", personality.get("aesthetic_initiative_note", "Not enough signal.")),
        ("Conceptual Resolutions", conceptual),
        ("Failure Style", personality.get("failure_style", "Undetermined")),
    ]
    fields = [
        ("Natural Attractors", "natural_attractors"),
        ("Resists / Weak Zones", "resistances"),
        ("Best Prompt Families", "best_prompt_families"),
        ("Weakness Triggers", "weakness_triggers"),
        ("Distinctive Traits", "distinctive_traits"),
        ("Recommended Role", "recommended_role"),
        ("Not Recommended Without Review", "not_recommended_without_review"),
    ]
    cards = []
    for label, key in fields:
        values = card.get(key, [])
        items = "".join(f"<li>{escape(str(item))}</li>" for item in values) if values else "<li>Not enough signal.</li>"
        cards.append(f"""<div class="card"><h3>{escape(label)}</h3><ul>{items}</ul></div>""")
    return f"""<section id="phenotype">
      <h2>{escape(str(card.get("display_title", "Checkpoint Behavioral Profile")))}</h2>
      <p class="meta">Formal CEF schema term: {escape(str(card.get("title", "Behavioral Phenotype Card")))}. A field-guide summary of what this checkpoint naturally gravitates toward, what it resists, and where it should be reviewed before use.</p>
      <div class="card"><h3>Checkpoint Personality Summary</h3><dl>{''.join(f'<dt>{escape(str(label))}</dt><dd>{escape(str(value))}</dd>' for label, value in personality_rows)}</dl><p class="meta">Qualitative memory aids derived from dossier evidence; not additional scores.</p></div>
      <div class="cards">{''.join(cards)}</div>
    </section>"""


def _ssp_html(dossier: dict[str, Any]) -> str:
    profiles = dossier.get("sparse_semantic_profiles", [])
    if not profiles:
        return """<section id="ssp"><h2>Sparse Semantic Profile</h2><p class="meta">No score-free SSP observer index was attached to this dossier.</p></section>"""
    cards = []
    for profile in profiles:
        phenotype = profile.get("semantic_phenotype", {})
        links = []
        for label, key in (("SSP report", "report_href"), ("contact sheet", "contact_sheet_href"), ("CPF-ready records", "behavioral_records_href"), ("observer index", "index_href")):
            if profile.get(key):
                links.append(f'<a href="{escape(str(profile[key]))}">{escape(label)}</a>')
        cards.append(
            f"<div class=\"card\"><h3>{escape(str(profile.get('observer', {}).get('label', 'SSP observer')))}</h3>"
            f"<p>{escape(str(profile.get('methodological_justification', '')))}</p>"
            f"<p class=\"meta\">Images: {profile.get('observed_images', 0)} | Failures: {profile.get('failures', 0)}</p>"
            f"<pre>{escape(json.dumps(phenotype, indent=2))}</pre><p>{' | '.join(links)}</p></div>"
        )
    return f"""<section id="ssp"><h2>Sparse Semantic Profile</h2>
      <p>Score-free prototype and attractor observations under minimal linguistic conditioning. These fields characterize sampled outputs; they are not correctness scores or mechanism claims.</p>
      <div class="cards">{''.join(cards)}</div></section>"""


def _conditions_html(dossier: dict[str, Any]) -> str:
    conditions = dossier["conditions"]
    rows = "\n".join(
        f"<tr><td>{escape(str(item['name']))}</td><td>{escape(str(item['suite_id']))}</td><td>{escape(str(item['tests']))}</td><td>{escape(_settings_text(item.get('defaults', {})))}</td></tr>"
        for item in conditions["manifests"]
    )
    return f"""<details id="layer0" open>
      <summary>Layer 0 - Experimental Conditions &amp; Provenance</summary>
      <p class="meta">Checkpoint titles: {escape(', '.join(conditions['checkpoint_titles']) or 'n/a')}</p>
      <p class="meta">Checkpoint hashes: {escape(', '.join(conditions['checkpoint_hashes']) or 'n/a')}</p>
      <p class="meta">Primary evaluator: {escape(str(conditions['primary_evaluator']))}</p>
      <p class="meta">Auditor: {escape(str(conditions['auditor']))}</p>
      <table><thead><tr><th>Suite</th><th>Suite ID</th><th>Tests</th><th>Generation Settings</th></tr></thead><tbody>{rows}</tbody></table>
    </details>"""


def _suite_overview_html(dossier: dict[str, Any]) -> str:
    rows = "\n".join(
        f"""<tr>
          <td>{escape(str(item['suite_name']))}</td>
          <td>{item['images']}</td>
          <td>{_fmt(item['average_score'])}</td>
          <td>{item['pass']} / {item['conditional_pass']} / {item['fail']}</td>
          <td>{_review_text(item)}</td>
          <td>{_suite_links(item)}</td>
        </tr>"""
        for item in dossier["suite_overview"]
    )
    capability_rows = "\n".join(
        f"""<tr><td>{escape(str(item['label']))}</td><td>{escape(str(item['rating']))}</td><td>{_fmt(item['score'])}</td><td><div class="bar"><i style="width:{_bar_width(item['score'])}%"></i></div></td><td>{item['evidence_count']}</td></tr>"""
        for item in dossier["capability_profile"]
    )
    return f"""<details id="layer1" open>
      <summary>Layer 1 - Observed Results</summary>
      <h3>Suite Overview</h3>
      <table><thead><tr><th>Suite</th><th>Images</th><th>Score</th><th>Pass / Conditional / Fail</th><th>Review Queue</th><th>Links</th></tr></thead><tbody>{rows}</tbody></table>
      <h3>Capability Radar</h3>
      <table><thead><tr><th>Capability</th><th>Rating</th><th>Score</th><th>Bar</th><th>Evidence</th></tr></thead><tbody>{capability_rows}</tbody></table>
    </details>"""


def _layer2_html(dossier: dict[str, Any]) -> str:
    signals = dossier["behavioral_signals"]
    return f"""<details id="layer2" open>
      <summary>Layer 2 - Derived Behavioral Signals</summary>
      <div class="grid">
        {_signal_card('Default Subject', signals['default_subject'])}
        {_signal_card('Default Mood', signals['default_mood'])}
        {_signal_card('Default Visual Language', signals['default_visual_language'])}
        {_signal_card('Latent / Failure Attractors', signals['latent_attractors'])}
      </div>
      <h3>Failure Personality</h3>
      <p>{escape(str(signals['failure_personality']))}</p>
      <h3>LoRA Compatibility Profile</h3>
      <p>{escape(str(signals['lora_compatibility_profile']))}</p>
      <h3>Recovery Tendencies</h3>
      <p>{escape(str(signals['recovery_tendencies']))}</p>
    </details>"""


def _tensions_html(dossier: dict[str, Any]) -> str:
    rows = "".join(
        f"""<div class="card"><h3>{escape(item['title'])}</h3><p><strong>Observation:</strong> {escape(item['observation'])}</p><p><strong>Interpretation:</strong> {escape(item['interpretation'])}</p></div>"""
        for item in dossier["characteristic_tensions"]
    )
    return f"""<details id="layer25" open><summary>Layer 2.5 - Characteristic Tensions</summary><div class="cards">{rows or '<p>No characteristic tensions derived yet.</p>'}</div></details>"""


def _working_html(dossier: dict[str, Any]) -> str:
    blocks = "\n".join(
        f"""<div class="card"><h3>{escape(block['title'])}</h3><div class="oei"><div><strong>Observation</strong><br>{escape(block['observation'])}</div><div><strong>Evidence</strong><ul>{''.join(f'<li>{escape(item)}</li>' for item in block['evidence'])}</ul></div><div><strong>Interpretation</strong><br>{escape(block['interpretation'])}</div><div><strong>Confidence</strong><br>{escape(block['confidence'])}</div></div></div>"""
        for block in dossier["observation_blocks"]
    )
    return f"""<details id="layer3" open>
      <summary>Layer 3 - Working Characterization</summary>
      <p>{escape(str(dossier['working_characterization']))}</p>
      <h3>Observation → Evidence → Interpretation</h3>
      <div class="cards">{blocks}</div>
    </details>"""


def _agreement_html(dossier: dict[str, Any]) -> str:
    item = dossier["evaluator_agreement"]
    return f"""<section id="agreement">
      <h2>Evaluator Agreement</h2>
      <div class="grid">
        <div class="metric"><span>Compared Suites</span><strong>{item['suites_compared']}</strong></div>
        <div class="metric"><span>Compared Tests</span><strong>{item['tests_compared']}</strong></div>
        <div class="metric"><span>Tier A</span><strong>{item['tier_a']}</strong></div>
        <div class="metric"><span>Tier B</span><strong>{item['tier_b']}</strong></div>
        <div class="metric"><span>Tier C</span><strong>{item['tier_c']}</strong></div>
        <div class="metric"><span>Hard Disagreements</span><strong>{item['hard_disagreements']}</strong></div>
      </div>
    </section>"""


def _gallery_html(dossier: dict[str, Any]) -> str:
    cards = "".join(
        f"""<div class="card">
          <a href="{escape(item['image_href'])}"><img class="thumb" src="{escape(item['image_href'])}" alt="{escape(str(item['test_id']))}"></a>
          <h3>{escape(str(item['role']))}</h3>
          <p class="meta">{escape(str(item['suite']))} | {escape(str(item['test_id']))} | score {_fmt(item['score'])} | {escape(str(item['pass_fail']))}</p>
          <p>{escape(str(item['summary'])[:300])}</p>
          <a href="{escape(item['suite_report_href'])}">Open suite report</a>
        </div>"""
        for item in dossier["representative_gallery"]
    )
    return f"""<section id="gallery"><h2>Representative Gallery</h2><div class="cards">{cards}</div></section>"""


def _exploratory_html(dossier: dict[str, Any]) -> str:
    artifacts = dossier.get("exploratory_artifacts", [])
    if not artifacts:
        return """<section id="exploratory"><h2>Exploratory Artifacts</h2><p>No exploratory artifacts archived for this checkpoint yet.</p></section>"""
    cards = []
    for item in artifacts:
        clusters = ", ".join(
            f"{cluster.get('label')} ({cluster.get('count')})"
            for cluster in item.get("observed_clusters", [])[:5]
        )
        hooks = ", ".join(
            f"{key}: {_fmt(value)}"
            for key, value in item.get("comparison_hooks", {}).items()
        )
        links = " | ".join(
            f'<a href="{escape(item[key])}">{escape(label)}</a>'
            for key, label in (
                ("markdown_href", "Markdown"),
                ("json_href", "JSON"),
                ("contact_sheet_href", "Contact sheet"),
            )
            if item.get(key)
        )
        cards.append(
            f"""<div class="card">
              <h3>{escape(str(item.get('title') or 'Exploratory Artifact'))}</h3>
              <p class="meta">Date: {escape(str(item.get('date') or ''))} | Confidence: {escape(str(item.get('confidence') or ''))}</p>
              <p>{escape(str(item.get('working_interpretation') or ''))}</p>
              <p><strong>Observed clusters:</strong> {escape(clusters)}</p>
              <p><strong>Comparison hooks:</strong> {escape(hooks)}</p>
              <p>{links}</p>
            </div>"""
        )
    return f"""<section id="exploratory">
      <h2>Exploratory Artifacts</h2>
      <p class="meta">Archived exploratory probes are documentary addenda, not scored suite evidence.</p>
      <div class="cards">{''.join(cards)}</div>
    </section>"""


def _unknowns_html(dossier: dict[str, Any]) -> str:
    return f"""<section id="unknowns"><h2>Known Unknowns</h2><ul>{''.join(f'<li>{escape(item)}</li>' for item in dossier['known_unknowns'])}</ul></section>"""


def _appendix_html(dossier: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><td>{escape(str(item['suite_name']))}</td><td>{_suite_links(item)}</td></tr>"
        for item in dossier["appendix"]
    )
    return f"""<details id="appendix" open><summary>Appendix - Evidence Links</summary><table><thead><tr><th>Suite</th><th>Artifacts</th></tr></thead><tbody>{rows}</tbody></table></details>"""


def _all_records(suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for suite in suites for record in suite.get("report", {}).get("records", []) if isinstance(record, dict)]


def _all_records_with_suite(suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"suite": suite, "record": record}
        for suite in suites
        for record in suite.get("report", {}).get("records", [])
        if isinstance(record, dict)
    ]


def _infer_checkpoint_id(suites: list[dict[str, Any]]) -> str:
    for record in _all_records(suites):
        value = str(record.get("checkpoint_id") or "").strip()
        if value:
            return value
    return "checkpoint"


def _display_checkpoint_name(checkpoint_id: str) -> str:
    return " ".join(part.capitalize() for part in checkpoint_id.split("_") if part) or "Checkpoint"


def _evaluator_roster(suites: list[dict[str, Any]]) -> list[str]:
    labels = {"Qwen3-VL-8B Primary"}
    if any(suite.get("judge_auditor") for suite in suites):
        labels.add("MiniCPM-V-4.5 Auditor")
    return sorted(labels)


def _overall_characterization(suites: list[dict[str, Any]]) -> str:
    summary = _summary_without_characterization(suites)
    profile = _capability_profile(suites)
    strongest = sorted(profile, key=lambda item: _float(item.get("score")) or 0, reverse=True)[:3]
    weakest = sorted(profile, key=lambda item: _float(item.get("score")) or 99)[:2]
    return (
        f"Observed average {_fmt(summary['average_score'])} across {summary['image_count']} images. "
        f"Strongest observed dimensions: {', '.join(item['label'].lower() for item in strongest)}. "
        f"Most review-worthy dimensions: {', '.join(item['label'].lower() for item in weakest)}."
    )


def _summary_without_characterization(suites: list[dict[str, Any]]) -> dict[str, Any]:
    records = _all_records(suites)
    counts = _pass_fail_counts(records)
    return {
        "suite_count": len(suites),
        "image_count": len(records),
        "average_score": _average([_float(record.get("overall_score")) for record in records]),
        "pass_count": counts["pass"],
        "conditional_pass_count": counts["conditional_pass"],
        "fail_count": counts["fail"],
    }


def _pass_fail_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "conditional_pass": 0, "fail": 0, "unknown": 0}
    for record in records:
        counts[_pass_fail_state(record)] += 1
    return counts


def _pass_fail_state(record: dict[str, Any]) -> str:
    value = str(record.get("pass_fail") or "").lower().replace("-", "_").replace(" ", "_")
    if "conditional" in value:
        return "conditional_pass"
    if "fail" in value:
        return "fail"
    if "pass" in value:
        return "pass"
    return "unknown"


def _rating(score: float | None) -> str:
    if score is None:
        return "Not targeted"
    if score >= 8.75:
        return "Excellent"
    if score >= 8.0:
        return "Strong"
    if score >= 7.0:
        return "Moderate"
    if score >= 6.0:
        return "Mixed"
    return "Weak"


def _lower_rating(value: Any) -> str:
    text = str(value or "not assessed")
    return text[:1].lower() + text[1:]


def _rank_terms(records: list[dict[str, Any]], terms: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    counts = []
    texts = [_flatten(record).lower() for record in records]
    for label, needles in terms.items():
        count = sum(1 for text in texts if any(needle in text for needle in needles))
        if count:
            counts.append({"label": label, "count": count})
    counts.sort(key=lambda item: (-int(item["count"]), str(item["label"])))
    return counts[:5]


def _top_observation_categories(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for record in records:
        for key in ("wildcard_observations", "semantic_observations"):
            for item in record.get(key, []) or []:
                if isinstance(item, dict):
                    counts[str(item.get("category") or "other")] += 1
    return [{"label": label, "count": count} for label, count in counts.most_common(6)]


def _failure_personality(records: list[dict[str, Any]]) -> str:
    failed = [record for record in records if _pass_fail_state(record) == "fail"]
    if not failed:
        return "No failing cases were recorded under these conditions."
    categories = Counter()
    tests = []
    for record in failed:
        tests.append(str(record.get("test_id")))
        for key in ("wildcard_observations", "semantic_observations"):
            for item in record.get(key, []) or []:
                if isinstance(item, dict):
                    categories[str(item.get("category") or "other")] += 1
    category_text = ", ".join(label.replace("_", " ") for label, _count in categories.most_common(4)) or "test-specific failures"
    return f"Failures clustered around {category_text}; representative failing tests include {', '.join(tests[:6])}."


def _lora_profile(records: list[dict[str, Any]]) -> str:
    lora_records = [record for record in records if "lora" in _record_text(record)]
    if not lora_records:
        return "LoRA behavior was not targeted in the analyzed records."
    avg = _average([_float(record.get("overall_score")) for record in lora_records])
    counts = _pass_fail_counts(lora_records)
    return f"LoRA-targeted records averaged {_fmt(avg)} with {counts['pass']} pass, {counts['conditional_pass']} conditional, and {counts['fail']} fail outcomes."


def _recovery_tendencies(records: list[dict[str, Any]]) -> str:
    conditional = [record for record in records if _pass_fail_state(record) == "conditional_pass"]
    if not conditional:
        return "No conditional-pass recovery band was recorded."
    avg = _average([_float(record.get("overall_score")) for record in conditional])
    return f"{len(conditional)} records landed in conditional-pass territory, averaging {_fmt(avg)}; these are useful for studying partial prompt recovery."


def _confidence_label(evidence_count: int, evaluator_agreement: bool) -> str:
    if evidence_count >= 20 and evaluator_agreement:
        return "High within tested conditions"
    if evidence_count >= 2:
        return "Medium within tested conditions"
    return "Low; limited evidence"


def _suite_label(run_name: str) -> str:
    label = run_name
    for prefix in ("run_betterthanwords_v30_", "run_"):
        if label.startswith(prefix):
            label = label[len(prefix) :]
    return " ".join(part.capitalize() for part in label.split("_") if part)


def _settings_text(defaults: dict[str, Any]) -> str:
    if not defaults:
        return "n/a"
    return (
        f"{defaults.get('steps', 'n/a')} steps, cfg {defaults.get('cfg_scale', 'n/a')}, "
        f"{defaults.get('width', 'n/a')}x{defaults.get('height', 'n/a')}, "
        f"{defaults.get('sampler_name', 'n/a')}/{defaults.get('scheduler', 'none')}"
    )


def _review_text(item: dict[str, Any]) -> str:
    if item.get("tier_a") is None:
        return "n/a"
    return f"A {item.get('tier_a')} / B {item.get('tier_b')} / C {item.get('tier_c')}"


def _suite_links(item: dict[str, Any]) -> str:
    links = []
    for key, label in (
        ("report_href", "Report"),
        ("contact_sheet_href", "Contact sheet"),
        ("comparison_href", "Comparison"),
        ("review_href", "Review queue"),
    ):
        href = item.get(key)
        if href:
            links.append(f'<a href="{escape(str(href))}">{label}</a>')
    return " | ".join(links) if links else "n/a"


def _signal_card(title: str, items: list[dict[str, Any]]) -> str:
    if not items:
        content = "<p class=\"meta\">Not enough signal.</p>"
    else:
        content = "<ul>" + "".join(f"<li>{escape(str(item['label']))}: {escape(str(item['count']))}</li>" for item in items) + "</ul>"
    return f'<div class="card"><h3>{escape(title)}</h3>{content}</div>'


def _bar_width(score: Any) -> int:
    value = _float(score)
    if value is None:
        return 0
    return max(0, min(100, int(value * 10)))


def _loras_used(suites: list[dict[str, Any]]) -> list[str]:
    loras: set[str] = set()
    for suite in suites:
        for test in suite.get("manifest", {}).get("tests", []) or []:
            for match in _LORA_RE.findall(str(test.get("prompt") or "")):
                loras.add(match)
    for record in _all_records(suites):
        for match in _LORA_RE.findall(_flatten(record)):
            loras.add(match)
    return sorted(loras)


def _recommended_roles(dossier: dict[str, Any]) -> list[str]:
    roles = []
    profile = {item["label"]: item for item in dossier["capability_profile"]}
    if (_float(profile.get("Photographic realism", {}).get("score")) or 0) >= 8:
        roles.append("photoreal portrait/base realism work")
    if (_float(profile.get("Human anatomy", {}).get("score")) or 0) >= 8:
        roles.append("human anatomy and adult realism evaluation")
    if (_float(profile.get("Animal anatomy", {}).get("score")) or 0) >= 8:
        roles.append("animal anatomy prompts")
    if (_float(profile.get("Environmental realism", {}).get("score")) or 0) >= 8:
        roles.append("realistic environment prompts")
    if not roles:
        roles.append("case-by-case reviewed generation")
    return roles


def _not_recommended_for(dossier: dict[str, Any]) -> list[str]:
    output = []
    profile = {item["label"]: item for item in dossier["capability_profile"]}
    if (_float(profile.get("LoRA robustness", {}).get("score")) or 10) < 8:
        output.append("unreviewed identity/style LoRA production")
    if (_float(profile.get("Conceptual prior", {}).get("score")) or 10) < 8:
        output.append("unreviewed abstract/conceptual prompt interpretation")
    if any("nudity" in item.get("observation", "").lower() for item in dossier["characteristic_tensions"]):
        output.append("strict clothing-state prompts without review")
    return output or ["no specific exclusion established under this dossier"]


def _top_tags(records: list[dict[str, Any]], positive: bool) -> list[str]:
    counts: Counter[str] = Counter()
    if positive:
        for record in records:
            for tag in record.get("recommended_tags", []) or []:
                counts[str(tag)] += 1
    else:
        for record in records:
            for key in ("wildcard_observations", "semantic_observations"):
                for item in record.get(key, []) or []:
                    if isinstance(item, dict):
                        counts[str(item.get("category") or "other")] += 1
            if _pass_fail_state(record) == "fail":
                counts["fail"] += 1
    return [label for label, _count in counts.most_common(5)]


def _records_matching_capability(suites: list[dict[str, Any]], label: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    hints_by_label = {
        "Photographic realism": ("face", "skin", "photoreal", "realistic", "photo"),
        "Human anatomy": ("anatomy", "body", "hands", "feet", "pose", "chest"),
        "Animal anatomy": ("horse", "dog", "animal", "conformation"),
        "Composition": ("composition", "perspective", "overhead", "mirror"),
        "Conceptual prior": ("concept", "hallucination", "prior"),
        "LoRA robustness": ("lora", "adapter", "trigger", "weight", "identity"),
        "Constraint fidelity": ("clothing", "integrity", "prompt", "object", "interaction"),
        "Environmental realism": ("environment", "ecology", "kitchen", "street", "library", "jungle"),
    }
    hints = hints_by_label.get(label, (label.lower(),))
    matches = []
    for suite in suites:
        for record in suite.get("report", {}).get("records", []):
            if any(hint in _record_text(record) for hint in hints):
                matches.append((suite, record))
    matches.sort(key=lambda item: _float(item[1].get("overall_score")) or 0, reverse=True)
    return matches


def _agreement_phrase(dossier: dict[str, Any]) -> str:
    agreement = dossier["evaluator_agreement"]
    if not agreement.get("tests_compared"):
        return "Primary-only evidence in this dossier."
    return (
        f"{agreement['tests_compared']} tests compared with {agreement['tier_a']} Tier A review items "
        f"and {agreement['hard_disagreements']} hard disagreements."
    )


def _nudity_tests(suites: list[dict[str, Any]]) -> list[str]:
    tests = []
    for record in _all_records(suites):
        if _has_observed_nudity(record):
            tests.append(str(record.get("test_id")))
    return tests[:8]


_LORA_RE = re.compile(r"<lora:([^:>]+):")


def _optional_relative(output_root: Path, path: Path) -> str:
    return _relative(output_root, path) if path.exists() else ""


def _relative(output_root: Path, path: Path) -> str:
    return Path(os.path.relpath(path.resolve(), output_root.resolve())).as_posix()


def _record_text(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key, "")) for key in ("test_id", "test_name", "prompt_adherence", "visual_summary", "recommended_tags")).lower()


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value or "")


def _average(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 2)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized_score(value: Any) -> float | None:
    score = _float(value)
    if score is None:
        return None
    if score > 10:
        return round(score / 10, 2)
    return score


def _fmt(value: Any) -> str:
    number = _float(value)
    if number is None:
        return "n/a"
    return f"{number:.2f}"


_SUBJECT_TERMS = {
    "solitary human": ("woman", "man", "person", "solitary", "portrait"),
    "group": ("group", "multiple", "two people", "three", "four people"),
    "animal / creature": ("horse", "dog", "creature", "animal", "fairy", "groblin"),
    "environment": ("environment", "landscape", "library", "street", "jungle", "garden"),
    "artifact / object": ("object", "cart", "mug", "book", "symbol", "text"),
}

_MOOD_TERMS = {
    "documentary": ("realistic", "photo", "ordinary", "natural light", "studio"),
    "dramatic": ("dramatic", "cinematic", "storm", "heroic", "fantasy"),
    "sensual / glamour": ("nude", "sensual", "glamour", "erotic", "beauty"),
    "contemplative": ("quiet", "contemplative", "stillness", "neutral", "reflective"),
    "surreal": ("surreal", "symbolic", "dreamlike", "abstract", "concept"),
}

_VISUAL_TERMS = {
    "photography": ("photo", "photographic", "realistic", "skin texture"),
    "cinematic": ("cinematic", "dramatic lighting", "film"),
    "fantasy": ("fantasy", "fairy", "creature", "guardian", "monster"),
    "illustration": ("illustration", "watercolor", "comic", "painterly"),
    "text/poster": ("text", "poster", "typography", "word"),
}
