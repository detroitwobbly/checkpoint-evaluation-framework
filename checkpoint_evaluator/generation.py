from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .forge import ForgeClient
from .models import CheckpointProfile, GenerationSettings, LoraProfile, TestCase, TestSuite


def run_generation_suite(
    suite: TestSuite,
    output_root: Path,
    forge: ForgeClient,
    run_id: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
    overwrite: bool = False,
) -> Path:
    if resume and overwrite:
        raise ValueError("resume and overwrite are mutually exclusive")
    run_id = run_id or f"run_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}_{suite.suite_id}"
    run_root = output_root / run_id
    suite_snapshot = suite.to_dict()
    _validate_run_reuse(run_root, suite_snapshot, resume=resume, overwrite=overwrite)
    run_root.mkdir(parents=True, exist_ok=True)
    # Analysis reads this run-local snapshot, so later manifest edits do not silently change an existing run.
    _write_json(run_root / "run_manifest.json", suite_snapshot)

    api_inventory = (
        {"dry_run": True, "version": {}, "options": {}, "models": [], "loras": []}
        if dry_run
        else {
            "version": forge.version(),
            "options": forge.options(),
            "models": forge.models(),
            "loras": _slim_loras(forge.loras()),
        }
    )
    inventory_path = run_root / "forge_inventory.json"
    if resume and inventory_path.exists():
        inventory_path = run_root / f"forge_inventory_resume_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    _write_json(inventory_path, api_inventory)

    records: list[dict[str, Any]] = []
    planned = len(suite.checkpoints) * len(suite.lora_profiles) * len(suite.tests)
    skipped = 0
    _write_run_state(run_root, "running", planned, records, skipped)
    approved_root = run_root / "approved"
    for checkpoint in suite.checkpoints:
        checkpoint_options = forge.set_checkpoint(checkpoint.title) if not dry_run else {}
        for lora_profile in suite.lora_profiles:
            for test in suite.tests:
                settings = suite.defaults.merged(test.settings)
                request_payload = _request_payload(test, settings, lora_profile)
                test_root = approved_root / f"checkpoint_{checkpoint.id}" / f"lora_{lora_profile.id}" / test.id
                test_root.mkdir(parents=True, exist_ok=True)
                _write_json(test_root / "request.json", request_payload)
                _write_json(test_root / "criteria.json", [criterion.to_dict() for criterion in test.criteria])
                if resume and not dry_run:
                    completed = _completed_record(
                        checkpoint,
                        lora_profile,
                        test,
                        test_root,
                        settings,
                        inventory_models=api_inventory["models"],
                    )
                    if completed is not None:
                        records.append(completed)
                        skipped += 1
                        _write_generation_index(run_root, run_id, records)
                        _write_run_state(run_root, "running", planned, records, skipped)
                        continue
                if dry_run:
                    records.append(
                        _record(
                            checkpoint,
                            lora_profile,
                            test,
                            test_root,
                            settings,
                            [],
                            checkpoint_options,
                            inventory_models=api_inventory["models"],
                            dry_run=True,
                        )
                    )
                    _write_generation_index(run_root, run_id, records)
                    _write_run_state(run_root, "running", planned, records, skipped)
                    continue

                generation = forge.txt2img(request_payload)
                image_paths = []
                for index, image_bytes in enumerate(generation.images, start=1):
                    image_path = test_root / _image_name(checkpoint, test, settings, index)
                    image_path.write_bytes(image_bytes)
                    image_paths.append(str(image_path))
                generation_metadata = {
                    "checkpoint": checkpoint.to_dict(),
                    "lora_profile": lora_profile.to_dict(),
                    "test": test.to_dict(),
                    "settings": settings.to_dict(),
                    "request": request_payload,
                    "checkpoint_options_after_switch": checkpoint_options,
                    "forge_info": generation.info,
                    "forge_response": generation.response_metadata,
                    "image_paths": image_paths,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                }
                _write_json(test_root / "generation.json", generation_metadata)
                records.append(
                    _record(
                        checkpoint,
                        lora_profile,
                        test,
                        test_root,
                        settings,
                        image_paths,
                        checkpoint_options,
                        generation_info=generation.info,
                        inventory_models=api_inventory["models"],
                    )
                )
                _write_generation_index(run_root, run_id, records)
                _write_run_state(run_root, "running", planned, records, skipped)

    _write_generation_index(run_root, run_id, records)
    _write_run_state(run_root, "complete", planned, records, skipped)
    return run_root


def _validate_run_reuse(
    run_root: Path,
    suite_snapshot: dict[str, Any],
    *,
    resume: bool,
    overwrite: bool,
) -> None:
    if not run_root.exists() or not any(run_root.iterdir()):
        return
    if not resume and not overwrite:
        raise FileExistsError(
            f"Run directory is not empty: {run_root}. Use --resume to keep completed cells, "
            "--overwrite to regenerate the same manifest, or choose a new --run-id."
        )
    manifest_path = run_root / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Cannot safely reuse a run without its manifest snapshot: {manifest_path}"
        )
    existing = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if existing != suite_snapshot:
        raise ValueError(
            "The supplied manifest differs from the run-local manifest snapshot. "
            "Choose a new run ID; CEF will not mix experimental manifolds in one run."
        )


def _completed_record(
    checkpoint: CheckpointProfile,
    lora_profile: LoraProfile,
    test: TestCase,
    test_root: Path,
    settings: GenerationSettings,
    *,
    inventory_models: list[dict[str, Any]],
) -> dict[str, Any] | None:
    generation_path = test_root / "generation.json"
    if not generation_path.exists():
        return None
    try:
        metadata = json.loads(generation_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    image_paths: list[str] = []
    for value in metadata.get("image_paths", []):
        recorded = Path(str(value))
        candidate = recorded if recorded.is_file() else test_root / recorded.name
        if not candidate.is_file():
            return None
        image_paths.append(str(candidate))
    if not image_paths:
        return None
    return _record(
        checkpoint,
        lora_profile,
        test,
        test_root,
        settings,
        image_paths,
        metadata.get("checkpoint_options_after_switch", {}),
        generation_info=metadata.get("forge_info", {}),
        inventory_models=inventory_models,
    )


def _write_generation_index(run_root: Path, run_id: str, records: list[dict[str, Any]]) -> None:
    _write_json(run_root / "generation_index.json", {"run_id": run_id, "records": records})


def _write_run_state(
    run_root: Path,
    status: str,
    planned: int,
    records: list[dict[str, Any]],
    skipped: int,
) -> None:
    _write_json(
        run_root / "run_state.json",
        {
            "status": status,
            "planned_cells": planned,
            "completed_cells": len(records),
            "pending_cells": max(planned - len(records), 0),
            "resumed_cells": skipped,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def _request_payload(test: TestCase, settings: GenerationSettings, lora_profile: LoraProfile) -> dict[str, Any]:
    prompt = test.prompt
    prompt_overrides = test.metadata.get("lora_prompt_overrides") if isinstance(test.metadata, dict) else None
    if isinstance(prompt_overrides, dict) and lora_profile.id in prompt_overrides:
        prompt = str(prompt_overrides[lora_profile.id])
    prompt_parts = [prompt.strip()]
    lora_suffix = lora_profile.prompt_suffix()
    if lora_suffix:
        prompt_parts.append(lora_suffix)
    payload = {
        "prompt": " ".join(part for part in prompt_parts if part),
        "negative_prompt": settings.negative_prompt,
        "steps": settings.steps,
        "cfg_scale": settings.cfg_scale,
        "width": settings.width,
        "height": settings.height,
        "sampler_name": settings.sampler_name,
        "seed": settings.seed,
        "batch_size": settings.batch_size,
        "n_iter": settings.n_iter,
        "save_images": False,
    }
    if settings.scheduler:
        payload["scheduler"] = settings.scheduler
    return payload


def _record(
    checkpoint: CheckpointProfile,
    lora_profile: LoraProfile,
    test: TestCase,
    test_root: Path,
    settings: GenerationSettings,
    image_paths: list[str],
    checkpoint_options: dict[str, Any],
    generation_info: dict[str, Any] | None = None,
    inventory_models: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    generation_info = generation_info or {}
    checkpoint_hash = _resolve_checkpoint_hash(
        generation_info.get("sd_model_hash"),
        inventory_models or [],
        checkpoint_options.get("sd_checkpoint_hash"),
    )
    return {
        "checkpoint_id": checkpoint.id,
        "checkpoint_title": checkpoint.title,
        "lora_profile_id": lora_profile.id,
        "test_id": test.id,
        "test_name": test.name,
        "test_root": str(test_root),
        "settings": settings.to_dict(),
        "image_paths": image_paths,
        "checkpoint_hash": checkpoint_hash,
        "forge_model_hash": generation_info.get("sd_model_hash"),
        "forge_model_name": generation_info.get("sd_model_name"),
        "dry_run": dry_run,
    }


def _resolve_checkpoint_hash(
    generated_hash: Any,
    inventory_models: list[dict[str, Any]],
    options_hash: Any,
) -> str | None:
    """Prefer the model identity emitted by txt2img over post-switch options.

    Forge Neo can update ``sd_model_checkpoint`` before ``sd_checkpoint_hash``.
    The generation response is authoritative for which model produced the image;
    match its short hash back to the inventory to preserve the full SHA-256.
    """
    generated = str(generated_hash or "").strip().lower()
    if generated:
        for model in inventory_models:
            sha256 = str(model.get("sha256") or "").strip().lower()
            short_hash = str(model.get("hash") or "").strip().lower()
            if generated in {short_hash, sha256} or (sha256 and sha256.startswith(generated)):
                return sha256 or short_hash
        return generated
    value = str(options_hash or "").strip()
    return value or None


def _slim_loras(loras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep Forge LoRA inventory useful without archiving huge metadata blobs.

    Forge/Forge-Neo may include embedded thumbnails and full training metadata
    in ``/sdapi/v1/loras``. For run provenance we need identity/discovery
    fields, not multi-megabyte base64 payloads repeated in every suite.
    """
    slim: list[dict[str, Any]] = []
    for item in loras:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        slim.append(
            {
                "name": item.get("name"),
                "alias": item.get("alias"),
                "path": item.get("path"),
                "hashes": {
                    key: metadata.get(key)
                    for key in (
                        "modelspec.hash_sha256",
                        "sshs_model_hash",
                        "sshs_legacy_hash",
                    )
                    if metadata.get(key)
                },
            }
        )
    return slim


def _image_name(checkpoint: CheckpointProfile, test: TestCase, settings: GenerationSettings, index: int) -> str:
    checkpoint_id = _safe_filename(checkpoint.id)
    test_id = _safe_filename(test.id)
    suffix = f"_{index:04d}" if settings.batch_size * settings.n_iter > 1 else ""
    return f"{checkpoint_id}_{test_id}_seed{settings.seed}_cfg{settings.cfg_scale:g}_steps{settings.steps}{suffix}.png"


def _safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return safe.strip("_") or "item"


def _write_json(path: Path, data: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
