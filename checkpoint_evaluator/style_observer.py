from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .analysis import _resolve_reference_images
from .analysis_client import (
    _extract_message_content,
    _image_data_url,
    _normalize_chat_completions_endpoint,
    _parse_json_content,
    _reference_content_blocks,
)


class StyleObserverClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1600,
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

    def observe_image(
        self,
        image_path: Path,
        directive: str,
        generation_metadata: dict[str, Any],
        reference_images: list[dict[str, Any]],
    ) -> dict[str, Any]:
        test = generation_metadata.get("test", {})
        request = generation_metadata.get("request", {})
        context = {
            "test_id": test.get("id", ""),
            "test_name": test.get("name", ""),
            "category": test.get("category", ""),
            "purpose": test.get("purpose", ""),
            "prompt": request.get("prompt") or test.get("prompt", ""),
            "reference_instruction": test.get("reference_instruction", ""),
            "reference_images": [
                {
                    "label": reference.get("label", ""),
                    "purpose": reference.get("purpose", ""),
                }
                for reference in reference_images
            ],
            "lora_profile": generation_metadata.get("lora_profile", {}),
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a literal visual observer. Report visible evidence only. "
                        "You are not a judge and must not score, rank, pass, or fail the image."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{directive.strip()}\n\nObservation context:\n{json.dumps(context, indent=2)}",
                        },
                        {"type": "text", "text": "Generated image under observation."},
                        {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                        *_reference_content_blocks(reference_images),
                    ],
                },
            ],
        }
        if self.use_response_format:
            payload["response_format"] = _observer_response_format()
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
            raise RuntimeError(f"Style observer request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Style observer request failed: {exc.reason}") from exc


def run_style_observer(
    run_root: Path,
    directive_path: Path,
    client: StyleObserverClient,
    observer_id: str,
    label: str,
    overwrite: bool = False,
    test_ids: list[str] | None = None,
    lora_profile_ids: list[str] | None = None,
    cases: list[str] | None = None,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    generation_index = json.loads((run_root / "generation_index.json").read_text(encoding="utf-8"))
    directive = directive_path.read_text(encoding="utf-8")
    selected_ids = set(test_ids or [])
    selected_profiles = set(lora_profile_ids or [])
    selected_cases = {_parse_case_spec(value) for value in (cases or [])}
    output_root = run_root / "observer_runs" / observer_id
    record_root = output_root / "records"
    record_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    for generation_record in generation_index.get("records", []):
        test_id = str(generation_record.get("test_id") or "")
        if selected_ids and test_id not in selected_ids:
            continue
        profile_id = str(generation_record.get("lora_profile_id") or "none")
        if selected_profiles and profile_id not in selected_profiles:
            continue
        if selected_cases and (profile_id, test_id) not in selected_cases:
            continue
        generation_path = Path(generation_record["test_root"]) / "generation.json"
        generation_metadata = json.loads(generation_path.read_text(encoding="utf-8"))
        references = _resolve_reference_images(generation_metadata, run_root)
        target_dir = record_root / profile_id / test_id
        target_dir.mkdir(parents=True, exist_ok=True)

        for image_value in generation_record.get("image_paths", []):
            image_path = Path(image_value)
            output_path = target_dir / f"{image_path.stem}_observer.json"
            if output_path.exists() and not overwrite:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            else:
                try:
                    observation = client.observe_image(image_path, directive, generation_metadata, references)
                    raw_response = observation.pop("_raw_response", None)
                    payload = {
                        "observer": {"id": observer_id, "label": label, "model": client.model},
                        "observation": observation,
                        "raw_response": raw_response,
                        "image_path": str(image_path),
                        "generation_path": str(generation_path),
                        "reference_images": references,
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
                        "reference_images": references,
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
                    "lora_profile_id": profile_id,
                    "test_id": test_id,
                    "test_name": generation_record.get("test_name"),
                    "image_path": str(image_path),
                    "observation_path": str(output_path),
                    "observer_failure": bool(payload.get("observer_failure")),
                    "requested_subject": observation.get("requested_subject", {}),
                    "visible_medium_features": observation.get("visible_medium_features", []),
                    "reference_similarities": observation.get("reference_similarities", []),
                    "reference_differences": observation.get("reference_differences", []),
                    "missing_reference_characteristics": observation.get("missing_reference_characteristics", []),
                    "possible_leakage": observation.get("possible_leakage", []),
                    "uncertainties": observation.get("uncertainties", []),
                    "observer_confidence": observation.get("observer_confidence"),
                    "summary": observation.get("summary", ""),
                }
            )

    index = {
        "artifact_type": "style_observer_index",
        "observer": {"id": observer_id, "label": label, "model": client.model},
        "directive": str(directive_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "observed_images": len(records),
        "failures": sum(1 for record in records if record["observer_failure"]),
        "records": records,
    }
    (output_root / "observer_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def _parse_case_spec(value: str) -> tuple[str, str]:
    profile_id, separator, test_id = value.partition(":")
    if not separator or not profile_id.strip() or not test_id.strip():
        raise ValueError(f"Observer case must be PROFILE_ID:TEST_ID, got: {value}")
    return profile_id.strip(), test_id.strip()


def _observer_response_format() -> dict[str, Any]:
    evidence_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["feature", "evidence", "confidence"],
        "properties": {
            "feature": {"type": "string"},
            "evidence": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cef_literal_style_observer",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "test_id",
                    "requested_subject",
                    "visible_medium_features",
                    "reference_similarities",
                    "reference_differences",
                    "missing_reference_characteristics",
                    "possible_leakage",
                    "uncertainties",
                    "observer_confidence",
                    "summary",
                ],
                "properties": {
                    "test_id": {"type": "string"},
                    "requested_subject": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["present", "description", "visible_prompt_elements", "missing_prompt_elements"],
                        "properties": {
                            "present": {"type": "string", "enum": ["yes", "no", "uncertain"]},
                            "description": {"type": "string"},
                            "visible_prompt_elements": {"type": "array", "items": {"type": "string"}},
                            "missing_prompt_elements": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "visible_medium_features": {"type": "array", "items": evidence_item},
                    "reference_similarities": {"type": "array", "items": evidence_item},
                    "reference_differences": {"type": "array", "items": evidence_item},
                    "missing_reference_characteristics": {"type": "array", "items": {"type": "string"}},
                    "possible_leakage": {"type": "array", "items": evidence_item},
                    "uncertainties": {"type": "array", "items": {"type": "string"}},
                    "observer_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "summary": {"type": "string"},
                },
            },
        },
    }
