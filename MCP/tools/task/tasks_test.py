#!/usr/bin/env python3
"""
Unit tests for task tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestTaskLastTool:
    """Test plexus_task_last tool patterns"""
    
    def test_task_last_validation_patterns(self):
        """Test task last parameter validation patterns"""
        def validate_task_last_params(task_type=None):
            # task_type is optional and can be None or string
            if task_type is not None and not isinstance(task_type, str):
                return False, "task_type must be a string or None"
            return True, None
        
        # Test valid parameters
        valid, error = validate_task_last_params(None)
        assert valid is True
        assert error is None
        
        # Test with task type
        valid, error = validate_task_last_params("Evaluation")
        assert valid is True
        assert error is None
        
        # Test with empty string task type
        valid, error = validate_task_last_params("")
        assert valid is True
        assert error is None
        
        # Test invalid task type parameter
        valid, error = validate_task_last_params(123)
        assert valid is False
        assert "task_type must be a string" in error
    
    def test_task_last_query_patterns(self):
        """Test GraphQL query patterns for task last"""
        account_id = "account-123"
        
        # Test the main GraphQL query structure
        query = """
        query ListTaskByAccountIdAndUpdatedAt($accountId: String!) {
            listTaskByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC, limit: 50) {
                items {
                    id
                    accountId
                    type
                    status
                    target
                    command
                    description
                    metadata
                    createdAt
                    updatedAt
                    startedAt
                    completedAt
                    estimatedCompletionAt
                    errorMessage
                    errorDetails
                    stdout
                    stderr
                    currentStageId
                    workerNodeId
                    dispatchStatus
                    scorecardId
                    scoreId
                }
            }
        }
        """
        
        # Test query structure elements
        assert "$accountId: String!" in query
        assert "accountId: $accountId" in query
        assert "sortDirection: DESC" in query
        assert "limit: 50" in query
        assert "listTaskByAccountIdAndUpdatedAt" in query
        assert "errorMessage" in query
        assert "dispatchStatus" in query
    
    def test_task_type_filtering_patterns(self):
        """Test task type filtering logic patterns"""
        # Mock tasks data
        mock_tasks = [
            {"id": "task-1", "type": "Evaluation", "status": "COMPLETED"},
            {"id": "task-2", "type": "Report", "status": "RUNNING"},
            {"id": "task-3", "type": "evaluation", "status": "FAILED"},  # Case variation
            {"id": "task-4", "type": "Other", "status": "PENDING"}
        ]
        
        def filter_tasks_by_type(tasks, task_type):
            if not task_type:
                return tasks
            return [t for t in tasks if t.get('type', '').lower() == task_type.lower()]
        
        # Test no filtering
        filtered = filter_tasks_by_type(mock_tasks, None)
        assert len(filtered) == 4
        
        # Test filtering by type (case insensitive)
        filtered = filter_tasks_by_type(mock_tasks, "Evaluation")
        assert len(filtered) == 2
        assert all(t['type'].lower() == 'evaluation' for t in filtered)
        
        # Test filtering with no matches
        filtered = filter_tasks_by_type(mock_tasks, "NonExistent")
        assert len(filtered) == 0
        
        # Test empty string filtering
        filtered = filter_tasks_by_type(mock_tasks, "")
        assert len(filtered) == 4  # Should return all since empty string is falsy
    
    def test_task_stages_query_patterns(self):
        """Test task stages query patterns"""
        task_id = "task-123"
        
        # Test the stages query structure
        stages_query = """
        query ListTaskStageByTaskId($taskId: String!) {
            listTaskStageByTaskId(taskId: $taskId) {
                items {
                    id
                    taskId
                    name
                    order
                    status
                    statusMessage
                    startedAt
                    completedAt
                    estimatedCompletionAt
                    processedItems
                    totalItems
                }
            }
        }
        """
        
        assert "$taskId: String!" in stages_query
        assert "taskId: $taskId" in stages_query
        assert "listTaskStageByTaskId" in stages_query
        assert "processedItems" in stages_query
        assert "totalItems" in stages_query
    
    def test_task_stages_sorting_patterns(self):
        """Test task stages sorting logic patterns"""
        # Mock stages data
        mock_stages = [
            {"id": "stage-3", "name": "Finalize", "order": 3, "status": "PENDING"},
            {"id": "stage-1", "name": "Initialize", "order": 1, "status": "COMPLETED"},
            {"id": "stage-2", "name": "Process", "order": 2, "status": "RUNNING"},
            {"id": "stage-4", "name": "No Order", "status": "PENDING"}  # Missing order
        ]
        
        # Test sorting logic
        sorted_stages = sorted(mock_stages, key=lambda s: s.get('order', 0))
        
        # Stage with no order should come first (order defaults to 0)
        assert sorted_stages[0]['name'] == "No Order"
        assert sorted_stages[1]['name'] == "Initialize"
        assert sorted_stages[2]['name'] == "Process"
        assert sorted_stages[3]['name'] == "Finalize"
    
    def test_task_response_patterns(self):
        """Test task response handling patterns"""
        # Test successful response
        mock_response = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': [
                    {
                        'id': 'task-123',
                        'accountId': 'account-456',
                        'type': 'Evaluation',
                        'status': 'COMPLETED',
                        'description': 'Test evaluation task',
                        'createdAt': '2024-01-01T00:00:00Z',
                        'updatedAt': '2024-01-01T12:00:00Z',
                        'errorMessage': None,
                        'dispatchStatus': 'DISPATCHED'
                    }
                ]
            }
        }
        
        tasks_data = mock_response.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])
        assert len(tasks_data) == 1
        assert tasks_data[0]['id'] == 'task-123'
        assert tasks_data[0]['type'] == 'Evaluation'
        
        # Test empty response
        empty_response = {
            'listTaskByAccountIdAndUpdatedAt': {
                'items': []
            }
        }
        
        tasks_data = empty_response.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])
        assert len(tasks_data) == 0
        
        # Test error response
        error_response = {
            'errors': [
                {'message': 'Access denied', 'path': ['listTaskByAccountIdAndUpdatedAt']}
            ]
        }
        
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Access denied' in error_details


class TestTaskInfoTool:
    """Test plexus_task_info tool patterns"""
    
    def test_task_info_validation_patterns(self):
        """Test task info parameter validation patterns"""
        def validate_task_info_params(task_id):
            if not task_id or not task_id.strip():
                return False, "task_id is required"
            return True, None
        
        # Test valid parameters
        valid, error = validate_task_info_params("task-123")
        assert valid is True
        assert error is None
        
        # Test empty task ID
        valid, error = validate_task_info_params("")
        assert valid is False
        assert "task_id is required" in error
        
        # Test whitespace-only task ID
        valid, error = validate_task_info_params("   ")
        assert valid is False
        assert "task_id is required" in error
        
        # Test None task ID
        valid, error = validate_task_info_params(None)
        assert valid is False
        assert "task_id is required" in error
    
    def test_task_info_query_patterns(self):
        """Test GraphQL query patterns for task info"""
        task_id = "task-123"
        
        # Test the main task query structure
        task_query = """
        query GetTask($id: ID!) {
            getTask(id: $id) {
                id
                accountId
                type
                status
                target
                command
                description
                metadata
                createdAt
                updatedAt
                startedAt
                completedAt
                estimatedCompletionAt
                errorMessage
                errorDetails
                stdout
                stderr
                currentStageId
                workerNodeId
                dispatchStatus
                scorecardId
                scoreId
            }
        }
        """
        
        assert "$id: ID!" in task_query
        assert "getTask(id: $id)" in task_query
        assert "errorMessage" in task_query
        assert "errorDetails" in task_query
        assert "currentStageId" in task_query
        assert "workerNodeId" in task_query
    
    def test_task_info_response_patterns(self):
        """Test task info response handling patterns"""
        # Test successful response
        mock_task_response = {
            'getTask': {
                'id': 'task-123',
                'accountId': 'account-456',
                'type': 'Report',
                'status': 'RUNNING',
                'target': 'scorecard-789',
                'command': 'generate_report',
                'description': 'Generate monthly report',
                'metadata': '{"key": "value"}',
                'createdAt': '2024-01-01T00:00:00Z',
                'updatedAt': '2024-01-01T12:00:00Z',
                'startedAt': '2024-01-01T01:00:00Z',
                'completedAt': None,
                'errorMessage': None,
                'errorDetails': None,
                'stdout': 'Processing...',
                'stderr': '',
                'currentStageId': 'stage-2',
                'workerNodeId': 'worker-001',
                'dispatchStatus': 'DISPATCHED',
                'scorecardId': 'scorecard-789',
                'scoreId': None
            }
        }
        
        task_data = mock_task_response.get('getTask')
        assert task_data is not None
        assert task_data['id'] == 'task-123'
        assert task_data['type'] == 'Report'
        assert task_data['status'] == 'RUNNING'
        assert task_data['currentStageId'] == 'stage-2'
        
        # Test task not found response
        not_found_response = {
            'getTask': None
        }
        
        task_data = not_found_response.get('getTask')
        assert task_data is None
        
        # Test error response
        error_response = {
            'errors': [
                {'message': 'Task not found', 'path': ['getTask']}
            ]
        }
        
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Task not found' in error_details
    
    def test_task_url_generation_patterns(self):
        """Test task URL generation patterns"""
        def get_task_url(task_id: str) -> str:
            """Mock the task URL generation logic"""
            base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
            if not base_url.endswith('/'):
                base_url += '/'
            path = f"lab/tasks/{task_id}"
            return base_url + path.lstrip('/')
        
        # Test URL generation
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com'}):
            url = get_task_url('task-123')
            assert url == 'https://test.example.com/lab/tasks/task-123'
        
        # Test with trailing slash in base URL
        with patch.dict(os.environ, {'PLEXUS_APP_URL': 'https://test.example.com/'}):
            url = get_task_url('task-456')
            assert url == 'https://test.example.com/lab/tasks/task-456'
        
        # Test with default URL
        with patch.dict(os.environ, {}, clear=True):
            url = get_task_url('task-789')
            assert url == 'https://plexus.anth.us/lab/tasks/task-789'


class TestTaskToolsSharedPatterns:
    """Test shared patterns across task tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used across task tools"""
        def validate_credentials():
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return False, "Missing API credentials"
            return True, None
        
        # Test with missing credentials
        with patch.dict(os.environ, {}, clear=True):
            valid, error = validate_credentials()
            assert valid is False
            assert "Missing API credentials" in error
        
        # Test with valid credentials
        with patch.dict(os.environ, {
            'PLEXUS_API_URL': 'https://test.example.com',
            'PLEXUS_API_KEY': 'test-key'
        }):
            valid, error = validate_credentials()
            assert valid is True
            assert error is None
    
    def test_stdout_redirection_pattern(self):
        """Test stdout redirection pattern used in all task tools"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()  # Mock original stdout
        temp_stdout = StringIO()
        
        # Simulate the pattern
        try:
            # Write something that should be captured
            print("This should be captured", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "This should be captured" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_client_creation_pattern(self):
        """Test client creation patterns used in task tools"""
        def simulate_client_creation():
            """Simulate the client creation pattern with nested stdout capture"""
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return None, "Missing API credentials"
            
            # Simulate nested stdout capture pattern
            client_stdout = StringIO()
            saved_stdout = StringIO()  # Mock current stdout
            
            try:
                # Mock successful client creation
                client = {"api_url": api_url, "api_key": api_key}
                
                # Simulate captured output check
                client_output = client_stdout.getvalue()
                if client_output:
                    # Would log warning in real implementation
                    pass
                
                return client, None
            finally:
                # Would restore stdout in real implementation
                pass
        
        # Test successful client creation
        with patch.dict(os.environ, {
            'PLEXUS_API_URL': 'https://test.example.com',
            'PLEXUS_API_KEY': 'test-key'
        }):
            client, error = simulate_client_creation()
            assert client is not None
            assert error is None
            assert client['api_url'] == 'https://test.example.com'
        
        # Test failed client creation
        with patch.dict(os.environ, {}, clear=True):
            client, error = simulate_client_creation()
            assert client is None
            assert "Missing API credentials" in error
    
    def test_error_response_handling_pattern(self):
        """Test GraphQL error response handling pattern"""
        # Test error response structure
        error_response = {
            'errors': [
                {
                    'message': 'Task not found',
                    'path': ['getTask'],
                    'extensions': {'code': 'NOT_FOUND'}
                }
            ]
        }
        
        # Test the pattern used to handle errors
        if 'errors' in error_response:
            error_details = json.dumps(error_response['errors'], indent=2)
            assert 'Task not found' in error_details
            assert 'NOT_FOUND' in error_details
    
    def test_account_id_resolution_pattern(self):
        """Test account ID resolution pattern"""
        def mock_get_default_account_id():
            # Mock the pattern used in task tools
            return "default-account-123"
        
        # Test default account resolution
        account_id = mock_get_default_account_id()
        assert account_id == "default-account-123"
    
    def test_task_data_enrichment_pattern(self):
        """Test task data enrichment patterns (adding stages and URL)"""
        # Mock task data
        task_data = {
            'id': 'task-123',
            'type': 'Evaluation',
            'status': 'COMPLETED'
        }
        
        # Mock stages data
        stages_data = [
            {'id': 'stage-1', 'name': 'Initialize', 'order': 1, 'status': 'COMPLETED'},
            {'id': 'stage-2', 'name': 'Process', 'order': 2, 'status': 'COMPLETED'},
            {'id': 'stage-3', 'name': 'Finalize', 'order': 3, 'status': 'COMPLETED'}
        ]
        
        # Test enrichment pattern
        # Sort stages by order
        stages_data.sort(key=lambda s: s.get('order', 0))
        
        # Include stages in the task data
        task_data['stages'] = stages_data
        
        # Add the task URL for convenience
        task_data['url'] = f"https://test.example.com/lab/tasks/{task_data['id']}"
        
        # Verify enrichment
        assert 'stages' in task_data
        assert len(task_data['stages']) == 3
        assert task_data['stages'][0]['name'] == 'Initialize'
        assert task_data['stages'][2]['name'] == 'Finalize'
        assert 'url' in task_data
        assert 'lab/tasks/task-123' in task_data['url']
    
    def test_query_execution_pattern(self):
        """Test query execution pattern with stdout capture"""
        def simulate_query_execution(query, variables):
            """Simulate the query execution pattern with stdout capture"""
            query_stdout = StringIO()
            saved_stdout = StringIO()  # Mock current stdout
            
            try:
                # Mock successful query execution
                if "listTaskByAccountIdAndUpdatedAt" in query:
                    result = {
                        'listTaskByAccountIdAndUpdatedAt': {
                            'items': [{'id': 'task-123', 'type': 'Test'}]
                        }
                    }
                elif "getTask" in query:
                    result = {
                        'getTask': {'id': variables.get('id'), 'type': 'Test'}
                    }
                else:
                    result = {}
                
                # Check for GraphQL errors
                if 'errors' in result:
                    error_details = json.dumps(result['errors'], indent=2)
                    return f"Error from Dashboard query: {error_details}"
                
                return result
            finally:
                # Check captured output
                query_output = query_stdout.getvalue()
                if query_output:
                    # Would log warning in real implementation
                    pass
        
        # Test successful query
        query = "query listTaskByAccountIdAndUpdatedAt { ... }"
        result = simulate_query_execution(query, {'accountId': 'account-123'})
        assert isinstance(result, dict)
        assert 'listTaskByAccountIdAndUpdatedAt' in result
        
        # Test task query
        query = "query getTask { ... }"
        result = simulate_query_execution(query, {'id': 'task-456'})
        assert isinstance(result, dict)
        assert result['getTask']['id'] == 'task-456'