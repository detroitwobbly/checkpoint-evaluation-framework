from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ForgeGeneration:
    images: list[bytes]
    response_metadata: dict[str, Any]
    info: dict[str, Any]


class ForgeClient:
    def __init__(self, base_url: str = "http://127.0.0.1:7860", timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def options(self) -> dict[str, Any]:
        return self._get_json("/sdapi/v1/options")

    def version(self) -> dict[str, Any]:
        """Return Forge/A1111 backend version metadata when the API exposes it.

        Forge-Neo is changing quickly enough that the web UI/runtime version is
        part of CEF Layer 0 provenance. The endpoint is not guaranteed across
        every compatible backend, so absence is recorded instead of making a
        generation run fail.
        """
        try:
            loaded = self._get_json("/sdapi/v1/version")
        except RuntimeError as exc:
            return {
                "available": False,
                "endpoint": "/sdapi/v1/version",
                "error": str(exc),
            }
        if isinstance(loaded, dict):
            return {"available": True, "endpoint": "/sdapi/v1/version", **loaded}
        return {
            "available": True,
            "endpoint": "/sdapi/v1/version",
            "raw": loaded,
        }

    def models(self) -> list[dict[str, Any]]:
        loaded = self._get_json("/sdapi/v1/sd-models")
        return loaded if isinstance(loaded, list) else []

    def loras(self) -> list[dict[str, Any]]:
        loaded = self._get_json("/sdapi/v1/loras")
        return loaded if isinstance(loaded, list) else []

    def samplers(self) -> list[dict[str, Any]]:
        loaded = self._get_json("/sdapi/v1/samplers")
        return loaded if isinstance(loaded, list) else []

    def schedulers(self) -> list[dict[str, Any]]:
        loaded = self._get_json("/sdapi/v1/schedulers")
        return loaded if isinstance(loaded, list) else []

    def memory(self) -> dict[str, Any]:
        loaded = self._get_json("/sdapi/v1/memory")
        return loaded if isinstance(loaded, dict) else {}

    def unload_checkpoint(self) -> dict[str, Any]:
        loaded = self._post_json("/sdapi/v1/unload-checkpoint", {})
        return loaded if isinstance(loaded, dict) else {}

    def reload_checkpoint(self) -> dict[str, Any]:
        loaded = self._post_json("/sdapi/v1/reload-checkpoint", {})
        return loaded if isinstance(loaded, dict) else {}

    def set_checkpoint(self, checkpoint_title: str) -> dict[str, Any]:
        options = self.options()
        if options.get("sd_model_checkpoint") == checkpoint_title:
            return options
        self._post_json("/sdapi/v1/options", {"sd_model_checkpoint": checkpoint_title})
        return self.options()

    def txt2img(self, payload: dict[str, Any]) -> ForgeGeneration:
        response = self._post_json("/sdapi/v1/txt2img", payload)
        images = [base64.b64decode(image) for image in response.get("images", [])]
        metadata = {key: value for key, value in response.items() if key != "images"}
        info = _parse_info(metadata.get("info"))
        return ForgeGeneration(images=images, response_metadata=metadata, info=info)

    def _get_json(self, path: str) -> Any:
        request = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        return self._open_json(request)

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Forge API failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Forge API failed: {exc.reason}") from exc


def _parse_info(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
        return loaded if isinstance(loaded, dict) else {"raw": value}
    return {}
