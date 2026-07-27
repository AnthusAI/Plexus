import logging
from types import SimpleNamespace

import pandas as pd

from plexus.data.DataCache import DataCache
from plexus.scores.core.ScoreData import ScoreData


class _Cache(DataCache):
    def load_dataframe(self, *args, **kwargs):
        raise NotImplementedError


def test_debug_dataframe_logs_schema_without_row_payloads(caplog):
    cache = _Cache()
    dataframe = pd.DataFrame(
        [{"content_id": "item-1", "text": "private transcript must not be logged"}]
    )

    with caplog.at_level(logging.INFO):
        cache.debug_dataframe(dataframe, context="Evaluation dataset", logger=logging.getLogger("test"))

    assert "Evaluation dataset: 1 rows x 2 columns" in caplog.text
    assert "content_id" in caplog.text
    assert "private transcript must not be logged" not in caplog.text


class _ScoreData(ScoreData):
    def __init__(self, dataframe):
        self._dataframe = dataframe
        self.parameters = SimpleNamespace(dependencies=None)

    def _load_data_cache(self):
        dataframe = self._dataframe

        class _ScoreDataCache:
            def load_dataframe(self, *, data=None, fresh=False):
                return dataframe

        return _ScoreDataCache()

    def analyze_dataset(self):
        return None


def test_score_data_logs_schema_without_sample_rows(caplog):
    score_data = _ScoreData(
        pd.DataFrame([{"text": "private transcript must not be logged", "label": "yes"}])
    )

    with caplog.at_level(logging.INFO):
        score_data.load_data()

    assert "Dataset loaded: 1 rows x 2 columns" in caplog.text
    assert "private transcript must not be logged" not in caplog.text
