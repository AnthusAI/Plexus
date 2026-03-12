import pandas as pd
import pytest
from unittest.mock import AsyncMock, Mock, patch

from plexus.Evaluation import AccuracyEvaluation
from plexus.Scorecard import Scorecard
from plexus.scores.Score import Score


@pytest.mark.asyncio
async def test_score_text_prefers_dashboard_client_for_item_lookup():
    evaluation = AccuracyEvaluation.__new__(AccuracyEvaluation)
    class DummyScorecard:
        def __init__(self):
            self.scores = []

        async def score_entire_text(self, **kwargs):
            return {}

    evaluation.scorecard = DummyScorecard()
    evaluation.score_names_to_process = lambda: []
    evaluation.subset_of_score_names = []
    evaluation.override_data = {}
    evaluation.total_skipped = 0
    evaluation.allow_no_labels = True
    evaluation.dashboard_client = Mock()
    evaluation.experiment_id = None

    row = pd.Series({"text": "hi", "item_id": "item-123"})

    with patch("plexus.dashboard.api.models.item.Item.get_by_id") as get_by_id:
        await evaluation.score_text(row)

    assert get_by_id.call_args[0][1] is evaluation.dashboard_client


@pytest.mark.asyncio
async def test_score_text_passes_item_to_scorecard():
    evaluation = AccuracyEvaluation.__new__(AccuracyEvaluation)

    class DummyScorecard:
        def __init__(self):
            self.scores = []
            self.kwargs = None

        async def score_entire_text(self, **kwargs):
            self.kwargs = kwargs
            return {}

    evaluation.scorecard = DummyScorecard()
    evaluation.score_names_to_process = lambda: []
    evaluation.subset_of_score_names = []
    evaluation.override_data = {}
    evaluation.total_skipped = 0
    evaluation.allow_no_labels = True
    evaluation.dashboard_client = Mock()
    evaluation.experiment_id = None

    row = pd.Series({"text": "hi", "item_id": "item-123"})
    fake_item = Mock()

    with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=fake_item):
        await evaluation.score_text(row)

    assert evaluation.scorecard.kwargs["item"] is fake_item


@pytest.mark.asyncio
async def test_evaluation_uses_input_source_text(tmp_path):
    yaml_content = """
name: TestScorecard
scores:
  - name: KeywordScore
    key: keyword_score
    id: test-score-id
    class: DummyScore
    item:
      class: DeepgramInputSource
      options:
        pattern: ".*deepgram.*\\\\.json$"
"""
    yaml_path = tmp_path / "scorecard.yaml"
    yaml_path.write_text(yaml_content)

    class DummyScore(Score):
        @classmethod
        async def create(cls, **parameters):
            return cls(**parameters)

        async def predict(self, model_input, context=None, **kwargs):
            captured["text"] = model_input.text
            return Score.Result(
                value=True,
                parameters=self.parameters,
            )

    with patch("plexus.scores.DummyScore", DummyScore, create=True):
        scorecard_class = Scorecard.create_from_yaml(str(yaml_path))
    scorecard_instance = scorecard_class(scorecard=scorecard_class.name)

    evaluation = AccuracyEvaluation.__new__(AccuracyEvaluation)
    evaluation.scorecard = scorecard_instance
    evaluation.scorecard_name = scorecard_class.name
    evaluation.score_names_to_process = lambda: scorecard_instance.score_names_to_process()
    evaluation.subset_of_score_names = None
    evaluation.override_data = {}
    evaluation.total_skipped = 0
    evaluation.allow_no_labels = True
    evaluation.dashboard_client = Mock()
    evaluation.experiment_id = None
    evaluation.processed_items_by_score = {}
    evaluation.processed_items = 0

    row = pd.Series({"text": "fallback", "item_id": "item-123"})

    captured = {}

    class DummyInputSource:
        def extract(self, item):
            from plexus.core.ScoreInput import ScoreInput
            return ScoreInput(text="hello from source", metadata={"input_source": "Dummy"})

    with patch("plexus.input_sources.InputSourceFactory.InputSourceFactory.create_input_source", return_value=DummyInputSource()):
        with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=Mock()):
            result = await evaluation.score_text(row, score_name="KeywordScore")

    score_result = result["results"]["test-score-id"]
    assert score_result.value is True
    assert captured["text"] == "hello from source"


@pytest.mark.asyncio
async def test_input_source_requires_item(tmp_path):
    yaml_content = """
name: TestScorecard
scores:
  - name: KeywordScore
    key: keyword_score
    id: test-score-id
    class: DummyScore
    item:
      class: DeepgramInputSource
      options:
        pattern: ".*deepgram.*\\\\.json$"
"""
    yaml_path = tmp_path / "scorecard.yaml"
    yaml_path.write_text(yaml_content)

    class DummyScore(Score):
        @classmethod
        async def create(cls, **parameters):
            return cls(**parameters)

        async def predict(self, model_input, context=None, **kwargs):
            return Score.Result(
                value=True,
                parameters=self.parameters,
            )

    with patch("plexus.scores.DummyScore", DummyScore, create=True):
        scorecard_class = Scorecard.create_from_yaml(str(yaml_path))
    scorecard_instance = scorecard_class(scorecard=scorecard_class.name)

    with pytest.raises(ValueError, match="Item is required"):
        await scorecard_instance.score_entire_text(
            text="fallback",
            metadata={},
            subset_of_score_names=["KeywordScore"],
            item=None,
        )
