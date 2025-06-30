"""Functions for fetching scorecard structures from the API."""

import logging
from typing import Dict, Any, Optional
from plexus.cli.direct_memoized_resolvers import direct_memoized_resolve_scorecard_identifier

def fetch_scorecard_structure(client, identifier: str) -> Optional[Dict[str, Any]]:
    """Fetch the basic structure of a scorecard without the full configurations.
    
    This function fetches minimal scorecard data including sections and scores,
    but importantly WITHOUT the champion version configurations to reduce data transfer.
    
    Args:
        client: The API client
        identifier: Scorecard identifier (ID, name, key, or external ID)
        
    Returns:
        Dict containing scorecard structure or None if not found
    """
    # First resolve the identifier to an ID
    scorecard_id = direct_memoized_resolve_scorecard_identifier(client, identifier)
    if not scorecard_id:
        logging.error(f"Could not resolve scorecard identifier: {identifier}")
        return None
    
    # Now fetch the minimal structure
    query = """
    query GetScorecardStructure($id: ID!) {
      getScorecard(id: $id) {
        id
        name
        key
        externalId
        sections {
          items {
            id
            name
            scores {
              items {
                id
                name
                key
                externalId
                championVersionId
              }
            }
          }
        }
      }
    }
    """
    
    try:
        # Execute the query directly without using the client as a context manager
        result = client.execute(query, {'id': scorecard_id})
        
        if not result or 'getScorecard' not in result:
            logging.error(f"Could not fetch scorecard with ID: {scorecard_id}")
            return None
        
        return result['getScorecard']
    except Exception as e:
        logging.error(f"Error fetching scorecard structure: {str(e)}")
        return None 