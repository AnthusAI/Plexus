"""Shared functions for resolving identifiers to IDs."""
from plexus.cli.console import console
from functools import lru_cache

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
        result = client.execute(query)
        if result.get('getScorecard'):
            console.print(f"[dim]Found scorecard by ID: {identifier}[/dim]")
            return identifier
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
        result = client.execute(query)
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
        result = client.execute(query)
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
        result = client.execute(query)
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
        result = client.execute(query)
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
        result = client.execute(query)
        score_data = result.get('getScore')
        if score_data and score_data.get('section', {}).get('scorecard', {}).get('id') == scorecard_id:
            return identifier
    except:
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
        result = client.execute(query)
        sections = result.get('getScorecard', {}).get('sections', {}).get('items', [])
        
        for section in sections:
            scores = section.get('scores', {}).get('items', [])
            for score in scores:
                if (score['id'] == identifier or 
                    score['name'] == identifier or 
                    score['key'] == identifier or 
                    score.get('externalId') == identifier):
                    return score['id']
    except:
        pass
    
    return None 