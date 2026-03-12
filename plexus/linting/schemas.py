"""
YAML DSL Schemas and Validation Rules - Python Implementation

Defines the schemas and validation rules for different YAML formats used in the application.
"""

from typing import Dict, Any, List
from .yaml_linter import YamlLinter
from .rules import RequiredFieldRule, AllowedValuesRule, TypeValidationRule, ValidationRule
from .data_source_rules import create_data_source_validation_rules


# Score Configuration Schema (JSON Schema format)
SCORE_YAML_SCHEMA = {
    "type": "object",
    "required": ["name", "key"],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1,
            "description": "Human-readable name for the score"
        },
        "key": {
            "type": "string",
            "pattern": "^[a-z0-9_-]+$",
            "description": "Unique identifier for the score (lowercase, alphanumeric, underscores, and hyphens only)"
        },
        "externalId": {
            "type": "string",
            "description": "External ID for the score (camelCase format)"
        },
        "external_id": {
            "type": "string",
            "description": "External ID for the score (snake_case format)"
        },
        "description": {
            "type": "string",
            "description": "Detailed description of what this score measures"
        },
        "type": {
            "type": "string",
            "enum": ["binary", "numeric", "categorical", "text"],
            "description": "Type of score output"
        },
        "version": {
            "type": "string",
            "description": "Version identifier for the score"
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags for categorizing the score"
        },
        "config": {
            "type": "object",
            "description": "Score-specific configuration parameters"
        }
    },
    "additionalProperties": True
}

# Data Source Configuration Schema (JSON Schema format)
DATA_SOURCE_YAML_SCHEMA = {
    "type": "object",
    "required": ["class"],
    "properties": {
        "class": {
            "type": "string",
            "enum": ["CallCriteriaDBCache"],
            "description": "Data source class - currently only CallCriteriaDBCache is supported"
        },
        "queries": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["scorecard_id", "number"],
                "properties": {
                    "scorecard_id": {
                        "type": "number",
                        "description": "ID of the scorecard to query"
                    },
                    "number": {
                        "type": "number",
                        "minimum": 1,
                        "description": "Number of records to retrieve"
                    },
                    "query": {
                        "type": "string",
                        "description": "Custom SQL query with placeholders like {scorecard_id} and {number}"
                    },
                    "minimum_calibration_count": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Minimum calibration count required"
                    }
                },
                "additionalProperties": False
            },
            "description": "List of database queries to execute"
        },
        "searches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["item_list_filename"],
                "properties": {
                    "item_list_filename": {
                        "type": "string",
                        "pattern": "^.+\\.(csv|txt)$",
                        "description": "Path to CSV or text file containing search items"
                    }
                },
                "additionalProperties": False
            },
            "description": "List of file-based searches to perform"
        },
        "balance": {
            "type": "boolean",
            "description": "Whether to balance the dataset (defaults to true)"
        }
    },
    "additionalProperties": False,
    "anyOf": [
        {"required": ["queries"]},
        {"required": ["searches"]}
    ]
}


def create_score_validation_rules() -> List[ValidationRule]:
    """Create validation rules for score configuration."""
    from .rules import ValidationRule
    from .yaml_linter import LintMessage
    
    class ScoreKeyFormatRule(ValidationRule):
        """Rule that validates score key format."""
        
        def __init__(self):
            super().__init__(
                rule_id='SCORE_KEY_FORMAT',
                description='Score key must be lowercase with only letters, numbers, underscores, and hyphens',
                severity='error'
            )
        
        def validate(self, data: Dict[str, Any]) -> List[LintMessage]:
            import re
            messages = []
            
            if 'key' in data and isinstance(data['key'], str):
                key_pattern = re.compile(r'^[a-z0-9_-]+$')
                if not key_pattern.match(data['key']):
                    messages.append(LintMessage(
                        level=self.severity,
                        code=self.rule_id,
                        title='Invalid Key Format',
                        message=f"Score key '{data['key']}' contains invalid characters.",
                        suggestion='Use only lowercase letters, numbers, underscores, and hyphens. Example: "sentiment_analysis" or "quality-score"',
                        doc_url='https://docs.plexus.ai/yaml-dsl/score-keys',
                        context={'field_path': 'key', 'current_value': data['key']}
                    ))
            
            return messages
    
    class ScoreExternalIdConsistencyRule(ValidationRule):
        """Rule that checks external ID format consistency."""
        
        def __init__(self):
            super().__init__(
                rule_id='SCORE_EXTERNAL_ID_CONSISTENCY',
                description='External ID should use consistent format (either camelCase or snake_case, not both)',
                severity='warning'
            )
        
        def validate(self, data: Dict[str, Any]) -> List[LintMessage]:
            messages = []
            
            has_camel_case = 'externalId' in data
            has_snake_case = 'external_id' in data
            
            if has_camel_case and has_snake_case:
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Inconsistent External ID Format',
                    message='Both externalId and external_id are present. Use only one format.',
                    suggestion='Choose either camelCase (externalId) or snake_case (external_id) and remove the other.',
                    doc_url='https://docs.plexus.ai/yaml-dsl/external-ids',
                    context={'has_camel_case': has_camel_case, 'has_snake_case': has_snake_case}
                ))
            
            return messages
    
    return [
        # Required fields
        RequiredFieldRule('name'),
        RequiredFieldRule('key'),
        
        # Type validation
        TypeValidationRule('name', str),
        TypeValidationRule('key', str),
        TypeValidationRule('description', str),
        
        # Custom score rules
        ScoreKeyFormatRule(),
        ScoreExternalIdConsistencyRule(),
        
        # Type validation for common score types
        AllowedValuesRule('type', ['binary', 'numeric', 'categorical', 'text'])
    ]


def create_score_linter() -> YamlLinter:
    """Create a YAML linter configured for score validation."""
    return YamlLinter(
        domain_schema=SCORE_YAML_SCHEMA,
        custom_rules=create_score_validation_rules(),
        doc_base_url='https://docs.plexus.ai/yaml-dsl/scores'
    )


def create_data_source_linter() -> YamlLinter:
    """Create a YAML linter configured for data source validation."""
    return YamlLinter(
        domain_schema=DATA_SOURCE_YAML_SCHEMA,
        custom_rules=create_data_source_validation_rules(),
        doc_base_url='https://docs.plexus.ai/yaml-dsl/data-sources'
    )


def create_linter_for_context(context: str) -> YamlLinter:
    """Create a linter for the specified context."""
    if context == 'score':
        return create_score_linter()
    elif context == 'data-source':
        return create_data_source_linter()
    else:
        raise ValueError(f"Unknown linter context: {context}")