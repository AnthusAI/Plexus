from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from docker.demo.core import DemoManifest, PHASES, generated_run_id, render_artifacts, validate_run_id
from docker.demo.bootstrap import SnapshotDeployer
from docker.demo.harness import DemoHarness


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run the Plexus Docker Desktop Kubernetes demo suite.")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--run-id", required=name in {"resume", "verify"})
        command.add_argument("--profile", choices=("strict", "guardrail"), default="strict")
        command.add_argument("--output-dir", type=Path)
        command.add_argument("--max-cost-usd", type=float, default=10.0)
        command.add_argument("--max-iterations", type=int, choices=(1, 2), default=2)
        command.add_argument("--promote", action="store_true")
        if name == "run":
            command.add_argument(
                "--deploy",
                action="store_true",
                help="Build an immutable HEAD snapshot and install or upgrade the local stack first.",
            )

    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--run-id", required=True)
    cleanup.add_argument("--output-dir", type=Path)
    cleanup.add_argument("--confirm", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run_id = validate_run_id(args.run_id) if args.run_id else generated_run_id()
    output_dir = require_external_output_dir(
        args.output_dir or Path("/tmp/plexus-k8s-demo") / run_id
    )
    manifest_path = output_dir / "manifest.json"

    if args.command == "cleanup":
        if not args.confirm:
            parser().error("cleanup requires --confirm")
        if not manifest_path.exists():
            parser().error(f"manifest not found: {manifest_path}")
        manifest = DemoManifest.load(manifest_path)
        deleted = DemoHarness(manifest, output_dir).cleanup()
        print(f"Cleaned demo run {run_id}: {sum(deleted.values())} prefixed records")
        return 0

    if manifest_path.exists():
        manifest = DemoManifest.load(manifest_path)
        if manifest.run_id != run_id:
            parser().error("output directory contains a different run ID")
        args.command = resolve_existing_command(args.command, manifest)
    else:
        if args.command in {"resume", "verify"}:
            parser().error(f"{args.command} requires an existing manifest: {manifest_path}")
        manifest = DemoManifest.new(run_id, args.profile, args.max_cost_usd, args.max_iterations)
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest.save(manifest_path)
        render_artifacts(manifest, output_dir)

    if args.command == "run" and args.deploy:
        deployment = SnapshotDeployer(output_dir).deploy()
        manifest.metadata["deployment"] = deployment
        manifest.save(manifest_path)

    env = os.environ.copy()
    env.update(
        {
            "PLEXUS_DEMO_COMMAND": args.command,
            "PLEXUS_DEMO_OUTPUT_DIR": str(output_dir.resolve()),
            "PLEXUS_DEMO_PROMOTE": "1" if args.promote else "0",
            "PLEXUS_DEMO_RESUME": "1" if args.command == "resume" else "0",
        }
    )
    suite = Path(__file__).with_name("acceptance_suite.py")
    pytest_args = [
        sys.executable,
        "-m",
        "pytest",
        str(suite),
        "-q",
        "--junitxml",
        str((output_dir / "junit.xml").resolve()),
    ]
    if args.command == "verify":
        pytest_args.extend(("-k", "verify_retained_run"))
    else:
        pytest_args.extend(("-k", "not verify_retained_run"))
    completed = subprocess.run(pytest_args, env=env, check=False)
    manifest = DemoManifest.load(manifest_path)
    render_artifacts(manifest, output_dir)
    print(f"Artifacts: {output_dir.resolve()}")
    return completed.returncode


def resolve_existing_command(command: str, manifest: DemoManifest) -> str:
    if command != "run":
        return command
    return "verify" if all(manifest.completed(phase) for phase in PHASES) else "resume"


def require_external_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[2]
    if resolved == repository_root or repository_root in resolved.parents:
        raise ValueError("demo artifacts must be written outside the repository")
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())
