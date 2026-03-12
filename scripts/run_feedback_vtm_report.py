#!/usr/bin/env python3
"""
Run the Feedback Analysis + Vector Topic Memory report.
Creates config if needed, then runs the report.
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.report.utils import resolve_account_id_for_command, resolve_report_config
    from plexus.dashboard.api.models.report_configuration import ReportConfiguration
    from plexus.reports.service import generate_report_with_parameters

    config_name = "Feedback Analysis + Vector Topic Memory"
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "feedback_and_vector_topic_memory_report.md")
    scorecard = "1438"
    days = "10"

    print("Creating client...")
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    print(f"Account ID: {account_id}")

    # Create config if it doesn't exist
    config = resolve_report_config(config_name, account_id, client)
    if not config:
        print(f"Creating config from {config_file}...")
        with open(config_file, "r") as f:
            content = f.read()
        config = ReportConfiguration.create(
            client=client,
            accountId=account_id,
            name=config_name,
            description="Feedback analysis + Vector Topic Memory",
            configuration=content,
        )
        print(f"Created config: {config.id}")
    else:
        print(f"Using existing config: {config.id} ({config.name})")

    # Run report
    print("Running report (scorecard=1438, days=10)...")
    report_id, first_block_error, task_id = generate_report_with_parameters(
        config_id=config.id,
        parameters={"scorecard": scorecard, "days": days},
        account_id=account_id,
        client=client,
        trigger="script",
        log_prefix="[RunScript]",
    )

    if first_block_error:
        print(f"Report completed with errors: {first_block_error}")
        print(f"Report ID: {report_id}")
    else:
        print(f"Report completed successfully!")
    print(f"Report ID: {report_id}")
    print(f"Task ID: {task_id}")
    print(f"\nView at: /lab/reports (or /reports/{report_id})")
    return 0 if first_block_error is None else 1

if __name__ == "__main__":
    sys.exit(main())
