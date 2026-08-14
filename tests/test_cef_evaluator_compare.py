import json
from pathlib import Path

from checkpoint_evaluator.evaluator_compare import (
    build_evaluator_comparison,
    build_judge_auditor_review,
    parse_analysis_spec,
    snapshot_analysis,
)
from checkpoint_evaluator.cli import build_parser


def test_snapshot_analysis_copies_current_index(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "analysis_index.json").write_text(
        json.dumps({"run_id": "run", "records": []}),
        encoding="utf-8",
    )
    (run_root / "report.json").write_text(json.dumps({"run_id": "run"}), encoding="utf-8")

    target = snapshot_analysis(
        run_root,
        "Qwen 2.5 VL",
        "Qwen Baseline",
        model_name="qwen2.5-vl",
        endpoint="http://127.0.0.1:1234",
        directive_used="protovision_qwen_directive.txt",
    )

    assert target == run_root / "analysis_runs" / "qwen_2_5_vl" / "analysis_index.json"
    assert json.loads(target.read_text(encoding="utf-8"))["run_id"] == "run"
    metadata = json.loads((target.parent / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["analysis_id"] == "qwen_2_5_vl"
    assert metadata["label"] == "Qwen Baseline"
    assert metadata["model_name"] == "qwen2.5-vl"
    assert metadata["endpoint"] == "http://127.0.0.1:1234"
    assert metadata["directive_used"] == "protovision_qwen_directive.txt"
    assert (target.parent / "report.json").exists()


def test_parse_analysis_spec_supports_optional_label():
    assert parse_analysis_spec("qwen=analysis.json") == ("qwen", "qwen", Path("analysis.json"))
    assert parse_analysis_spec("internvl=InternVL 14B=analysis.json") == (
        "internvl",
        "InternVL 14B",
        Path("analysis.json"),
    )


def test_serve_report_command_parses_run_root_and_port():
    args = build_parser().parse_args(
        [
            "serve-report",
            "--run-root",
            "cef_runs/run",
            "--port",
            "8776",
        ]
    )

    assert args.command == "serve-report"
    assert args.port == 8776
    assert args.bind == "127.0.0.1"


def test_build_evaluator_comparison_writes_side_by_side_report(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    image_path = run_root / "image.png"
    image_path.write_bytes(b"fake image bytes")
    qwen = _analysis_index(run_root, image_path, 7.0, "artifact", "small artifact")
    intern = _analysis_index(run_root, image_path, 8.0, "unprompted_nudity", "nudity noted as prior leakage")
    qwen_path = run_root / "qwen.json"
    intern_path = run_root / "intern.json"
    qwen_path.write_text(json.dumps(qwen), encoding="utf-8")
    intern_path.write_text(json.dumps(intern), encoding="utf-8")

    output = build_evaluator_comparison(
        run_root,
        [("qwen", "Qwen", qwen_path), ("internvl", "InternVL", intern_path)],
    )

    html = output.read_text(encoding="utf-8")
    assert "CEF Evaluator Comparison" in html
    assert "TEST_001_FACE_NEUTRAL" in html
    assert "Qwen" in html
    assert "InternVL" in html
    assert "small artifact" in html
    assert "nudity noted as prior leakage" in html
    assert "Reference delta" in html
    assert "Evaluator Metrics" in html
    assert "Score Variance" in html
    assert "Pass/fail disagreement count" in html
    assert "Evaluator Personality Profile" in html


def test_build_judge_auditor_review_uses_tiered_rules(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    image_path = run_root / "image.png"
    image_path.write_bytes(b"fake image bytes")
    primary = {
        "checkpoint_summary": {"ckpt": {"average_score": 8.0}},
        "records": [
            _record("TEST_PASS_FAIL", image_path, 8.0, "pass"),
            _record("TEST_CALIBRATION", image_path, 8.0, "pass"),
            _record("TEST_NUDITY_NOTE", image_path, 8.0, "pass"),
        ],
    }
    auditor = {
        "records": [
            _record("TEST_PASS_FAIL", image_path, 5.0, "fail"),
            _record("TEST_CALIBRATION", image_path, 7.0, "conditional_pass"),
            _record(
                "TEST_NUDITY_NOTE",
                image_path,
                8.0,
                "pass",
                wildcard=[{"category": "unprompted_nudity", "severity": "major", "observation": "nude subject", "evidence": "visible"}],
            ),
        ],
    }
    primary_path = run_root / "primary.json"
    auditor_path = run_root / "auditor.json"
    primary_path.write_text(json.dumps(primary), encoding="utf-8")
    auditor_path.write_text(json.dumps(auditor), encoding="utf-8")

    json_path, md_path = build_judge_auditor_review(
        run_root,
        ("primary", "Primary", primary_path),
        ("auditor", "Auditor", auditor_path),
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    tiers = {record["test_id"]: record["review_tier"] for record in payload["records"]}
    assert tiers["TEST_PASS_FAIL"] == "A_REVIEW_REQUIRED"
    assert tiers["TEST_CALIBRATION"] == "C_CALIBRATION_REVIEW"
    assert tiers["TEST_NUDITY_NOTE"] == "NONE"
    assert md_path.exists()


def _analysis_index(run_root, image_path, score, wildcard_category, wildcard_text):
    return {
        "run_id": "run",
        "analyzed_images": 1,
        "intent_failure_summary": {"failed_intent_count": 0},
        "reference_assisted_summary": {"average_score_delta": 1.0},
        "evaluator_confidence_summary": {"average_confidence": 0.75},
        "wildcard_summary": {"total_observations": 1},
        "semantic_summary": {"total_observations": 0},
        "records": [
            {
                "test_id": "TEST_001_FACE_NEUTRAL",
                "test_name": "Face Neutral",
                "image_path": str(image_path),
                "overall_score": score,
                "pass_fail": "pass",
                "evaluator_confidence": 0.75,
                "rubric_scores": {
                    "prompt_adherence": score,
                    "anatomy": score,
                    "artifact_severity": 1,
                    "identity_retention": None,
                    "lora_integration": None,
                },
                "intent_failure_check": {
                    "passes_human_intent": True,
                    "confidence": 0.8,
                    "failure_modes": [],
                    "explanation": "passes",
                },
                "reference_comparison": {"score_delta": 1.0},
                "recommended_tags": ["good_face"],
                "strengths": ["clear face"],
                "failures": [],
                "wildcard_observations": [
                    {
                        "category": wildcard_category,
                        "severity": "minor",
                        "observation": wildcard_text,
                    }
                ],
                "semantic_observations": [],
            }
        ],
    }


def _record(test_id, image_path, score, pass_fail, wildcard=None):
    return {
        "test_id": test_id,
        "test_name": test_id,
        "image_path": str(image_path),
        "overall_score": score,
        "pass_fail": pass_fail,
        "intent_failure_check": {"passes_human_intent": True, "confidence": 0.8, "failure_modes": [], "explanation": ""},
        "rubric_scores": {
            "prompt_adherence": score,
            "composition": score,
            "anatomy": score,
            "environment_quality": score,
            "artifact_severity": 1,
        },
        "wildcard_observations": wildcard or [],
        "semantic_observations": [],
    }
