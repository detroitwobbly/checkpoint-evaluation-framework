from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ResolvedComfyWorkflow:
    variant: str
    api_workflow: dict[str, Any]
    ui_workflow: dict[str, Any]
    output_node: str

    @property
    def api_sha256(self) -> str:
        return semantic_sha256(self.api_workflow)

    @property
    def ui_sha256(self) -> str:
        return semantic_sha256(self.ui_workflow)

    def submission_payload(self, client_id: str) -> dict[str, Any]:
        return {
            "prompt": self.api_workflow,
            "client_id": client_id,
            "extra_data": {"extra_pnginfo": {"workflow": self.ui_workflow}},
        }


class ComfyWorkflowFamily:
    def __init__(self, root: Path, manifest: dict[str, Any]) -> None:
        self.root = root
        self.manifest = manifest

    @classmethod
    def load(cls, binding_path: Path) -> "ComfyWorkflowFamily":
        manifest = json.loads(binding_path.read_text(encoding="utf-8"))
        family = cls(binding_path.parent, manifest)
        family.validate()
        return family

    def variants(self) -> tuple[str, ...]:
        return tuple(self.manifest["variants"])

    def validate(self) -> None:
        if self.manifest.get("schema_version") != 1:
            raise ValueError("Unsupported Comfy binding schema version.")
        for variant_name, variant in self.manifest.get("variants", {}).items():
            api = self._read_json(variant["api_workflow"])
            ui = self._read_json(variant["ui_workflow"])
            ui_nodes = _ui_nodes(ui)
            output_node = str(variant["output_node"])
            if api.get(output_node, {}).get("class_type") != "SaveImage":
                raise ValueError(f"{variant_name}: output node {output_node} is not SaveImage.")
            if set(api) != set(ui_nodes):
                raise ValueError(f"{variant_name}: UI and API node sets differ.")
            for field, binding in variant["bindings"].items():
                node_id, class_type, input_name = binding
                node = api.get(str(node_id))
                if not node:
                    raise ValueError(f"{variant_name}.{field}: missing node {node_id}.")
                if node.get("class_type") != class_type:
                    raise ValueError(f"{variant_name}.{field}: expected {class_type} at node {node_id}.")
                if input_name not in node.get("inputs", {}):
                    raise ValueError(f"{variant_name}.{field}: missing API input {input_name}.")
                if input_name not in ui_nodes[str(node_id)].get("widgets_values_named", {}):
                    raise ValueError(f"{variant_name}.{field}: missing UI widget {input_name}.")

    def resolve(self, variant_name: str, values: dict[str, Any]) -> ResolvedComfyWorkflow:
        try:
            variant = self.manifest["variants"][variant_name]
        except KeyError as exc:
            raise ValueError(f"Unknown Comfy workflow variant: {variant_name}") from exc
        unknown = sorted(set(values) - set(variant["bindings"]))
        if unknown:
            raise ValueError(f"Unbound Comfy workflow fields: {', '.join(unknown)}")

        api = copy.deepcopy(self._read_json(variant["api_workflow"]))
        ui = copy.deepcopy(self._read_json(variant["ui_workflow"]))
        ui_nodes = _ui_nodes(ui)
        for field, value in values.items():
            node_id, _class_type, input_name = variant["bindings"][field]
            node_id = str(node_id)
            api[node_id]["inputs"][input_name] = value
            _set_ui_widget(ui_nodes[node_id], input_name, value)
        return ResolvedComfyWorkflow(
            variant=variant_name,
            api_workflow=api,
            ui_workflow=ui,
            output_node=str(variant["output_node"]),
        )

    def _read_json(self, name: str) -> dict[str, Any]:
        return json.loads((self.root / name).read_text(encoding="utf-8"))


def semantic_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ui_nodes(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node["id"]): node for node in workflow.get("nodes", [])}


def _set_ui_widget(node: dict[str, Any], input_name: str, value: Any) -> None:
    named = node.get("widgets_values_named")
    positional = node.get("widgets_values")
    if not isinstance(named, dict) or input_name not in named:
        raise ValueError(f"UI node {node.get('id')} has no named widget {input_name}.")
    keys = list(named)
    index = keys.index(input_name)
    if not isinstance(positional, list) or index >= len(positional):
        raise ValueError(f"UI node {node.get('id')} has no positional widget for {input_name}.")
    named[input_name] = value
    positional[index] = value
