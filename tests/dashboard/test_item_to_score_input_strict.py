import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from plexus.dashboard.api.models.item import Item


def _make_item():
    return Item(
        id="item-123",
        evaluationId="eval-1",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
        accountId="acct-1",
        isEvaluation=False,
        text="fallback text",
        metadata={},
        attachedFiles=["items/123/deepgram.json"],
        client=Mock(),
    )


def test_to_score_input_raises_on_input_source_error():
    item = _make_item()
    item_config = {"class": "DeepgramInputSource", "options": {"pattern": ".*deepgram.*\\.json$"}}

    with patch("plexus.input_sources.InputSourceFactory.InputSourceFactory.create_input_source") as create_input_source:
        create_input_source.side_effect = ValueError("No Deepgram file")
        with pytest.raises(ValueError, match="No Deepgram file"):
            item.to_score_input(item_config)
