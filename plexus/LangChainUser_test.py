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
