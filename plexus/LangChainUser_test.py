import subprocess
import sys

import pytest


pytestmark = pytest.mark.unit


def test_langgraph_score_import_does_not_require_azure_identity():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['azure'] = None; "
            "sys.modules['azure.identity'] = None; "
            "from plexus.scores.LangGraphScore import LangGraphScore; "
            "assert LangGraphScore.__name__ == 'LangGraphScore'",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_langgraph_score_import_does_not_load_optional_engines_or_providers():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; "
            "blocked = ["
            "'tactus', 'graphviz', 'litellm', 'langchain_aws', "
            "'langchain_openai', 'langchain_ollama', "
            "'langchain_community.callbacks', 'langchain_community.chat_models', "
            "'plexus.dashboard.api.client', "
            "'plexus.dashboard.api.models.account', "
            "'plexus.dashboard.api.models.scoring_job'"
            "]; "
            "[sys.modules.__setitem__(name, None) for name in blocked]; "
            "from plexus.scores.LangGraphScore import LangGraphScore; "
            "assert LangGraphScore.__name__ == 'LangGraphScore'",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_tactus_score_import_does_not_load_tactus_runtime():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['tactus'] = None; "
            "from plexus.scores.TactusScore import TactusScore; "
            "assert TactusScore.__name__ == 'TactusScore'",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
