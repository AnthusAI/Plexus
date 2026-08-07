from pathlib import Path


def test_clean_runtime_dependency_audit_installs_only_the_command_service_extra() -> None:
    script = (
        Path(__file__).parents[2]
        / "scripts"
        / "audit-command-service-runtime-dependencies.sh"
    ).read_text(encoding="utf-8")

    assert 'mktemp -d "${TMPDIR:-/tmp}/plexus-command-runtime-audit.XXXXXX"' in script
    assert 'audit_python="${PYTHON:-python3}"' in script
    assert 'command-service runtime audit requires Python >=3.11,<3.13' in script
    assert '(3, 11) <= sys.version_info[:2] < (3, 13)' in script
    assert 'install --no-build-isolation "$root_dir[command-service-runtime]"' in script
    assert 'cd "$audit_dir"' in script
    assert 'python" -m plexus.command_worker.smoke' in script
    assert 'from kombu.asynchronous.http.curl import CurlClient; CurlClient()' in script
    assert "[all]" not in script
    assert "[ml]" not in script
