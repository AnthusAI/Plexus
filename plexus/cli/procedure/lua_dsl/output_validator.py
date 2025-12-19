"""
Output Schema Validator for Lua DSL Procedures

Validates that Lua workflow return values match the declared output schema.
Enables type safety and composability for sub-agent workflows.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class OutputValidationError(Exception):
    """Raised when workflow output doesn't match schema."""
    pass


class OutputValidator:
    """
    Validates procedure output against declared schema.

    Supports:
    - Type checking (string, number, boolean, object, array)
    - Required field validation
    - Nested object validation
    - Clear error messages
    """

    # Type mapping from YAML to Python
    TYPE_MAP = {
        'string': str,
        'number': (int, float),
        'boolean': bool,
        'object': dict,
        'array': list
    }

    def __init__(self, output_schema: Optional[Dict[str, Any]] = None):
        """
        Initialize validator with output schema.

        Args:
            output_schema: Dict of output field definitions
                Example:
                {
                    'limerick': {
                        'type': 'string',
                        'required': True,
                        'description': 'The generated limerick'
                    },
                    'node_id': {
                        'type': 'string',
                        'required': False
                    }
                }
        """
        self.schema = output_schema or {}
        logger.debug(f"OutputValidator initialized with {len(self.schema)} output fields")

    def validate(self, output: Any) -> Dict[str, Any]:
        """
        Validate workflow output against schema.

        Args:
            output: The return value from Lua workflow

        Returns:
            Validated output dict

        Raises:
            OutputValidationError: If validation fails
        """
        # If no schema defined, accept any output
        if not self.schema:
            logger.debug("No output schema defined, skipping validation")
            if isinstance(output, dict):
                return output
            elif hasattr(output, 'items'):
                # Lua table - convert to dict
                return dict(output.items())
            else:
                return {'result': output}

        # Convert Lua tables to dicts recursively
        if hasattr(output, 'items') or isinstance(output, dict):
            logger.debug("Converting Lua tables to Python dicts recursively")
            output = self._convert_lua_tables(output)

        # Output must be a dict/table
        if not isinstance(output, dict):
            raise OutputValidationError(
                f"Output must be an object/table, got {type(output).__name__}"
            )

        errors = []

        # Check required fields
        for field_name, field_def in self.schema.items():
            is_required = field_def.get('required', False)

            if is_required and field_name not in output:
                errors.append(f"Required field '{field_name}' is missing")
                continue

            # Skip validation if field not present and not required
            if field_name not in output:
                continue

            # Type checking
            expected_type = field_def.get('type')
            if expected_type:
                value = output[field_name]
                if not self._check_type(value, expected_type):
                    actual_type = type(value).__name__
                    errors.append(
                        f"Field '{field_name}' should be {expected_type}, got {actual_type}"
                    )

        # Check for unexpected fields (warning only)
        for field_name in output:
            if field_name not in self.schema:
                logger.warning(f"Unexpected field '{field_name}' in output (not in schema)")

        if errors:
            error_msg = "Output validation failed:\n  " + "\n  ".join(errors)
            raise OutputValidationError(error_msg)

        logger.info(f"Output validation passed for {len(output)} fields")
        return output

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if value matches expected type.

        Args:
            value: The value to check
            expected_type: Expected type string ('string', 'number', etc.)

        Returns:
            True if type matches
        """
        if value is None:
            # None is acceptable for optional fields
            return True

        python_type = self.TYPE_MAP.get(expected_type)
        if not python_type:
            logger.warning(f"Unknown type '{expected_type}', skipping validation")
            return True

        # Handle Lua tables as dicts/arrays
        if expected_type in ('object', 'array'):
            if hasattr(value, 'items') or hasattr(value, '__iter__'):
                return True

        return isinstance(value, python_type)

    def _convert_lua_tables(self, obj: Any) -> Any:
        """
        Recursively convert Lua tables to Python dicts/lists.

        Args:
            obj: Object to convert

        Returns:
            Converted object
        """
        # Handle Lua tables (have .items() method)
        if hasattr(obj, 'items') and not isinstance(obj, dict):
            return {k: self._convert_lua_tables(v) for k, v in obj.items()}

        # Handle lists
        elif isinstance(obj, (list, tuple)):
            return [self._convert_lua_tables(item) for item in obj]

        # Handle dicts
        elif isinstance(obj, dict):
            return {k: self._convert_lua_tables(v) for k, v in obj.items()}

        # Return as-is for primitives
        else:
            return obj

    def get_field_description(self, field_name: str) -> Optional[str]:
        """Get description for an output field."""
        if field_name in self.schema:
            return self.schema[field_name].get('description')
        return None

    def get_required_fields(self) -> List[str]:
        """Get list of required output fields."""
        return [
            name for name, def_ in self.schema.items()
            if def_.get('required', False)
        ]

    def get_optional_fields(self) -> List[str]:
        """Get list of optional output fields."""
        return [
            name for name, def_ in self.schema.items()
            if not def_.get('required', False)
        ]
