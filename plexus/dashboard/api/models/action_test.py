import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from .action import Action
from .action_stage import ActionStage

@pytest.fixture
def mock_client():
    client = MagicMock()
    # Default response for getAction
    client.execute.return_value = {
        'getAction': {
            'id': 'test-action-id',
            'accountId': 'test-account',
            'type': 'TEST',
            'status': 'PENDING',
            'target': 'test/target',
            'command': 'test command'
        }
    }
    return client

@pytest.fixture
def mock_action(mock_client):
    return Action(
        id='test-action-id',
        accountId='test-account',
        type='TEST',
        status='PENDING',
        target='test/target',
        command='test command',
        createdAt=datetime(2024, 1, 1, tzinfo=timezone.utc),
        client=mock_client
    )

def test_create_action(mock_client):
    mock_client.execute.return_value = {
        'createAction': {
            'id': 'test-action-id',
            'accountId': 'test-account',
            'type': 'TEST',
            'status': 'PENDING',
            'target': 'test/target',
            'command': 'test command',
            'createdAt': '2024-01-01T00:00:00Z'
        }
    }
    
    action = Action.create(
        client=mock_client,
        accountId='test-account',
        type='TEST',
        target='test/target',
        command='test command'
    )
    assert action.id == 'test-action-id'
    assert action.accountId == 'test-account'
    assert action.type == 'TEST'
    assert action.status == 'PENDING'
    assert action.target == 'test/target'
    assert action.command == 'test command'
    assert action.createdAt == datetime(2024, 1, 1, tzinfo=timezone.utc)

def test_update_action(mock_client, mock_action):
    mock_client.execute.side_effect = [
        # First call - getAction
        {
            'getAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'PENDING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        # Second call - updateAction
        {
            'updateAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command',
                'startedAt': '2024-01-01T00:01:00Z'
            }
        }
    ]
    
    updated = mock_action.update(
        status='RUNNING',
        startedAt=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)
    )
    assert updated.status == 'RUNNING'
    assert updated.startedAt == datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)

def test_get_by_id(mock_client):
    mock_client.execute.return_value = {
        'getAction': {
            'id': 'test-action-id',
            'accountId': 'test-account',
            'type': 'TEST',
            'status': 'PENDING',
            'target': 'test/target',
            'command': 'test command',
            'createdAt': '2024-01-01T00:00:00Z'
        }
    }
    
    action = Action.get_by_id('test-action-id', mock_client)
    assert action.id == 'test-action-id'
    assert action.accountId == 'test-account'

def test_get_stages(mock_client, mock_action):
    mock_client.execute.return_value = {
        'listActionStages': {
            'items': [
                {
                    'id': 'stage-1',
                    'actionId': mock_action.id,
                    'name': 'Stage 1',
                    'order': 1,
                    'status': 'PENDING',
                    'processedItems': 0,
                    'totalItems': 100
                }
            ]
        }
    }
    
    stages = mock_action.get_stages()
    assert len(stages) == 1
    assert stages[0].id == 'stage-1'
    assert stages[0].name == 'Stage 1'

def test_start_processing(mock_client, mock_action):
    mock_client.execute.side_effect = [
        # First call - getAction
        {
            'getAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'PENDING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        # Second call - updateAction
        {
            'updateAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command',
                'startedAt': '2024-01-01T00:01:00Z'
            }
        }
    ]
    
    mock_action.start_processing()
    assert mock_client.execute.call_count == 2  # One for get, one for update
    assert 'RUNNING' in str(mock_client.execute.call_args_list[-1])

def test_complete_processing(mock_client, mock_action):
    mock_client.execute.side_effect = [
        # First call - getAction
        {
            'getAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        # Second call - updateAction
        {
            'updateAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'COMPLETED',
                'target': 'test/target',
                'command': 'test command',
                'completedAt': '2024-01-01T00:02:00Z'
            }
        }
    ]
    
    mock_action.complete_processing()
    assert mock_client.execute.call_count == 2
    assert 'COMPLETED' in str(mock_client.execute.call_args_list[-1])

def test_fail_processing(mock_client, mock_action):
    mock_client.execute.side_effect = [
        # First call - getAction
        {
            'getAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'RUNNING',
                'target': 'test/target',
                'command': 'test command'
            }
        },
        # Second call - updateAction
        {
            'updateAction': {
                'id': 'test-action-id',
                'accountId': 'test-account',
                'type': 'TEST',
                'status': 'FAILED',
                'target': 'test/target',
                'command': 'test command',
                'errorMessage': 'Test error',
                'completedAt': '2024-01-01T00:02:00Z'
            }
        }
    ]
    
    mock_action.fail_processing('Test error', {'details': 'test'})
    assert mock_client.execute.call_count == 2
    assert 'FAILED' in str(mock_client.execute.call_args_list[-1])
    assert 'Test error' in str(mock_client.execute.call_args_list[-1])

def test_update_progress(mock_client, mock_action):
    # Mock responses for each API call
    def mock_execute(query, variables):
        print(f"\nExecuting query: {query}")
        print(f"With variables: {variables}\n")
        
        # Clean up the query string for comparison
        query = ' '.join(query.split())
        print(f"Cleaned query: {query}")
        
        # Extract the operation type and name
        parts = query.split('(', 1)[0].strip().split()
        operation_type = parts[0] if parts else ''
        operation_name = parts[1] if len(parts) > 1 else ''
        print(f"Operation type: {operation_type}, name: {operation_name}")
        
        if operation_type == 'query':
            if operation_name == 'ListActionStages':
                return {
                    'listActionStages': {
                        'items': []
                    }
                }
            elif operation_name == 'GetAction':
                print("Matched GetAction query")
                return {
                    'getAction': {
                        'id': mock_action.id,
                        'accountId': 'test-account',
                        'type': 'TEST',
                        'status': 'PENDING',
                        'target': 'test/target',
                        'command': 'test command'
                    }
                }
            elif operation_name == 'GetActionStage':
                stage_id = variables.get('id')
                if stage_id:
                    return {
                        'getActionStage': {
                            'id': stage_id,
                            'actionId': mock_action.id,
                            'name': 'Test Stage',
                            'order': 1,
                            'status': 'PENDING',
                            'processedItems': 0,
                            'totalItems': 100,
                            'statusMessage': None,
                            'startedAt': None,
                            'completedAt': None,
                            'estimatedCompletionAt': None
                        }
                    }
                return {}
        elif operation_type == 'mutation':
            if operation_name == 'UpdateAction':
                return {
                    'updateAction': {
                        'id': mock_action.id,
                        'accountId': 'test-account',
                        'type': 'TEST',
                        'status': 'RUNNING',
                        'target': 'test/target',
                        'command': 'test command'
                    }
                }
            elif operation_name == 'CreateActionStage':
                stage_id = 'stage-1'
                return {
                    'createActionStage': {
                        'id': stage_id,
                        'actionId': mock_action.id,
                        'name': variables['input']['name'],
                        'order': variables['input']['order'],
                        'status': variables['input']['status'],
                        'processedItems': variables['input']['processedItems'],
                        'totalItems': variables['input']['totalItems'],
                        'statusMessage': None,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None
                    }
                }
            elif operation_name == 'UpdateActionStage':
                stage_id = variables['input']['id']
                print(f"Handling UpdateActionStage mutation with stage_id: {stage_id}")
                response = {
                    'updateActionStage': {
                        'id': stage_id,
                        'actionId': mock_action.id,
                        'name': 'Test Stage',
                        'order': 1,
                        'status': variables['input']['status'],
                        'processedItems': variables['input'].get('processedItems', 0),
                        'totalItems': variables['input'].get('totalItems', 100),
                        'statusMessage': None,
                        'startedAt': None,
                        'completedAt': None,
                        'estimatedCompletionAt': None
                    }
                }
                print(f"Returning response: {response}")
                return response
        
        print(f"No match found for operation type: {operation_type}, name: {operation_name}")
        return {}

    mock_client.execute = MagicMock(side_effect=mock_execute)
    
    stages = mock_action.update_progress(
        processed_items=50,
        total_items=100,
        stage_configs={
            'Test Stage': {
                'order': 1,
                'totalItems': 100,
                'processedItems': 0
            }
        }
    )
    
    assert len(stages) == 1
    assert stages[0].name == 'Test Stage'
    # Expected sequence:
    # 1. GetAction + UpdateAction (action.update)
    # 2. ListActionStages (get_stages)
    # 3. CreateActionStage (ActionStage.create)
    # 4. GetActionStage + UpdateActionStage (stage.update)
    assert mock_client.execute.call_count == 6

def test_fail_current_stage(mock_client, mock_action):
    # Mock responses for each API call
    def mock_execute(query, variables):
        if 'listActionStages' in query:
            return {
                'listActionStages': {
                    'items': [{
                        'id': 'stage-1',
                        'actionId': mock_action.id,
                        'name': 'Test Stage',
                        'order': 1,
                        'status': 'RUNNING',
                        'processedItems': 50,
                        'totalItems': 100
                    }]
                }
            }
        elif 'getActionStage' in query:
            return {
                'getActionStage': {
                    'id': 'stage-1',
                    'actionId': mock_action.id,
                    'name': 'Test Stage',
                    'order': 1,
                    'status': 'RUNNING'
                }
            }
        elif 'updateActionStage' in query:
            return {
                'updateActionStage': {
                    'id': 'stage-1',
                    'actionId': mock_action.id,
                    'name': 'Test Stage',
                    'order': 1,
                    'status': 'FAILED',
                    'statusMessage': 'Test error'
                }
            }
        return {}

    mock_client.execute = MagicMock(side_effect=mock_execute)
    
    mock_action.fail_current_stage('Test error', {'details': 'test'})
    assert mock_client.execute.call_count == 3  # get stages, get stage, update stage
    assert 'FAILED' in str(mock_client.execute.call_args_list[-1]) 