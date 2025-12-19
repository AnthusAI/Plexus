"""
YAML Parser and Validator for Lua DSL Procedures.

Parses procedure YAML configurations and validates required structure.
"""

import yaml
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ProcedureConfigError(Exception):
    """Raised when procedure configuration is invalid."""
    pass


class ProcedureYAMLParser:
    """Parses and validates Lua DSL procedure YAML configurations."""

    @staticmethod
    def parse(yaml_content: str) -> Dict[str, Any]:
        """
        Parse YAML content into a validated procedure configuration.

        Args:
            yaml_content: YAML string to parse

        Returns:
            Validated configuration dictionary

        Raises:
            ProcedureConfigError: If YAML is invalid or missing required fields
        """
        try:
            config = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ProcedureConfigError(f"Invalid YAML syntax: {e}")

        if not isinstance(config, dict):
            raise ProcedureConfigError("YAML root must be a dictionary")

        # Validate required top-level fields
        ProcedureYAMLParser._validate_required_fields(config)

        # Validate specific sections
        ProcedureYAMLParser._validate_params(config.get('params', {}))
        ProcedureYAMLParser._validate_outputs(config.get('outputs', {}))
        ProcedureYAMLParser._validate_agents(config.get('agents', {}))
        ProcedureYAMLParser._validate_workflow(config.get('workflow'))

        logger.info(f"Successfully parsed procedure: {config.get('name')}")
        return config

    @staticmethod
    def _validate_required_fields(config: Dict[str, Any]) -> None:
        """Validate that required top-level fields are present."""
        required = ['name', 'version', 'workflow']
        missing = [field for field in required if field not in config]

        if missing:
            raise ProcedureConfigError(
                f"Missing required fields: {', '.join(missing)}"
            )

        # Validate class field if present (for routing)
        if 'class' in config:
            if config['class'] != 'LuaDSL':
                logger.warning(
                    f"Procedure class '{config['class']}' may not be compatible "
                    "with Lua DSL runtime"
                )

    @staticmethod
    def _validate_params(params: Dict[str, Any]) -> None:
        """Validate parameter definitions (Plexus standard)."""
        if not isinstance(params, dict):
            raise ProcedureConfigError("'params' must be a dictionary")

        for param_name, param_def in params.items():
            if not isinstance(param_def, dict):
                raise ProcedureConfigError(
                    f"Parameter '{param_name}' definition must be a dictionary"
                )

            # Validate type field if present
            if 'type' in param_def:
                valid_types = ['string', 'number', 'boolean', 'array', 'object']
                if param_def['type'] not in valid_types:
                    raise ProcedureConfigError(
                        f"Parameter '{param_name}' has invalid type: {param_def['type']}. "
                        f"Must be one of: {', '.join(valid_types)}"
                    )

    @staticmethod
    def _validate_outputs(outputs: Dict[str, Any]) -> None:
        """Validate output definitions."""
        if not isinstance(outputs, dict):
            raise ProcedureConfigError("'outputs' must be a dictionary")

        for output_name, output_def in outputs.items():
            if not isinstance(output_def, dict):
                raise ProcedureConfigError(
                    f"Output '{output_name}' definition must be a dictionary"
                )

            # Validate type field if present
            if 'type' in output_def:
                valid_types = ['string', 'number', 'boolean', 'array', 'object']
                if output_def['type'] not in valid_types:
                    raise ProcedureConfigError(
                        f"Output '{output_name}' has invalid type: {output_def['type']}. "
                        f"Must be one of: {', '.join(valid_types)}"
                    )

    @staticmethod
    def _validate_agents(agents: Dict[str, Any]) -> None:
        """Validate agent definitions."""
        if not isinstance(agents, dict):
            raise ProcedureConfigError("'agents' must be a dictionary")

        if not agents:
            raise ProcedureConfigError("At least one agent must be defined")

        for agent_name, agent_def in agents.items():
            if not isinstance(agent_def, dict):
                raise ProcedureConfigError(
                    f"Agent '{agent_name}' definition must be a dictionary"
                )

            # Validate required agent fields
            required_agent_fields = ['system_prompt', 'initial_message']
            missing = [
                field for field in required_agent_fields
                if field not in agent_def
            ]

            if missing:
                raise ProcedureConfigError(
                    f"Agent '{agent_name}' missing required fields: {', '.join(missing)}"
                )

            # Validate tools field if present
            if 'tools' in agent_def:
                if not isinstance(agent_def['tools'], list):
                    raise ProcedureConfigError(
                        f"Agent '{agent_name}' tools must be a list"
                    )

    @staticmethod
    def _validate_workflow(workflow: Optional[str]) -> None:
        """Validate workflow Lua code."""
        if not workflow:
            raise ProcedureConfigError("'workflow' field is required")

        if not isinstance(workflow, str):
            raise ProcedureConfigError("'workflow' must be a string")

        if not workflow.strip():
            raise ProcedureConfigError("'workflow' cannot be empty")

        # Basic Lua syntax check (just verify it's not obviously broken)
        # The actual Lua runtime will do full validation
        if workflow.count('(') != workflow.count(')'):
            logger.warning("Workflow has unmatched parentheses - may have syntax errors")

    @staticmethod
    def extract_agent_names(config: Dict[str, Any]) -> List[str]:
        """Extract list of agent names from configuration."""
        return list(config.get('agents', {}).keys())

    @staticmethod
    def get_agent_config(config: Dict[str, Any], agent_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific agent."""
        return config.get('agents', {}).get(agent_name)
