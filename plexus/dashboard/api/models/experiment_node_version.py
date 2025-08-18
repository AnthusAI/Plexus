"""
ExperimentNodeVersion Model - Python representation of the GraphQL ExperimentNodeVersion type.

Represents a specific version of an experiment node, containing:
- YAML configuration for this version
- Computed value (JSON data)
- Status tracking (QUEUED, RUNNING, SUCCEEDED, FAILED)
- Sequential ordering within the node

Each version belongs to a specific node and experiment, and versions are ordered
by their sequence number within each node.
"""

import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
import json
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class ExperimentNodeVersion(BaseModel):
    experimentId: str
    nodeId: str
    status: Optional[str]
    code: str
    hypothesis: Optional[str]
    insight: Optional[str]
    value: Optional[Dict[str, Any]]
    createdAt: str
    updatedAt: str

    def __init__(
        self,
        id: str,
        experimentId: str,
        nodeId: str,
        code: str,
        createdAt: str,
        updatedAt: str,
        value: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        hypothesis: Optional[str] = None,
        insight: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.experimentId = experimentId
        self.nodeId = nodeId
        self.status = status
        self.code = code
        self.hypothesis = hypothesis
        self.insight = insight
        self.value = value or {}
        self.createdAt = createdAt
        self.updatedAt = updatedAt

    @classmethod
    def fields(cls) -> str:
        return """
            id
            experimentId
            nodeId
            status
            code
            hypothesis
            insight
            value
            createdAt
            updatedAt
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'ExperimentNodeVersion':
        # Parse value JSON if it's a string
        value = data.get('value')
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # If JSON parsing fails, wrap the string
                value = {"raw_value": value}
        elif value is None:
            value = {}
        
        return cls(
            id=data['id'],
            experimentId=data['experimentId'],
            nodeId=data['nodeId'],
            status=data.get('status'),
            code=data['code'],
            hypothesis=data.get('hypothesis'),
            insight=data.get('insight'),
            value=value,
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            client=client
        )

    @classmethod
    def create(
        cls,
        client: '_BaseAPIClient',
        experimentId: str,
        nodeId: str,
        code: str,
        status: Optional[str] = None,
        hypothesis: Optional[str] = None,
        insight: Optional[str] = None,
        value: Optional[Dict[str, Any]] = None
    ) -> 'ExperimentNodeVersion':
        """Create a new experiment node version.
        
        Args:
            client: The API client
            experimentId: ID of the experiment this version belongs to
            nodeId: ID of the node this version belongs to
            code: Code configuration content (YAML/JSON)
            value: Computed value (will be JSON-serialized, optional)
            status: Version status (optional)
            hypothesis: Hypothesis for this version (optional)
            insight: Insight for this version (optional)
            
        Returns:
            The created ExperimentNodeVersion instance
        """
        logger.debug(f"Creating experiment node version for node {nodeId}")
        
        # Ensure value is JSON-serializable
        if value is not None and not isinstance(value, (dict, list, str, int, float, bool)):
            value = {"raw_value": str(value)}
        
        input_data = {
            'experimentId': experimentId,
            'nodeId': nodeId,
            'code': code
        }
        
        # Only include value if it's not None
        if value is not None:
            input_data['value'] = json.dumps(value) if isinstance(value, (dict, list)) else value
        
        if status is not None:
            input_data['status'] = status
        if hypothesis is not None:
            input_data['hypothesis'] = hypothesis
        if insight is not None:
            input_data['insight'] = insight
            
        mutation = """
        mutation CreateExperimentNodeVersion($input: CreateExperimentNodeVersionInput!) {
            createExperimentNodeVersion(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createExperimentNodeVersion'], client)

    @classmethod
    def list_by_node(cls, nodeId: str, client: '_BaseAPIClient', limit: int = 100) -> List['ExperimentNodeVersion']:
        """List versions for a node, ordered by creation time descending (latest first).
        
        Args:
            nodeId: The node ID to filter by
            client: The API client instance
            limit: Maximum number of versions to return
            
        Returns:
            List of ExperimentNodeVersion instances ordered by createdAt descending
        """
        logger.debug(f"Listing versions for node: {nodeId}")
        
        query = """
        query ListVersionsByNode($nodeId: ID!, $limit: Int) {
            listExperimentNodeVersionByNodeIdAndCreatedAt(
                nodeId: $nodeId
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
            result = client.execute(query, {'nodeId': nodeId, 'limit': limit})
            items = result['listExperimentNodeVersionByNodeIdAndCreatedAt']['items']
        except Exception as e:
            logger.warning(f"Version query failed ({e}), returning empty list")
            logger.info(f"No versions found for node {nodeId}")
            return []
        
        logger.debug(f"Found {len(items)} versions for node {nodeId}")
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    def get_latest_by_node(cls, nodeId: str, client: '_BaseAPIClient') -> Optional['ExperimentNodeVersion']:
        """Get the latest version for a node (most recent by createdAt).
        
        Args:
            nodeId: The node ID to get the latest version for
            client: The API client instance
            
        Returns:
            The latest ExperimentNodeVersion or None if no versions exist
        """
        versions = cls.list_by_node(nodeId, client, limit=1)
        return versions[0] if versions else None

    def update(
        self, 
        status: Optional[str] = None, 
        yaml: Optional[str] = None, 
        value: Optional[Dict[str, Any]] = None
    ) -> 'ExperimentNodeVersion':
        """Update this experiment node version.
        
        Args:
            status: New status ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')
            yaml: New YAML configuration
            value: New computed value (will be JSON-serialized)
            
        Returns:
            Updated ExperimentNodeVersion instance
        """
        if not self._client:
            raise ValueError("Cannot update experiment node version without client")
            
        logger.debug(f"Updating experiment node version {self.id}")
        
        input_data = {'id': self.id}
        if status is not None:
            input_data['status'] = status
        if yaml is not None:
            input_data['yaml'] = yaml
        if value is not None:
            # Ensure value is JSON-serializable
            if not isinstance(value, (dict, list, str, int, float, bool, type(None))):
                value = {"raw_value": str(value)}
            input_data['value'] = json.dumps(value) if isinstance(value, (dict, list)) else value
            
        mutation = """
        mutation UpdateExperimentNodeVersion($input: UpdateExperimentNodeVersionInput!) {
            updateExperimentNodeVersion(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_version = self.from_dict(result['updateExperimentNodeVersion'], self._client)
        
        # Update current instance
        if status is not None:
            self.status = updated_version.status
        if yaml is not None:
            self.yaml = updated_version.yaml
        if value is not None:
            self.value = updated_version.value
        
        return self

    def delete(self) -> bool:
        """Delete this experiment node version.
        
        Returns:
            True if deletion was successful
        """
        if not self._client:
            raise ValueError("Cannot delete experiment node version without client")
            
        logger.debug(f"Deleting experiment node version {self.id}")
        
        mutation = """
        mutation DeleteExperimentNodeVersion($input: DeleteExperimentNodeVersionInput!) {
            deleteExperimentNodeVersion(input: $input) {
                id
            }
        }
        """
        
        result = self._client.execute(mutation, {'input': {'id': self.id}})
        return result.get('deleteExperimentNodeVersion', {}).get('id') == self.id

    def get_node(self) -> Optional['ExperimentNode']:
        """Get the node this version belongs to.
        
        Returns:
            The ExperimentNode this version belongs to, or None if not found
        """
        if not self._client:
            return None
            
        from .experiment_node import ExperimentNode
        try:
            return ExperimentNode.get_by_id(self.nodeId, self._client)
        except ValueError:
            return None

    def get_experiment(self) -> Optional['Experiment']:
        """Get the experiment this version belongs to.
        
        Returns:
            The Experiment this version belongs to, or None if not found
        """
        if not self._client:
            return None
            
        from .experiment import Experiment
        try:
            return Experiment.get_by_id(self.experimentId, self._client)
        except ValueError:
            return None

    def mark_running(self) -> 'ExperimentNodeVersion':
        """Mark this version as running.
        
        Returns:
            Updated ExperimentNodeVersion instance
        """
        return self.update(status='RUNNING')

    def mark_succeeded(self, final_value: Optional[Dict[str, Any]] = None) -> 'ExperimentNodeVersion':
        """Mark this version as succeeded.
        
        Args:
            final_value: Optional final computed value to set
            
        Returns:
            Updated ExperimentNodeVersion instance
        """
        if final_value is not None:
            return self.update(status='SUCCEEDED', value=final_value)
        else:
            return self.update(status='SUCCEEDED')

    def mark_failed(self, error_info: Optional[Dict[str, Any]] = None) -> 'ExperimentNodeVersion':
        """Mark this version as failed.
        
        Args:
            error_info: Optional error information to include in the value
            
        Returns:
            Updated ExperimentNodeVersion instance
        """
        if error_info is not None:
            # Merge error info with existing value
            updated_value = self.value.copy()
            updated_value.update({"error": error_info})
            return self.update(status='FAILED', value=updated_value)
        else:
            return self.update(status='FAILED')

    def get_yaml_config(self) -> str:
        """Get the code configuration for this version.
        
        Returns:
            The code configuration string
        """
        return self.code

    def get_computed_value(self) -> Dict[str, Any]:
        """Get the computed value for this version.
        
        Returns:
            The computed value as a dictionary
        """
        return self.value

    def is_completed(self) -> bool:
        """Check if this version has completed (succeeded or failed).
        
        Returns:
            True if status is SUCCEEDED or FAILED
        """
        return self.status in ['SUCCEEDED', 'FAILED']

    def is_running(self) -> bool:
        """Check if this version is currently running.
        
        Returns:
            True if status is RUNNING
        """
        return self.status == 'RUNNING'

    def is_queued(self) -> bool:
        """Check if this version is queued for execution.
        
        Returns:
            True if status is QUEUED
        """
        return self.status == 'QUEUED'