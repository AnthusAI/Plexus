from pathlib import Path


def test_console_worker_docker_context_includes_mcp_python_tools():
    repo_root = Path(__file__).resolve().parents[4]
    dockerignore_lines = repo_root.joinpath(".dockerignore").read_text().splitlines()

    mcp_exclude_index = dockerignore_lines.index("MCP/")
    mcp_include_index = dockerignore_lines.index("!MCP/")
    mcp_python_include_index = dockerignore_lines.index("!MCP/**/*.py")

    assert mcp_include_index > mcp_exclude_index
    assert mcp_python_include_index > mcp_exclude_index
