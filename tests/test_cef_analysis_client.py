import json

from checkpoint_evaluator.analysis_client import _normalize_chat_completions_endpoint
from checkpoint_evaluator.analysis_client import _parse_json_content
from checkpoint_evaluator.analysis_client import _response_format_schema
from checkpoint_evaluator.analysis import _build_analysis_report
from checkpoint_evaluator.analysis import _filtered_records
from checkpoint_evaluator.analysis import _reference_comparison


def test_qwen_endpoint_normalization():
    assert _normalize_chat_completions_endpoint("http://host:1234") == "http://host:1234/v1/chat/completions"
    assert _normalize_chat_completions_endpoint("http://host:1234/v1") == "http://host:1234/v1/chat/completions"
    assert (
        _normalize_chat_completions_endpoint("http://host:1234/v1/chat/completions")
        == "http://host:1234/v1/chat/completions"
    )


def test_parse_json_content_strips_markdown_fence():
    parsed = _parse_json_content('```json\n{"overall_score": 8.5}\n```')

    assert parsed["overall_score"] == 8.5


def test_analysis_report_averages_scores():
    report = _build_analysis_report(
        "run_test",
        [
            {"checkpoint_id": "a", "test_id": "t1", "overall_score": 8},
            {"checkpoint_id": "a", "test_id": "t1", "overall_score": 6},
            {"checkpoint_id": "b", "test_id": "t1", "overall_score": 5},
        ],
    )

    assert json.dumps(report)
    assert report["checkpoint_summary"]["a"]["average_score"] == 7.0
    assert report["test_summary"]["t1"]["count"] == 3


def test_filtered_records_keeps_requested_test_ids_case_insensitive():
    records = [{"test_id": "TEST_001"}, {"test_id": "TEST_002"}]

    filtered = _filtered_records(records, ["test_002"])

    assert filtered == [{"test_id": "TEST_002"}]


def test_filtered_records_rejects_missing_test_ids():
    records = [{"test_id": "TEST_001"}]

    try:
        _filtered_records(records, ["TEST_999"])
    except ValueError as exc:
        assert "TEST_999" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing test ID.")


def test_response_schema_requires_discovery_observations():
    schema = _response_format_schema()["json_schema"]["schema"]

    assert "wildcard_observations" in schema["required"]
    assert "semantic_observations" in schema["required"]
    assert "intent_failure_check" in schema["required"]
    assert "rubric_scores" in schema["required"]
    assert "recommended_tags" in schema["required"]
    assert "evaluator_confidence" in schema["required"]
    wildcard = schema["properties"]["wildcard_observations"]["items"]
    assert wildcard["properties"]["category"]["enum"] == [
        "anatomy",
        "composition",
        "object",
        "scale",
        "style",
        "artifact",
        "physics",
        "physics_failure",
        "perspective_failure",
        "unprompted_nudity",
        "prior_leakage",
        "age_bias",
        "beauty_bias",
        "body_bias",
        "clothing_bias",
        "species_bias",
        "lora_checkpoint_incompatibility",
        "lora_overpowering",
        "lora_resistance",
        "lora_stylization_drift",
        "lora_identity_suppression",
        "prompt_conflict",
        "safety",
        "other",
    ]
    semantic = schema["properties"]["semantic_observations"]["items"]
    assert semantic["required"] == [
        "category",
        "severity",
        "confidence",
        "observation",
        "evidence",
        "suggested_new_criterion",
    ]
    assert "species_mismatch" in semantic["properties"]["category"]["enum"]
    assert "physics" in semantic["properties"]["category"]["enum"]
    intent = schema["properties"]["intent_failure_check"]
    assert intent["required"] == ["passes_human_intent", "confidence", "failure_modes", "explanation"]
    assert "ordinary_animal_substitution" in intent["properties"]["failure_modes"]["items"]["enum"]
    rubric = schema["properties"]["rubric_scores"]
    assert "artifact_severity" in rubric["required"]
    assert "identity_retention" in rubric["required"]
    assert rubric["properties"]["identity_retention"]["type"] == ["number", "null"]
    assert "lora_integration" in rubric["required"]
    assert rubric["properties"]["lora_integration"]["type"] == ["number", "null"]


def test_analysis_report_summarizes_wildcards_without_affecting_scores():
    report = _build_analysis_report(
        "run_test",
        [
            {
                "checkpoint_id": "a",
                "test_id": "t1",
                "overall_score": 8,
                "wildcard_observations": [
                    {
                        "category": "object",
                        "severity": "major",
                        "observation": "extra weapon visible",
                        "evidence": "a second blade is visible",
                        "suggested_new_criterion": "only one primary weapon is visible",
                    }
                ],
            }
        ],
    )

    assert report["checkpoint_summary"]["a"]["average_score"] == 8.0
    assert report["wildcard_summary"]["total_observations"] == 1
    assert report["wildcard_summary"]["by_category"]["object"] == 1
    assert report["wildcard_summary"]["major_issues"][0]["test_id"] == "t1"


def test_analysis_report_summarizes_semantics_without_affecting_scores():
    report = _build_analysis_report(
        "run_test",
        [
            {
                "checkpoint_id": "a",
                "test_id": "t1",
                "overall_score": 9,
                "semantic_observations": [
                    {
                        "category": "scale",
                        "severity": "major",
                        "confidence": 0.9,
                        "observation": "small fairy reads as human sized",
                        "evidence": "the fairy occupies most of the log",
                        "suggested_new_criterion": "fairy remains insect-sized relative to the environment",
                    }
                ],
            }
        ],
    )

    assert report["checkpoint_summary"]["a"]["average_score"] == 9.0
    assert report["semantic_summary"]["total_observations"] == 1
    assert report["semantic_summary"]["by_category"]["scale"] == 1
    assert report["semantic_summary"]["by_severity"]["major"] == 1
    assert report["semantic_summary"]["major_issues"][0]["observation"] == "small fairy reads as human sized"


def test_analysis_report_summarizes_intent_failures_without_affecting_scores():
    report = _build_analysis_report(
        "run_test",
        [
            {
                "checkpoint_id": "a",
                "test_id": "t1",
                "overall_score": 9,
                "intent_failure_check": {
                    "passes_human_intent": False,
                    "confidence": 0.85,
                    "failure_modes": ["ordinary_animal_substitution", "wrong_subject_trait"],
                    "explanation": "the large creature reads as a winged mouse",
                },
            }
        ],
    )

    assert report["checkpoint_summary"]["a"]["average_score"] == 9.0
    assert report["intent_failure_summary"]["failed_intent_count"] == 1
    assert report["intent_failure_summary"]["failure_modes"]["wrong_subject_trait"] == 1


def test_analysis_report_summarizes_rubric_scores():
    report = _build_analysis_report(
        "run_test",
        [
            {
                "checkpoint_id": "a",
                "test_id": "t1",
                "overall_score": 8,
                "rubric_scores": {"anatomy": 7, "artifact_severity": 2},
            },
            {
                "checkpoint_id": "a",
                "test_id": "t2",
                "overall_score": 6,
                "rubric_scores": {"anatomy": 5, "artifact_severity": 4},
            },
        ],
    )

    assert report["rubric_summary"]["anatomy"]["average_score"] == 6.0
    assert report["rubric_summary"]["artifact_severity"]["average_score"] == 3.0


def test_analysis_report_summarizes_evaluator_confidence():
    report = _build_analysis_report(
        "run_test",
        [
            {"checkpoint_id": "a", "test_id": "t1", "overall_score": 3, "evaluator_confidence": 0.9},
            {"checkpoint_id": "a", "test_id": "t2", "overall_score": 8, "evaluator_confidence": 0.5},
        ],
    )

    summary = report["evaluator_confidence_summary"]
    assert summary["average_confidence"] == 0.7
    assert summary["high_confidence_low_scores"][0]["test_id"] == "t1"


def test_analysis_report_summarizes_reference_assisted_records():
    report = _build_analysis_report(
        "run_test",
        [
            {
                "checkpoint_id": "a",
                "test_id": "horse",
                "overall_score": 7,
                "reference_images": [{"label": "horse_conformation_contact_sheet_v1"}],
            },
            {"checkpoint_id": "a", "test_id": "portrait", "overall_score": 8},
        ],
    )

    summary = report["reference_assisted_summary"]
    assert summary["assisted_image_count"] == 1
    assert summary["assisted_test_ids"] == ["horse"]
    assert summary["by_reference"]["horse_conformation_contact_sheet_v1"] == 1


def test_reference_comparison_tracks_delta_and_new_observations(tmp_path):
    comparison = _reference_comparison(
        assisted_analysis={
            "overall_score": 8.5,
            "failures": ["front left cannon alignment differs from reference"],
            "wildcard_observations": [
                {
                    "observation": "fetlock angle appears more collapsed than the reference examples",
                }
            ],
        },
        unassisted_analysis={
            "overall_score": 7.5,
            "failures": ["minor hoof asymmetry"],
            "wildcard_observations": [],
        },
        references=[{"label": "horse_reference_v1"}],
        unassisted_path=tmp_path / "unassisted.json",
    )

    assert comparison["reference_used"] is True
    assert comparison["reference_id"] == "horse_reference_v1"
    assert comparison["unassisted_score"] == 7.5
    assert comparison["assisted_score"] == 8.5
    assert comparison["score_delta"] == 1.0
    assert "front left cannon alignment differs from reference" in comparison["new_observations"]
    assert "fetlock angle appears more collapsed than the reference examples" in comparison["new_observations"]
