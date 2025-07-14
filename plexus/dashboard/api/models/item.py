from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timezone
from .base import BaseModel
from ..client import _BaseAPIClient
import json
import logging

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
            # Convert metadata to JSON string like other SDK models
            import json
            input_data['metadata'] = json.dumps(metadata)
        
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
        
        # Convert metadata to JSON string like other SDK models
        if 'metadata' in kwargs and kwargs['metadata'] is not None:
            import json
            kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
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
    
    @classmethod
    def upsert_by_identifiers(
        cls,
        client: _BaseAPIClient,
        account_id: str,
        identifiers: Dict[str, Any],
        external_id: Optional[str] = None,
        description: Optional[str] = None,
        text: Optional[str] = None,
        metadata: Optional[Dict] = None,
        evaluation_id: Optional[str] = None,
        is_evaluation: bool = False,
        debug: bool = False
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Upsert an Item using identifier-based lookup to prevent duplicates.
        
        This method provides the core functionality for preventing duplicate Items
        by using the Identifier table's GSI for efficient lookups.
        
        Args:
            client: PlexusDashboardClient instance
            account_id: The Plexus account ID
            identifiers: Dict containing identifier values like {'formId': '12345', 'reportId': '67890'}
            external_id: Optional external ID for the item
            description: Optional item description
            text: Optional text content
            metadata: Optional metadata dict
            evaluation_id: Optional evaluation ID (defaults to 'prediction-default' for non-evaluation items)
            is_evaluation: Whether this is an evaluation item
            debug: Enable debug logging
            
        Returns:
            Tuple of (item_id, was_created, error_msg)
            - item_id: The ID of the created/updated Item, or None if failed
            - was_created: True if item was created, False if updated
            - error_msg: Error message if operation failed, None if successful
            
        Example:
            identifiers = {'formId': '12345', 'reportId': '67890'}
            item_id, was_created, error = Item.upsert_by_identifiers(
                client=client,
                account_id='account-123',
                identifiers=identifiers,
                external_id='report-67890',
                description='Call transcript',
                text='Full transcript text...'
            )
        """
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            logger = logging.getLogger(__name__)
            logger.debug(f"[ITEM UPSERT] Starting upsert with identifiers: {identifiers}")
        
        if not account_id:
            error_msg = "Missing required account_id parameter"
            if debug:
                logger.error(error_msg)
            return None, False, error_msg
        
        try:
            # Step 1: Look up existing Item using identifiers
            existing_item = cls._lookup_item_by_identifiers(client, account_id, identifiers, debug)
            
            # Step 2: Fallback to external_id lookup if identifier lookup failed
            if not existing_item and external_id:
                if debug:
                    logger.debug(f"[ITEM UPSERT] Identifier lookup failed, trying external_id: {external_id}")
                existing_item = cls._lookup_item_by_external_id(client, account_id, external_id, debug)
            
            # Step 3: Create or update the Item
            if existing_item:
                # Update existing Item
                item_id = existing_item['id']
                if debug:
                    logger.debug(f"[ITEM UPSERT] Updating existing Item: {item_id}")
                
                update_kwargs = {}
                if description:
                    update_kwargs['description'] = description
                if text:
                    update_kwargs['text'] = text
                if metadata:
                    update_kwargs['metadata'] = metadata
                if external_id:
                    update_kwargs['externalId'] = external_id
                
                # Add legacy identifiers format for backwards compatibility
                if identifiers:
                    legacy_identifiers = cls._convert_identifiers_to_legacy_format(identifiers)
                    if legacy_identifiers:
                        update_kwargs['identifiers'] = legacy_identifiers
                
                # Get existing item object and update it
                item_obj = cls.get_by_id(item_id, client)
                if item_obj:
                    updated_item = item_obj.update(**update_kwargs)
                    return updated_item.id, False, None
                else:
                    return None, False, f"Could not retrieve existing Item {item_id} for update"
            
            else:
                # Create new Item
                if debug:
                    logger.debug("[ITEM UPSERT] Creating new Item")
                
                # Set evaluation_id for non-evaluation items
                if not evaluation_id:
                    evaluation_id = 'prediction-default' if not is_evaluation else None
                
                create_kwargs = {
                    'accountId': account_id,
                    'isEvaluation': is_evaluation
                }
                
                if evaluation_id:
                    create_kwargs['evaluationId'] = evaluation_id
                if external_id:
                    create_kwargs['externalId'] = external_id
                if description:
                    create_kwargs['description'] = description
                if text:
                    create_kwargs['text'] = text
                if metadata:
                    create_kwargs['metadata'] = metadata
                
                # Add legacy identifiers format for backwards compatibility
                if identifiers:
                    legacy_identifiers = cls._convert_identifiers_to_legacy_format(identifiers)
                    if legacy_identifiers:
                        create_kwargs['identifiers'] = legacy_identifiers
                
                # Create the Item - evaluationId, text, and metadata are positional/named parameters
                # Remove these from kwargs since they're handled separately
                create_kwargs_cleaned = {k: v for k, v in create_kwargs.items() 
                                       if k not in ['evaluationId', 'text', 'metadata']}
                
                new_item = cls.create(
                    client=client,
                    evaluationId=evaluation_id or 'prediction-default',
                    text=text,
                    metadata=metadata,
                    **create_kwargs_cleaned
                )
                
                # Create separate Identifier records for GSI-based lookups
                if identifiers:
                    cls._create_identifier_records(client, new_item.id, account_id, identifiers, debug)
                
                return new_item.id, True, None
        
        except Exception as e:
            error_msg = f"Exception during Item upsert: {str(e)}"
            if debug:
                logger.exception(error_msg)
            return None, False, error_msg
    
    @classmethod
    def _lookup_item_by_identifiers(
        cls,
        client: _BaseAPIClient,
        account_id: str,
        identifiers: Dict[str, Any],
        debug: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Look up an Item by its identifiers using the Identifier table's GSI.
        
        Args:
            client: PlexusDashboardClient instance
            account_id: The account ID
            identifiers: Dict containing identifier values
            debug: Enable debug logging
            
        Returns:
            The Item object if found, None otherwise
        """
        if not identifiers or not account_id:
            return None
        
        # Import here to avoid circular import
        from .identifier import Identifier
        
        # Try different identifier values in priority order (reportId first as most unique)
        identifier_values_to_try = []
        if isinstance(identifiers, dict):
            # Map input keys to their actual stored names and extract values
            key_mapping = {
                'reportId': 'report ID',
                'formId': 'form ID', 
                'sessionId': 'session ID',
                'ccId': 'call criteria ID'
            }
            
            for key in ['reportId', 'formId', 'sessionId', 'ccId']:
                if key in identifiers and identifiers[key]:
                    identifier_values_to_try.append(str(identifiers[key]))
            
            # Also try direct stored name lookups for backwards compatibility
            for stored_name in ['report ID', 'form ID', 'session ID', 'call criteria ID']:
                if stored_name in identifiers and identifiers[stored_name]:
                    identifier_values_to_try.append(str(identifiers[stored_name]))
        
        if not identifier_values_to_try:
            return None
        
        try:
            # Use the Identifier model's GSI-based lookup
            for identifier_value in identifier_values_to_try:
                if debug:
                    logger = logging.getLogger(__name__)
                    logger.info(f"[IDENTIFIER LOOKUP] Searching for: {identifier_value}")
                
                identifier = Identifier.find_by_value(identifier_value, account_id, client)
                if identifier:
                    if debug:
                        logger.info(f"[IDENTIFIER LOOKUP] Found identifier: itemId={identifier.itemId} (type: {type(identifier.itemId)}), name={identifier.name}, value={identifier.value}")
                    
                    # Found identifier, now get the associated Item
                    try:
                        # Validate and fix itemId before calling get_by_id
                        item_id = identifier.itemId
                        if not isinstance(item_id, str) or not item_id.strip():
                            if debug:
                                logger.warning(f"[IDENTIFIER LOOKUP] Invalid itemId detected: {repr(item_id)} (type: {type(item_id)}), skipping this identifier")
                            continue  # Skip this identifier and try the next one
                        
                        item = cls.get_by_id(item_id, client)
                        if item:
                            if debug:
                                logger.info(f"[IDENTIFIER LOOKUP] Found Item via identifier: {item.id}")
                            return {
                                'id': item.id,
                                'externalId': item.externalId,
                                'description': item.description,
                                'accountId': item.accountId,
                                'identifiers': item.identifiers,
                                'text': item.text
                            }
                    except Exception as get_by_id_error:
                        if debug:
                            logger.error(f"[IDENTIFIER LOOKUP] get_by_id failed for itemId={identifier.itemId}: {get_by_id_error}")
                        # Continue to try next identifier value
            
            if debug:
                logger = logging.getLogger(__name__)
                logger.info(f"[IDENTIFIER LOOKUP] No Item found for identifier values: {identifier_values_to_try}")
            return None
            
        except Exception as e:
            if debug:
                logger = logging.getLogger(__name__)
                logger.error(f"Error in identifier lookup: {e}")
            return None
    
    @classmethod
    def _lookup_item_by_external_id(
        cls,
        client: _BaseAPIClient,
        account_id: str,
        external_id: str,
        debug: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Look up an Item by its externalId within an account (fallback method).
        
        Args:
            client: PlexusDashboardClient instance
            account_id: The account ID
            external_id: The external ID to search for
            debug: Enable debug logging
            
        Returns:
            The Item object if found, None otherwise
        """
        if not external_id or not account_id:
            return None
        
        try:
            # Use the existing list method with filtering
            items = cls.list(
                client=client,
                filter={
                    'and': [
                        {'accountId': {'eq': account_id}},
                        {'externalId': {'eq': external_id}}
                    ]
                },
                limit=1
            )
            
            if items:
                item = items[0]
                if debug:
                    logger = logging.getLogger(__name__)
                    logger.debug(f"[EXTERNAL_ID LOOKUP] Found Item: {item.id}")
                return {
                    'id': item.id,
                    'externalId': item.externalId,
                    'description': item.description,
                    'accountId': item.accountId,
                    'identifiers': item.identifiers,
                    'text': item.text
                }
            
            if debug:
                logger = logging.getLogger(__name__)
                logger.debug(f"[EXTERNAL_ID LOOKUP] No Item found with externalId: {external_id}")
            return None
            
        except Exception as e:
            if debug:
                logger = logging.getLogger(__name__)
                logger.error(f"Error in external_id lookup: {e}")
            return None
    
    @classmethod
    def _create_identifier_records(
        cls,
        client: _BaseAPIClient,
        item_id: str,
        account_id: str,
        identifiers: Dict[str, Any],
        debug: bool = False
    ) -> List[str]:
        """
        Create separate Identifier records for an Item.
        
        Args:
            client: PlexusDashboardClient instance
            item_id: The Item's ID
            account_id: The account ID
            identifiers: Dict containing identifier values
            debug: Enable debug logging
            
        Returns:
            List of created identifier composite IDs
        """
        if not identifiers or not item_id or not account_id:
            return []
        
        # Import here to avoid circular import
        from .identifier import Identifier
        
        created_identifiers = []
        
        try:
            if isinstance(identifiers, dict):
                # Create identifiers in a consistent order with proper names
                identifier_mapping = {
                    'formId': 'Form',
                    'reportId': 'Report',
                    'sessionId': 'Session',
                    'ccId': 'CC ID'
                }
                
                position = 1
                for key, name in identifier_mapping.items():
                    if key in identifiers and identifiers[key]:
                        value = str(identifiers[key])
                        url = None
                        
                        # Add URL for form IDs
                        if key == 'formId':
                            url = f"https://app.callcriteria.com/r/{value}"
                        
                        # Create the identifier using the Identifier model
                        identifier = Identifier.create(
                            client=client,
                            itemId=item_id,
                            name=name,
                            value=value,
                            accountId=account_id,
                            url=url,
                            position=position
                        )
                        
                        created_identifiers.append(f"{item_id}#{name}#{value}")
                        
                        if debug:
                            logger = logging.getLogger(__name__)
                            logger.debug(f"[CREATE IDENTIFIER] Created {name} identifier: {value}")
                        
                        position += 1
            
            if debug:
                logger = logging.getLogger(__name__)
                logger.debug(f"[CREATE IDENTIFIER] Created {len(created_identifiers)} identifier records")
            
            return created_identifiers
            
        except Exception as e:
            if debug:
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating identifier records: {e}")
            return []
    
    @classmethod
    def _convert_identifiers_to_legacy_format(cls, identifiers: Dict[str, Any]) -> Optional[str]:
        """
        Convert identifiers dict to legacy JSON format for backwards compatibility.
        
        Args:
            identifiers: Modern identifiers dict
            
        Returns:
            JSON string in legacy format, or None if conversion fails
        """
        try:
            legacy_identifiers = []
            if isinstance(identifiers, dict):
                for key, value in identifiers.items():
                    if value:
                        if key == 'formId':
                            legacy_identifiers.append({
                                "name": "form ID", 
                                "id": str(value),
                                "url": f"https://app.callcriteria.com/r/{value}"
                            })
                        elif key == 'reportId':
                            legacy_identifiers.append({"name": "report ID", "id": str(value)})
                        elif key == 'sessionId':
                            legacy_identifiers.append({"name": "session ID", "id": str(value)})
                        elif key == 'ccId':
                            legacy_identifiers.append({"name": "CC ID", "id": str(value)})
            
            return json.dumps(legacy_identifiers) if legacy_identifiers else None
        except Exception:
            return None
    
    @classmethod
    def find_by_identifier(
        cls,
        client: _BaseAPIClient,
        account_id: str,
        identifier_key: str,
        identifier_value: str,
        debug: bool = False
    ) -> Optional['Item']:
        """
        Find an Item using a specific identifier (reportId, formId, sessionId, etc.).
        
        This method provides a general-purpose way to find Items by any identifier type,
        not limited to cache-specific use cases.
        
        Args:
            client: API client for database operations
            account_id: Account ID to scope the search
            identifier_key: The type of identifier (e.g., 'reportId', 'formId', 'sessionId')
            identifier_value: The value to search for
            debug: Enable debug logging
            
        Returns:
            Item object if found, None otherwise
            
        Example:
            # Find item by report ID
            item = Item.find_by_identifier(client, account_id, 'reportId', '277307013')
            
            # Find item by form ID  
            item = Item.find_by_identifier(client, account_id, 'formId', '12345')
        """
        if debug:
            logger = logging.getLogger(__name__)
            logger.debug(f"[FIND BY IDENTIFIER] Searching for {identifier_key}={identifier_value} in account {account_id}")
        
        try:
            # Use the existing identifier lookup mechanism from upsert_by_identifiers
            item_dict = cls._lookup_item_by_identifiers(
                client=client,
                account_id=account_id,
                identifiers={identifier_key: identifier_value},
                debug=debug
            )
            
            if item_dict:
                if debug:
                    logger.info(f"[FIND BY IDENTIFIER] Found item dict: {item_dict}")
                
                # Extract the item ID from the returned dictionary
                item_id = item_dict['id']
                
                # Get the full Item object
                item = cls.get_by_id(item_id, client)
                return item
            else:
                if debug:
                    logger.info(f"[FIND BY IDENTIFIER] No item found for {identifier_key}={identifier_value}")
                return None
                
        except Exception as e:
            if debug:
                logger = logging.getLogger(__name__)
                logger.error(f"[FIND BY IDENTIFIER] Error searching for {identifier_key}={identifier_value}: {e}")
            return None 