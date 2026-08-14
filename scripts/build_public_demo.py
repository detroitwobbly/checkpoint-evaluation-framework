from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from checkpoint_evaluator.reporting import build_contact_sheet, build_html_report


CEF_PNG_KEYS = (
    "cef_schema_version",
    "cef_publication_profile",
    "cef_run_id",
    "cef_cell_id",
    "cef_checkpoint_id",
    "cef_test_id",
    "cef_manifest_sha256",
    "cef_evidence_sha256",
    "cef_original_png_sha256",
)


def build_public_demo(run_root: Path, output_root: Path) -> dict[str, Any]:
    run_root = run_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Public-demo output is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = run_root / "run_manifest.json"
    generation_index_path = run_root / "generation_index.json"
    analysis_index_path = run_root / "analysis_index.json"
    report_path = run_root / "report.json"
    adjudication_path = run_root / "human_adjudication.json"
    required = (manifest_path, generation_index_path, analysis_index_path, report_path, adjudication_path)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing approved run artifacts: {', '.join(missing)}")

    manifest = _read_json(manifest_path)
    generation_index = _read_json(generation_index_path)
    analysis_index = _read_json(analysis_index_path)
    report = _read_json(report_path)
    adjudication = _read_json(adjudication_path)
    if adjudication.get("status") != "approved":
        raise ValueError("Public export requires an approved human_adjudication.json artifact.")

    run_id = str(report.get("run_id") or analysis_index.get("run_id") or run_root.name)
    manifest_sha256 = _sha256(manifest_path)
    public_manifest = _public_manifest(manifest)
    _write_json(output_root / "manifest.json", public_manifest)

    generation_by_key = {
        (str(record.get("checkpoint_id")), str(record.get("test_id"))): record
        for record in generation_index.get("records", [])
        if isinstance(record, dict)
    }
    human_by_key = {
        (str(record.get("checkpoint_id")), str(record.get("test_id"))): record
        for record in adjudication.get("records", [])
        if isinstance(record, dict)
    }
    display_by_id = {
        str(item.get("id")): str(item.get("display_name"))
        for item in manifest.get("metadata", {}).get("checkpoint_provenance", [])
        if isinstance(item, dict) and item.get("id") and item.get("display_name")
    }

    public_report = copy.deepcopy(report)
    public_report.get("evaluator", {}).pop("endpoint", None)
    public_records = []
    artifacts = []
    image_root = output_root / "assets" / "images"
    evidence_root = output_root / "evidence"
    image_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    for machine_record in analysis_index.get("records", []):
        if not isinstance(machine_record, dict):
            continue
        checkpoint_id = str(machine_record.get("checkpoint_id") or "")
        test_id = str(machine_record.get("test_id") or "")
        key = (checkpoint_id, test_id)
        generation_record = generation_by_key.get(key, {})
        human_record = human_by_key.get(key, {})
        source_image = _resolve_image(machine_record.get("image_path"), run_root)
        cell_id = _safe_name(f"{checkpoint_id}__{machine_record.get('lora_profile_id', 'none')}__{test_id}")
        public_image = image_root / f"{cell_id}.png"
        evidence_path = evidence_root / f"{cell_id}.json"
        request_path = source_image.parent / "request.json"
        generation_path = source_image.parent / "generation.json"

        evidence = {
            "artifact_type": "cef_public_image_evidence",
            "schema_version": "1.0",
            "publication_profile": "sanitized-v1",
            "run_id": run_id,
            "cell_id": cell_id,
            "checkpoint": {
                "id": checkpoint_id,
                "display_name": display_by_id.get(checkpoint_id, checkpoint_id),
                "sha256": generation_record.get("checkpoint_hash"),
            },
            "test": {
                "id": test_id,
                "name": machine_record.get("test_name"),
            },
            "generation": {
                "settings": generation_record.get("settings", {}),
                "request": _read_json(request_path) if request_path.exists() else {},
                "forge_model_hash": generation_record.get("forge_model_hash"),
            },
            "machine_evaluation": _public_machine_record(machine_record),
            "human_adjudication": _public_human_record(human_record),
            "private_artifact_anchors": {
                "original_png_sha256": _sha256(source_image),
                "run_manifest_sha256": manifest_sha256,
                "request_json_sha256": _sha256(request_path) if request_path.exists() else None,
                "generation_json_sha256": _sha256(generation_path) if generation_path.exists() else None,
            },
        }
        _write_json(evidence_path, evidence)
        evidence_sha256 = _sha256(evidence_path)
        envelope = {
            "cef_schema_version": "1",
            "cef_publication_profile": "sanitized-v1",
            "cef_run_id": run_id,
            "cef_cell_id": cell_id,
            "cef_checkpoint_id": checkpoint_id,
            "cef_test_id": test_id,
            "cef_manifest_sha256": manifest_sha256,
            "cef_evidence_sha256": evidence_sha256,
            "cef_original_png_sha256": _sha256(source_image),
        }
        _write_sanitized_png(source_image, public_image, envelope)
        public_image_sha256 = _sha256(public_image)
        artifacts.append(
            {
                "cell_id": cell_id,
                "image": public_image.relative_to(output_root).as_posix(),
                "image_sha256": public_image_sha256,
                "evidence": evidence_path.relative_to(output_root).as_posix(),
                "evidence_sha256": evidence_sha256,
                "original_png_sha256": _sha256(source_image),
                "embedded_png_keys": list(CEF_PNG_KEYS),
                "pixel_equivalent": True,
                "transformation": {
                    "decode": "lossless",
                    "encode": "lossless PNG re-encode",
                    "source_metadata_removed": True,
                    "cef_envelope_added": True,
                    "pixel_content_modified": False,
                    "container_bytes_modified": True,
                },
            }
        )

        display_record = copy.deepcopy(machine_record)
        display_record["checkpoint_title"] = display_by_id.get(checkpoint_id, checkpoint_id)
        display_record["image_path"] = str(public_image)
        display_record["analysis_path"] = str(evidence_path)
        public_records.append(display_record)

    public_report["records"] = public_records
    public_report["generated_images"] = len(public_records)
    public_report["analyzed_images"] = len(public_records)
    public_report["publication_profile"] = "sanitized-v1"
    contact_sheet = build_contact_sheet(public_report, output_root)
    if contact_sheet:
        public_report["contact_sheet"] = contact_sheet.relative_to(output_root).as_posix()
    html = build_html_report(public_report, output_root)
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    (output_root / "index.html").write_text(html, encoding="utf-8")

    json_report = copy.deepcopy(public_report)
    for record in json_report.get("records", []):
        record["image_path"] = Path(str(record["image_path"])).relative_to(output_root).as_posix()
        record["analysis_path"] = Path(str(record["analysis_path"])).relative_to(output_root).as_posix()
    _write_json(output_root / "report.json", json_report)
    index = {
        "artifact_type": "cef_public_artifact_index",
        "schema_version": "1.0",
        "publication_profile": "sanitized-v1",
        "run_id": run_id,
        "source_manifest_sha256": manifest_sha256,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "sanitization_assertions": [
            "Public PNGs contain only the declared CEF text envelope.",
            "Raw Forge/A1111 PNG metadata is not included.",
            "Pixel values match the corresponding private original.",
            "Private original PNGs are not modified.",
        ],
    }
    _write_json(output_root / "artifact_index.json", index)
    shutil.copy2(Path(__file__).resolve().parents[1] / "LICENSE", output_root / "LICENSE")
    (output_root / ".nojekyll").write_text("", encoding="utf-8")
    return index


def _write_sanitized_png(source: Path, destination: Path, envelope: dict[str, str]) -> None:
    from PIL import Image, ImageChops, PngImagePlugin

    if set(envelope) != set(CEF_PNG_KEYS):
        raise ValueError("CEF PNG envelope keys do not match the declared schema.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        original.load()
        clean = original.copy()
        pnginfo = PngImagePlugin.PngInfo()
        for key in CEF_PNG_KEYS:
            pnginfo.add_text(key, str(envelope[key]))
        clean.save(destination, format="PNG", pnginfo=pnginfo, optimize=False)
        original_pixels = original.convert("RGBA")
    with Image.open(destination) as published:
        published.load()
        if set(published.info) != set(CEF_PNG_KEYS):
            raise ValueError(f"Unexpected public PNG metadata keys: {sorted(published.info)}")
        if ImageChops.difference(original_pixels, published.convert("RGBA")).getbbox() is not None:
            raise ValueError(f"Pixel mismatch after sanitized PNG export: {source}")


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    provenance = manifest.get("metadata", {}).get("checkpoint_provenance", [])
    metadata = copy.deepcopy(manifest.get("metadata", {}))
    metadata["notes"] = (
        "Human adjudication approved on 2026-08-14. Public images and evidence use the sanitized-v1 publication profile."
    )
    provenance_by_id = {
        str(item.get("id")): item for item in provenance if isinstance(item, dict) and item.get("id")
    }
    return {
        "suite_id": manifest.get("suite_id"),
        "name": manifest.get("name"),
        "metadata": metadata,
        "checkpoints": [
            {
                "id": checkpoint.get("id"),
                "display_name": provenance_by_id.get(str(checkpoint.get("id")), {}).get("display_name"),
                "sha256": provenance_by_id.get(str(checkpoint.get("id")), {}).get("sha256"),
            }
            for checkpoint in manifest.get("checkpoints", [])
            if isinstance(checkpoint, dict)
        ],
        "lora_profiles": [{"id": item.get("id"), "loras": []} for item in manifest.get("lora_profiles", [])],
        "defaults": manifest.get("defaults", {}),
        "tests": manifest.get("tests", []),
    }


def _public_machine_record(record: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "overall_score",
        "pass_fail",
        "evaluator_confidence",
        "criteria_scores",
        "rubric_scores",
        "visual_summary",
        "prompt_adherence",
        "intent_failure_check",
        "failures",
        "warnings",
        "wildcard_observations",
        "semantic_observations",
    )
    return {key: record.get(key) for key in allowed if key in record}


def _public_human_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    return {
        "outcome": record.get("human_outcome") or record.get("draft_outcome"),
        "machine_outcome": record.get("machine_outcome"),
        "agreement": record.get("agreement"),
        "observation": record.get("observation"),
        "safety_or_rights_flags": record.get("safety_or_rights_flags", []),
    }


def _resolve_image(value: Any, run_root: Path) -> Path:
    candidate = Path(str(value))
    options = [candidate]
    if not candidate.is_absolute():
        options.extend((Path.cwd() / candidate, run_root / candidate, run_root / candidate.name))
    for option in options:
        if option.is_file():
            return option.resolve()
    raise FileNotFoundError(f"Could not resolve generated image: {value}")


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return loaded


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a self-contained sanitized CEF public-demo candidate.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    index = build_public_demo(args.run_root, args.output_root)
    print(json.dumps({"output_root": str(args.output_root), "artifacts": index["artifact_count"]}, indent=2))


if __name__ == "__main__":
    main()
