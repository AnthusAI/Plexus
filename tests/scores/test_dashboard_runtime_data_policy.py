from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest

from plexus.scores.core.ScoreData import ScoreData


def test_dashboard_runtime_never_imports_a_yaml_declared_data_class(monkeypatch) -> None:
    score = SimpleNamespace(
        parameters=SimpleNamespace(data={"class": "UnapprovedYamlDataSource"})
    )
    monkeypatch.setenv("PLEXUS_RUNTIME_PROFILE", "dashboard")

    with pytest.raises(RuntimeError, match="Dashboard commands cannot load a data class declared in score YAML"):
        ScoreData._load_data_cache(score)


def test_local_runtime_keeps_existing_yaml_data_class_behavior(monkeypatch) -> None:
    class LocalDataSource:
        def __init__(self, **_kwargs) -> None:
            pass

    score = SimpleNamespace(
        parameters=SimpleNamespace(data={"class": "LocalDataSource"})
    )
    monkeypatch.delenv("PLEXUS_RUNTIME_PROFILE", raising=False)
    monkeypatch.setattr(builtins, "LocalDataSource", LocalDataSource, raising=False)

    assert isinstance(ScoreData._load_data_cache(score), LocalDataSource)
