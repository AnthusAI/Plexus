"""
GraphNode Model - Python representation of the GraphQL GraphNode type.

Represents a node in the procedure tree structure. Each node belongs to a procedure
and can have a parent node (None for root nodes) and child nodes. Nodes track
their status information and store metadata as JSON.

The simplified schema stores all data directly on the GraphNode using a metadata field
instead of separate code, hypothesis, insight, and value fields.
"""

import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class GraphNode(BaseModel):
    accountId: str
    procedureId: str
    parentNodeId: Optional[str]
    name: Optional[str]
    status: Optional[str]
    metadata: Optional[Dict[str, Any]]
    createdAt: str
    updatedAt: str

    def __init__(
        self,
        id: str,
        accountId: str,
        procedureId: str,
        createdAt: str,
        updatedAt: str,
        parentNodeId: Optional[str] = None,
        name: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.accountId = accountId
        self.procedureId = procedureId
        self.parentNodeId = parentNodeId
        self.name = name
        self.status = status
        self.metadata = metadata
        self.createdAt = createdAt
        self.updatedAt = updatedAt

    @classmethod
    def fields(cls) -> str:
        return """
            id
            accountId
            procedureId
            parentNodeId
            name
            status
            metadata
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'GraphNode':
        # Handle metadata field - parse JSON string back to dict if possible
        metadata = data.get('metadata')
        if metadata and isinstance(metadata, str):
            try:
                import json
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, keep it as string
                pass
        
        return cls(
            id=data['id'],
            accountId=data['accountId'],
            procedureId=data['procedureId'],
            parentNodeId=data.get('parentNodeId'),
            name=data.get('name'),
            status=data.get('status'),
            metadata=metadata,
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            client=client
        )

    @classmethod
    def create(
        cls,
        client: '_BaseAPIClient',
        accountId: str,
        procedureId: str,
        parentNodeId: Optional[str] = None,
        name: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'GraphNode':
        """Create a new graph node.
        
        Args:
            client: The API client
            accountId: ID of the account this node belongs to
            procedureId: ID of the procedure this node belongs to
            parentNodeId: ID of the parent node (None for root nodes)
            name: Name of the node (optional)
            status: Node status (optional)
            metadata: Metadata as JSON (optional)
            
        Returns:
            The created GraphNode instance
        """
        logger.debug(f"Creating graph node for procedure {procedureId}")
        
        input_data = {
            'accountId': accountId,
            'procedureId': procedureId
        }
        
        if parentNodeId is not None:
            input_data['parentNodeId'] = parentNodeId
        if name is not None:
            input_data['name'] = name
        if status is not None:
            input_data['status'] = status
        if metadata is not None:
            # Convert dict to JSON string for GraphQL schema compatibility
            import json
            input_data['metadata'] = json.dumps(metadata) if isinstance(metadata, dict) else str(metadata)
            
        mutation = """
        mutation CreateGraphNode($input: CreateGraphNodeInput!) {
            createGraphNode(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createGraphNode'], client)

    @classmethod
    def list_by_procedure(cls, procedureId: str, client: '_BaseAPIClient', limit: int = 100) -> List['GraphNode']:
        """List nodes for a procedure, ordered by creation time.
        
        Args:
            procedureId: The procedure ID to filter by
            client: The API client instance
            limit: Maximum number of nodes to return
            
        Returns:
            List of GraphNode instances ordered by creation time
        """
        logger.debug(f"Listing nodes for procedure: {procedureId}")
        
        query = """
        query ListNodesByProcedure($procedureId: ID!, $limit: Int) {
            listGraphNodeByProcedureIdAndCreatedAt(
                procedureId: $procedureId
                sortDirection: DESC
                limit: $limit
            ) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        try:
            result = client.execute(query, {'procedureId': procedureId, 'limit': limit})
            items = result['listGraphNodeByProcedureIdAndCreatedAt']['items']
        except Exception as e:
            logger.warning(f"Node query failed ({e}), returning empty list")
            logger.info(f"No nodes found for procedure {procedureId}")
            return []
        
        logger.debug(f"Found {len(items)} nodes for procedure {procedureId}")
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    def list_by_parent(cls, parentNodeId: str, client: '_BaseAPIClient', limit: int = 100) -> List['GraphNode']:
        """List child nodes for a parent node.
        
        Args:
            parentNodeId: The parent node ID to filter by
            client: The API client instance
            limit: Maximum number of nodes to return
            
        Returns:
            List of GraphNode instances that are children of the parent
        """
        logger.debug(f"Listing child nodes for parent: {parentNodeId}")
        
        query = """
        query ListNodesByParent($parentNodeId: ID!, $limit: Int) {
            listGraphNodeByParentNodeId(
                parentNodeId: $parentNodeId
                limit: $limit
            ) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        try:
            result = client.execute(query, {'parentNodeId': parentNodeId, 'limit': limit})
            items = result['listGraphNodeByParentNodeId']['items']
        except Exception as e:
            logger.warning(f"Parent nodes query failed ({e}), returning empty list")
            return []
        
        logger.debug(f"Found {len(items)} child nodes for parent {parentNodeId}")
        return [cls.from_dict(item, client) for item in items]

    def update(self, status: Optional[str] = None) -> 'GraphNode':
        """Update this graph node.
        
        Args:
            status: New status
            
        Returns:
            Updated GraphNode instance
        """
        if not self._client:
            raise ValueError("Cannot update graph node without client")
            
        logger.debug(f"Updating graph node {self.id}")
        
        input_data = {'id': self.id}
        if status is not None:
            input_data['status'] = status
            
        mutation = """
        mutation UpdateGraphNode($input: UpdateGraphNodeInput!) {
            updateGraphNode(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_node = self.from_dict(result['updateGraphNode'], self._client)
        
        # Update current instance
        if status is not None:
            self.status = updated_node.status
        
        return self

    def delete(self) -> bool:
        """Delete this graph node.
        
        Returns:
            True if deletion was successful
        """
        if not self._client:
            raise ValueError("Cannot delete graph node without client")
            
        logger.debug(f"Deleting graph node {self.id}")
        
        mutation = """
        mutation DeleteGraphNode($input: DeleteGraphNodeInput!) {
            deleteGraphNode(input: $input) {
                id
            }
        }
        """
        
        result = self._client.execute(mutation, {'input': {'id': self.id}})
        return result.get('deleteGraphNode', {}).get('id') == self.id

    def update_content(
        self, 
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'GraphNode':
        """Update the content of this node.
        
        Args:
            status: New status (optional)
            metadata: New metadata (JSON object, optional)
            
        Returns:
            The updated GraphNode
        """
        if not self._client:
            raise ValueError("Cannot update node without client")
        
        # Build update input - only include fields that are being updated
        input_data = {'id': self.id}
        
        if status is not None:
            input_data['status'] = status
        if metadata is not None:
            # Convert dict to JSON string for GraphQL schema compatibility
            import json
            input_data['metadata'] = json.dumps(metadata) if isinstance(metadata, dict) else str(metadata)
            
        mutation = """
        mutation UpdateGraphNode($input: UpdateGraphNodeInput!) {
            updateGraphNode(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_node = self.from_dict(result['updateGraphNode'], self._client)
        
        # Update current instance with new values
        if status is not None:
            self.status = updated_node.status
        if metadata is not None:
            self.metadata = updated_node.metadata
        
        return self

    def get_parent(self) -> Optional['GraphNode']:
        """Get the parent node for this node.
        
        Returns:
            The parent GraphNode or None if this is a root node
        """
        if not self.parentNodeId or not self._client:
            return None
            
        try:
            return GraphNode.get_by_id(self.parentNodeId, self._client)
        except ValueError:
            return None

    def get_children(self, limit: int = 100) -> List['GraphNode']:
        """Get child nodes for this node.
        
        Args:
            limit: Maximum number of children to return
            
        Returns:
            List of child GraphNode instances
        """
        if not self._client:
            return []
            
        return GraphNode.list_by_parent(self.id, self._client, limit)

    def create_child(
        self, 
        initial_metadata: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None
    ) -> 'GraphNode':
        """Create a child node with initial metadata.
        
        Args:
            initial_metadata: Initial metadata (optional, defaults to None)
            status: Node status (optional)
            
        Returns:
            The created child GraphNode
        """
        if not self._client:
            raise ValueError("Cannot create child node without client")
            
        # Create the child node
        child_node = GraphNode.create(
            client=self._client,
            procedureId=self.procedureId,
            parentNodeId=self.id,
            status=status
        )
        
        # Update child node with initial content
        if initial_metadata is not None or status is not None:
            child_node.update_content(
                status=status,
                metadata=initial_metadata
            )
        
        logger.debug(f"Created child node {child_node.id} for parent {self.id}")
        return child_node



