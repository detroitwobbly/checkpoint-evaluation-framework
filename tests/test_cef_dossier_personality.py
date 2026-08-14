from checkpoint_evaluator.dossier import _balance_axis
from checkpoint_evaluator.dossier import _aesthetic_initiative
from checkpoint_evaluator.dossier import _conceptual_resolutions
from checkpoint_evaluator.dossier import _qualitative_axis
from checkpoint_evaluator.dossier import _observation_text
from checkpoint_evaluator.dossier import _mode_of_interpretation


def test_personality_axes_are_qualitative():
    assert _qualitative_axis(9.0) == "High"
    assert _qualitative_axis(7.5) == "Moderate"
    assert _qualitative_axis(None) == "Undetermined"
    assert _balance_axis(4, 1) == "High"
    assert _balance_axis(1, 4) == "Low"


def test_conceptual_resolution_families_are_ranked_from_evidence():
    records = [
        {"observation": "A couple embraces during a family reunion at home."},
        {"observation": "People gather in a domestic kitchen."},
        {"observation": "A couple resolves a difficult human interaction."},
        {"observation": "A commercial studio portrait and headshot."},
    ]

    resolved = _conceptual_resolutions(records)

    assert resolved[0] == "Human interactions"
    assert "Commercial portraiture" in resolved


def test_observation_text_excludes_rubric_wording():
    record = {
        "criteria_scores": [
            {
                "criterion": "Check for poster or typography behavior.",
                "evidence": "The image is a quiet domestic photograph.",
            }
        ],
        "visual_summary": "A family gathers in a kitchen.",
    }

    text = _observation_text(record)

    assert "family gathers" in text
    assert "poster" not in text


def test_aesthetic_initiative_uses_observed_decisions_and_tracks_tension():
    records = [
        {"test_id": "A", "visual_summary": "A painterly symbolic scene with atmospheric light.", "pass_fail": "pass"},
        {"test_id": "B", "visual_summary": "A cinematic interpretation with dramatic lighting.", "pass_fail": "fail"},
        {"test_id": "C", "visual_summary": "A literal product photograph.", "pass_fail": "pass"},
    ]
    prompts = {"A": "two people meeting", "B": "a ceramic cup", "C": "a literal product photograph"}

    label, note = _aesthetic_initiative(records, prompts)

    assert label == "High"
    assert "2 of 3" in note
    assert "1 of those records" in note


def test_mode_of_interpretation_is_categorical_and_evidence_based():
    records = [
        {"visual_summary": "A candid documentary photograph suitable for a magazine editorial."},
        {"visual_summary": "The scene has a restrained editorial presentation."},
        {"visual_summary": "A reportage-style candid view of daily life."},
        {"visual_summary": "A cinematic fantasy scene with dramatic lighting."},
        {"visual_summary": "A neutral product image."},
    ]

    label, note = _mode_of_interpretation(records)

    assert label == "Editorial / documentary"
    assert "3 of 5" in note
    assert "not a score" in note


def test_mode_of_interpretation_ignores_style_words_already_in_prompt():
    records = [
        {"test_id": "A", "visual_summary": "A painterly watercolor portrait."},
        {"test_id": "B", "visual_summary": "A candid documentary scene."},
    ]

    label, _note = _mode_of_interpretation(records, {"A": "a painterly watercolor portrait", "B": "two people meeting"})

    assert label == "Editorial / documentary"
