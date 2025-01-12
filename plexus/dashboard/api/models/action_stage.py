from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient

@dataclass
class ActionStage(BaseModel):
    actionId: str
    name: str
    order: int
    status: str
    statusMessage: Optional[str] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    estimatedCompletionAt: Optional[datetime] = None
    processedItems: Optional[int] = None
    totalItems: Optional[int] = None

    def __init__(
        self,
        id: str,
        actionId: str,
        name: str,
        order: int,
        status: str,
        statusMessage: Optional[str] = None,
        startedAt: Optional[datetime] = None,
        completedAt: Optional[datetime] = None,
        estimatedCompletionAt: Optional[datetime] = None,
        processedItems: Optional[int] = None,
        totalItems: Optional[int] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.actionId = actionId
        self.name = name
        self.order = order
        self.status = status
        self.statusMessage = statusMessage
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.estimatedCompletionAt = estimatedCompletionAt
        self.processedItems = processedItems
        self.totalItems = totalItems

    @classmethod
    def fields(cls) -> str:
        return """
            id
            actionId
            name
            order
            status
            statusMessage
            startedAt
            completedAt
            estimatedCompletionAt
            processedItems
            totalItems
        """

    @classmethod
    def create(
        cls,
        client: _BaseAPIClient,
        actionId: str,
        name: str,
        order: int,
        status: str,
        statusMessage: Optional[str] = None,
        **kwargs
    ) -> 'ActionStage':
        input_data = {
            'actionId': actionId,
            'name': name,
            'order': order,
            'status': status
        }

        if statusMessage:
            input_data['statusMessage'] = statusMessage

        optional_fields = [
            'startedAt', 'completedAt', 'estimatedCompletionAt',
            'processedItems', 'totalItems'
        ]
        for field in optional_fields:
            if field in kwargs:
                input_data[field] = kwargs[field]

        mutation = """
        mutation CreateActionStage($input: CreateActionStageInput!) {
            createActionStage(input: $input) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(mutation, {'input': input_data})
        return cls.from_dict(result['createActionStage'], client)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'ActionStage':
        # Convert datetime fields
        for date_field in ['startedAt', 'completedAt', 'estimatedCompletionAt']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace('Z', '+00:00')
                )

        # Extract required fields first
        id = data.pop('id')
        actionId = data.pop('actionId')
        name = data.pop('name')
        order = data.pop('order')
        status = data.pop('status')

        # Create instance with required fields
        return cls(
            id=id,
            actionId=actionId,
            name=name,
            order=order,
            status=status,
            client=client,
            **data  # Pass remaining fields as kwargs
        )

    def update(self, **kwargs) -> 'ActionStage':
        # Convert datetime fields to ISO format strings
        for field, value in kwargs.items():
            if isinstance(value, datetime):
                kwargs[field] = value.isoformat().replace('+00:00', 'Z')

        mutation = """
        mutation UpdateActionStage($input: UpdateActionStageInput!) {
            updateActionStage(input: $input) {
                %s
            }
        }
        """ % self.fields()

        query = """
        query GetActionStage($id: ID!) {
            getActionStage(id: $id) {
                actionId
                name
                order
                status
            }
        }
        """
        result = self._client.execute(query, {'id': self.id})
        current_data = result.get('getActionStage', {})

        # If we don't have current data, use the instance's data
        input_data = {
            'id': self.id,
            'actionId': current_data.get('actionId', self.actionId),
            'name': current_data.get('name', self.name),
            'order': current_data.get('order', self.order),
            'status': current_data.get('status', self.status),
            **kwargs
        }

        result = self._client.execute(mutation, {'input': input_data})
        return self.from_dict(result['updateActionStage'], self._client)

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'ActionStage':
        query = """
        query GetActionStage($id: ID!) {
            getActionStage(id: $id) {
                %s
            }
        }
        """ % cls.fields()

        result = client.execute(query, {'id': id})
        if not result or 'getActionStage' not in result:
            raise Exception(f"Failed to get ActionStage {id}")

        return cls.from_dict(result['getActionStage'], client) 