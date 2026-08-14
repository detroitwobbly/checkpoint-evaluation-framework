import json

from checkpoint_evaluator.reporting import build_report


def test_build_report_writes_html_and_json(tmp_path):
    run_root = tmp_path / "run_report"
    run_root.mkdir()
    (run_root / "generation_index.json").write_text(
        json.dumps({"records": [{"image_paths": ["image.png"]}]}),
        encoding="utf-8",
    )
    (run_root / "analysis_index.json").write_text(
        json.dumps(
            {
                "run_id": "run_report",
                "analyzed_images": 1,
                "checkpoint_summary": {"ckpt": {"average_score": 8.0, "count": 1}},
                "test_summary": {"test": {"average_score": 8.0, "count": 1}},
                "records": [
                    {
                        "checkpoint_id": "ckpt",
                        "lora_profile_id": "none",
                        "test_id": "test",
                        "test_name": "Test",
                        "image_path": str(run_root / "image.png"),
                        "analysis_path": str(run_root / "image_analysis.json"),
                        "overall_score": 8.0,
                        "criteria_scores": [{"criterion": "visible", "score": 8.0, "evidence": "visible"}],
                        "rubric_scores": {
                            "prompt_adherence": 8.0,
                            "composition": 7.0,
                            "anatomy": 6.0,
                            "artifact_severity": 2.0,
                        },
                        "pass_fail": "pass",
                        "recommended_tags": ["good_composition"],
                        "wildcard_observations": [
                            {
                                "category": "artifact",
                                "severity": "minor",
                                "confidence": 0.8,
                                "observation": "small edge artifact",
                                "evidence": "visible near the border",
                                "suggested_new_criterion": "no obvious border artifacts",
                            }
                        ],
                        "semantic_observations": [
                            {
                                "category": "subject_identity",
                                "severity": "major",
                                "confidence": 0.9,
                                "observation": "subject identity mismatch",
                                "evidence": "the small creature reads as a child rather than a fairy",
                                "suggested_new_criterion": "subject reads as the intended creature type",
                            }
                        ],
                        "intent_failure_check": {
                            "passes_human_intent": False,
                            "confidence": 0.85,
                            "failure_modes": ["subject_identity"],
                            "explanation": "the subject reads as the wrong creature type",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_report(run_root)

    assert report["generated_images"] == 1
    assert (run_root / "report.json").exists()
    html = (run_root / "report.html").read_text(encoding="utf-8")
    assert "CEF Report" in html
    assert "visible" in html
    assert "Wildcard Observations" in html
    assert "small edge artifact" in html
    assert "Semantic Observations" in html
    assert "subject identity mismatch" in html
    assert "Intent Failure Check" in html
    assert "the subject reads as the wrong creature type" in html
    assert "Rubric Averages" in html
    assert "prompt_adherence" in html
