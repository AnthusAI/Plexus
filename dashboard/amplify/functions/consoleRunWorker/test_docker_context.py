from pathlib import Path


def test_console_worker_docker_context_includes_mcp_python_tools():
    repo_root = Path(__file__).resolve().parents[4]
    dockerignore_lines = repo_root.joinpath(".dockerignore").read_text().splitlines()

    mcp_exclude_index = dockerignore_lines.index("MCP/")
    mcp_include_index = dockerignore_lines.index("!MCP/")
    mcp_tree_include_index = dockerignore_lines.index("!MCP/**")

    assert mcp_include_index > mcp_exclude_index
    assert mcp_tree_include_index > mcp_exclude_index


def test_console_worker_dockerfile_verifies_mcp_tool_modules():
    repo_root = Path(__file__).resolve().parents[4]
    dockerfile = repo_root.joinpath(
        "dashboard/amplify/functions/consoleRunWorker/Dockerfile"
    ).read_text()

    assert "PYTHONPATH=/workspace:/workspace/MCP" in dockerfile
    assert "test -f /workspace/MCP/tools/scorecard/scorecards.py" in dockerfile
    assert "test -f /workspace/MCP/tools/evaluation/evaluations.py" in dockerfile
