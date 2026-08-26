from pathlib import Path

import pytest

from checkpoint_evaluator.comfy_workflow import ComfyWorkflowFamily


BINDINGS = Path(__file__).parents[1] / "workflows" / "comfy" / "sdxl_txt2img_bindings.json"


def family() -> ComfyWorkflowFamily:
    return ComfyWorkflowFamily.load(BINDINGS)


def test_resolve_updates_api_and_matching_editable_ui_widgets():
    resolved = family().resolve(
        "single_lora",
        {
            "checkpoint": "different.safetensors",
            "positive_prompt": "a brass automaton",
            "negative_prompt": "text",
            "seed": 137,
            "cfg_scale": 5.5,
            "lora_name": "Near_Far_v1.safetensors",
            "lora_strength_model": -1.25,
            "lora_strength_clip": -0.75,
            "output_prefix": "CEF/run/cell",
        },
    )
    assert resolved.api_workflow["3"]["inputs"]["seed"] == 137
    assert resolved.api_workflow["10"]["inputs"]["strength_model"] == -1.25
    ui_nodes = {str(node["id"]): node for node in resolved.ui_workflow["nodes"]}
    assert ui_nodes["3"]["widgets_values_named"]["seed"] == 137
    assert ui_nodes["3"]["widgets_values"][0] == 137
    assert ui_nodes["10"]["widgets_values_named"]["strength_model"] == -1.25
    assert ui_nodes["10"]["widgets_values"][1] == -1.25
    assert ui_nodes["9"]["widgets_values_named"]["filename_prefix"] == "CEF/run/cell"


def test_submission_payload_carries_resolved_editable_workflow_as_png_metadata():
    resolved = family().resolve("base", {"seed": 812, "positive_prompt": "a wooden cube"})
    payload = resolved.submission_payload("client-test")
    assert payload["prompt"]["3"]["inputs"]["seed"] == 812
    embedded = payload["extra_data"]["extra_pnginfo"]["workflow"]
    nodes = {str(node["id"]): node for node in embedded["nodes"]}
    assert nodes["3"]["widgets_values_named"]["seed"] == 812
    assert nodes["6"]["widgets_values_named"]["text"] == "a wooden cube"


def test_unknown_binding_is_rejected_before_submission():
    with pytest.raises(ValueError, match="Unbound"):
        family().resolve("base", {"lora_name": "not-legal-in-baseline.safetensors"})
