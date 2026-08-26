from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .comfy import ComfyClient
from .comfy_workflow import ComfyWorkflowFamily
from .forge import ForgeClient
from .models import CheckpointProfile, LoraProfile


@dataclass(slots=True)
class BackendGeneration:
    images: list[bytes]
    response_metadata: dict[str, Any]
    info: dict[str, Any]
    artifacts: dict[str, Any] = field(default_factory=dict)


class GenerationPending(RuntimeError):
    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"Generation submitted and intentionally paused: {prompt_id}")
        self.prompt_id = prompt_id


class GenerationBackend(Protocol):
    backend_id: str
    prompt_lora_tokens: bool

    def inventory(self, dry_run: bool = False) -> dict[str, Any]: ...

    def prepare_checkpoint(self, checkpoint: CheckpointProfile, dry_run: bool = False) -> dict[str, Any]: ...

    def generate(
        self,
        request_payload: dict[str, Any],
        checkpoint: CheckpointProfile,
        lora_profile: LoraProfile,
        test_root: Path,
        *,
        resume_pending: bool = False,
        pause_after_submit: bool = False,
    ) -> BackendGeneration: ...

    def release_resources(self) -> dict[str, Any]: ...


class ForgeBackend:
    backend_id = "forge"
    prompt_lora_tokens = True

    def __init__(self, base_url: str = "http://127.0.0.1:7860", timeout: int = 300) -> None:
        self.client = ForgeClient(base_url, timeout=timeout)

    def inventory(self, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"backend_id": self.backend_id, "dry_run": True, "version": {}, "options": {}, "models": [], "loras": []}
        return {
            "backend_id": self.backend_id,
            "version": self.client.version(),
            "options": self.client.options(),
            "models": self.client.models(),
            "loras": _slim_forge_loras(self.client.loras()),
        }

    def prepare_checkpoint(self, checkpoint: CheckpointProfile, dry_run: bool = False) -> dict[str, Any]:
        return {} if dry_run else self.client.set_checkpoint(checkpoint.title)

    def generate(
        self,
        request_payload: dict[str, Any],
        checkpoint: CheckpointProfile,
        lora_profile: LoraProfile,
        test_root: Path,
        *,
        resume_pending: bool = False,
        pause_after_submit: bool = False,
    ) -> BackendGeneration:
        if pause_after_submit:
            raise ValueError("Forge has no separate submit/retrieve phase; --pause-after-submit is Comfy-only.")
        generation = self.client.txt2img(request_payload)
        return BackendGeneration(generation.images, generation.response_metadata, generation.info)

    def release_resources(self) -> dict[str, Any]:
        return self.client.unload_checkpoint()


class ComfyBackend:
    backend_id = "comfy"
    prompt_lora_tokens = False

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        timeout: int = 300,
        bindings_path: Path | None = None,
    ) -> None:
        self.client = ComfyClient(base_url, timeout=timeout)
        if bindings_path is None:
            bindings_path = Path(__file__).resolve().parents[1] / "workflows" / "comfy" / "sdxl_txt2img_bindings.json"
        self.bindings_path = bindings_path.resolve()
        self.family = ComfyWorkflowFamily.load(self.bindings_path)
        self._inventory: dict[str, Any] | None = None

    def inventory(self, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {
                "backend_id": self.backend_id,
                "dry_run": True,
                "version": {},
                "options": {},
                "models": [],
                "loras": [],
                "workflow_bindings": str(self.bindings_path),
            }
        checkpoint_info = self.client.object_info("CheckpointLoaderSimple")
        lora_info = self.client.object_info("LoraLoader")
        checkpoints = checkpoint_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        loras = lora_info["LoraLoader"]["input"]["required"]["lora_name"][0]
        self._inventory = {
            "backend_id": self.backend_id,
            "version": self.client.system_stats(),
            "options": {"workflow_family": self.family.manifest.get("workflow_family")},
            "models": [{"title": name, "model_name": name} for name in checkpoints],
            "loras": [{"name": name, "alias": name} for name in loras],
            "workflow_bindings": str(self.bindings_path),
            "workflow_variants": list(self.family.variants()),
        }
        return self._inventory

    def prepare_checkpoint(self, checkpoint: CheckpointProfile, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"checkpoint": checkpoint.title, "validated": False, "dry_run": True}
        inventory = self._inventory or self.inventory()
        available = {str(model.get("title")) for model in inventory["models"]}
        if checkpoint.title not in available:
            raise ValueError(f"Checkpoint is not available in ComfyUI: {checkpoint.title}")
        return {"checkpoint": checkpoint.title, "validated": True, "selection": "resolved_graph_input"}

    def generate(
        self,
        request_payload: dict[str, Any],
        checkpoint: CheckpointProfile,
        lora_profile: LoraProfile,
        test_root: Path,
        *,
        resume_pending: bool = False,
        pause_after_submit: bool = False,
    ) -> BackendGeneration:
        if int(request_payload.get("n_iter", 1)) != 1:
            raise ValueError("ComfyBackend currently requires n_iter=1; use batch_size for multiple outputs.")
        if len(lora_profile.loras) > 1:
            raise ValueError("The canonical Comfy workflow currently supports zero or one LoRA per profile.")

        values = {
            "checkpoint": checkpoint.title,
            "positive_prompt": str(request_payload["prompt"]),
            "negative_prompt": str(request_payload.get("negative_prompt", "")),
            "seed": int(request_payload["seed"]),
            "steps": int(request_payload["steps"]),
            "cfg_scale": float(request_payload["cfg_scale"]),
            "sampler_name": str(request_payload["sampler_name"]),
            "scheduler": str(request_payload.get("scheduler") or "normal"),
            "denoise": 1.0,
            "width": int(request_payload["width"]),
            "height": int(request_payload["height"]),
            "batch_size": int(request_payload.get("batch_size", 1)),
            "output_prefix": (
                f"CEF/{test_root.parents[3].name}/{test_root.parent.parent.name}/"
                f"{test_root.parent.name}/{test_root.name}"
            ),
        }
        variant = "base"
        if lora_profile.loras:
            variant = "single_lora"
            lora = lora_profile.loras[0]
            values.update(
                {
                    "lora_name": lora.name,
                    "lora_strength_model": lora.weight,
                    "lora_strength_clip": lora.weight,
                }
            )
        resolved = self.family.resolve(variant, values)
        _write_json_atomic(test_root / "resolved_api_workflow.json", resolved.api_workflow)
        _write_json_atomic(test_root / "resolved_ui_workflow.json", resolved.ui_workflow)
        _write_json_atomic(
            test_root / "backend_request.json",
            {
                "backend_id": self.backend_id,
                "variant": variant,
                "values": values,
                "resolved_api_sha256": resolved.api_sha256,
                "resolved_ui_sha256": resolved.ui_sha256,
            },
        )

        submission_path = test_root / "backend_submission.json"
        submission_response: dict[str, Any]
        recovered_submission = False
        if resume_pending and submission_path.exists():
            submission_record = json.loads(submission_path.read_text(encoding="utf-8-sig"))
            if submission_record.get("resolved_api_sha256") != resolved.api_sha256:
                raise ValueError("Pending Comfy submission API graph hash does not match the current resolved graph.")
            if submission_record.get("resolved_ui_sha256") != resolved.ui_sha256:
                raise ValueError("Pending Comfy submission UI graph hash does not match the current resolved graph.")
            prompt_id = str(submission_record["prompt_id"])
            submission_response = dict(submission_record.get("response") or {})
            recovered_submission = True
        else:
            submission = self.client.submit(resolved)
            prompt_id = submission.prompt_id
            submission_response = submission.response
            _write_json_atomic(
                submission_path,
                {
                    "backend_id": self.backend_id,
                    "prompt_id": prompt_id,
                    "response": submission_response,
                    "resolved_api_sha256": resolved.api_sha256,
                    "resolved_ui_sha256": resolved.ui_sha256,
                },
            )
        if pause_after_submit and not recovered_submission:
            raise GenerationPending(prompt_id)

        history = self.client.history(prompt_id)
        if history is None:
            history = self.client.wait(prompt_id, deadline_seconds=max(self.client.timeout, 30), poll_seconds=1)
        else:
            self.client._raise_for_execution_error(history)
        _write_json_atomic(test_root / "backend_history.json", history)
        refs = self.client.output_images(history, resolved.output_node)
        images = [self.client.download_image(ref) for ref in refs]
        return BackendGeneration(
            images=images,
            response_metadata={
                "backend_id": self.backend_id,
                "prompt_id": prompt_id,
                "submission": submission_response,
                "history": history,
                "output_references": refs,
                "recovered_submission": recovered_submission,
            },
            info={
                "backend": self.backend_id,
                "checkpoint": checkpoint.title,
                "lora_profile_id": lora_profile.id,
            },
            artifacts={
                "resolved_api_sha256": resolved.api_sha256,
                "resolved_ui_sha256": resolved.ui_sha256,
                "submission_path": str(submission_path),
                "history_path": str(test_root / "backend_history.json"),
            },
        )

    def release_resources(self) -> dict[str, Any]:
        before = self.client.system_stats()
        response = self.client.free(unload_models=True, free_memory=True)
        time.sleep(1.0)
        after = self.client.system_stats()
        return {"before": before, "request": {"unload_models": True, "free_memory": True}, "response": response, "after": after}


def _slim_forge_loras(loras: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                    for key in ("modelspec.hash_sha256", "sshs_model_hash", "sshs_legacy_hash")
                    if metadata.get(key)
                },
            }
        )
    return slim


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)
