#!/usr/bin/env python3
"""
Run the Vector Topic Memory report (ONLY the memory block, no Feedback Analysis).
Creates config if needed, then runs the report.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.report.utils import resolve_account_id_for_command, resolve_report_config
    from plexus.dashboard.api.models.report_configuration import ReportConfiguration
    from plexus.reports.service import generate_report_with_parameters

    parser = argparse.ArgumentParser(description="Run the Vector Topic Memory report")
    parser.add_argument("--scorecard", type=str, required=True, help="The Scorecard ID (or external ID)")
    parser.add_argument("--score-id", type=str, help="Optional specific Score ID to filter by")
    parser.add_argument("--days", type=str, default="90", help="Number of days to analyze (default: 90)")
    args = parser.parse_args()

    config_name = "Semantic Reinforcement Memory"
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_topic_memory_report.md")

    print("Creating client...")
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    print(f"Account ID: {account_id}")

    with open(config_file, "r") as f:
        template_content = f.read()

    config = resolve_report_config(config_name, account_id, client)
    if not config:
        print(f"Creating config from {config_file}...")
        config = ReportConfiguration.create(
            client=client,
            accountId=account_id,
            name=config_name,
            description="Vector Topic Memory only — tests the memory system",
            configuration=template_content,
        )
        print(f"Created config: {config.id}")
    else:
        print(f"Syncing config from {config_file}...")
        config = config.update(
            client=client,
            name=config.name,
            accountId=account_id,
            configuration=template_content,
            description="Vector Topic Memory only — tests the memory system",
        )
        print(f"Using config: {config.id} ({config.name})")

    report_params = {"scorecard": args.scorecard, "days": args.days}
    if args.score_id:
        report_params["score_id"] = args.score_id
        print(f"Running report for score_id: {args.score_id} (Vector Topic Memory only)...")
    else:
        print(f"Running report for all scores in scorecard {args.scorecard} (Vector Topic Memory only)...")

    report_id, first_block_error, task_id = generate_report_with_parameters(
        config_id=config.id,
        parameters=report_params,
        account_id=account_id,
        client=client,
        trigger="script",
        log_prefix="[RunScript]",
    )

    if first_block_error:
        print(f"Report completed with errors: {first_block_error}")
    else:
        print("Report completed successfully!")
    print(f"Report ID: {report_id}")
    print(f"Task ID: {task_id}")
    print(f"\nView at: /lab/reports or /reports/{report_id}")
    return 0 if first_block_error is None else 1

if __name__ == "__main__":
    sys.exit(main())
