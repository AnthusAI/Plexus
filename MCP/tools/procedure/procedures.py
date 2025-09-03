"""
Procedure MCP Tools - Model Context Protocol tools for procedure management.

Provides MCP tools that reuse the same ProcedureService as the CLI commands,
ensuring consistent behavior and DRY principles.

Available tools:
- plexus_procedure_create: Create a new procedure
- plexus_procedure_list: List procedures
- plexus_procedure_info: Get detailed procedure information
- plexus_procedure_update: Update procedure configuration
- plexus_procedure_delete: Delete a procedure
- plexus_procedure_run: Run an procedure
- plexus_procedure_yaml: Get procedure YAML configuration
- stop_conversation: Stop the current conversation with a reason
"""

import logging
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

def register_procedure_tools(mcp):
    """Register procedure management tools with the MCP server."""
    
    # Import here to avoid circular imports
    try:
        import sys
        import os
        
        # Add the project root to Python path
        mcp_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(mcp_dir)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from plexus.cli.shared.client_utils import create_client
        from plexus.cli.procedure.service import ProcedureService, DEFAULT_PROCEDURE_YAML
        
        def get_procedure_service():
            """Get an ProcedureService instance."""
            client = create_client()
            if not client:
                raise ValueError("Could not create API client")
            return ProcedureService(client)
            
    except ImportError as e:
        logger.error(f"Failed to import procedure dependencies: {e}")
        return
    
    # Tool models
    class CreateProcedureRequest(BaseModel):
        account_identifier: Annotated[str, Field(description="Account identifier (key, name, or ID)")]
        scorecard_identifier: Annotated[str, Field(description="Scorecard identifier (key, name, or ID)")]
        score_identifier: Annotated[str, Field(description="Score identifier (key, name, or ID)")]
        yaml_config: Annotated[Optional[str], Field(description="YAML configuration (uses default if not provided)")] = None
        featured: Annotated[bool, Field(description="Whether to mark as featured")] = False
        create_root_node: Annotated[bool, Field(description="Whether to create a root node (default: True)")] = True
    
    class ListProceduresRequest(BaseModel):
        account_identifier: Annotated[str, Field(description="Account identifier (key, name, or ID)")]
        scorecard_identifier: Annotated[Optional[str], Field(description="Optional scorecard identifier to filter by")] = None
        limit: Annotated[int, Field(description="Maximum number of procedures to return")] = 20
    
    class ProcedureInfoRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
        include_yaml: Annotated[bool, Field(description="Whether to include YAML configuration")] = False
    
    class UpdateProcedureRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
        yaml_config: Annotated[str, Field(description="New YAML configuration")]
        note: Annotated[Optional[str], Field(description="Optional note for this version")] = None
    
    class DeleteProcedureRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
    
    class ProcedureYamlRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
    
    class ProcedureRunRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
        max_iterations: Annotated[Optional[int], Field(description="Maximum number of iterations")] = None
        timeout: Annotated[Optional[int], Field(description="Timeout in seconds")] = None
        async_mode: Annotated[bool, Field(description="Whether to run asynchronously")] = False
        dry_run: Annotated[bool, Field(description="Whether to perform a dry run")] = False
    
    class ProcedureChatSessionsRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
        limit: Annotated[int, Field(description="Maximum number of sessions to return")] = 10
    
    class ProcedureChatMessagesRequest(BaseModel):
        procedure_id: Annotated[str, Field(description="Procedure ID")]
        session_id: Annotated[Optional[str], Field(description="Specific session ID (optional - if not provided, shows all sessions)")] = None
        limit: Annotated[int, Field(description="Maximum number of messages to return per session")] = 50
        show_tool_calls: Annotated[bool, Field(description="Whether to include tool call details")] = True
        show_tool_responses: Annotated[bool, Field(description="Whether to include tool response details")] = True
    
    @mcp.tool()
    def plexus_procedure_create(request: CreateProcedureRequest) -> Dict[str, Any]:
        """Create a new procedure.
        
        Creates an procedure associated with a specific scorecard and score.
        If no YAML configuration is provided, uses a default BeamSearch template.
        Returns the created procedure details including IDs for further operations.
        """
        try:
            service = get_procedure_service()
            
            result = service.create_procedure(
                account_identifier=request.account_identifier,
                scorecard_identifier=request.scorecard_identifier,
                score_identifier=request.score_identifier,
                yaml_config=request.yaml_config,
                featured=request.featured,
                create_root_node=request.create_root_node
            )
            
            if not result.success:
                return {
                    "success": False,
                    "error": result.message
                }
            
            return {
                "success": True,
                "message": result.message,
                "procedure": {
                    "id": result.procedure.id,
                    "featured": result.procedure.featured,
                    "created_at": result.procedure.createdAt.isoformat(),
                    "scorecard_id": result.procedure.scorecardId,
                    "score_id": result.procedure.scoreId,
                    "root_node_id": result.root_node.id,
                    "initial_version_id": result.initial_version.id
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating procedure: {e}")
            return {
                "success": False,
                "error": f"Failed to create procedure: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_list(request: ListProceduresRequest) -> Dict[str, Any]:
        """List procedures for an account.
        
        Returns procedures ordered by most recent first. Can be filtered by scorecard.
        Useful for finding existing procedures or monitoring procedure activity.
        """
        try:
            service = get_procedure_service()
            
            procedures = service.list_procedures(
                account_identifier=request.account_identifier,
                scorecard_identifier=request.scorecard_identifier,
                limit=request.limit
            )
            
            return {
                "success": True,
                "count": len(procedures),
                "procedures": [
                    {
                        "id": exp.id,
                        "featured": exp.featured,
                        "created_at": exp.createdAt.isoformat(),
                        "updated_at": exp.updatedAt.isoformat(),
                        "scorecard_id": exp.scorecardId,
                        "score_id": exp.scoreId,
                        "root_node_id": exp.rootNodeId
                    }
                    for exp in procedures
                ]
            }
            
        except Exception as e:
            logger.error(f"Error listing procedures: {e}")
            return {
                "success": False,
                "error": f"Failed to list procedures: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_info(request: ProcedureInfoRequest) -> Dict[str, Any]:
        """Get detailed information about an procedure.
        
        Returns comprehensive procedure details including node and version counts,
        associated scorecard/score information, and optionally the YAML configuration.
        """
        try:
            service = get_procedure_service()
            
            info = service.get_procedure_info(request.procedure_id)
            if not info:
                return {
                    "success": False,
                    "error": f"Procedure {request.procedure_id} not found"
                }
            
            result = {
                "success": True,
                "procedure": {
                    "id": info.procedure.id,
                    "featured": info.procedure.featured,
                    "created_at": info.procedure.createdAt.isoformat(),
                    "updated_at": info.procedure.updatedAt.isoformat(),
                    "account_id": info.procedure.accountId,
                    "scorecard_id": info.procedure.scorecardId,
                    "score_id": info.procedure.scoreId,
                    "root_node_id": info.procedure.rootNodeId
                },
                "summary": {
                    "node_count": info.node_count,
                    "version_count": info.version_count,
                    "scorecard_name": info.scorecard_name,
                    "score_name": info.score_name
                }
            }
            
            if request.include_yaml:
                yaml_config = service.get_procedure_yaml(request.procedure_id)
                if yaml_config:
                    result["yaml_config"] = yaml_config
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting procedure info: {e}")
            return {
                "success": False,
                "error": f"Failed to get procedure info: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_update(request: UpdateProcedureRequest) -> Dict[str, Any]:
        """Update a procedure's configuration.
        
        Creates a new version with the provided YAML configuration.
        The procedure will maintain its history of configurations through versions.
        """
        try:
            service = get_procedure_service()
            
            success, message = service.update_procedure_config(
                request.procedure_id,
                request.yaml_config,
                request.note
            )
            
            return {
                "success": success,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error updating procedure: {e}")
            return {
                "success": False,
                "error": f"Failed to update procedure: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_delete(request: DeleteProcedureRequest) -> Dict[str, Any]:
        """Delete a procedure and all its data.
        
        WARNING: This permanently deletes the procedure, all its nodes, and all versions.
        This action cannot be undone. Use with caution.
        """
        try:
            service = get_procedure_service()
            
            success, message = service.delete_procedure(request.procedure_id)
            
            return {
                "success": success,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error deleting procedure: {e}")
            return {
                "success": False,
                "error": f"Failed to delete procedure: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_yaml(request: ProcedureYamlRequest) -> Dict[str, Any]:
        """Get the latest YAML configuration for an procedure.
        
        Returns the current YAML configuration from the procedure's latest version.
        Useful for reviewing configurations or as a starting point for updates.
        """
        try:
            service = get_procedure_service()
            
            yaml_config = service.get_procedure_yaml(request.procedure_id)
            if not yaml_config:
                return {
                    "success": False,
                    "error": f"Could not get YAML configuration for procedure {request.procedure_id}"
                }
            
            return {
                "success": True,
                "yaml_config": yaml_config
            }
            
        except Exception as e:
            logger.error(f"Error getting procedure YAML: {e}")
            return {
                "success": False,
                "error": f"Failed to get procedure YAML: {str(e)}"
            }
    
    @mcp.tool()
    async def plexus_procedure_run(request: ProcedureRunRequest) -> Dict[str, Any]:
        """Run an procedure with the given ID.
        
        Executes the procedure using its configured YAML settings. The procedure
        will process its nodes according to the defined workflow and return results.
        
        This function provides the same functionality as the CLI 'plexus procedure run'
        command, ensuring consistent behavior between CLI and MCP interfaces.
        """
        try:
            service = get_procedure_service()
            
            # Build options dictionary from request
            options = {}
            if request.max_iterations is not None:
                options['max_iterations'] = request.max_iterations
            if request.timeout is not None:
                options['timeout'] = request.timeout
            # Include boolean flags regardless of their value for consistency with CLI
            options['async_mode'] = request.async_mode
            options['dry_run'] = request.dry_run
            
            # Run the procedure using the same service method as CLI (now async)
            result = await service.run_procedure(request.procedure_id, **options)
            
            # Return the same structured result as the service method
            return result
            
        except Exception as e:
            logger.error(f"Error running procedure: {e}")
            return {
                "procedure_id": request.procedure_id,
                "status": "error",
                "error": f"Failed to run procedure: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_template() -> Dict[str, Any]:
        """Get the default procedure YAML template.
        
        Returns the default BeamSearch configuration template that can be customized
        for creating new procedures. Useful as a starting point for procedure design.
        """
        try:
            return {
                "success": True,
                "template": DEFAULT_PROCEDURE_YAML,
                "description": "Default BeamSearch procedure template with value calculation and exploration prompts"
            }
            
        except Exception as e:
            logger.error(f"Error getting procedure template: {e}")
            return {
                "success": False,
                "error": f"Failed to get procedure template: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_chat_sessions(request: ProcedureChatSessionsRequest) -> Dict[str, Any]:
        """Get chat sessions for an procedure.
        
        Returns all chat sessions associated with the procedure's nodes, including
        session status, creation time, and message counts. Useful for understanding
        conversation activity within an procedure.
        """
        try:
            # Import GraphQL client locally to avoid circular imports
            from plexus.dashboard.api.client import PlexusDashboardClient
            
            client = PlexusDashboardClient()
            
            # Query for chat sessions associated with this procedure
            query = '''
            query ListChatSessions($procedureId: String!, $limit: Int!) {
                listChatSessions(filter: {procedureId: {eq: $procedureId}}, limit: $limit) {
                    items {
                        id
                        status
                        procedureId
                        nodeId
                        createdAt
                        updatedAt
                        messages {
                            items {
                                id
                                messageType
                            }
                        }
                    }
                }
            }
            '''
            
            result = client.execute(query, {
                'procedureId': request.procedure_id,
                'limit': request.limit
            })
            
            if 'errors' in result:
                return {
                    "success": False,
                    "error": f"GraphQL errors: {result['errors']}"
                }
                
            # Handle both wrapped and unwrapped GraphQL responses
            sessions = []
            if 'data' in result:
                sessions = result['data'].get('listChatSessions', {}).get('items', [])
            elif 'listChatSessions' in result:
                sessions = result['listChatSessions'].get('items', [])
            
            # Process sessions to include message counts and types
            processed_sessions = []
            for session in sessions:
                messages = session.get('messages', {}).get('items', [])
                message_types = {}
                for msg in messages:
                    msg_type = msg.get('messageType', 'MESSAGE')
                    message_types[msg_type] = message_types.get(msg_type, 0) + 1
                
                processed_sessions.append({
                    "id": session["id"],
                    "status": session["status"],
                    "node_id": session.get("nodeId"),
                    "created_at": session["createdAt"],
                    "updated_at": session.get("updatedAt"),
                    "message_count": len(messages),
                    "message_types": message_types
                })
            
            return {
                "success": True,
                "procedure_id": request.procedure_id,
                "session_count": len(processed_sessions),
                "sessions": processed_sessions
            }
            
        except Exception as e:
            logger.error(f"Error getting procedure chat sessions: {e}")
            return {
                "success": False,
                "error": f"Failed to get chat sessions: {str(e)}"
            }
    
    @mcp.tool()
    def plexus_procedure_chat_messages(request: ProcedureChatMessagesRequest) -> Dict[str, Any]:
        """Get chat messages for an procedure.
        
        Returns detailed chat conversation including system messages, user messages,
        assistant responses, tool calls, and tool responses. Useful for debugging
        conversation flow and understanding AI reasoning process.
        """
        try:
            # Import GraphQL client locally to avoid circular imports
            from plexus.dashboard.api.client import PlexusDashboardClient
            import json
            
            client = PlexusDashboardClient()
            
            if request.session_id:
                # Query for a specific session
                query = '''
                query GetChatSession($id: ID!) {
                    getChatSession(id: $id) {
                        id
                        status
                        procedureId
                        nodeId
                        createdAt
                        messages {
                            items {
                                id
                                role
                                messageType
                                toolName
                                content
                                sequenceNumber
                                parentMessageId
                                createdAt
                            }
                        }
                    }
                }
                '''
                
                result = client.execute(query, {'id': request.session_id})
                
                if 'errors' in result:
                    return {
                        "success": False,
                        "error": f"GraphQL errors: {result['errors']}"
                    }
                
                # Handle both wrapped and unwrapped GraphQL responses
                session = None
                if 'data' in result:
                    session = result['data'].get('getChatSession')
                elif 'getChatSession' in result:
                    session = result['getChatSession']
                if not session:
                    return {
                        "success": False,
                        "error": f"Session {request.session_id} not found"
                    }
                
                sessions = [session]
            else:
                # Query for all sessions in the procedure
                query = '''
                query ListChatSessions($procedureId: String!, $limit: Int!) {
                    listChatSessions(filter: {procedureId: {eq: $procedureId}}, limit: $limit) {
                        items {
                            id
                            status
                            procedureId
                            nodeId
                            createdAt
                            messages {
                                items {
                                    id
                                    role
                                    messageType
                                    toolName
                                    content
                                    sequenceNumber
                                    parentMessageId
                                    createdAt
                                }
                            }
                        }
                    }
                }
                '''
                
                result = client.execute(query, {
                    'procedureId': request.procedure_id,
                    'limit': request.limit
                })
                
                if 'errors' in result:
                    return {
                        "success": False,
                        "error": f"GraphQL errors: {result['errors']}"
                    }
                
                # Handle both wrapped and unwrapped GraphQL responses
                sessions = []
                if 'data' in result:
                    sessions = result['data'].get('listChatSessions', {}).get('items', [])
                elif 'listChatSessions' in result:
                    sessions = result['listChatSessions'].get('items', [])
            
            # Process sessions and messages
            processed_sessions = []
            total_messages = 0
            tool_calls = 0
            tool_responses = 0
            missing_responses = 0
            
            for session in sessions:
                messages = session.get('messages', {}).get('items', [])
                # Sort messages by sequence number
                messages.sort(key=lambda m: m.get('sequenceNumber', 0))
                
                # Track messages within this session
                session_tool_calls = []
                session_tool_responses = []
                processed_messages = []
                
                for msg in messages[:request.limit]:
                    msg_type = msg.get('messageType', 'MESSAGE')
                    role = msg.get('role', '')
                    
                    # Parse content if it's JSON
                    content = msg.get('content', '')
                    parsed_content = content
                    try:
                        if content.startswith('{') and content.endswith('}'):
                            parsed_content = json.loads(content)
                    except:
                        pass  # Keep as string if not valid JSON
                    
                    processed_msg = {
                        "id": msg["id"],
                        "sequence_number": msg.get("sequenceNumber", 0),
                        "role": role,
                        "message_type": msg_type,
                        "content": parsed_content,
                        "created_at": msg["createdAt"],
                        "parent_message_id": msg.get("parentMessageId")
                    }
                    
                    # Add tool-specific fields if requested
                    if msg_type == 'TOOL_CALL' and request.show_tool_calls:
                        processed_msg["tool_name"] = msg.get("toolName")
                        session_tool_calls.append(msg["id"])
                        tool_calls += 1
                        
                    elif msg_type == 'TOOL_RESPONSE' and request.show_tool_responses:
                        processed_msg["tool_name"] = msg.get("toolName", "Unknown")
                        session_tool_responses.append(msg["id"])
                        tool_responses += 1
                    
                    processed_messages.append(processed_msg)
                    total_messages += 1
                
                # Check for missing tool responses
                session_missing = 0
                for call_id in session_tool_calls:
                    # Find if there's a response with this call as parent
                    has_response = any(
                        resp_msg.get('parentMessageId') == call_id 
                        for resp_msg in messages 
                        if resp_msg.get('messageType') == 'TOOL_RESPONSE'
                    )
                    if not has_response:
                        session_missing += 1
                
                missing_responses += session_missing
                
                processed_sessions.append({
                    "session_id": session["id"],
                    "status": session["status"],
                    "node_id": session.get("nodeId"),
                    "created_at": session["createdAt"],
                    "message_count": len(processed_messages),
                    "tool_calls": len(session_tool_calls),
                    "tool_responses": len(session_tool_responses),
                    "missing_responses": session_missing,
                    "messages": processed_messages
                })
            
            return {
                "success": True,
                "procedure_id": request.procedure_id,
                "session_count": len(processed_sessions),
                "total_messages": total_messages,
                "summary": {
                    "tool_calls": tool_calls,
                    "tool_responses": tool_responses,
                    "missing_responses": missing_responses,
                    "response_rate": f"{((tool_responses / tool_calls) * 100):.1f}%" if tool_calls > 0 else "N/A"
                },
                "sessions": processed_sessions
            }
            
        except Exception as e:
            logger.error(f"Error getting procedure chat messages: {e}")
            return {
                "success": False,
                "error": f"Failed to get chat messages: {str(e)}"
            }
    
    # Register the stop tool
    from .stop import register_stop_tool
    register_stop_tool(mcp)
    
    logger.info("Registered procedure management tools")