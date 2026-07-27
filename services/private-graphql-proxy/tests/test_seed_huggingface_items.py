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


def test_resolve_label_names_uses_only_dataset_declared_labels():
    seed_huggingface_items = load_seed_module()
    dataset = SimpleNamespace(
        features={"label": SimpleNamespace(names=["billing", "technical"])}
    )

    assert seed_huggingface_items.resolve_label_names(dataset) == ["billing", "technical"]


def test_resolve_label_names_has_no_default_dataset_fallback():
    seed_huggingface_items = load_seed_module()
    dataset = SimpleNamespace(features={"domain": SimpleNamespace(names=["support"])})

    assert seed_huggingface_items.resolve_label_names(dataset) == ()


def test_datasets_server_loader_fetches_exact_bounded_pages(monkeypatch):
    seed_huggingface_items = load_seed_module()
    requests = []

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"rows": [{"row": row} for row in self.rows]}

    def fake_get(url, *, params, timeout):
        requests.append((url, params, timeout))
        return FakeResponse([{"text": f"row-{index}"} for index in range(params["offset"], params["offset"] + params["length"])])

    monkeypatch.setattr(seed_huggingface_items.requests, "get", fake_get)

    _dataset, rows = seed_huggingface_items.load_rows(
        "public/demo", "test", 10, 200, source="datasets-server"
    )

    assert len(rows) == 200
    assert [request[1]["offset"] for request in requests] == [10, 110]
    assert all(request[1]["length"] == 100 for request in requests)


def test_datasets_server_loader_fails_when_the_requested_slice_is_incomplete(monkeypatch):
    seed_huggingface_items = load_seed_module()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"rows": [{"row": {"text": "only-row"}}]}

    monkeypatch.setattr(seed_huggingface_items.requests, "get", lambda *_args, **_kwargs: FakeResponse())

    try:
        seed_huggingface_items.load_rows("public/demo", "test", 0, 2, source="datasets-server")
    except RuntimeError as exc:
        assert "returned 1 rows; expected 2" in str(exc)
    else:
        raise AssertionError("Expected an incomplete datasets-server response to fail")


def test_seed_fixtures_can_create_labeled_feedback_from_an_explicit_field(monkeypatch):
    seed_huggingface_items = load_seed_module()
    calls = []

    class FakeClient:
        def execute(self, query, variables):
            calls.append((query, variables))
            if "createItem" in query:
                return {"createItem": {"id": variables["input"]["id"]}}
            if "createIdentifier" in query:
                return {"createIdentifier": {"itemId": variables["input"]["itemId"]}}
            if "createFeedbackItem" in query:
                return {"createFeedbackItem": {"id": variables["input"]["id"]}}
            raise AssertionError("Unexpected GraphQL operation")

    monkeypatch.setattr(
        seed_huggingface_items,
        "load_rows",
        lambda *_args, **_kwargs: (SimpleNamespace(features={}), [{"text": "Public sample", "domain": "aviation"}]),
    )

    fixtures = seed_huggingface_items.seed_fixtures(
        client=FakeClient(),
        account_id="account-1",
        score_id="score-1",
        dataset_name="public/demo",
        split="test",
        start=0,
        limit=1,
        prefix="fixture",
        identifier_name="External ID",
        verify=False,
        label_field="domain",
        feedback_scorecard_id="scorecard-1",
    )

    assert fixtures[0].label == "aviation"
    assert fixtures[0].label_name == "aviation"
    item_input = next(variables["input"] for query, variables in calls if "createItem" in query)
    assert item_input["metadata"] == {
        "source": "private-graphql-proxy-fixture",
        "dataset": "public/demo",
        "split": "test",
        "row_index": 0,
    }
    feedback_input = next(variables["input"] for query, variables in calls if "createFeedbackItem" in query)
    assert feedback_input["finalAnswerValue"] == "aviation"
    assert feedback_input["scorecardId"] == "scorecard-1"
    assert feedback_input["editedAt"].endswith("+00:00")


def test_feedback_seeding_rejects_implicit_labels():
    seed_huggingface_items = load_seed_module()

    try:
        seed_huggingface_items.seed_fixtures(
            client=SimpleNamespace(),
            account_id="account-1",
            score_id="score-1",
            dataset_name="public/demo",
            split="test",
            start=0,
            limit=1,
            prefix="fixture",
            identifier_name="External ID",
            verify=False,
            feedback_scorecard_id="scorecard-1",
        )
    except ValueError as exc:
        assert "--label-field" in str(exc)
    else:
        raise AssertionError("Expected feedback seeding without an explicit label field to fail")
