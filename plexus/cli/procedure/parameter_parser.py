"""
YAML Parameter Parser for Procedures

Extracts configurable parameter values from procedure YAML code.
This allows procedures to have dynamic parameters (like scorecard_id, score_id, score_version_id)
that are stored within the YAML code rather than as fixed fields on the Procedure model.
"""

import yaml
import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParameterDefinition:
    """Definition of a configurable parameter from YAML."""
    name: str
    type: str
    label: str
    required: bool = False
    default: Optional[Any] = None
    options: Optional[List[str]] = None


class ProcedureParameterParser:
    """
    Parses configurable parameters from procedure YAML code.
    
    Parameters are defined in the YAML configuration and their values
    are injected into the code using placeholder syntax like {{parameter_name}}.
    
    Example YAML:
        configurable_parameters:
          - name: scorecard_id
            type: scorecard_select
            label: Scorecard
            required: true
          - name: score_id  
            type: score_select
            label: Score
            required: true
          - name: score_version_id
            type: score_version_select
            label: Score Version
            required: false
        
        # Values injected as:
        scorecard: "{{scorecard_id}}"
        score: "{{score_id}}"
        version: "{{score_version_id}}"
    """
    
    @staticmethod
    def parse_parameter_definitions(yaml_code: str) -> List[ParameterDefinition]:
        """
        Extract parameter definitions from YAML code.
        
        Args:
            yaml_code: The procedure YAML configuration
            
        Returns:
            List of ParameterDefinition objects
        """
        try:
            yaml_data = yaml.safe_load(yaml_code)
            if not yaml_data or not isinstance(yaml_data, dict):
                logger.warning("Invalid YAML structure for parameter parsing")
                return []
            
            param_configs = yaml_data.get('configurable_parameters', [])
            if not param_configs:
                logger.debug("No configurable_parameters found in YAML")
                return []
            
            parameters = []
            for param_config in param_configs:
                if not isinstance(param_config, dict):
                    logger.warning(f"Invalid parameter configuration: {param_config}")
                    continue
                
                param = ParameterDefinition(
                    name=param_config.get('name', ''),
                    type=param_config.get('type', 'string'),
                    label=param_config.get('label', param_config.get('name', '')),
                    required=param_config.get('required', False),
                    default=param_config.get('default'),
                    options=param_config.get('options')
                )
                
                if param.name:
                    parameters.append(param)
                else:
                    logger.warning(f"Parameter missing name: {param_config}")
            
            logger.debug(f"Parsed {len(parameters)} parameter definitions from YAML")
            return parameters
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing parameter definitions: {e}")
            return []
    
    @staticmethod
    def extract_parameter_values(yaml_code: str) -> Dict[str, Any]:
        """
        Extract actual parameter values from YAML code by finding injected values.
        
        This searches for patterns like: key: "{{parameter_name}}" or key: "actual_value"
        and attempts to extract the current values.
        
        Args:
            yaml_code: The procedure YAML configuration with values injected
            
        Returns:
            Dictionary mapping parameter names to their current values
        """
        values = {}
        
        try:
            # First, get parameter definitions to know what to look for
            parameters = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
            
            # Parse the YAML
            yaml_data = yaml.safe_load(yaml_code)
            if not yaml_data or not isinstance(yaml_data, dict):
                return values
            
            # For each parameter, try to find its value in the YAML structure
            for param in parameters:
                value = ProcedureParameterParser._find_parameter_value_in_yaml(
                    yaml_data, param.name
                )
                if value is not None:
                    values[param.name] = value
                    logger.debug(f"Found value for parameter '{param.name}': {value}")
            
            return values
            
        except Exception as e:
            logger.error(f"Error extracting parameter values: {e}")
            return values
    
    @staticmethod
    def _find_parameter_value_in_yaml(data: Any, param_name: str, depth: int = 0) -> Optional[Any]:
        """
        Recursively search YAML data structure for a parameter value.
        
        Looks for values that were injected via {{param_name}} placeholders.
        Since the YAML has been processed and values injected, we need to find
        the actual values by pattern matching.
        
        Args:
            data: YAML data structure to search
            param_name: Name of the parameter to find
            depth: Current recursion depth (safety limit)
            
        Returns:
            The parameter value if found, None otherwise
        """
        if depth > 10:  # Safety limit for recursion
            return None
        
        if isinstance(data, dict):
            # Check if any key matches the parameter name pattern
            for key, value in data.items():
                # Direct key match (e.g., "scorecard_id": "actual_value")
                if key == param_name:
                    return value
                
                # Recursive search in nested structures
                result = ProcedureParameterParser._find_parameter_value_in_yaml(
                    value, param_name, depth + 1
                )
                if result is not None:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = ProcedureParameterParser._find_parameter_value_in_yaml(
                    item, param_name, depth + 1
                )
                if result is not None:
                    return result
        
        return None
    
    @staticmethod
    def get_required_parameters(yaml_code: str) -> Dict[str, ParameterDefinition]:
        """
        Get all required parameters that must have values.
        
        Args:
            yaml_code: The procedure YAML configuration
            
        Returns:
            Dictionary mapping parameter names to their definitions (required only)
        """
        parameters = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        return {p.name: p for p in parameters if p.required}
    
    @staticmethod
    def validate_parameter_values(
        yaml_code: str,
        provided_values: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, List[str]]:
        """
        Validate that all required parameters have values.
        
        Args:
            yaml_code: The procedure YAML configuration
            provided_values: Optional dict of externally provided values to check
            
        Returns:
            Tuple of (is_valid, list_of_missing_parameters)
        """
        required_params = ProcedureParameterParser.get_required_parameters(yaml_code)
        
        # If no provided values, try to extract from YAML
        if provided_values is None:
            provided_values = ProcedureParameterParser.extract_parameter_values(yaml_code)
        
        missing = []
        for param_name, param_def in required_params.items():
            value = provided_values.get(param_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(param_name)
                logger.warning(
                    f"Required parameter '{param_name}' ({param_def.label}) is missing or empty"
                )
        
        is_valid = len(missing) == 0
        return is_valid, missing
