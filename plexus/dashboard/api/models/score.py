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
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path
from .base import BaseModel
from .scorecard import Scorecard
from plexus.cli.shared import get_score_yaml_path

if TYPE_CHECKING:
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
        client: Optional['_BaseAPIClient'] = None
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
    def from_dict(cls, data: Dict[str, Any], client: '_BaseAPIClient') -> 'Score':
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
    def get_by_id(cls, id: str, client: '_BaseAPIClient') -> 'Score':
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
    def get_by_name(cls, name: str, scorecard_id: str, client: '_BaseAPIClient') -> Optional['Score']:
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
    def get_by_key(cls, key: str, scorecard_id: str, client: '_BaseAPIClient') -> Optional['Score']:
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
                          client: '_BaseAPIClient') -> Optional['Score']:
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
    def list_by_section_id(cls, section_id: str, client: '_BaseAPIClient', 
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

    def get_code(self) -> Optional[Dict[str, Any]]:
        """
        Get the score's code from its champion version.
        
        Returns:
            Optional[Dict[str, Any]]: The parsed YAML code, or None if not found
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
            
        code_yaml = version_result['getScoreVersion'].get('configuration')
        if not code_yaml:
            logger.error(f"No code found in version {champion_version_id}")
            return None

        try:
            # Parse the YAML content
            return yaml.safe_load(code_yaml)
        except Exception as e:
            logger.error(f"Error parsing YAML code for Score {self.id}: {e}")
            return None

    def get_valid_classes(self) -> List[Dict[str, Any]]:
        """
        Get the list of valid classes from the score's code.
        
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
        config = self.get_code()
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
        config = self.get_code()
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

    def get_champion_code_yaml(self) -> Optional[str]:
        """
        Get the raw YAML code string from the champion version.
        
        Returns:
            Optional[str]: The raw YAML code string, or None if not found
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
            
        code_yaml = version_result['getScoreVersion'].get('configuration')
        if not code_yaml:
            logger.error(f"No code found in version {champion_version_id}")
            return None

        return code_yaml

    def get_champion_configuration_yaml(self) -> Optional[str]:
        """
        Get the raw YAML configuration string from the champion version.
        
        Returns:
            Optional[str]: The raw YAML configuration string, or None if not found
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
            return None
            
        champion_version_id = result['getScore'].get('championVersionId')
        if not champion_version_id:
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
            return None
            
        return version_result['getScoreVersion'].get('configuration')

    def get_local_configuration_path(self, scorecard_name: Optional[str] = None) -> Path:
        """
        Get the local YAML file path for this score's configuration.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Path: Path to the local YAML configuration file
        """
        return self.get_local_code_path(scorecard_name)

    def pull_configuration(self, scorecard_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Pull the champion version configuration to local file.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Dict containing:
                - success: bool
                - file_path: str (path where configuration was saved)
                - version_id: str (the champion version ID that was pulled)
                - error: str (error message if failed)
        """
        result = self.pull_code_and_guidelines(scorecard_name)
        if result["success"]:
            return {
                "success": True,
                "file_path": result["code_file_path"],
                "version_id": result["version_id"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }

    def push_configuration(self, scorecard_name: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
        """
        Push local configuration file as a new score version.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            note: Optional version note.
            
        Returns:
            Dict containing:
                - success: bool
                - version_id: str (new version ID if created, existing if no changes)
                - champion_updated: bool (whether champion version was updated)
                - skipped: bool (true if no changes detected)
                - error: str (error message if failed)
        """
        result = self.push_code_and_guidelines(scorecard_name, note)
        return result

    def create_version_from_yaml(self, yaml_content: str, note: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new score version from YAML content string.
        
        Args:
            yaml_content: The YAML configuration content as a string
            note: Optional version note.
            
        Returns:
            Dict containing:
                - success: bool
                - version_id: str (new version ID if created, existing if no changes)
                - champion_updated: bool (whether champion version was updated)
                - skipped: bool (true if no changes detected)
                - error: str (error message if failed)
        """
        return self.create_version_from_code(
            yaml_content, 
            note or 'Updated via Score.create_version_from_yaml()'
        )

    def get_local_code_path(self, scorecard_name: Optional[str] = None) -> Path:
        """
        Get the local YAML file path for this score's code.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Path: Path to the local YAML code file
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
            
        # Use the existing get_score_yaml_path function for consistency
        from plexus.cli.shared import get_score_yaml_path
        return get_score_yaml_path(scorecard_name, self.name)

    def get_local_guidelines_path(self, scorecard_name: Optional[str] = None) -> Path:
        """
        Get the local file path for this score's guidelines.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Path: Path to the local guidelines file
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
            
        # Use the same directory structure as code, but with .md extension
        from plexus.cli.shared import get_score_yaml_path
        code_path = get_score_yaml_path(scorecard_name, self.name)
        # Replace .yaml extension with .md for guidelines
        return code_path.with_suffix('.md')

    def pull_code_and_guidelines(self, scorecard_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Pull the champion version code and guidelines to local files.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            
        Returns:
            Dict containing:
                - success: bool
                - code_file_path: str (path where code was saved)
                - guidelines_file_path: str (path where guidelines were saved)
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
                    guidelines
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
            code_yaml = version_data.get('configuration')
            guidelines = version_data.get('guidelines', '')
            
            if not code_yaml:
                return {
                    "success": False,
                    "error": "NO_CODE",
                    "message": f"No code found in version {champion_version_id}"
                }

            # Get the local file paths
            code_path = self.get_local_code_path(scorecard_name)
            guidelines_path = self.get_local_guidelines_path(scorecard_name)
            
            # Create directory if it doesn't exist
            code_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write code to YAML file with version metadata as comments
            with open(code_path, 'w') as f:
                f.write(f"# Pulled from Plexus API\n")
                f.write(f"# Score: {self.name}\n")
                f.write(f"# Champion Version ID: {champion_version_id}\n")
                f.write(f"# Created: {version_data.get('createdAt', 'Unknown')}\n")
                f.write(f"# Updated: {version_data.get('updatedAt', 'Unknown')}\n")
                if version_data.get('note'):
                    f.write(f"# Note: {version_data['note']}\n")
                f.write(f"#\n")
                f.write(code_yaml)
            
            # Write guidelines to markdown file
            with open(guidelines_path, 'w') as f:
                f.write(f"# Guidelines for {self.name}\n\n")
                f.write(f"<!-- Pulled from Plexus API -->\n")
                f.write(f"<!-- Champion Version ID: {champion_version_id} -->\n")
                f.write(f"<!-- Updated: {version_data.get('updatedAt', 'Unknown')} -->\n\n")
                if guidelines:
                    f.write(guidelines)
                else:
                    f.write("*No guidelines specified for this score.*\n")
            
            logger.info(f"Successfully pulled code and guidelines for Score {self.name}")
            
            return {
                "success": True,
                "code_file_path": str(code_path),
                "guidelines_file_path": str(guidelines_path),
                "version_id": champion_version_id,
                "message": f"Successfully pulled code to {code_path} and guidelines to {guidelines_path}"
            }
            
        except Exception as e:
            error_msg = f"Error pulling code and guidelines for Score {self.name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "UNEXPECTED_ERROR",
                "message": error_msg
            }

    def push_code_and_guidelines(self, scorecard_name: Optional[str] = None, 
                                note: Optional[str] = None) -> Dict[str, Any]:
        """
        Push local code and guidelines files as a new score version.
        
        Automatically detects which files have changed by comparing with the current champion version.
        Only creates a new version if either code or guidelines have changed.
        
        Args:
            scorecard_name: Optional scorecard name. If not provided, will lookup via API.
            note: Optional version note. Defaults to "Updated via Score.push_code_and_guidelines()"
            
        Returns:
            Dict containing:
                - success: bool
                - version_id: str (new version ID if created, existing if no changes)
                - champion_updated: bool (whether champion version was updated)
                - message: str (success/error message)
                - skipped: bool (true if no changes detected)
                - changes_detected: dict with 'code' and 'guidelines' booleans indicating what changed
        """
        if not self._client:
            return {
                "success": False,
                "error": "NO_CLIENT",
                "message": "Score instance must have an API client to push configuration"
            }

        try:
            # Get the local file paths
            code_path = self.get_local_code_path(scorecard_name)
            guidelines_path = self.get_local_guidelines_path(scorecard_name)
            
            # Check which files exist
            code_exists = code_path.exists()
            guidelines_exists = guidelines_path.exists()
            
            if not code_exists and not guidelines_exists:
                return {
                    "success": False,
                    "error": "NO_FILES_FOUND",
                    "message": f"No local files found at: {code_path} or {guidelines_path}"
                }

            # Read local files
            local_code = None
            local_guidelines = None
            
            if code_exists:
                with open(code_path, 'r') as f:
                    local_content = f.read()
                
                # Strip metadata comments that we add during pull
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
                
                local_code = '\n'.join(local_yaml_lines).strip()
            
            if guidelines_exists:
                with open(guidelines_path, 'r') as f:
                    guidelines_content = f.read()
                
                # Strip markdown metadata comments that we add during pull
                guidelines_lines = []
                in_metadata = True
                
                for line in guidelines_content.split('\n'):
                    # Skip the title and metadata comments at the start
                    if in_metadata:
                        if line.startswith('# Guidelines for') or line.startswith('<!--') or line.strip() == '':
                            continue
                        else:
                            in_metadata = False
                    
                    if not in_metadata:
                        guidelines_lines.append(line)
                
                local_guidelines = '\n'.join(guidelines_lines).strip()
                # Remove the placeholder text if it's there
                if local_guidelines == "*No guidelines specified for this score.*":
                    local_guidelines = ""

            # Get current champion version for comparison
            # If no local code, get current code to preserve it
            if not code_exists:
                champion_query = f"""
                query GetScore {{
                    getScore(id: "{self.id}") {{
                        championVersionId
                    }}
                }}
                """
                champion_result = self._client.execute(champion_query, {'id': self.id})
                current_champion_id = champion_result.get('getScore', {}).get('championVersionId')
                
                if current_champion_id:
                    config_query = f"""
                    query GetScoreVersion {{
                        getScoreVersion(id: "{current_champion_id}") {{
                            configuration
                        }}
                    }}
                    """
                    config_result = self._client.execute(config_query, {'id': current_champion_id})
                    local_code = config_result.get('getScoreVersion', {}).get('configuration', '')

            # Use the foundational create_version_from_code method
            result = self.create_version_from_code(
                local_code or '', 
                note or 'Updated via Score.push_code_and_guidelines()',
                guidelines=local_guidelines
            )
            
            # Add information about what was detected/pushed
            if result["success"]:
                result["changes_detected"] = {
                    "code": code_exists,
                    "guidelines": guidelines_exists
                }
            
            return result
            
        except Exception as e:
            error_msg = f"Error pushing code and guidelines for Score {self.name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "UNEXPECTED_ERROR",
                "message": error_msg
            }

    def create_version_from_code(self, code_content: str, note: Optional[str] = None, guidelines: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new score version from code and guidelines content.
        
        This is the foundational method that only creates a new version if the content 
        has changed from the current champion version.
        
        Args:
            code_content: The YAML code content as a string
            note: Optional version note. Defaults to "Updated via Score.create_version_from_code()"
            guidelines: Optional guidelines content as a string
            
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
                "message": "Score instance must have an API client to create version"
            }

        try:
            # Validate YAML code content if provided
            if code_content:
                try:
                    import yaml
                    yaml.safe_load(code_content)
                    # NOTE: Guidelines are NOT extracted from YAML as they are a separate field
                    
                except yaml.YAMLError as e:
                    return {
                        "success": False,
                        "error": "INVALID_YAML",
                        "message": f"Invalid YAML code content: {str(e)}"
                    }

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
                        guidelines
                    }
                }
                """
                
                version_result = self._client.execute(version_query, {'id': current_champion_id})
                if version_result and 'getScoreVersion' in version_result:
                    current_version_data = version_result['getScoreVersion']
                    current_yaml = (current_version_data.get('configuration') or '').strip()
                    current_guidelines = (current_version_data.get('guidelines') or '').strip()
                    
                    # Compare both code and guidelines (ignoring whitespace differences)
                    code_unchanged = current_yaml == (code_content or '').strip()
                    guidelines_unchanged = current_guidelines == (guidelines or '').strip()
                    
                    if code_unchanged and guidelines_unchanged:
                        logger.info(f"No changes detected for Score {self.name}, skipping version creation")
                        return {
                            "success": True,
                            "version_id": current_champion_id,
                            "champion_updated": False,
                            "message": f"No changes detected for Score {self.name}, skipping version creation",
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
                'configuration': (code_content or '').strip(),
                'note': note or 'Updated via Score.create_version_from_code()',
                # Mark as featured by default so the version is created as a candidate for champion
                # (promotion will be explicitly set via updateScore below)
                'isFeatured': True
            }
            
            # Add guidelines if provided
            if guidelines:
                stripped_guidelines = guidelines.strip()
                if stripped_guidelines:
                    version_input['guidelines'] = stripped_guidelines
            
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

            # MCP tools should NOT promote versions to champion - that's a separate process
            champion_updated = False

            logger.info(f"Successfully created new version {new_version_id} for Score {self.name}")
            
            return {
                "success": True,
                "version_id": new_version_id,
                "champion_updated": champion_updated,
                "message": f"Successfully created new version for Score {self.name}",
                "skipped": False
            }
            
        except Exception as e:
            error_msg = f"Error creating version for Score {self.name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "UNEXPECTED_ERROR",
                "message": error_msg
            }