"""
JSON Schema validation for YAML DSL linter.

Provides schema-based validation using JSON Schema.
"""

from typing import List, Dict, Any, Optional
import json

try:
    import jsonschema
    from jsonschema import ValidationError, SchemaError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    ValidationError = Exception
    SchemaError = Exception


class SchemaValidator:
    """Validates YAML data against JSON Schema."""
    
    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        """
        Initialize the schema validator.
        
        Args:
            schema: JSON schema to validate against
        """
        self.schema = schema
        
        if not HAS_JSONSCHEMA and schema:
            # We'll create a warning message when validate is called
            pass
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        """
        Validate data against the schema.
        
        Args:
            data: Parsed YAML data to validate
            
        Returns:
            List of LintMessage objects for schema violations
        """
        # Import here to avoid circular imports
        from .yaml_linter import LintMessage
        
        messages = []
        
        if not self.schema:
            return messages
        
        if not HAS_JSONSCHEMA:
            messages.append(LintMessage(
                level='warning',
                code='SCHEMA_VALIDATOR_UNAVAILABLE',
                title='Schema Validation Unavailable',
                message='JSON Schema validation is not available. Install jsonschema package for schema validation.',
                suggestion='Run: pip install jsonschema',
                doc_url='https://docs.plexus.ai/yaml-dsl/schema-validation'
            ))
            return messages
        
        try:
            # Validate the schema itself first
            jsonschema.Draft7Validator.check_schema(self.schema)
            
            # Create validator
            validator = jsonschema.Draft7Validator(self.schema)
            
            # Validate the data
            errors = sorted(validator.iter_errors(data), key=lambda e: e.absolute_path)
            
            for error in errors:
                # Convert jsonschema ValidationError to LintMessage
                field_path = '.'.join(str(p) for p in error.absolute_path) if error.absolute_path else 'root'
                
                messages.append(LintMessage(
                    level='error',
                    code='SCHEMA_VALIDATION_ERROR',
                    title='Schema Validation Failed',
                    message=f"Schema validation error at '{field_path}': {error.message}",
                    suggestion=self._get_schema_suggestion(error),
                    doc_url='https://docs.plexus.ai/yaml-dsl/schema-validation',
                    context={
                        'field_path': field_path,
                        'schema_path': '.'.join(str(p) for p in error.schema_path) if error.schema_path else '',
                        'validator': error.validator,
                        'validator_value': error.validator_value
                    }
                ))
                
        except SchemaError as e:
            messages.append(LintMessage(
                level='error',
                code='INVALID_SCHEMA',
                title='Invalid Schema',
                message=f"The provided schema is invalid: {e.message}",
                suggestion='Please check your JSON schema definition.',
                doc_url='https://docs.plexus.ai/yaml-dsl/schema-validation'
            ))
            
        except Exception as e:
            messages.append(LintMessage(
                level='error',
                code='SCHEMA_VALIDATION_INTERNAL_ERROR',
                title='Schema Validation Error',
                message=f"An error occurred during schema validation: {str(e)}",
                suggestion='Please check your schema and data, or report this as a bug.',
                doc_url='https://docs.plexus.ai/yaml-dsl/troubleshooting'
            ))
        
        return messages
    
    def _get_schema_suggestion(self, error: 'ValidationError') -> str:
        """Generate helpful suggestions based on schema validation errors."""
        validator = error.validator
        message = error.message.lower()
        
        if validator == 'required':
            return f"Please add the required field: {error.validator_value}"
        elif validator == 'type':
            return f"Please ensure the value is of type: {error.validator_value}"
        elif validator == 'enum':
            return f"Please use one of the allowed values: {', '.join(map(str, error.validator_value))}"
        elif validator == 'minimum':
            return f"Please use a value greater than or equal to {error.validator_value}"
        elif validator == 'maximum':
            return f"Please use a value less than or equal to {error.validator_value}"
        elif validator == 'minLength':
            return f"Please provide at least {error.validator_value} characters"
        elif validator == 'maxLength':
            return f"Please provide no more than {error.validator_value} characters"
        elif validator == 'pattern':
            return f"Please ensure the value matches the required pattern"
        elif 'additional' in message:
            return "Please remove the unexpected field or check your schema"
        else:
            return "Please check the value against the schema requirements"