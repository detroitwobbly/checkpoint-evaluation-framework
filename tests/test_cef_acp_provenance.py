import json
from pathlib import Path

from PIL import Image, PngImagePlugin

from checkpoint_evaluator.provenance import extract_png_provenance, extract_run_png_provenance, parse_forge_parameters


def test_parse_forge_parameters_extracts_common_fields():
    parameters = (
        "example subject laboratory portrait\n"
        "Negative prompt: low quality, blurry\n"
        "Steps: 30, Sampler: DPM++ 2M, Schedule type: Karras, CFG scale: 6, Seed: 123, "
        "Size: 1024x1024, Model hash: abc123, Model: ExampleModel, Version: f2.0"
    )

    parsed = parse_forge_parameters(parameters)

    assert parsed["prompt"] == "example subject laboratory portrait"
    assert parsed["negative_prompt"] == "low quality, blurry"
    assert parsed["settings"]["steps"] == 30
    assert parsed["settings"]["sampler"] == "DPM++ 2M"
    assert parsed["settings"]["schedule_type"] == "Karras"
    assert parsed["settings"]["cfg_scale"] == 6
    assert parsed["settings"]["seed"] == 123
    assert parsed["settings"]["model"] == "ExampleModel"


def test_parse_forge_parameters_preserves_extension_contributors():
    parameters = (
        "portrait prompt\n"
        "Negative prompt: none\n"
        "Steps: 28, Sampler: DPM++ 2M, CFG scale: 5, Seed: 999, Size: 1024x1024, "
        "ADetailer model: face_yolov8n.pt, ADetailer confidence: 0.3, "
        "ControlNet 0 module: openpose_full, ControlNet 0 model: controlnet-openpose-sdxl, "
        "ControlNet 0 weight: 0.75, Lora hashes: \"adapter_alpha: 0ea55c3dd2f6, adapter_beta: d969831d4087\", "
        "Mystery Extension Knob: goblin mode, Version: neo-2.24"
    )

    parsed = parse_forge_parameters(parameters)

    assert parsed["raw_key_values"]["ADetailer model"] == "face_yolov8n.pt"
    assert parsed["contributors"]["adetailer"]["ADetailer confidence"] == "0.3"
    assert parsed["contributors"]["controlnet"]["ControlNet 0 module"] == "openpose_full"
    assert parsed["contributors"]["lora"]["Lora hashes"] == "adapter_alpha: 0ea55c3dd2f6, adapter_beta: d969831d4087"
    assert parsed["lora_hashes"] == [
        {"name": "adapter_alpha", "hash": "0ea55c3dd2f6"},
        {"name": "adapter_beta", "hash": "d969831d4087"},
    ]
    assert parsed["unknown_key_values"]["Mystery Extension Knob"] == "goblin mode"


def test_parse_forge_parameters_structures_controlnet_unit_blob():
    parameters = (
        "portrait prompt\n"
        "Negative prompt: none\n"
        "Steps: 38, Sampler: DPM++ 2M SDE, CFG scale: 6, Seed: 4042239949, "
        "ControlNet 0: Module: CLIP-ViT-H (IPAdapter), Model: ip-adapter-plus-face_sdxl_vit-h, "
        "Weight: 0.25, Resize Mode: Just Resize, Processor Res: 0.5, Threshold A: 0.5, "
        "Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: False, "
        "Control Mode: Balanced, Hr Option: Both, Version: neo-2.26"
    )

    parsed = parse_forge_parameters(parameters)

    assert parsed["contributors"]["controlnet"]["ControlNet 0"].startswith("Module: CLIP-ViT-H")
    assert parsed["controlnet_units"][0]["unit"] == 0
    assert parsed["controlnet_units"][0]["parameters"]["module"] == "CLIP-ViT-H (IPAdapter)"
    assert parsed["controlnet_units"][0]["parameters"]["model"] == "ip-adapter-plus-face_sdxl_vit-h"
    assert parsed["controlnet_units"][0]["parameters"]["weight"] == 0.25
    assert parsed["controlnet_units"][0]["parameters"]["guidance_end"] == 1.0
    assert parsed["controlnet_units"][0]["appears_to_use_ipadapter"] is True


def test_extract_png_provenance_preserves_raw_text_and_parsed_fields(tmp_path: Path):
    image_path = tmp_path / "forge.png"
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text(
        "parameters",
        "test prompt\nNegative prompt: none\nSteps: 24, Sampler: Euler a, CFG scale: 4.5, Seed: 42, Size: 64x64",
    )
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(image_path, pnginfo=pnginfo)

    record = extract_png_provenance(image_path)

    assert record["image"]["width"] == 64
    assert record["png_text"]["parameters"].startswith("test prompt")
    assert record["parsed_parameters"]["settings"]["steps"] == 24
    assert len(record["image_sha256"]) == 64


def test_extract_run_png_provenance_uses_generation_index(tmp_path: Path):
    run_root = tmp_path / "run"
    test_root = run_root / "approved" / "checkpoint_demo" / "lora_none" / "ACP_01"
    test_root.mkdir(parents=True)
    image_path = test_root / "image.png"
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("parameters", "prompt\nSteps: 1, Sampler: Euler, CFG scale: 1, Seed: 7, Size: 8x8")
    Image.new("RGB", (8, 8)).save(image_path, pnginfo=pnginfo)
    (test_root / "generation.json").write_text(
        json.dumps(
            {
                "checkpoint": {"id": "demo", "title": "demo"},
                "lora_profile": {"id": "none", "loras": []},
                "test": {"id": "ACP_01", "prompt": "prompt"},
                "settings": {"seed": 7},
                "forge_info": {"sd_model_name": "demo"},
            }
        ),
        encoding="utf-8",
    )
    (run_root / "generation_index.json").write_text(
        json.dumps({"records": [{"image_paths": [str(image_path)]}]}),
        encoding="utf-8",
    )

    index = extract_run_png_provenance(run_root)

    assert index["image_count"] == 1
    assert index["failure_count"] == 0
    assert index["records"][0]["cef_generation"]["test"]["id"] == "ACP_01"
    assert (run_root / "png_provenance_index.json").exists()
