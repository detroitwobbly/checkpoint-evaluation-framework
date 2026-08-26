from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from checkpoint_evaluator.comfy import ComfyClient  # noqa: E402
from checkpoint_evaluator.comfy_workflow import ComfyWorkflowFamily  # noqa: E402
from checkpoint_evaluator.provenance import extract_png_provenance  # noqa: E402


RUN_ID = "run_comfy_sdxl_backend_smoke_v0"
RUN_ROOT = REPO_ROOT / "cef_runs" / RUN_ID
BINDINGS = REPO_ROOT / "workflows" / "comfy" / "sdxl_txt2img_bindings.json"
COMMON = {
    "checkpoint": "juggernautXL_ragnarokBy.safetensors",
    "positive_prompt": "A woman wearing a black dress",
    "negative_prompt": "text, watermark",
    "seed": 42,
    "steps": 30,
    "cfg_scale": 7.0,
    "sampler_name": "dpmpp_2m_sde",
    "scheduler": "karras",
    "denoise": 1.0,
    "width": 1024,
    "height": 1024,
    "batch_size": 1,
}
CELLS = [
    {"cell_id": "baseline_seed42", "variant": "base"},
    {
        "cell_id": "near_far_w-1_seed42",
        "variant": "single_lora",
        "lora_name": "Near_Far_v1.safetensors",
        "lora_strength_model": -1.0,
        "lora_strength_clip": -1.0,
    },
    {
        "cell_id": "near_far_w+1_seed42",
        "variant": "single_lora",
        "lora_name": "Near_Far_v1.safetensors",
        "lora_strength_model": 1.0,
        "lora_strength_clip": 1.0,
    },
    {
        "cell_id": "near_far_w+1_seed42_repeat",
        "variant": "single_lora",
        "lora_name": "Near_Far_v1.safetensors",
        "lora_strength_model": 1.0,
        "lora_strength_clip": 1.0,
        "repeat_of": "near_far_w+1_seed42",
    },
]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pixel_sha256(data: bytes) -> tuple[str, dict[str, Any]]:
    with Image.open(io.BytesIO(data)) as image:
        pixels = image.convert("RGBA").tobytes()
        return sha256_bytes(pixels), {"width": image.width, "height": image.height, "mode": image.mode}


def completed(cell_dir: Path) -> bool:
    generation = cell_dir / "generation.json"
    if not generation.exists():
        return False
    record = json.loads(generation.read_text(encoding="utf-8"))
    return record.get("status") == "complete" and all(Path(path).exists() for path in record.get("image_paths", []))


def rebuild_index() -> dict[str, Any]:
    records = []
    for path in sorted((RUN_ROOT / "cells").glob("*/generation.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    index = {
        "artifact_type": "generation_index",
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "updated_at": now(),
        "record_count": len(records),
        "records": records,
    }
    write_json(RUN_ROOT / "generation_index.json", index)
    return index


def verify_completed_run(client: ComfyClient, index: dict[str, Any]) -> dict[str, Any]:
    records_by_id = {record["cell_id"]: record for record in index["records"]}
    cells = []
    all_graph_checks = True
    for specification in CELLS:
        record = records_by_id.get(specification["cell_id"])
        if not record or record.get("status") != "complete":
            continue
        image_path = Path(record["image_paths"][0])
        provenance = extract_png_provenance(image_path)
        write_json(image_path.with_name(f"{image_path.stem}_provenance.json"), provenance)
        graph = provenance.get("comfy", {}).get("api_prompt_graph", {})
        sampler = graph.get("3", {}).get("inputs", {})
        lora = graph.get("10", {}).get("inputs", {})
        expected_weight = specification.get("lora_strength_model")
        graph_checks = {
            "backend_is_comfyui": provenance.get("backend") == "comfyui",
            "prompt_and_workflow_chunks_present": {"prompt", "workflow"}.issubset(provenance["png_text_keys"]),
            "seed_is_42": sampler.get("seed") == 42,
            "sampler_is_dpmpp_2m_sde_karras": sampler.get("sampler_name") == "dpmpp_2m_sde"
            and sampler.get("scheduler") == "karras",
            "lora_weight_matches": (
                not expected_weight
                and not lora
                or lora.get("strength_model") == expected_weight
                and lora.get("strength_clip") == expected_weight
            ),
        }
        all_graph_checks = all_graph_checks and all(graph_checks.values())
        cells.append(
            {
                "cell_id": record["cell_id"],
                "elapsed_seconds": record["elapsed_seconds"],
                "png_sha256": record["images"][0]["png_sha256"],
                "pixel_sha256_rgba": record["images"][0]["pixel_sha256_rgba"],
                "embedded_lora_name": lora.get("lora_name"),
                "embedded_model_weight": lora.get("strength_model"),
                "embedded_clip_weight": lora.get("strength_clip"),
                "checks": graph_checks,
            }
        )
    cells_by_id = {cell["cell_id"]: cell for cell in cells}
    original = cells_by_id.get("near_far_w+1_seed42", {})
    repeat = cells_by_id.get("near_far_w+1_seed42_repeat", {})
    stats = client.system_stats()
    return {
        "artifact_type": "comfy_backend_smoke_verification",
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "verified_at": now(),
        "all_four_cells_complete": len(cells) == 4,
        "all_embedded_graph_checks_pass": all_graph_checks and len(cells) == 4,
        "deterministic_repeat_pixel_equal": bool(original)
        and original.get("pixel_sha256_rgba") == repeat.get("pixel_sha256_rgba"),
        "full_png_expected_to_differ_due_to_output_prefix_metadata": bool(original)
        and original.get("png_sha256") != repeat.get("png_sha256"),
        "post_run_resources": {
            "ram_free_bytes": stats["system"]["ram_free"],
            "vram_free_bytes": stats["devices"][0]["vram_free"],
        },
        "cells": cells,
    }


def manifest() -> dict[str, Any]:
    return {
        "artifact_type": "comfy_backend_smoke_manifest",
        "schema_version": "0.1",
        "run_id": RUN_ID,
        "created_at": now(),
        "purpose": "Verify CEF submission, retrieval, provenance, LoRA polarity, and deterministic repeat through ComfyUI.",
        "bindings_path": str(BINDINGS),
        "common_generation_settings": COMMON,
        "cells": CELLS,
        "execution_policy": "Strictly sequential; resumable per completed cell.",
    }


def run_cell(client: ComfyClient, family: ComfyWorkflowFamily, cell: dict[str, Any]) -> None:
    cell_id = cell["cell_id"]
    cell_dir = RUN_ROOT / "cells" / cell_id
    if completed(cell_dir):
        print(f"SKIP complete {cell_id}", flush=True)
        return

    values = dict(COMMON)
    values.update({key: value for key, value in cell.items() if key.startswith("lora_")})
    values["output_prefix"] = f"CEF/comfy_smoke/{cell_id}"
    resolved = family.resolve(cell["variant"], values)
    request_record = {
        "run_id": RUN_ID,
        "cell_id": cell_id,
        "created_at": now(),
        "variant": cell["variant"],
        "values": values,
        "repeat_of": cell.get("repeat_of"),
        "resolved_api_sha256": resolved.api_sha256,
        "resolved_ui_sha256": resolved.ui_sha256,
    }
    write_json(cell_dir / "cef_request.json", request_record)
    write_json(cell_dir / "resolved_api_workflow.json", resolved.api_workflow)
    write_json(cell_dir / "resolved_ui_workflow.json", resolved.ui_workflow)

    print(f"SUBMIT {cell_id}", flush=True)
    started = time.monotonic()
    try:
        submission = client.submit(resolved)
        write_json(
            cell_dir / "submission.json",
            {"submitted_at": now(), "prompt_id": submission.prompt_id, "response": submission.response},
        )
        print(f"QUEUED {cell_id} prompt_id={submission.prompt_id}", flush=True)
        history = client.wait(submission.prompt_id, deadline_seconds=1200, poll_seconds=1)
        write_json(cell_dir / "history.json", history)
        refs = client.output_images(history, resolved.output_node)
        image_paths = []
        image_records = []
        for index, ref in enumerate(refs, start=1):
            data = client.download_image(ref)
            image_path = cell_dir / f"image_{index:05d}.png"
            image_path.write_bytes(data)
            pixel_hash, image_shape = pixel_sha256(data)
            provenance = extract_png_provenance(image_path)
            write_json(cell_dir / f"image_{index:05d}_provenance.json", provenance)
            image_paths.append(str(image_path))
            image_records.append(
                {
                    "path": str(image_path),
                    "png_sha256": sha256_bytes(data),
                    "pixel_sha256_rgba": pixel_hash,
                    "shape": image_shape,
                    "comfy_output_reference": ref,
                    "png_text_keys": provenance["png_text_keys"],
                }
            )
        record = {
            "run_id": RUN_ID,
            "cell_id": cell_id,
            "status": "complete",
            "completed_at": now(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "prompt_id": submission.prompt_id,
            "variant": cell["variant"],
            "repeat_of": cell.get("repeat_of"),
            "checkpoint": {"name": values["checkpoint"]},
            "lora_profile": {
                "name": values.get("lora_name"),
                "strength_model": values.get("lora_strength_model"),
                "strength_clip": values.get("lora_strength_clip"),
            },
            "test": {"id": cell_id, "prompt": values["positive_prompt"]},
            "settings": values,
            "resolved_graphs": {"api_sha256": resolved.api_sha256, "ui_sha256": resolved.ui_sha256},
            "image_paths": image_paths,
            "images": image_records,
        }
        write_json(cell_dir / "generation.json", record)
        rebuild_index()
        print(f"COMPLETE {cell_id} elapsed={record['elapsed_seconds']}s pixel_sha256={image_records[0]['pixel_sha256_rgba']}", flush=True)
    except Exception as exc:
        write_json(
            cell_dir / "error.json",
            {"failed_at": now(), "cell_id": cell_id, "error_type": type(exc).__name__, "error": str(exc)},
        )
        rebuild_index()
        print(f"FAILED {cell_id}: {type(exc).__name__}: {exc}", flush=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the resumable CEF ComfyUI four-cell smoke gate.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--max-new-cells", type=int, default=1)
    args = parser.parse_args()

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    if not (RUN_ROOT / "run_manifest.json").exists():
        write_json(RUN_ROOT / "run_manifest.json", manifest())
    family = ComfyWorkflowFamily.load(BINDINGS)
    client = ComfyClient(args.base_url)
    write_json(RUN_ROOT / "comfy_system_stats_latest.json", client.system_stats())

    run_count = 0
    for cell in CELLS:
        cell_dir = RUN_ROOT / "cells" / cell["cell_id"]
        if completed(cell_dir):
            continue
        if run_count >= args.max_new_cells:
            break
        run_cell(client, family, cell)
        run_count += 1
    index = rebuild_index()
    verification = verify_completed_run(client, index)
    write_json(RUN_ROOT / "smoke_verification.json", verification)
    print(f"RUN_ROOT {RUN_ROOT}", flush=True)
    print(f"INDEX_RECORDS {index['record_count']}", flush=True)
    if verification["all_four_cells_complete"]:
        print(
            "VERIFIED "
            f"graphs={verification['all_embedded_graph_checks_pass']} "
            f"deterministic_pixels={verification['deterministic_repeat_pixel_equal']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
