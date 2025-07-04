"""
Core YAML DSL Linter Implementation

Provides the main YamlLinter class for validating YAML syntax and domain-specific rules.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import json

from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.scanner import ScannerError
from ruamel.yaml.parser import ParserError
from ruamel.yaml.constructor import ConstructorError

from .rules import RuleEngine
from .schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


@dataclass
class LintMessage:
    """Represents a single linting issue or success message."""
    
    # Message classification
    level: str  # 'error', 'warning', 'info', 'success'
    code: str   # Unique error code (e.g., 'YAML_SYNTAX_001', 'DOMAIN_REQUIRED_FIELD')
    
    # Message content
    title: str
    message: str
    suggestion: Optional[str] = None
    
    # Location information
    line: Optional[int] = None
    column: Optional[int] = None
    
    # Documentation links
    doc_url: Optional[str] = None
    doc_section: Optional[str] = None
    
    # Additional context
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'level': self.level,
            'code': self.code,
            'title': self.title,
            'message': self.message,
            'suggestion': self.suggestion,
            'line': self.line,
            'column': self.column,
            'doc_url': self.doc_url,
            'doc_section': self.doc_section,
            'context': self.context
        }


@dataclass
class LintResult:
    """Complete linting results for a YAML document."""
    
    # Overall status
    is_valid: bool
    success_message: Optional[str] = None
    
    # Individual messages
    messages: List[LintMessage] = field(default_factory=list)
    
    # Statistics
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # Parsed content (if successful)
    parsed_content: Optional[Dict[str, Any]] = None
    
    def add_message(self, message: LintMessage) -> None:
        """Add a message and update counters."""
        self.messages.append(message)
        
        if message.level == 'error':
            self.error_count += 1
            self.is_valid = False
        elif message.level == 'warning':
            self.warning_count += 1
        elif message.level == 'info':
            self.info_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'is_valid': self.is_valid,
            'success_message': self.success_message,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'info_count': self.info_count,
            'messages': [msg.to_dict() for msg in self.messages],
            'parsed_content': self.parsed_content
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class YamlLinter:
    """
    Main YAML DSL linter that validates both syntax and domain-specific rules.
    
    This class provides comprehensive linting for YAML-based configuration files,
    including syntax validation using ruamel.yaml and domain-specific rule validation.
    """
    
    def __init__(self, 
                 domain_schema: Optional[Dict[str, Any]] = None,
                 custom_rules: Optional[List[Any]] = None,
                 doc_base_url: str = "https://docs.plexus.ai/yaml-dsl"):
        """
        Initialize the YAML linter.
        
        Args:
            domain_schema: JSON schema defining the domain-specific structure
            custom_rules: List of custom validation rules
            doc_base_url: Base URL for documentation links
        """
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096
        
        self.doc_base_url = doc_base_url
        
        # Initialize validation components
        self.schema_validator = SchemaValidator(domain_schema) if domain_schema else None
        self.rule_engine = RuleEngine(custom_rules or [])
        
        # Configure YAML parser for better error reporting
        self.yaml.indent(mapping=2, sequence=4, offset=2)
    
    def lint(self, yaml_content: str, source_path: Optional[str] = None) -> LintResult:
        """
        Lint a YAML document for syntax and domain-specific issues.
        
        Args:
            yaml_content: The YAML content to lint
            source_path: Optional path to the source file (for better error messages)
            
        Returns:
            LintResult containing all validation results
        """
        result = LintResult(is_valid=True)
        
        try:
            # Stage 1: YAML Syntax Validation
            parsed_content = self._validate_syntax(yaml_content, result)
            
            if not result.is_valid:
                return result
            
            result.parsed_content = parsed_content
            
            # Stage 2: Schema Validation (if schema provided)
            if self.schema_validator and parsed_content is not None:
                self._validate_schema(parsed_content, result)
            
            # Stage 3: Domain-specific Rule Validation
            if parsed_content is not None:
                self._validate_rules(parsed_content, result)
            
            # Stage 4: Generate success message if no issues
            if result.is_valid and not result.messages:
                result.success_message = "✅ No issues found – nice work! Your YAML is well-formed and follows all domain rules."
                result.add_message(LintMessage(
                    level='success',
                    code='VALIDATION_SUCCESS',
                    title='Validation Successful',
                    message=result.success_message,
                    doc_url=f"{self.doc_base_url}/best-practices"
                ))
            
        except Exception as e:
            logger.exception("Unexpected error during linting")
            result.add_message(LintMessage(
                level='error',
                code='LINTER_INTERNAL_ERROR',
                title='Internal Linter Error',
                message=f"An unexpected error occurred during validation: {str(e)}",
                suggestion="Please check your YAML syntax and try again. If the issue persists, please report this as a bug.",
                doc_url=f"{self.doc_base_url}/troubleshooting"
            ))
        
        return result
    
    def lint_file(self, file_path: Union[str, Path]) -> LintResult:
        """
        Lint a YAML file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            LintResult containing all validation results
        """
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.lint(content, str(file_path))
        
        except FileNotFoundError:
            result = LintResult(is_valid=True)
            result.add_message(LintMessage(
                level='error',
                code='FILE_NOT_FOUND',
                title='File Not Found',
                message=f"Could not find file: {file_path}",
                suggestion="Please check that the file path is correct and the file exists.",
                doc_url=f"{self.doc_base_url}/troubleshooting"
            ))
            return result
        
        except UnicodeDecodeError as e:
            result = LintResult(is_valid=True)
            result.add_message(LintMessage(
                level='error',
                code='FILE_ENCODING_ERROR',
                title='File Encoding Error',
                message=f"Could not read file due to encoding issues: {str(e)}",
                suggestion="Please ensure the file is saved with UTF-8 encoding.",
                doc_url=f"{self.doc_base_url}/troubleshooting"
            ))
            return result
    
    def _validate_syntax(self, yaml_content: str, result: LintResult) -> Optional[Dict[str, Any]]:
        """Validate YAML syntax using ruamel.yaml."""
        try:
            # Parse the YAML content
            parsed = self.yaml.load(yaml_content)
            
            # Handle empty documents
            if parsed is None:
                result.add_message(LintMessage(
                    level='warning',
                    code='YAML_EMPTY_DOCUMENT',
                    title='Empty Document',
                    message='The YAML document is empty or contains only comments.',
                    suggestion='Consider adding some content or removing the file if not needed.',
                    doc_url=f"{self.doc_base_url}/structure"
                ))
                return {}
            
            return parsed
            
        except ScannerError as e:
            result.add_message(LintMessage(
                level='error',
                code='YAML_SCANNER_ERROR',
                title='YAML Syntax Error',
                message=f"Scanner error: {e.problem}",
                suggestion=self._get_scanner_suggestion(e),
                line=getattr(e.problem_mark, 'line', None),
                column=getattr(e.problem_mark, 'column', None),
                doc_url=f"{self.doc_base_url}/syntax-errors"
            ))
            
        except ParserError as e:
            result.add_message(LintMessage(
                level='error',
                code='YAML_PARSER_ERROR',
                title='YAML Structure Error',
                message=f"Parser error: {e.problem}",
                suggestion=self._get_parser_suggestion(e),
                line=getattr(e.problem_mark, 'line', None),
                column=getattr(e.problem_mark, 'column', None),
                doc_url=f"{self.doc_base_url}/syntax-errors"
            ))
            
        except ConstructorError as e:
            result.add_message(LintMessage(
                level='error',
                code='YAML_CONSTRUCTOR_ERROR',
                title='YAML Value Error',
                message=f"Constructor error: {e.problem}",
                suggestion="Check that all values are properly formatted and use supported YAML types.",
                line=getattr(e.problem_mark, 'line', None),
                column=getattr(e.problem_mark, 'column', None),
                doc_url=f"{self.doc_base_url}/data-types"
            ))
            
        except YAMLError as e:
            result.add_message(LintMessage(
                level='error',
                code='YAML_GENERAL_ERROR',
                title='YAML Error',
                message=f"YAML processing error: {str(e)}",
                suggestion="Please check your YAML syntax and formatting.",
                doc_url=f"{self.doc_base_url}/syntax-errors"
            ))
            
        return None
    
    def _validate_schema(self, parsed_content: Dict[str, Any], result: LintResult) -> None:
        """Validate against JSON schema if provided."""
        if self.schema_validator:
            schema_messages = self.schema_validator.validate(parsed_content)
            for message in schema_messages:
                result.add_message(message)
    
    def _validate_rules(self, parsed_content: Dict[str, Any], result: LintResult) -> None:
        """Validate against custom domain rules."""
        rule_messages = self.rule_engine.validate(parsed_content)
        for message in rule_messages:
            result.add_message(message)
    
    def _get_scanner_suggestion(self, error: ScannerError) -> str:
        """Generate helpful suggestions for scanner errors."""
        problem = error.problem.lower()
        
        if 'tab' in problem:
            return "YAML doesn't allow tabs for indentation. Please use spaces instead."
        elif 'indent' in problem:
            return "Check your indentation. YAML requires consistent spacing (usually 2 or 4 spaces per level)."
        elif 'found character' in problem and 'cannot start' in problem:
            return "This character cannot start a YAML value. Try quoting the value if it contains special characters."
        else:
            return "Please check the YAML syntax around this location."
    
    def _get_parser_suggestion(self, error: ParserError) -> str:
        """Generate helpful suggestions for parser errors."""
        problem = error.problem.lower()
        
        if 'mapping' in problem:
            return "Check that all mapping keys are properly formatted and indented."
        elif 'sequence' in problem:
            return "Check that list items (starting with '-') are properly indented."
        elif 'expected' in problem:
            return "The YAML structure is incomplete. Check for missing colons, brackets, or quotes."
        else:
            return "Please check the YAML structure and formatting around this location."