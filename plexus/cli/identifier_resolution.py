"""Shared functions for resolving identifiers to IDs."""
from plexus.cli.console import console
from functools import lru_cache
from gql.transport.exceptions import TransportQueryError
from gql import gql
import logging

@lru_cache(maxsize=100)
def resolve_scorecard_identifier(client, identifier):
    """Resolve a scorecard identifier to its ID."""
    
    # First try direct ID lookup
    try:
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{identifier}") {{
                id
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        if result.get('getScorecard'):
            console.print(f"[dim]Found scorecard by ID: {identifier}[/dim]")
            return identifier
    except TransportQueryError as e:
        console.print(f"[dim]Error looking up by ID: {str(e)}[/dim]")
    except Exception as e:
        console.print(f"[dim]Error looking up by ID: {str(e)}[/dim]")
    
    # Try lookup by key
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 10) {{
                items {{
                    id
                    key
                    name
                }}
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            if len(items) > 1:
                console.print(f"[yellow]Warning: Found multiple scorecards with key '{identifier}':[/yellow]")
                for i, item in enumerate(items):
                    console.print(f"[yellow]{i+1}. {item.get('name')} (ID: {item.get('id')}, Key: {item.get('key')})[/yellow]")
                console.print(f"[yellow]Using the first match: {items[0].get('name')} (ID: {items[0].get('id')})[/yellow]")
            else:
                console.print(f"[dim]Found scorecard by key: {items[0]['id']} (key: {items[0].get('key')})[/dim]")
            return items[0]['id']
    except TransportQueryError as e:
        console.print(f"[dim]Error looking up by key: {str(e)}[/dim]")
    except Exception as e:
        console.print(f"[dim]Error looking up by key: {str(e)}[/dim]")
    
    # Try lookup by name
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 10) {{
                items {{
                    id
                    name
                    key
                }}
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            if len(items) > 1:
                console.print(f"[yellow]Warning: Found multiple scorecards with name '{identifier}':[/yellow]")
                for i, item in enumerate(items):
                    console.print(f"[yellow]{i+1}. {item.get('name')} (ID: {item.get('id')}, Key: {item.get('key')})[/yellow]")
                console.print(f"[yellow]Using the first match: {items[0].get('name')} (ID: {items[0].get('id')})[/yellow]")
            else:
                console.print(f"[dim]Found scorecard by name: {items[0]['id']} (name: {items[0].get('name')})[/dim]")
            return items[0]['id']
    except TransportQueryError as e:
        console.print(f"[dim]Error looking up by name: {str(e)}[/dim]")
    except Exception as e:
        console.print(f"[dim]Error looking up by name: {str(e)}[/dim]")
    
    # Try lookup by externalId
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ externalId: {{ eq: "{identifier}" }} }}, limit: 10) {{
                items {{
                    id
                    externalId
                    name
                    key
                }}
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            if len(items) > 1:
                console.print(f"[yellow]Warning: Found multiple scorecards with externalId '{identifier}':[/yellow]")
                for i, item in enumerate(items):
                    console.print(f"[yellow]{i+1}. {item.get('name')} (ID: {item.get('id')}, Key: {item.get('key')})[/yellow]")
                console.print(f"[yellow]Using the first match: {items[0].get('name')} (ID: {items[0].get('id')})[/yellow]")
            else:
                console.print(f"[dim]Found scorecard by externalId: {items[0]['id']} (externalId: {items[0].get('externalId')})[/dim]")
            return items[0]['id']
    except TransportQueryError as e:
        console.print(f"[dim]Error looking up by externalId: {str(e)}[/dim]")
    except Exception as e:
        console.print(f"[dim]Error looking up by externalId: {str(e)}[/dim]")
    
    # If we get here, try a more flexible search for the key
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(limit: 100) {{
                items {{
                    id
                    key
                    name
                    externalId
                }}
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        items = result.get('listScorecards', {}).get('items', [])
        
        # First try exact match on key
        key_matches = [item for item in items if item.get('key') == identifier]
        if key_matches:
            if len(key_matches) > 1:
                console.print(f"[yellow]Warning: Found multiple scorecards with key '{identifier}':[/yellow]")
                for i, item in enumerate(key_matches):
                    console.print(f"[yellow]{i+1}. {item.get('name')} (ID: {item.get('id')}, Key: {item.get('key')})[/yellow]")
                console.print(f"[yellow]Using the first match: {key_matches[0].get('name')} (ID: {key_matches[0].get('id')})[/yellow]")
            else:
                console.print(f"[dim]Found scorecard by exact key match: {key_matches[0]['id']} (key: {key_matches[0].get('key')})[/dim]")
            return key_matches[0]['id']
        
        # Then try exact match on externalId
        ext_id_matches = [item for item in items if item.get('externalId') == identifier]
        if ext_id_matches:
            if len(ext_id_matches) > 1:
                console.print(f"[yellow]Warning: Found multiple scorecards with externalId '{identifier}':[/yellow]")
                for i, item in enumerate(ext_id_matches):
                    console.print(f"[yellow]{i+1}. {item.get('name')} (ID: {item.get('id')}, Key: {item.get('key')})[/yellow]")
                console.print(f"[yellow]Using the first match: {ext_id_matches[0].get('name')} (ID: {ext_id_matches[0].get('id')})[/yellow]")
            else:
                console.print(f"[dim]Found scorecard by exact externalId match: {ext_id_matches[0]['id']} (externalId: {ext_id_matches[0].get('externalId')})[/dim]")
            return ext_id_matches[0]['id']
        
        # Then try exact match on name
        name_matches = [item for item in items if item.get('name') == identifier]
        if name_matches:
            if len(name_matches) > 1:
                console.print(f"[yellow]Warning: Found multiple scorecards with name '{identifier}':[/yellow]")
                for i, item in enumerate(name_matches):
                    console.print(f"[yellow]{i+1}. {item.get('name')} (ID: {item.get('id')}, Key: {item.get('key')})[/yellow]")
                console.print(f"[yellow]Using the first match: {name_matches[0].get('name')} (ID: {name_matches[0].get('id')})[/yellow]")
            else:
                console.print(f"[dim]Found scorecard by exact name match: {name_matches[0]['id']} (name: {name_matches[0].get('name')})[/dim]")
            return name_matches[0]['id']
    except TransportQueryError as e:
        console.print(f"[dim]Error during flexible search: {str(e)}[/dim]")
    except Exception as e:
        console.print(f"[dim]Error during flexible search: {str(e)}[/dim]")
    
    return None

@lru_cache(maxsize=100)
def resolve_score_identifier(client, scorecard_id: str, identifier: str):
    """Resolve a score identifier to its ID within a specific scorecard.
    
    Args:
        client: The API client
        scorecard_id: The ID of the scorecard containing the score
        identifier: The identifier to resolve (ID, name, key, or external ID)
        
    Returns:
        The score ID if found, None otherwise
    """
    # First try direct ID lookup
    try:
        query = f"""
        query GetScore {{
            getScore(id: "{identifier}") {{
                id
                section {{
                    scorecard {{
                        id
                    }}
                }}
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        score_data = result.get('getScore')
        if score_data and score_data.get('section', {}).get('scorecard', {}).get('id') == scorecard_id:
            return identifier
    except Exception:
        pass
    
    # Try lookup within the scorecard
    try:
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{scorecard_id}") {{
                sections {{
                    items {{
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        sections = result.get('getScorecard', {}).get('sections', {}).get('items', [])
        
        for section in sections:
            scores = section.get('scores', {}).get('items', [])
            for score in scores:
                if (score['id'] == identifier or 
                    score['name'] == identifier or 
                    score['key'] == identifier or 
                    score.get('externalId') == identifier):
                    return score['id']
    except Exception:
        pass
    
    return None 

async def resolve_data_source(client, identifier: str):
    """Resolve a DataSource identifier to a DataSource object.
    
    Args:
        client: The API client
        identifier: The identifier to resolve (ID, key, or name)
        
    Returns:
        The DataSource object if found, None otherwise
    """
    from plexus.dashboard.api.models.data_source import DataSource

    logging.debug(f"resolve_data_source called with identifier: {identifier}")

    # 1. Try to get by ID
    try:
        logging.debug("Attempting to resolve by ID...")
        data_source = await DataSource.get(client, identifier)
        if data_source:
            logging.info(f"Found DataSource by ID: {identifier}")
            return data_source
        else:
            logging.debug(f"No DataSource found with ID: {identifier}")
    except Exception as e:
        logging.debug(f"Could not find DataSource by ID {identifier}: {e}")

    # 2. Try to get by key
    try:
        logging.debug("Attempting to resolve by key...")
        data_sources = await DataSource.list_by_key(client, identifier)
        if data_sources:
            data_source = data_sources[0]  # Take the first match
            logging.info(f"Found DataSource by key '{identifier}': {data_source.id}")
            return data_source
        else:
            logging.debug(f"No DataSource found with key: {identifier}")
    except Exception as e:
        logging.debug(f"Could not find DataSource by key {identifier}: {e}")

    # 3. Try to get by name
    try:
        logging.debug("Attempting to resolve by name...")
        data_sources = await DataSource.list_by_name(client, identifier)
        if data_sources:
            data_source = data_sources[0]  # Take the first match
            logging.info(f"Found DataSource by name '{identifier}': {data_source.id}")
            return data_source
        else:
            logging.debug(f"No DataSource found with name: {identifier}")
    except Exception as e:
        logging.debug(f"Could not find DataSource by name {identifier}: {e}")

    logging.error(f"Could not resolve DataSource identifier: {identifier}")
    return None 

@lru_cache(maxsize=100)
def resolve_item_identifier(client, identifier: str, account_id: str = None):
    """Resolve an item identifier to its ID.
    
    Args:
        client: The API client
        identifier: The identifier to resolve (ID or any identifier value)
        account_id: Optional account ID to limit search scope
        
    Returns:
        The item ID if found, None otherwise
    """
    # First try direct ID lookup
    try:
        from plexus.dashboard.api.models.item import Item
        item = Item.get_by_id(identifier, client)
        if item:
            console.print(f"[dim]Found item by ID: {identifier}[/dim]")
            return identifier
    except ValueError:
        # Not found by ID, continue to identifier search
        pass
    except Exception as e:
        console.print(f"[dim]Error looking up item by ID: {str(e)}[/dim]")
    
    # If account_id is provided, try identifier value search
    if account_id:
        try:
            from plexus.utils.identifier_search import find_item_by_identifier
            item = find_item_by_identifier(identifier, account_id, client)
            if item:
                console.print(f"[dim]Found item by identifier value: {item.id} (value: {identifier})[/dim]")
                return item.id
        except Exception as e:
            console.print(f"[dim]Error looking up item by identifier value: {str(e)}[/dim]")
    
    # If no account_id provided, we can't do identifier search
    # Try to get account_id from environment or recent activity
    if not account_id:
        import os
        account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
        if account_key:
            # Try to resolve account_key to account_id
            try:
                from plexus.cli.reports.utils import resolve_account_id_for_command
                account_id = resolve_account_id_for_command(client, account_key)
                if account_id:
                    from plexus.utils.identifier_search import find_item_by_identifier
                    item = find_item_by_identifier(identifier, account_id, client)
                    if item:
                        console.print(f"[dim]Found item by identifier value (using env account): {item.id} (value: {identifier})[/dim]")
                        return item.id
            except Exception as e:
                console.print(f"[dim]Error resolving account from environment: {str(e)}[/dim]")
    
    return None 