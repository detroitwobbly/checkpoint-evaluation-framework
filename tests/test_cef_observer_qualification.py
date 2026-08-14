import json

from checkpoint_evaluator.cli import build_parser
from checkpoint_evaluator.observer_qualification import build_observer_qualification


def test_observer_qualification_flags_scale_noncompliance(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    qwen_path = run_root / "qwen.json"
    mini_path = run_root / "mini.json"
    qwen_path.write_text(
        json.dumps(
            {
                "records": [
                    _record("TEST_1", 8.0, 0.95, "pass", "visible hand issue"),
                    _record("TEST_2", 7.0, 0.90, "conditional_pass", "minor object issue"),
                ]
            }
        ),
        encoding="utf-8",
    )
    mini_path.write_text(
        json.dumps(
            {
                "records": [
                    _record("TEST_1", 72.0, 34.0, "conditional_pass", "visible hand issue"),
                    _record("TEST_2", 66.0, 30.0, "conditional_pass", "new concern"),
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_observer_qualification(
        analyses=[("qwen", "Qwen", qwen_path), ("mini", "Mini", mini_path)],
        output_root=tmp_path / "qualification",
    )

    cards = {card["analysis_id"]: card for card in report["observer_cards"]}
    assert "judge" in cards["qwen"]["qualified_roles"]
    assert "judge" not in cards["mini"]["qualified_roles"]
    assert cards["mini"]["normalized_average_score"] == 6.9
    assert cards["mini"]["scale_compliance"]["overall_score_0_10"] == 0
    assert cards["mini"]["scale_compliance"]["evaluator_confidence_0_1"] == 0
    assert "scale_noncompliant" in cards["mini"]["observer_character"]
    assert any("No official scoring" in item for item in cards["mini"]["restrictions"])
    assert (tmp_path / "qualification" / "observer_qualification.html").exists()
    assert (tmp_path / "qualification" / "observer_qualification.md").exists()


def test_observer_qualification_merges_repeated_observer_ids(tmp_path):
    first = tmp_path / "qwen_first.json"
    second = tmp_path / "qwen_second.json"
    first.write_text(json.dumps({"records": [_record("A", 8.0, 0.9, "pass", "first")]}), encoding="utf-8")
    second.write_text(json.dumps({"records": [_record("B", 8.0, 0.9, "pass", "second")]}), encoding="utf-8")

    report = build_observer_qualification(
        analyses=[("qwen", "Qwen", first), ("qwen", "Qwen", second)],
        output_root=tmp_path / "qualification",
    )

    assert len(report["observer_cards"]) == 1
    assert report["observer_cards"][0]["records"] == 2
    assert len(report["observer_cards"][0]["analysis_paths"]) == 2


def test_observer_qualification_command_parses():
    args = build_parser().parse_args(
        [
            "observer-qualification",
            "--output-root",
            "cef_runs/observer_qualification/test",
            "--analysis",
            "qwen=Qwen=analysis.json",
        ]
    )

    assert args.command == "observer-qualification"
    assert args.output_root.name == "test"
    assert args.analysis == ["qwen=Qwen=analysis.json"]


def _record(test_id, score, confidence, pass_fail, observation):
    return {
        "test_id": test_id,
        "overall_score": score,
        "evaluator_confidence": confidence,
        "pass_fail": pass_fail,
        "warnings": [],
        "recommended_tags": [],
        "wildcard_observations": [
            {
                "category": "artifact",
                "severity": "minor",
                "observation": observation,
                "evidence": "visible pixels",
            }
        ],
        "semantic_observations": [],
    }
