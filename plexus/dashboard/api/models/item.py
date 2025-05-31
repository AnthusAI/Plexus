from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

@dataclass
class Item(BaseModel):
    evaluationId: str
    createdAt: datetime
    updatedAt: datetime
    accountId: str
    isEvaluation: bool
    text: Optional[str] = None
    metadata: Optional[Dict] = None
    identifiers: Optional[Dict] = None
    externalId: Optional[str] = None
    description: Optional[str] = None
    scoreId: Optional[str] = None
    attachedFiles: Optional[list] = None

    def __init__(
        self,
        id: str,
        evaluationId: str,
        createdAt: datetime,
        updatedAt: datetime,
        accountId: str,
        isEvaluation: bool,
        text: Optional[str] = None,
        metadata: Optional[Dict] = None,
        identifiers: Optional[Dict] = None,
        externalId: Optional[str] = None,
        description: Optional[str] = None,
        scoreId: Optional[str] = None,
        attachedFiles: Optional[list] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.evaluationId = evaluationId
        self.text = text
        self.metadata = metadata
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.identifiers = identifiers
        self.externalId = externalId
        self.description = description
        self.accountId = accountId
        self.scoreId = scoreId
        self.isEvaluation = isEvaluation
        self.attachedFiles = attachedFiles

    @classmethod
    def fields(cls) -> str:
        return """
            id
            externalId
            description
            accountId
            evaluationId
            scoreId
            updatedAt
            createdAt
            isEvaluation
            identifiers
            metadata
            attachedFiles
        """

    @classmethod
    def create(cls, client: _BaseAPIClient, evaluationId: str, text: Optional[str] = None, 
               metadata: Optional[Dict] = None, **kwargs) -> 'Item':
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        input_data = {
            'evaluationId': evaluationId,
            'createdAt': now,
            'updatedAt': now,
            **kwargs
        }
        
        if text is not None:
            input_data['text'] = text
        if metadata is not None:
            input_data['metadata'] = metadata
        
        mutation = """
        mutation CreateItem($input: CreateItemInput!) {
            createItem(input: $input) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createItem'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Item':
        for date_field in ['createdAt', 'updatedAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        return cls(
            id=data['id'],
            evaluationId=data.get('evaluationId', ''),
            createdAt=data.get('createdAt', datetime.now(timezone.utc)),
            updatedAt=data.get('updatedAt', datetime.now(timezone.utc)),
            accountId=data.get('accountId', ''),
            isEvaluation=data.get('isEvaluation', True),
            text=data.get('text'),
            metadata=data.get('metadata'),
            identifiers=data.get('identifiers'),
            externalId=data.get('externalId'),
            description=data.get('description'),
            scoreId=data.get('scoreId'),
            attachedFiles=data.get('attachedFiles'),
            client=client
        )

    def update(self, **kwargs) -> 'Item':
        if 'createdAt' in kwargs:
            raise ValueError("createdAt cannot be modified after creation")
            
        update_data = {
            'updatedAt': datetime.now(timezone.utc).isoformat().replace(
                '+00:00', 'Z'
            ),
            **kwargs
        }
        
        mutation = """
        mutation UpdateItem($input: UpdateItemInput!) {
            updateItem(input: $input) {
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
        return self.from_dict(result['updateItem'], self._client) 