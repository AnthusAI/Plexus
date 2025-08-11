import json
from unittest.mock import patch, Mock


def test_cli_cost_analyze_outputs_summary(capsys):
    from plexus.cli.CostCommands import analyze

    fake_summary = {
        "accountId": "acct-1",
        "days": 7,
        "totals": {"count": 2, "total_cost": "0.12"},
        "groups": [
            {"scorecardId": "sc1", "scoreId": "s1", "count": 2, "total_cost": "0.12"}
        ],
    }

    with patch('plexus.cli.CostCommands.create_client') as mock_create_client, \
         patch('plexus.cli.CostCommands.resolve_account_id_for_command', return_value='acct-1'), \
         patch('plexus.cli.CostCommands.ScoreResultCostAnalyzer') as mock_analyzer_cls:
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_analyzer = Mock()
        mock_analyzer.summarize.return_value = fake_summary
        mock_analyzer_cls.return_value = mock_analyzer

        analyze.callback(days=7, scorecard=None, score=None, output='json')

    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert data["accountId"] == "acct-1"
    assert data["days"] == 7
    assert data["totals"]["total_cost"] == "0.12"


