import json

from checkpoint_evaluator.reporting import build_report


def test_build_report_writes_html_and_json(tmp_path):
    run_root = tmp_path / "run_report"
    run_root.mkdir()
    (run_root / "generation_index.json").write_text(
        json.dumps({"records": [{"image_paths": ["image.png"]}]}),
        encoding="utf-8",
    )
    (run_root / "run_manifest.json").write_text(
        json.dumps(
            {
                "suite_id": "CONTROLLED_DEMO",
                "name": "Controlled Materials Demo",
                "metadata": {
                    "method": "fixed-seed counterfactuals",
                    "intended_scope": "portfolio demonstration",
                    "research_question": "Can the checkpoints follow the controlled change?",
                    "evaluation_cautions": ["Directional judgments require human review."],
                    "checkpoint_provenance": [
                        {
                            "id": "ckpt",
                            "display_name": "Example Checkpoint",
                            "creator": "Example Creator",
                            "license": "Example License",
                            "sha256": "abc123",
                            "source": "https://example.com/model",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    (run_root / "human_adjudication.json").write_text(
        json.dumps(
            {
                "status": "approved",
                "approved_by": "Human Reviewer",
                "approved_at": "2026-08-14T16:35:36-04:00",
                "summary": {
                    "records": 1,
                    "human_pass": 0,
                    "human_fail": 1,
                    "machine_agreements": 0,
                },
                "records": [
                    {
                        "checkpoint_id": "ckpt",
                        "test_id": "test",
                        "machine_outcome": "pass",
                        "human_outcome": "fail",
                        "agreement": False,
                        "observation": "Human review found a visible contradiction.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_root / "analysis_index.json").write_text(
        json.dumps(
            {
                "run_id": "run_report",
                "evaluator": {
                    "client": "QwenEvaluationClient",
                    "endpoint": "http://127.0.0.1:1234/v1/chat/completions",
                    "model": "vision-model",
                    "temperature": 0.1,
                    "max_tokens": 3000,
                    "response_mode": "json",
                    "structured_response_requested": True,
                },
                "directive": {"name": "evaluator.txt", "sha256": "abc123"},
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
    assert "Controlled Materials Demo" in html
    assert "Experiment at a Glance" in html
    assert "machine observations, not ground truth" in html
    assert "Directional judgments require human review." in html
    assert "Can the checkpoints follow the controlled change?" in html
    assert "Checkpoint Provenance" in html
    assert "Example Checkpoint" in html
    assert "Controlled Manifold: 1 Generated Image" in html
    assert 'class="contact-sheet"' in html
    assert "Human Adjudication" in html
    assert "0 pass / 1 fail" in html
    assert "Human review found a visible contradiction." in html
    assert "visible" in html
    assert "Wildcard Observations" in html
    assert "small edge artifact" in html
    assert "Semantic Observations" in html
    assert "subject identity mismatch" in html
    assert "Intent Failure Check" in html
    assert "the subject reads as the wrong creature type" in html
    assert "Rubric Averages" in html
    assert "prompt_adherence" in html
    assert "Evaluator Provenance" in html
    assert "vision-model" in html
    assert "evaluator.txt" in html
    assert report["evaluator"]["model"] == "vision-model"
    assert report["suite_name"] == "Controlled Materials Demo"
