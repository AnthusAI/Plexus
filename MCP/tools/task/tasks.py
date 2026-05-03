#!/usr/bin/env python3
"""
Task management tools for Plexus MCP Server
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Union, Optional
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_task_tools(mcp: FastMCP):
    """Register task tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_task_last(
        task_type: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Gets the most recent task for an account, with optional filtering by task type.
        
        Parameters:
        - task_type: Optional filter by task type (e.g., 'Evaluation', 'Report', etc.)
        
        Returns:
        - Detailed information about the most recent task, including its stages
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Create the client
            try:
                client_stdout = StringIO()
                saved_stdout = sys.stdout
                sys.stdout = client_stdout
                
                try:
                    client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                finally:
                    client_output = client_stdout.getvalue()
                    if client_output:
                        logger.warning(f"Captured unexpected stdout during client creation in get_latest_plexus_task: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Get default account ID
            default_account_id = _get_default_account_id()
            if not default_account_id:
                return "Error: No default account ID available."

            # Query for the most recent task using the GSI
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
            
            # Execute query
            query_stdout = StringIO()
            saved_stdout = sys.stdout
            sys.stdout = query_stdout
            
            try:
                result = client.execute(query, {'accountId': default_account_id})
                
                # Check for GraphQL errors
                if 'errors' in result:
                    error_details = json.dumps(result['errors'], indent=2)
                    logger.error(f"Dashboard query returned errors: {error_details}")
                    return f"Error from Dashboard query: {error_details}"

                tasks_data = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

                if not tasks_data:
                    return "No tasks found for this account."

                # Filter by task type if specified
                if task_type:
                    tasks_data = [t for t in tasks_data if t.get('type', '').lower() == task_type.lower()]
                    if not tasks_data:
                        return f"No tasks found of type '{task_type}' for this account."

                # Get the most recent task
                latest_task_data = tasks_data[0]
                
                # Get task stages
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
                
                stages_result = client.execute(stages_query, {'taskId': latest_task_data['id']})
                stages_data = stages_result.get('listTaskStageByTaskId', {}).get('items', [])
                
                # Sort stages by order
                stages_data.sort(key=lambda s: s.get('order', 0))
                
                # Include stages in the task data
                latest_task_data['stages'] = stages_data
                
                # Add the task URL for convenience
                latest_task_data['url'] = _get_task_url(latest_task_data["id"])
                
                return latest_task_data
                
            finally:
                query_output = query_stdout.getvalue()
                if query_output:
                    logger.warning(f"Captured unexpected stdout during task query execution: {query_output}")
                sys.stdout = saved_stdout
                
        except Exception as e:
            logger.error(f"Error retrieving latest task: {str(e)}", exc_info=True)
            return f"Error retrieving latest task: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_latest_plexus_task: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_task_info(task_id: str) -> Union[str, Dict[str, Any]]:
        """
        Gets detailed information about a specific task by its ID, including task stages.
        
        Parameters:
        - task_id: The unique ID of the task
        
        Returns:
        - Detailed information about the task, including its stages
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Create the client
            try:
                client_stdout = StringIO()
                saved_stdout = sys.stdout
                sys.stdout = client_stdout
                
                try:
                    client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                finally:
                    client_output = client_stdout.getvalue()
                    if client_output:
                        logger.warning(f"Captured unexpected stdout during client creation in get_plexus_task_details: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Query for the specific task
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
            
            # Execute task query
            query_stdout = StringIO()
            saved_stdout = sys.stdout
            sys.stdout = query_stdout
            
            try:
                task_result = client.execute(task_query, {'id': task_id})
                
                # Check for GraphQL errors
                if 'errors' in task_result:
                    error_details = json.dumps(task_result['errors'], indent=2)
                    logger.error(f"Dashboard query returned errors: {error_details}")
                    return f"Error from Dashboard query: {error_details}"

                task_data = task_result.get('getTask')
                if not task_data:
                    return f"Task not found with ID: {task_id}"

                # Get task stages
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
                
                stages_result = client.execute(stages_query, {'taskId': task_id})
                stages_data = stages_result.get('listTaskStageByTaskId', {}).get('items', [])
                
                # Sort stages by order
                stages_data.sort(key=lambda s: s.get('order', 0))
                
                # Include stages in the task data
                task_data['stages'] = stages_data
                
                # Add the task URL for convenience
                task_data['url'] = _get_task_url(task_id)
                
                return task_data
                
            finally:
                query_output = query_stdout.getvalue()
                if query_output:
                    logger.warning(f"Captured unexpected stdout during task query execution: {query_output}")
                sys.stdout = saved_stdout
                
        except Exception as e:
            logger.error(f"Error retrieving task details: {str(e)}", exc_info=True)
            return f"Error retrieving task details: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_plexus_task_details: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout


def _get_task_url(task_id: str) -> str:
    """
    Generates a URL for viewing a task in the dashboard.
    
    Parameters:
    - task_id: The ID of the task
    
    Returns:
    - Full URL to the task in the dashboard
    """
    from urllib.parse import urljoin
    
    base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
    # Ensure base URL ends with a slash for urljoin to work correctly
    if not base_url.endswith('/'):
        base_url += '/'
    # Strip leading slash from path if present to avoid double slashes
    path = f"lab/tasks/{task_id}".lstrip('/')
    return urljoin(base_url, path)


def _get_default_account_id():
    """Get the default account ID, resolving it if necessary."""
    try:
        # Import the global function from the main server
        import sys
        import importlib.util
        
        # Import the main server module to access the global function
        spec = importlib.util.spec_from_file_location("plexus_fastmcp_server", 
                                                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                                               "plexus_fastmcp_server.py"))
        if spec and spec.loader:
            server_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(server_module)
            return server_module.get_default_account_id()
        return None
    except Exception as e:
        logger.warning(f"Error getting default account ID: {str(e)}")
        return None