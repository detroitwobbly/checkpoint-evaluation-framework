import json
from pathlib import Path

import pytest

from checkpoint_evaluator.generation import _request_payload
from checkpoint_evaluator.generation import _resolve_checkpoint_hash
from checkpoint_evaluator.generation import run_generation_suite
from checkpoint_evaluator.forge import ForgeGeneration
from checkpoint_evaluator.manifest import load_suite
from checkpoint_evaluator.models import ReferenceImage


MANIFEST = Path(__file__).parent / "fixtures" / "smoke_manifest.json"


def test_load_json_manifest():
    suite = load_suite(MANIFEST)

    assert suite.suite_id == "CEF_SMOKE"
    assert suite.checkpoints[0].title == "sd\\YOUR_CHECKPOINT.safetensors"
    assert suite.lora_profiles[0].id == "none"
    assert suite.tests[0].criteria[0].description == "red cube visible"


def test_request_payload_appends_lora_tokens():
    suite = load_suite(MANIFEST)
    test = suite.tests[0]
    profile = suite.lora_profiles[0]

    payload = _request_payload(test, suite.defaults, profile)

    assert payload["prompt"] == "a simple red cube on a wooden table, neutral studio lighting"
    assert payload["negative_prompt"] == "blurry, low quality, text, watermark"
    assert payload["save_images"] is False


def test_request_payload_includes_scheduler_when_present():
    suite = load_suite(MANIFEST)
    settings = suite.defaults.merged({"scheduler": "Karras"})
    payload = _request_payload(suite.tests[0], settings, suite.lora_profiles[0])

    assert payload["scheduler"] == "Karras"


def test_testcase_preserves_category_and_purpose():
    suite = load_suite(MANIFEST)
    test = suite.tests[0]
    test.category = "object"
    test.purpose = "smoke"

    assert test.to_dict()["category"] == "object"
    assert test.to_dict()["purpose"] == "smoke"


def test_testcase_preserves_reference_images():
    suite = load_suite(MANIFEST)
    test = suite.tests[0]
    test.reference_images = [
        ReferenceImage(
            label="material_reference",
            path="references/material_reference.jpg",
            purpose="material calibration",
        )
    ]
    test.reference_instruction = "Use this for foam judgment."

    serialized = test.to_dict()

    assert serialized["reference_images"][0]["label"] == "material_reference"
    assert serialized["reference_images"][0]["purpose"] == "material calibration"
    assert serialized["reference_instruction"] == "Use this for foam judgment."


class FakeForge:
    def __init__(self):
        self.generation_calls = 0

    def version(self):
        return {"available": True, "version": "test"}

    def options(self):
        return {"sd_model_checkpoint": "sd\\YOUR_CHECKPOINT.safetensors", "sd_checkpoint_hash": "abc123"}

    def set_checkpoint(self, checkpoint_title):
        return {"sd_model_checkpoint": checkpoint_title, "sd_checkpoint_hash": "abc123"}

    def models(self):
        return []

    def loras(self):
        return []

    def txt2img(self, payload):
        self.generation_calls += 1
        return ForgeGeneration(images=[b"synthetic-image-bytes"], response_metadata={}, info={"sd_model_hash": "abc123"})


def test_generation_dry_run_uses_approved_structure(tmp_path):
    suite = load_suite(MANIFEST)

    run_root = run_generation_suite(suite, tmp_path, FakeForge(), run_id="run_test", dry_run=True)

    expected = run_root / "approved" / "checkpoint_example_checkpoint" / "lora_none" / "CEF_SMOKE_01"
    assert expected.exists()
    assert (expected / "request.json").exists()


def test_generation_resume_skips_complete_cells_and_preserves_inventory(tmp_path):
    suite = load_suite(MANIFEST)
    first = FakeForge()
    run_root = run_generation_suite(suite, tmp_path, first, run_id="run_resume")

    second = FakeForge()
    resumed_root = run_generation_suite(suite, tmp_path, second, run_id="run_resume", resume=True)

    assert resumed_root == run_root
    assert first.generation_calls == 1
    assert second.generation_calls == 0
    state = json.loads((run_root / "run_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "complete"
    assert state["completed_cells"] == 1
    assert state["resumed_cells"] == 1
    assert len(list(run_root.glob("forge_inventory_resume_*.json"))) == 1


def test_generation_resume_regenerates_incomplete_cell(tmp_path):
    suite = load_suite(MANIFEST)
    run_root = run_generation_suite(suite, tmp_path, FakeForge(), run_id="run_incomplete")
    image_path = next(run_root.rglob("*.png"))
    image_path.unlink()

    resumed = FakeForge()
    run_generation_suite(suite, tmp_path, resumed, run_id="run_incomplete", resume=True)

    assert resumed.generation_calls == 1
    assert image_path.exists()


def test_generation_refuses_ambiguous_run_reuse(tmp_path):
    suite = load_suite(MANIFEST)
    run_generation_suite(suite, tmp_path, FakeForge(), run_id="run_existing", dry_run=True)

    with pytest.raises(FileExistsError, match="--resume"):
        run_generation_suite(suite, tmp_path, FakeForge(), run_id="run_existing", dry_run=True)


def test_generation_resume_refuses_manifest_drift(tmp_path):
    suite = load_suite(MANIFEST)
    run_generation_suite(suite, tmp_path, FakeForge(), run_id="run_drift", dry_run=True)
    suite.tests[0].prompt = "a different prompt"

    with pytest.raises(ValueError, match="differs"):
        run_generation_suite(suite, tmp_path, FakeForge(), run_id="run_drift", dry_run=True, resume=True)


def test_generated_hash_overrides_stale_post_switch_options_hash():
    models = [
        {
            "hash": "b54e38a6bd",
            "sha256": "b54e38a6bdaf010179bcaf4ca8637598a5b0b7587bab3b6ebd1cdff699d8863d",
        }
    ]

    resolved = _resolve_checkpoint_hash(
        "b54e38a6bd",
        models,
        "0e457c591afeda5e1cb1e1b6809639c862bd168d6e6a5c47c2200e506ec988c0",
    )

    assert resolved == "b54e38a6bdaf010179bcaf4ca8637598a5b0b7587bab3b6ebd1cdff699d8863d"
