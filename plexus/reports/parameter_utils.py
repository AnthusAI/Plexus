"""
Utility functions for handling parameters in report configurations.

This module provides functions for:
- Extracting parameter definitions from YAML configuration
- Validating parameter values
- Rendering configuration content with Jinja2 templates
"""

import yaml
from typing import Dict, Any, List, Optional
from jinja2 import Environment, StrictUndefined, TemplateError
import logging

logger = logging.getLogger(__name__)


def extract_parameters_from_config(configuration: str) -> tuple[List[Dict[str, Any]], str]:
    """
    Extract parameter definitions and content from report configuration.
    
    Args:
        configuration: The full report configuration string (may include YAML frontmatter)
        
    Returns:
        Tuple of (parameter_definitions, content)
        - parameter_definitions: List of parameter definition dicts
        - content: The report content (everything after --- separator, or full config if no separator)
    """
    # Check for YAML frontmatter (parameters section before ---)
    if '---' in configuration:
        parts = configuration.split('---', 1)
        frontmatter = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ''
        
        try:
            # Parse the frontmatter YAML
            data = yaml.safe_load(frontmatter)
            if data and isinstance(data, dict) and 'parameters' in data:
                parameters = data['parameters']
                if isinstance(parameters, list):
                    return parameters, content
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter: {e}")
            # Fall through to return empty parameters
    
    # No parameters found
    return [], configuration


def has_parameters(configuration: str) -> bool:
    """
    Check if a configuration has parameter definitions.
    
    Args:
        configuration: The report configuration string
        
    Returns:
        True if parameters are defined, False otherwise
    """
    parameters, _ = extract_parameters_from_config(configuration)
    return len(parameters) > 0


def validate_parameter_value(param_def: Dict[str, Any], value: Any) -> tuple[bool, Optional[str]]:
    """
    Validate a parameter value against its definition.
    
    Args:
        param_def: Parameter definition dict with 'name', 'type', 'required', etc.
        value: The value to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    param_name = param_def.get('name', 'unknown')
    param_type = param_def.get('type', 'text')
    required = param_def.get('required', False)
    
    # Check if required parameter is provided
    if required and (value is None or value == ''):
        return False, f"Parameter '{param_name}' is required"
    
    # If not required and no value, that's OK
    if value is None or value == '':
        return True, None
    
    # Type-specific validation
    if param_type == 'number':
        try:
            num_value = float(value) if isinstance(value, str) else value
            
            # Check min/max constraints
            if 'min' in param_def and num_value < param_def['min']:
                return False, f"Parameter '{param_name}' must be >= {param_def['min']}"
            if 'max' in param_def and num_value > param_def['max']:
                return False, f"Parameter '{param_name}' must be <= {param_def['max']}"
                
            return True, None
        except (ValueError, TypeError):
            return False, f"Parameter '{param_name}' must be a number"
    
    elif param_type == 'boolean':
        if isinstance(value, bool):
            return True, None
        if isinstance(value, str):
            if value.lower() in ('true', 'yes', 'y', '1'):
                return True, None
            if value.lower() in ('false', 'no', 'n', '0'):
                return True, None
        return False, f"Parameter '{param_name}' must be a boolean (true/false)"
    
    elif param_type == 'select':
        # Check if value is in options
        options = param_def.get('options', [])
        if options:
            valid_values = [opt['value'] if isinstance(opt, dict) else opt for opt in options]
            if value not in valid_values:
                return False, f"Parameter '{param_name}' must be one of: {', '.join(map(str, valid_values))}"
    
    # All other types (text, date, etc.) - just check it's not empty if required
    return True, None


def validate_all_parameters(param_defs: List[Dict[str, Any]], values: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate all parameter values against their definitions.
    
    Args:
        param_defs: List of parameter definitions
        values: Dictionary of parameter name -> value
        
    Returns:
        Tuple of (all_valid, list_of_errors)
    """
    errors = []
    
    for param_def in param_defs:
        param_name = param_def.get('name')
        if not param_name:
            continue
            
        value = values.get(param_name)
        is_valid, error = validate_parameter_value(param_def, value)
        
        if not is_valid and error:
            errors.append(error)
    
    return len(errors) == 0, errors


def render_configuration_with_parameters(
    configuration: str, 
    parameters: Dict[str, Any],
    strict: bool = True
) -> str:
    """
    Render report configuration content with Jinja2 parameter interpolation.
    
    Args:
        configuration: The report configuration content (may include parameter definitions)
        parameters: Dictionary of parameter name -> value mappings
        strict: If True, raise error on undefined variables. If False, leave them as-is.
        
    Returns:
        The rendered configuration with parameters interpolated
        
    Raises:
        TemplateError: If Jinja2 rendering fails (e.g., undefined variable in strict mode)
    """
    # Extract parameters and content
    param_defs, content = extract_parameters_from_config(configuration)
    
    # Create Jinja2 environment
    env = Environment(
        undefined=StrictUndefined if strict else None,
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    try:
        # Render the template
        template = env.from_string(content)
        rendered = template.render(**parameters)
        return rendered
    except TemplateError as e:
        logger.error(f"Jinja2 template rendering failed: {e}")
        raise


def get_parameter_display_value(param_def: Dict[str, Any], value: Any) -> str:
    """
    Get a human-readable display string for a parameter value.
    
    Args:
        param_def: Parameter definition
        value: The parameter value
        
    Returns:
        String representation for display
    """
    if value is None or value == '':
        return '<not set>'
    
    param_type = param_def.get('type', 'text')
    
    if param_type == 'boolean':
        return 'Yes' if value else 'No'
    elif param_type == 'select':
        # Try to find label for this value
        options = param_def.get('options', [])
        for opt in options:
            if isinstance(opt, dict):
                if opt.get('value') == value:
                    return opt.get('label', str(value))
        return str(value)
    else:
        return str(value)


def normalize_parameter_value(param_def: Dict[str, Any], value: str) -> Any:
    """
    Convert a string parameter value to the appropriate Python type.
    
    Args:
        param_def: Parameter definition with 'type' field
        value: String value from CLI or user input
        
    Returns:
        Converted value (int, bool, str, etc.)
    """
    param_type = param_def.get('type', 'text')
    
    if value is None or value == '':
        return None
    
    if param_type == 'number':
        try:
            # Try int first, fall back to float
            if '.' in str(value):
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value  # Return as-is if conversion fails
    
    elif param_type == 'boolean':
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', 'y', '1')
        return bool(value)
    
    else:
        # text, date, select, and others - keep as string
        return str(value)

