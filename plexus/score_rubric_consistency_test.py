import json

from plexus.score_rubric_consistency import (
    ScoreRubricConsistencyRequest,
    ScoreRubricConsistencyService,
    merge_consistency_result_into_parameters,
)


def test_score_rubric_consistency_service_returns_compact_payload():
    def invoke(prompt: str, model: str) -> str:
        assert "Score code/configuration" in prompt
        assert model == "test-model"
        return json.dumps(
            {
                "status": "potential_conflict",
                "paragraph": (
                    "The rubric says two missing dosages should fail, but the prompt allows "
                    "two missing current medications. This may make the score more permissive "
                    "than the rubric during evaluation."
                ),
            }
        )

    result = ScoreRubricConsistencyService(
        invoke_model=invoke,
        model="test-model",
    ).generate(
        ScoreRubricConsistencyRequest(
            scorecard_identifier="Scorecard",
            score_identifier="Medication Review: Dosage",
            score_version_id="version-1",
            rubric_text="Fail when two or more current meds lack dosage.",
            score_code="Pass when no more than two meds lack dosage.",
        )
    )

    assert result.status == "potential_conflict"
    assert result.score_version_id == "version-1"
    assert "more permissive than the rubric" in result.paragraph
    assert result.diagnostics["rubric_characters"] > 0


def test_merge_consistency_result_into_parameters_preserves_existing_fields():
    service = ScoreRubricConsistencyService(
        invoke_model=lambda _prompt, _model: json.dumps(
            {"status": "consistent", "paragraph": "The score and rubric match."}
        )
    )
    result = service.generate(
        ScoreRubricConsistencyRequest(
            scorecard_identifier="Scorecard",
            score_identifier="Score",
            score_version_id="version-1",
            rubric_text="Rubric",
            score_code="Code",
        )
    )

    merged = merge_consistency_result_into_parameters(
        json.dumps({"days": 90}),
        result,
    )

    assert merged["days"] == 90
    assert merged["score_rubric_consistency_check"]["status"] == "consistent"
    assert merged["score_rubric_consistency_check"]["score_version_id"] == "version-1"


def test_score_rubric_consistency_retries_invalid_json_once():
    calls = []

    def invoke(prompt: str, _model: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return ""
        return json.dumps(
            {"status": "consistent", "paragraph": "The score code follows the rubric."}
        )

    result = ScoreRubricConsistencyService(invoke_model=invoke).generate(
        ScoreRubricConsistencyRequest(
            scorecard_identifier="Scorecard",
            score_identifier="Score",
            score_version_id="version-1",
            rubric_text="Rubric",
            score_code="Code",
        )
    )

    assert result.status == "consistent"
    assert len(calls) == 2
    assert "prior response was not valid JSON" in calls[1]
