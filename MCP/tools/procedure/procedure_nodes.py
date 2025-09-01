"""
MCP tools for procedure node management.

This module provides tools for AI agents to create and manage procedure nodes
during procedure runs, allowing them to generate and test different hypotheses.
"""

import logging
from typing import Dict, Any, Optional
import yaml
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.procedure import Procedure
from plexus.dashboard.api.models.graph_node import GraphNode
from plexus.cli.scorecard.scorecards import resolve_account_identifier

logger = logging.getLogger(__name__)

def register_procedure_node_tools(server, procedure_context: Optional[Dict[str, Any]] = None):
    """Register procedure node management tools."""
    
    @server.tool()
    async def create_procedure_node(
        procedure_id: str,
        hypothesis_description: str,
        node_name: Optional[str] = None,
        yaml_configuration: Optional[str] = None,
        parent_node_id: Optional[str] = None,
        initial_value: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new procedure node with a specific hypothesis configuration.
        
        This tool allows the AI agent to create new procedure nodes to test different
        hypotheses or variations of the score configuration.
        
        IMPORTANT: You must provide both a distinctive node_name and a structured hypothesis_description.
        
        Args:
            procedure_id: ID of the procedure to add the node to
            hypothesis_description: Structured description with TWO parts:
                1) GOAL: What you're trying to improve (e.g., "Reduce false positives for medical queries")
                2) METHOD: Specific implementation approach (e.g., "Add medical domain keywords to classification prompt")
                Format as "GOAL: [description]\nMETHOD: [specific implementation]"
            node_name: Optional short, distinctive name for this hypothesis. If not provided, will be 
                auto-generated from the first few words of the hypothesis description.
                Examples: "Medical Query Filtering", "Threshold Adjustment v2", "Context-Aware Prompting"
            yaml_configuration: Optional modified score YAML configuration. If not provided, the node will be 
                created without an initial configuration - this can be added later in a separate step.
            parent_node_id: Optional parent node ID (if None, creates child of root node)
            initial_value: Optional initial computed value (defaults to hypothesis info)
            
        Returns:
            JSON string with creation result and new node details
        """
        try:
            logger.info(f"Creating procedure node for procedure {procedure_id}")
            
            # Validate YAML configuration if provided
            parsed_yaml = None
            if yaml_configuration:
                try:
                    parsed_yaml = yaml.safe_load(yaml_configuration)
                    logger.debug(f"YAML configuration validated successfully")
                except yaml.YAMLError as e:
                    return f"Error: Invalid YAML configuration: {str(e)}"
            else:
                logger.debug(f"No YAML configuration provided - node will be created without initial config")
            
            # Get Plexus client from procedure context if available
            if procedure_context and 'client' in procedure_context:
                client = procedure_context['client']
            else:
                # Fallback to creating new client (may fail if no credentials)
                client = PlexusDashboardClient()
            
            # Get the procedure
            procedure = Procedure.get_by_id(procedure_id, client)
            if not procedure:
                return f"Error: Procedure {procedure_id} not found"
            
            # Get the parent node (root node if none specified)
            if parent_node_id:
                parent_node = GraphNode.get_by_id(parent_node_id, client)
                if not parent_node:
                    return f"Error: Parent node {parent_node_id} not found"
            else:
                # Use root node as parent - AI agents CANNOT create root nodes
                if not procedure.rootNodeId:
                    return "Error: Procedure has no root node. Root nodes must be created programmatically."
                parent_node_id = procedure.rootNodeId
            
            # CRITICAL: AI agents are FORBIDDEN from creating root-level nodes (parentNodeId=None)
            # All AI-created nodes MUST have a parent to maintain proper tree structure
            if parent_node_id is None:
                return "Error: AI agents cannot create root-level nodes. All nodes must have a parent."
            
            # Auto-generate node_name if not provided or validate if provided
            if not node_name or not node_name.strip():
                # Auto-generate name from first few words of hypothesis
                words = hypothesis_description.split()[:4]
                node_name = " ".join(words)
                if len(hypothesis_description.split()) > 4:
                    node_name += "..."
                # Fallback if name is too long
                if len(node_name) > 50:
                    node_name = "Hypothesis Node"
                logger.info(f"Auto-generated node name: '{node_name}'")
            else:
                node_name = node_name.strip()
                if len(node_name) > 80:
                    # Truncate instead of failing
                    node_name = node_name[:77] + "..."
                    logger.warning(f"Truncated long node name to: '{node_name}'")
            
            # Set up initial value with hypothesis info
            if initial_value is None:
                initial_value = {
                    "hypothesis": hypothesis_description,
                    "created_by": "ai_agent",
                    "initialized": True
                }
            else:
                initial_value["hypothesis"] = hypothesis_description
                initial_value["created_by"] = "ai_agent"
            
            # FINAL SAFETY CHECK: Ensure we're not accidentally creating a root node
            if parent_node_id is None:
                return "Error: Final safety check failed - cannot create node without parent"
            
            # Verify parent node actually exists and is accessible
            try:
                parent_node_check = GraphNode.get_by_id(parent_node_id, client)
                if not parent_node_check:
                    return f"Error: Parent node {parent_node_id} not accessible"
            except Exception as e:
                return f"Error: Cannot verify parent node {parent_node_id}: {str(e)}"

            # Create the new node with code field (required by GraphQL schema)
            # In simplified schema, code is stored directly on the node, not in separate versions
            node_code = yaml_configuration or "# No configuration provided - concept-only node"
            
            new_node = GraphNode.create(
                client=client,
                procedureId=procedure_id,
                parentNodeId=parent_node_id,
                name=node_name,
                status='ACTIVE',
                code=node_code,  # Required field in GraphQL schema
                hypothesis=hypothesis_description,  # Store hypothesis directly on node
                value=initial_value  # Store additional metadata in value field
            )
            
            # Note: hypothesis is now stored directly on the GraphNode, and initial_value in the value field
            # This ensures the UI can display the hypothesis information properly
            logger.info(f"Successfully created node {new_node.id} with hypothesis: {hypothesis_description[:100]}...")
            
            # NOTE: Chat recording is handled by the main procedure session
            # Do not create separate chat sessions for individual nodes as this fragments
            # the conversation. All tool calls and responses should be recorded in the 
            # single root-level chat session managed by the ProcedureAIRunner.
            logger.info(f"Node {new_node.id} created - chat recording handled by main session")
            
            logger.info(f"Successfully created procedure node {new_node.id}")
            
            result = {
                "success": True,
                "node_id": new_node.id,
                "node_name": node_name,
                "procedure_id": procedure_id,
                "parent_node_id": parent_node_id,
                "hypothesis": hypothesis_description,
                "status": "Node created successfully and ready for testing",
                "yaml_preview": (yaml_configuration[:200] + "..." if len(yaml_configuration) > 200 else yaml_configuration) if yaml_configuration else "No YAML configuration provided"
            }
            
            return f"Successfully created procedure node: {result}"
            
        except Exception as e:
            error_msg = f"Error creating procedure node: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def get_procedure_tree(procedure_id: str) -> str:
        """
        Get the complete procedure tree structure showing all nodes and their relationships.
        
        This tool helps the AI agent understand the current procedure structure before
        creating new nodes.
        
        Args:
            procedure_id: ID of the procedure to analyze
            
        Returns:
            JSON string with complete procedure tree structure
        """
        try:
            logger.info(f"Getting procedure tree for {procedure_id}")
            
            # Get Plexus client
            client = PlexusDashboardClient()
            
            # Get the procedure
            procedure = Procedure.get_by_id(procedure_id, client)
            if not procedure:
                return f"Error: Procedure {procedure_id} not found"
            
            # Get all nodes
            all_nodes = GraphNode.list_by_procedure(procedure_id, client)
            
            # Build tree structure
            nodes_info = []
            for node in all_nodes:
                # In simplified schema, data is stored directly on node (no separate versions)
                node_info = {
                    "node_id": node.id,
                    "name": node.name,
                    "status": node.status,
                    "parent_node_id": node.parentNodeId,
                    "content": {
                        "code": node.code[:100] + "..." if node.code and len(node.code) > 100 else (node.code if node.code else "No configuration"),
                        "created_at": node.createdAt,
                        "updated_at": node.updatedAt
                    }
                }
                nodes_info.append(node_info)
            
            # Get root node
            root_node = procedure.get_root_node()
            
            result = {
                "procedure_id": procedure_id,
                "total_nodes": len(all_nodes),
                "root_node_id": root_node.id if root_node else None,
                "nodes": nodes_info
            }
            
            return f"Procedure tree structure: {result}"
            
        except Exception as e:
            error_msg = f"Error getting procedure tree: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def update_node_content(
        node_id: str,
        yaml_configuration: str,
        update_description: str,
        computed_value: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Update the content of an existing procedure node with new configuration.
        
        This allows the AI agent to iteratively improve hypotheses by updating node content
        directly (simplified schema stores data directly on nodes).
        
        Args:
            node_id: ID of the node to update
            yaml_configuration: Updated YAML configuration
            update_description: Description of what changed in this update
            computed_value: Optional computed results (defaults to update info)
            
        Returns:
            JSON string with update result
        """
        try:
            logger.info(f"Updating node {node_id} with new content")
            
            # Validate YAML configuration
            try:
                parsed_yaml = yaml.safe_load(yaml_configuration)
                logger.debug(f"YAML configuration validated successfully")
            except yaml.YAMLError as e:
                return f"Error: Invalid YAML configuration: {str(e)}"
            
            # Get Plexus client from procedure context if available
            if procedure_context and 'client' in procedure_context:
                client = procedure_context['client']
            else:
                # Fallback to creating new client (may fail if no credentials)
                client = PlexusDashboardClient()
            
            # Get the node
            node = GraphNode.get_by_id(node_id, client)
            if not node:
                return f"Error: Node {node_id} not found"
            
            # Set up computed value for tracking
            if computed_value is None:
                computed_value = {
                    "update_description": update_description,
                    "updated_by": "ai_agent"
                }
            else:
                computed_value["update_description"] = update_description
                computed_value["updated_by"] = "ai_agent"
            
            # Update node content directly (simplified schema)
            updated_node = node.update_content(
                code=yaml_configuration,
                status='QUEUED',
                hypothesis=update_description,
                value=computed_value
            )
            
            logger.info(f"Successfully updated content for node {node_id}")
            
            result = {
                "success": True,
                "node_id": node_id,
                "update_description": update_description,
                "status": "Node content updated successfully and ready for testing",
                "yaml_preview": yaml_configuration[:200] + "..." if len(yaml_configuration) > 200 else yaml_configuration
            }
            
            return f"Successfully updated node content: {result}"
            
        except Exception as e:
            error_msg = f"Error updating node content: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def delete_procedure_node(node_id: str) -> str:
        """
        Delete a procedure node and all its versions.
        
        WARNING: This permanently deletes the node and all its data.
        This action cannot be undone.
        
        Args:
            node_id: ID of the procedure node to delete
            
        Returns:
            Success/error message
        """
        try:
            logger.info(f"Deleting procedure node {node_id}")
            
            # Get Plexus client
            client = PlexusDashboardClient()
            
            # Get the node first to verify it exists
            node = GraphNode.get_by_id(node_id, client)
            if not node:
                return f"Error: Procedure node {node_id} not found"
            
            # In simplified schema, just delete the node directly (no separate versions)
            success = node.delete()
            
            if success:
                logger.info(f"Successfully deleted procedure node {node_id}")
                return f"Successfully deleted procedure node {node_id}"
            else:
                return f"Failed to delete procedure node {node_id}"
                
        except Exception as e:
            error_msg = f"Error deleting procedure node {node_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    logger.info("Registered procedure node management tools")