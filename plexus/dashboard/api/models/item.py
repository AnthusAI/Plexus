from typing import Optional, Dict, Any, List
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
    createdByType: Optional[str] = None  # "evaluation" or "prediction"
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
        createdByType: Optional[str] = None,
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
        self.createdByType = createdByType
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
            text
            accountId
            evaluationId
            scoreId
            updatedAt
            createdAt
            isEvaluation
            createdByType
            identifiers
            metadata
            attachedFiles
        """

    @classmethod
    def list(
        cls,
        client: _BaseAPIClient,
        filter: Optional[Dict[str, Any]] = None,
        sort: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
        next_token: Optional[str] = None
    ) -> List['Item']:
        """
        List items with optional filtering and sorting.
        
        Args:
            client: The API client to use
            filter: Filter conditions (e.g., {'accountId': {'eq': 'account123'}})
            sort: Sort configuration (e.g., {'createdAt': 'DESC'})
            limit: Maximum number of items to return
            next_token: Pagination token
            
        Returns:
            List of Item objects
        """
        
        # Build the GraphQL query
        query_vars = []
        query_args = []
        variables = {}
        
        if filter:
            query_vars.append("$filter: ModelItemFilterInput")
            query_args.append("filter: $filter")
            variables["filter"] = filter
            
        if limit:
            query_vars.append("$limit: Int")
            query_args.append("limit: $limit")
            variables["limit"] = limit
            
        if next_token:
            query_vars.append("$nextToken: String")
            query_args.append("nextToken: $nextToken")
            variables["nextToken"] = next_token
            
        # Check if we should use a GSI for sorting
        use_gsi = False
        if sort and 'createdAt' in sort and filter and 'accountId' in filter:
            # Use the byAccountIdAndCreatedAt GSI for efficient sorting
            use_gsi = True
            sort_direction = sort.get('createdAt', 'ASC')
            
            # Extract accountId from filter
            account_id_filter = filter.get('accountId', {})
            if 'eq' in account_id_filter:
                account_id = account_id_filter['eq']
                
                query_vars = ["$accountId: String!", "$sortDirection: ModelSortDirection"]
                query_args = ["accountId: $accountId", "sortDirection: $sortDirection"]
                variables = {
                    "accountId": account_id,
                    "sortDirection": sort_direction
                }
                
                if limit:
                    query_vars.append("$limit: Int")
                    query_args.append("limit: $limit")
                    variables["limit"] = limit
                    
                query_name = "listItemByAccountIdAndCreatedAt"
        
        if not use_gsi:
            query_name = "listItems"
            
        # Build the complete query
        query_vars_str = ", ".join(query_vars) if query_vars else ""
        query_args_str = ", ".join(query_args) if query_args else ""
        
        if query_vars_str:
            query_signature = f"({query_vars_str})"
        else:
            query_signature = ""
            
        if query_args_str:
            query_call = f"({query_args_str})"
        else:
            query_call = ""
        
        query = f"""
        query ListItems{query_signature} {{
            {query_name}{query_call} {{
                items {{
                    {cls.fields()}
                }}
                nextToken
            }}
        }}
        """
        
        result = client.execute(query, variables)
        items_data = result.get(query_name, {}).get('items', [])
        
        return [cls.from_dict(item_data, client) for item_data in items_data]

    @classmethod
    def get_by_id(cls, item_id: str, client: _BaseAPIClient) -> Optional['Item']:
        """
        Get a single item by its ID.
        
        Args:
            item_id: The ID of the item to retrieve
            client: The API client to use
            
        Returns:
            Item object if found, None otherwise
        """
        query = f"""
        query GetItem($id: ID!) {{
            getItem(id: $id) {{
                {cls.fields()}
            }}
        }}
        """
        
        result = client.execute(query, {'id': item_id})
        item_data = result.get('getItem')
        
        if item_data:
            return cls.from_dict(item_data, client)
        return None

    @classmethod
    def create(cls, client: _BaseAPIClient, evaluationId: str, text: Optional[str] = None, 
               metadata: Optional[Dict] = None, createdByType: Optional[str] = None, **kwargs) -> 'Item':
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Handle evaluationId requirement - DynamoDB GSI requires non-empty string
        if not evaluationId:
            # For prediction items, use a default evaluation ID
            if kwargs.get('isEvaluation', True) == False:
                evaluationId = 'prediction-default'
            else:
                # For evaluation items, evaluationId should be provided
                raise ValueError("evaluationId is required for evaluation items")
        
        # Determine createdByType if not provided
        if createdByType is None:
            # Default based on isEvaluation flag or evaluationId presence
            if kwargs.get('isEvaluation', True) or (evaluationId and evaluationId != 'prediction-default'):
                createdByType = "evaluation"
            else:
                createdByType = "prediction"
        
        input_data = {
            'evaluationId': evaluationId,
            'createdAt': now,
            'updatedAt': now,
            'createdByType': createdByType,
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
            createdByType=data.get('createdByType'),
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