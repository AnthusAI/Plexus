from pathlib import Path


def test_packaged_async_score_processor_exposes_an_isolated_handler() -> None:
    from plexus.runtime.async_score_processor import handler

    assert callable(handler.lambda_handler)
    assert "plexus/runtime/async_score_processor" in Path(handler.__file__).as_posix()


def test_packaged_async_score_processor_exposes_a_self_contained_dockerfile() -> None:
    from plexus.runtime.async_score_processor import dockerfile_path

    dockerfile = dockerfile_path()
    contents = dockerfile.read_text()

    assert dockerfile.name == "Dockerfile"
    assert "ARG PLEXUS_REF" in contents
    assert "^[0-9a-f]{40}$" in contents
    assert 'git fetch --depth=1 origin "${PLEXUS_REF}"' in contents
    assert 'test "$(git rev-parse HEAD)" = "${PLEXUS_REF}"' in contents
    assert "poetry install --only main --extras scoring --no-root" in contents
    assert "poetry build --format wheel" in contents
    assert "COPY ." not in contents
    assert "COPY plexus" not in contents
    assert "COPY score-processor-lambda" not in contents
    assert (
        'CMD ["plexus.runtime.async_score_processor.handler.lambda_handler"]'
        in contents
    )


def test_legacy_score_processor_files_remain_separate_from_packaged_runtime() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    legacy_dockerfile = repository_root / "score-processor-lambda" / "Dockerfile"
    legacy_handler = repository_root / "score-processor-lambda" / "handler.py"

    assert legacy_dockerfile.is_file()
    assert legacy_handler.is_file()
    assert "plexus.runtime.async_score_processor" not in legacy_dockerfile.read_text()
    assert "plexus.runtime.async_score_processor" not in legacy_handler.read_text()
