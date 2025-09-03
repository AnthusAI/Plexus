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
    async def upsert_procedure_node(
        procedure_id: str,
        node_id: Optional[str] = None,
        node_name: Optional[str] = None,
        parent_node_id: Optional[str] = None,
        status: Optional[str] = None,
        **metadata_fields
    ) -> str:
        """
        Create or update a procedure node with arbitrary metadata.
        
        This is a general-purpose tool that can create new nodes or update existing ones
        by storing any key-value pairs in the node's metadata field.
        
        Args:
            procedure_id: ID of the procedure to add the node to
            node_id: Optional ID of existing node to update (if None, creates new node)
            node_name: Optional name for the node
            parent_node_id: Optional parent node ID (if None and creating, uses root node)
            status: Optional status for the node (e.g., 'ACTIVE', 'QUEUED')
            **metadata_fields: Any additional key-value pairs to store in node metadata
                Common fields might include:
                - hypothesis: Description of what this node is testing
                - description: General description
                - config: YAML or other configuration data
                - created_by: Who/what created this node
            
        Returns:
            JSON string with operation result and node details
        """
        try:
            # Get Plexus client from procedure context if available
            if procedure_context and 'client' in procedure_context:
                client = procedure_context['client']
            else:
                # Fallback to creating new client (may fail if no credentials)
                client = PlexusDashboardClient()
            
            # Update existing node
            if node_id:
                logger.info(f"Updating existing node {node_id}")
                
                # Get the existing node
                node = GraphNode.get_by_id(node_id, client)
                if not node:
                    return f"Error: Node {node_id} not found"
                
                # Preserve existing metadata and add new fields
                current_metadata = node.metadata or {}
                updated_metadata = {**current_metadata, **metadata_fields}
                
                # Update the node
                updated_node = node.update_content(
                    status=status,
                    metadata=updated_metadata
                )
                
                logger.info(f"Successfully updated node {node_id}")
                
                result = {
                    "success": True,
                    "operation": "update",
                    "node_id": node_id,
                    "node_name": node.name,
                    "procedure_id": procedure_id,
                    "status": "Node updated successfully",
                    "metadata": updated_metadata
                }
                
            # Create new node
            else:
                logger.info(f"Creating new node for procedure {procedure_id}")
                
                # Get the procedure
                procedure = Procedure.get_by_id(procedure_id, client)
                if not procedure:
                    return f"Error: Procedure {procedure_id} not found"
                
                # Determine parent node
                if not parent_node_id:
                    # Use root node as parent - AI agents CANNOT create root nodes
                    if not procedure.rootNodeId:
                        return "Error: Procedure has no root node. Root nodes must be created programmatically."
                    parent_node_id = procedure.rootNodeId
                
                # Verify parent node exists
                try:
                    parent_node_check = GraphNode.get_by_id(parent_node_id, client)
                    if not parent_node_check:
                        return f"Error: Parent node {parent_node_id} not accessible"
                except Exception as e:
                    return f"Error: Cannot verify parent node {parent_node_id}: {str(e)}"
                
                # Auto-generate node name if not provided
                if not node_name or not node_name.strip():
                    if 'hypothesis' in metadata_fields:
                        # Auto-generate name from hypothesis
                        words = str(metadata_fields['hypothesis']).split()[:4]
                        node_name = " ".join(words)
                        if len(str(metadata_fields['hypothesis']).split()) > 4:
                            node_name += "..."
                    else:
                        node_name = "Procedure Node"
                    
                    if len(node_name) > 50:
                        node_name = "Procedure Node"
                    logger.info(f"Auto-generated node name: '{node_name}'")
                else:
                    node_name = node_name.strip()
                    if len(node_name) > 80:
                        node_name = node_name[:77] + "..."
                        logger.warning(f"Truncated long node name to: '{node_name}'")
                
                # Create the new node
                new_node = GraphNode.create(
                    client=client,
                    procedureId=procedure_id,
                    parentNodeId=parent_node_id,
                    name=node_name,
                    status=status or 'ACTIVE',
                    metadata=metadata_fields
                )
                
                logger.info(f"Successfully created node {new_node.id}")
                
                result = {
                    "success": True,
                    "operation": "create",
                    "node_id": new_node.id,
                    "node_name": node_name,
                    "procedure_id": procedure_id,
                    "parent_node_id": parent_node_id,
                    "status": "Node created successfully",
                    "metadata": metadata_fields
                }
            
            return f"Successfully completed upsert operation: {result}"
            
        except Exception as e:
            error_msg = f"Error in upsert operation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def get_procedure_info(procedure_id: str, node_id: Optional[str] = None) -> str:
        """
        Get information about a procedure and optionally a specific node.
        
        This tool provides both high-level procedure structure and detailed node information.
        
        Args:
            procedure_id: ID of the procedure to analyze
            node_id: Optional ID of specific node to get details for
            
        Returns:
            JSON string with procedure and/or node information
        """
        try:
            # Get Plexus client from procedure context if available
            if procedure_context and 'client' in procedure_context:
                client = procedure_context['client']
            else:
                client = PlexusDashboardClient()
            
            # Get the procedure
            procedure = Procedure.get_by_id(procedure_id, client)
            if not procedure:
                return f"Error: Procedure {procedure_id} not found"
            
            result = {
                "procedure_id": procedure_id,
                "procedure_name": getattr(procedure, 'name', None),
                "root_node_id": procedure.rootNodeId
            }
            
            # Get specific node info if requested
            if node_id:
                logger.info(f"Getting info for node {node_id}")
                
                node = GraphNode.get_by_id(node_id, client)
                if not node:
                    return f"Error: Node {node_id} not found"
                
                result["node"] = {
                    "node_id": node.id,
                    "name": node.name,
                    "status": node.status,
                    "parent_node_id": node.parentNodeId,
                    "metadata": node.metadata or {},
                    "created_at": node.createdAt,
                    "updated_at": node.updatedAt
                }
            else:
                # Get summary of all nodes
                logger.info(f"Getting all nodes for procedure {procedure_id}")
                
                all_nodes = GraphNode.list_by_procedure(procedure_id, client)
                
                nodes_summary = []
                for node in all_nodes:
                    metadata = node.metadata or {}
                    
                    node_summary = {
                        "node_id": node.id,
                        "name": node.name,
                        "status": node.status,
                        "parent_node_id": node.parentNodeId,
                        "metadata_keys": list(metadata.keys()),
                        "created_at": node.createdAt
                    }
                    
                    # Include hypothesis preview if available
                    if 'hypothesis' in metadata:
                        hypothesis = str(metadata['hypothesis'])
                        node_summary["hypothesis_preview"] = hypothesis[:100] + "..." if len(hypothesis) > 100 else hypothesis
                    
                    nodes_summary.append(node_summary)
                
                result["total_nodes"] = len(all_nodes)
                result["nodes"] = nodes_summary
            
            return f"Procedure information: {result}"
            
        except Exception as e:
            error_msg = f"Error getting procedure info: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    logger.info("Registered procedure node tools: upsert_procedure_node, get_procedure_info")