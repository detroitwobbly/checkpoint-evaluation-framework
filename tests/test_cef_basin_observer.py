import json
from pathlib import Path

from checkpoint_evaluator.basin_observer import basin_observer_response_format, run_basin_observer


def _observation(test_id: str) -> dict:
    return {
        "test_id": test_id,
        "primary_visual_subject": "document",
        "basin_membership_score": 85,
        "boundary_status": "branch",
        "distance_from_prototype": 70,
        "prototype_centrality": 70,
        "prototype_parent": "document",
        "representative_value": "useful_edge_probe",
        "boundary_value": 90,
        "evidence_for_membership": ["Framed document layout with seals."],
        "evidence_against_membership": ["No narrative figure is visible."],
        "attractor_types": ["certificate", "seal"],
        "dominant_attractor": "certificate",
        "dominant_visual_anchor": "document",
        "circular_emblematic_form": "yes",
        "narrative_figure_present": "no",
        "media_layout_present": "yes",
        "boundary_behavior": "branching",
        "boundary_branch": "official document",
        "uncertainties": ["Pseudo-text is unreadable."],
        "suggested_next_probes": ["diploma", "document seal"],
        "observer_confidence": "high",
        "recommendation": "accept_boundary_example",
        "summary": "The image appears to be an official-document branch of the basin.",
    }


class _MockBasinClient:
    model = "mock-basin-observer"

    def observe_image(self, _image_path, _directive, generation_metadata):
        return {**_observation(generation_metadata["test"]["id"]), "_raw_response": {"mock": True}}


def test_basin_observer_schema_is_strict_and_complete():
    schema = basin_observer_response_format()["json_schema"]["schema"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["basin_membership_score"]["maximum"] == 100
    assert "branch" in schema["properties"]["boundary_status"]["enum"]
    assert schema["properties"]["representative_value"]["enum"] == [
        "canonical_example",
        "good_teaching_example",
        "useful_edge_probe",
        "poor_representative",
        "unclear",
    ]
    assert "currency" in schema["properties"]["prototype_parent"]["enum"]


def test_basin_observer_exports_index(tmp_path: Path):
    run_root = tmp_path / "run_demo"
    test_root = run_root / "approved" / "checkpoint_demo" / "lora_none" / "SSP_SUPP_CERTIFICATE"
    test_root.mkdir(parents=True)
    image_path = test_root / "demo.png"
    image_path.write_bytes(b"fake")
    generation = {
        "checkpoint": {"id": "demo", "title": "demo"},
        "test": {
            "id": "SSP_SUPP_CERTIFICATE",
            "name": "Certificate",
            "prompt": "certificate",
            "metadata": {"source_module": "ssp_symbolic_presentation_boundary"},
        },
        "settings": {"seed": 12345},
        "request": {"prompt": "certificate"},
        "image_paths": [str(image_path)],
    }
    (test_root / "generation.json").write_text(json.dumps(generation), encoding="utf-8")
    (run_root / "generation_index.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "checkpoint_id": "demo",
                        "test_id": "SSP_SUPP_CERTIFICATE",
                        "test_name": "Certificate",
                        "test_root": str(test_root),
                        "image_paths": [str(image_path)],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    directive = tmp_path / "directive.txt"
    directive.write_text("Observe basin membership.", encoding="utf-8")

    index = run_basin_observer(
        run_root=run_root,
        directive_path=directive,
        client=_MockBasinClient(),
        observer_id="mock",
        label="Mock Basin Observer",
    )

    assert index["artifact_type"] == "basin_observer_index"
    assert index["observed_images"] == 1
    assert index["records"][0]["basin_membership_score"] == 85
    assert (run_root / "observer_runs" / "mock" / "basin_observer_index.json").exists()
