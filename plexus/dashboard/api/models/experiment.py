"""
Experiment Model - Python representation of the GraphQL Experiment type.

Provides methods to manage experiments including:
- Creating new experiments
- Linking to scorecards and scores
- Managing experiment nodes and versions
- YAML configuration handling

Each experiment belongs to an account and is associated with a scorecard and score.
Experiments use a tree structure of nodes, where each node has versions containing
YAML configurations and computed values.
"""

import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
from .base import BaseModel

if TYPE_CHECKING:
    from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Experiment(BaseModel):
    featured: bool
    rootNodeId: Optional[str]
    createdAt: datetime
    updatedAt: datetime
    accountId: str
    scorecardId: Optional[str]
    scoreId: Optional[str]

    def __init__(
        self,
        id: str,
        featured: bool,
        accountId: str,
        createdAt: datetime,
        updatedAt: datetime,
        rootNodeId: Optional[str] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.featured = featured
        self.rootNodeId = rootNodeId
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.accountId = accountId
        self.scorecardId = scorecardId
        self.scoreId = scoreId

    @classmethod
    def fields(cls) -> str:
        return """
            id
            featured
            rootNodeId
            createdAt
            updatedAt
            accountId
            scorecardId
            scoreId
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'Experiment':
        # Parse datetime strings
        created_at = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
        
        return cls(
            id=data['id'],
            featured=data.get('featured', False),
            rootNodeId=data.get('rootNodeId'),
            createdAt=created_at,
            updatedAt=updated_at,
            accountId=data['accountId'],
            scorecardId=data.get('scorecardId'),
            scoreId=data.get('scoreId'),
            client=client
        )

    @classmethod
    def create(
        cls,
        client: '_BaseAPIClient',
        accountId: str,
        scorecardId: str,
        scoreId: str,
        featured: bool = False
    ) -> 'Experiment':
        """Create a new experiment.
        
        Args:
            client: The API client
            accountId: ID of the account this experiment belongs to
            scorecardId: ID of the scorecard this experiment is associated with
            scoreId: ID of the score this experiment is associated with
            featured: Whether this experiment should be featured
            
        Returns:
            The created Experiment instance
        """
        logger.debug(f"Creating experiment for scorecard {scorecardId} and score {scoreId}")
        
        input_data = {
            'accountId': accountId,
            'scorecardId': scorecardId,
            'scoreId': scoreId,
            'featured': featured
        }
            
        mutation = """
        mutation CreateExperiment($input: CreateExperimentInput!) {
            createExperiment(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createExperiment'], client)

    @classmethod
    def list_by_account(cls, accountId: str, client: '_BaseAPIClient', limit: int = 100) -> List['Experiment']:
        """List experiments for an account, ordered by most recent first.
        
        Args:
            accountId: The account ID to filter by
            client: The API client instance
            limit: Maximum number of experiments to return
            
        Returns:
            List of Experiment instances ordered by updatedAt descending
        """
        logger.debug(f"Listing experiments for account: {accountId}")
        
        query = """
        query ListExperimentsByAccount($accountId: String!, $limit: Int) {
            listExperimentByAccountIdAndUpdatedAt(
                accountId: $accountId
                sortDirection: DESC
                limit: $limit
            ) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'accountId': accountId, 'limit': limit})
        items = result['listExperimentByAccountIdAndUpdatedAt']['items']
        
        logger.debug(f"Found {len(items)} experiments for account {accountId}")
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    def list_by_scorecard(cls, scorecardId: str, client: '_BaseAPIClient', limit: int = 100) -> List['Experiment']:
        """List experiments for a scorecard, ordered by most recent first.
        
        Args:
            scorecardId: The scorecard ID to filter by
            client: The API client instance
            limit: Maximum number of experiments to return
            
        Returns:
            List of Experiment instances ordered by updatedAt descending
        """
        logger.debug(f"Listing experiments for scorecard: {scorecardId}")
        
        query = """
        query ListExperimentsByScorecard($scorecardId: String!, $limit: Int) {
            listExperimentByScorecardIdAndUpdatedAt(
                scorecardId: $scorecardId
                sortDirection: DESC
                limit: $limit
            ) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'scorecardId': scorecardId, 'limit': limit})
        items = result['listExperimentByScorecardIdAndUpdatedAt']['items']
        
        logger.debug(f"Found {len(items)} experiments for scorecard {scorecardId}")
        return [cls.from_dict(item, client) for item in items]

    def update(self, featured: Optional[bool] = None, scorecardId: Optional[str] = None, scoreId: Optional[str] = None) -> 'Experiment':
        """Update this experiment.
        
        Args:
            featured: Whether this experiment should be featured
            scorecardId: New scorecard ID (optional)
            scoreId: New score ID (optional)
            
        Returns:
            Updated Experiment instance
        """
        if not self._client:
            raise ValueError("Cannot update experiment without client")
            
        logger.debug(f"Updating experiment {self.id}")
        
        input_data = {'id': self.id}
        if featured is not None:
            input_data['featured'] = featured
        if scorecardId is not None:
            input_data['scorecardId'] = scorecardId
        if scoreId is not None:
            input_data['scoreId'] = scoreId
            
        mutation = """
        mutation UpdateExperiment($input: UpdateExperimentInput!) {
            updateExperiment(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_experiment = self.from_dict(result['updateExperiment'], self._client)
        
        # Update current instance
        self.featured = updated_experiment.featured
        self.scorecardId = updated_experiment.scorecardId
        self.scoreId = updated_experiment.scoreId
        self.updatedAt = updated_experiment.updatedAt
        
        return self

    def delete(self) -> bool:
        """Delete this experiment.
        
        Returns:
            True if deletion was successful
        """
        if not self._client:
            raise ValueError("Cannot delete experiment without client")
            
        logger.debug(f"Deleting experiment {self.id}")
        
        mutation = """
        mutation DeleteExperiment($input: DeleteExperimentInput!) {
            deleteExperiment(input: $input) {
                id
            }
        }
        """
        
        result = self._client.execute(mutation, {'input': {'id': self.id}})
        delete_result = result.get('deleteExperiment')
        if delete_result is None:
            return False
        return delete_result.get('id') == self.id

    def get_root_node(self) -> Optional['ExperimentNode']:
        """Get the root node for this experiment.
        
        Returns:
            The root ExperimentNode or None if not set
        """
        if not self.rootNodeId or not self._client:
            return None
            
        from .experiment_node import ExperimentNode
        try:
            return ExperimentNode.get_by_id(self.rootNodeId, self._client)
        except ValueError:
            return None

    def create_root_node(self, yaml_config: str, initial_value: Optional[Dict[str, Any]] = None) -> 'ExperimentNode':
        """Create a root node for this experiment with an initial version.
        
        Args:
            yaml_config: The YAML configuration for the initial version
            initial_value: Optional initial computed value (defaults to {"initialized": True})
            
        Returns:
            The created ExperimentNode
        """
        if not self._client:
            raise ValueError("Cannot create root node without client")
            
        from .experiment_node import ExperimentNode
        from .experiment_node_version import ExperimentNodeVersion
        
        logger.debug(f"Creating root node for experiment {self.id}")
        
        # Create the node
        node = ExperimentNode.create(
            client=self._client,
            experimentId=self.id,
            parentNodeId=None,
            status='ACTIVE'
        )
        
        # Create initial version
        if initial_value is None:
            initial_value = {"initialized": True}
            
        version = ExperimentNodeVersion.create(
            client=self._client,
            experimentId=self.id,
            nodeId=node.id,
            code=yaml_config,
            status='QUEUED',
            value=initial_value
        )
        
        # Update experiment to set root node
        self.update_root_node(node.id)
        
        logger.debug(f"Created root node {node.id} with initial version {version.id}")
        return node

    def update_root_node(self, rootNodeId: Optional[str]) -> 'Experiment':
        """Update the root node ID for this experiment.
        
        Args:
            rootNodeId: The ID of the node to set as root
            
        Returns:
            Updated Experiment instance
        """
        if not self._client:
            raise ValueError("Cannot update root node without client")
            
        logger.debug(f"Setting root node {rootNodeId} for experiment {self.id}")
        
        input_data = {'id': self.id}
        
        # Only include rootNodeId if it's not None (avoid DynamoDB empty string error)
        if rootNodeId is not None:
            input_data['rootNodeId'] = rootNodeId
            
        mutation = """
        mutation UpdateExperiment($input: UpdateExperimentInput!) {
            updateExperiment(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_experiment = self.from_dict(result['updateExperiment'], self._client)
        
        # Update current instance
        self.rootNodeId = updated_experiment.rootNodeId
        self.updatedAt = updated_experiment.updatedAt
        
        return self