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
from pathlib import Path
from .base import BaseModel
from .scorecard import Scorecard
from ..client import _BaseAPIClient
from plexus.cli.shared import get_score_yaml_path

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
        if not self._client:
            raise ValueError("No API client available")

        # First get the champion version ID
        query = """
        query GetScore($id: ID!) {
            getScore(id: $id) {
                championVersionId
            }
        }
        """
        
        result = self._client.execute(query, {'id': self.id})
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
        
        version_result = self._client.execute(version_query, {'id': champion_version_id})
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

    def get_local_configuration_path(self, scorecard_name: Optional[str] = None) -> Path:
        """
        Get the local YAML file path for this score's configuration.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Path: Path to the local YAML configuration file
        """
        if not scorecard_name:
            if not self._client:
                raise ValueError("No API client available to lookup scorecard name")
            
            # Get the section to find the scorecard
            section_query = """
            query GetSection($id: ID!) {
                getSection(id: $id) {
                    scorecardId
                }
            }
            """
            
            section_result = self._client.execute(section_query, {'id': self.sectionId})
            if not section_result or 'getSection' not in section_result:
                raise ValueError(f"Could not find section {self.sectionId}")
                
            scorecard_id = section_result['getSection']['scorecardId']
            scorecard = Scorecard.get_by_id(scorecard_id, self._client)
            scorecard_name = scorecard.name
            
        return get_score_yaml_path(scorecard_name, self.name)

    def pull_configuration(self, scorecard_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Pull the champion version YAML configuration to a local file.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Dict containing:
                - success: bool
                - file_path: str (path where file was saved)
                - version_id: str (the champion version ID that was pulled)
                - message: str (success/error message)
        """
        if not self._client:
            return {
                "success": False,
                "error": "No API client available",
                "message": "Score instance must have an API client to pull configuration"
            }

        try:
            # Get the champion version ID
            query = """
            query GetScore($id: ID!) {
                getScore(id: $id) {
                    championVersionId
                }
            }
            """
            
            result = self._client.execute(query, {'id': self.id})
            if not result or 'getScore' not in result:
                return {
                    "success": False,
                    "error": "API_ERROR",
                    "message": f"Failed to get champion version ID for Score {self.id}"
                }
                
            champion_version_id = result['getScore'].get('championVersionId')
            if not champion_version_id:
                return {
                    "success": False,
                    "error": "NO_CHAMPION_VERSION",
                    "message": f"No champion version found for Score {self.name}"
                }

            # Get the version content
            version_query = """
            query GetScoreVersion($id: ID!) {
                getScoreVersion(id: $id) {
                    configuration
                    createdAt
                    updatedAt
                    note
                }
            }
            """
            
            version_result = self._client.execute(version_query, {'id': champion_version_id})
            if not version_result or 'getScoreVersion' not in version_result:
                return {
                    "success": False,
                    "error": "VERSION_NOT_FOUND",
                    "message": f"Failed to get version content for version {champion_version_id}"
                }
                
            version_data = version_result['getScoreVersion']
            config_yaml = version_data.get('configuration')
            if not config_yaml:
                return {
                    "success": False,
                    "error": "NO_CONFIGURATION",
                    "message": f"No configuration found in version {champion_version_id}"
                }

            # Get the local file path
            yaml_path = self.get_local_configuration_path(scorecard_name)
            
            # Create directory if it doesn't exist
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file with version metadata as comments
            with open(yaml_path, 'w') as f:
                f.write(f"# Pulled from Plexus API\n")
                f.write(f"# Score: {self.name}\n")
                f.write(f"# Champion Version ID: {champion_version_id}\n")
                f.write(f"# Created: {version_data.get('createdAt', 'Unknown')}\n")
                f.write(f"# Updated: {version_data.get('updatedAt', 'Unknown')}\n")
                if version_data.get('note'):
                    f.write(f"# Note: {version_data['note']}\n")
                f.write(f"#\n")
                f.write(config_yaml)
            
            logger.info(f"Successfully pulled configuration for Score {self.name} to {yaml_path}")
            
            return {
                "success": True,
                "file_path": str(yaml_path),
                "version_id": champion_version_id,
                "message": f"Successfully pulled configuration to {yaml_path}"
            }
            
        except Exception as e:
            error_msg = f"Error pulling configuration for Score {self.name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "UNEXPECTED_ERROR",
                "message": error_msg
            }

    def push_configuration(self, scorecard_name: Optional[str] = None, 
                          note: Optional[str] = None) -> Dict[str, Any]:
        """
        Push local YAML configuration as a new score version.
        
        Only creates a new version if the content has changed from the current champion version.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            note: Optional version note. Defaults to "Updated via Score.push_configuration()"
            
        Returns:
            Dict containing:
                - success: bool
                - version_id: str (new version ID if created, existing if no changes)
                - champion_updated: bool (whether champion version was updated)
                - message: str (success/error message)
                - skipped: bool (true if no changes detected)
        """
        if not self._client:
            return {
                "success": False,
                "error": "NO_CLIENT",
                "message": "Score instance must have an API client to push configuration"
            }

        try:
            # Get the local file path
            yaml_path = self.get_local_configuration_path(scorecard_name)
            
            if not yaml_path.exists():
                return {
                    "success": False,
                    "error": "FILE_NOT_FOUND",
                    "message": f"Local YAML file not found at: {yaml_path}"
                }

            # Read the local YAML content
            with open(yaml_path, 'r') as f:
                local_content = f.read()
            
            # Strip metadata comments that we add during pull
            # Only strip comments that match our specific metadata format
            local_yaml_lines = []
            metadata_prefixes = [
                '# Pulled from Plexus API',
                '# Score:',
                '# Champion Version ID:',
                '# Created:',
                '# Updated:',
                '# Note:'
            ]
            
            for line in local_content.split('\n'):
                # Skip our metadata comments and the separator line
                if line.strip() == '#':
                    continue
                is_metadata = False
                for prefix in metadata_prefixes:
                    if line.strip().startswith(prefix):
                        is_metadata = True
                        break
                if not is_metadata:
                    local_yaml_lines.append(line)
            
            local_yaml_clean = '\n'.join(local_yaml_lines).strip()

            # Get current champion version for comparison
            query = """
            query GetScore($id: ID!) {
                getScore(id: $id) {
                    championVersionId
                }
            }
            """
            
            result = self._client.execute(query, {'id': self.id})
            if not result or 'getScore' not in result:
                return {
                    "success": False,
                    "error": "API_ERROR",
                    "message": f"Failed to get current version for Score {self.id}"
                }
                
            current_champion_id = result['getScore'].get('championVersionId')
            
            # Compare with current champion version to avoid no-op pushes
            if current_champion_id:
                version_query = """
                query GetScoreVersion($id: ID!) {
                    getScoreVersion(id: $id) {
                        configuration
                    }
                }
                """
                
                version_result = self._client.execute(version_query, {'id': current_champion_id})
                if version_result and 'getScoreVersion' in version_result:
                    current_yaml = version_result['getScoreVersion'].get('configuration', '').strip()
                    
                    # Compare content (ignoring whitespace differences)
                    if current_yaml == local_yaml_clean:
                        logger.info(f"No changes detected for Score {self.name}, skipping version creation")
                        return {
                            "success": True,
                            "version_id": current_champion_id,
                            "champion_updated": False,
                            "message": f"No changes detected, keeping current version {current_champion_id}",
                            "skipped": True
                        }

            # Create new version
            mutation = """
            mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
                createScoreVersion(input: $input) {
                    id
                    configuration
                    createdAt
                    updatedAt
                    note
                    score {
                        id
                        championVersionId
                    }
                }
            }
            """
            
            version_input = {
                'scoreId': self.id,
                'configuration': local_yaml_clean,
                'note': note or 'Updated via Score.push_configuration()',
                'isFeatured': True  # Auto-promote to champion
            }
            
            # Include parent version if available
            if current_champion_id:
                version_input['parentVersionId'] = current_champion_id
            
            result = self._client.execute(mutation, {'input': version_input})
            
            if not result or 'createScoreVersion' not in result:
                return {
                    "success": False,
                    "error": "VERSION_CREATION_FAILED",
                    "message": "Failed to create new score version"
                }
            
            new_version = result['createScoreVersion']
            new_version_id = new_version['id']
            
            logger.info(f"Successfully created new version {new_version_id} for Score {self.name}")
            
            return {
                "success": True,
                "version_id": new_version_id,
                "champion_updated": True,
                "message": f"Successfully created new version {new_version_id}",
                "skipped": False
            }
            
        except Exception as e:
            error_msg = f"Error pushing configuration for Score {self.name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "UNEXPECTED_ERROR", 
                "message": error_msg
            }