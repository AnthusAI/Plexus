"""
Evaluation Model - Python representation of the GraphQL Evaluation type.

This model represents individual Evaluations in the system, tracking:
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
class Evaluation(BaseModel):
    type: str
    accountId: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    parameters: Optional[Dict] = None
    metrics: Optional[Dict] = None
    inferences: Optional[int] = None
    accuracy: Optional[float] = None
    cost: Optional[float] = None
    startedAt: Optional[datetime] = None
    elapsedSeconds: Optional[int] = None
    estimatedRemainingSeconds: Optional[int] = None
    totalItems: Optional[int] = None
    processedItems: Optional[int] = None
    errorMessage: Optional[str] = None
    errorDetails: Optional[Dict] = None
    scorecardId: Optional[str] = None
    scoreId: Optional[str] = None
    confusionMatrix: Optional[Dict] = None
    scoreGoal: Optional[str] = None
    datasetClassDistribution: Optional[Dict] = None
    isDatasetClassDistributionBalanced: Optional[bool] = None
    predictedClassDistribution: Optional[Dict] = None
    isPredictedClassDistributionBalanced: Optional[bool] = None
    taskId: Optional[str] = None

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
        accuracy: Optional[float] = None,
        cost: Optional[float] = None,
        startedAt: Optional[datetime] = None,
        elapsedSeconds: Optional[int] = None,
        estimatedRemainingSeconds: Optional[int] = None,
        totalItems: Optional[int] = None,
        processedItems: Optional[int] = None,
        errorMessage: Optional[str] = None,
        errorDetails: Optional[Dict] = None,
        scorecardId: Optional[str] = None,
        scoreId: Optional[str] = None,
        confusionMatrix: Optional[Dict] = None,
        scoreGoal: Optional[str] = None,
        datasetClassDistribution: Optional[Dict] = None,
        isDatasetClassDistributionBalanced: Optional[bool] = None,
        predictedClassDistribution: Optional[Dict] = None,
        isPredictedClassDistributionBalanced: Optional[bool] = None,
        taskId: Optional[str] = None,
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
        self.accuracy = accuracy
        self.cost = cost
        self.startedAt = startedAt
        self.elapsedSeconds = elapsedSeconds
        self.estimatedRemainingSeconds = estimatedRemainingSeconds
        self.totalItems = totalItems
        self.processedItems = processedItems
        self.errorMessage = errorMessage
        self.errorDetails = errorDetails
        self.scorecardId = scorecardId
        self.scoreId = scoreId
        self.confusionMatrix = confusionMatrix
        self.scoreGoal = scoreGoal
        self.datasetClassDistribution = datasetClassDistribution
        self.isDatasetClassDistributionBalanced = isDatasetClassDistributionBalanced
        self.predictedClassDistribution = predictedClassDistribution
        self.isPredictedClassDistributionBalanced = isPredictedClassDistributionBalanced
        self.taskId = taskId

    @classmethod
    def fields(cls) -> str:
        """Fields to request in queries and mutations"""
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
            accuracy
            cost
            startedAt
            elapsedSeconds
            estimatedRemainingSeconds
            totalItems
            processedItems
            errorMessage
            errorDetails
            scorecardId
            scoreId
            confusionMatrix
            scoreGoal
            datasetClassDistribution
            isDatasetClassDistributionBalanced
            predictedClassDistribution
            isPredictedClassDistributionBalanced
            taskId
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
        taskId: Optional[str] = None,
        **kwargs
    ) -> 'Evaluation':
        """Create a new Evaluation."""
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
        if taskId:
            input_data['taskId'] = taskId
        
        mutation = """
        mutation CreateEvaluation($input: CreateEvaluationInput!) {
            createEvaluation(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        logger.info(f"Create Evaluation response: {result}")
        
        if not result or 'createEvaluation' not in result:
            raise Exception(f"Failed to create Evaluation. Response: {result}")
        
        return cls.from_dict(result['createEvaluation'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Evaluation':
        # Convert string dates to datetime objects
        for date_field in ['createdAt', 'updatedAt', 'startedAt']:
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
            accuracy=data.get('accuracy'),
            cost=data.get('cost'),
            startedAt=data.get('startedAt'),
            elapsedSeconds=data.get('elapsedSeconds'),
            estimatedRemainingSeconds=data.get('estimatedRemainingSeconds'),
            totalItems=data.get('totalItems'),
            processedItems=data.get('processedItems'),
            errorMessage=data.get('errorMessage'),
            errorDetails=data.get('errorDetails'),
            scorecardId=data.get('scorecardId'),
            scoreId=data.get('scoreId'),
            confusionMatrix=data.get('confusionMatrix'),
            scoreGoal=data.get('scoreGoal'),
            datasetClassDistribution=data.get('datasetClassDistribution'),
            isDatasetClassDistributionBalanced=data.get('isDatasetClassDistributionBalanced'),
            predictedClassDistribution=data.get('predictedClassDistribution'),
            isPredictedClassDistributionBalanced=data.get('isPredictedClassDistributionBalanced'),
            taskId=data.get('taskId'),
            client=client
        )

    def update(self, **kwargs) -> None:
        """Update Evaluation fields in a background thread.
        
        This is a non-blocking operation - the mutation is performed
        in a background thread.
        
        Args:
            **kwargs: Fields to update
        """
        def _update_Evaluation():
            try:
                # Always update the updatedAt timestamp
                kwargs['updatedAt'] = datetime.now(timezone.utc).isoformat().replace(
                    '+00:00', 'Z'
                )
                
                mutation = """
                mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                    updateEvaluation(input: $input) {
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
                logger.error(f"Error updating Evaluation: {e}")
        
        # Spawn background thread
        thread = Thread(target=_update_Evaluation, daemon=True)
        thread.start()

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient, include_score_results: bool = False) -> 'Evaluation':
        query = """
        query GetEvaluation($id: ID!) {
            getEvaluation(id: $id) {
                %s
            }
        }
        """ % (cls.fields() + (' scoreResults { items { value confidence metadata correct } }' if include_score_results else ''))
        
        result = client.execute(query, {'id': id})
        if not result or 'getEvaluation' not in result:
            raise Exception(f"Failed to get Evaluation {id}. Response: {result}")
        
        return cls.from_dict(result['getEvaluation'], client)