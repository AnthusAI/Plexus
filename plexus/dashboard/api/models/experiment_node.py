"""
ExperimentNode Model - Python representation of the GraphQL ExperimentNode type.

Represents a node in the experiment tree structure. Each node belongs to an experiment
and can have a parent node (None for root nodes) and child nodes. Nodes track
their version number within the experiment and maintain status information.

Each node can have multiple versions (ExperimentNodeVersion) containing different
YAML configurations and computed values.
"""

import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class ExperimentNode(BaseModel):
    experimentId: str
    parentNodeId: Optional[str]
    name: Optional[str]
    status: Optional[str]
    createdAt: str
    updatedAt: str

    def __init__(
        self,
        id: str,
        experimentId: str,
        createdAt: str,
        updatedAt: str,
        parentNodeId: Optional[str] = None,
        name: Optional[str] = None,
        status: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.experimentId = experimentId
        self.parentNodeId = parentNodeId
        self.name = name
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt

    @classmethod
    def fields(cls) -> str:
        return """
            id
            experimentId
            parentNodeId
            name
            status
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'ExperimentNode':
        return cls(
            id=data['id'],
            experimentId=data['experimentId'],
            parentNodeId=data.get('parentNodeId'),
            name=data.get('name'),
            status=data.get('status'),
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            client=client
        )

    @classmethod
    def create(
        cls,
        client: '_BaseAPIClient',
        experimentId: str,
        parentNodeId: Optional[str] = None,
        name: Optional[str] = None,
        status: Optional[str] = None
    ) -> 'ExperimentNode':
        """Create a new experiment node.
        
        Args:
            client: The API client
            experimentId: ID of the experiment this node belongs to
            parentNodeId: ID of the parent node (None for root nodes)
            name: Name of the node (optional)
            status: Node status (optional)
            
        Returns:
            The created ExperimentNode instance
        """
        logger.debug(f"Creating experiment node for experiment {experimentId}")
        
        input_data = {
            'experimentId': experimentId
        }
        
        if parentNodeId is not None:
            input_data['parentNodeId'] = parentNodeId
        if name is not None:
            input_data['name'] = name
        if status is not None:
            input_data['status'] = status
            
        mutation = """
        mutation CreateExperimentNode($input: CreateExperimentNodeInput!) {
            createExperimentNode(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createExperimentNode'], client)

    @classmethod
    def list_by_experiment(cls, experimentId: str, client: '_BaseAPIClient', limit: int = 100) -> List['ExperimentNode']:
        """List nodes for an experiment, ordered by creation time.
        
        Args:
            experimentId: The experiment ID to filter by
            client: The API client instance
            limit: Maximum number of nodes to return
            
        Returns:
            List of ExperimentNode instances ordered by creation time
        """
        logger.debug(f"Listing nodes for experiment: {experimentId}")
        
        query = """
        query ListNodesByExperiment($experimentId: ID!, $limit: Int) {
            listExperimentNodeByExperimentIdAndCreatedAt(
                experimentId: $experimentId
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
            result = client.execute(query, {'experimentId': experimentId, 'limit': limit})
            items = result['listExperimentNodeByExperimentIdAndCreatedAt']['items']
        except Exception as e:
            logger.warning(f"Node query failed ({e}), returning empty list")
            logger.info(f"No nodes found for experiment {experimentId}")
            return []
        
        logger.debug(f"Found {len(items)} nodes for experiment {experimentId}")
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    def list_by_parent(cls, parentNodeId: str, client: '_BaseAPIClient', limit: int = 100) -> List['ExperimentNode']:
        """List child nodes for a parent node.
        
        Args:
            parentNodeId: The parent node ID to filter by
            client: The API client instance
            limit: Maximum number of nodes to return
            
        Returns:
            List of ExperimentNode instances that are children of the parent
        """
        logger.debug(f"Listing child nodes for parent: {parentNodeId}")
        
        query = """
        query ListNodesByParent($parentNodeId: ID!, $limit: Int) {
            listExperimentNodeByParentNodeId(
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
            items = result['listExperimentNodeByParentNodeId']['items']
        except Exception as e:
            logger.warning(f"Parent nodes query failed ({e}), returning empty list")
            return []
        
        logger.debug(f"Found {len(items)} child nodes for parent {parentNodeId}")
        return [cls.from_dict(item, client) for item in items]

    def update(self, status: Optional[str] = None) -> 'ExperimentNode':
        """Update this experiment node.
        
        Args:
            status: New status
            
        Returns:
            Updated ExperimentNode instance
        """
        if not self._client:
            raise ValueError("Cannot update experiment node without client")
            
        logger.debug(f"Updating experiment node {self.id}")
        
        input_data = {'id': self.id}
        if status is not None:
            input_data['status'] = status
            
        mutation = """
        mutation UpdateExperimentNode($input: UpdateExperimentNodeInput!) {
            updateExperimentNode(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_node = self.from_dict(result['updateExperimentNode'], self._client)
        
        # Update current instance
        if status is not None:
            self.status = updated_node.status
        
        return self

    def delete(self) -> bool:
        """Delete this experiment node.
        
        Returns:
            True if deletion was successful
        """
        if not self._client:
            raise ValueError("Cannot delete experiment node without client")
            
        logger.debug(f"Deleting experiment node {self.id}")
        
        mutation = """
        mutation DeleteExperimentNode($input: DeleteExperimentNodeInput!) {
            deleteExperimentNode(input: $input) {
                id
            }
        }
        """
        
        result = self._client.execute(mutation, {'input': {'id': self.id}})
        return result.get('deleteExperimentNode', {}).get('id') == self.id

    def get_versions(self, limit: int = 100) -> List['ExperimentNodeVersion']:
        """Get all versions for this node, ordered by sequence number.
        
        Args:
            limit: Maximum number of versions to return
            
        Returns:
            List of ExperimentNodeVersion instances ordered by seq
        """
        if not self._client:
            return []
            
        from .experiment_node_version import ExperimentNodeVersion
        return ExperimentNodeVersion.list_by_node(self.id, self._client, limit)

    def get_latest_version(self) -> Optional['ExperimentNodeVersion']:
        """Get the latest version for this node (highest seq number).
        
        Returns:
            The latest ExperimentNodeVersion or None if no versions exist
        """
        versions = self.get_versions(limit=1)
        return versions[0] if versions else None

    def create_version(
        self, 
        code: str, 
        status: Optional[str] = None,
        hypothesis: Optional[str] = None,
        insight: Optional[str] = None,
        value: Optional[Dict[str, Any]] = None
    ) -> 'ExperimentNodeVersion':
        """Create a new version for this node.
        
        Args:
            code: Code configuration (YAML/JSON)
            value: Computed value (JSON object, optional)
            status: Version status (optional)
            hypothesis: Hypothesis for this version (optional)
            insight: Insight for this version (optional)
            
        Returns:
            The created ExperimentNodeVersion
        """
        if not self._client:
            raise ValueError("Cannot create version without client")
            
        from .experiment_node_version import ExperimentNodeVersion
        
        return ExperimentNodeVersion.create(
            client=self._client,
            experimentId=self.experimentId,
            nodeId=self.id,
            status=status,
            code=code,
            hypothesis=hypothesis,
            insight=insight,
            value=value
        )

    def get_parent(self) -> Optional['ExperimentNode']:
        """Get the parent node for this node.
        
        Returns:
            The parent ExperimentNode or None if this is a root node
        """
        if not self.parentNodeId or not self._client:
            return None
            
        try:
            return ExperimentNode.get_by_id(self.parentNodeId, self._client)
        except ValueError:
            return None

    def get_children(self, limit: int = 100) -> List['ExperimentNode']:
        """Get child nodes for this node.
        
        Args:
            limit: Maximum number of children to return
            
        Returns:
            List of child ExperimentNode instances
        """
        if not self._client:
            return []
            
        return ExperimentNode.list_by_parent(self.id, self._client, limit)

    def create_child(
        self, 
        code: str, 
        initial_value: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        hypothesis: Optional[str] = None,
        insight: Optional[str] = None
    ) -> 'ExperimentNode':
        """Create a child node with an initial version.
        
        Args:
            code: Code configuration for the initial version
            initial_value: Initial computed value (optional, defaults to None)
            status: Node status (optional)
            hypothesis: Hypothesis for the initial version (optional)
            insight: Insight for the initial version (optional)
            
        Returns:
            The created child ExperimentNode
        """
        if not self._client:
            raise ValueError("Cannot create child node without client")
            
        # Create the child node
        child_node = ExperimentNode.create(
            client=self._client,
            experimentId=self.experimentId,
            parentNodeId=self.id,
            status=status
        )
        
        # Create initial version for the child
        child_node.create_version(
            code=code,
            value=initial_value,
            status=status,
            hypothesis=hypothesis,
            insight=insight
        )
        
        logger.debug(f"Created child node {child_node.id} for parent {self.id}")
        return child_node