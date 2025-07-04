'''Core logic for item management commands.'''
from typing import Optional, Dict, List, Any
import os
import glob
import json
import yaml
from plexus.dashboard.api.models.item import Item
from plexus.dashboard.api.models.identifier import Identifier
from plexus.cli.client_utils import PlexusDashboardClient

def _process_item_folder(item_path: str) -> Dict[str, Any]:
    """Process a folder to extract item data."""
    item_data = {
        'attachedFiles': [],
        'metadata': {},
        'identifiers': [],
        'text': None
    }

    for root, _, files in os.walk(item_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file == 'text.txt':
                with open(file_path, 'r') as f:
                    item_data['text'] = f.read()
            elif file in ('metadata.json', 'metadata.yaml'):
                with open(file_path, 'r') as f:
                    if file.endswith('.json'):
                        item_data['metadata'] = json.load(f)
                    else:
                        item_data['metadata'] = yaml.safe_load(f)
            elif file in ('identifiers.json', 'identifiers.yaml'):
                with open(file_path, 'r') as f:
                    if file.endswith('.json'):
                        item_data['identifiers'] = json.load(f)
                    else:
                        item_data['identifiers'] = yaml.safe_load(f)
            else:
                item_data['attachedFiles'].append(file_path)
    
    return item_data

def resolve_item(client: PlexusDashboardClient, account_id: str, item_identifier: str) -> Optional[Item]:
    """Resolve an item by its ID, external ID, or an identifier value."""
    # 1. Try by direct Item ID
    try:
        item = Item.get_by_id(item_identifier, client)
        if item and item.accountId == account_id:
            return item
    except Exception:
        pass  # Not found by ID

    # 2. Try by externalId
    query_external_id = f"""
    query GetItemByExternalId($accountId: String!, $externalId: String!) {{
        itemsByAccountIdAndExternalId(accountId: $accountId, externalId: {{eq: $externalId}}) {{
            items {{
                {Item.fields()}
            }}
        }}
    }}
    """
    result = client.execute(query_external_id, {'accountId': account_id, 'externalId': item_identifier})
    items = result.get('itemsByAccountIdAndExternalId', {}).get('items', [])
    if items:
        return Item.from_dict(items[0], client)

    # 3. Try by Identifier
    identifier = Identifier.find_by_value(item_identifier, account_id, client)
    if identifier:
        try:
            item = Item.get_by_id(identifier.itemId, client)
            if item and item.accountId == account_id:
                return item
        except Exception:
            pass  # Item not found for this identifier

    return None

def insert_items(
    client: PlexusDashboardClient, 
    account_id: str, 
    item_path_glob: str, 
    evaluation_id: Optional[str], 
    score_id: Optional[str], 
    is_evaluation: bool
) -> List[Dict[str, Any]]:
    """Logic to insert one or more items from folder paths."""
    results = []
    item_paths = glob.glob(item_path_glob)
    if not item_paths:
        return [{'path': item_path_glob, 'status': 'error', 'message': 'No items found matching path'}]

    for item_path in item_paths:
        if not os.path.isdir(item_path):
            continue

        item_data = _process_item_folder(item_path)

        kwargs = {
            'accountId': account_id,
            'isEvaluation': is_evaluation,
            'text': item_data.get('text'),
            'metadata': item_data.get('metadata'),
            'attachedFiles': item_data.get('attachedFiles'),
            'identifiers': item_data.get('identifiers', [])
        }
        kwargs['identifiers'].append({'name': 'folderPath', 'value': os.path.relpath(item_path)})

        if score_id:
            kwargs['scoreId'] = score_id
        
        try:
            new_item = Item.create(
                client=client,
                evaluationId=evaluation_id,
                **kwargs
            )
            results.append({'path': item_path, 'status': 'success', 'item': new_item})
        except Exception as e:
            results.append({'path': item_path, 'status': 'error', 'message': str(e)})
    
    return results

def upsert_items(
    client: PlexusDashboardClient, 
    account_id: str, 
    item_path_glob: str, 
    evaluation_id: Optional[str], 
    score_id: Optional[str], 
    is_evaluation: bool
) -> List[Dict[str, Any]]:
    """Logic to upsert one or more items from folder paths."""
    results = []
    item_paths = glob.glob(item_path_glob)
    if not item_paths:
        return [{'path': item_path_glob, 'status': 'error', 'message': 'No items found matching path'}]

    for item_path in item_paths:
        if not os.path.isdir(item_path):
            continue

        item_data = _process_item_folder(item_path)
        relative_path = os.path.relpath(item_path)

        item = resolve_item(client, account_id, relative_path)

        kwargs = {
            'text': item_data.get('text'),
            'metadata': item_data.get('metadata'),
            'attachedFiles': item_data.get('attachedFiles'),
        }

        if item:
            # Update existing item
            try:
                updated_item = item.update(**kwargs)
                results.append({'path': item_path, 'status': 'updated', 'item': updated_item})
            except Exception as e:
                results.append({'path': item_path, 'status': 'error', 'message': str(e)})
        else:
            # Create new item
            create_kwargs = {
                'accountId': account_id,
                'isEvaluation': is_evaluation,
                'identifiers': item_data.get('identifiers', [])
            }
            create_kwargs['identifiers'].append({'name': 'folderPath', 'value': relative_path})
            if score_id:
                create_kwargs['scoreId'] = score_id
            
            create_kwargs.update(kwargs)

            try:
                new_item = Item.create(
                    client=client,
                    evaluationId=evaluation_id,
                    **create_kwargs
                )
                results.append({'path': item_path, 'status': 'inserted', 'item': new_item})
            except Exception as e:
                results.append({'path': item_path, 'status': 'error', 'message': str(e)})
    return results

def delete_item(client: PlexusDashboardClient, account_id: str, item_identifier: str) -> Dict[str, Any]:
    """Logic to delete an item."""
    item = resolve_item(client, account_id, item_identifier)
    if not item:
        return {'status': 'error', 'message': f'Item \'{item_identifier}\' not found'}

    try:
        item.delete()
        return {'status': 'success', 'item_id': item.id}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}