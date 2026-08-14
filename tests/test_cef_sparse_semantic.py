import json
from pathlib import Path

from checkpoint_evaluator.models import TestSuite as SuiteModel
from checkpoint_evaluator.dossier import _sparse_semantic_profiles, _ssp_html
from checkpoint_evaluator.semantic_observer import (
    _replication_profiles,
    build_sparse_semantic_comparison,
    run_sparse_semantic_observer,
    semantic_agency_gradient_response_format,
    sparse_semantic_response_format,
)


def _observation(test_id: str) -> dict:
    return {
        "test_id": test_id,
        "observed_subject_class": "creature",
        "observed_subject_description": "A blue round creature faces the viewer.",
        "observed_medium": "digital illustration",
        "literalness": "literal",
        "symbolic_interpretation": "none",
        "prototype_class": "monster",
        "semantic_drift": "nearby_concept",
        "animacy_resolution": "agentive",
        "threat_bias": "benign",
        "null_semantic_occupancy": 0,
        "null_occupancy_applicable": False,
        "modifier_dominance": 0,
        "modifier_dominance_applicable": False,
        "collapse_type": "none",
        "semantic_residue_notes": "",
        "style_coherence": "high",
        "composition_clarity": "high",
        "narrative_clarity": "not_applicable",
        "negative_space_preservation": "not_applicable",
        "unsupported_inference_flags": [],
        "claim_discipline_flags": [],
        "uncertainties": [],
        "observer_confidence": "high",
        "summary": "The output resolves as a blue creature.",
    }


def test_manifest_metadata_round_trips():
    suite = SuiteModel.from_mapping({
        "suite_id": "SSP",
        "name": "SSP",
        "metadata": {"methodological_justification": "because"},
        "checkpoints": ["checkpoint.safetensors"],
        "tests": [{"id": "A", "prompt": "thing", "metadata": {"prompt_role": "anchor"}}],
    })

    result = suite.to_dict()

    assert result["metadata"]["methodological_justification"] == "because"
    assert result["tests"][0]["metadata"]["prompt_role"] == "anchor"


def test_sparse_semantic_schema_is_strict_and_complete():
    schema = sparse_semantic_response_format()["json_schema"]["schema"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["null_semantic_occupancy"]["maximum"] == 5
    assert "strongly_agentive" in schema["properties"]["animacy_resolution"]["enum"]


def test_semantic_agency_gradient_schema_extends_sparse_observer_fields():
    schema = semantic_agency_gradient_response_format()["json_schema"]["schema"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "embodiment_level" in schema["properties"]
    assert "human" in schema["properties"]["embodiment_level"]["enum"]
    assert "social_role" in schema["properties"]["agency_level"]["enum"]
    assert "editorial_portrait_with_lifestyle_pull" in schema["properties"]["presentation_grammar"]["enum"]
    assert schema["properties"]["sag_evidence_for"]["type"] == "array"


class _MockClient:
    model = "mock-semantic-observer"

    def observe_image(self, _image_path, _directive, generation_metadata):
        return {**_observation(generation_metadata["test"]["id"]), "_raw_response": {"mock": True}}


def test_semantic_observer_exports_phenotype_and_cpf_records(tmp_path: Path):
    run_root = tmp_path / "run_demo"
    test_root = run_root / "approved" / "checkpoint_demo" / "lora_none" / "SSP_T3_THING_ANCHOR"
    test_root.mkdir(parents=True)
    image_path = test_root / "demo.png"
    generation = {
        "checkpoint": {"id": "demo", "title": "sd\\demo.safetensors"},
        "lora_profile": {"id": "none", "loras": []},
        "test": {
            "id": "SSP_T3_THING_ANCHOR", "name": "Thing", "prompt": "thing",
            "metadata": {"source_module": "ssp", "prompt_role": "anchor", "semantic_anchor_type": "weak_anchor"},
        },
        "settings": {"seed": 12345},
        "request": {"prompt": "thing"},
        "image_paths": [str(image_path)],
    }
    (test_root / "generation.json").write_text(json.dumps(generation), encoding="utf-8")
    (run_root / "generation_index.json").write_text(json.dumps({"records": [{
        "checkpoint_id": "demo", "checkpoint_title": "sd\\demo.safetensors", "checkpoint_hash": "abc",
        "test_id": "SSP_T3_THING_ANCHOR", "test_root": str(test_root), "image_paths": [str(image_path)],
    }]}), encoding="utf-8")
    directive = tmp_path / "directive.txt"
    directive.write_text("Observe visible evidence.", encoding="utf-8")

    index = run_sparse_semantic_observer(run_root, directive, _MockClient(), "mock", "Mock Observer")

    output = run_root / "observer_runs" / "mock"
    assert index["observed_images"] == 1
    assert index["semantic_phenotype"]["dominant_prototype_classes"][0] == {"label": "monster", "count": 1}
    behavioral = json.loads((output / "behavioral_observation_records.json").read_text(encoding="utf-8"))
    assert behavioral["records"][0]["evaluator_role"] == "score_free_semantic_observer"
    assert behavioral["records"][0]["prompt_metadata"]["semantic_anchor_type"] == "weak_anchor"
    assert (output / "ssp_report.html").exists()


def test_cross_checkpoint_comparison_preserves_descriptive_labels(tmp_path: Path):
    paths = []
    for checkpoint, prototype in (("alpha", "monster"), ("beta", "artifact")):
        path = tmp_path / checkpoint / "ssp_observer_index.json"
        path.parent.mkdir()
        record = {"checkpoint_id": checkpoint, "test_id": "THING", "prompt": "thing", **_observation("THING")}
        record["prototype_class"] = prototype
        path.write_text(json.dumps({"observed_images": 1, "failures": 0, "semantic_phenotype": {}, "records": [record]}), encoding="utf-8")
        paths.append(path)

    comparison = build_sparse_semantic_comparison(paths, tmp_path / "comparison", "SSP Comparison")

    observations = comparison["prompt_comparisons"][0]["observations"]
    assert {item["prototype_class"] for item in observations} == {"monster", "artifact"}
    assert (tmp_path / "comparison" / "ssp_comparison.html").exists()


def test_dossier_attachment_keeps_ssp_separate_from_scored_summary(tmp_path: Path):
    index_path = tmp_path / "ssp" / "ssp_observer_index.json"
    index_path.parent.mkdir()
    index_path.write_text(json.dumps({
        "artifact_type": "sparse_semantic_observer_index",
        "observer": {"id": "qwen", "label": "Qwen SSP"},
        "observed_images": 59,
        "failures": 0,
        "methodological_justification": "Sparse prompts expose prototype resolution.",
        "semantic_phenotype": {"dominant_prototype_classes": [{"label": "artifact", "count": 10}]},
    }), encoding="utf-8")

    profiles = _sparse_semantic_profiles([index_path], tmp_path / "dossier")
    dossier = {"sparse_semantic_profiles": profiles, "summary": {"image_count": 183}}
    html = _ssp_html(dossier)

    assert dossier["summary"]["image_count"] == 183
    assert profiles[0]["observed_images"] == 59
    assert "Qwen SSP" in html
    assert "correctness scores" in html


def test_replication_profiles_report_stable_and_mixed_prototypes():
    records = [
        {"prototype_class": "texture", "literalness": "abstract", "null_occupancy_applicable": True, "null_semantic_occupancy": 1, "prompt_metadata": {"replication_group": "NULL_A"}},
        {"prototype_class": "texture", "literalness": "abstract", "null_occupancy_applicable": True, "null_semantic_occupancy": 2, "prompt_metadata": {"replication_group": "NULL_A"}},
        {"prototype_class": "human", "literalness": "literal", "null_occupancy_applicable": True, "null_semantic_occupancy": 4, "prompt_metadata": {"replication_group": "NULL_B"}},
        {"prototype_class": "artifact", "literalness": "literal", "null_occupancy_applicable": True, "null_semantic_occupancy": 3, "prompt_metadata": {"replication_group": "NULL_B"}},
    ]

    profiles = {item["replication_group"]: item for item in _replication_profiles(records)}

    assert profiles["NULL_A"]["prototype_stability"] == "stable"
    assert profiles["NULL_B"]["prototype_stability"] == "mixed"
