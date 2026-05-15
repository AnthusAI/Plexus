from __future__ import annotations

import json

import pytest

from . import execute

pytestmark = pytest.mark.unit


def test_model_frontier_runtime_plans_variants():
    module = execute.PlexusRuntimeModule()

    result = module.model_frontier.plan(
        {
            "yaml_content": (
                "name: Test\n"
                "class: LangGraphScore\n"
                "model_provider: ChatOpenAI\n"
                "model_name: gpt-5-mini\n"
                "base_model_name: gpt-5-mini\n"
                "verbosity: low\n"
            ),
            "candidate_matrix": {
                "models": [
                    {
                        "label": "nano",
                        "model_provider": "ChatOpenAI",
                        "model_name": "gpt-5.4-nano",
                    }
                ]
            },
        }
    )

    assert result["count"] == 2
    assert result["variants"][0]["label"] == "current"
    assert result["variants"][1]["model_name"] == "gpt-5.4-nano"
    assert result["variants"][1]["base_model_name"] == "gpt-5.4-nano"
    assert module.api_calls == ["plexus.model_frontier.plan"]


def test_model_frontier_runtime_finalizes_unpersisted_artifacts():
    module = execute.PlexusRuntimeModule()

    result = module.model_frontier.finalize(
        {
            "rows": [
                {
                    "label": "current",
                    "cost_axis": 0.01,
                    "accuracy_axis": 0.8,
                }
            ],
            "title": "Frontier",
        }
    )

    assert result["persisted"] is False
    assert result["artifact_paths"] == [
        "reportblocks/unpersisted/frontier.json",
        "reportblocks/unpersisted/frontier.csv",
        "reportblocks/unpersisted/frontier.html",
    ]
    assert result["report_output"]["output_compacted"] is True
    assert json.loads(result["artifacts"]["frontier.json"])["rows"][0]["is_pareto_frontier"] is True


def test_model_frontier_runtime_finalizes_persisted_report_attachments(monkeypatch):
    attached_calls = []

    monkeypatch.setattr(
        "plexus.cli.shared.client_utils.create_client",
        lambda: "client-1",
    )

    def fake_add_file_to_report_block(report_block_id, file_name, content, content_type=None, client=None):
        attached_calls.append(
            {
                "report_block_id": report_block_id,
                "file_name": file_name,
                "content": content,
                "content_type": content_type,
                "client": client,
            }
        )
        return [f"reportblocks/{report_block_id}/{call['file_name']}" for call in attached_calls]

    monkeypatch.setattr(
        "plexus.reports.s3_utils.add_file_to_report_block",
        fake_add_file_to_report_block,
    )

    module = execute.PlexusRuntimeModule()
    result = module.model_frontier.finalize(
        {
            "report_block_id": "rb-1",
            "rows": [{"label": "current", "cost_axis": 0.01, "accuracy_axis": 0.8}],
        }
    )

    assert result["persisted"] is True
    assert [call["file_name"] for call in attached_calls] == [
        "frontier.json",
        "frontier.csv",
        "frontier.html",
    ]
    assert attached_calls[0]["content_type"] == "application/json"
    assert attached_calls[0]["client"] == "client-1"
    assert result["report_output"]["output_compacted"] is True
    assert result["artifact_paths"][-1] == "reportblocks/rb-1/frontier.html"
