#!/usr/bin/env python3
"""
ProcedureTemplate Model - Represents procedure configuration templates.

This model stores the YAML templates that define how procedures work,
including state machine configurations for hypothesis generation.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .base import BaseModel
from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class ProcedureTemplate(BaseModel):
    """
    NOTE: This model now queries the Procedure table with isTemplate=true.
    ProcedureTemplate table was removed to save CloudFormation resources.
    Templates are now Procedures with isTemplate=true.
    """
    id: str
    name: str
    description: Optional[str]
    template: str  # The YAML template content (stored as 'code' in Procedure table)
    version: str  # Template version (e.g., "1.0", "2.1")
    isDefault: Optional[bool]  # Whether this is the default template
    category: Optional[str]  # e.g., "hypothesis_generation", "beam_search"
    accountId: str
    createdAt: datetime
    updatedAt: datetime
    client: '_BaseAPIClient' = None
    
    @classmethod
    def fields(cls) -> str:
        """Return GraphQL fields for this model (queries Procedure table)."""
        return """
        id
        name
        description
        code
        version
        isDefault
        category
        accountId
        createdAt
        updatedAt
        isTemplate
        """
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'ProcedureTemplate':
        """Create a ProcedureTemplate instance from GraphQL response data.

        NOTE: 'code' field from Procedure table is mapped to 'template' field here.
        """

        # Parse datetime fields
        created_at = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        updated_at = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))

        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description'),
            template=data.get('code', ''),  # 'code' field in Procedure maps to 'template' here
            version=data.get('version', '1.0'),
            isDefault=data.get('isDefault'),
            category=data.get('category'),
            accountId=data['accountId'],
            createdAt=created_at,
            updatedAt=updated_at,
            client=client
        )
    
    @classmethod
    def create(
        cls,
        client: '_BaseAPIClient',
        name: str,
        template: str,
        version: str,
        accountId: str,
        description: Optional[str] = None,
        isDefault: Optional[bool] = None,
        category: Optional[str] = None
    ) -> 'ProcedureTemplate':
        """Create a new procedure template.
        
        Args:
            client: The API client
            name: Template name
            template: YAML template content
            version: Template version
            accountId: Account ID
            description: Optional template description
            isDefault: Whether this is the default template
            category: Template category
            
        Returns:
            The created ProcedureTemplate instance
        """
        logger.debug(f"Creating procedure template '{name}' version '{version}'")
        
        input_data = {
            'name': name,
            'code': template,  # 'template' parameter maps to 'code' field in Procedure
            'version': version,
            'accountId': accountId,
            'isTemplate': True  # Mark this as a template
        }

        if description is not None:
            input_data['description'] = description
        if isDefault is not None:
            input_data['isDefault'] = isDefault
        if category is not None:
            input_data['category'] = category

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
    def get_default_for_account(cls, account_id: str, client: '_BaseAPIClient', category: str = "hypothesis_generation") -> Optional['ProcedureTemplate']:
        """Get the default procedure template for an account.
        
        Args:
            account_id: The account ID
            client: The API client
            category: Template category (defaults to "hypothesis_generation")
            
        Returns:
            The default ProcedureTemplate, or None if not found
        """
        try:
            query = """
            query ListProceduresByAccount($accountId: String!) {
                listProcedureByAccountIdAndUpdatedAt(accountId: $accountId) {
                    items {
                        %s
                    }
                }
            }
            """ % cls.fields()

            result = client.execute(query, {
                'accountId': account_id
            })

            items = result.get('listProcedureByAccountIdAndUpdatedAt', {}).get('items', [])

            # Filter for templates only (isTemplate=true)
            items = [item for item in items if item.get('isTemplate') == True]
            
            # Find the default template for this category
            for item in items:
                if item.get('isDefault') and item.get('category') == category:
                    return cls.from_dict(item, client)
            
            # If no default found, return the most recent template in this category
            category_templates = [item for item in items if item.get('category') == category]
            if category_templates:
                # Sort by updatedAt and return the most recent
                category_templates.sort(key=lambda x: x['updatedAt'], reverse=True)
                return cls.from_dict(category_templates[0], client)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting default template for account {account_id}: {e}")
            return None
    
    @classmethod
    def list_by_account(cls, account_id: str, client: '_BaseAPIClient', limit: int = 100) -> List['ProcedureTemplate']:
        """Get all procedure templates for an account.
        
        Args:
            account_id: The account ID
            client: The API client
            limit: Maximum number of templates to return
            
        Returns:
            List of ProcedureTemplate instances
        """
        try:
            query = """
            query ListProceduresByAccount($accountId: String!, $limit: Int) {
                listProcedureByAccountIdAndUpdatedAt(accountId: $accountId, limit: $limit) {
                    items {
                        %s
                    }
                }
            }
            """ % cls.fields()

            result = client.execute(query, {
                'accountId': account_id,
                'limit': limit
            })

            items = result.get('listProcedureByAccountIdAndUpdatedAt', {}).get('items', [])

            # Filter for templates only (isTemplate=true)
            items = [item for item in items if item.get('isTemplate') == True]
            return [cls.from_dict(item, client) for item in items]
            
        except Exception as e:
            logger.error(f"Error listing templates for account {account_id}: {e}")
            return []
    
    def get_template_content(self) -> str:
        """Get the YAML template content."""
        return self.template
    
    def update_template(self, template: str, version: Optional[str] = None) -> 'ProcedureTemplate':
        """Update the template content and optionally the version.
        
        Args:
            template: New YAML template content
            version: Optional new version string
            
        Returns:
            Updated ProcedureTemplate instance
        """
        if not self._client:
            raise ValueError("Cannot update template without client")
        
        input_data = {
            'id': self.id,
            'code': template  # 'template' parameter maps to 'code' field
        }

        if version is not None:
            input_data['version'] = version

        mutation = """
        mutation UpdateProcedure($input: UpdateProcedureInput!) {
            updateProcedure(input: $input) {
                %s
            }
        }
        """ % self.fields()

        result = self._client.execute(mutation, {'input': input_data})
        return self.from_dict(result['updateProcedure'], self._client)



