from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .analysis_client import _extract_message_content, _image_data_url, _normalize_chat_completions_endpoint, _parse_json_content


METHODOLOGICAL_JUSTIFICATION = (
    "Minimal prompts reduce external semantic constraint, allowing checkpoint-specific conceptual priors "
    "to contribute more visibly to the resulting prototype."
)


class SparseSemanticObserverClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2200,
        timeout: int = 600,
        use_response_format: bool = True,
        observer_schema: str = "sparse-semantic",
    ) -> None:
        self.endpoint = _normalize_chat_completions_endpoint(endpoint)
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.use_response_format = use_response_format
        self.observer_schema = observer_schema

    def observe_image(self, image_path: Path, directive: str, generation_metadata: dict[str, Any]) -> dict[str, Any]:
        test = generation_metadata.get("test", {})
        request = generation_metadata.get("request", {})
        context = {
            "test_id": test.get("id", ""),
            "test_name": test.get("name", ""),
            "source_suite": "sparse_semantic_probe",
            "source_module": (test.get("metadata") or {}).get("source_module", "ssp"),
            "prompt": request.get("prompt", test.get("prompt", "")),
            "prompt_metadata": test.get("metadata", {}),
            "seed": (generation_metadata.get("settings") or {}).get("seed"),
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a score-free sparse-semantic visual observer. Describe only visible evidence. "
                        "Never infer beliefs, intent, training data, hidden mechanisms, or causes."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{directive.strip()}\n\nObservation context:\n{json.dumps(context, indent=2)}"},
                        {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                    ],
                },
            ],
        }
        if self.use_response_format:
            payload["response_format"] = observer_response_format(self.observer_schema)
        raw = self._post(payload)
        parsed = _parse_json_content(_extract_message_content(raw))
        parsed["_raw_response"] = raw
        return parsed

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"SSP observer request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"SSP observer request failed: {exc.reason}") from exc


def run_sparse_semantic_observer(
    run_root: Path,
    directive_path: Path,
    client: SparseSemanticObserverClient,
    observer_id: str,
    label: str,
    overwrite: bool = False,
    test_ids: list[str] | None = None,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    generation_index = _read_json(run_root / "generation_index.json")
    directive = directive_path.read_text(encoding="utf-8-sig")
    selected = set(test_ids or [])
    output_root = run_root / "observer_runs" / observer_id
    record_root = output_root / "records"
    record_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    behavioral_records: list[dict[str, Any]] = []

    for generation_record in generation_index.get("records", []):
        test_id = str(generation_record.get("test_id") or "")
        if selected and test_id not in selected:
            continue
        generation_path = Path(generation_record["test_root"]) / "generation.json"
        generation_metadata = _read_json(generation_path)
        test = generation_metadata.get("test", {})
        metadata = test.get("metadata", {}) or {}
        for image_value in generation_record.get("image_paths", []):
            image_path = Path(image_value)
            output_path = record_root / test_id / f"{image_path.stem}_ssp_observer.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists() and not overwrite:
                payload = _read_json(output_path)
            else:
                try:
                    observation = client.observe_image(image_path, directive, generation_metadata)
                    raw_response = observation.pop("_raw_response", None)
                    payload = {
                        "artifact_type": "ssp_observation",
                        "observer": {"id": observer_id, "label": label, "model": client.model},
                        "observation": observation,
                        "raw_response": raw_response,
                        "image_path": str(image_path),
                        "generation_path": str(generation_path),
                        "observed_at": datetime.now().isoformat(timespec="seconds"),
                    }
                except Exception as exc:
                    if not continue_on_error:
                        raise
                    payload = {
                        "artifact_type": "ssp_observation_failure",
                        "observer": {"id": observer_id, "label": label, "model": client.model},
                        "observer_failure": True,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "image_path": str(image_path),
                        "generation_path": str(generation_path),
                        "observed_at": datetime.now().isoformat(timespec="seconds"),
                    }
                output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            observation = payload.get("observation", {})
            record = {
                "observer_id": observer_id,
                "observer_label": label,
                "model": client.model,
                "checkpoint_id": generation_record.get("checkpoint_id"),
                "checkpoint_title": generation_record.get("checkpoint_title"),
                "checkpoint_hash": generation_record.get("checkpoint_hash"),
                "test_id": test_id,
                "prompt": (generation_metadata.get("request") or {}).get("prompt", test.get("prompt", "")),
                "seed": (generation_metadata.get("settings") or {}).get("seed"),
                "image_path": str(image_path),
                "observation_path": str(output_path),
                "prompt_metadata": metadata,
                "semantic_anchor_type": metadata.get("semantic_anchor_type"),
                "semantic_neighborhood_id": metadata.get("semantic_neighborhood_id"),
                "prompt_role": metadata.get("prompt_role"),
                "observer_failure": bool(payload.get("observer_failure")),
                **{key: observation.get(key) for key in _OBSERVATION_FIELDS},
            }
            records.append(record)
            behavioral_records.append(_behavioral_observation_record(record, observation, payload))

    index = {
        "artifact_type": "sparse_semantic_observer_index",
        "schema_version": "1.0",
        "methodological_justification": METHODOLOGICAL_JUSTIFICATION,
        "observer": {"id": observer_id, "label": label, "model": client.model},
        "observer_schema": getattr(client, "observer_schema", "sparse-semantic"),
        "directive": str(directive_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "observed_images": len(records),
        "failures": sum(1 for record in records if record["observer_failure"]),
        "semantic_phenotype": _semantic_phenotype(records),
        "records": records,
    }
    index_path = output_root / "ssp_observer_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    (output_root / "behavioral_observation_records.json").write_text(
        json.dumps({"artifact_type": "behavioral_observation_record_set", "schema_version": "1.0", "records": behavioral_records}, indent=2),
        encoding="utf-8",
    )
    with (output_root / "behavioral_observation_records.jsonl").open("w", encoding="utf-8") as stream:
        for item in behavioral_records:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    _write_ssp_report(index, output_root)
    _build_contact_sheet(records, output_root / "ssp_contact_sheet.jpg")
    return index


def build_sparse_semantic_comparison(index_paths: list[Path], output_root: Path, title: str) -> dict[str, Any]:
    if len(index_paths) < 2:
        raise ValueError("SSP comparison requires at least two observer indexes.")
    indexes = [_read_json(path) for path in index_paths]
    checkpoints = []
    by_prompt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path, index in zip(index_paths, indexes):
        records = index.get("records", [])
        checkpoint_id = next((str(record.get("checkpoint_id")) for record in records if record.get("checkpoint_id")), path.parent.name)
        checkpoints.append({
            "checkpoint_id": checkpoint_id,
            "index_path": str(path),
            "observed_images": index.get("observed_images", 0),
            "failures": index.get("failures", 0),
            "semantic_phenotype": index.get("semantic_phenotype", {}),
        })
        for record in records:
            by_prompt[str(record.get("test_id"))].append({
                "checkpoint_id": checkpoint_id,
                "prompt": record.get("prompt"),
                "prototype_class": record.get("prototype_class"),
                "literalness": record.get("literalness"),
                "animacy_resolution": record.get("animacy_resolution"),
                "threat_bias": record.get("threat_bias"),
                "observed_medium": record.get("observed_medium"),
                "semantic_anchor_type": record.get("semantic_anchor_type"),
                "semantic_neighborhood_id": record.get("semantic_neighborhood_id"),
                "prompt_role": record.get("prompt_role"),
                "summary": record.get("summary"),
                "image_path": record.get("image_path"),
            })
    comparison = {
        "artifact_type": "sparse_semantic_cross_checkpoint_comparison",
        "schema_version": "1.0",
        "title": title,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "methodological_justification": METHODOLOGICAL_JUSTIFICATION,
        "checkpoints": checkpoints,
        "prompt_comparisons": [{"test_id": key, "observations": value} for key, value in sorted(by_prompt.items())],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "ssp_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    (output_root / "ssp_comparison.html").write_text(_comparison_html(comparison), encoding="utf-8")
    return comparison


_BASE_OBSERVATION_FIELDS = (
    "observed_subject_class", "observed_subject_description", "observed_medium", "literalness",
    "symbolic_interpretation", "prototype_class", "semantic_drift", "animacy_resolution", "threat_bias",
    "null_semantic_occupancy", "null_occupancy_applicable", "modifier_dominance", "modifier_dominance_applicable",
    "collapse_type", "semantic_residue_notes", "style_coherence", "composition_clarity", "narrative_clarity",
    "negative_space_preservation", "unsupported_inference_flags", "claim_discipline_flags", "uncertainties",
    "observer_confidence", "summary",
)

_SAG_OBSERVATION_FIELDS = (
    "embodiment_level", "agency_level", "presentation_grammar",
    "human_primary", "creature_primary", "functional_object_retained", "human_accompaniment",
    "editorial_lifestyle_pull", "clothing_state_leakage",
    "sag_evidence_for", "sag_evidence_against", "sag_uncertainties",
)

_OBSERVATION_FIELDS = (*_BASE_OBSERVATION_FIELDS, *_SAG_OBSERVATION_FIELDS)


def observer_response_format(observer_schema: str) -> dict[str, Any]:
    if observer_schema == "sparse-semantic":
        return sparse_semantic_response_format()
    if observer_schema == "semantic-agency-gradient":
        return semantic_agency_gradient_response_format()
    raise ValueError(f"Unknown semantic observer schema: {observer_schema}")


def sparse_semantic_response_format() -> dict[str, Any]:
    enums = {
        "literalness": ["literal", "symbolic", "abstract", "unknown"],
        "symbolic_interpretation": ["none", "possible", "clear", "unknown"],
        "prototype_class": ["human", "animal", "monster", "plant", "architecture", "artifact", "landscape", "geometric_primitive", "photograph", "painting", "texture", "blank", "mixed", "unknown"],
        "semantic_drift": ["prompt", "nearby_concept", "unrelated_concept", "indeterminate"],
        "animacy_resolution": ["inert", "ambiguous", "animate", "agentive", "strongly_agentive", "unknown"],
        "threat_bias": ["none", "benign", "neutral", "uncanny", "threatening", "hostile", "unknown"],
        "collapse_type": ["none", "low_information_texture", "paper_linen_field", "amorphous_blob", "partial_subject_residue", "portrait_collapse", "central_subject_collapse", "abstract_material_field", "unknown"],
        "style_coherence": ["not_applicable", "low", "medium", "high", "unknown"],
        "composition_clarity": ["not_applicable", "low", "medium", "high", "unknown"],
        "narrative_clarity": ["not_applicable", "low", "medium", "high", "unknown"],
        "negative_space_preservation": ["not_applicable", "low", "medium", "high", "unknown"],
        "observer_confidence": ["low", "medium", "high"],
    }
    properties: dict[str, Any] = {
        "test_id": {"type": "string"},
        "observed_subject_class": {"type": "string"},
        "observed_subject_description": {"type": "string"},
        "observed_medium": {"type": "string"},
        "null_semantic_occupancy": {"type": "integer", "minimum": 0, "maximum": 5},
        "null_occupancy_applicable": {"type": "boolean"},
        "modifier_dominance": {"type": "integer", "minimum": 0, "maximum": 5},
        "modifier_dominance_applicable": {"type": "boolean"},
        "semantic_residue_notes": {"type": "string"},
        "unsupported_inference_flags": {"type": "array", "items": {"type": "string"}},
        "claim_discipline_flags": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    }
    properties.update({key: {"type": "string", "enum": values} for key, values in enums.items()})
    required = ["test_id", *_BASE_OBSERVATION_FIELDS]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cef_sparse_semantic_observation",
            "strict": True,
            "schema": {"type": "object", "additionalProperties": False, "required": required, "properties": properties},
        },
    }


def semantic_agency_gradient_response_format() -> dict[str, Any]:
    base = sparse_semantic_response_format()["json_schema"]["schema"]
    properties = dict(base["properties"])
    sag_enums = {
        "embodiment_level": ["none", "partial", "object", "creature", "human", "mixed", "unknown"],
        "agency_level": ["none", "implicit", "animal", "person", "social_role", "mixed", "unknown"],
        "presentation_grammar": [
            "none", "studio_object", "product_render", "editorial_portrait",
            "editorial_portrait_with_lifestyle_pull", "lifestyle_scene", "narrative_scene",
            "media_layout", "symbolic_presentation", "abstract_field", "mixed", "unknown",
        ],
        "human_primary": ["yes", "no", "partial", "unknown"],
        "creature_primary": ["yes", "no", "partial", "unknown"],
        "functional_object_retained": ["yes", "no", "partial", "not_applicable", "unknown"],
        "human_accompaniment": ["yes", "no", "partial", "unknown"],
        "editorial_lifestyle_pull": ["none", "weak", "moderate", "strong", "unknown"],
        "clothing_state_leakage": ["none", "mild", "moderate", "strong", "not_applicable", "unknown"],
    }
    properties.update({key: {"type": "string", "enum": values} for key, values in sag_enums.items()})
    properties.update(
        {
            "sag_evidence_for": {"type": "array", "items": {"type": "string"}},
            "sag_evidence_against": {"type": "array", "items": {"type": "string"}},
            "sag_uncertainties": {"type": "array", "items": {"type": "string"}},
        }
    )
    required = ["test_id", *_BASE_OBSERVATION_FIELDS, *_SAG_OBSERVATION_FIELDS]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cef_semantic_agency_gradient_observation",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": required,
                "properties": properties,
            },
        },
    }


def _behavioral_observation_record(record: dict[str, Any], observation: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("prompt_metadata", {}) or {}
    return {
        "observation_id": f"{record.get('checkpoint_id')}:{record.get('test_id')}:{record.get('seed')}:{record.get('observer_id')}",
        "source_suite": "sparse_semantic_probe",
        "source_module": metadata.get("source_module", "ssp"),
        "checkpoint": {"id": record.get("checkpoint_id"), "title": record.get("checkpoint_title"), "hash": record.get("checkpoint_hash")},
        "prompt": record.get("prompt"),
        "prompt_metadata": metadata,
        "seed": record.get("seed"),
        "image_id": Path(str(record.get("image_path"))).stem,
        "image_path": record.get("image_path"),
        "evaluator_model": record.get("model"),
        "evaluator_role": "score_free_semantic_observer",
        "evaluator_response": observation,
        "parsed_labels": {key: observation.get(key) for key in _OBSERVATION_FIELDS if key not in {"summary", "uncertainties"}},
        "confidence": observation.get("observer_confidence"),
        "unsupported_inference_flags": observation.get("unsupported_inference_flags", []),
        "claim_discipline_flags": observation.get("claim_discipline_flags", []),
        "human_review": {"status": "not_reviewed", "notes": ""},
        "cpf_notes": "",
        "observer_failure": bool(payload.get("observer_failure")),
    }


def _semantic_phenotype(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [record for record in records if not record.get("observer_failure")]
    return {
        "record_count": len(valid),
        "dominant_prototype_classes": _rank(valid, "prototype_class"),
        "dominant_media": _rank(valid, "observed_medium"),
        "literalness_distribution": _counts(valid, "literalness"),
        "animacy_distribution": _counts(valid, "animacy_resolution"),
        "threat_bias_distribution": _counts(valid, "threat_bias"),
        "collapse_distribution": _counts(valid, "collapse_type"),
        "semantic_anchor_type_distribution": _counts(valid, "semantic_anchor_type"),
        "prompt_role_distribution": _counts(valid, "prompt_role"),
        "semantic_neighborhoods": _neighborhood_profiles(valid),
        "replication_stability": _replication_profiles(valid),
        "mean_null_semantic_occupancy": _mean([record.get("null_semantic_occupancy") for record in valid if record.get("null_occupancy_applicable")]),
        "mean_modifier_dominance": _mean([record.get("modifier_dominance") for record in valid if record.get("modifier_dominance_applicable")]),
        "claim_discipline_flag_count": sum(len(record.get("claim_discipline_flags") or []) for record in valid),
        "note": "Descriptive synthesis only; no correctness score or mechanism claim is implied.",
    }


def _neighborhood_profiles(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        neighborhood = record.get("semantic_neighborhood_id")
        if neighborhood:
            groups[str(neighborhood)].append(record)
    return [{
        "semantic_neighborhood_id": neighborhood,
        "records": len(items),
        "prototype_classes": _counts(items, "prototype_class"),
        "animacy_resolution": _counts(items, "animacy_resolution"),
        "threat_bias": _counts(items, "threat_bias"),
    } for neighborhood, items in sorted(groups.items())]


def _replication_profiles(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        group = (record.get("prompt_metadata") or {}).get("replication_group")
        if group:
            groups[str(group)].append(record)
    profiles = []
    for group, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        prototypes = _counts(items, "prototype_class")
        literalness = _counts(items, "literalness")
        top_count = max(prototypes.values(), default=0)
        profiles.append({
            "replication_group": group,
            "records": len(items),
            "prototype_classes": prototypes,
            "literalness": literalness,
            "prototype_stability": "stable" if top_count == len(items) else "mixed",
            "null_semantic_occupancy": [item.get("null_semantic_occupancy") for item in items if item.get("null_occupancy_applicable")],
        })
    return profiles


def _counts(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(record.get(key)) for record in records if record.get(key) not in (None, "", "unknown")))


def _rank(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [{"label": label, "count": count} for label, count in Counter(str(record.get(key)) for record in records if record.get(key) not in (None, "", "unknown")).most_common(8)]


def _mean(values: list[Any]) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numbers) / len(numbers), 3) if numbers else None


def _write_ssp_report(index: dict[str, Any], output_root: Path) -> None:
    phenotype = index.get("semantic_phenotype", {})
    rows = []
    for record in index.get("records", []):
        image_rel = os.path.relpath(str(record.get("image_path")), output_root).replace("\\", "/")
        rows.append(
            "<tr>"
            f"<td><img src=\"{escape(image_rel)}\" loading=\"lazy\"></td>"
            f"<td><strong>{escape(str(record.get('test_id')))}</strong><br>{escape(repr(record.get('prompt')))}<br>seed {escape(str(record.get('seed')))}</td>"
            f"<td>{escape(str(record.get('prototype_class')))}<br>{escape(str(record.get('animacy_resolution')))}<br>{escape(str(record.get('threat_bias')))}</td>"
            f"<td>{escape(str(record.get('literalness')))}<br>{escape(str(record.get('observed_medium')))}</td>"
            f"<td>{escape(str(record.get('summary') or ''))}</td>"
            "</tr>"
        )
    html = f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>CEF Sparse Semantic Probe</title>
<style>body{{font:14px Segoe UI,sans-serif;margin:24px;background:#f6f6f2;color:#20231f}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d7d9d2;padding:8px;vertical-align:top}}img{{width:150px;height:150px;object-fit:cover}}code{{white-space:pre-wrap}}.meta{{color:#62675f}}</style></head><body>
<h1>Sparse Semantic Probe</h1><p>{escape(METHODOLOGICAL_JUSTIFICATION)}</p>
<p class=\"meta\">Observer: {escape(str(index.get('observer', {}).get('label')))} | Images: {index.get('observed_images')} | Failures: {index.get('failures')}</p>
<h2>Semantic Phenotype</h2><code>{escape(json.dumps(phenotype, indent=2))}</code>
<h2>Observations</h2><table><thead><tr><th>Image</th><th>Probe</th><th>Prototype</th><th>Resolution</th><th>Observation</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    (output_root / "ssp_report.html").write_text(html, encoding="utf-8")


def _build_contact_sheet(records: list[dict[str, Any]], output_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    usable = [record for record in records if Path(str(record.get("image_path"))).exists()]
    if not usable:
        return
    width, height, columns = 260, 310, 5
    rows = (len(usable) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * height), "#f4f2ea")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, record in enumerate(usable):
        x, y = (index % columns) * width, (index // columns) * height
        with Image.open(record["image_path"]) as source:
            image = source.convert("RGB")
            image.thumbnail((250, 250))
            sheet.paste(image, (x + (width - image.width) // 2, y + 4))
        label = f"{record.get('test_id')} | {record.get('prototype_class')}\n{record.get('literalness')} | {record.get('animacy_resolution')}"
        draw.multiline_text((x + 5, y + 258), label, fill="#20231f", font=font, spacing=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def _comparison_html(comparison: dict[str, Any]) -> str:
    rows = []
    for item in comparison.get("prompt_comparisons", []):
        cells = []
        for observation in item.get("observations", []):
            cells.append(
                f"<strong>{escape(str(observation.get('checkpoint_id')))}</strong>: "
                f"{escape(str(observation.get('prototype_class')))} / {escape(str(observation.get('literalness')))} / "
                f"{escape(str(observation.get('animacy_resolution')))}<br>"
            )
        rows.append(f"<tr><td>{escape(str(item.get('test_id')))}</td><td>{''.join(cells)}</td></tr>")
    return f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>{escape(str(comparison.get('title')))}</title>
<style>body{{font:14px Segoe UI,sans-serif;margin:24px;background:#f6f6f2}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d7d9d2;padding:8px;vertical-align:top}}</style></head><body>
<h1>{escape(str(comparison.get('title')))}</h1><p>{escape(METHODOLOGICAL_JUSTIFICATION)}</p>
<table><thead><tr><th>Probe</th><th>Checkpoint resolutions</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>"""


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return loaded
