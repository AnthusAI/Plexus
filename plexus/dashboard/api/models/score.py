"""
Score Model - Python representation of the GraphQL Score type.

Represents a scoring method within a scorecard section, tracking:
- Configuration and metadata
- AI model details
- Performance metrics
- Version history
"""

import logging
import yaml
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseModel
from ..client import _BaseAPIClient

logger = logging.getLogger(__name__)

@dataclass
class Score(BaseModel):
    name: str
    key: str
    externalId: str
    type: str
    order: int
    sectionId: str
    accuracy: Optional[float] = None
    version: Optional[str] = None
    aiProvider: Optional[str] = None
    aiModel: Optional[str] = None

    def __init__(
        self,
        id: str,
        name: str,
        key: str,
        externalId: str,
        type: str,
        order: int,
        sectionId: str,
        accuracy: Optional[float] = None,
        version: Optional[str] = None,
        aiProvider: Optional[str] = None,
        aiModel: Optional[str] = None,
        client: Optional[_BaseAPIClient] = None
    ):
        super().__init__(id, client)
        self.name = name
        self.key = key
        self.externalId = externalId
        self.type = type
        self.order = order
        self.sectionId = sectionId
        self.accuracy = accuracy
        self.version = version
        self.aiProvider = aiProvider
        self.aiModel = aiModel

    @classmethod
    def fields(cls) -> str:
        return """
            id
            name
            key
            externalId
            type
            order
            sectionId
            accuracy
            version
            aiProvider
            aiModel
        """

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: _BaseAPIClient) -> 'Score':
        return cls(
            id=data['id'],
            name=data['name'],
            key=data['key'],
            externalId=data['externalId'],
            type=data['type'],
            order=data['order'],
            sectionId=data['sectionId'],
            accuracy=data.get('accuracy'),
            version=data.get('version'),
            aiProvider=data.get('aiProvider'),
            aiModel=data.get('aiModel'),
            client=client
        )

    @classmethod
    def get_by_id(cls, id: str, client: _BaseAPIClient) -> 'Score':
        query = """
        query GetScore($id: ID!) {
            getScore(id: $id) {
                %s
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'id': id})
        if not result or 'getScore' not in result:
            raise Exception(f"Failed to get Score {id}")
            
        return cls.from_dict(result['getScore'], client)

    @classmethod
    def get_by_name(cls, name: str, scorecard_id: str, client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its name"""
        query = """
        query GetScoreByName($name: String!) {
            listScoreByName(name: $name) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'name': name})
        if not result or 'listScoreByName' not in result or not result['listScoreByName']['items']:
            return None
            
        return cls.from_dict(result['listScoreByName']['items'][0], client)

    @classmethod
    def get_by_key(cls, key: str, scorecard_id: str, client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its key"""
        query = """
        query GetScoreByKey($key: String!) {
            listScoreByKey(key: $key) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'key': key})
        if not result or 'listScoreByKey' not in result or not result['listScoreByKey']['items']:
            return None
            
        return cls.from_dict(result['listScoreByKey']['items'][0], client)

    @classmethod
    def get_by_external_id(cls, external_id: str, scorecard_id: str, 
                          client: _BaseAPIClient) -> Optional['Score']:
        """Get a score by its external ID"""
        query = """
        query GetScoreByExternalId($externalId: String!) {
            listScoreByExternalId(externalId: $externalId) {
                items {
                    %s
                }
            }
        }
        """ % cls.fields()
        
        result = client.execute(query, {'externalId': external_id})
        if not result or 'listScoreByExternalId' not in result or not result['listScoreByExternalId']['items']:
            return None
            
        return cls.from_dict(result['listScoreByExternalId']['items'][0], client)

    @classmethod
    def list_by_section_id(cls, section_id: str, client: _BaseAPIClient, 
                          next_token: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Get all scores for a section with pagination support
        
        Returns:
            Dict containing:
                - items: List of Score objects
                - nextToken: Token for next page if more results exist
        """
        query = """
        query ListScoresBySectionId($sectionId: String!, $limit: Int, $nextToken: String) {
            listScoreBySectionId(sectionId: $sectionId, limit: $limit, nextToken: $nextToken) {
                items {
                    %s
                }
                nextToken
            }
        }
        """ % cls.fields()
        
        variables = {
            'sectionId': section_id,
            'limit': limit
        }
        if next_token:
            variables['nextToken'] = next_token
            
        result = client.execute(query, variables)
        if not result or 'listScoreBySectionId' not in result:
            return {'items': [], 'nextToken': None}
            
        list_result = result['listScoreBySectionId']
        return {
            'items': [cls.from_dict(item, client) for item in list_result['items']],
            'nextToken': list_result.get('nextToken')
        }

    def get_configuration(self) -> Optional[Dict[str, Any]]:
        """
        Get the score's configuration from its champion version.
        
        Returns:
            Optional[Dict[str, Any]]: The parsed YAML configuration, or None if not found
        """
        if not self.client:
            raise ValueError("No API client available")

        # First get the champion version ID
        query = """
        query GetScore($id: ID!) {
            getScore(id: $id) {
                championVersionId
            }
        }
        """
        
        result = self.client.execute(query, {'id': self.id})
        if not result or 'getScore' not in result:
            logger.error(f"Failed to get champion version ID for Score {self.id}")
            return None
            
        champion_version_id = result['getScore'].get('championVersionId')
        if not champion_version_id:
            logger.error(f"No champion version found for Score {self.id}")
            return None

        # Then get the version content
        version_query = """
        query GetScoreVersion($id: ID!) {
            getScoreVersion(id: $id) {
                configuration
            }
        }
        """
        
        version_result = self.client.execute(version_query, {'id': champion_version_id})
        if not version_result or 'getScoreVersion' not in version_result:
            logger.error(f"Failed to get version content for version {champion_version_id}")
            return None
            
        config_yaml = version_result['getScoreVersion'].get('configuration')
        if not config_yaml:
            logger.error(f"No configuration found in version {champion_version_id}")
            return None

        try:
            # Parse the YAML content
            return yaml.safe_load(config_yaml)
        except Exception as e:
            logger.error(f"Error parsing YAML configuration for Score {self.id}: {e}")
            return None

    def get_valid_classes(self) -> List[Dict[str, Any]]:
        """
        Get the list of valid classes from the score's configuration.
        
        Looks for a 'classes' key in the score's YAML configuration, where each class
        has at least a 'name' field and may have additional metadata like 'positive'.
        
        Example YAML format:
        ```yaml
        classes:
          - name: Yes
            positive: true
          - name: No
        ```
        
        Returns:
            List[Dict[str, Any]]: List of valid class dictionaries, each containing at least a 'name' key
                                 and any additional metadata from the configuration.
                                 Returns empty list if not found or on error.
        """
        config = self.get_configuration()
        if not config:
            return []

        # Look for classes in the configuration
        classes = config.get('classes', [])
        if not isinstance(classes, list):
            logger.warning(f"classes in configuration for Score {self.id} is not a list")
            return []

        # Validate that each class has a name
        valid_classes = []
        for class_def in classes:
            if isinstance(class_def, dict) and 'name' in class_def:
                valid_classes.append(class_def)
            else:
                logger.warning(f"Invalid class definition in configuration for Score {self.id}: {class_def}")

        return valid_classes

    def get_valid_classes_count(self) -> int:
        """
        Get the number of valid classes from the score's configuration.
        
        This method looks at:
        1. The explicit valid_classes list in the configuration
        2. Any output values specified in conditions that might add additional classes
        
        Returns:
            int: Number of valid classes, defaulting to 2 (binary classification) if not found.
        """
        config = self.get_configuration()
        if not config:
            logger.info(f"No configuration found for Score {self.id}, defaulting to 2 (binary classification)")
            return 2

        # Get base valid classes from configuration
        valid_classes = set()
        
        # Look for valid_classes in the graph nodes
        if 'graph' in config:
            for node in config['graph']:
                if 'valid_classes' in node:
                    valid_classes.update(node['valid_classes'])
                
                # Look for output values in conditions
                if 'conditions' in node:
                    for condition in node['conditions']:
                        if 'output' in condition and 'value' in condition['output']:
                            valid_classes.add(condition['output']['value'])

        if not valid_classes:
            logger.info(f"No valid classes found in configuration for Score {self.id}, defaulting to 2 (binary classification)")
            return 2

        logger.info(f"Found {len(valid_classes)} valid classes in configuration for Score {self.id}: {valid_classes}")
        return len(valid_classes)