"""Generate a go/no-go report draft from runtime MCP harness results.

This produces a report scaffold from `results/<run-id>/` without pretending that
stub-only results satisfy the real spike gate. The final go/no-go decision still
requires frontier-model runs from `plx-724038`.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness import BOOT_PROMPT, BOOT_PROMPT_TOKEN_LIMIT, estimate_tokens, load_tasks


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
REPORT_TEMPLATE = ROOT / "report_template.md"


@dataclass
class SummaryRow:
    task_id: str
    model_id: str
    succeeded_first_try: bool
    attempts_used: int
    total_input_tokens: int
    total_output_tokens: int
    tool_definition_tokens: int
    latency_ms: int
    total_cost_usd: float
    failure_classification: str


def load_summary(run_id: str) -> list[SummaryRow]:
    path = RESULTS_DIR / run_id / "summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"No summary found at {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            SummaryRow(
                task_id=row["task_id"],
                model_id=row["model_id"],
                succeeded_first_try=row["succeeded_first_try"].lower() == "true",
                attempts_used=int(row["attempts_used"]),
                total_input_tokens=int(row["total_input_tokens"]),
                total_output_tokens=int(row["total_output_tokens"]),
                tool_definition_tokens=int(row["tool_definition_tokens"]),
                latency_ms=int(row["latency_ms"]),
                total_cost_usd=float(row["total_cost_usd"]),
                failure_classification=row["failure_classification"],
            )
            for row in reader
        ]


def load_result_details(run_id: str) -> list[dict[str, Any]]:
    root = RESULTS_DIR / run_id
    details: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*.json")):
        details.append(json.loads(path.read_text()))
    return details


def load_catalog_measurement(run_id: str) -> dict[str, Any] | None:
    path = RESULTS_DIR / run_id / "mcp_catalog_measurement.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_run_metadata(run_id: str) -> dict[str, Any] | None:
    path = RESULTS_DIR / run_id / "run_metadata.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def summarize(rows: list[SummaryRow], details: list[dict[str, Any]]) -> dict[str, Any]:
    curated_task_count = len(load_tasks())
    by_model: dict[str, list[SummaryRow]] = defaultdict(list)
    by_task: dict[str, list[SummaryRow]] = defaultdict(list)
    for row in rows:
        by_model[row.model_id].append(row)
        by_task[row.task_id].append(row)

    model_summaries = []
    for model_id, model_rows in sorted(by_model.items()):
        passed = sum(row.succeeded_first_try for row in model_rows)
        total = len(model_rows)
        model_summaries.append(
            {
                "model_id": model_id,
                "passed": passed,
                "total": total,
                "success_rate": passed / total if total else 0,
                "input_tokens": sum(row.total_input_tokens for row in model_rows),
                "output_tokens": sum(row.total_output_tokens for row in model_rows),
                "cost_usd": sum(row.total_cost_usd for row in model_rows),
                "latency_ms": sum(row.latency_ms for row in model_rows),
            }
        )

    failures = [row for row in rows if not row.succeeded_first_try]
    real_model_summaries = [
        summary for summary in model_summaries if summary["model_id"] != "stub-oracle"
    ]
    complete_real_model_summaries = [
        summary for summary in real_model_summaries if summary["total"] >= curated_task_count
    ]
    pass_gate_models = [
        summary
        for summary in complete_real_model_summaries
        if summary["success_rate"] >= 0.85
    ]
    decision_ready = len(complete_real_model_summaries) >= 4
    gate_passed = decision_ready and len(pass_gate_models) >= 2

    stream_event_count = sum(len(detail.get("stream_events", [])) for detail in details)
    stream_summaries = [
        {
            "task_id": detail.get("task_id"),
            "model_id": detail.get("model_id"),
            "stream_event_count": len(detail.get("stream_events", [])),
            "event_types": sorted(
                {
                    event.get("event", "unknown")
                    for event in detail.get("stream_events", [])
                }
            ),
        }
        for detail in details
        if detail.get("stream_events")
    ]
    average_tool_definition_tokens = (
        sum(row.tool_definition_tokens for row in rows) / len(rows) if rows else 0
    )
    current_boot_prompt_tokens = estimate_tokens(BOOT_PROMPT.read_text())

    return {
        "model_summaries": model_summaries,
        "failures": failures,
        "decision_ready": decision_ready,
        "gate_passed": gate_passed,
        "pass_gate_model_count": len(pass_gate_models),
        "real_model_count": len(real_model_summaries),
        "complete_real_model_count": len(complete_real_model_summaries),
        "curated_task_count": curated_task_count,
        "stream_event_count": stream_event_count,
        "stream_summaries": stream_summaries,
        "average_tool_definition_tokens": average_tool_definition_tokens,
        "current_boot_prompt_tokens": current_boot_prompt_tokens,
        "boot_prompt_token_limit": BOOT_PROMPT_TOKEN_LIMIT,
    }


def render_markdown(
    run_id: str,
    rows: list[SummaryRow],
    summary: dict[str, Any],
    catalog_measurement: dict[str, Any] | None,
    run_metadata: dict[str, Any] | None,
) -> str:
    if not rows:
        raise ValueError("Cannot render report for empty result set")

    recommendation = "PENDING"
    recommendation_detail = (
        "Real frontier-model results are not complete. Do not make a go/no-go decision yet."
    )
    if summary["decision_ready"]:
        if summary["gate_passed"]:
            recommendation = "GO"
            recommendation_detail = (
                "At least 2 real models achieved >=85% first-try success."
            )
        else:
            recommendation = "NO-GO / REWORK"
            recommendation_detail = (
                "Fewer than 2 real models achieved >=85% first-try success."
            )

    lines = [
        "# Runtime MCP Validation Report",
        "",
        f"Run ID: `{run_id}`",
        "",
        "## 1. Executive Summary",
        "",
        f"Recommendation: **{recommendation}**",
        "",
        recommendation_detail,
        "",
        "Proceed gate: >=85% first-try success on at least 2 of 4 real frontier models.",
        f"A real model only counts toward the gate after covering all `{summary['curated_task_count']}` curated tasks.",
        "",
        f"Real model count in this run: `{summary['real_model_count']}`.",
        f"Complete real model count in this run: `{summary['complete_real_model_count']}`.",
        f"Models meeting gate threshold: `{summary['pass_gate_model_count']}`.",
        "",
        "## 2. Quantitative Results",
        "",
        "| Model | Passed | Total | First-Try Success | Input Tokens | Output Tokens | Cost USD | Latency ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in summary["model_summaries"]:
        lines.append(
            "| {model_id} | {passed} | {total} | {success:.1%} | {input_tokens} | {output_tokens} | {cost:.6f} | {latency} |".format(
                model_id=model["model_id"],
                passed=model["passed"],
                total=model["total"],
                success=model["success_rate"],
                input_tokens=model["input_tokens"],
                output_tokens=model["output_tokens"],
                cost=model["cost_usd"],
                latency=model["latency_ms"],
            )
        )

    lines.extend(
        [
            "",
            "## 3. Failure-Mode Classification",
            "",
        ]
    )
    if not summary["failures"]:
        lines.append("No failed task/model pairs in this result set.")
    else:
        lines.extend(
            [
                "| Task | Model | Classification |",
                "|---|---|---|",
            ]
        )
        for failure in summary["failures"]:
            lines.append(
                f"| `{failure.task_id}` | `{failure.model_id}` | `{failure.failure_classification or 'unclassified'}` |"
            )

    lines.extend(
        [
            "",
            "## 4. Streaming UX Assessment",
            "",
            f"Observed stream event count across result details: `{summary['stream_event_count']}`.",
            "",
        ]
    )
    if summary["stream_summaries"]:
        lines.extend(
            [
                "| Task | Model | Events | Event Types |",
                "|---|---|---:|---|",
            ]
        )
        for stream in summary["stream_summaries"]:
            lines.append(
                f"| `{stream['task_id']}` | `{stream['model_id']}` | {stream['stream_event_count']} | `{', '.join(stream['event_types'])}` |"
            )
        lines.append("")
    lines.extend(
        [
            "For real-provider runs, inspect transcripts and progress events for long-running evaluation tasks before finalizing this section.",
            "",
            "## 5. Context / Token Overhead",
            "",
            f"Average tool-definition / boot-prompt tokens per task: `{summary['average_tool_definition_tokens']:.0f}`.",
            f"Current `boot_prompt.md` estimated tokens: `{summary['current_boot_prompt_tokens']}` / `{summary['boot_prompt_token_limit']}`.",
        ]
    )
    if catalog_measurement:
        current = catalog_measurement["current_mcp_catalog"]
        single = catalog_measurement["single_execute_tactus_tool"]
        lines.extend(
            [
                f"Measured current MCP catalog: `{catalog_measurement['current_mcp_tool_count']}` tools, `{current['tokens']}` estimated tokens, `{current['bytes']}` bytes.",
                f"Measured single `execute_tactus` payload: `{single['tokens']}` estimated tokens, `{single['bytes']}` bytes.",
                f"Measured token reduction: `{catalog_measurement['token_reduction']}` tokens, `{catalog_measurement['token_reduction_ratio']}x` smaller.",
                "",
                "Largest current tool schemas by estimated tokens:",
                "",
                "| Tool | Tokens | Bytes |",
                "|---|---:|---:|",
            ]
        )
        for tool in catalog_measurement["largest_current_tools"]:
            lines.append(f"| `{tool['name']}` | {tool['tokens']} | {tool['bytes']} |")
        lines.append("")
    else:
        lines.extend(
            [
                "",
                "MCP catalog measurement is missing. Run `python spikes/runtime-mcp-validation/measure_mcp_catalog.py --run-id <run-id>` before final go/no-go.",
                "",
            ]
        )
    lines.extend(
        [
            "## 6. Decision",
            "",
        ]
    )
    if run_metadata:
        cost_plan = run_metadata.get("cost_plan", {})
        lines.extend(
            [
                "Run cost plan:",
                "",
                f"- Real provider calls planned: `{cost_plan.get('real_call_count')}`",
                f"- Estimated real-provider cost: `${cost_plan.get('estimated_cost_usd')}`",
                f"- Max total cost cap: `${cost_plan.get('max_total_cost_usd')}`",
                f"- Estimated cost per real call: `${cost_plan.get('estimated_real_call_cost_usd')}`",
                "",
            ]
        )
    if summary["decision_ready"]:
        lines.append(f"Decision: **{recommendation}**.")
    else:
        lines.append(
            "Decision: **PENDING**. Real frontier-model results from `plx-724038` are required."
        )

    return "\n".join(lines) + "\n"


def write_report(run_id: str) -> Path:
    rows = load_summary(run_id)
    details = load_result_details(run_id)
    catalog_measurement = load_catalog_measurement(run_id)
    run_metadata = load_run_metadata(run_id)
    summary = summarize(rows, details)
    markdown = render_markdown(run_id, rows, summary, catalog_measurement, run_metadata)
    path = RESULTS_DIR / run_id / "report.md"
    path.write_text(markdown)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Harness result run id")
    args = parser.parse_args()
    path = write_report(args.run_id)
    print(json.dumps({"report": str(path)}, indent=2))


if __name__ == "__main__":
    main()
