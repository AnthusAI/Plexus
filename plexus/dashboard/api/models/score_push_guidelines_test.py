from plexus.cli.shared import get_score_guidelines_path, get_score_yaml_path
from plexus.dashboard.api.models.score import Score


class RecordingClient:
    def __init__(self, champion_configuration="name: Test\nkey: old\n", champion_guidelines="Existing guide"):
        self.champion_configuration = champion_configuration
        self.champion_guidelines = champion_guidelines
        self.created_inputs = []

    def execute(self, query, variables=None):
        variables = variables or {}

        if "getScore(id:" in query or "getScore(id: $id)" in query:
            return {"getScore": {"championVersionId": "champion-version"}}

        if "getScoreVersion" in query:
            return {
                "getScoreVersion": {
                    "configuration": self.champion_configuration,
                    "guidelines": self.champion_guidelines,
                }
            }

        if "createScoreVersion" in query:
            self.created_inputs.append(variables["input"])
            return {"createScoreVersion": {"id": "new-version"}}

        raise AssertionError(f"Unexpected query: {query}")


def make_score(client):
    return Score(
        id="score-1",
        name="Medication Review: Individual Confirmation",
        key="medication-review-individual-confirmation",
        externalId="external-1",
        type="LangGraphScore",
        order=1,
        sectionId="section-1",
        client=client,
    )


def test_local_guidelines_path_uses_guidelines_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(tmp_path / "scorecards"))
    score = make_score(RecordingClient())

    path = score.get_local_guidelines_path("SelectQuote HCS Medium-Risk")

    assert path == (
        tmp_path
        / "scorecards"
        / "SelectQuote HCS Medium-Risk"
        / "guidelines"
        / "Medication Review- Individual Confirmation.md"
    )


def test_create_version_preserves_champion_guidelines_when_guidelines_omitted():
    client = RecordingClient(champion_guidelines="Existing guide")
    score = make_score(client)

    result = score.create_version_from_code("name: Test\nkey: new\n")

    assert result["success"] is True
    assert client.created_inputs[-1]["guidelines"] == "Existing guide"


def test_create_version_allows_explicit_guidelines_clear():
    client = RecordingClient(champion_guidelines="Existing guide")
    score = make_score(client)

    result = score.create_version_from_code("name: Test\nkey: new\n", guidelines="")

    assert result["success"] is True
    assert client.created_inputs[-1]["guidelines"] == ""


def test_push_code_and_guidelines_reads_canonical_guidelines_file(monkeypatch, tmp_path):
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(tmp_path / "scorecards"))
    client = RecordingClient(champion_guidelines="Existing guide")
    score = make_score(client)

    yaml_path = get_score_yaml_path("SelectQuote HCS Medium-Risk", score.name)
    yaml_path.write_text("name: Test\nkey: new\n", encoding="utf-8")
    guidelines_path = get_score_guidelines_path("SelectQuote HCS Medium-Risk", score.name)
    guidelines_path.write_text("Canonical guide", encoding="utf-8")

    result = score.push_code_and_guidelines("SelectQuote HCS Medium-Risk", note="test")

    assert result["success"] is True
    assert client.created_inputs[-1]["guidelines"] == "Canonical guide"
