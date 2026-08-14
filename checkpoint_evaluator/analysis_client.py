from __future__ import annotations

import base64
import json
import mimetypes
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class QwenEvaluationClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 3000,
        timeout: int = 180,
        use_response_format: bool = True,
        response_mode: str = "json",
    ) -> None:
        self.endpoint = _normalize_chat_completions_endpoint(endpoint)
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.use_response_format = use_response_format
        self.response_mode = response_mode

    def provenance(self) -> dict[str, Any]:
        """Return sanitized evaluator settings suitable for run artifacts.

        Credentials are deliberately excluded. The normalized endpoint and decoding
        controls are part of the experiment and must survive beyond the live process.
        """
        return {
            "client": type(self).__name__,
            "endpoint": self.endpoint,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout,
            "response_mode": self.response_mode,
            "structured_response_requested": self.use_response_format,
        }

    def evaluate_image(
        self,
        image_path: Path,
        directive: str,
        generation_metadata: dict[str, Any],
        criteria: list[dict[str, Any]],
        reference_images: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        test = generation_metadata.get("test", {})
        request = generation_metadata.get("request", {})
        reference_images = reference_images or []
        # Keep the text context compact and structured; the generated image remains the only scored image.
        context = {
            "test_id": test.get("id", ""),
            "test_name": test.get("name", ""),
            "prompt": request.get("prompt") or test.get("prompt", ""),
            "negative_prompt": request.get("negative_prompt", ""),
            "criteria": criteria,
            "reference_assisted_evaluation": bool(reference_images),
            "reference_instruction": test.get("reference_instruction", ""),
            "reference_images": [
                {
                    "label": reference.get("label", ""),
                    "path": reference.get("path", ""),
                    "purpose": reference.get("purpose", ""),
                }
                for reference in reference_images
            ],
            "checkpoint": generation_metadata.get("checkpoint", {}),
            "lora_profile": generation_metadata.get("lora_profile", {}),
            "generation": {
                "seed": request.get("seed"),
                "steps": request.get("steps"),
                "cfg_scale": request.get("cfg_scale"),
                "sampler_name": request.get("sampler_name"),
                "width": request.get("width"),
                "height": request.get("height"),
            },
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict, skeptical image evaluation assistant for Stable Diffusion benchmark testing. "
                        "Your job includes finding cases where an image technically satisfies rubric items but fails the "
                        "plain human intent of the prompt."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{directive.strip()}\n\nEvaluation context:\n{json.dumps(context, indent=2)}",
                        },
                        {
                            "type": "text",
                            "text": "Generated image under evaluation. Score only this image.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(image_path)},
                        },
                        *_reference_content_blocks(reference_images),
                    ],
                },
            ],
        }
        if self.use_response_format:
            # LM Studio/OpenAI-compatible servers that honor this schema give us much cleaner report data.
            payload["response_format"] = _response_format_schema()
        raw_response = self._post(payload)
        if self.response_mode == "markdown":
            parsed = _normalize_analysis_response(
                _parse_markdown_content(_extract_message_content(raw_response), str(test.get("id", "")))
            )
        else:
            try:
                parsed = _normalize_analysis_response(_parse_json_content(_extract_message_content(raw_response)))
            except ValueError:
                # Some OpenAI-compatible VLM servers advertise JSON/schema support but occasionally emit
                # an incomplete object. Retrying the same visual request preserves the evaluation source
                # better than attempting to repair missing visual claims from partial text.
                raw_response = self._post(payload)
                parsed = _normalize_analysis_response(_parse_json_content(_extract_message_content(raw_response)))
        parsed["_raw_response"] = raw_response
        return parsed

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen evaluation request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Qwen evaluation request failed: {exc.reason}") from exc


def _response_format_schema() -> dict[str, Any]:
    # Keep this schema aligned with the Qwen directive whenever categories or failure modes are added.
    string_array = {"type": "array", "items": {"type": "string"}}
    score_or_null = {"type": ["number", "null"], "minimum": 0, "maximum": 10}
    rubric_scores = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "prompt_adherence",
            "composition",
            "anatomy",
            "face_quality",
            "hand_quality",
            "foot_quality",
            "style_adherence",
            "object_interaction",
            "identity_retention",
            "lora_integration",
            "environment_quality",
            "artifact_severity",
        ],
        "properties": {
            "prompt_adherence": score_or_null,
            "composition": score_or_null,
            "anatomy": score_or_null,
            "face_quality": score_or_null,
            "hand_quality": score_or_null,
            "foot_quality": score_or_null,
            "style_adherence": score_or_null,
            "object_interaction": score_or_null,
            "identity_retention": score_or_null,
            "lora_integration": score_or_null,
            "environment_quality": score_or_null,
            "artifact_severity": score_or_null,
        },
    }
    wildcard_observation = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "category",
            "severity",
            "confidence",
            "observation",
            "evidence",
            "suggested_new_criterion",
        ],
        "properties": {
            "category": {
                "type": "string",
                "enum": [
                    "anatomy",
                    "composition",
                    "object",
                    "scale",
                    "style",
                    "artifact",
                    "physics",
                    "physics_failure",
                    "perspective_failure",
                    "unprompted_nudity",
                    "prior_leakage",
                    "age_bias",
                    "beauty_bias",
                    "body_bias",
                    "clothing_bias",
                    "species_bias",
                    "lora_checkpoint_incompatibility",
                    "lora_overpowering",
                    "lora_resistance",
                    "lora_stylization_drift",
                    "lora_identity_suppression",
                    "prompt_conflict",
                    "safety",
                    "other",
                ],
            },
            "severity": {"type": "string", "enum": ["info", "minor", "major", "critical"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "observation": {"type": "string"},
            "evidence": {"type": "string"},
            "suggested_new_criterion": {"type": "string"},
        },
    }
    semantic_observation = {
        "type": "object",
        "additionalProperties": False,
        "required": ["category", "severity", "confidence", "observation", "evidence", "suggested_new_criterion"],
        "properties": {
            "category": {
                "type": "string",
                "enum": [
                    "scale",
                    "subject_identity",
                    "species_mismatch",
                    "intent_conflict",
                    "ecological",
                    "physics",
                    "prompt_conflict",
                    "other",
                ],
            },
            "severity": {"type": "string", "enum": ["info", "minor", "major", "critical"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "observation": {"type": "string"},
            "evidence": {"type": "string"},
            "suggested_new_criterion": {"type": "string"},
        },
    }
    intent_failure_check = {
        "type": "object",
        "additionalProperties": False,
        "required": ["passes_human_intent", "confidence", "failure_modes", "explanation"],
        "properties": {
            "passes_human_intent": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "failure_modes": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "subject_identity",
                        "species_mismatch",
                        "wrong_scale",
                        "wrong_subject_trait",
                        "ordinary_animal_substitution",
                        "intent_conflict",
                        "prompt_literalism",
                        "other",
                    ],
                },
            },
            "explanation": {"type": "string"},
        },
    }
    criterion_score = {
        "type": "object",
        "additionalProperties": False,
        "required": ["criterion_id", "criterion", "score", "confidence", "evidence"],
        "properties": {
            "criterion_id": {"type": "string"},
            "criterion": {"type": "string"},
            "score": {"type": "number", "minimum": 0, "maximum": 10},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "string"},
        },
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cef_image_evaluation",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "test_id",
                    "overall_score",
                    "criteria_scores",
                    "visual_summary",
                    "prompt_adherence",
                    "strengths",
                    "failures",
                    "unexpected_priors",
                    "style_notes",
                    "warnings",
                    "wildcard_observations",
                    "semantic_observations",
                    "intent_failure_check",
                    "rubric_scores",
                    "pass_fail",
                    "recommended_tags",
                    "evaluator_confidence",
                ],
                "properties": {
                    "test_id": {"type": "string"},
                    "overall_score": {"type": "number", "minimum": 0, "maximum": 10},
                    "criteria_scores": {"type": "array", "items": criterion_score},
                    "visual_summary": {"type": "string"},
                    "prompt_adherence": {"type": "string"},
                    "strengths": string_array,
                    "failures": string_array,
                    "unexpected_priors": string_array,
                    "style_notes": string_array,
                    "warnings": string_array,
                    "wildcard_observations": {"type": "array", "items": wildcard_observation},
                    "semantic_observations": {"type": "array", "items": semantic_observation},
                    "intent_failure_check": intent_failure_check,
                    "rubric_scores": rubric_scores,
                    "pass_fail": {"type": "string", "enum": ["pass", "conditional_pass", "fail"]},
                    "recommended_tags": string_array,
                    "evaluator_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    }


def _normalize_chat_completions_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        return endpoint
    if path.endswith("/v1"):
        return endpoint.rstrip("/") + "/chat/completions"
    return endpoint.rstrip("/") + "/v1/chat/completions"


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _reference_content_blocks(reference_images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if not reference_images:
        return blocks
    # References follow the generated image so the model is repeatedly told what is evidence versus calibration.
    blocks.append(
        {
            "type": "text",
            "text": (
                "Reference images follow. They are calibration aids only. Do not score the reference images, "
                "do not require exact duplication, and score only the generated image above."
            ),
        }
    )
    for index, reference in enumerate(reference_images, start=1):
        resolved_path = Path(str(reference.get("resolved_path") or reference.get("path") or ""))
        label = str(reference.get("label") or f"reference_{index:02d}")
        purpose = str(reference.get("purpose") or "")
        blocks.append(
            {
                "type": "text",
                "text": f"Reference image {index}: {label}. Purpose: {purpose}",
            }
        )
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(resolved_path)},
            }
        )
    return blocks


def _extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("OpenAI-compatible response did not contain choices[0].message.content") from exc
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    raise ValueError("Model response content was not text")


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON response must be an object")
    return parsed


def _parse_markdown_content(content: str, fallback_test_id: str = "") -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("Model returned empty Markdown content")
    sections = _markdown_sections(text)
    scores_text = sections.get("scores", text)
    score_patterns = {
        "overall_score": r"(?:overall\s+score|overall)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "concept_resolution": r"concept\s+resolution\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "symbolic_richness": r"symbolic\s+richness\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "narrative_suggestion": r"narrative\s+suggestion\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "prior_leakage": r"prior\s+leakage\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "visual_originality": r"visual\s+originality\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "literal_text_dependency": r"literal\s+text\s+dependency\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "artifact_severity": r"artifact\s+severity\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        "evaluator_confidence": r"(?:confidence|evaluator\s+confidence)\s*:\s*([0-9]+(?:\.[0-9]+)?)",
    }
    values = {key: _markdown_score(scores_text, pattern) for key, pattern in score_patterns.items()}
    overall_score = values.pop("overall_score")
    if overall_score is None:
        scored_values = [value for key, value in values.items() if value is not None and key != "evaluator_confidence"]
        overall_score = round(sum(scored_values) / len(scored_values), 2) if scored_values else 0
    pass_fail = _markdown_pass_fail(scores_text, overall_score)
    interpretation = _section_text(sections, "interpretation")
    interesting_failure = _section_text(sections, "interesting failure", "failure", "failures")
    quote = _section_text(sections, "quote")
    prior_items = _markdown_bullets(_section_text(sections, "prior leakage", "priors", "prior leakage tags"))
    tags = _markdown_bullets(_section_text(sections, "tags", "recommended tags"))

    semantic_observations = []
    if interpretation:
        semantic_observations.append(
            {
                "category": "other",
                "severity": "info",
                "confidence": _confidence(values.get("evaluator_confidence")),
                "observation": interpretation,
                "evidence": quote or "Structured Markdown interpretation section.",
                "suggested_new_criterion": "",
            }
        )
    if interesting_failure:
        semantic_observations.append(
            {
                "category": "intent_conflict",
                "severity": "major" if pass_fail == "fail" else "minor",
                "confidence": _confidence(values.get("evaluator_confidence")),
                "observation": interesting_failure,
                "evidence": quote or "Structured Markdown interesting failure section.",
                "suggested_new_criterion": "",
            }
        )

    wildcard_observations = [
        {
            "category": _prior_category(item),
            "severity": "major" if _prior_category(item) in {"prior_leakage", "unprompted_nudity"} else "minor",
            "confidence": _confidence(values.get("evaluator_confidence")),
            "observation": item,
            "evidence": "Listed by evaluator under prior leakage.",
            "suggested_new_criterion": "",
        }
        for item in prior_items
    ]

    rubric_scores = {key: value for key, value in values.items() if key != "evaluator_confidence" and value is not None}
    return {
        "test_id": _markdown_test_id(text) or fallback_test_id,
        "overall_score": overall_score,
        "criteria_scores": [],
        "visual_summary": interpretation,
        "prompt_adherence": interpretation,
        "strengths": _markdown_bullets(_section_text(sections, "strengths")),
        "failures": _markdown_bullets(_section_text(sections, "failures")),
        "unexpected_priors": prior_items,
        "style_notes": [],
        "warnings": ["Parsed from structured Markdown evaluator output."],
        "wildcard_observations": wildcard_observations,
        "semantic_observations": semantic_observations,
        "intent_failure_check": {
            "passes_human_intent": pass_fail != "fail",
            "confidence": _confidence(values.get("evaluator_confidence")),
            "failure_modes": ["intent_conflict"] if pass_fail == "fail" else [],
            "explanation": interesting_failure or interpretation,
        },
        "rubric_scores": rubric_scores,
        "pass_fail": pass_fail,
        "recommended_tags": tags,
        "evaluator_confidence": _confidence(values.get("evaluator_confidence")),
        "markdown_response": text,
    }


def _markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            current = _normalize_heading(match.group(1))
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def _normalize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", value.lower()).strip()


def _section_text(sections: dict[str, str], *names: str) -> str:
    for name in names:
        text = sections.get(_normalize_heading(name), "").strip()
        if text:
            return text
    return ""


def _markdown_score(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return max(0.0, min(10.0, float(match.group(1))))
    except ValueError:
        return None


def _markdown_pass_fail(text: str, overall_score: float | int | None) -> str:
    match = re.search(r"(?:pass\s*/?\s*fail|pass_fail|result)\s*:\s*([A-Za-z_ -]+)", text, flags=re.IGNORECASE)
    if match:
        raw_value = match.group(1).strip().lower().replace("-", "_")
        if raw_value.startswith("conditional"):
            return "conditional_pass"
        if raw_value.startswith("pass"):
            return "pass"
        if raw_value.startswith("fail"):
            return "fail"
    score = float(overall_score or 0)
    if score >= 7:
        return "pass"
    if score >= 5:
        return "conditional_pass"
    return "fail"


def _markdown_test_id(text: str) -> str:
    match = re.search(r"test\s+id\s*:\s*([A-Za-z0-9_-]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _markdown_bullets(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        match = re.match(r"\s*[-*]\s+(.+?)\s*$", line)
        if match:
            items.append(match.group(1).strip())
    if items:
        return items
    stripped = text.strip()
    if stripped:
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", stripped) if item.strip()]
        if len(sentences) == 1 and len(sentences[0]) < 240:
            return [sentences[0]]
    return []


def _confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.5
    if score > 1:
        score = score / 10
    return max(0.0, min(1.0, score))


def _prior_category(value: str) -> str:
    lowered = value.lower()
    if "nude" in lowered or "nsfw" in lowered:
        return "unprompted_nudity"
    if "beauty" in lowered:
        return "beauty_bias"
    if "body" in lowered:
        return "body_bias"
    if "cloth" in lowered:
        return "clothing_bias"
    if "style" in lowered or "fantasy" in lowered or "anime" in lowered:
        return "style"
    return "prior_leakage"


def _normalize_analysis_response(parsed: dict[str, Any]) -> dict[str, Any]:
    parsed.setdefault("test_id", "")
    parsed.setdefault("overall_score", 0)
    parsed.setdefault("criteria_scores", [])
    parsed.setdefault("visual_summary", "")
    parsed.setdefault("prompt_adherence", "")
    parsed.setdefault("strengths", [])
    parsed.setdefault("failures", [])
    parsed.setdefault("unexpected_priors", [])
    parsed.setdefault("style_notes", [])
    parsed.setdefault("warnings", [])
    parsed.setdefault("wildcard_observations", [])
    parsed.setdefault("semantic_observations", [])
    parsed.setdefault(
        "intent_failure_check",
        {"passes_human_intent": True, "confidence": 0, "failure_modes": [], "explanation": ""},
    )
    parsed.setdefault("rubric_scores", {})
    rubric = parsed["rubric_scores"] if isinstance(parsed["rubric_scores"], dict) else {}
    for key in (
        "prompt_adherence",
        "composition",
        "anatomy",
        "face_quality",
        "hand_quality",
        "foot_quality",
        "style_adherence",
        "object_interaction",
        "identity_retention",
        "lora_integration",
        "environment_quality",
        "artifact_severity",
    ):
        rubric.setdefault(key, None)
    parsed["rubric_scores"] = rubric
    parsed.setdefault("pass_fail", "conditional_pass")
    parsed.setdefault("recommended_tags", [])
    parsed.setdefault("evaluator_confidence", 0)
    return parsed
