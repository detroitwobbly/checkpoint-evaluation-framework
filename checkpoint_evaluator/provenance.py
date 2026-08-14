from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PNG_SUFFIXES = {".png"}


def extract_png_provenance(image_path: Path) -> dict[str, Any]:
    """Extract conservative provenance from a generated PNG.

    The raw PNG text chunks are preserved because Forge/A1111 metadata varies by
    version. Parsed fields are best-effort conveniences, not a replacement for
    the raw metadata.
    """
    from PIL import Image

    with Image.open(image_path) as image:
        info = dict(image.info)
        width, height = image.size
        mode = image.mode
        format_name = image.format

    text_chunks = {str(key): _jsonable(value) for key, value in info.items()}
    parameters = _first_text_value(text_chunks, ["parameters", "prompt", "Description", "UserComment"])
    parsed = parse_forge_parameters(parameters or "")
    return {
        "image_path": str(image_path),
        "image_sha256": _sha256(image_path),
        "file_size_bytes": image_path.stat().st_size,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "image": {"width": width, "height": height, "mode": mode, "format": format_name},
        "png_text_keys": sorted(text_chunks),
        "png_text": text_chunks,
        "parameters_text": parameters,
        "parsed_parameters": parsed,
        "parser_notes": [
            "Parsed parameters are best-effort for Forge/A1111-style PNG metadata.",
            "Use png_text/parameters_text as canonical provenance when parser output is incomplete.",
        ],
    }


def extract_run_png_provenance(run_root: Path) -> dict[str, Any]:
    generation_index_path = run_root / "generation_index.json"
    if generation_index_path.exists():
        generation_index = json.loads(generation_index_path.read_text(encoding="utf-8-sig"))
        image_paths = [
            Path(path)
            for record in generation_index.get("records", [])
            for path in record.get("image_paths", [])
            if str(path).lower().endswith(".png")
        ]
    else:
        image_paths = sorted(path for path in run_root.rglob("*.png") if path.is_file())

    records = []
    failures = []
    for image_path in image_paths:
        try:
            record = extract_png_provenance(image_path)
        except Exception as exc:  # pragma: no cover - exercised by malformed external files
            failures.append({"image_path": str(image_path), "error": str(exc), "error_type": type(exc).__name__})
            continue
        generation_path = image_path.parent / "generation.json"
        if generation_path.exists():
            generation = json.loads(generation_path.read_text(encoding="utf-8-sig"))
            record["cef_generation"] = {
                "checkpoint": generation.get("checkpoint", {}),
                "lora_profile": generation.get("lora_profile", {}),
                "test": generation.get("test", {}),
                "settings": generation.get("settings", {}),
                "forge_info": generation.get("forge_info", {}),
            }
        records.append(record)

    index = {
        "artifact_type": "png_provenance_index",
        "schema_version": "0.1",
        "run_root": str(run_root),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "image_count": len(records),
        "failure_count": len(failures),
        "records": records,
        "failures": failures,
    }
    (run_root / "png_provenance_index.json").write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


def parse_forge_parameters(parameters: str) -> dict[str, Any]:
    if not parameters.strip():
        return {}
    prompt_text, negative_prompt, tail = _split_parameters(parameters)
    raw_key_values = _parse_key_value_tail(tail) if tail else {}
    normalized_settings = {
        _normalize_key(key): _coerce_value(value)
        for key, value in raw_key_values.items()
    }
    parsed: dict[str, Any] = {
        "prompt": prompt_text,
        "negative_prompt": negative_prompt,
        "raw_settings": tail,
        "raw_key_values": raw_key_values,
        "settings": normalized_settings,
        "contributors": _contributor_buckets(raw_key_values),
        "unknown_key_values": _unknown_key_values(raw_key_values),
    }
    if "Lora hashes" in raw_key_values:
        parsed["lora_hashes"] = _parse_lora_hashes(raw_key_values["Lora hashes"])
    controlnet_units = _parse_controlnet_units(raw_key_values)
    if controlnet_units:
        parsed["controlnet_units"] = controlnet_units
    return parsed


def _split_parameters(parameters: str) -> tuple[str, str, str]:
    text = parameters.replace("\r\n", "\n").strip()
    negative_marker = "\nNegative prompt:"
    if negative_marker in text:
        prompt, rest = text.split(negative_marker, 1)
        rest = rest.strip()
        settings_match = re.search(r"\nSteps:\s*", rest)
        if settings_match:
            negative = rest[: settings_match.start()].strip()
            tail = rest[settings_match.start() + 1 :].strip()
        else:
            negative = rest
            tail = ""
        return prompt.strip(), negative, tail

    settings_match = re.search(r"\nSteps:\s*", text)
    if settings_match:
        return text[: settings_match.start()].strip(), "", text[settings_match.start() + 1 :].strip()
    return text, "", ""


def _parse_key_value_tail(tail: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    parts = _split_settings_parts(tail)
    index = 0
    while index < len(parts):
        part = parts[index]
        if ":" not in part:
            index += 1
            continue
        key, value = part.split(":", 1)
        key = key.strip()
        value = value.strip()
        if re.fullmatch(r"ControlNet\s+\d+", key, flags=re.IGNORECASE):
            collected = [value]
            index += 1
            while index < len(parts) and ":" in parts[index]:
                nested_key, _nested_value = parts[index].split(":", 1)
                if _normalize_key(nested_key) not in _CONTROLNET_NESTED_KEYS:
                    break
                collected.append(parts[index])
                index += 1
            fields[key] = _strip_balanced_quotes(", ".join(item.strip() for item in collected if item.strip()))
            continue
        fields[key] = _strip_balanced_quotes(value)
        index += 1
    return fields


def _split_settings_parts(tail: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    for char in tail:
        if escape:
            current.append(char)
            escape = False
            continue
        if char == "\\":
            current.append(char)
            escape = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            current.append(char)
            quote = char
            continue
        if char == ",":
            remainder = "".join(current).strip()
            # A new A1111/Forge setting usually follows ", Key: value". If the
            # following text is not key-like, keep the comma inside the value.
            parts.append(remainder)
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return _merge_non_key_parts(parts)


def _merge_non_key_parts(parts: list[str]) -> list[str]:
    merged: list[str] = []
    key_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9 _./()+-]{0,80}:")
    for part in parts:
        if not part:
            continue
        if key_pattern.match(part) or not merged:
            merged.append(part)
        else:
            merged[-1] = f"{merged[-1]}, {part}"
    return merged


def _strip_balanced_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _normalize_key(key: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in key)
    return "_".join(part for part in normalized.split("_") if part)


def _coerce_value(value: str) -> Any:
    stripped = value.strip()
    if re.fullmatch(r"-?\d+", stripped):
        try:
            return int(stripped)
        except ValueError:
            return stripped
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        try:
            return float(stripped)
        except ValueError:
            return stripped
    return stripped


def _contributor_buckets(raw_key_values: dict[str, str]) -> dict[str, dict[str, str]]:
    buckets = {
        "adetailer": {},
        "controlnet": {},
        "lora": {},
        "hires": {},
        "refiner": {},
        "vae": {},
        "forge_or_scheduler": {},
        "other_extensions": {},
    }
    for key, value in raw_key_values.items():
        normalized = _normalize_key(key)
        if normalized.startswith("adetailer") or normalized.startswith("ad_"):
            buckets["adetailer"][key] = value
        elif normalized.startswith("controlnet") or normalized.startswith("control_net"):
            buckets["controlnet"][key] = value
        elif "lora" in normalized:
            buckets["lora"][key] = value
        elif normalized.startswith("hires") or normalized in {"denoising_strength", "upscale_by", "hires_upscaler"}:
            buckets["hires"][key] = value
        elif normalized.startswith("refiner"):
            buckets["refiner"][key] = value
        elif "vae" in normalized:
            buckets["vae"][key] = value
        elif normalized in {"schedule_type", "beta_schedule_alpha", "beta_schedule_beta", "distilled_cfg_scale", "rng", "version"}:
            buckets["forge_or_scheduler"][key] = value
        elif normalized not in _KNOWN_PARAMETER_KEYS:
            buckets["other_extensions"][key] = value
    return {key: value for key, value in buckets.items() if value}


def _unknown_key_values(raw_key_values: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in raw_key_values.items()
        if _normalize_key(key) not in _KNOWN_PARAMETER_KEYS
    }


def _parse_lora_hashes(value: str) -> list[dict[str, str]]:
    items = []
    for part in _split_lora_hash_parts(value):
        if ":" not in part:
            continue
        name, hash_value = part.split(":", 1)
        items.append({"name": name.strip(), "hash": hash_value.strip()})
    return items


def _split_lora_hash_parts(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_controlnet_units(raw_key_values: dict[str, str]) -> list[dict[str, Any]]:
    units = []
    pattern = re.compile(r"^ControlNet\s+(\d+)$", re.IGNORECASE)
    for key, value in raw_key_values.items():
        match = pattern.match(key.strip())
        if not match:
            continue
        unit = {
            "unit": int(match.group(1)),
            "raw": value,
            "parameters": {
                _normalize_key(nested_key): _coerce_value(nested_value)
                for nested_key, nested_value in _parse_key_value_tail(value).items()
            },
            "raw_key_values": _parse_key_value_tail(value),
        }
        module = str(unit["parameters"].get("module", ""))
        model = str(unit["parameters"].get("model", ""))
        unit["appears_to_use_ipadapter"] = "ipadapter" in module.lower() or "ip-adapter" in model.lower()
        units.append(unit)
    return sorted(units, key=lambda item: item["unit"])


_KNOWN_PARAMETER_KEYS = {
    "steps",
    "sampler",
    "schedule_type",
    "cfg_scale",
    "distilled_cfg_scale",
    "seed",
    "size",
    "model",
    "model_hash",
    "rng",
    "version",
    "clip_skip",
    "ensd",
    "vae",
    "vae_hash",
    "lora_hashes",
    "ti_hashes",
    "hashes",
    "beta_schedule_alpha",
    "beta_schedule_beta",
}


_CONTROLNET_NESTED_KEYS = {
    "module",
    "model",
    "weight",
    "resize_mode",
    "processor_res",
    "threshold_a",
    "threshold_b",
    "guidance_start",
    "guidance_end",
    "pixel_perfect",
    "control_mode",
    "hr_option",
    "preprocessor",
    "starting_control_step",
    "ending_control_step",
    "control_weight",
}


def _first_text_value(info: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for value in info.values():
        if isinstance(value, str) and ("Steps:" in value or "Negative prompt:" in value):
            return value
    return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
