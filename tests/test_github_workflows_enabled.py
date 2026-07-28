from pathlib import Path

import yaml


def test_supported_github_actions_workflows_are_enabled():
    repo_root = Path(__file__).resolve().parents[1]
    workflows = repo_root / ".github" / "workflows"
    expected = (
        "ci.yaml",
        "documentation.yml",
        "release.yml",
    )

    for filename in expected:
        workflow_path = workflows / filename
        assert workflow_path.is_file(), (
            f"GitHub Actions workflow is disabled: {filename}"
        )
        assert yaml.safe_load(workflow_path.read_text()) is not None
        assert not workflow_path.with_name(f"{filename}.bak").exists()


def test_ruleset_sync_stays_disabled_without_supported_admin_authentication():
    workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"

    assert not workflows.joinpath("ruleset-sync.yml").exists()
    assert workflows.joinpath("ruleset-sync.yml.bak").is_file()


def test_python_ci_targets_only_the_production_runtime():
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yaml"
    )
    python_job = yaml.safe_load(workflow_path.read_text())["jobs"]["python-tests"]
    setup_step = next(
        step
        for step in python_job["steps"]
        if step.get("name", "").startswith("Set up Conda")
    )

    assert python_job["name"] == "Python Tests (3.11)"
    assert "strategy" not in python_job
    assert setup_step["with"]["python-version"] == "3.11"
