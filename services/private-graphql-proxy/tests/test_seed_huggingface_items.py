from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace
from pathlib import Path


def load_seed_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "seed_huggingface_items.py"
    spec = importlib.util.spec_from_file_location("seed_huggingface_items", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_huggingface_fixture_uses_explicit_text_features(monkeypatch):
    seed_huggingface_items = load_seed_module()
    captured = {}

    class FakeValue:
        def __init__(self, kind):
            self.kind = kind

    class FakeFeatures(dict):
        pass

    def fake_load_dataset(dataset_name, *, split, **kwargs):
        captured["dataset_name"] = dataset_name
        captured["split"] = split
        captured["kwargs"] = kwargs
        return [{"text": "Agent transcript", "domain": "support"}]

    monkeypatch.setitem(
        sys.modules,
        "datasets",
        SimpleNamespace(
            Features=FakeFeatures,
            Value=FakeValue,
            load_dataset=fake_load_dataset,
        ),
    )

    _dataset, rows = seed_huggingface_items.load_rows(
        seed_huggingface_items.DEFAULT_DATASET,
        "test",
        2,
        3,
    )

    assert rows == [{"text": "Agent transcript", "domain": "support"}]
    assert captured["dataset_name"] == seed_huggingface_items.DEFAULT_DATASET
    assert captured["split"] == "test[2:5]"
    features = captured["kwargs"]["features"]
    assert isinstance(features, FakeFeatures)
    assert set(features) == {"text", "domain", "gender", "accent"}
    assert all(value.kind == "string" for value in features.values())
