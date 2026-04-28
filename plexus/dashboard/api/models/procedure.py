"""
Procedure Model - Python representation of the GraphQL Procedure type.

Provides methods to manage procedures including:
- Creating new procedures
- Linking to scorecards and scores
- YAML configuration handling

Each procedure belongs to an account and is associated with a scorecard and score.
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
    state: Optional[str]
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
        name: Optional[str] = None,
        status: Optional[str] = None,
        code: Optional[str] = None,
        state: Optional[str] = None,
        parentProcedureId: Optional[str] = None,  # Changed from templateId
        templateId: Optional[str] = None,  # Keep for backward compatibility
        isTemplate: Optional[bool] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        scoreVersionId: Optional[str] = None,
        client: Optional['_BaseAPIClient'] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.status = status
        self.featured = featured
        self.code = code
        self.state = state
        # Use parentProcedureId if provided, otherwise fall back to templateId for backward compat
        self.parentProcedureId = parentProcedureId or templateId
        self.templateId = parentProcedureId or templateId  # Keep both for backward compat
        self.isTemplate = isTemplate
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
            name
            description
            status
            featured
            isTemplate
            code
            category
            version
            isDefault
            parentProcedureId
            waitingOnMessageId
            metadata
            createdAt
            updatedAt
            accountId
            scorecardId
            scoreId
            scoreVersionId
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'Procedure':
        # Parse datetime strings
        created_at = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
        
        return cls(
            id=data['id'],
            name=data.get('name'),
            status=data.get('status'),
            featured=data.get('featured', False),
            code=data.get('code'),
            state=data.get('state'),
            parentProcedureId=data.get('parentProcedureId'),
            isTemplate=data.get('isTemplate'),
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
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        featured: bool = False,
        parentProcedureId: Optional[str] = None,
        isTemplate: bool = False,
        code: Optional[str] = None,
        state: str = "start",
        scoreVersionId: Optional[str] = None
    ) -> 'Procedure':
        """Create a new procedure.

        Args:
            client: The API client
            accountId: ID of the account this procedure belongs to
            scorecardId: Optional ID of the scorecard this procedure is associated with
            scoreId: Optional ID of the score this procedure is associated with
            featured: Whether this procedure should be featured
            parentProcedureId: Optional ID of the parent procedure (if this is an instance)
            isTemplate: Whether this procedure is a template (default: False)
            code: Optional YAML code for the procedure
            state: Initial state (default: "start")
            scoreVersionId: Optional ID of the score version

        Returns:
            The created Procedure instance
        """
        if scorecardId and scoreId:
            logger.debug(f"Creating procedure for scorecard {scorecardId} and score {scoreId}")
        else:
            logger.debug(f"Creating standalone procedure")

        # Generate name from code or use default
        name = "Lua DSL Procedure"
        if code:
            # Try to extract name from YAML
            try:
                import yaml
                yaml_data = yaml.safe_load(code)
                if yaml_data and 'name' in yaml_data:
                    name = yaml_data['name']
            except:
                pass

        input_data = {
            'accountId': accountId,
            'name': name,
            'featured': featured,
            'isTemplate': isTemplate,
            # Note: 'state' is NOT supported in CreateProcedureInput GraphQL schema
        }

        # Add optional fields if provided
        if scorecardId:
            input_data['scorecardId'] = scorecardId
        if scoreId:
            input_data['scoreId'] = scoreId
        if parentProcedureId:
            input_data['parentProcedureId'] = parentProcedureId
        if code:
            input_data['code'] = code
        if scoreVersionId:
            input_data['scoreVersionId'] = scoreVersionId
            
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

    def update(
        self,
        featured: Optional[bool] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        code: Optional[str] = None,
    ) -> 'Procedure':
        """Update this procedure.
        
        Args:
            featured: Whether this procedure should be featured
            scorecardId: New scorecard ID (optional)
            scoreId: New score ID (optional)
            code: New procedure YAML/code (optional)
            
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
        if code is not None:
            input_data['code'] = code
            
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
        self.code = updated_procedure.code
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

