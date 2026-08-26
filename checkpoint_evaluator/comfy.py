from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

from .comfy_workflow import ResolvedComfyWorkflow


class ComfyError(RuntimeError):
    """A ComfyUI transport, queue, or execution failure."""


@dataclass(slots=True)
class ComfySubmission:
    prompt_id: str
    response: dict[str, Any]


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

    def system_stats(self) -> dict[str, Any]:
        return self._get_json("/system_stats")

    def object_info(self, node_class: str | None = None) -> dict[str, Any]:
        suffix = f"/{urllib.parse.quote(node_class)}" if node_class else ""
        return self._get_json(f"/object_info{suffix}")

    def submit(self, workflow: ResolvedComfyWorkflow) -> ComfySubmission:
        response = self._post_json("/prompt", workflow.submission_payload(self.client_id))
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyError(f"ComfyUI did not return a prompt_id: {response!r}")
        node_errors = response.get("node_errors") or {}
        if node_errors:
            raise ComfyError(f"ComfyUI rejected workflow nodes: {node_errors!r}")
        return ComfySubmission(str(prompt_id), response)

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        result = self._get_json(f"/history/{urllib.parse.quote(prompt_id)}")
        return result.get(prompt_id)

    def wait(self, prompt_id: str, deadline_seconds: float = 900.0, poll_seconds: float = 1.0) -> dict[str, Any]:
        deadline = time.monotonic() + deadline_seconds
        while time.monotonic() < deadline:
            record = self.history(prompt_id)
            if record is not None:
                self._raise_for_execution_error(record)
                return record
            time.sleep(poll_seconds)
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}.")

    def output_images(self, history: dict[str, Any], output_node: str) -> list[dict[str, str]]:
        images = history.get("outputs", {}).get(str(output_node), {}).get("images", [])
        if not images:
            raise ComfyError(f"ComfyUI history has no images at output node {output_node}.")
        return [
            {
                "filename": str(item["filename"]),
                "subfolder": str(item.get("subfolder", "")),
                "type": str(item.get("type", "output")),
            }
            for item in images
        ]

    def download_image(self, image_ref: dict[str, str]) -> bytes:
        query = urllib.parse.urlencode(image_ref)
        return self._get_bytes(f"/view?{query}")

    def interrupt(self, prompt_id: str | None = None) -> dict[str, Any]:
        return self._post_json("/interrupt", {"prompt_id": prompt_id} if prompt_id else {})

    def cancel(self, prompt_id: str) -> dict[str, Any]:
        return self._post_json(f"/api/jobs/{urllib.parse.quote(prompt_id)}/cancel", {})

    def free(self, *, unload_models: bool = True, free_memory: bool = True) -> dict[str, Any]:
        return self._post_json(
            "/free",
            {"unload_models": unload_models, "free_memory": free_memory},
        )

    @staticmethod
    def _raise_for_execution_error(history: dict[str, Any]) -> None:
        status = history.get("status", {})
        if status.get("status_str") == "error" or not status.get("completed", True):
            messages = status.get("messages", [])
            raise ComfyError(f"ComfyUI execution failed: {messages!r}")

    def _get_json(self, path: str) -> dict[str, Any]:
        return json.loads(self._request(path).decode("utf-8"))

    def _get_bytes(self, path: str) -> bytes:
        return self._request(path)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        response = self._request(path, body, {"Content-Type": "application/json"})
        if not response.strip():
            return {}
        decoded = json.loads(response.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else {"response": decoded}

    def _request(self, path: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyError(f"ComfyUI HTTP {exc.code} for {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ComfyError(f"Unable to reach ComfyUI at {self.base_url}: {exc.reason}") from exc
