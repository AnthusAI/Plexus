from pathlib import Path
import subprocess
import sys
import tomllib


def test_cli_framework_is_a_declared_core_runtime_dependency():
    """A clean base installation must be able to start the Plexus CLI."""
    project_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())

    dependencies = pyproject["tool"]["poetry"]["dependencies"]

    assert "click" in dependencies


def test_login_help_does_not_import_the_legacy_command_graph():
    """Authentication must start without loading unrelated scoring commands."""
    code = """
import sys
sys.modules['plexus.cli.shared.CommandLineInterface'] = None
sys.argv = ['plexus', 'login', '--help']
from plexus.cli.entrypoint import main
main()
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Sign in through the configured Cognito" in result.stdout


def test_installed_cli_uses_the_lightweight_entrypoint():
    project_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())

    assert pyproject["tool"]["poetry"]["scripts"]["plexus"] == "plexus.cli.entrypoint:main"


def test_worker_scoring_extra_declares_legacy_cli_import_dependencies():
    """The worker image must import every command used by the demo fixture."""
    project_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())

    scoring = set(pyproject["tool"]["poetry"]["extras"]["scoring"])

    assert {
        "contractions",
        "openpyxl",
        "pandas",
        "pyarrow",
        "seaborn",
    } <= scoring
