import hashlib
import json
from pathlib import Path

from PIL import Image, PngImagePlugin

from scripts.build_public_demo import CEF_PNG_KEYS, build_public_demo


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_public_demo_export_strips_raw_metadata_and_adds_cef_envelope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_root = tmp_path / "runs" / "demo"
    cell_root = run_root / "approved" / "checkpoint_a" / "lora_none" / "TEST"
    cell_root.mkdir(parents=True)
    image_path = cell_root / "source.png"
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("parameters", "private prompt and Forge parameters")
    pnginfo.add_text("private_extension_field", "must not publish")
    Image.new("RGB", (16, 16), color=(20, 40, 60)).save(image_path, pnginfo=pnginfo)
    original_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    _write_json(cell_root / "request.json", {"prompt": "public test prompt", "seed": 7})
    _write_json(cell_root / "generation.json", {"image_paths": [str(image_path)]})
    _write_json(
        run_root / "run_manifest.json",
        {
            "suite_id": "DEMO",
            "name": "Demo",
            "metadata": {
                "checkpoint_provenance": [
                    {"id": "a", "display_name": "Checkpoint A", "sha256": "abc", "source": "https://example.com"}
                ]
            },
            "checkpoints": [{"id": "a", "title": "private/path/model.safetensors"}],
            "lora_profiles": [{"id": "none", "loras": []}],
            "defaults": {"seed": 7},
            "tests": [{"id": "TEST", "name": "Test", "prompt": "public test prompt"}],
        },
    )
    generation_record = {
        "checkpoint_id": "a",
        "test_id": "TEST",
        "settings": {"seed": 7},
        "image_paths": [str(image_path)],
        "checkpoint_hash": "abc",
        "forge_model_hash": "abc",
        "forge_model_name": "model",
    }
    _write_json(run_root / "generation_index.json", {"run_id": "demo", "records": [generation_record]})
    analysis_record = {
        "checkpoint_id": "a",
        "lora_profile_id": "none",
        "test_id": "TEST",
        "test_name": "Test",
        "image_path": str(image_path),
        "analysis_path": str(cell_root / "analysis.json"),
        "overall_score": 8,
        "pass_fail": "pass",
        "criteria_scores": [],
    }
    _write_json(run_root / "analysis_index.json", {"run_id": "demo", "records": [analysis_record]})
    human_record = {
        "checkpoint_id": "a",
        "test_id": "TEST",
        "machine_outcome": "pass",
        "draft_outcome": "pass",
        "agreement": True,
        "observation": "The criterion is satisfied.",
    }
    adjudication = {
        "status": "approved",
        "approved_by": "Reviewer",
        "summary": {"records": 1, "human_pass": 1, "human_fail": 0, "machine_agreements": 1},
        "records": [human_record],
    }
    _write_json(run_root / "human_adjudication.json", adjudication)
    _write_json(
        run_root / "report.json",
        {
            "run_id": "demo",
            "suite_name": "Demo",
            "suite_metadata": {},
            "checkpoint_summary": {"a": {"average_score": 8, "count": 1}},
            "test_summary": {"TEST": {"average_score": 8, "count": 1}},
            "records": [analysis_record],
            "human_adjudication": adjudication,
        },
    )

    output_root = tmp_path / "public"
    result = build_public_demo(run_root, output_root)

    assert result["artifact_count"] == 1
    artifact = result["artifacts"][0]
    assert artifact["pixel_equivalent"] is True
    assert artifact["transformation"] == {
        "decode": "lossless",
        "encode": "lossless PNG re-encode",
        "source_metadata_removed": True,
        "cef_envelope_added": True,
        "pixel_content_modified": False,
        "container_bytes_modified": True,
    }
    published_path = output_root / artifact["image"]
    with Image.open(published_path) as published:
        assert set(published.info) == set(CEF_PNG_KEYS)
        assert "parameters" not in published.info
        assert "private_extension_field" not in published.info
        assert published.info["cef_original_png_sha256"] == original_hash
        assert published.getpixel((0, 0)) == (20, 40, 60)
    assert hashlib.sha256(image_path.read_bytes()).hexdigest() == original_hash
    assert "private/path" not in (output_root / "manifest.json").read_text(encoding="utf-8")
    assert (output_root / "index.html").exists()
    assert (output_root / "artifact_index.json").exists()
