"""
GraphNode Primitive - Graph-based knowledge representation.

Provides:
- GraphNode.create(content, metadata) - Create a new node
- GraphNode.root() - Get root node (if exists)
- GraphNode.current() - Get current working node
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GraphNodePrimitive:
    """
    Manages graph node operations for procedure execution.

    Graph nodes provide tree-based data storage for procedures,
    useful for tree search, hypothesis tracking, etc.
    """

    def __init__(self, client, procedure_id: str, account_id: str):
        """
        Initialize GraphNode primitive.

        Args:
            client: PlexusDashboardClient instance
            procedure_id: Procedure ID for node creation
            account_id: Account ID for node creation
        """
        self.client = client
        self.procedure_id = procedure_id
        self.account_id = account_id
        self._current_node = None
        logger.debug(f"GraphNodePrimitive initialized for procedure {procedure_id}")

    def create(self, content: str, metadata: Optional[Dict[str, Any]] = None, parent_node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new graph node.

        Args:
            content: Text content for the node
            metadata: Optional metadata dict
            parent_node_id: Optional parent node ID (None for root)

        Returns:
            Dict with node info: {id, content, metadata}

        Example (Lua):
            local node = GraphNode.create("My limerick here", {type = "poem"})
            Log.info("Created node: " .. node.id)
        """
        try:
            from plexus.dashboard.api.models.graph_node import GraphNode
            import json

            logger.info(f"Creating graph node (parent: {parent_node_id or 'None'})")

            # Convert Lua table to Python dict if needed
            if metadata and hasattr(metadata, 'items'):
                # It's a Lua table, convert to dict
                node_metadata = dict(metadata.items())
            elif metadata:
                node_metadata = dict(metadata)
            else:
                node_metadata = {}

            if content:
                node_metadata['content'] = content

            # Convert metadata to JSON string for GraphQL
            metadata_json = json.dumps(node_metadata)

            # Create the node with metadata
            node = GraphNode.create(
                client=self.client,
                accountId=self.account_id,
                procedureId=self.procedure_id,
                parentNodeId=parent_node_id,
                status='ACTIVE'
            )

            # Update with metadata
            if metadata_json:
                node.update_content(status='ACTIVE', metadata=node_metadata)

            logger.info(f"Created graph node {node.id}")

            # Set as current node
            self._current_node = node

            return {
                'id': node.id,
                'content': content,
                'metadata': node_metadata,
                'parent_id': parent_node_id
            }

        except Exception as e:
            logger.error(f"Error creating graph node: {e}", exc_info=True)
            return {
                'error': str(e)
            }

    def root(self) -> Optional[Dict[str, Any]]:
        """
        Get the root node for this procedure (if exists).

        Returns:
            Dict with node info or None if no root node exists

        Example (Lua):
            local root = GraphNode.root()
            if root then
                Log.info("Root node exists: " .. root.id)
            end
        """
        try:
            from plexus.dashboard.api.models.procedure import Procedure

            procedure = Procedure.get_by_id(self.procedure_id, self.client)
            root_node = procedure.get_root_node()

            if not root_node:
                logger.debug("No root node exists")
                return None

            return {
                'id': root_node.id,
                'status': getattr(root_node, 'status', 'UNKNOWN'),
                'metadata': getattr(root_node, 'metadata', {})
            }

        except Exception as e:
            logger.error(f"Error getting root node: {e}")
            return None

    def current(self) -> Optional[Dict[str, Any]]:
        """
        Get the current working node.

        Returns:
            Dict with node info or None if no current node set

        Example (Lua):
            local node = GraphNode.current()
            if node then
                Log.info("Current node: " .. node.id)
            end
        """
        if not self._current_node:
            logger.debug("No current node set")
            return None

        return {
            'id': self._current_node.id,
            'status': getattr(self._current_node, 'status', 'UNKNOWN'),
            'metadata': getattr(self._current_node, 'metadata', {})
        }

    def set_current(self, node_id: str) -> bool:
        """
        Set the current working node (for internal use).

        Args:
            node_id: Node ID to set as current

        Returns:
            True if successful
        """
        try:
            from plexus.dashboard.api.models.graph_node import GraphNode

            node = GraphNode.get_by_id(node_id, self.client)
            self._current_node = node
            logger.info(f"Set current node to {node_id}")
            return True

        except Exception as e:
            logger.error(f"Error setting current node: {e}")
            return False

    def __repr__(self) -> str:
        return f"GraphNodePrimitive(procedure={self.procedure_id})"
