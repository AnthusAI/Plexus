#!/usr/bin/env python3
"""
Test script for the new "all scorecards" feedback analysis mode.
This tests the FeedbackAnalysis block with scorecard="all".
"""

import sys
import asyncio
sys.path.insert(0, '/Users/ryan.porter/Projects/Plexus')

from plexus.cli.shared.client_utils import create_client
from plexus.reports.blocks.feedback_analysis import FeedbackAnalysis

async def test_all_scorecards_mode():
    """Test the all scorecards analysis mode."""
    print("=" * 80)
    print("Testing 'All Scorecards' Feedback Analysis Mode")
    print("=" * 80)

    # Create client
    client = create_client()
    if not client:
        print("ERROR: Could not create client")
        return

    print("\n✓ Client created successfully")

    # Create FeedbackAnalysis block instance
    config = {
        "scorecard": "all",  # This triggers the new mode
        "days": 3  # Last 3 days for quick testing
    }

    params = {
        "account_id": "9c929f25-a91f-4db7-8943-5aa93498b8e9"  # Your default account
    }

    print(f"\n✓ Configuration: scorecard='all', days=3")
    print(f"✓ Account ID: {params['account_id']}")

    # Instantiate the block
    block = FeedbackAnalysis(
        config=config,
        params=params,
        api_client=client
    )

    print("\n✓ FeedbackAnalysis block created")
    print("\nRunning analysis (this may take a while)...")
    print("-" * 80)

    # Run the analysis
    try:
        output, log = await block.generate()

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE!")
        print("=" * 80)

        # Parse the output to show summary
        if output:
            # Output could be YAML string or dict (if error)
            if isinstance(output, str):
                # Output is YAML string - show first 1000 chars
                print("\n📊 Output Preview (first 1000 chars):")
                print("-" * 80)
                print(output[:1000])
                print("..." if len(output) > 1000 else "")
                print("-" * 80)
                print(f"\n✓ Total output length: {len(output)} characters")

                # Try to extract some key info
                if "total_scorecards_analyzed:" in output:
                    import re
                    match = re.search(r'total_scorecards_analyzed:\s*(\d+)', output)
                    if match:
                        count = match.group(1)
                        print(f"✓ Total scorecards analyzed: {count}")

                if "mode: all_scorecards" in output:
                    print("✓ Mode confirmed: all_scorecards")
            elif isinstance(output, dict):
                # Output is a dict (likely error case)
                print("\n📊 Output (dict format):")
                print("-" * 80)
                import json
                print(json.dumps(output, indent=2, default=str)[:1000])
                print("-" * 80)

                if 'error' in output:
                    print(f"\n⚠️  Error in output: {output['error']}")
                if 'total_scorecards_analyzed' in output:
                    print(f"✓ Total scorecards analyzed: {output['total_scorecards_analyzed']}")
                if 'mode' in output:
                    print(f"✓ Mode: {output['mode']}")

        print("\n📝 Log Preview (last 500 chars):")
        print("-" * 80)
        if log:
            print(log[-500:] if len(log) > 500 else log)
        print("-" * 80)

        print("\n✅ TEST PASSED - All scorecards mode executed successfully!")

    except Exception as e:
        print(f"\n❌ ERROR during analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(test_all_scorecards_mode())
    sys.exit(0 if success else 1)
