from __future__ import annotations

import json
from pathlib import Path

import pytest

from checkpoint_evaluator.backend import ComfyBackend, GenerationPending
from checkpoint_evaluator.comfy import ComfySubmission
from checkpoint_evaluator.models import CheckpointProfile, LoraProfile, LoraSpec
from checkpoint_evaluator.generation import _request_payload
from checkpoint_evaluator.models import Criterion, GenerationSettings, TestCase as CEFTestCase


class FakeComfyClient:
    timeout = 30

    def __init__(self) -> None:
        self.submit_count = 0
        self.complete = False

    def submit(self, workflow):
        self.submit_count += 1
        return ComfySubmission("p1", {"prompt_id": "p1", "node_errors": {}})

    def history(self, prompt_id: str):
        if not self.complete:
            return None
        return {
            "status": {"status_str": "success", "completed": True, "messages": []},
            "outputs": {"9": {"images": [{"filename": "x.png", "subfolder": "", "type": "output"}]}},
        }

    def wait(self, prompt_id: str, deadline_seconds: float, poll_seconds: float):
        self.complete = True
        return self.history(prompt_id)

    @staticmethod
    def _raise_for_execution_error(history):
        return None

    @staticmethod
    def output_images(history, output_node: str):
        return history["outputs"][output_node]["images"]

    @staticmethod
    def download_image(image_ref):
        return b"png"


def request() -> dict:
    return {
        "prompt": "A woman wearing a black dress",
        "negative_prompt": "text, watermark",
        "steps": 30,
        "cfg_scale": 7.0,
        "width": 1024,
        "height": 1024,
        "sampler_name": "dpmpp_2m_sde",
        "scheduler": "karras",
        "seed": 42,
        "batch_size": 1,
        "n_iter": 1,
    }


def test_comfy_pending_submission_is_recovered_without_resubmit(tmp_path: Path) -> None:
    backend = ComfyBackend()
    fake = FakeComfyClient()
    backend.client = fake
    checkpoint = CheckpointProfile("juggernaut", "juggernautXL_ragnarokBy.safetensors")
    profile = LoraProfile("near", [LoraSpec("Near_Far_v1.safetensors", 1.0)])

    with pytest.raises(GenerationPending, match="p1"):
        backend.generate(request(), checkpoint, profile, tmp_path, pause_after_submit=True)

    assert fake.submit_count == 1
    submission = json.loads((tmp_path / "backend_submission.json").read_text())
    assert submission["prompt_id"] == "p1"
    assert submission["resolved_api_sha256"]
    assert submission["resolved_ui_sha256"]
    fake.complete = True

    generation = backend.generate(request(), checkpoint, profile, tmp_path, resume_pending=True)

    assert fake.submit_count == 1
    assert generation.images == [b"png"]
    assert generation.response_metadata["recovered_submission"] is True
    resolved = json.loads((tmp_path / "resolved_api_workflow.json").read_text())
    assert resolved["10"]["inputs"]["strength_model"] == 1.0
    assert resolved["10"]["inputs"]["strength_clip"] == 1.0


def test_comfy_refuses_pending_submission_when_graph_changed(tmp_path: Path) -> None:
    backend = ComfyBackend()
    fake = FakeComfyClient()
    backend.client = fake
    checkpoint = CheckpointProfile("juggernaut", "juggernautXL_ragnarokBy.safetensors")
    profile = LoraProfile("near", [LoraSpec("Near_Far_v1.safetensors", 1.0)])
    with pytest.raises(GenerationPending):
        backend.generate(request(), checkpoint, profile, tmp_path, pause_after_submit=True)

    changed = request()
    changed["seed"] = 137
    with pytest.raises(ValueError, match="graph hash"):
        backend.generate(changed, checkpoint, profile, tmp_path, resume_pending=True)


def test_comfy_rejects_more_than_one_lora(tmp_path: Path) -> None:
    backend = ComfyBackend()
    profile = LoraProfile("two", [LoraSpec("a.safetensors"), LoraSpec("b.safetensors")])
    with pytest.raises(ValueError, match="zero or one LoRA"):
        backend.generate(
            request(),
            CheckpointProfile("c", "juggernautXL_ragnarokBy.safetensors"),
            profile,
            tmp_path,
        )


def test_comfy_request_omits_forge_lora_prompt_token() -> None:
    test = CEFTestCase("t", "t", "A portrait", [Criterion("c", "visible")])
    profile = LoraProfile("near", [LoraSpec("Near_Far_v1.safetensors", -1.0)])
    payload = _request_payload(test, GenerationSettings(), profile, include_lora_tokens=False)
    assert payload["prompt"] == "A portrait"
    assert "<lora:" not in payload["prompt"]
