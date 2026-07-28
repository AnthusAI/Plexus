from pathlib import Path

import yaml


def test_standard_github_actions_workflows_are_enabled():
    repo_root = Path(__file__).resolve().parents[1]
    workflows = repo_root / ".github" / "workflows"
    expected = (
        "ci.yaml",
        "documentation.yml",
        "release.yml",
        "ruleset-sync.yml",
    )

    for filename in expected:
        workflow_path = workflows / filename
        assert workflow_path.is_file(), (
            f"GitHub Actions workflow is disabled: {filename}"
        )
        assert yaml.safe_load(workflow_path.read_text()) is not None
        assert not workflow_path.with_name(f"{filename}.bak").exists()
