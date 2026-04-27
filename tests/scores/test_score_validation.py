import pytest
from pydantic import ValidationError as PydanticValidationError

from plexus.scores.Score import Score


class StaticResultScore(Score):
    def __init__(self, *, result=None, result_list=None, **parameters):
        super().__init__(**parameters)
        self._result = result
        self._result_list = result_list

    def predict(self, context, model_input: Score.Input):
        if self._result_list is not None:
            return self._result_list
        return self._result


def _model_input() -> Score.Input:
    return Score.Input(text="test transcript")


def test_validation_disabled_when_not_configured():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        result=Score.Result(parameters=Score.Parameters(name="test_score"), value="Maybe"),
    )
    result = score.predict(None, _model_input())
    assert result.value == "Maybe"


def test_value_valid_classes_passes():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        validation={"value": {"valid_classes": ["Yes", "No"]}},
        result=Score.Result(parameters=Score.Parameters(name="test_score"), value="Yes"),
    )
    result = score.predict(None, _model_input())
    assert result.value == "Yes"


def test_value_valid_classes_raises_validation_error():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        validation={"value": {"valid_classes": ["Yes", "No"]}},
        result=Score.Result(parameters=Score.Parameters(name="test_score"), value="Maybe"),
    )
    with pytest.raises(Score.ValidationError, match="is not in valid_classes"):
        score.predict(None, _model_input())


def test_pattern_validation_passes():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        validation={"value": {"patterns": [r"^NQ - (?!Other$).*"]}},
        result=Score.Result(parameters=Score.Parameters(name="test_score"), value="NQ - Pricing"),
    )
    result = score.predict(None, _model_input())
    assert result.value == "NQ - Pricing"


def test_pattern_validation_fails():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        validation={"value": {"patterns": [r"^NQ - (?!Other$).*"]}},
        result=Score.Result(parameters=Score.Parameters(name="test_score"), value="NQ - Other"),
    )
    with pytest.raises(Score.ValidationError, match="does not match any configured pattern"):
        score.predict(None, _model_input())


def test_explanation_length_constraints():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        validation={"explanation": {"minimum_length": 10, "maximum_length": 20}},
        result=Score.Result(
            parameters=Score.Parameters(name="test_score"),
            value="Yes",
            explanation="Too short",
        ),
    )
    with pytest.raises(Score.ValidationError, match="below minimum_length"):
        score.predict(None, _model_input())


def test_list_result_items_are_validated():
    score = StaticResultScore(
        name="test_score",
        scorecard_name="test_scorecard",
        validation={"value": {"valid_classes": ["Yes", "No"]}},
        result_list=[
            Score.Result(parameters=Score.Parameters(name="test_score"), value="Yes"),
            Score.Result(parameters=Score.Parameters(name="test_score"), value="Maybe"),
        ],
    )
    with pytest.raises(Score.ValidationError, match="is not in valid_classes"):
        score.predict(None, _model_input())


def test_invalid_regex_is_rejected_at_parameter_parse_time():
    with pytest.raises(PydanticValidationError):
        StaticResultScore(
            name="test_score",
            scorecard_name="test_scorecard",
            validation={"value": {"patterns": [r"(unclosed"]}},
            result=Score.Result(parameters=Score.Parameters(name="test_score"), value="Yes"),
        )
