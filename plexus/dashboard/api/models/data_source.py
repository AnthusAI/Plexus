from __future__ import annotations
import os
import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from plexus.dashboard.api.models.base import BaseModel
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account

if TYPE_CHECKING:
    from plexus.dashboard.api.models.data_set import DataSet

class DataSource(BaseModel):
    _model_name = "DataSource"

    def __init__(
        self,
        id: str,
        name: str,
        key: Optional[str] = None,
        description: Optional[str] = None,
        yamlConfiguration: Optional[str] = None,
        attachedFiles: Optional[List[str]] = None,
        createdAt: Optional[str] = None,
        updatedAt: Optional[str] = None,
        owner: Optional[str] = None,
        accountId: Optional[str] = None,
        currentVersionId: Optional[str] = None,
        scoreId: Optional[str] = None,
        scorecardId: Optional[str] = None,
        dataSets: Optional[List[DataSet]] = None,
        client: Optional[PlexusDashboardClient] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.key = key
        self.description = description
        self.yamlConfiguration = yamlConfiguration
        self.attachedFiles = attachedFiles
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.owner = owner
        self.accountId = accountId
        self.currentVersionId = currentVersionId
        self.scoreId = scoreId
        self.scorecardId = scorecardId
        self.dataSets = dataSets

    @classmethod
    def fields(cls) -> str:
        """Return the GraphQL fields to query for this model"""
        return """
            id
            name
            key
            description
            yamlConfiguration
            attachedFiles
            createdAt
            updatedAt
            accountId
            currentVersionId
            scoreId
            scorecardId
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: PlexusDashboardClient) -> DataSource:
        """Create a DataSource instance from a dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            key=data.get('key'),
            description=data.get('description'),
            yamlConfiguration=data.get('yamlConfiguration'),
            attachedFiles=data.get('attachedFiles'),
            createdAt=data.get('createdAt'),
            updatedAt=data.get('updatedAt'),
            owner=data.get('accountId'),  # Map accountId to owner for backward compatibility
            accountId=data.get('accountId'),  # Also store as accountId
            currentVersionId=data.get('currentVersionId'),
            scoreId=data.get('scoreId'),
            scorecardId=data.get('scorecardId'),
            client=client
        )

    @classmethod
    async def get(cls, client: PlexusDashboardClient, id: str) -> Optional[DataSource]:
        """Fetch a DataSource by its ID."""
        try:
            return cls.get_by_id(id, client)
        except ValueError:
            return None

    @classmethod
    async def list(cls, client: PlexusDashboardClient, filter: Optional[Dict] = None) -> List[DataSource]:
        """List DataSources with optional filtering."""
        query = f"""
            query ListDataSources($filter: ModelDataSourceFilterInput) {{
                listDataSources(filter: $filter) {{
                    items {{
                        {cls.fields()}
                    }}
                }}
            }}
        """
        variables = {"filter": filter} if filter else {}
        response = client.execute(query, variables)
        items = response.get('listDataSources', {}).get('items', [])
        return [cls.from_dict(item, client) for item in items]

    @classmethod
    async def list_by_key(cls, client: PlexusDashboardClient, key: str) -> List[DataSource]:
        """Fetch DataSources by key using the GSI."""
        logging.debug(f"list_by_key called with key: {key}")
        
        account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')
        logging.debug(f"PLEXUS_ACCOUNT_KEY: {account_key}")
        if not account_key:
            logging.error("PLEXUS_ACCOUNT_KEY not found in environment")
            return []
            
        account = Account.get_by_key(account_key, client)
        if not account:
            logging.error(f"Account not found for key: {account_key}")
            return []
        logging.debug(f"Found account: {account.id} ({account.name})")

        # After Stage 1 deployment, we'll use the account-isolated query
        # For now, use the non-isolated query until Stage 1 is deployed
        query = f"""
            query ListDataSourceByKey($key: String!) {{
                listDataSourceByKey(key: $key) {{
                    items {{
                        {cls.fields()}
                    }}
                }}
            }}
        """
        variables = {"key": key}
        
        logging.debug(f"Executing GraphQL query: {query}")
        logging.debug(f"Query variables: {variables}")
        
        response = client.execute(query, variables)
        logging.debug(f"GraphQL response: {response}")
        
        items = response.get('listDataSourceByKey', {}).get('items', [])
        logging.debug(f"Found {len(items)} items")
        
        # Filter by account ID since the query is not account-isolated yet
        account_filtered_items = [item for item in items if item.get('accountId') == account.id]
        logging.debug(f"Found {len(account_filtered_items)} items after account filtering")
        
        return [cls.from_dict(item, client) for item in account_filtered_items]

    @classmethod
    async def list_by_name(cls, client: PlexusDashboardClient, name: str) -> List[DataSource]:
        """Fetch DataSources by name using the GSI."""
        logging.debug(f"list_by_name called with name: {name}")
        
        account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')
        logging.debug(f"PLEXUS_ACCOUNT_KEY: {account_key}")
        if not account_key:
            logging.error("PLEXUS_ACCOUNT_KEY not found in environment")
            return []
            
        account = Account.get_by_key(account_key, client)
        if not account:
            logging.error(f"Account not found for key: {account_key}")
            return []
        logging.debug(f"Found account: {account.id} ({account.name})")

        # Use the non-isolated query since schema was reverted
        query = f"""
            query ListDataSourceByName($name: String!) {{
                listDataSourceByName(name: $name) {{
                    items {{
                        {cls.fields()}
                    }}
                }}
            }}
        """
        variables = {"name": name}
        
        logging.debug(f"Executing GraphQL query: {query}")
        logging.debug(f"Query variables: {variables}")
        
        response = client.execute(query, variables)
        logging.debug(f"GraphQL response: {response}")
        
        items = response.get('listDataSourceByName', {}).get('items', [])
        logging.debug(f"Found {len(items)} items")
        
        # Filter by account ID since the query is not account-isolated
        account_filtered_items = [item for item in items if item.get('accountId') == account.id]
        logging.debug(f"Found {len(account_filtered_items)} items after account filtering")
        
        return [cls.from_dict(item, client) for item in account_filtered_items]

    @classmethod
    async def get_by_name(cls, name: str, client: PlexusDashboardClient) -> Optional[DataSource]:
        """Fetch a DataSource by its name."""
        items = await cls.list(client, filter={"name": {"eq": name}})
        return items[0] if items else None 