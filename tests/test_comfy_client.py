from __future__ import annotations

from typing import Any

import pytest

from checkpoint_evaluator.comfy import ComfyClient, ComfyError
from checkpoint_evaluator.comfy_workflow import ResolvedComfyWorkflow


class FakeClient(ComfyClient):
    def __init__(self) -> None:
        super().__init__("http://invalid")
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.history_records: list[dict[str, Any] | None] = []

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.posts.append((path, payload))
        return {"prompt_id": "p1", "node_errors": {}}

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        return self.history_records.pop(0)

    def _get_bytes(self, path: str) -> bytes:
        return b"png"


def resolved() -> ResolvedComfyWorkflow:
    return ResolvedComfyWorkflow("base", {"9": {}}, {"nodes": []}, "9")


def test_submit_preserves_ui_workflow_for_png_metadata() -> None:
    client = FakeClient()
    submission = client.submit(resolved())
    assert submission.prompt_id == "p1"
    payload = client.posts[0][1]
    assert payload["prompt"] == {"9": {}}
    assert payload["extra_data"]["extra_pnginfo"]["workflow"] == {"nodes": []}


def test_wait_and_download_output() -> None:
    client = FakeClient()
    complete = {
        "status": {"status_str": "success", "completed": True, "messages": []},
        "outputs": {"9": {"images": [{"filename": "x.png", "subfolder": "a", "type": "output"}]}},
    }
    client.history_records = [None, complete]
    history = client.wait("p1", deadline_seconds=1, poll_seconds=0)
    refs = client.output_images(history, "9")
    assert refs == [{"filename": "x.png", "subfolder": "a", "type": "output"}]
    assert client.download_image(refs[0]) == b"png"


def test_wait_raises_execution_error() -> None:
    client = FakeClient()
    client.history_records = [{"status": {"status_str": "error", "completed": False, "messages": [["execution_error", {"x": 1}]]}}]
    with pytest.raises(ComfyError, match="execution failed"):
        client.wait("p1", deadline_seconds=1, poll_seconds=0)


def test_missing_output_is_an_error() -> None:
    with pytest.raises(ComfyError, match="no images"):
        FakeClient().output_images({"outputs": {}}, "9")


def test_targeted_interrupt_and_free_payloads() -> None:
    client = FakeClient()
    client.interrupt("p1")
    client.free()
    assert client.posts[-2] == ("/interrupt", {"prompt_id": "p1"})
    assert client.posts[-1] == ("/free", {"unload_models": True, "free_memory": True})
