from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1] / "workflows" / "comfy"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def ui_nodes(name: str) -> dict[str, dict]:
    return {str(node["id"]): node for node in load(name)["nodes"]}


def test_bindings_resolve_to_expected_api_node_inputs():
    manifest = load("sdxl_txt2img_bindings.json")
    for variant in manifest["variants"].values():
        workflow = load(variant["api_workflow"])
        assert workflow[variant["output_node"]]["class_type"] == "SaveImage"
        for node_id, class_type, input_name in variant["bindings"].values():
            assert workflow[node_id]["class_type"] == class_type
            assert input_name in workflow[node_id]["inputs"]


def test_baseline_is_a_true_no_lora_graph():
    api = load("sdxl_txt2img_base_api.json")
    ui = ui_nodes("sdxl_txt2img_base_ui.json")
    assert all(node["class_type"] != "LoraLoader" for node in api.values())
    assert all(node["type"] != "LoraLoader" for node in ui.values())
    assert api["3"]["inputs"]["model"] == ["4", 0]
    assert api["6"]["inputs"]["clip"] == ["4", 1]
    assert api["7"]["inputs"]["clip"] == ["4", 1]


def test_single_lora_routes_model_and_clip_but_not_vae_through_loader():
    api = load("sdxl_txt2img_single_lora_api.json")
    assert sum(node["class_type"] == "LoraLoader" for node in api.values()) == 1
    assert api["10"]["inputs"]["model"] == ["4", 0]
    assert api["10"]["inputs"]["clip"] == ["4", 1]
    assert api["3"]["inputs"]["model"] == ["10", 0]
    assert api["6"]["inputs"]["clip"] == ["10", 1]
    assert api["7"]["inputs"]["clip"] == ["10", 1]
    assert api["8"]["inputs"]["vae"] == ["4", 2]


def test_ui_and_api_exports_have_matching_nodes_and_widget_values():
    pairs = (
        ("sdxl_txt2img_base_api.json", "sdxl_txt2img_base_ui.json"),
        ("sdxl_txt2img_single_lora_api.json", "sdxl_txt2img_single_lora_ui.json"),
    )
    for api_name, ui_name in pairs:
        api = load(api_name)
        ui = ui_nodes(ui_name)
        assert set(api) == set(ui)
        for node_id, api_node in api.items():
            assert ui[node_id]["type"] == api_node["class_type"]
            named = ui[node_id].get("widgets_values_named", {})
            for input_name, value in api_node["inputs"].items():
                if not isinstance(value, list):
                    assert named[input_name] == value


def test_canonical_defaults_match_first_cef_comfy_gate():
    for name in ("sdxl_txt2img_base_api.json", "sdxl_txt2img_single_lora_api.json"):
        workflow = load(name)
        sampler = workflow["3"]["inputs"]
        assert {key: sampler[key] for key in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise")} == {
            "seed": 42,
            "steps": 30,
            "cfg": 7,
            "sampler_name": "dpmpp_2m_sde",
            "scheduler": "karras",
            "denoise": 1,
        }
        assert workflow["5"]["inputs"] == {"width": 1024, "height": 1024, "batch_size": 1}


def test_workflows_use_only_core_nodes():
    expected = {
        "CheckpointLoaderSimple", "LoraLoader", "CLIPTextEncode",
        "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage",
    }
    for name in ("sdxl_txt2img_base_api.json", "sdxl_txt2img_single_lora_api.json"):
        assert {node["class_type"] for node in load(name).values()} <= expected
