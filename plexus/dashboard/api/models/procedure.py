"""
Procedure Model - Python representation of the GraphQL Procedure type.

Provides methods to manage procedures including:
- Creating new procedures
- Linking to scorecards and scores
- Managing graph nodes and versions
- YAML configuration handling

Each procedure belongs to an account and is associated with a scorecard and score.
Procedures use a tree structure of nodes, where each node has versions containing
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
class Procedure(BaseModel):
    featured: bool
    rootNodeId: Optional[str]
    createdAt: datetime
    updatedAt: datetime
    accountId: str
    scorecardId: Optional[str]
    scoreId: Optional[str]
    scoreVersionId: Optional[str]

    def __init__(
        self,
        id: str,
        featured: bool,
        accountId: str,
        createdAt: datetime,
        updatedAt: datetime,
        rootNodeId: Optional[str] = None,
        code: Optional[str] = None,
        templateId: Optional[str] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        scoreVersionId: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.featured = featured
        self.code = code
        self.templateId = templateId
        self.rootNodeId = rootNodeId
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.accountId = accountId
        self.scorecardId = scorecardId
        self.scoreId = scoreId
        self.scoreVersionId = scoreVersionId

    @classmethod
    def fields(cls) -> str:
        return """
            id
            featured
            code
            templateId
            rootNodeId
            createdAt
            updatedAt
            accountId
            scorecardId
            scoreId
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'Procedure':
        # Parse datetime strings
        created_at = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
        
        return cls(
            id=data['id'],
            featured=data.get('featured', False),
            code=data.get('code'),
            templateId=data.get('templateId'),
            rootNodeId=data.get('rootNodeId'),
            createdAt=created_at,
            updatedAt=updated_at,
            accountId=data['accountId'],
            scorecardId=data.get('scorecardId'),
            scoreId=data.get('scoreId'),
            scoreVersionId=data.get('scoreVersionId'),
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
    ) -> 'Procedure':
        """Create a new procedure.
        
        Args:
            client: The API client
            accountId: ID of the account this procedure belongs to
            scorecardId: ID of the scorecard this procedure is associated with
            scoreId: ID of the score this procedure is associated with
            featured: Whether this procedure should be featured
            
        Returns:
            The created Procedure instance
        """
        logger.debug(f"Creating procedure for scorecard {scorecardId} and score {scoreId}")
        
        input_data = {
            'accountId': accountId,
            'scorecardId': scorecardId,
            'scoreId': scoreId,
            'featured': featured
        }
            
        mutation = """
        mutation CreateProcedure($input: CreateProcedureInput!) {
            createProcedure(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createProcedure'], client)

    @classmethod
    def list_by_account(cls, accountId: str, client: '_BaseAPIClient', limit: int = 100) -> List['Procedure']:
        """List procedures for an account, ordered by most recent first.
        
        Args:
            accountId: The account ID to filter by
            client: The API client instance
            limit: Maximum number of procedures to return
            
        Returns:
            List of Procedure instances ordered by updatedAt descending
        """
        logger.debug(f"Listing procedures for account: {accountId}")
        
        query = """
        query ListProceduresByAccount($accountId: String!, $limit: Int) {
            listProcedureByAccountIdAndUpdatedAt(
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
        items = result['listProcedureByAccountIdAndUpdatedAt']['items']
        
        logger.debug(f"Found {len(items)} procedures for account {accountId}")
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    def list_by_scorecard(cls, scorecardId: str, client: '_BaseAPIClient', limit: int = 100) -> List['Procedure']:
        """List procedures for a scorecard, ordered by most recent first.
        
        Args:
            scorecardId: The scorecard ID to filter by
            client: The API client instance
            limit: Maximum number of procedures to return
            
        Returns:
            List of Procedure instances ordered by updatedAt descending
        """
        logger.debug(f"Listing procedures for scorecard: {scorecardId}")
        
        query = """
        query ListProceduresByScorecard($scorecardId: String!, $limit: Int) {
            listProcedureByScorecardIdAndUpdatedAt(
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
        items = result['listProcedureByScorecardIdAndUpdatedAt']['items']
        
        logger.debug(f"Found {len(items)} procedures for scorecard {scorecardId}")
        return [cls.from_dict(item, client) for item in items]

    def update(self, featured: Optional[bool] = None, scorecardId: Optional[str] = None, scoreId: Optional[str] = None) -> 'Procedure':
        """Update this procedure.
        
        Args:
            featured: Whether this procedure should be featured
            scorecardId: New scorecard ID (optional)
            scoreId: New score ID (optional)
            
        Returns:
            Updated Procedure instance
        """
        if not self._client:
            raise ValueError("Cannot update procedure without client")
            
        logger.debug(f"Updating procedure {self.id}")
        
        input_data = {'id': self.id}
        if featured is not None:
            input_data['featured'] = featured
        if scorecardId is not None:
            input_data['scorecardId'] = scorecardId
        if scoreId is not None:
            input_data['scoreId'] = scoreId
            
        mutation = """
        mutation UpdateProcedure($input: UpdateProcedureInput!) {
            updateProcedure(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_procedure = self.from_dict(result['updateProcedure'], self._client)
        
        # Update current instance
        self.featured = updated_procedure.featured
        self.scorecardId = updated_procedure.scorecardId
        self.scoreId = updated_procedure.scoreId
        self.updatedAt = updated_procedure.updatedAt
        
        return self

    def delete(self) -> bool:
        """Delete this procedure.
        
        Returns:
            True if deletion was successful
        """
        if not self._client:
            raise ValueError("Cannot delete procedure without client")
            
        logger.debug(f"Deleting procedure {self.id}")
        
        mutation = """
        mutation DeleteProcedure($input: DeleteProcedureInput!) {
            deleteProcedure(input: $input) {
                id
            }
        }
        """
        
        result = self._client.execute(mutation, {'input': {'id': self.id}})
        delete_result = result.get('deleteProcedure')
        if delete_result is None:
            return False
        return delete_result.get('id') == self.id

    def get_root_node(self) -> Optional['GraphNode']:
        """Get the root node for this procedure.
        
        Returns:
            The root GraphNode or None if not set
        """
        if not self.rootNodeId or not self._client:
            return None
            
        from .graph_node import GraphNode
        try:
            return GraphNode.get_by_id(self.rootNodeId, self._client)
        except ValueError:
            return None

    def create_root_node(self, yaml_config: str, initial_metadata: Optional[Dict[str, Any]] = None) -> 'GraphNode':
        """Create a root node for this procedure with initial metadata.
        
        Args:
            yaml_config: The YAML configuration for the initial version
            initial_metadata: Optional initial metadata (defaults to {"initialized": True})
            
        Returns:
            The created GraphNode
        """
        if not self._client:
            raise ValueError("Cannot create root node without client")
            
        from .graph_node import GraphNode
        
        logger.debug(f"Creating root node for procedure {self.id}")
        
        # Create the node
        node = GraphNode.create(
            client=self._client,
            procedureId=self.id,
            parentNodeId=None,
            status='ACTIVE'
        )
        
        # Set initial metadata
        if initial_metadata is None:
            initial_metadata = {"initialized": True, "code": yaml_config}
            
        node.update_content(
            status='QUEUED',
            metadata=initial_metadata
        )
        
        # Update procedure to set root node
        self.update_root_node(node.id)
        
        logger.debug(f"Created root node {node.id} for procedure {self.id}")
        return node

    def update_root_node(self, rootNodeId: Optional[str]) -> 'Procedure':
        """Update the root node ID for this procedure.
        
        Args:
            rootNodeId: The ID of the node to set as root
            
        Returns:
            Updated Procedure instance
        """
        if not self._client:
            raise ValueError("Cannot update root node without client")
            
        logger.debug(f"Setting root node {rootNodeId} for procedure {self.id}")
        
        input_data = {'id': self.id}
        
        # Only include rootNodeId if it's not None (avoid DynamoDB empty string error)
        if rootNodeId is not None:
            input_data['rootNodeId'] = rootNodeId
            
        mutation = """
        mutation UpdateProcedure($input: UpdateProcedureInput!) {
            updateProcedure(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        result = self._client.execute(mutation, {'input': input_data})
        updated_procedure = self.from_dict(result['updateProcedure'], self._client)
        
        # Update current instance
        self.rootNodeId = updated_procedure.rootNodeId
        self.updatedAt = updated_procedure.updatedAt
        
        return self



