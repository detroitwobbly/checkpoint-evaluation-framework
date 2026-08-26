from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from checkpoint_evaluator.backend import ComfyBackend, ForgeBackend, GenerationBackend, GenerationPending
from checkpoint_evaluator.generation import (
    _image_name,
    _record,
    _request_payload,
    _write_json,
)
from checkpoint_evaluator.manifest import load_suite
from checkpoint_evaluator.models import CheckpointProfile, GenerationSettings, LoraProfile, TestCase, TestSuite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a CEF generation manifest with resumable per-case checkpoints."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-root", default=Path("cef_runs"), type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--backend", choices=("forge", "comfy"), default="forge")
    parser.add_argument("--base-url", help="Backend URL; defaults to :7860 for Forge and :8188 for ComfyUI.")
    parser.add_argument("--comfy-bindings", type=Path, help="Optional Comfy UI/API workflow binding manifest.")
    parser.add_argument("--timeout", default=300, type=int)
    parser.add_argument("--resume", action="store_true", help="Skip completed cases with valid generation.json/images.")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate even completed cases.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-lora", action="append", help="Run only matching lora profile id. Repeatable.")
    parser.add_argument("--only-test", action="append", help="Run only matching test id. Repeatable.")
    parser.add_argument("--start-after-test", help="Skip until after this test id has been passed.")
    parser.add_argument("--stop-after", type=int, help="Stop after N generated/skipped cases for canaries.")
    parser.add_argument(
        "--pause-after-submit",
        action="store_true",
        help="Comfy recovery test: persist one prompt_id, then stop before waiting/retrieval.",
    )
    parser.add_argument("--release-resources", action="store_true", help="Release backend models/memory after a completed run.")
    args = parser.parse_args()

    if args.resume and args.overwrite:
        raise SystemExit("--resume and --overwrite are mutually hostile little goblins; choose one.")

    suite = load_suite(args.manifest)
    run_root = (args.output_root / args.run_id).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    _write_json_once_or_snapshot(run_root / "run_manifest.json", suite.to_dict(), args.overwrite)

    base_url = args.base_url or ("http://127.0.0.1:8188" if args.backend == "comfy" else "http://127.0.0.1:7860")
    backend: GenerationBackend
    if args.backend == "comfy":
        backend = ComfyBackend(base_url, timeout=args.timeout, bindings_path=args.comfy_bindings)
    else:
        backend = ForgeBackend(base_url, timeout=args.timeout)

    session = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": str(args.manifest),
        "run_id": args.run_id,
        "resume": args.resume,
        "overwrite": args.overwrite,
        "dry_run": args.dry_run,
        "only_lora": args.only_lora or [],
        "only_test": args.only_test or [],
        "start_after_test": args.start_after_test,
        "stop_after": args.stop_after,
        "backend": args.backend,
        "base_url": base_url,
        "comfy_bindings": str(args.comfy_bindings) if args.comfy_bindings else None,
        "pause_after_submit": args.pause_after_submit,
        "release_resources": args.release_resources,
    }
    _append_jsonl(run_root / "generation_sessions.jsonl", session)

    inventory = backend.inventory(args.dry_run)
    inventory_name = f"{args.backend}_inventory.json"
    _write_json_once_or_snapshot(run_root / inventory_name, inventory, args.overwrite)
    _write_json(run_root / f"{args.backend}_inventory_latest.json", inventory)
    _write_json(run_root / "backend_inventory_latest.json", inventory)

    existing_records = _load_generation_records(run_root / "generation_index.json")
    record_map = {_record_key(record): record for record in existing_records}

    counters = {
        "completed": 0,
        "skipped_completed": 0,
        "pending": 0,
        "failed": 0,
        "dry_run": 0,
        "filtered": 0,
    }
    processed = 0
    passed_start_after = args.start_after_test is None

    only_lora = set(args.only_lora or [])
    only_test = set(args.only_test or [])

    for checkpoint in suite.checkpoints:
        checkpoint_options = backend.prepare_checkpoint(checkpoint, args.dry_run)
        for lora_profile in suite.lora_profiles:
            if only_lora and lora_profile.id not in only_lora:
                counters["filtered"] += len(suite.tests)
                continue
            for test in suite.tests:
                allowed_loras = test.metadata.get("allowed_lora_profile_ids") or test.metadata.get("allowed_lora_profile_id")
                if isinstance(allowed_loras, str):
                    allowed_loras = [allowed_loras]
                if allowed_loras and lora_profile.id not in set(allowed_loras):
                    counters["filtered"] += 1
                    continue
                if args.start_after_test and not passed_start_after:
                    if test.id == args.start_after_test:
                        passed_start_after = True
                    counters["filtered"] += 1
                    continue
                if only_test and test.id not in only_test:
                    counters["filtered"] += 1
                    continue
                if args.stop_after is not None and processed >= args.stop_after:
                    return _finish(run_root, record_map, counters, stopped_early=True)

                processed += 1
                status = _run_case(
                    run_root=run_root,
                    suite=suite,
                    checkpoint=checkpoint,
                    lora_profile=lora_profile,
                    test=test,
                    checkpoint_options=checkpoint_options,
                    inventory=inventory,
                    backend=backend,
                    record_map=record_map,
                    dry_run=args.dry_run,
                    resume=args.resume,
                    overwrite=args.overwrite,
                    pause_after_submit=args.pause_after_submit,
                )
                counters[status] += 1
                _write_generation_index(run_root / "generation_index.json", args.run_id, record_map)
                if status == "pending":
                    return _finish(run_root, record_map, counters, stopped_early=True)

    if args.release_resources and not args.dry_run:
        _write_json_atomic(run_root / "backend_resource_release.json", backend.release_resources())
    return _finish(run_root, record_map, counters, stopped_early=False)


def _run_case(
    run_root: Path,
    suite: TestSuite,
    checkpoint: CheckpointProfile,
    lora_profile: LoraProfile,
    test: TestCase,
    checkpoint_options: dict[str, Any],
    inventory: dict[str, Any],
    backend: GenerationBackend,
    record_map: dict[tuple[str, str, str], dict[str, Any]],
    dry_run: bool,
    resume: bool,
    overwrite: bool,
    pause_after_submit: bool,
) -> str:
    settings = suite.defaults.merged(test.settings)
    request_payload = _request_payload(
        test,
        settings,
        lora_profile,
        include_lora_tokens=backend.prompt_lora_tokens,
    )
    test_root = (
        run_root
        / "approved"
        / f"checkpoint_{checkpoint.id}"
        / f"lora_{lora_profile.id}"
        / test.id
    )
    test_root.mkdir(parents=True, exist_ok=True)

    key = (checkpoint.id, lora_profile.id, test.id)
    complete = _case_complete(test_root)
    if resume and complete and not overwrite:
        existing = _load_existing_record(test_root, checkpoint, lora_profile, test, settings, checkpoint_options, inventory)
        record_map[key] = existing
        return "skipped_completed"

    _write_json(test_root / "request.json", request_payload)
    _write_json(test_root / "criteria.json", [criterion.to_dict() for criterion in test.criteria])

    if dry_run:
        record_map[key] = _record(
            checkpoint,
            lora_profile,
            test,
            test_root,
            settings,
            [],
            checkpoint_options,
            inventory_models=inventory["models"],
            dry_run=True,
        )
        record_map[key]["backend_id"] = backend.backend_id
        return "dry_run"

    try:
        generation = backend.generate(
            request_payload,
            checkpoint,
            lora_profile,
            test_root,
            resume_pending=resume,
            pause_after_submit=pause_after_submit,
        )
        image_paths: list[str] = []
        for index, image_bytes in enumerate(generation.images, start=1):
            image_path = test_root / _image_name(checkpoint, test, settings, index)
            _write_bytes_atomic(image_path, image_bytes)
            image_paths.append(str(image_path))

        generation_metadata = {
            "checkpoint": checkpoint.to_dict(),
            "lora_profile": lora_profile.to_dict(),
            "test": test.to_dict(),
            "settings": settings.to_dict(),
            "request": request_payload,
            "checkpoint_options_after_switch": checkpoint_options,
            "backend_id": backend.backend_id,
            "backend_info": generation.info,
            "backend_response": generation.response_metadata,
            "backend_artifacts": generation.artifacts,
            "forge_info": generation.info if backend.backend_id == "forge" else {},
            "forge_response": generation.response_metadata if backend.backend_id == "forge" else {},
            "image_paths": image_paths,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "resumable_runner": True,
        }
        _write_json_atomic(test_root / "generation.json", generation_metadata)
        record = _record(
            checkpoint,
            lora_profile,
            test,
            test_root,
            settings,
            image_paths,
            checkpoint_options,
            generation_info=generation.info,
            inventory_models=inventory["models"],
        )
        record["backend_id"] = backend.backend_id
        record_map[key] = record
        _clear_failure_marker(test_root)
        return "completed"
    except GenerationPending as pending:
        _write_json_atomic(
            test_root / "generation_pending.json",
            {
                "backend_id": backend.backend_id,
                "prompt_id": pending.prompt_id,
                "checkpoint_id": checkpoint.id,
                "lora_profile_id": lora_profile.id,
                "test_id": test.id,
                "test_root": str(test_root),
            },
        )
        return "pending"
    except Exception as exc:  # noqa: BLE001 - failure records are a feature here
        failure = {
            "failed_at": datetime.now().isoformat(timespec="seconds"),
            "checkpoint_id": checkpoint.id,
            "lora_profile_id": lora_profile.id,
            "test_id": test.id,
            "test_root": str(test_root),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _write_json(test_root / "generation_failure.json", failure)
        _append_jsonl(run_root / "generation_failures.jsonl", failure)
        return "failed"


def _case_complete(test_root: Path) -> bool:
    generation_path = test_root / "generation.json"
    if not generation_path.exists():
        return False
    try:
        generation = json.loads(generation_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return False
    image_paths = generation.get("image_paths") or []
    if not image_paths:
        return False
    return all(Path(path).exists() and Path(path).stat().st_size > 0 for path in image_paths)


def _load_existing_record(
    test_root: Path,
    checkpoint: CheckpointProfile,
    lora_profile: LoraProfile,
    test: TestCase,
    settings: GenerationSettings,
    checkpoint_options: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    generation = json.loads((test_root / "generation.json").read_text(encoding="utf-8-sig"))
    record = _record(
        checkpoint,
        lora_profile,
        test,
        test_root,
        settings,
        generation.get("image_paths") or [],
        checkpoint_options,
        generation_info=generation.get("forge_info") or generation.get("backend_info") or {},
        inventory_models=inventory["models"],
    )
    record["backend_id"] = generation.get("backend_id", inventory.get("backend_id", "forge"))
    return record


def _load_generation_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    return list(data.get("records", []))


def _record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("checkpoint_id")), str(record.get("lora_profile_id")), str(record.get("test_id")))


def _write_generation_index(path: Path, run_id: str, record_map: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    records = sorted(
        record_map.values(),
        key=lambda record: (
            str(record.get("checkpoint_id")),
            str(record.get("lora_profile_id")),
            str(record.get("test_id")),
        ),
    )
    _write_json_atomic(path, {"run_id": run_id, "records": records})


def _write_json_once_or_snapshot(path: Path, data: Any, overwrite: bool) -> None:
    if overwrite or not path.exists():
        _write_json_atomic(path, data)
        return
    latest = path.with_name(f"{path.stem}_latest{path.suffix}")
    _write_json_atomic(latest, data)


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, sort_keys=True))
        handle.write("\n")


def _clear_failure_marker(test_root: Path) -> None:
    for name in ("generation_failure.json", "generation_pending.json"):
        marker = test_root / name
        if marker.exists():
            marker.unlink()


def _finish(
    run_root: Path,
    record_map: dict[tuple[str, str, str], dict[str, Any]],
    counters: dict[str, int],
    stopped_early: bool,
) -> int:
    summary = {
        "run_root": str(run_root),
        "records": len(record_map),
        "counters": counters,
        "stopped_early": stopped_early,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json_atomic(run_root / "generation_resumable_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if counters.get("failed", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
