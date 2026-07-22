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
    assert "test -f /workspace/MCP/tools/tactus_runtime/execute.py" in dockerfile
    assert "test -f /workspace/MCP/tools/tactus_runtime/_item_helpers.py" in dockerfile
    assert "test -f /workspace/MCP/server.py" in dockerfile


def test_console_worker_installs_scoring_runtime_dependencies():
    repo_root = Path(__file__).resolve().parents[4]
    dockerfile = repo_root.joinpath(
        "dashboard/amplify/functions/consoleRunWorker/Dockerfile"
    ).read_text()

    assert 'pip install --progress-bar off -e "/workspace[scoring]"' in dockerfile
    assert '"celery>=5.4.0"' in dockerfile


def test_console_worker_uses_a_preinitialized_interactive_alias():
    repo_root = Path(__file__).resolve().parents[4]
    resource = repo_root.joinpath(
        "dashboard/amplify/functions/consoleRunWorker/resource.ts"
    ).read_text()
    backend = repo_root.joinpath("dashboard/amplify/backend.ts").read_text()

    assert 'PLEXUS_EAGER_CONSOLE_RUNTIME: "true"' in resource
    assert 'aliasName: "interactive"' in resource
    assert "provisionedConcurrentExecutions: 1" in resource
    assert "stringValue: this.responderAlias.functionArn" in resource
    assert "resourceName: 'amplify-*ConsoleChatResponder*:*'" in backend
    assert "arnFormat: ArnFormat.COLON_RESOURCE_NAME" in backend


def test_console_worker_asset_hash_forces_nested_stack_refresh():
    repo_root = Path(__file__).resolve().parents[4]
    resource = repo_root.joinpath(
        "dashboard/amplify/functions/consoleRunWorker/resource.ts"
    ).read_text()

    assert "new ecr_assets.DockerImageAsset" in resource
    assert "CONSOLE_WORKER_IMAGE_ASSET_HASH: workerImage.assetHash" in resource
    assert "lambda.DockerImageCode.fromEcr(workerImage.repository" in resource


def test_console_responder_parameter_isolated_by_environment():
    repo_root = Path(__file__).resolve().parents[4]
    resource = repo_root.joinpath(
        "dashboard/amplify/functions/consoleRunWorker/resource.ts"
    ).read_text()
    backend = repo_root.joinpath("dashboard/amplify/backend.ts").read_text()
    dispatcher = repo_root.joinpath(
        "dashboard/amplify/data/resolvers/dispatchConsoleChat.ts"
    ).read_text()

    assert "parameterName: props.responderParameterName" in resource
    assert (
        "const consoleResponderParameterName = "
        "`/plexus/${consoleWorkerEnvironmentName}/console-chat/responder`;" in backend
    )
    assert "responderParameterName: consoleResponderParameterName," in backend
    assert 'CONSOLE_RESPONDER_PARAMETER_NAME' in backend
    assert 'consoleResponderParameterName,' in backend
    assert "process.env.CONSOLE_RESPONDER_PARAMETER_NAME" in dispatcher
    assert "'/plexus/console-chat/responder'" not in dispatcher


def test_sandbox_hotpatch_overlays_the_complete_worker_source():
    repo_root = Path(__file__).resolve().parents[4]
    dockerfile = repo_root.joinpath(
        "dashboard/amplify/functions/consoleRunWorker/Dockerfile.sandbox-hotpatch"
    ).read_text()

    assert "COPY plexus /workspace/plexus" in dockerfile
    assert "COPY MCP /workspace/MCP" in dockerfile
    assert (
        "COPY dashboard/amplify/functions/consoleRunWorker/app.py /var/task/app.py"
        in dockerfile
    )
