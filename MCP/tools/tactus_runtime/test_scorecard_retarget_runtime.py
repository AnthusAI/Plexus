from __future__ import annotations

import pytest

from . import execute

pytestmark = pytest.mark.unit


def test_scorecard_retarget_runtime_plans_single_score():
    module = execute.PlexusRuntimeModule()

    result = module.scorecard_retarget.plan_score(
        {
            "yaml_content": (
                "name: Test\n"
                "class: LangGraphScore\n"
                "model_provider: ChatOpenAI\n"
                "model_name: gpt-5-mini\n"
                "base_model_name: gpt-5-mini\n"
            ),
            "target": {"model_name": "gpt-5.4-nano"},
        }
    )

    assert result["changed"] is True
    assert result["candidate"]["model_name"] == "gpt-5.4-nano"
    assert module.api_calls == ["plexus.scorecard_retarget.plan_score"]


def test_scorecard_retarget_is_listed_in_plexus_api_list():
    module = execute.PlexusRuntimeModule()

    catalog = module.api.list()

    assert "plexus.scorecard_retarget" in catalog
    assert "plan_score" in catalog["plexus.scorecard_retarget"]
