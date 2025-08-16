"""
MCP tools for experiment node management.

This module provides tools for AI agents to create and manage experiment nodes
during experiment runs, allowing them to generate and test different hypotheses.
"""

import logging
from typing import Dict, Any, Optional
import yaml
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.experiment import Experiment
from plexus.dashboard.api.models.experiment_node import ExperimentNode
from plexus.cli.scorecard.scorecards import resolve_account_identifier

logger = logging.getLogger(__name__)

def register_experiment_node_tools(server, experiment_context: Optional[Dict[str, Any]] = None):
    """Register experiment node management tools."""
    
    @server.tool()
    async def create_experiment_node(
        experiment_id: str,
        yaml_configuration: str,
        hypothesis_description: str,
        node_name: Optional[str] = None,
        parent_node_id: Optional[str] = None,
        initial_value: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new experiment node with a specific hypothesis configuration.
        
        This tool allows the AI agent to create new experiment nodes to test different
        hypotheses or variations of the score configuration.
        
        IMPORTANT: You must provide both a distinctive node_name and a structured hypothesis_description.
        
        Args:
            experiment_id: ID of the experiment to add the node to
            yaml_configuration: Modified score YAML configuration (e.g., LangGraphScore with updated prompts, thresholds, etc.)
            hypothesis_description: Structured description with TWO parts:
                1) GOAL: What you're trying to improve (e.g., "Reduce false positives for medical queries")
                2) METHOD: Specific implementation approach (e.g., "Add medical domain keywords to classification prompt")
                Format as "GOAL: [description]\nMETHOD: [specific implementation]"
            node_name: Optional short, distinctive name for this hypothesis. If not provided, will be 
                auto-generated from the first few words of the hypothesis description.
                Examples: "Medical Query Filtering", "Threshold Adjustment v2", "Context-Aware Prompting"
            parent_node_id: Optional parent node ID (if None, creates child of root node)
            initial_value: Optional initial computed value (defaults to hypothesis info)
            
        Returns:
            JSON string with creation result and new node details
        """
        try:
            logger.info(f"Creating experiment node for experiment {experiment_id}")
            
            # Validate YAML configuration
            try:
                parsed_yaml = yaml.safe_load(yaml_configuration)
                logger.debug(f"YAML configuration validated successfully")
            except yaml.YAMLError as e:
                return f"Error: Invalid YAML configuration: {str(e)}"
            
            # Get Plexus client from experiment context if available
            if experiment_context and 'client' in experiment_context:
                client = experiment_context['client']
            else:
                # Fallback to creating new client (may fail if no credentials)
                client = PlexusDashboardClient()
            
            # Get the experiment
            experiment = Experiment.get_by_id(experiment_id, client)
            if not experiment:
                return f"Error: Experiment {experiment_id} not found"
            
            # Get the parent node (root node if none specified)
            if parent_node_id:
                parent_node = ExperimentNode.get_by_id(parent_node_id, client)
                if not parent_node:
                    return f"Error: Parent node {parent_node_id} not found"
            else:
                # Use root node as parent - AI agents CANNOT create root nodes
                if not experiment.rootNodeId:
                    return "Error: Experiment has no root node. Root nodes must be created programmatically."
                parent_node_id = experiment.rootNodeId
            
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
                parent_node_check = ExperimentNode.get_by_id(parent_node_id, client)
                if not parent_node_check:
                    return f"Error: Parent node {parent_node_id} not accessible"
            except Exception as e:
                return f"Error: Cannot verify parent node {parent_node_id}: {str(e)}"

            # Create the new node (guaranteed to have a parent)
            new_node = ExperimentNode.create(
                client=client,
                experimentId=experiment_id,
                parentNodeId=parent_node_id,
                name=node_name,
                status='ACTIVE'
            )
            
            # Create initial version for the new node
            # Note: yaml_configuration should be a modified score configuration, not experiment configuration
            new_node.create_version(
                code=yaml_configuration,  # This should be score YAML (LangGraphScore, etc.)
                value=initial_value,
                status='ACTIVE',
                hypothesis=hypothesis_description
            )
            
            # Create a chat session for this node to record future AI interactions
            try:
                from plexus.cli.experiment.chat_recorder import ExperimentChatRecorder
                chat_recorder = ExperimentChatRecorder(client, experiment_id, new_node.id)
                session_id = await chat_recorder.start_session({
                    'node_id': new_node.id,
                    'node_name': node_name,
                    'hypothesis': hypothesis_description,
                    'created_by': 'ai_agent'
                })
                if session_id:
                    logger.info(f"Created chat session {session_id} for node {new_node.id}")
                    await chat_recorder.record_system_message(f"Node created: {node_name}\n\nHypothesis: {hypothesis_description}")
                    await chat_recorder.end_session('COMPLETED')
                else:
                    logger.warning(f"Failed to create chat session for node {new_node.id}")
            except Exception as e:
                logger.warning(f"Could not create chat session for node {new_node.id}: {e}")
            
            logger.info(f"Successfully created experiment node {new_node.id}")
            
            result = {
                "success": True,
                "node_id": new_node.id,
                "node_name": node_name,
                "experiment_id": experiment_id,
                "parent_node_id": parent_node_id,
                "hypothesis": hypothesis_description,
                "status": "Node created successfully and ready for testing",
                "yaml_preview": yaml_configuration[:200] + "..." if len(yaml_configuration) > 200 else yaml_configuration
            }
            
            return f"Successfully created experiment node: {result}"
            
        except Exception as e:
            error_msg = f"Error creating experiment node: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def get_experiment_tree(experiment_id: str) -> str:
        """
        Get the complete experiment tree structure showing all nodes and their relationships.
        
        This tool helps the AI agent understand the current experiment structure before
        creating new nodes.
        
        Args:
            experiment_id: ID of the experiment to analyze
            
        Returns:
            JSON string with complete experiment tree structure
        """
        try:
            logger.info(f"Getting experiment tree for {experiment_id}")
            
            # Get Plexus client
            client = PlexusDashboardClient()
            
            # Get the experiment
            experiment = Experiment.get_by_id(experiment_id, client)
            if not experiment:
                return f"Error: Experiment {experiment_id} not found"
            
            # Get all nodes
            all_nodes = ExperimentNode.list_by_experiment(experiment_id, client)
            
            # Build tree structure
            nodes_info = []
            for node in all_nodes:
                # Get latest version for each node
                latest_version = node.get_latest_version()
                
                node_info = {
                    "node_id": node.id,
                    "status": node.status,
                    "parent_node_id": node.parentNodeId,
                    "latest_version": {
                        "status": latest_version.status if latest_version else None,
                        "hypothesis": latest_version.value.get("hypothesis", "No hypothesis") if latest_version and latest_version.value else None,
                        "yaml_preview": latest_version.code[:100] + "..." if latest_version and len(latest_version.code) > 100 else (latest_version.code if latest_version else None)
                    } if latest_version else None
                }
                nodes_info.append(node_info)
            
            # Get root node
            root_node = experiment.get_root_node()
            
            result = {
                "experiment_id": experiment_id,
                "total_nodes": len(all_nodes),
                "root_node_id": root_node.id if root_node else None,
                "nodes": nodes_info
            }
            
            return f"Experiment tree structure: {result}"
            
        except Exception as e:
            error_msg = f"Error getting experiment tree: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def update_node_version(
        node_id: str,
        yaml_configuration: str,
        update_description: str,
        computed_value: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new version for an existing experiment node with updated configuration.
        
        This allows the AI agent to iteratively improve hypotheses by creating new versions
        of existing nodes.
        
        Args:
            node_id: ID of the node to update
            yaml_configuration: Updated YAML configuration
            update_description: Description of what changed in this update
            computed_value: Optional computed results (defaults to update info)
            
        Returns:
            JSON string with update result
        """
        try:
            logger.info(f"Updating node {node_id} with new version")
            
            # Validate YAML configuration
            try:
                parsed_yaml = yaml.safe_load(yaml_configuration)
                logger.debug(f"YAML configuration validated successfully")
            except yaml.YAMLError as e:
                return f"Error: Invalid YAML configuration: {str(e)}"
            
            # Get Plexus client
            client = PlexusDashboardClient()
            
            # Get the node
            node = ExperimentNode.get_by_id(node_id, client)
            if not node:
                return f"Error: Node {node_id} not found"
            
            # Set up computed value
            if computed_value is None:
                computed_value = {
                    "update_description": update_description,
                    "updated_by": "ai_agent"
                }
            else:
                computed_value["update_description"] = update_description
                computed_value["updated_by"] = "ai_agent"
            
            # Create new version
            new_version = node.create_version(
                code=yaml_configuration,
                value=computed_value,
                status='QUEUED',
                insight=update_description
            )
            
            logger.info(f"Successfully created version {new_version.id} for node {node_id}")
            
            result = {
                "success": True,
                "node_id": node_id,
                "version_id": new_version.id,
                "update_description": update_description,
                "status": "Version created successfully and ready for testing"
            }
            
            return f"Successfully updated node version: {result}"
            
        except Exception as e:
            error_msg = f"Error updating node version: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    @server.tool()
    async def delete_experiment_node(node_id: str) -> str:
        """
        Delete an experiment node and all its versions.
        
        WARNING: This permanently deletes the node and all its data.
        This action cannot be undone.
        
        Args:
            node_id: ID of the experiment node to delete
            
        Returns:
            Success/error message
        """
        try:
            logger.info(f"Deleting experiment node {node_id}")
            
            # Get Plexus client
            client = PlexusDashboardClient()
            
            # Get the node first to verify it exists
            node = ExperimentNode.get_by_id(node_id, client)
            if not node:
                return f"Error: Experiment node {node_id} not found"
            
            # Delete all versions first
            versions = node.get_versions()
            for version in versions:
                version.delete()
                logger.info(f"Deleted version {version.id} for node {node_id}")
            
            # Delete the node itself
            success = node.delete()
            
            if success:
                logger.info(f"Successfully deleted experiment node {node_id}")
                return f"Successfully deleted experiment node {node_id} and {len(versions)} versions"
            else:
                return f"Failed to delete experiment node {node_id}"
                
        except Exception as e:
            error_msg = f"Error deleting experiment node {node_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    logger.info("Registered experiment node management tools")