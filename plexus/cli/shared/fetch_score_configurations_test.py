from pathlib import Path

from ruamel.yaml import YAML

from plexus.cli.shared import get_score_yaml_path
from plexus.cli.shared.fetch_score_configurations import fetch_score_configurations


class _FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _query, variable_values=None):
        assert variable_values == {"id": "score-version-db-123"}
        return {
            "getScoreVersion": {
                "id": "score-version-db-123",
                "configuration": "\n".join(
                    [
                        "name: Agent Misrepresentation",
                        "key: agent-misrepresentation",
                        'id: "45813"',
                        "version: internal-yaml-version",
                        "class: LangGraphScore",
                        "",
                    ]
                ),
            }
        }


def test_fetch_score_configurations_normalizes_in_memory_version(tmp_path, monkeypatch):
    monkeypatch.setenv("SCORECARD_CACHE_DIR", str(tmp_path / "scorecards"))

    configurations = fetch_score_configurations(
        client=_FakeClient(),
        scorecard_data={"name": "SelectQuote HCS Medium-Risk"},
        target_scores=[
            {
                "id": "69e2adba-553e-49a3-9ede-7f9a679a08f3",
                "name": "Agent Misrepresentation",
                "championVersionId": "score-version-db-123",
            }
        ],
        cache_status={"69e2adba-553e-49a3-9ede-7f9a679a08f3": False},
        use_cache=False,
    )

    parser = YAML(typ="safe")
    in_memory = parser.load(configurations["69e2adba-553e-49a3-9ede-7f9a679a08f3"])
    on_disk = parser.load(
        Path(
            get_score_yaml_path(
                "SelectQuote HCS Medium-Risk",
                "Agent Misrepresentation",
            )
        ).read_text()
    )

    assert in_memory["version"] == "score-version-db-123"
    assert on_disk["version"] == "score-version-db-123"
    assert in_memory == on_disk
