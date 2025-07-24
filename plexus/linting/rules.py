"""
Domain-specific validation rules for YAML DSL linter.

Provides a flexible rule engine for implementing custom validation logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .yaml_linter import LintMessage


@dataclass
class ValidationRule(ABC):
    """Abstract base class for validation rules."""
    
    rule_id: str
    description: str
    severity: str = 'error'  # 'error', 'warning', 'info'
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        """
        Validate the data against this rule.
        
        Args:
            data: Parsed YAML data to validate
            
        Returns:
            List of LintMessage objects for any violations
        """
        pass


class RuleEngine:
    """Engine for running validation rules against YAML data."""
    
    def __init__(self, rules: List[ValidationRule]):
        """
        Initialize the rule engine.
        
        Args:
            rules: List of validation rules to apply
        """
        self.rules = rules
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        """
        Run all rules against the provided data.
        
        Args:
            data: Parsed YAML data to validate
            
        Returns:
            List of all LintMessage objects from rule violations
        """
        # Import here to avoid circular imports
        from .yaml_linter import LintMessage
        
        messages = []
        
        for rule in self.rules:
            try:
                rule_messages = rule.validate(data)
                messages.extend(rule_messages)
            except Exception as e:
                # If a rule fails, generate an error message
                messages.append(LintMessage(
                    level='error',
                    code='RULE_ENGINE_ERROR',
                    title='Rule Validation Error',
                    message=f"Error running rule '{rule.rule_id}': {str(e)}",
                    suggestion="Please check the rule configuration or report this as a bug.",
                    context={'rule_id': rule.rule_id, 'error': str(e)}
                ))
        
        return messages


# Example domain-specific rules

class RequiredFieldRule(ValidationRule):
    """Rule that validates required fields exist."""
    
    def __init__(self, field_path: str, rule_id: Optional[str] = None):
        """
        Initialize the required field rule.
        
        Args:
            field_path: Dot-separated path to the required field (e.g., 'config.name')
            rule_id: Optional custom rule ID
        """
        self.field_path = field_path
        super().__init__(
            rule_id=rule_id or f"REQUIRED_FIELD_{field_path.upper().replace('.', '_')}",
            description=f"Field '{field_path}' is required",
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Navigate to the field using dot notation
        current = data
        path_parts = self.field_path.split('.')
        
        try:
            for part in path_parts[:-1]:
                if not isinstance(current, dict) or part not in current:
                    raise KeyError(f"Path not found: {part}")
                current = current[part]
            
            # Check if the final field exists
            final_field = path_parts[-1]
            if not isinstance(current, dict) or final_field not in current:
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Required Field Missing',
                    message=f"Required field '{self.field_path}' is missing.",
                    suggestion=f"Please add the '{self.field_path}' field to your configuration.",
                    doc_url="https://docs.plexus.ai/yaml-dsl/required-fields",
                    context={'field_path': self.field_path}
                ))
            elif current[final_field] is None or current[final_field] == '':
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Required Field Empty',
                    message=f"Required field '{self.field_path}' is empty.",
                    suggestion=f"Please provide a value for the '{self.field_path}' field.",
                    doc_url="https://docs.plexus.ai/yaml-dsl/required-fields",
                    context={'field_path': self.field_path}
                ))
                
        except (KeyError, TypeError):
            messages.append(LintMessage(
                level=self.severity,
                code=self.rule_id,
                title='Required Field Missing',
                message=f"Required field '{self.field_path}' is missing.",
                suggestion=f"Please add the '{self.field_path}' field to your configuration.",
                doc_url="https://docs.plexus.ai/yaml-dsl/required-fields",
                context={'field_path': self.field_path}
            ))
        
        return messages


class AllowedValuesRule(ValidationRule):
    """Rule that validates field values are from allowed set."""
    
    def __init__(self, field_path: str, allowed_values: List[Any], rule_id: Optional[str] = None):
        """
        Initialize the allowed values rule.
        
        Args:
            field_path: Dot-separated path to the field
            allowed_values: List of allowed values
            rule_id: Optional custom rule ID
        """
        self.field_path = field_path
        self.allowed_values = allowed_values
        super().__init__(
            rule_id=rule_id or f"ALLOWED_VALUES_{field_path.upper().replace('.', '_')}",
            description=f"Field '{field_path}' must be one of: {allowed_values}",
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Navigate to the field
        current = data
        path_parts = self.field_path.split('.')
        
        try:
            for part in path_parts:
                if not isinstance(current, dict) or part not in current:
                    # Field doesn't exist - not our concern
                    return messages
                current = current[part]
            
            # Check if value is allowed
            if current not in self.allowed_values:
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Invalid Field Value',
                    message=f"Field '{self.field_path}' has invalid value '{current}'.",
                    suggestion=f"Please use one of the allowed values: {', '.join(map(str, self.allowed_values))}",
                    doc_url="https://docs.plexus.ai/yaml-dsl/field-values",
                    context={
                        'field_path': self.field_path,
                        'current_value': current,
                        'allowed_values': self.allowed_values
                    }
                ))
                
        except (KeyError, TypeError):
            # Field path is invalid - not our concern
            pass
        
        return messages


class TypeValidationRule(ValidationRule):
    """Rule that validates field types."""
    
    def __init__(self, field_path: str, expected_type: type, rule_id: Optional[str] = None):
        """
        Initialize the type validation rule.
        
        Args:
            field_path: Dot-separated path to the field
            expected_type: Expected Python type
            rule_id: Optional custom rule ID
        """
        self.field_path = field_path
        self.expected_type = expected_type
        super().__init__(
            rule_id=rule_id or f"TYPE_VALIDATION_{field_path.upper().replace('.', '_')}",
            description=f"Field '{field_path}' must be of type {expected_type.__name__}",
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Navigate to the field
        current = data
        path_parts = self.field_path.split('.')
        
        try:
            for part in path_parts:
                if not isinstance(current, dict) or part not in current:
                    # Field doesn't exist - not our concern
                    return messages
                current = current[part]
            
            # Check type
            if not isinstance(current, self.expected_type):
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Invalid Field Type',
                    message=f"Field '{self.field_path}' should be {self.expected_type.__name__}, but got {type(current).__name__}.",
                    suggestion=f"Please ensure '{self.field_path}' is a {self.expected_type.__name__}.",
                    doc_url="https://docs.plexus.ai/yaml-dsl/data-types",
                    context={
                        'field_path': self.field_path,
                        'expected_type': self.expected_type.__name__,
                        'actual_type': type(current).__name__
                    }
                ))
                
        except (KeyError, TypeError):
            # Field path is invalid - not our concern
            pass
        
        return messages