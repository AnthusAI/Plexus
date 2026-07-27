from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import pytest

from docker.demo.core import DemoManifest, PHASES, render_artifacts
from docker.demo.harness import DemoHarness


@pytest.fixture(scope="session")
def harness() -> DemoHarness:
    output_dir = Path(os.environ["PLEXUS_DEMO_OUTPUT_DIR"])
    manifest = DemoManifest.load(output_dir / "manifest.json")
    return DemoHarness(
        manifest=manifest,
        output_dir=output_dir,
        promote=os.environ.get("PLEXUS_DEMO_PROMOTE") == "1",
        resume=os.environ.get("PLEXUS_DEMO_RESUME") == "1",
    )


def _run_phase(harness: DemoHarness, phase: str, action: Callable[[], dict]) -> None:
    for predecessor in PHASES[: PHASES.index(phase)]:
        if not harness.manifest.completed(predecessor):
            pytest.skip(f"prerequisite phase {predecessor} did not pass")
    if harness.resume and harness.manifest.completed(phase):
        pytest.skip(f"phase {phase} already passed")
    started = time.monotonic()
    try:
        summary = action()
    except Exception as exc:
        harness.manifest.record_phase(
            phase,
            passed=False,
            summary={"elapsed_seconds": round(time.monotonic() - started, 3)},
            error=str(exc),
        )
        harness.manifest.save(harness.manifest_path)
        render_artifacts(harness.manifest, harness.output_dir)
        raise
    summary = {**summary, "elapsed_seconds": round(time.monotonic() - started, 3)}
    harness.manifest.record_phase(phase, passed=True, summary=summary)
    harness.manifest.save(harness.manifest_path)
    render_artifacts(harness.manifest, harness.output_dir)


def test_01_infrastructure(harness: DemoHarness) -> None:
    _run_phase(harness, "infrastructure", harness.infrastructure)


def test_02_seed_run_scoped_public_fixture(harness: DemoHarness) -> None:
    _run_phase(harness, "seed", harness.seed)


def test_03_prediction_and_idempotency(harness: DemoHarness) -> None:
    _run_phase(harness, "prediction", harness.prediction)


def test_04_feedback_and_regression_evaluations(harness: DemoHarness) -> None:
    _run_phase(harness, "evaluation", harness.evaluation)


def test_05_reporting(harness: DemoHarness) -> None:
    _run_phase(harness, "reporting", harness.reporting)


def test_06_guarded_optimization(harness: DemoHarness) -> None:
    _run_phase(harness, "optimization", harness.optimization)


def test_07_recovery_and_idempotent_upgrade(harness: DemoHarness) -> None:
    _run_phase(harness, "recovery", harness.recovery)


def test_verify_retained_run(harness: DemoHarness) -> None:
    if os.environ.get("PLEXUS_DEMO_COMMAND") != "verify":
        pytest.skip("retained-run verification is a separate command")
    harness.verify_retained()
