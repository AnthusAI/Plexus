"""
Experiment Model - Python representation of the GraphQL Experiment type.

This model class provides a Pythonic interface to the GraphQL Experiment type,
with all fields matching the schema definition. It handles:
- Data type conversion (e.g., ISO8601 strings to datetime objects)
- GraphQL mutation/query generation
- Object instantiation from API responses

The class structure mirrors the GraphQL schema, with fields like:
- type: The experiment type (e.g., 'accuracy', 'consistency')
- status: Current state ('PENDING', 'RUNNING', etc.)
- metrics: Performance metrics as JSON
- etc.

All fields in this class correspond directly to CLI options in the
plexus-dashboard experiment create/update commands.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import PlexusAPIClient
from .sample import Sample

@dataclass
class Experiment(BaseModel):
    type: str
    accountId: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    parameters: Optional[Dict] = None
    metrics: Optional[Dict] = None
    inferences: Optional[int] = None
    results: Optional[int] = None
    cost: Optional[float] = None
    progress: Optional[float] = None
    accuracy: Optional[float] = None
    accuracyType: Optional[str] = None
    sensitivity: Optional[float] = None
    specificity: Optional[float] = None
    precision: Optional[float] = None
    startedAt: Optional[datetime] = None
    estimatedEndAt: Optional[datetime] = None
    totalItems: Optional[int] = None
    processedItems: Optional[int] = None
    errorMessage: Optional[str] = None
    errorDetails: Optional[Dict] = None
    scorecardId: Optional[str] = None
    scoreId: Optional[str] = None
    confusionMatrix: Optional[Dict] = None

    def __init__(
        self,
        id: str,
        type: str,
        accountId: str,
        status: str,
        createdAt: datetime,
        updatedAt: datetime,
        parameters: Optional[Dict] = None,
        metrics: Optional[Dict] = None,
        inferences: Optional[int] = None,
        results: Optional[int] = None,
        cost: Optional[float] = None,
        progress: Optional[float] = None,
        accuracy: Optional[float] = None,
        accuracyType: Optional[str] = None,
        sensitivity: Optional[float] = None,
        specificity: Optional[float] = None,
        precision: Optional[float] = None,
        startedAt: Optional[datetime] = None,
        estimatedEndAt: Optional[datetime] = None,
        totalItems: Optional[int] = None,
        processedItems: Optional[int] = None,
        errorMessage: Optional[str] = None,
        errorDetails: Optional[Dict] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        confusionMatrix: Optional[Dict] = None,
        client: Optional[PlexusAPIClient] = None
    ):
        super().__init__(id, client)
        self.type = type
        self.accountId = accountId
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.parameters = parameters
        self.metrics = metrics
        self.inferences = inferences
        self.results = results
        self.cost = cost
        self.progress = progress
        self.accuracy = accuracy
        self.accuracyType = accuracyType
        self.sensitivity = sensitivity
        self.specificity = specificity
        self.precision = precision
        self.startedAt = startedAt
        self.estimatedEndAt = estimatedEndAt
        self.totalItems = totalItems
        self.processedItems = processedItems
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails
        self.scorecardId = scorecardId
        self.scoreId = scoreId
        self.confusionMatrix = confusionMatrix

    @classmethod
    def fields(cls) -> str:
        return """
            id
            type
            accountId
            status
            createdAt
            updatedAt
            parameters
            metrics
            inferences
            results
            cost
            progress
            accuracy
            accuracyType
            sensitivity
            specificity
            precision
            startedAt
            estimatedEndAt
            totalItems
            processedItems
            errorMessage
            errorDetails
            scorecardId
            scoreId
            confusionMatrix
        """

    @classmethod
    def create(cls, client: PlexusAPIClient, accountId: str, **kwargs) -> 'Experiment':
        # Format datetime in ISO 8601 format with Z suffix for UTC
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Build input dictionary
        input_data = {
            'accountId': accountId,
            'status': kwargs.get('status', 'PENDING'),
            'createdAt': now,
            'updatedAt': now,
            **kwargs  # Include any additional fields provided
        }
        
        mutation = """
        mutation CreateExperiment($input: CreateExperimentInput!) {
            createExperiment(input: $input) {
                %s
            }
        }
        """ % cls.fields()  # Use all fields in response
        
        variables = {
            'input': input_data
        }
        
        result = client.execute(mutation, variables)
        return cls.from_dict(result['createExperiment'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: PlexusAPIClient) -> 'Experiment':
        # Convert string dates to datetime objects
        for date_field in ['createdAt', 'updatedAt', 'startedAt', 'estimatedEndAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))

        return cls(
            id=data['id'],
            type=data['type'],
            accountId=data['accountId'],
            status=data['status'],
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            parameters=data.get('parameters'),
            metrics=data.get('metrics'),
            inferences=data.get('inferences'),
            results=data.get('results'),
            cost=data.get('cost'),
            progress=data.get('progress'),
            accuracy=data.get('accuracy'),
            accuracyType=data.get('accuracyType'),
            sensitivity=data.get('sensitivity'),
            specificity=data.get('specificity'),
            precision=data.get('precision'),
            startedAt=data.get('startedAt'),
            estimatedEndAt=data.get('estimatedEndAt'),
            totalItems=data.get('totalItems'),
            processedItems=data.get('processedItems'),
            errorMessage=data.get('errorMessage'),
            errorDetails=data.get('errorDetails'),
            scorecardId=data.get('scorecardId'),
            scoreId=data.get('scoreId'),
            confusionMatrix=data.get('confusionMatrix'),
            client=client
        )

    def update(self, **kwargs) -> 'Experiment':
        """Update this experiment with new values.
        
        Required fields are automatically handled:
        - type: Uses existing value if not provided
        - status: Uses existing value if not provided
        - updatedAt: Always set to current time
        - createdAt: Cannot be modified
        
        Args:
            **kwargs: Fields to update. Any field not provided keeps its current value.
            
        Returns:
            Experiment: Updated experiment instance
            
        Raises:
            ValueError: If attempting to modify createdAt
        """
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified after creation")
            
        # Build update data starting with required fields
        update_data = {
            'type': kwargs.pop('type', self.type),
            'status': kwargs.pop('status', self.status),
            'updatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        
        # Add any other provided fields
        update_data.update(kwargs)
        
        mutation = """
        mutation UpdateExperiment($input: UpdateExperimentInput!) {
            updateExperiment(input: $input) {
                %s
            }
        }
        """ % self.fields()
        
        variables = {
            'input': {
                'id': self.id,
                **update_data
            }
        }
        
        result = self._client.execute(mutation, variables)
        return self.from_dict(result['updateExperiment'], self._client)

    def get_samples(self) -> List['Sample']:
        """Get all samples associated with this experiment."""
        query = """
        query GetExperimentSamples($experimentId: ID!) {
            listSamples(filter: { experimentId: { eq: $experimentId } }) {
                items {
                    %s
                }
            }
        }
        """ % Sample.fields()
        
        result = self._client.execute(query, {'experimentId': self.id})
        return [Sample.from_dict(item, self._client) 
                for item in result['listSamples']['items']]