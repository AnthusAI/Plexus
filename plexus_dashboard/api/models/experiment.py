"""
Experiment Model - Python representation of the GraphQL Experiment type.

This model represents individual experiments in the system, tracking:
- Accuracy and performance metrics
- Processing status and progress
- Error states and details
- Relationships to accounts, scorecards, and scores

All mutations (create/update) are performed in background threads for 
non-blocking operation.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Thread
from .base import BaseModel
from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

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
    cost: Optional[float] = None
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
        client: Optional[_BaseAPIClient] = None,
        parameters: Optional[Dict] = None,
        metrics: Optional[Dict] = None,
        inferences: Optional[int] = None,
        cost: Optional[float] = None,
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
        self.cost = cost
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
            cost
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
    def create(
        cls,
        client: _BaseAPIClient,
        type: str,
        accountId: str,
        *,  # Force keyword arguments
        status: str = 'PENDING',
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        **kwargs
    ) -> 'Experiment':
        """Create a new experiment.
        
        Args:
            client: The API client
            type: Type of experiment (e.g., 'accuracy', 'consistency')
            accountId: Account context
            status: Initial status (default: 'PENDING')
            scorecardId: Optional scorecard association
            scoreId: Optional score association
            **kwargs: Additional experiment fields
            
        Returns:
            The created Experiment instance
        """
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        input_data = {
            'type': type,
            'accountId': accountId,
            'status': status,
            'createdAt': now,
            'updatedAt': now,
            **kwargs
        }
        
        if scorecardId:
            input_data['scorecardId'] = scorecardId
        if scoreId:
            input_data['scoreId'] = scoreId
        
        mutation = """
        mutation CreateExperiment($input: CreateExperimentInput!) {
            createExperiment(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        logger.info(f"Create experiment response: {result}")
        
        if not result or 'createExperiment' not in result:
            raise Exception(f"Failed to create experiment. Response: {result}")
        
        return cls.from_dict(result['createExperiment'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Experiment':
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
            cost=data.get('cost'),
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

    def update(self, **kwargs) -> None:
        """Update experiment fields in a background thread.
        
        This is a non-blocking operation - the mutation is performed
        in a background thread.
        
        Args:
            **kwargs: Fields to update
        """
        def _update_experiment():
            try:
                # Always update the updatedAt timestamp
                kwargs['updatedAt'] = datetime.now(timezone.utc).isoformat().replace(
                    '+00:00', 'Z'
                )
                
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
                        **kwargs
                    }
                }
                
                self._client.execute(mutation, variables)
                
            except Exception as e:
                logger.error(f"Error updating experiment: {e}")
        
        # Spawn background thread
        thread = Thread(target=_update_experiment, daemon=True)
        thread.start()