"""
GraphQL API Client - Handles authentication and API communication.

This client uses API key authentication to communicate with the AppSync GraphQL API.
It's configured through environment variables:
- PLEXUS_API_URL: The AppSync API endpoint
- PLEXUS_API_KEY: The API key for authentication

The client provides a simple interface for executing GraphQL queries and mutations,
handling:
- Authentication headers
- Request retries
- Error handling
- Response parsing
"""

import os
from typing import Optional, Dict, Any
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.exceptions import TransportQueryError

class PlexusAPIClient:
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.api_url = api_url or os.environ.get('PLEXUS_API_URL')
        self.api_key = api_key or os.environ.get('PLEXUS_API_KEY')
        
        if not all([self.api_url, self.api_key]):
            raise ValueError("Missing required API URL or API key")
            
        # Set up GQL client with API key authentication
        transport = RequestsHTTPTransport(
            url=self.api_url,
            headers={
                'x-api-key': self.api_key,
                'Content-Type': 'application/json',
            },
            verify=True,
            retries=3,
        )
        
        self.client = Client(
            transport=transport,
            fetch_schema_from_transport=False
        )
    
    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            return self.client.execute(gql(query), variable_values=variables)
        except TransportQueryError as e:
            raise Exception(f"GraphQL query failed: {str(e)}")