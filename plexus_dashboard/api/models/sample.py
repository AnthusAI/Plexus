from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

@dataclass
class Sample(BaseModel):
    """
    Sample Model - Python representation of the GraphQL Sample type.

    Represents individual samples within an evaluation, tracking:
    - Raw data being evaluated
    - Predictions and ground truth
    - Correctness of predictions
    - Creation and update timestamps

    This model is typically used in conjunction with Evaluation for:
    - Recording individual test cases
    - Tracking prediction accuracy
    - Building confusion matrices
    - Training data management

    Unlike Evaluation, Sample uses synchronous mutations as it's
    typically used in high-volume batch operations where immediate
    feedback is needed.

    Example Usage:
        # Create a new sample
        sample = Sample.create(
            client=client,
            evaluationId="exp-123",
            data={"text": "example content"},
            prediction="positive",
            groundTruth="positive"
        )
        
        # Update prediction
        updated = sample.update(
            prediction="negative",
            isCorrect=False
        )
    """
    evaluationId: str
    data: Dict
    createdAt: datetime
    updatedAt: datetime
    prediction: Optional[str] = None
    groundTruth: Optional[str] = None
    isCorrect: Optional[bool] = None

    def __init__(
        self,
        id: str,
        evaluationId: str,
        data: Dict,
        createdAt: datetime,
        updatedAt: datetime,
        prediction: Optional[str] = None,
        groundTruth: Optional[str] = None,
        isCorrect: Optional[bool] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.evaluationId = evaluationId
        self.data = data
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.prediction = prediction
        self.groundTruth = groundTruth
        self.isCorrect = isCorrect

    @classmethod
    def fields(cls) -> str:
        return """
            id
            evaluationId
            data
            createdAt
            updatedAt
            prediction
            groundTruth
            isCorrect
        """

    @classmethod
    def create(cls, client: _BaseAPIClient, evaluationId: str, data: Dict, 
               **kwargs) -> 'Sample':
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        input_data = {
            'evaluationId': evaluationId,
            'data': data,
            'createdAt': now,
            'updatedAt': now,
            **kwargs
        }
        
        mutation = """
        mutation CreateSample($input: CreateSampleInput!) {
            createSample(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createSample'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Sample':
        for date_field in ['createdAt', 'updatedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        return cls(
            id=data['id'],
            evaluationId=data['evaluationId'],
            data=data['data'],
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt'],
            prediction=data.get('prediction'),
            groundTruth=data.get('groundTruth'),
            isCorrect=data.get('isCorrect'),
            client=client
        )

    def update(self, **kwargs) -> 'Sample':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified after creation")
            
        update_data = {
            'updatedAt': datetime.now(timezone.utc).isoformat().replace(
                '+00:00', 'Z'
            ),
            **kwargs
        }
        
        mutation = """
        mutation UpdateSample($input: UpdateSampleInput!) {
            updateSample(input: $input) {
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
        return self.from_dict(result['updateSample'], self._client) 