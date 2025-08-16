"""
Experiment Service - Shared service layer for experiment operations.

This service provides a high-level interface for experiment management that can be
used by both CLI commands and MCP tools, ensuring DRY principles and consistent
behavior across different interfaces.

The service handles:
- Experiment creation with proper validation
- YAML configuration management  
- Node and version lifecycle management
- Error handling and logging
- Account and resource resolution
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import yaml
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.experiment import Experiment
from plexus.dashboard.api.models.experiment_node import ExperimentNode
from plexus.dashboard.api.models.experiment_node_version import ExperimentNodeVersion
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier
from plexus.cli.scorecard.scorecards import resolve_account_identifier

logger = logging.getLogger(__name__)

# Default YAML template for new experiments
DEFAULT_EXPERIMENT_YAML = """class: "BeamSearch"

value: |
  -- Extract accuracy score from experiment node's structured data
  local score = experiment_node.value.accuracy or 0
  -- Apply cost penalty to balance performance vs efficiency  
  local penalty = (experiment_node.value.cost or 0) * 0.1
  -- Return single scalar value (higher is better)
  return score - penalty

exploration: |
  You are helping optimize an AI system through beam search experimentation.
  
  You have access to previous experiment results including their configurations, 
  performance metrics, and computed values. Your job is to suggest new experiment 
  variations that might improve performance.
  
  Based on the results so far, propose specific changes to try next. Focus on 
  modifications that could address weaknesses or build on promising directions.
  
  Generate concrete, actionable suggestions for the next experiment iteration.
"""

@dataclass
class ExperimentCreationResult:
    """Result of creating a new experiment."""
    experiment: Experiment
    root_node: ExperimentNode
    initial_version: ExperimentNodeVersion
    success: bool
    message: str

@dataclass
class ExperimentInfo:
    """Comprehensive information about an experiment."""
    experiment: Experiment
    root_node: Optional[ExperimentNode]
    latest_version: Optional[ExperimentNodeVersion]
    node_count: int
    version_count: int
    scorecard_name: Optional[str]
    score_name: Optional[str]

class ExperimentService:
    """Service for managing experiments with shared logic for CLI and MCP."""
    
    def __init__(self, client: PlexusDashboardClient):
        self.client = client
        
    def create_experiment(
        self,
        account_identifier: str,
        scorecard_identifier: str, 
        score_identifier: str,
        yaml_config: Optional[str] = None,
        featured: bool = False,
        initial_value: Optional[Dict[str, Any]] = None,
        create_root_node: bool = True
    ) -> ExperimentCreationResult:
        """Create a new experiment with optional root node and initial version.
        
        Args:
            account_identifier: Account ID, key, or name
            scorecard_identifier: Scorecard ID, key, or name  
            score_identifier: Score ID, key, or name
            yaml_config: YAML configuration (uses default if None)
            featured: Whether to mark as featured
            initial_value: Initial computed value (defaults to {"initialized": True})
            create_root_node: Whether to create a root node (defaults to True for backward compatibility)
            
        Returns:
            ExperimentCreationResult with creation details
        """
        try:
            # Resolve identifiers
            account_id = resolve_account_identifier(self.client, account_identifier)
            if not account_id:
                return ExperimentCreationResult(
                    experiment=None,
                    root_node=None, 
                    initial_version=None,
                    success=False,
                    message=f"Could not resolve account: {account_identifier}"
                )
                
            scorecard_id = resolve_scorecard_identifier(self.client, scorecard_identifier)
            if not scorecard_id:
                return ExperimentCreationResult(
                    experiment=None,
                    root_node=None,
                    initial_version=None, 
                    success=False,
                    message=f"Could not resolve scorecard: {scorecard_identifier}"
                )
                
            # Resolve score identifier
            score_id = self._resolve_score_identifier(scorecard_id, score_identifier)
            if not score_id:
                return ExperimentCreationResult(
                    experiment=None,
                    root_node=None,
                    initial_version=None,
                    success=False,
                    message=f"Could not resolve score: {score_identifier}"
                )
            
            # Validate YAML if provided or if creating root node
            if yaml_config is not None or create_root_node:
                # Use default YAML if not provided and root node is requested
                if yaml_config is None and create_root_node:
                    yaml_config = DEFAULT_EXPERIMENT_YAML
                    
                # Validate YAML
                if yaml_config:
                    try:
                        yaml.safe_load(yaml_config)
                    except yaml.YAMLError as e:
                        return ExperimentCreationResult(
                            experiment=None,
                            root_node=None,
                            initial_version=None,
                            success=False,
                            message=f"Invalid YAML configuration: {str(e)}"
                        )
            
            # Create experiment
            experiment = Experiment.create(
                client=self.client,
                accountId=account_id,
                scorecardId=scorecard_id,
                scoreId=score_id,
                featured=featured
            )
            
            root_node = None
            initial_version = None
            
            # Optionally create root node with initial version
            if create_root_node:
                root_node = experiment.create_root_node(yaml_config, initial_value)
                initial_version = root_node.get_latest_version()
                logger.info(f"Successfully created experiment {experiment.id} with root node {root_node.id}")
            else:
                logger.info(f"Successfully created experiment {experiment.id} without root node")
            
            return ExperimentCreationResult(
                experiment=experiment,
                root_node=root_node,
                initial_version=initial_version,
                success=True,
                message=f"Created experiment {experiment.id}" + (" with root node" if create_root_node else " without root node")
            )
            
        except Exception as e:
            logger.error(f"Error creating experiment: {str(e)}", exc_info=True)
            return ExperimentCreationResult(
                experiment=None,
                root_node=None,
                initial_version=None,
                success=False,
                message=f"Failed to create experiment: {str(e)}"
            )
    
    def get_experiment_info(self, experiment_id: str) -> Optional[ExperimentInfo]:
        """Get comprehensive information about an experiment.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            ExperimentInfo with full experiment details, or None if not found
        """
        try:
            # Get experiment
            experiment = Experiment.get_by_id(experiment_id, self.client)
            
            # Get root node
            root_node = experiment.get_root_node()
            
            # Get latest version
            latest_version = None
            if root_node:
                latest_version = root_node.get_latest_version()
            
            # Count nodes and versions (handle GraphQL schema issues gracefully)
            node_count = 0
            version_count = 0
            
            try:
                all_nodes = ExperimentNode.list_by_experiment(experiment_id, self.client)
                node_count = len(all_nodes)
                
                for node in all_nodes:
                    versions = node.get_versions()
                    version_count += len(versions)
            except Exception as e:
                logger.warning(f"Could not count experiment nodes/versions: {e}")
                # Set defaults for experiments without proper node structure
                node_count = 1 if root_node else 0
                version_count = 1 if root_node else 0
            
            # Get scorecard and score names
            scorecard_name = None
            score_name = None
            
            if experiment.scorecardId:
                try:
                    scorecard = Scorecard.get_by_id(experiment.scorecardId, self.client)
                    scorecard_name = scorecard.name
                except Exception:
                    pass
                    
            if experiment.scoreId:
                try:
                    score = Score.get_by_id(experiment.scoreId, self.client)
                    score_name = score.name
                except Exception:
                    pass
            
            return ExperimentInfo(
                experiment=experiment,
                root_node=root_node,
                latest_version=latest_version,
                node_count=node_count,
                version_count=version_count,
                scorecard_name=scorecard_name,
                score_name=score_name
            )
            
        except Exception as e:
            logger.error(f"Error getting experiment info for {experiment_id}: {str(e)}")
            return None
    
    def list_experiments(
        self, 
        account_identifier: str, 
        scorecard_identifier: Optional[str] = None,
        limit: int = 100
    ) -> List[Experiment]:
        """List experiments for an account, optionally filtered by scorecard.
        
        Args:
            account_identifier: Account ID, key, or name
            scorecard_identifier: Optional scorecard ID, key, or name to filter by
            limit: Maximum number of experiments to return
            
        Returns:
            List of Experiment instances ordered by most recent first
        """
        try:
            # Resolve account
            account_id = resolve_account_identifier(self.client, account_identifier)
            if not account_id:
                logger.error(f"Could not resolve account: {account_identifier}")
                return []
            
            if scorecard_identifier:
                # Filter by scorecard
                scorecard_id = resolve_scorecard_identifier(self.client, scorecard_identifier)
                if not scorecard_id:
                    logger.error(f"Could not resolve scorecard: {scorecard_identifier}")
                    return []
                return Experiment.list_by_scorecard(scorecard_id, self.client, limit)
            else:
                # List all for account
                return Experiment.list_by_account(account_id, self.client, limit)
                
        except Exception as e:
            logger.error(f"Error listing experiments: {str(e)}")
            return []
    
    def delete_experiment(self, experiment_id: str) -> Tuple[bool, str]:
        """Delete an experiment and all its nodes/versions.
        
        Args:
            experiment_id: ID of the experiment to delete
            
        Returns:
            Tuple of (success, message)
        """
        try:
            experiment = Experiment.get_by_id(experiment_id, self.client)
            
            # Delete all nodes and their versions
            nodes = ExperimentNode.list_by_experiment(experiment_id, self.client)
            for node in nodes:
                # Delete all versions for this node
                versions = node.get_versions()
                for version in versions:
                    version.delete()
                # Delete the node
                node.delete()
            
            # Delete the experiment
            success = experiment.delete()
            
            if success:
                logger.info(f"Successfully deleted experiment {experiment_id}")
                return True, f"Deleted experiment {experiment_id}"
            else:
                return False, f"Failed to delete experiment {experiment_id}"
                
        except Exception as e:
            logger.error(f"Error deleting experiment {experiment_id}: {str(e)}")
            return False, f"Error deleting experiment: {str(e)}"
    
    def update_experiment_config(
        self, 
        experiment_id: str, 
        yaml_config: str,
        note: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Update an experiment's configuration by creating a new version.
        
        Args:
            experiment_id: ID of the experiment
            yaml_config: New YAML configuration
            note: Optional note for the version
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate YAML
            try:
                yaml.safe_load(yaml_config)
            except yaml.YAMLError as e:
                return False, f"Invalid YAML configuration: {str(e)}"
            
            experiment = Experiment.get_by_id(experiment_id, self.client)
            root_node = experiment.get_root_node()
            
            if not root_node:
                return False, "Experiment has no root node"
            
            # Get current highest seq number
            versions = root_node.get_versions()
            next_seq = max([v.seq for v in versions]) + 1 if versions else 1
            
            # Create new version
            new_version = root_node.create_version(
                seq=next_seq,
                yaml_config=yaml_config,
                value={"note": note} if note else {"updated": True},
                status='QUEUED'
            )
            
            logger.info(f"Created new version {new_version.id} for experiment {experiment_id}")
            return True, f"Updated experiment configuration (version {new_version.id})"
            
        except Exception as e:
            logger.error(f"Error updating experiment config: {str(e)}")
            return False, f"Error updating configuration: {str(e)}"
    
    def get_experiment_yaml(self, experiment_id: str) -> Optional[str]:
        """Get the latest YAML configuration for an experiment.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            YAML configuration string, or None if not found
        """
        try:
            experiment = Experiment.get_by_id(experiment_id, self.client)
            root_node = experiment.get_root_node()
            
            if not root_node:
                return None
                
            latest_version = root_node.get_latest_version()
            if not latest_version:
                return None
                
            return latest_version.get_yaml_config()
            
        except Exception as e:
            logger.error(f"Error getting experiment YAML: {str(e)}")
            return None
    
    def _resolve_score_identifier(self, scorecard_id: str, score_identifier: str) -> Optional[str]:
        """Resolve a score identifier within a specific scorecard.
        
        Args:
            scorecard_id: ID of the scorecard to search within
            score_identifier: Score ID, key, or name
            
        Returns:
            Score ID if found, None otherwise
        """
        try:
            # First try direct ID lookup
            if score_identifier.startswith('score-') or len(score_identifier) > 20:
                try:
                    score = Score.get_by_id(score_identifier, self.client)
                    # Verify it belongs to the correct scorecard
                    if score.scorecard_id == scorecard_id:
                        return score_identifier
                except Exception:
                    pass
            
            # Try looking up by key or name within the scorecard
            query = """
            query GetScoresByScorecard($scorecardId: String!) {
                getScorecard(id: $scorecardId) {
                    sections {
                        items {
                            scores {
                                items {
                                    id
                                    name
                                    key
                                    externalId
                                }
                            }
                        }
                    }
                }
            }
            """
            
            result = self.client.execute(query, {'scorecardId': scorecard_id})
            scorecard_data = result.get('getScorecard')
            
            if not scorecard_data:
                return None
            
            # Search through all scores in all sections
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    # Check for matches by key, name, or externalId
                    if (score.get('key') == score_identifier or 
                        score.get('name') == score_identifier or
                        score.get('externalId') == score_identifier):
                        return score['id']
            
            logger.warning(f"Could not resolve score identifier: {score_identifier}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving score identifier: {str(e)}")
            return None
    
    async def run_experiment(self, experiment_id: str, **options) -> Dict[str, Any]:
        """
        Run an experiment with the given ID.
        
        This function executes an experiment with MCP tool support, allowing the experiment
        to provide AI models with access to Plexus MCP tools during execution.
        
        Args:
            experiment_id: ID of the experiment to run
            **options: Optional parameters for experiment execution:
                - max_iterations: Maximum number of iterations (int)
                - timeout: Timeout in seconds (int) 
                - async_mode: Whether to run asynchronously (bool)
                - dry_run: Whether to perform a dry run (bool)
                - enable_mcp: Whether to enable MCP tools (bool, default True)
                - mcp_tools: List of MCP tool categories to enable (list)
                
        Returns:
            Dictionary containing:
                - experiment_id: The experiment ID
                - status: Current status ('running', 'completed', 'error', 'initiated')
                - message: Human-readable status message
                - error: Error message if applicable
                - run_id: Unique run identifier (future)
                - progress: Progress information (future)
                - mcp_info: Information about MCP tools if enabled
        """
        logger.info(f"Starting experiment run for experiment ID: {experiment_id}")
        
        # Input validation
        if not experiment_id or not isinstance(experiment_id, str):
            error_msg = "Invalid experiment ID: must be a non-empty string"
            logger.error(error_msg)
            return {
                'experiment_id': experiment_id,
                'status': 'error',
                'error': error_msg
            }
        
        try:
            # Get experiment details to validate it exists
            experiment_info = self.get_experiment_info(experiment_id)
            if not experiment_info:
                error_msg = f"Experiment not found: {experiment_id}"
                logger.error(error_msg)
                return {
                    'experiment_id': experiment_id,
                    'status': 'error',
                    'error': error_msg
                }
            
            logger.info(f"Found experiment: {experiment_id} (Scorecard: {experiment_info.scorecard_name})")
            
            # PROGRAMMATIC PHASE: Ensure proper experiment structure
            await self._ensure_experiment_structure(experiment_info)
            
            # Extract options for future use
            max_iterations = options.get('max_iterations', 100)
            timeout = options.get('timeout', 3600)  # 1 hour default
            async_mode = options.get('async_mode', False)
            dry_run = options.get('dry_run', False)
            
            logger.info(f"Experiment run options: max_iterations={max_iterations}, timeout={timeout}, async_mode={async_mode}, dry_run={dry_run}")
            
            # Initialize MCP server with all Plexus tools
            mcp_server = None
            mcp_info = None
            
            try:
                from .mcp_transport import create_experiment_mcp_server
                
                # Create experiment context for MCP tools
                experiment_context = {
                    'experiment_id': experiment_id,
                    'account_id': experiment_info.experiment.accountId,
                    'scorecard_id': experiment_info.experiment.scorecardId,
                    'score_id': experiment_info.experiment.scoreId,
                    'scorecard_name': experiment_info.scorecard_name,
                    'score_name': experiment_info.score_name,
                    'node_count': experiment_info.node_count,
                    'version_count': experiment_info.version_count,
                    'options': options
                }
                
                # Always create MCP server with all available tools
                mcp_server = await create_experiment_mcp_server(
                    experiment_context=experiment_context,
                    plexus_tools=None  # None means all tools
                )
                
                mcp_info = {
                    'available_tools': list(mcp_server.transport.tools.keys()),
                    'server_info': mcp_server.transport.server_info
                }
                
                logger.info(f"MCP server initialized with {len(mcp_server.transport.tools)} tools")
                
            except ImportError as e:
                logger.warning(f"Could not import MCP transport: {e}")
                mcp_info = {'error': 'MCP transport not available'}
            except Exception as e:
                logger.warning(f"Failed to initialize MCP server: {e}")
                mcp_info = {'error': str(e)}
            
            # Hello-world implementation for now
            if dry_run:
                logger.info("Performing dry run - no actual execution")
                result = {
                    'experiment_id': experiment_id,
                    'status': 'completed',
                    'message': f'Dry run completed successfully for experiment: {experiment_id}',
                    'details': {
                        'experiment_id': experiment_id,
                        'scorecard_name': experiment_info.scorecard_name,
                        'node_count': experiment_info.node_count,
                        'options': options
                    }
                }
                
                if mcp_info:
                    result['mcp_info'] = mcp_info
                    
                return result
            
            # Initialize result structure
            result = {
                'experiment_id': experiment_id,
                'status': 'initiated',
                'message': f'Experiment run initiated successfully for: {experiment_id}',
                'details': {
                    'experiment_id': experiment_id,
                    'scorecard_name': experiment_info.scorecard_name,
                    'score_name': experiment_info.score_name,
                    'node_count': experiment_info.node_count,
                    'options': options
                }
            }
            
            if mcp_info:
                result['mcp_info'] = mcp_info
            
            # AI-powered experiment execution with MCP tools
            if mcp_server and not dry_run:
                try:
                    # Get experiment YAML configuration
                    experiment_yaml = self.get_experiment_yaml(experiment_id)
                    if not experiment_yaml:
                        logger.warning(f"No YAML configuration found for experiment {experiment_id}, using default")
                        experiment_yaml = DEFAULT_EXPERIMENT_YAML
                    
                    # Import and run AI experiment
                    from .langchain_mcp import run_experiment_with_ai
                    
                    logger.info("Starting AI-powered experiment execution with MCP tools...")
                    
                    # Get OpenAI API key from options or configuration system
                    openai_api_key = options.get('openai_api_key')
                    if not openai_api_key:
                        try:
                            # Use Plexus configuration loader for proper .plexus/config.yaml + .env support
                            from plexus.config.loader import load_config
                            load_config()  # This loads config and sets environment variables
                            import os
                            openai_api_key = os.getenv('OPENAI_API_KEY')
                            logger.info(f"Service loaded OpenAI key: {'Yes' if openai_api_key else 'No'}")
                        except Exception as e:
                            logger.warning(f"Failed to load configuration for OpenAI key: {e}")
                    else:
                        logger.info(f"Service using OpenAI key from options: Yes")
                    
                    ai_result = await run_experiment_with_ai(
                        experiment_id=experiment_id,
                        experiment_yaml=experiment_yaml,
                        mcp_server=mcp_server,
                        openai_api_key=openai_api_key,
                        experiment_context=experiment_context,
                        client=self.client
                    )
                    
                    if ai_result.get('success'):
                        logger.info("AI experiment execution completed successfully")
                        
                        # Add AI results to the response
                        result['ai_execution'] = {
                            'completed': True,
                            'tools_used': ai_result.get('tool_names', []),
                            'response_length': len(ai_result.get('response', '')),
                            'prompt_used': len(ai_result.get('prompt', ''))
                        }
                        result['status'] = 'completed'
                        result['message'] = f'AI-powered experiment completed successfully for: {experiment_id}'
                        
                    else:
                        logger.error(f"AI experiment execution failed: {ai_result.get('error')}")
                        result['ai_execution'] = {
                            'completed': False,
                            'error': ai_result.get('error'),
                            'suggestion': ai_result.get('suggestion', 'Check logs for details')
                        }
                        # Don't fail the whole experiment, just note the AI execution issue
                        result['status'] = 'completed_with_warnings'
                        result['message'] = f'Experiment completed but AI execution had issues: {ai_result.get("error", "Unknown error")}'
                        
                except ImportError as e:
                    logger.warning(f"Could not import AI experiment modules: {e}")
                    result['ai_execution'] = {
                        'completed': False,
                        'error': 'AI modules not available',
                        'suggestion': 'Install langchain and openai packages for AI-powered experiments'
                    }
                except Exception as e:
                    logger.error(f"Error during AI experiment execution: {e}")
                    result['ai_execution'] = {
                        'completed': False,
                        'error': str(e)
                    }
                    
            # Basic MCP demonstration for dry runs or when AI is not available
            elif mcp_server:
                try:
                    async with mcp_server.connect({'name': 'Experiment Runner'}) as mcp_client:
                        # Demonstrate MCP tool interaction
                        logger.info("Testing MCP tool interaction...")
                        
                        # Get experiment context via MCP
                        context_result = await mcp_client.call_tool("get_experiment_context", {})
                        logger.info("Successfully called get_experiment_context via MCP")
                        
                        # Log a message via MCP
                        await mcp_client.call_tool("log_message", {
                            "message": f"Experiment {experiment_id} execution started",
                            "level": "info"
                        })
                        
                        logger.info("MCP-enabled experiment execution completed successfully")
                        
                except Exception as e:
                    logger.error(f"Error during MCP-enabled execution: {e}")
                    return {
                        'experiment_id': experiment_id,
                        'status': 'error',
                        'error': f'MCP execution error: {str(e)}',
                        'mcp_info': mcp_info
                    }
            
            logger.info(f"Experiment run initiated successfully for: {experiment_id}")
            return result
            
        except Exception as e:
            error_msg = f"Error running experiment {experiment_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'experiment_id': experiment_id,
                'status': 'error',
                'error': error_msg
            }
    
    async def _ensure_experiment_structure(self, experiment_info: 'ExperimentInfo') -> None:
        """
        Programmatically ensure the experiment has the proper structure.
        
        This includes:
        1. Creating a root node if it doesn't exist
        2. Populating the root node with the champion score configuration
        3. Any other structural requirements
        
        This is done programmatically (not by AI agents) for reliability.
        """
        try:
            experiment = experiment_info.experiment
            logger.info(f"Ensuring proper structure for experiment {experiment.id}")
            
            # Check if root node exists
            root_node = experiment_info.root_node
            
            if not root_node:
                logger.info("No root node found - creating root node programmatically")
                await self._create_root_node_with_champion_config(experiment)
            else:
                # Check if root node has proper score configuration
                latest_version = root_node.get_latest_version()
                if not latest_version or not latest_version.code:
                    logger.info("Root node exists but lacks score configuration - updating")
                    await self._update_root_node_with_champion_config(root_node, experiment)
                else:
                    logger.info("Root node structure appears valid - no action needed")
                    
        except Exception as e:
            logger.error(f"Error ensuring experiment structure: {e}")
            # Don't fail the entire experiment run for structure issues
            pass
    
    async def _create_root_node_with_champion_config(self, experiment: Experiment) -> ExperimentNode:
        """Create a root node populated with the champion score configuration."""
        try:
            # Get the champion score configuration
            score_config = await self._get_champion_score_config(experiment.scoreId)
            if not score_config:
                logger.warning(f"Could not get champion config for score {experiment.scoreId}")
                score_config = "# Champion score configuration not available\nname: placeholder"
            
            # Create the root node
            root_node = ExperimentNode.create(
                client=self.client,
                experimentId=experiment.id,
                parentNodeId=None,  # Root node has no parent
                name="Root",
                status='ACTIVE'
            )
            
            # Create initial version with champion score config (no hypothesis for root node)
            root_version = root_node.create_version(
                code=score_config,  # This is the score YAML, not experiment YAML
                value={
                    "type": "root_node",
                    "description": "Starting configuration from champion score",
                    "created_by": "programmatic"
                },
                status='ACTIVE'
                # No hypothesis - root node is just the baseline configuration
            )
            
            # Update experiment to point to this root node (persist to database)
            experiment = experiment.update_root_node(root_node.id)
            
            logger.info(f"Created root node {root_node.id} with champion score configuration")
            return root_node
            
        except Exception as e:
            logger.error(f"Error creating root node: {e}")
            raise
    
    async def _update_root_node_with_champion_config(self, root_node: ExperimentNode, experiment: Experiment) -> None:
        """Update existing root node with champion score configuration."""
        try:
            # Get the champion score configuration
            score_config = await self._get_champion_score_config(experiment.scoreId)
            if not score_config:
                logger.warning(f"Could not get champion config for score {experiment.scoreId}")
                return
            
            # Create new version with champion config (no hypothesis for root node)
            root_version = root_node.create_version(
                code=score_config,  # This is the score YAML, not experiment YAML
                value={
                    "type": "root_node_update",
                    "description": "Updated with champion score configuration",
                    "created_by": "programmatic"
                },
                status='ACTIVE'
                # No hypothesis - root node is just the baseline configuration
            )
            
            logger.info(f"Updated root node {root_node.id} with champion score configuration")
            
        except Exception as e:
            logger.error(f"Error updating root node: {e}")
            raise
    
    async def _get_champion_score_config(self, score_id: str) -> Optional[str]:
        """Get the champion (current) YAML configuration for a score."""
        try:
            # Use the MCP tool to get score configuration since we don't have direct access
            # This ensures we get the same configuration that MCP tools would use
            from MCP.tools.score.scores import get_score_configuration
            
            # The MCP tool expects scorecard and score identifiers, but we only have score_id
            # Let's get the score first to get its name and scorecard
            score = Score.get_by_id(score_id, self.client)
            if not score:
                logger.error(f"Score {score_id} not found")
                return None
            
            # Get scorecard to find the score name
            scorecard = Scorecard.get_by_id(score.scorecardId, self.client)
            if not scorecard:
                logger.error(f"Scorecard {score.scorecardId} not found")
                return None
            
            # Use MCP tool to get configuration
            config_result = get_score_configuration(
                scorecard_identifier=scorecard.name,
                score_identifier=score.name,
                client=self.client
            )
            
            if config_result and isinstance(config_result, str) and "yaml_config" in config_result:
                # Extract YAML from MCP result
                import json
                try:
                    result_data = json.loads(config_result)
                    champion_config = result_data.get('yaml_config')
                    if champion_config:
                        logger.info(f"Retrieved champion configuration for score {score_id}")
                        return champion_config
                except json.JSONDecodeError:
                    pass
            
            logger.warning(f"No champion configuration found for score {score_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting champion score config for {score_id}: {e}")
            return None