from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .analysis_client import _extract_message_content, _image_data_url, _normalize_chat_completions_endpoint, _parse_json_content


class BasinObserverClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2200,
        timeout: int = 600,
        use_response_format: bool = True,
    ) -> None:
        self.endpoint = _normalize_chat_completions_endpoint(endpoint)
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.use_response_format = use_response_format

    def observe_image(self, image_path: Path, directive: str, generation_metadata: dict[str, Any]) -> dict[str, Any]:
        test = generation_metadata.get("test", {})
        request = generation_metadata.get("request", {})
        context = {
            "test_id": test.get("id", ""),
            "test_name": test.get("name", ""),
            "category": test.get("category", ""),
            "purpose": test.get("purpose", ""),
            "prompt": request.get("prompt") or test.get("prompt", ""),
            "prompt_metadata": test.get("metadata", {}),
            "checkpoint": generation_metadata.get("checkpoint", {}),
            "settings": generation_metadata.get("settings", {}),
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful visual field observer. Report visible evidence only. "
                        "Separate observation from hypothesis and do not infer training source or mechanism."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{directive.strip()}\n\nObservation context:\n{json.dumps(context, indent=2)}"},
                        {"type": "text", "text": "Generated image under observation."},
                        {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                    ],
                },
            ],
        }
        if self.use_response_format:
            payload["response_format"] = basin_observer_response_format()
        raw_response = self._post(payload)
        parsed = _parse_json_content(_extract_message_content(raw_response))
        parsed["_raw_response"] = raw_response
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
            raise RuntimeError(f"Basin observer request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Basin observer request failed: {exc.reason}") from exc


def run_basin_observer(
    run_root: Path,
    directive_path: Path,
    client: BasinObserverClient,
    observer_id: str,
    label: str,
    overwrite: bool = False,
    test_ids: list[str] | None = None,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    generation_index = json.loads((run_root / "generation_index.json").read_text(encoding="utf-8"))
    directive = directive_path.read_text(encoding="utf-8")
    selected_ids = set(test_ids or [])
    output_root = run_root / "observer_runs" / observer_id
    record_root = output_root / "records"
    record_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    for generation_record in generation_index.get("records", []):
        test_id = str(generation_record.get("test_id") or "")
        if selected_ids and test_id not in selected_ids:
            continue
        generation_path = Path(generation_record["test_root"]) / "generation.json"
        generation_metadata = json.loads(generation_path.read_text(encoding="utf-8"))
        target_dir = record_root / test_id
        target_dir.mkdir(parents=True, exist_ok=True)

        for image_value in generation_record.get("image_paths", []):
            image_path = Path(image_value)
            output_path = target_dir / f"{image_path.stem}_basin_observer.json"
            if output_path.exists() and not overwrite:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            else:
                try:
                    observation = client.observe_image(image_path, directive, generation_metadata)
                    raw_response = observation.pop("_raw_response", None)
                    payload = {
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
            records.append(
                {
                    "observer_id": observer_id,
                    "observer_label": label,
                    "model": client.model,
                    "checkpoint_id": generation_record.get("checkpoint_id"),
                    "test_id": test_id,
                    "test_name": generation_record.get("test_name"),
                    "image_path": str(image_path),
                    "observation_path": str(output_path),
                    "observer_failure": bool(payload.get("observer_failure")),
                    "basin_membership_score": observation.get("basin_membership_score"),
                    "boundary_status": observation.get("boundary_status"),
                    "distance_from_prototype": observation.get("distance_from_prototype"),
                    "prototype_centrality": observation.get("prototype_centrality"),
                    "prototype_parent": observation.get("prototype_parent"),
                    "representative_value": observation.get("representative_value"),
                    "boundary_value": observation.get("boundary_value"),
                    "primary_visual_subject": observation.get("primary_visual_subject"),
                    "dominant_visual_anchor": observation.get("dominant_visual_anchor"),
                    "dominant_attractor": observation.get("dominant_attractor"),
                    "boundary_behavior": observation.get("boundary_behavior"),
                    "observer_confidence": observation.get("observer_confidence"),
                    "recommendation": observation.get("recommendation"),
                    "summary": observation.get("summary", ""),
                }
            )

    index = {
        "artifact_type": "basin_observer_index",
        "observer": {"id": observer_id, "label": label, "model": client.model},
        "directive": str(directive_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "observed_images": len(records),
        "failures": sum(1 for record in records if record["observer_failure"]),
        "records": records,
    }
    (output_root / "basin_observer_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def basin_observer_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cef_ssp_basin_observer",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "test_id",
                    "primary_visual_subject",
                    "basin_membership_score",
                    "boundary_status",
                    "distance_from_prototype",
                    "prototype_centrality",
                    "prototype_parent",
                    "representative_value",
                    "boundary_value",
                    "evidence_for_membership",
                    "evidence_against_membership",
                    "attractor_types",
                    "dominant_attractor",
                    "dominant_visual_anchor",
                    "circular_emblematic_form",
                    "narrative_figure_present",
                    "media_layout_present",
                    "boundary_behavior",
                    "boundary_branch",
                    "uncertainties",
                    "suggested_next_probes",
                    "observer_confidence",
                    "recommendation",
                    "summary",
                ],
                "properties": {
                    "test_id": {"type": "string"},
                    "primary_visual_subject": {"type": "string", "enum": ["character", "object", "circular_emblem", "document", "media_artifact", "scene", "text_layout", "mixed", "unclear"]},
                    "basin_membership_score": {"type": "number", "minimum": 0, "maximum": 100},
                    "boundary_status": {"type": "string", "enum": ["core", "branch", "edge", "outside", "ambiguous"]},
                    "distance_from_prototype": {"type": "number", "minimum": 0, "maximum": 100},
                    "prototype_centrality": {"type": "number", "minimum": 0, "maximum": 100},
                    "prototype_parent": {"type": "string", "enum": ["medal", "seal", "document", "cover", "poster", "editorial", "currency", "heraldry", "identity", "packaging", "mascot", "plaque", "trophy", "stamp", "ticket", "other", "unclear"]},
                    "representative_value": {"type": "string", "enum": ["canonical_example", "good_teaching_example", "useful_edge_probe", "poor_representative", "unclear"]},
                    "boundary_value": {"type": "number", "minimum": 0, "maximum": 100},
                    "evidence_for_membership": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "evidence_against_membership": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "attractor_types": {"type": "array", "items": {"type": "string"}},
                    "dominant_attractor": {"type": "string"},
                    "dominant_visual_anchor": {"type": "string", "enum": ["circle", "text", "figure", "document", "object", "scene", "border", "frame", "mixed", "unclear"]},
                    "circular_emblematic_form": {"type": "string", "enum": ["yes", "no", "partial", "unclear"]},
                    "narrative_figure_present": {"type": "string", "enum": ["yes", "no", "partial", "unclear"]},
                    "media_layout_present": {"type": "string", "enum": ["yes", "no", "partial", "unclear"]},
                    "boundary_behavior": {"type": "string", "enum": ["inside", "branching", "outside", "ambiguous"]},
                    "boundary_branch": {"type": "string"},
                    "uncertainties": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "suggested_next_probes": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "observer_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "recommendation": {"type": "string", "enum": ["accept_core_basin_example", "accept_boundary_example", "human_review_recommended", "outside_basin"]},
                    "summary": {"type": "string"},
                },
            },
        },
    }
