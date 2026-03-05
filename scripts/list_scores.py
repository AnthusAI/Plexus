import sys
import os
import asyncio
from plexus.cli.shared.client_utils import create_client
from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

client = create_client()
account_id = resolve_account_id_for_command(client, None)

async def run():
    scorecard = Scorecard.get_by_external_id("1438", client=client)
    if not scorecard:
        print("Scorecard 1438 not found")
        return
    
    print(f"Scorecard: {scorecard.name} (ID: {scorecard.id})")
    
    # Try to find Medication Verification
    query = """
    query ListScores {
        listScores(limit: 1000) {
            items {
                id
                name
                externalId
                scorecardId
            }
        }
    }
    """
    res = client.execute(query)
    for item in res.get('listScores', {}).get('items', []):
        if item and 'Medication' in item.get('name', ''):
            print(item)

asyncio.run(run())

