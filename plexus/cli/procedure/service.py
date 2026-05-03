"""
Procedure Service - Shared service layer for procedure operations.

This service provides a high-level interface for procedure management that can be
used by both CLI commands and MCP tools, ensuring DRY principles and consistent
behavior across different interfaces.

The service handles:
- Procedure creation with proper validation
- YAML configuration management
- Error handling and logging
- Account and resource resolution
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from contextlib import nullcontext
from pathlib import Path
import tempfile
import time
import yaml
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.procedure import Procedure
from plexus.dashboard.api.models.procedure_template import ProcedureTemplate
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.task import Task
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier
from plexus.cli.scorecard.scorecards import resolve_account_identifier
from plexus.cli.procedure.parameter_parser import ProcedureParameterParser
from plexus.cli.procedure.builtin_procedures import is_builtin_procedure_id, get_builtin_procedure_yaml

logger = logging.getLogger(__name__)

def _validate_yaml_template(template_data):
    """Validate that a YAML template has required sections for procedures."""
    if not isinstance(template_data, dict):
        return False

    # Detect procedure class
    procedure_class = template_data.get('class')

    if procedure_class == 'Tactus':
        required_keys = ['name', 'version', 'class', 'code']
        for key in required_keys:
            if key not in template_data:
                logger.warning(f"Tactus template missing required key: {key}")
                return False

        code = template_data.get('code', '')
        if not isinstance(code, str) or not code.strip():
            logger.warning("Tactus template must have non-empty 'code' section")
            return False

        if 'workflow' in template_data:
            logger.warning("Tactus templates use 'code', not 'workflow'")
            return False

        logger.info("Tactus validation passed")
        return True

    if procedure_class == 'LuaDSL':
        logger.warning("LuaDSL procedure class is no longer supported. Use class: Tactus with code.")
        return False

    # Validate SOP Agent-style structures (SOPAgent and legacy classes like BeamSearch)
    if procedure_class != 'Tactus':
        required_keys = ['class', 'prompts']
        for key in required_keys:
            if key not in template_data:
                logger.warning(f"Template missing required key: {key}")
                return False

        # Check for required prompt sections
        prompts = template_data.get('prompts', {})
        required_prompts = ['worker_system_prompt', 'worker_user_prompt', 'manager_system_prompt']
        for prompt_key in required_prompts:
            if prompt_key not in prompts:
                logger.warning(f"Template missing required prompt: {prompt_key}")
                return False
            if not prompts[prompt_key] or prompts[prompt_key].strip() == '':
                logger.warning(f"Template has empty prompt: {prompt_key}")
                return False

        logger.info("SOP Agent validation passed")
        return True

    logger.warning(f"Unknown or missing procedure class: {procedure_class}")
    return False

# NO DEFAULT TEMPLATE - procedures must have YAML in database
# Users MUST provide their own YAML via Procedure.code or ProcedureTemplate

@dataclass
class ProcedureCreationResult:
    """Result of creating a new procedure."""
    procedure: Optional[Procedure]
    success: bool
    message: str

@dataclass
class ProcedureInfo:
    """Comprehensive information about an procedure."""
    procedure: Procedure
    scorecard_name: Optional[str] = None
    score_name: Optional[str] = None

class ProcedureService:
    """Service for managing experiments with shared logic for CLI and MCP."""
    
    def __init__(self, client: PlexusDashboardClient):
        self.client = client
    
    def get_or_create_default_template(self, account_id: str) -> Optional[ProcedureTemplate]:
        """Get the default procedure template for an account.
        
        NOTE: This no longer creates templates automatically. Users must create
        their own ProcedureTemplates via the dashboard or API.
        
        Args:
            account_id: The account ID
            
        Returns:
            The default ProcedureTemplate instance if one exists, None otherwise
        """
        # Try to get existing default template
        template = ProcedureTemplate.get_default_for_account(
            account_id, self.client, "hypothesis_generation"
        )
        
        if template:
            logger.debug(f"Found existing default template {template.id} for account {account_id}")
            return template
        
        logger.warning(f"No default procedure template found for account {account_id}")
        logger.warning("Users must create ProcedureTemplates via dashboard or API")
        return None
        
    def create_procedure(
        self,
        account_identifier: str,
        scorecard_identifier: Optional[str] = None,
        score_identifier: Optional[str] = None,
        yaml_config: Optional[str] = None,
        featured: bool = False,
        template_id: Optional[str] = None,
        score_version_id: Optional[str] = None,
        stage_configs: Optional[Dict[str, Any]] = None,
    ) -> ProcedureCreationResult:
        """Create a new procedure.

        Args:
            account_identifier: Account ID, key, or name
            scorecard_identifier: Scorecard ID, key, or name
            score_identifier: Score ID, key, or name
            yaml_config: YAML configuration (uses default if None)
            featured: Whether to mark as featured
            template_id: Optional template/parent procedure ID (NOTE: stored as parentProcedureId in schema)
            score_version_id: Optional score version ID

        Returns:
            ProcedureCreationResult with creation details
        """
        try:
            # Resolve identifiers
            account_id = resolve_account_identifier(self.client, account_identifier)
            if not account_id:
                return ProcedureCreationResult(
                    procedure=None,
                    success=False,
                    message=f"Could not resolve account: {account_identifier}"
                )

            # Resolve scorecard identifier (optional for standalone procedures)
            scorecard_id = None
            if scorecard_identifier:
                scorecard_id = resolve_scorecard_identifier(self.client, scorecard_identifier)
                if not scorecard_id:
                    return ProcedureCreationResult(
                        procedure=None,
                        success=False,
                        message=f"Could not resolve scorecard: {scorecard_identifier}"
                    )

            # Resolve score identifier (optional for standalone procedures)
            score_id = None
            if score_identifier and scorecard_id:
                from plexus.cli.shared.direct_identifier_resolution import direct_resolve_score_identifier
                score_id = direct_resolve_score_identifier(self.client, scorecard_id, score_identifier)
                if not score_id:
                    return ProcedureCreationResult(
                        procedure=None,
                        success=False,
                        message=f"Could not resolve score: {score_identifier}"
                    )
            
            # Get or create procedure template
            if template_id:
                # Use specified template
                try:
                    template = ProcedureTemplate.get_by_id(template_id, self.client)
                    if not template:
                        return ProcedureCreationResult(
                            procedure=None,
                            success=False,
                            message=f"Template not found: {template_id}"
                        )
                except Exception as e:
                    return ProcedureCreationResult(
                        procedure=None,
                        success=False,
                        message=f"Error loading template {template_id}: {str(e)}"
                    )
            else:
                # Get or create default template
                template = self.get_or_create_default_template(account_id)
            
            # Validate YAML if provided.
            if yaml_config is not None:
                # Validate YAML
                if yaml_config:
                    try:
                        yaml_data = yaml.safe_load(yaml_config)
                        # Enhanced validation - check for required structure
                        if not _validate_yaml_template(yaml_data):
                            return ProcedureCreationResult(
                                procedure=None,
                                success=False,
                                message="YAML configuration is invalid for its procedure class. Tactus requires class/name/version/code; SOPAgent requires class/prompts."
                            )
                    except yaml.YAMLError as e:
                        return ProcedureCreationResult(
                            procedure=None,
                            success=False,
                            message=f"Invalid YAML configuration: {str(e)}"
                        )
            
            # If scorecard/score weren't supplied as arguments, try to infer from YAML parameter values.
            # Handles both 'scorecard_id' (UUID) and 'scorecard' (external ID / name) parameter names.
            if yaml_config and (not scorecard_id or not score_id):
                from plexus.cli.procedure.parameter_parser import ProcedureParameterParser
                param_values = ProcedureParameterParser.extract_parameter_values(yaml_config)
                if not scorecard_id:
                    _sc_val = param_values.get('scorecard_id') or param_values.get('scorecard')
                    if _sc_val:
                        resolved = resolve_scorecard_identifier(self.client, _sc_val)
                        if resolved:
                            scorecard_id = resolved
                if not score_id and scorecard_id:
                    _s_val = param_values.get('score_id') or param_values.get('score')
                    if _s_val:
                        resolved = self._resolve_score_identifier(scorecard_id, _s_val)
                        if resolved:
                            score_id = resolved

            # Create experiment
            procedure = Procedure.create(
                client=self.client,
                accountId=account_id,
                scorecardId=scorecard_id,
                scoreId=score_id,
                parentProcedureId=template.id if template else None,  # Changed from templateId
                isTemplate=False,  # Mark as instance, not template
                code=yaml_config,  # Store YAML in procedure
                featured=featured,
                scoreVersionId=score_version_id
            )
            
            # Get or create Task with stages from state machine
            task = self._get_or_create_task_with_stages_for_procedure(
                procedure_id=procedure.id,
                account_id=account_id,
                scorecard_id=scorecard_id,
                score_id=score_id,
                stage_configs=stage_configs,
            )
            if task:
                logger.info(f"Using Task {task.id} with {len(task.get_stages())} stages for procedure {procedure.id}")
            
            logger.info(f"Successfully created procedure {procedure.id}")
            
            return ProcedureCreationResult(
                procedure=procedure,
                success=True,
                message=f"Created procedure {procedure.id}"
            )
            
        except Exception as e:
            logger.error(f"Error creating experiment: {str(e)}", exc_info=True)
            return ProcedureCreationResult(
                procedure=None,
                success=False,
                message=f"Failed to create experiment: {str(e)}"
            )
    
    def get_procedure_info(self, procedure_id: str) -> Optional[ProcedureInfo]:
        """Get comprehensive information about an procedure.
        
        Args:
            procedure_id: ID of the experiment
            
        Returns:
            ProcedureInfo with full procedure details, or None if not found
        """
        try:
            # Get experiment
            procedure = Procedure.get_by_id(procedure_id, self.client)
            
            # Get scorecard and score names
            scorecard_name = None
            score_name = None
            
            if procedure.scorecardId:
                try:
                    scorecard = Scorecard.get_by_id(procedure.scorecardId, self.client)
                    scorecard_name = scorecard.name
                except Exception:
                    pass
                    
            if procedure.scoreId:
                try:
                    score = Score.get_by_id(procedure.scoreId, self.client)
                    score_name = score.name
                except Exception:
                    pass
            
            return ProcedureInfo(
                procedure=procedure,
                scorecard_name=scorecard_name,
                score_name=score_name
            )
            
        except Exception as e:
            logger.error(f"Error getting procedure info for {procedure_id}: {str(e)}")
            return None
    
    def list_procedures(
        self, 
        account_identifier: str, 
        scorecard_identifier: Optional[str] = None,
        limit: int = 100
    ) -> List[Procedure]:
        """List procedures for an account, optionally filtered by scorecard.
        
        Args:
            account_identifier: Account ID, key, or name
            scorecard_identifier: Optional scorecard ID, key, or name to filter by
            limit: Maximum number of experiments to return
            
        Returns:
            List of Procedure instances ordered by most recent first
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
                return Procedure.list_by_scorecard(scorecard_id, self.client, limit)
            else:
                # List all for account
                return Procedure.list_by_account(account_id, self.client, limit)
                
        except Exception as e:
            logger.error(f"Error listing experiments: {str(e)}")
            return []
    
    def delete_procedure(self, procedure_id: str) -> Tuple[bool, str]:
        """Delete an procedure.
        
        Args:
            procedure_id: ID of the procedure to delete
            
        Returns:
            Tuple of (success, message)
        """
        try:
            procedure = Procedure.get_by_id(procedure_id, self.client)

            # Delete the experiment
            success = procedure.delete()
            
            if success:
                logger.info(f"Successfully deleted procedure {procedure_id}")
                return True, f"Deleted procedure {procedure_id}"
            else:
                return False, f"Failed to delete procedure {procedure_id}"
                
        except Exception as e:
            logger.error(f"Error deleting procedure {procedure_id}: {str(e)}")
            return False, f"Error deleting experiment: {str(e)}"
    
    def update_procedure_config(
        self, 
        procedure_id: str, 
        yaml_config: str,
        note: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Update a procedure's configuration.
        
        Args:
            procedure_id: ID of the experiment
            yaml_config: New YAML configuration
            note: Optional note for the version
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate YAML
            try:
                yaml_data = yaml.safe_load(yaml_config)
                # Enhanced validation - check for required structure
                if not _validate_yaml_template(yaml_data):
                    return False, "YAML configuration is invalid for its procedure class. Tactus requires class/name/version/code; SOPAgent requires class/prompts."
            except yaml.YAMLError as e:
                return False, f"Invalid YAML configuration: {str(e)}"
            
            procedure = Procedure.get_by_id(procedure_id, self.client)
            procedure.update(code=yaml_config)

            logger.info(f"Updated procedure configuration for procedure {procedure_id}")
            return True, "Updated procedure configuration"
            
        except Exception as e:
            logger.error(f"Error updating procedure config: {str(e)}")
            return False, f"Error updating configuration: {str(e)}"
    
    def get_procedure_yaml(self, procedure_id: str) -> Optional[str]:
        """Get the YAML configuration for a procedure.
        
        Priority order:
        1. Procedure.code field (directly stored YAML)
        2. Procedure.templateId -> ProcedureTemplate
        3. Account default template
        
        Args:
            procedure_id: ID of the procedure
            
        Returns:
            YAML configuration string, or None if not found
        """
        builtin_yaml = get_builtin_procedure_yaml(procedure_id)
        if builtin_yaml:
            logger.info(f"Using built-in YAML configuration for {procedure_id}")
            return builtin_yaml

        try:
            procedure = Procedure.get_by_id(procedure_id, self.client)
            if not procedure:
                return None
            
            # FIRST: Check if procedure has code directly stored
            if hasattr(procedure, 'code') and procedure.code:
                logger.info(f"Using YAML from Procedure.code field for {procedure_id}")
                return procedure.code
            
            # SECOND: Get template if procedure has one
            # NOTE: templateId was renamed to parentProcedureId
            parent_id = getattr(procedure, 'parentProcedureId', None) or getattr(procedure, 'templateId', None)
            if parent_id:
                template = ProcedureTemplate.get_by_id(parent_id, self.client)
                if template:
                    logger.info(f"Using YAML from parent template {parent_id} for {procedure_id}")
                    return template.get_template_content()
            
            # THIRD: Fallback to account default template
            template = ProcedureTemplate.get_default_for_account(
                procedure.accountId, self.client, "hypothesis_generation"
            )
            if template:
                logger.info(f"Using YAML from account default template for {procedure_id}")
                return template.get_template_content()
            
            logger.warning(f"No YAML configuration found for procedure {procedure_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting procedure YAML: {str(e)}")
            return None

    def get_experiment_yaml(self, procedure_id: str) -> Optional[str]:
        """Backward-compatible alias for callers still using older naming."""
        return self.get_procedure_yaml(procedure_id)

    def test_procedure_specs(
        self,
        procedure_id: Optional[str] = None,
        yaml_config: Optional[str] = None,
        mode: str = 'mock',
        scenario: Optional[str] = None,
        parallel: bool = True,
        workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run embedded Tactus Specification blocks for a procedure.

        Exactly one of procedure_id or yaml_config must be provided.
        """
        if bool(procedure_id) == bool(yaml_config):
            raise ValueError("Provide exactly one of procedure_id or yaml_config.")

        if mode not in {'mock', 'integration'}:
            raise ValueError("Invalid mode. Expected one of: mock, integration.")

        yaml_text = yaml_config
        if procedure_id:
            yaml_text = self.get_procedure_yaml(procedure_id)
            if not yaml_text:
                raise ValueError(f"Could not load YAML for procedure {procedure_id}.")

        try:
            config = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML configuration: {exc}") from exc

        if not isinstance(config, dict):
            raise ValueError("Invalid YAML configuration: root must be a mapping.")

        procedure_class = config.get('class')
        if procedure_class != 'Tactus':
            raise ValueError(
                f"Procedure class must be 'Tactus' for spec testing (found: {procedure_class!r})."
            )

        tactus_code = config.get('code')
        if not isinstance(tactus_code, str) or not tactus_code.strip():
            raise ValueError("Tactus procedure YAML must contain a non-empty 'code' field.")

        from tactus.validation.validator import TactusValidator, ValidationMode

        validator = TactusValidator()
        validation_result = validator.validate(tactus_code, mode=ValidationMode.FULL)
        if not validation_result.valid:
            formatted_errors = []
            for err in validation_result.errors:
                location = f" @ {err.location}" if getattr(err, 'location', None) else ''
                formatted_errors.append(f"- {err.message}{location}")
            details = "\n".join(formatted_errors) if formatted_errors else "- Unknown validation error"
            raise ValueError(f"Tactus validation failed:\n{details}")

        registry = validation_result.registry
        gherkin_spec = getattr(registry, 'gherkin_specifications', None) if registry else None
        if not gherkin_spec or not str(gherkin_spec).strip():
            raise ValueError("No embedded Specification([[ ... ]]) block found in Tactus code.")

        from tactus.testing.test_runner import TactusTestRunner
        from unittest.mock import patch as patch_object

        temp_file_path: Optional[Path] = None
        runner = None
        start = time.time()

        try:
            with tempfile.NamedTemporaryFile('w', suffix='.tac', delete=False) as handle:
                handle.write(tactus_code)
                temp_file_path = Path(handle.name)

            runner = TactusTestRunner(
                procedure_file=temp_file_path,
                mocked=(mode == 'mock'),
            )
            runner.setup(gherkin_spec)

            cpu_context = nullcontext()
            if workers is not None and workers > 0 and parallel:
                cpu_context = patch_object(
                    'tactus.testing.test_runner.os.cpu_count',
                    return_value=max(1, workers),
                )

            with cpu_context:
                raw_result = runner.run_tests(
                    parallel=parallel,
                    scenario_filter=scenario,
                )
        except ValueError:
            raise
        except Exception as exc:
            if mode == 'integration':
                raise RuntimeError(
                    f"Integration spec run failed. Check LLM/tool credentials and MCP connectivity: {exc}"
                ) from exc
            raise RuntimeError(f"Spec run failed: {exc}") from exc
        finally:
            if runner is not None:
                try:
                    runner.cleanup()
                except Exception:
                    logger.debug("Failed to cleanup Tactus test runner", exc_info=True)
            if temp_file_path and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except Exception:
                    logger.debug("Failed to delete temporary Tactus file", exc_info=True)

        features: List[Dict[str, Any]] = []
        for feature in raw_result.features:
            scenarios: List[Dict[str, Any]] = []
            for scenario_result in feature.scenarios:
                steps: List[Dict[str, Any]] = []
                failed_step_messages: List[str] = []
                for step in scenario_result.steps:
                    step_payload = {
                        'keyword': step.keyword,
                        'message': step.message,
                        'status': step.status,
                        'duration': step.duration,
                    }
                    if step.error_message:
                        step_payload['error_message'] = step.error_message
                        failed_step_messages.append(
                            f"{step.keyword} {step.message}: {step.error_message}"
                        )
                    steps.append(step_payload)

                scenarios.append({
                    'name': scenario_result.name,
                    'status': scenario_result.status,
                    'duration': scenario_result.duration,
                    'steps': steps,
                    'failed_step_messages': failed_step_messages,
                })

            features.append({
                'name': feature.name,
                'description': feature.description,
                'status': feature.status,
                'duration': feature.duration,
                'scenarios': scenarios,
            })

        return {
            'success': raw_result.failed_scenarios == 0,
            'mode': mode,
            'summary': {
                'total_scenarios': raw_result.total_scenarios,
                'passed_scenarios': raw_result.passed_scenarios,
                'failed_scenarios': raw_result.failed_scenarios,
                'duration_seconds': raw_result.total_duration,
            },
            'features': features,
            'metadata': {
                'procedure_id': procedure_id,
                'scenario_filter': scenario,
                'parallel': parallel,
                'workers': workers,
                'wall_time_seconds': round(time.time() - start, 3),
            },
        }

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
            query GetScoresByScorecard($scorecardId: ID!) {
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
    
    async def run_experiment(self, procedure_id: str, **options) -> Dict[str, Any]:
        """
        Run an procedure with the given ID.

        This function executes an procedure with MCP tool support, allowing the experiment
        to provide AI models with access to Plexus MCP tools during execution.

        Args:
            procedure_id: ID of the procedure to run
            **options: Optional parameters for procedure execution:
                - max_iterations: Maximum number of iterations (int)
                - timeout: Timeout in seconds (int)
                - async_mode: Whether to run asynchronously (bool)
                - dry_run: Whether to perform a dry run (bool)
                - enable_mcp: Whether to enable MCP tools (bool, default True)
                - mcp_tools: List of MCP tool categories to enable (list)
                
        Returns:
            Dictionary containing:
                - procedure_id: The procedure ID
                - status: Current status ('running', 'completed', 'error', 'initiated')
                - message: Human-readable status message
                - error: Error message if applicable
                - run_id: Unique run identifier (future)
                - progress: Progress information (future)
                - mcp_info: Information about MCP tools if enabled
        """
        logger.info(f"Starting procedure run for procedure ID: {procedure_id}")
        
        # Input validation
        if not procedure_id or not isinstance(procedure_id, str):
            error_msg = "Invalid procedure ID: must be a non-empty string"
            logger.error(error_msg)
            return {
                'procedure_id': procedure_id,
                'status': 'error',
                'error': error_msg
            }

        try:
            built_in_procedure = is_builtin_procedure_id(procedure_id)
            procedure_info = None
            if built_in_procedure:
                logger.info(f"Running built-in procedure: {procedure_id}")
            else:
                # Get procedure details to validate it exists
                procedure_info = self.get_procedure_info(procedure_id)
                if not procedure_info:
                    error_msg = f"Procedure not found: {procedure_id}"
                    logger.error(error_msg)
                    return {
                        'procedure_id': procedure_id,
                        'status': 'error',
                        'error': error_msg
                    }

                logger.info(f"Found experiment: {procedure_id} (Scorecard: {procedure_info.scorecard_name})")

            # Check if this is a Tactus procedure and route accordingly
            yaml_config = self.get_procedure_yaml(procedure_id)
            if yaml_config:
                import yaml as yaml_lib
                try:
                    config = yaml_lib.safe_load(yaml_config)
                    procedure_class = config.get('class') if isinstance(config, dict) else None

                    if procedure_class == 'Tactus':
                        logger.info(f"Routing procedure {procedure_id} to Tactus runtime")

                        account_id = options.get('account_id')
                        if not account_id:
                            try:
                                account_id = self.client._resolve_account_id()
                            except Exception:
                                account_id = None

                        scorecard_id = procedure_info.procedure.scorecardId if procedure_info else None
                        score_id = procedure_info.procedure.scoreId if procedure_info else None

                        # Build context with procedure info
                        context = {
                            'procedure_id': procedure_id,
                            'scorecard_name': procedure_info.scorecard_name if procedure_info else None,
                            'score_name': procedure_info.score_name if procedure_info else None,
                            'scorecard_id': scorecard_id,
                            'score_id': score_id,
                        }
                        if account_id:
                            context['account_id'] = account_id

                        # Console chat runs can provide explicit trigger text/history
                        # captured at dispatch time; pass these through directly so
                        # detached worker execution preserves continuity.
                        console_user_message = options.get('console_user_message')
                        if isinstance(console_user_message, str) and console_user_message.strip():
                            context['console_user_message'] = console_user_message.strip()
                        console_session_history = options.get('console_session_history')
                        if isinstance(console_session_history, list) and console_session_history:
                            context['console_session_history'] = console_session_history

                        # Merge user-provided context (from CLI) into procedure context
                        user_context = options.pop('context', None)
                        if isinstance(user_context, dict):
                            context.update(user_context)

                        # Expose task_id so the Stage.set() MCP tool can update the dashboard
                        task_id_for_tracking = options.get('_task_id_for_stage_tracking')
                        if task_id_for_tracking:
                            context['task_id'] = task_id_for_tracking

                        rubric_memory_briefing = await self._build_optimizer_rubric_memory_briefing(
                            context
                        )
                        if rubric_memory_briefing:
                            context['rubric_memory_briefing'] = rubric_memory_briefing

                        from .procedure_executor import execute_procedure
                        enable_mcp = bool(options.pop('enable_mcp', True))
                        mcp_server = None
                        if enable_mcp:
                            from .mcp_transport import create_procedure_mcp_server
                            mcp_server = await create_procedure_mcp_server(
                                experiment_context=context
                            )

                        result = await execute_procedure(
                            procedure_id=procedure_id,
                            procedure_code=yaml_config,
                            client=self.client,
                            mcp_server=mcp_server,
                            context=context,
                            **options
                        )

                        return result

                    if procedure_class == 'LuaDSL':
                        return {
                            'procedure_id': procedure_id,
                            'status': 'error',
                            'error': "Unsupported procedure class: LuaDSL."
                        }

                except Exception as e:
                    logger.warning(f"Error checking procedure class: {e}, falling back to SOP Agent")

            if built_in_procedure:
                return {
                    'procedure_id': procedure_id,
                    'status': 'error',
                    'error': f"Built-in procedure {procedure_id} must define class: Tactus."
                }

            return {
                'procedure_id': procedure_id,
                'status': 'error',
                'error': "Unsupported procedure class: only class: Tactus procedures are supported. Legacy node-backed SOP procedures have been removed."
            }

        except Exception as e:
            error_msg = f"Error running procedure {procedure_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'procedure_id': procedure_id,
                'status': 'error',
                'error': error_msg
            }
    
    async def _ensure_procedure_structure(self, procedure_info: 'ProcedureInfo', score_version_id: Optional[str] = None) -> None:
        """Procedure structure is stored directly on the Procedure record."""
        return None

    async def _get_champion_score_config(self, score_id: str) -> Optional[str]:
        """Get the champion (current) YAML configuration for a score."""
        try:
            from plexus.dashboard.api.models.score import Score
            
            score = Score.get_by_id(score_id, self.client)
            if not score:
                logger.error(f"Score {score_id} not found")
                return None
            
            champion_config = score.get_champion_configuration_yaml()
            if champion_config:
                logger.info(f"Retrieved champion configuration for score {score_id}")
                return champion_config
            else:
                logger.warning(f"No champion configuration found for score {score_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting champion score config for {score_id}: {e}")
            return None
    
    async def _get_score_version_config(self, score_version_id: str) -> Optional[str]:
        """Get the YAML configuration for a specific score version."""
        try:
            # Fetch the specific version's configuration via GraphQL query
            query = f"""
            query GetScoreVersionCode {{
                getScoreVersion(id: "{score_version_id}") {{
                    id
                    configuration
                }}
            }}
            """

            result = self.client.execute(query)
            if not result or 'getScoreVersion' not in result or not result['getScoreVersion']:
                logger.error(f"Score version {score_version_id} not found")
                return None

            configuration = result['getScoreVersion'].get('configuration')
            if configuration:
                logger.info(f"Retrieved configuration for score version {score_version_id}")
                return configuration
            else:
                logger.warning(f"No configuration found for score version {score_version_id}")
                return None

        except Exception as e:
            logger.error(f"Error getting score version config for {score_version_id}: {e}")
            return None
    
    async def _get_feedback_alignment_docs(self) -> Optional[str]:
        """Get the feedback alignment documentation."""
        try:
            # Read the documentation file directly since MCP tools are async and require server context
            import os
            
            # Navigate to the plexus docs directory
            current_dir = os.path.dirname(os.path.abspath(__file__))  # experiment/
            cli_dir = os.path.dirname(current_dir)  # cli/
            plexus_dir = os.path.dirname(cli_dir)  # plexus/
            docs_dir = os.path.join(plexus_dir, "docs")
            file_path = os.path.join(docs_dir, "feedback-alignment.md")
            
            logger.info(f"Reading documentation file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            logger.info(f"Successfully read feedback alignment documentation ({len(content)} characters)")
            return content
            
        except FileNotFoundError:
            logger.warning(f"Feedback alignment documentation not found at {file_path}")
            return "# Feedback Alignment Documentation\nDocumentation not available - proceed with general analysis principles."
        except Exception as e:
            logger.error(f"Error getting feedback alignment docs: {e}")
            return "# Feedback Alignment Documentation\nDocumentation not available - proceed with general analysis principles."
    
    async def _get_score_yaml_format_docs(self) -> Optional[str]:
        """Get the score YAML format documentation."""
        try:
            # Read the documentation file directly since MCP tools are async and require server context
            import os
            
            # Navigate to the plexus docs directory
            current_dir = os.path.dirname(os.path.abspath(__file__))  # experiment/
            cli_dir = os.path.dirname(current_dir)  # cli/
            plexus_dir = os.path.dirname(cli_dir)  # plexus/
            docs_dir = os.path.join(plexus_dir, "docs")
            file_path = os.path.join(docs_dir, "score-yaml-format.md")
            
            logger.info(f"Reading documentation file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            logger.info(f"Successfully read score YAML format documentation ({len(content)} characters)")
            return content
            
        except FileNotFoundError:
            logger.warning(f"Score YAML format documentation not found at {file_path}")
            return "# Score YAML Format Documentation\nDocumentation not available - proceed with general score configuration principles."
        except Exception as e:
            logger.error(f"Error getting score YAML format docs: {e}")
            return "# Score YAML Format Documentation\nDocumentation not available - proceed with general score configuration principles."
    
    async def _run_evaluation_for_procedure(
        self,
        procedure_id: str,
        scorecard_name: str,
        score_name: str,
        score_version_id: Optional[str],
        account_id: str,
        parameter_values: Dict[str, Any],
        n_samples: int = 50
    ) -> str:
        """
        Run an evaluation to establish baseline performance for the procedure.

        This replaces the feedback summary approach with actual evaluation data,
        providing the AI agent with quantitative metrics and confusion matrix results.

        Args:
            scorecard_name: Name of the scorecard
            score_name: Name of the score
            score_version_id: Optional specific score version to evaluate
            account_id: Account ID
            parameter_values: Parsed parameter values from YAML
            n_samples: Number of samples to evaluate (default 50)

        Returns:
            Formatted string with evaluation results for procedure context
        """
        try:
            from plexus.cli.shared.evaluation_runner import run_accuracy_evaluation
            from plexus.cli.shared import get_score_yaml_path
            import json
            import os

            logger.info(f"Running evaluation: {scorecard_name}/{score_name} (version: {score_version_id or 'champion'}, samples: {n_samples})")

            # If a specific version is specified, write it to local YAML first
            if score_version_id:
                logger.info(f"Writing score version {score_version_id} to local YAML before evaluation")
                try:
                    # Get the version configuration
                    version_config = await self._get_score_version_config(score_version_id)
                    if not version_config:
                        raise RuntimeError(f"Could not retrieve configuration for score version {score_version_id}")

                    # Write to local YAML file
                    yaml_path = get_score_yaml_path(scorecard_name, score_name)
                    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)

                    with open(yaml_path, 'w') as f:
                        f.write(version_config)

                    logger.info(f"Successfully wrote version {score_version_id} to {yaml_path}")
                except Exception as e:
                    logger.error(f"Failed to write score version {score_version_id}: {e}")
                    raise RuntimeError(f"Cannot run evaluation: failed to write score version {score_version_id}")

            # Run the evaluation using the shared runner
            # It will use the local YAML file we just wrote
            evaluation_result = await run_accuracy_evaluation(
                scorecard_name=scorecard_name,
                score_name=score_name,
                number_of_samples=n_samples,
                sampling_method="random",
                procedure_id=procedure_id,
                fresh=True,
                use_yaml=True  # Use local YAML configuration
            )

            # Return evaluation results as JSON - same format as MCP tool
            # This is token-efficient and contains all necessary information
            logger.info("Evaluation completed successfully")
            return json.dumps(evaluation_result, indent=2)

        except Exception as e:
            logger.error(f"Error running evaluation for procedure: {e}", exc_info=True)
            error_result = {
                "error": str(e),
                "message": "Error running evaluation - procedure cannot proceed without baseline metrics"
            }
            return json.dumps(error_result, indent=2)
    
    
    async def _get_feedback_summary(self, scorecard_name: str, score_name: str, account_id: str, days: int = 7) -> Optional[str]:
        """Get feedback summary for the last N days."""
        try:
            # Use the feedback service directly to get the same data as the MCP tool
            from plexus.cli.feedback.feedback_service import FeedbackService
            from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier
            
            # Resolve scorecard and get scorecard/score IDs
            scorecard_id = resolve_scorecard_identifier(self.client, scorecard_name)
            if not scorecard_id:
                logger.warning(f"Could not resolve scorecard: {scorecard_name}")
                return f"# Feedback Summary\nError: Scorecard '{scorecard_name}' not found."
            
            # Account ID is passed in from the procedure context
            if not account_id:
                logger.warning("No account ID provided to feedback summary")
                return f"# Feedback Summary\nError: No account ID provided."
            
            # Find the score ID within the scorecard (same logic as MCP tool)
            scorecard_query = f"""
            query GetScorecardWithScores {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                    sections {{
                        items {{
                            scores {{
                                items {{
                                    id
                                    name
                                    key
                                    externalId
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            response = self.client.execute(scorecard_query)
            scorecard_data = response.get('getScorecard')
            if not scorecard_data:
                return f"# Feedback Summary\nError: Could not retrieve scorecard data."
            
            # Find score using same matching logic as MCP tool
            score_match = None
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    if (score.get('id') == score_name or 
                        score.get('name', '').lower() == score_name.lower() or 
                        score.get('key') == score_name or 
                        score.get('externalId') == score_name or
                        score_name.lower() in score.get('name', '').lower()):
                        score_match = score
                        break
                if score_match:
                    break
            
            if not score_match:
                return f"# Feedback Summary\nError: Score '{score_name}' not found in scorecard '{scorecard_data['name']}'."
            
            # Generate summary using the shared service (same as MCP tool)
            summary_result = await FeedbackService.summarize_feedback(
                client=self.client,
                scorecard_name=scorecard_data['name'],
                score_name=score_match['name'],
                scorecard_id=scorecard_data['id'],
                score_id=score_match['id'],
                account_id=account_id,
                days=days
            )
            
            # Format the structured data for procedure consumption
            return self._format_feedback_summary_for_experiment(
                summary_result, 
                scorecard_data['name'], 
                score_match['name'], 
                days
            )
            
        except Exception as e:
            logger.error(f"Error getting feedback summary: {e}")
            return f"# Feedback Summary\nError retrieving feedback data: {str(e)}"
    
    def _format_feedback_summary_for_experiment(self, summary_result, scorecard_name: str, score_name: str, days: int) -> str:
        """Format feedback summary result for procedure context consumption."""
        from datetime import datetime
        
        # Extract structured data from the result
        analysis = summary_result.analysis
        confusion_matrix = analysis.get('confusion_matrix', {})
        total_items = analysis.get('total_items', 0)
        accuracy = analysis.get('accuracy', 0)
        ac1 = analysis.get('ac1', 0)
        
        # Build clean, focused format for confusion matrix interpretation
        feedback_alignment = f"""## FEEDBACK ANALYSIS - CONFUSION MATRIX DATA

**Scorecard:** {scorecard_name}
**Score:** {score_name}
**Period:** Last {days} days (Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')})

### KEY METRICS
- **Total Feedback Items:** {total_items}
- **Accuracy:** {accuracy:.1f}%
- **Agreement (AC1):** {ac1:.2f}

### CONFUSION MATRIX - SCORING CORRECTIONS
"""

        # Parse confusion matrix data
        if confusion_matrix and 'matrix' in confusion_matrix:
            labels = confusion_matrix.get('labels', [])
            matrix = confusion_matrix.get('matrix', [])
            
            feedback_alignment += "**Error Patterns (AI Prediction → Human Correction):**\n\n"
            
            total_errors = 0
            error_details = []
            
            for row in matrix:
                actual_label = row.get('actualClassLabel', '')
                predicted_counts = row.get('predictedClassCounts', {})
                
                for predicted_label, count in predicted_counts.items():
                    if actual_label != predicted_label and count > 0:
                        # This is an error - AI predicted wrong
                        error_details.append((predicted_label, actual_label, count))
                        total_errors += count
                        feedback_alignment += f"- **{predicted_label} → {actual_label}:** {count} corrections (AI said '{predicted_label}', human corrected to '{actual_label}')\n"
            
            if total_errors == 0:
                feedback_alignment += "- No scoring errors found in this period\n"
            
            feedback_alignment += f"\n**Total Corrections:** {total_errors}\n"
            
            # Add correct predictions summary
            feedback_alignment += "\n**Correct Predictions (for context):**\n"
            for row in matrix:
                actual_label = row.get('actualClassLabel', '')
                predicted_counts = row.get('predictedClassCounts', {})
                correct_count = predicted_counts.get(actual_label, 0)
                if correct_count > 0:
                    feedback_alignment += f"- **{actual_label} → {actual_label}:** {correct_count} correct\n"
        
        feedback_alignment += f"""

### ANALYSIS PRIORITIES
Based on this data, you should prioritize examining error types with the highest correction counts first.

### NEXT STEPS
1. Interpret these patterns - which errors are most frequent?
2. Use plexus_feedback_find to examine ALL examples of the most common errors
3. Sample 1-2 correct predictions for context only
"""
        
        logger.info(f"Retrieved feedback summary for {scorecard_name}/{score_name} (last {days} days)")
        return feedback_alignment

    async def _build_optimizer_rubric_memory_briefing(
        self,
        experiment_context: Dict[str, Any],
    ) -> Optional[str]:
        """Generate optional score-level rubric-memory briefing for optimizer prompts."""
        scorecard_name = experiment_context.get('scorecard_name')
        score_name = experiment_context.get('score_name')
        score_id = experiment_context.get('score_id')
        if not scorecard_name or not score_name or not score_id:
            return None
        try:
            from plexus.rubric_memory import RubricMemoryContextProvider

            provider = RubricMemoryContextProvider(api_client=self.client)
            status = provider.local_corpus_status(
                scorecard_identifier=scorecard_name,
                score_identifier=score_name,
            )
            if not status["available"]:
                logger.warning(
                    "Rubric memory not available for optimizer briefing; missing canonical folders: %s",
                    ", ".join(
                        root["path"] for root in status["roots"] if not root["exists"]
                    ),
                )
                return None
            context = await provider.generate_for_score_item(
                scorecard_identifier=scorecard_name,
                score_identifier=score_name,
                score_id=score_id,
                topic_hint="Score-level optimizer rubric-memory briefing",
            )
            return context.markdown_context
        except Exception as exc:
            logger.warning("Could not build optimizer rubric-memory briefing: %s", exc)
            return None
    
    def _reset_procedure_to_start(self, procedure_id: str, account_id: str) -> bool:
        """
        Reset a procedure's TaskStages back to START state.

        This resets all TaskStages to PENDING so the procedure can restart from the beginning.

        Args:
            procedure_id: The procedure ID
            account_id: The account ID

        Returns:
            True if successful, False otherwise
        """
        try:
            from plexus.dashboard.api.models.task import Task
            import json

            logger.info(f"Resetting procedure {procedure_id} TaskStages to START state")

            # Find the task for this procedure
            query = """
            query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $limit: Int) {
                listTaskByAccountIdAndUpdatedAt(accountId: $accountId, limit: $limit) {
                    items {
                        id
                        target
                        metadata
                    }
                }
            }
            """

            result = self.client.execute(query, {"accountId": account_id, "limit": 1000})
            tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

            # Find task for this procedure
            task_id = None
            for task_data in tasks:
                try:
                    metadata = json.loads(task_data.get('metadata', '{}')) if isinstance(task_data.get('metadata'), str) else task_data.get('metadata', {})
                    if metadata.get('procedure_id') == procedure_id:
                        task_id = task_data['id']
                        break
                except:
                    continue

            if not task_id:
                logger.warning(f"No Task found for procedure {procedure_id} - skipping state reset")
                return False

            # Get task and reset its status
            task = Task.get_by_id(task_id, self.client)
            task.update(status='PENDING', errorMessage=None, errorDetails=None)

            # Reset all TaskStages to PENDING
            stages_query = """
            query ListTaskStageByTaskId($taskId: ID!) {
                listTaskStageByTaskId(taskId: $taskId) {
                    items {
                        id
                    }
                }
            }
            """

            stages_result = self.client.execute(stages_query, {"taskId": task_id})
            stages = stages_result.get('listTaskStageByTaskId', {}).get('items', [])

            for stage in stages:
                mutation = """
                mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
                    updateTaskStage(input: $input) {
                        id
                        status
                    }
                }
                """
                self.client.execute(mutation, {
                    "input": {
                        "id": stage['id'],
                        "status": "PENDING",
                        "startedAt": None,
                        "completedAt": None
                    }
                })

            logger.info(f"✓ Reset {len(stages)} TaskStages to PENDING for procedure {procedure_id}")
            return True

        except Exception as e:
            logger.error(f"Error resetting procedure state: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _update_procedure_state(self, procedure_id: str, new_state: str, current_state: Optional[str] = None) -> bool:
        """
        Update the state of a procedure using state machine validation.

        Args:
            procedure_id: The procedure ID
            new_state: The new state value
            current_state: The current state (if None, reads from Procedure.state)

        Returns:
            True if successful, False otherwise
        """
        from .state_machine import create_state_machine

        try:
            # Get current procedure
            procedure = Procedure.get_by_id(procedure_id, self.client)
            if not procedure:
                logger.error(f"Procedure {procedure_id} not found")
                return False

            # Use provided current_state or fall back to reading from TaskStages
            if current_state is None:
                # TaskStages are the source of truth for state
                current_state = self._get_current_state_from_task_stages(procedure_id, procedure.accountId)
                logger.info(f"[DEBUG] No current_state provided, reading from TaskStages: {current_state}")
                if current_state is None:
                    current_state = 'start'  # Default to start if no TaskStages exist
                    logger.info(f"[DEBUG] No TaskStages found, defaulting to 'start'")
            else:
                logger.info(f"[DEBUG] Using provided current_state: {current_state}")

            # Create state machine and validate transition
            logger.info(f"[DEBUG] Creating state machine with client: {self.client}")
            sm = create_state_machine(procedure_id, current_state, self.client)
            logger.info(f"[DEBUG] State machine created, sm.client = {sm.client}")
            
            # Map state transitions to event names (hardcoded to avoid executing callbacks twice)
            transition_map = {
                ('start', 'evaluation'): 'begin',
                (None, 'evaluation'): 'begin',  # None is treated as start
                ('evaluation', 'hypothesis'): 'analyze',
                ('hypothesis', 'test'): 'start_testing',
                ('test', 'insights'): 'analyze_results',
                ('insights', 'hypothesis'): 'continue_iteration',  # NEW: Loop back for next round
                ('insights', 'completed'): 'finish_from_insights',
                ('hypothesis', 'completed'): 'finish_from_hypothesis',
                ('hypothesis', 'error'): 'fail_from_hypothesis',
                ('test', 'error'): 'fail_from_test',
                ('insights', 'error'): 'fail_from_insights',
                ('evaluation', 'error'): 'fail_from_evaluation',
                ('error', 'evaluation'): 'retry_from_error',
                ('error', 'start'): 'restart_from_error',
            }

            transition_key = (current_state, new_state)
            transition_name = transition_map.get(transition_key)

            if not transition_name:
                logger.error(f"Invalid state transition from {current_state} to {new_state}")
                logger.error(f"Valid transitions from {current_state}: {[k for k in transition_map.keys() if k[0] == current_state]}")
                return False
            
            # Execute the transition (this will run callbacks and validate)
            # The state machine callbacks handle updating TaskStages, which are the source of truth
            try:
                getattr(sm, transition_name)()
                logger.info(f"State machine transition executed: {transition_name} ({current_state} → {new_state})")
                return True
            except Exception as e:
                logger.error(f"State machine transition failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating procedure state: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_current_state_from_task_stages(self, procedure_id: str, account_id: str) -> Optional[str]:
        """
        Get the current state of a procedure by examining its TaskStages.

        TaskStages are the source of truth for procedure state. This method finds
        the Task for this procedure and determines the current state based on
        which TaskStage is currently RUNNING or the last COMPLETED stage.

        Args:
            procedure_id: The procedure ID
            account_id: The account ID

        Returns:
            The current state name (lowercase: "start", "evaluation", "hypothesis", "test", "insights")
            or None if no Task/TaskStages exist
        """
        try:
            from plexus.dashboard.api.models.task import Task

            # Find the Task for this procedure using GSI on accountId
            # Use listTaskByAccountIdAndUpdatedAt which is indexed
            from datetime import datetime, timezone, timedelta

            query = """
            query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int, $nextToken: String) {
                listTaskByAccountIdAndUpdatedAt(accountId: $accountId, updatedAt: $updatedAt, limit: $limit, nextToken: $nextToken) {
                    items {
                        id
                        target
                    }
                    nextToken
                }
            }
            """

            # Query ALL tasks for this account (no date filter to avoid GSI lag issues)
            # Start from a very old date to get everything
            very_old_date = "2000-01-01T00:00:00.000Z"

            tasks = []
            next_token = None
            target_patterns = [f"procedure/run/{procedure_id}", f"procedure/{procedure_id}"]

            while True:
                variables = {
                    "accountId": account_id,
                    "updatedAt": {"ge": very_old_date},  # Get all tasks
                    "limit": 1000
                }
                if next_token:
                    variables["nextToken"] = next_token

                result = self.client.execute(query, variables)
                page_tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

                # Check this page for matching tasks
                for task in page_tasks:
                    if any(pattern in task['target'] for pattern in target_patterns):
                        tasks.append(task)

                # If we found our task, stop scanning
                if tasks:
                    logger.info(f"Found {len(tasks)} tasks matching procedure ID '{procedure_id}'")
                    break

                next_token = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('nextToken')
                if not next_token:
                    break

            if not tasks:
                logger.warning(f"No Task found for procedure {procedure_id} in account {account_id}")


            # Find exact match - check both formats
            # TaskProgressTracker uses "procedure/run/{id}" format
            # ProcedureService._get_or_create_task uses "procedure/{id}" format
            task_id = None
            for task_data in tasks:
                if task_data['target'] == f"procedure/run/{procedure_id}" or task_data['target'] == f"procedure/{procedure_id}":
                    task_id = task_data['id']
                    logger.info(f"Found Task {task_id} with target: {task_data['target']}")
                    break

            if not task_id:
                logger.warning(f"No Task found for procedure {procedure_id}, cannot determine state from TaskStages")
                return None

            # Get TaskStages for this task
            stage_query = """
            query GetTask($id: ID!) {
                getTask(id: $id) {
                    stages {
                        items {
                            id
                            name
                            status
                            order
                        }
                    }
                }
            }
            """

            result = self.client.execute(stage_query, {"id": task_id})
            stages = result.get('getTask', {}).get('stages', {}).get('items', [])

            if not stages:
                logger.warning(f"Task {task_id} has no TaskStages")
                return None

            # Sort stages by order
            stages.sort(key=lambda s: s['order'])

            # Find the current state:
            # 1. If any stage is RUNNING, that's the current state
            # 2. Otherwise, find the last COMPLETED stage and return the next one
            # 3. If all are PENDING, we're at the start

            running_stage = None
            last_completed_stage = None
            last_completed_order = -1

            for stage in stages:
                if stage['status'] == 'RUNNING':
                    running_stage = stage
                    break
                elif stage['status'] == 'COMPLETED' and stage['order'] > last_completed_order:
                    last_completed_stage = stage
                    last_completed_order = stage['order']

            if running_stage:
                # Convert stage name to lowercase state
                return running_stage['name'].lower()
            elif last_completed_stage:
                # Find the next stage after the last completed one
                next_order = last_completed_order + 1
                for stage in stages:
                    if stage['order'] == next_order:
                        return stage['name'].lower()
                # If no next stage, we're at the end
                return "completed"
            else:
                # All stages are PENDING, we're at the first stage
                return stages[0]['name'].lower() if stages else None

        except Exception as e:
            logger.error(f"Error getting current state from TaskStages: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _get_evaluation_results(self, evaluation_id: str) -> str:
        """Retrieve evaluation results by ID."""
        try:
            from plexus.Evaluation import Evaluation
            import json

            eval_obj = Evaluation.get_by_id(evaluation_id, self.client)
            if not eval_obj:
                logger.error(f"Evaluation {evaluation_id} not found")
                return '{"error": "Evaluation not found"}'

            # Format evaluation results as JSON string
            results = {
                'evaluation_id': evaluation_id,
                'accuracy': eval_obj.accuracy,
                'ac1': getattr(eval_obj, 'ac1', None),
                'confusion_matrix': getattr(eval_obj, 'confusionMatrix', None),
                'precision': getattr(eval_obj, 'precision', None),
                'recall': getattr(eval_obj, 'recall', None),
                'status': eval_obj.status
            }

            logger.info(f"✓ Retrieved evaluation results for {evaluation_id}: accuracy={results['accuracy']}")
            return json.dumps(results)

        except Exception as e:
            logger.error(f"Failed to retrieve evaluation results: {e}")
            return '{"error": "Failed to retrieve evaluation results"}'

    def _get_or_create_task_with_stages_for_procedure(
        self,
        procedure_id: str,
        account_id: str,
        scorecard_id: Optional[str] = None,
        score_id: Optional[str] = None,
        stage_configs: Optional[Dict[str, Any]] = None,
    ) -> Optional['Task']:
        """
        Get or create a Task with stages based on the procedure's state machine.

        This method reuses existing Tasks for a procedure if they exist, otherwise
        creates a new Task record and TaskStage records for each state in the
        procedure's state machine workflow.

        Args:
            procedure_id: The procedure ID
            account_id: The account ID
            scorecard_id: Optional scorecard ID
            score_id: Optional score ID

        Returns:
            The existing or created Task object, or None if creation failed
        """
        from plexus.dashboard.api.models.task import Task
        from .state_machine_stages import get_stages_from_state_machine
        import json
        from datetime import datetime, timezone

        try:
            # First, check if a Task already exists for this procedure
            # Use the indexed query listTaskByAccountIdAndUpdatedAt
            query = """
            query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int) {
                listTaskByAccountIdAndUpdatedAt(accountId: $accountId, updatedAt: $updatedAt, limit: $limit) {
                    items {
                        id
                        target
                        status
                    }
                }
            }
            """

            # Query all tasks for this account
            variables = {
                "accountId": account_id,
                "updatedAt": {"ge": "2000-01-01T00:00:00.000Z"},  # Get all tasks
                "limit": 1000
            }

            result = self.client.execute(query, variables)
            all_tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

            # Filter for tasks matching this procedure ID
            existing_tasks = [
                task for task in all_tasks
                if procedure_id in task.get('target', '')
            ]

            # Find the task with exact target match
            existing_task = None
            for task_data in existing_tasks:
                if task_data['target'] == f"procedure/{procedure_id}":
                    existing_task = task_data
                    break

            if existing_task:
                logger.info(f"Reusing existing Task {existing_task['id']} for procedure {procedure_id}")
                # Get the full Task object
                task = Task.get_by_id(existing_task['id'], self.client)
                return task

            # No existing task found, create a new one
            logger.info(f"No existing Task found, creating new Task for procedure {procedure_id}")

            # Get stages from state machine (or use caller-provided configs)
            if stage_configs is None:
                stage_configs = get_stages_from_state_machine()

            # Build metadata
            metadata = {
                "type": "Procedure",
                "procedure_id": procedure_id,
                "task_type": "Procedure"
            }

            # Create the Task
            logger.info(f"Creating Task for procedure {procedure_id}")
            task = Task.create(
                client=self.client,
                accountId=account_id,
                type="Procedure",
                status="PENDING",  # Initial status
                target=f"procedure/{procedure_id}",
                command=f"procedure {procedure_id}",
                description=f"Procedure workflow for {procedure_id}",
                dispatchStatus="ANNOUNCED",
                metadata=json.dumps(metadata)
                # createdAt and updatedAt are auto-generated by the database
            )

            if not task:
                logger.error(f"Failed to create Task for procedure {procedure_id}")
                return None

            logger.info(f"Created Task {task.id} for procedure {procedure_id}")
            
            # Create TaskStage records for each state
            from plexus.dashboard.api.models.task_stage import TaskStage
            
            logger.info(f"Creating {len(stage_configs)} TaskStages for Task {task.id}")
            for stage_name, stage_config in stage_configs.items():
                try:
                    logger.info(f"Creating TaskStage: {stage_name} (order {stage_config.order})")
                    stage = TaskStage.create(
                        client=self.client,
                        taskId=task.id,
                        name=stage_name,
                        order=stage_config.order,
                        status="PENDING",  # All stages start as PENDING
                        statusMessage=stage_config.status_message or f"{stage_name} stage"
                        # createdAt and updatedAt are auto-generated by the database
                    )
                    logger.info(f"✓ Created TaskStage {stage.id}: {stage_name}")
                except Exception as e:
                    logger.error(f"✗ Failed to create TaskStage {stage_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            return task
            
        except Exception as e:
            logger.error(f"Error creating Task with stages for procedure {procedure_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
