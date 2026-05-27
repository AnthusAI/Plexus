import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from plexus.Evaluation import Evaluation


def test_evaluation_create_score_result_persists_timestamps():
    evaluation = Evaluation.__new__(Evaluation)
    evaluation.experiment_id = "evaluation-1"
    evaluation.account_id = "account-1"
    evaluation.scorecard_id = "scorecard-1"
    evaluation.dashboard_client = SimpleNamespace(
        execute=Mock(return_value={"createScoreResult": {"id": "score-result-1"}})
    )
    evaluation.logging = SimpleNamespace(error=Mock(), warning=Mock())

    score_result = SimpleNamespace(
        value="Yes",
        confidence=0.9,
        explanation='The agent said "General Kenobi" [0:01.20-0:02.00].',
        metadata={},
        parameters=SimpleNamespace(id="score-1", name="Test Score"),
        start_time_seconds=5,
        end_time_seconds=6,
    )

    asyncio.run(
        evaluation._create_score_result(
            score_result=score_result,
            content_id="item-1",
            result={"resolved_item_id": "item-1"},
        )
    )

    variables = evaluation.dashboard_client.execute.call_args.args[1]
    input_data = variables["input"]
    assert input_data["startTimeSeconds"] == 5.0
    assert input_data["endTimeSeconds"] == 6.0
