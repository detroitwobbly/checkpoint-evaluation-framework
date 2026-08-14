import json
from pathlib import Path

from scripts.build_run_pipeline_review import build_review


def test_run_pipeline_review_builds_dashboard_and_links_artifacts(tmp_path: Path):
    run_root = tmp_path / "run_demo"
    run_root.mkdir()
    report_assets = run_root / "report_assets"
    report_assets.mkdir()
    (report_assets / "contact_sheet.jpg").write_bytes(b"not really a jpg")

    generation_index = {
        "records": [
            {
                "checkpoint_id": "demo_checkpoint",
                "test_id": "SAG_001",
                "test_root": str(run_root / "approved" / "SAG_001"),
                "image_paths": [str(run_root / "approved" / "SAG_001" / "image.png")],
            }
        ]
    }
    (run_root / "generation_index.json").write_text(json.dumps(generation_index), encoding="utf-8")
    (run_root / "png_provenance_index.json").write_text(
        json.dumps({
            "artifact_type": "png_provenance_index",
            "image_count": 1,
            "failure_count": 0,
            "records": [{"png_text_keys": ["parameters"], "parsed_parameters": {"contributors": {"loras": ["A"]}}}],
        }),
        encoding="utf-8",
    )

    observer_root = run_root / "observer_runs" / "qwen_sag"
    observer_root.mkdir(parents=True)
    observer_index = {
        "artifact_type": "sparse_semantic_observer_index",
        "observer_schema": "semantic-agency-gradient",
        "observer": {"id": "qwen", "label": "Qwen SAG"},
        "observed_images": 1,
        "failures": 0,
        "records": [
            {
                "test_id": "SAG_001",
                "prompt": "presence",
                "prototype_class": "human",
                "observer_confidence": "low",
                "embodiment_level": "human",
                "agency_level": "person",
                "presentation_grammar": "editorial_portrait",
                "summary": "A human subject is primary.",
            }
        ],
    }
    (observer_root / "ssp_observer_index.json").write_text(json.dumps(observer_index), encoding="utf-8")
    (observer_root / "ssp_report.html").write_text("<html>ssp</html>", encoding="utf-8")
    (observer_root / "behavioral_observation_records.json").write_text(json.dumps({"records": []}), encoding="utf-8")

    summary_root = observer_root / "sag_summary"
    summary_root.mkdir()
    (summary_root / "semantic_agency_gradient_summary.json").write_text(
        json.dumps({"artifact_type": "semantic_agency_gradient_summary", "overall": {"record_count": 1, "embodiment_counts": {"human": 1}}}),
        encoding="utf-8",
    )
    (summary_root / "semantic_agency_gradient_review.html").write_text("<html>sag</html>", encoding="utf-8")

    routing_root = observer_root / "routing_summary"
    routing_root.mkdir()
    (routing_root / "phenotype_routing_summary.json").write_text(
        json.dumps({"artifact_type": "phenotype_routing_summary", "recommendations": [{"id": "human_default"}]}),
        encoding="utf-8",
    )

    review = build_review(run_root)

    assert review["generation"]["image_count"] == 1
    assert review["provenance"]["status"] == "present"
    assert review["observation"][0]["observer_schema"] == "semantic-agency-gradient"
    assert review["human_review"]["records_needing_review"] == 1
    assert (run_root / "run_pipeline_review.json").exists()
    html = (run_root / "run_pipeline_review.html").read_text(encoding="utf-8")
    assert "CEF Run Pipeline Review" in html
    assert "Qwen SAG" in html
    assert "semantic_agency_gradient_summary" in html
