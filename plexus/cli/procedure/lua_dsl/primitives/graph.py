"""
GraphNode Primitive - Graph-based knowledge representation.

Provides:
- GraphNode.create(content, metadata) - Create a new node
- GraphNode.root() - Get root node (if exists)
- GraphNode.current() - Get current working node
- GraphNode.get(node_id) - Get node by ID

Node methods (on returned node objects):
- node:children() - Get child nodes
- node:parent() - Get parent node
- node:score() - Get node score
- node:metadata() - Get node metadata
- node:set_metadata(key, value) - Set metadata field
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class NodeWrapper:
    """
    Wrapper for GraphNode database objects that provides Lua-callable methods.

    This class wraps the GraphNode database model and exposes its methods
    in a way that's accessible from Lua.
    """

    def __init__(self, node, client):
        """
        Initialize node wrapper.

        Args:
            node: GraphNode database model instance
            client: PlexusDashboardClient for queries
        """
        self.node = node
        self.client = client
        self.id = node.id
        self.status = getattr(node, 'status', 'UNKNOWN')

    def children(self):
        """
        Get child nodes.

        Returns:
            List of child node wrappers

        Example (Lua):
            local children = node:children()
            for i, child in ipairs(children) do
                Log.info("Child: " .. child.id)
            end
        """
        try:
            from plexus.dashboard.api.models.graph_node import GraphNode

            children_nodes = GraphNode.get_children(self.node.id, self.client)
            return [NodeWrapper(child, self.client) for child in children_nodes]
        except Exception as e:
            logger.error(f"Error getting children for node {self.id}: {e}")
            return []

    def parent(self):
        """
        Get parent node.

        Returns:
            Parent node wrapper or None

        Example (Lua):
            local parent = node:parent()
            if parent then
                Log.info("Parent: " .. parent.id)
            end
        """
        try:
            from plexus.dashboard.api.models.graph_node import GraphNode

            if not self.node.parentNodeId:
                return None

            parent_node = GraphNode.get_by_id(self.node.parentNodeId, self.client)
            return NodeWrapper(parent_node, self.client)
        except Exception as e:
            logger.error(f"Error getting parent for node {self.id}: {e}")
            return None

    def score(self):
        """
        Get node score.

        Returns:
            Node score value or None

        Example (Lua):
            local score = node:score()
            if score then
                Log.info("Score: " .. score)
            end
        """
        return getattr(self.node, 'score', None)

    def metadata(self):
        """
        Get node metadata.

        Returns:
            Metadata dict

        Example (Lua):
            local meta = node:metadata()
            Log.info("Type: " .. (meta.type or "unknown"))
        """
        return getattr(self.node, 'metadata', {}) or {}

    def set_metadata(self, key: str, value: Any):
        """
        Set a metadata field.

        Args:
            key: Metadata key
            value: Value to set

        Returns:
            True if successful

        Example (Lua):
            node:set_metadata("status", "completed")
            node:set_metadata("score", 0.95)
        """
        try:
            metadata = getattr(self.node, 'metadata', {}) or {}
            metadata[key] = value

            self.node.update_content(
                status=self.node.status,
                metadata=metadata
            )
            logger.info(f"Updated metadata for node {self.id}: {key} = {value}")
            return True
        except Exception as e:
            logger.error(f"Error setting metadata for node {self.id}: {e}")
            return False

    def __repr__(self):
        return f"NodeWrapper(id={self.id}, status={self.status})"


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

    def create(self, content: str, metadata: Optional[Dict[str, Any]] = None, parent_node_id: Optional[str] = None):
        """
        Create a new graph node.

        Args:
            content: Text content for the node
            metadata: Optional metadata dict
            parent_node_id: Optional parent node ID (None for root)

        Returns:
            NodeWrapper with methods: children(), parent(), score(), metadata(), set_metadata()

        Example (Lua):
            local node = GraphNode.create("My limerick here", {type = "poem"})
            Log.info("Created node: " .. node.id)

            -- Node methods available:
            local children = node:children()
            local parent = node:parent()
            node:set_metadata("status", "reviewed")
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

            # Return NodeWrapper with all node methods
            return NodeWrapper(node, self.client)

        except Exception as e:
            logger.error(f"Error creating graph node: {e}", exc_info=True)
            return None

    def root(self):
        """
        Get the root node for this procedure (if exists).

        Returns:
            NodeWrapper or None if no root node exists

        Example (Lua):
            local root = GraphNode.root()
            if root then
                Log.info("Root node exists: " .. root.id)
                local children = root:children()  -- Node methods available
            end
        """
        try:
            from plexus.dashboard.api.models.procedure import Procedure

            procedure = Procedure.get_by_id(self.procedure_id, self.client)
            root_node = procedure.get_root_node()

            if not root_node:
                logger.debug("No root node exists")
                return None

            return NodeWrapper(root_node, self.client)

        except Exception as e:
            logger.error(f"Error getting root node: {e}")
            return None

    def current(self):
        """
        Get the current working node.

        Returns:
            NodeWrapper or None if no current node set

        Example (Lua):
            local node = GraphNode.current()
            if node then
                Log.info("Current node: " .. node.id)
                node:set_metadata("visited", true)  -- Node methods available
            end
        """
        if not self._current_node:
            logger.debug("No current node set")
            return None

        return NodeWrapper(self._current_node, self.client)

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
