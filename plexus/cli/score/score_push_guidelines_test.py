import pytest

pytest.importorskip("ruamel.yaml")
from graphql import print_ast

from plexus.cli.score import scores as score_commands
from plexus.cli.shared import get_score_yaml_path


class CliRecordingClient:
    def __init__(self):
        self.created_inputs = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, variables=None):
        variables = variables or {}
        query = query if isinstance(query, str) else print_ast(query)

        if "getScorecard" in query:
            return {"getScorecard": {"name": "SelectQuote HCS Medium-Risk"}}

        if "getScore(id:" in query:
            return {
                "getScore": {
                    "id": "score-1",
                    "name": "Medication Review: Individual Confirmation",
                    "championVersionId": "champion-version",
                }
            }

        if "getScoreVersion" in query:
            return {
                "getScoreVersion": {
                    "configuration": "name: Medication Review: Individual Confirmation\nkey: old\n",
                    "guidelines": "Cloud guide",
                }
            }

        if "createScoreVersion" in query:
            self.created_inputs.append(variables["input"])
            return {
                "createScoreVersion": {
                    "id": "new-version",
                    "configuration": variables["input"]["configuration"],
                    "createdAt": "2026-05-05T00:00:00Z",
                    "updatedAt": "2026-05-05T00:00:00Z",
                    "note": variables["input"]["note"],
                    "score": {
                        "id": "score-1",
                        "name": "Medication Review: Individual Confirmation",
                        "championVersionId": "champion-version",
                    },
                }
            }

        raise AssertionError(f"Unexpected query: {query}")


def test_cli_push_preserves_champion_guidelines_when_local_guidelines_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(tmp_path / "scorecards"))
    client = CliRecordingClient()
    monkeypatch.setattr(score_commands, "create_client", lambda: client)
    monkeypatch.setattr(
        score_commands,
        "memoized_resolve_scorecard_identifier",
        lambda _client, _scorecard: "scorecard-1",
    )
    monkeypatch.setattr(
        score_commands,
        "memoized_resolve_score_identifier",
        lambda _client, _scorecard_id, _score: "score-1",
    )

    yaml_path = get_score_yaml_path(
        "SelectQuote HCS Medium-Risk",
        "Medication Review: Individual Confirmation",
    )
    yaml_path.write_text(
        "name: Medication Review: Individual Confirmation\n"
        "version: champion-version\n"
        "key: new\n",
        encoding="utf-8",
    )

    score_commands.push.callback(
        scorecard="SelectQuote HCS Medium-Risk",
        score="Medication Review: Individual Confirmation",
        note="test",
    )

    assert client.created_inputs[-1]["guidelines"] == "Cloud guide"
