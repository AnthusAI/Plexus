import json
from plexus.cli.shared.client_utils import create_client
from plexus.dashboard.api.models.report import Report

client = create_client()
report = Report.get_by_id("31479875-dfc7-4592-9b6e-f4f439e5eb22", client)
if not report:
    print("Report not found")
else:
    for block in getattr(report, 'blocks', getattr(report, 'reportBlocks', getattr(report, 'report_blocks', getattr(report, 'items', getattr(report, 'ReportBlocks', []))))):
        print(f"Block: {block.name}")
        try:
            out = json.loads(block.output)
            print("Keys in output:", list(out.keys()))
            if "scores" in out:
                print(f"Found {len(out['scores'])} scores")
                for s in out["scores"]:
                    print(f"  - {s['score_name']}: {s.get('items_processed')} items, {len(s.get('topics', []))} topics")
                    for t in s.get("topics", []):
                        print(f"      Topic: {t['label']} ({t.get('memory_tier')}, {t.get('days_inactive')}d inactive)")
            else:
                print("No scores key in output")
        except Exception as e:
            print("Error parsing output", e)
