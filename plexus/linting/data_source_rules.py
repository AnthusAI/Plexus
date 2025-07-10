"""
Data source specific validation rules for YAML DSL linter.

These rules validate the CallCriteriaDBCache data source schema.
"""

from typing import List, Dict, Any, TYPE_CHECKING
from .rules import ValidationRule

if TYPE_CHECKING:
    from .yaml_linter import LintMessage


class DataSourceQueriesOrSearchesRule(ValidationRule):
    """Rule that ensures either queries or searches is present for CallCriteriaDBCache."""
    
    def __init__(self):
        super().__init__(
            rule_id='DATA_SOURCE_QUERIES_OR_SEARCHES_REQUIRED',
            description='CallCriteriaDBCache data source must have either queries or searches defined',
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Only apply this rule to CallCriteriaDBCache
        if data.get('class') != 'CallCriteriaDBCache':
            return messages
        
        has_queries = (
            'queries' in data and 
            isinstance(data['queries'], list) and 
            len(data['queries']) > 0
        )
        has_searches = (
            'searches' in data and 
            isinstance(data['searches'], list) and 
            len(data['searches']) > 0
        )
        
        if not has_queries and not has_searches:
            messages.append(LintMessage(
                level=self.severity,
                code=self.rule_id,
                title='Missing Queries or Searches',
                message='Data source must have either "queries" or "searches" defined (or both).',
                suggestion='Add a "queries" section for database queries or a "searches" section for file-based searches.',
                doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#structure',
                context={'has_queries': has_queries, 'has_searches': has_searches}
            ))
        
        return messages


class DataSourceQueryStructureRule(ValidationRule):
    """Rule that validates query item structure."""
    
    def __init__(self):
        super().__init__(
            rule_id='DATA_SOURCE_QUERY_STRUCTURE',
            description='Query items must have required fields and valid structure',
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        if 'queries' in data and isinstance(data['queries'], list):
            for index, query in enumerate(data['queries']):
                if not isinstance(query, dict):
                    continue
                
                # Check required fields
                if 'scorecard_id' not in query:
                    messages.append(LintMessage(
                        level=self.severity,
                        code='DATA_SOURCE_QUERY_MISSING_SCORECARD_ID',
                        title='Missing Scorecard ID',
                        message=f'Query item {index + 1} is missing required "scorecard_id" field.',
                        suggestion='Add a "scorecard_id" field with a numeric scorecard identifier.',
                        doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                        context={'query_index': index, 'field': 'scorecard_id'}
                    ))
                
                if 'number' not in query:
                    messages.append(LintMessage(
                        level=self.severity,
                        code='DATA_SOURCE_QUERY_MISSING_NUMBER',
                        title='Missing Number Field',
                        message=f'Query item {index + 1} is missing required "number" field.',
                        suggestion='Add a "number" field specifying how many records to retrieve.',
                        doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                        context={'query_index': index, 'field': 'number'}
                    ))
                
                # Validate number is positive
                if 'number' in query:
                    number = query['number']
                    if not isinstance(number, (int, float)) or number < 1:
                        messages.append(LintMessage(
                            level=self.severity,
                            code='DATA_SOURCE_QUERY_INVALID_NUMBER',
                            title='Invalid Number Value',
                            message=f'Query item {index + 1} has invalid "number" value. Must be a positive integer.',
                            suggestion='Set "number" to a positive integer (e.g., 1000, 5000).',
                            doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                            context={'query_index': index, 'current_value': number}
                        ))
                
                # Validate scorecard_id is numeric
                if 'scorecard_id' in query:
                    scorecard_id = query['scorecard_id']
                    if not isinstance(scorecard_id, (int, float)):
                        messages.append(LintMessage(
                            level=self.severity,
                            code='DATA_SOURCE_QUERY_INVALID_SCORECARD_ID',
                            title='Invalid Scorecard ID',
                            message=f'Query item {index + 1} has invalid "scorecard_id" value. Must be a number.',
                            suggestion='Set "scorecard_id" to a numeric scorecard identifier (e.g., 1329, 555).',
                            doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                            context={'query_index': index, 'current_value': scorecard_id}
                        ))
        
        return messages


class DataSourceSearchStructureRule(ValidationRule):
    """Rule that validates search item structure."""
    
    def __init__(self):
        super().__init__(
            rule_id='DATA_SOURCE_SEARCH_STRUCTURE',
            description='Search items must have required fields and valid file paths',
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        if 'searches' in data and isinstance(data['searches'], list):
            for index, search in enumerate(data['searches']):
                if not isinstance(search, dict):
                    continue
                
                # Check required fields
                if 'item_list_filename' not in search:
                    messages.append(LintMessage(
                        level=self.severity,
                        code='DATA_SOURCE_SEARCH_MISSING_FILENAME',
                        title='Missing Item List Filename',
                        message=f'Search item {index + 1} is missing required "item_list_filename" field.',
                        suggestion='Add an "item_list_filename" field with a path to a CSV or text file.',
                        doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#searches',
                        context={'search_index': index, 'field': 'item_list_filename'}
                    ))
                
                # Validate file extension
                if 'item_list_filename' in search:
                    filename = search['item_list_filename']
                    if isinstance(filename, str):
                        filename_lower = filename.lower()
                        if not filename_lower.endswith('.csv') and not filename_lower.endswith('.txt'):
                            messages.append(LintMessage(
                                level='warning',
                                code='DATA_SOURCE_SEARCH_INVALID_FILE_TYPE',
                                title='Unusual File Type',
                                message=f'Search item {index + 1} file "{filename}" should typically be a .csv or .txt file.',
                                suggestion='Use a .csv or .txt file for item lists.',
                                doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#searches',
                                context={'search_index': index, 'filename': filename}
                            ))
        
        return messages


class FeedbackItemsValidationRule(ValidationRule):
    """Rule that validates FeedbackItems data source parameters."""
    
    def __init__(self):
        super().__init__(
            rule_id='FEEDBACK_ITEMS_VALIDATION',
            description='FeedbackItems data source must have required parameters',
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Only apply this rule to FeedbackItems
        if data.get('class') != 'FeedbackItems':
            return messages
        
        # Required fields for FeedbackItems
        required_fields = ['scorecard', 'score', 'days']
        
        for field in required_fields:
            if field not in data:
                messages.append(LintMessage(
                    level=self.severity,
                    code=f'FEEDBACK_ITEMS_MISSING_{field.upper()}',
                    title=f'Missing {field.title()} Field',
                    message=f'FeedbackItems data source is missing required "{field}" field.',
                    suggestion=f'Add a "{field}" field to specify the {field} parameter.',
                    doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
                    context={'field': field}
                ))
        
        # Validate days is positive integer
        if 'days' in data:
            days = data['days']
            if not isinstance(days, int) or days <= 0:
                messages.append(LintMessage(
                    level=self.severity,
                    code='FEEDBACK_ITEMS_INVALID_DAYS',
                    title='Invalid Days Value',
                    message='FeedbackItems "days" must be a positive integer.',
                    suggestion='Set "days" to a positive integer (e.g., 7, 14, 30).',
                    doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
                    context={'current_value': days}
                ))
        
        # Validate limit is positive integer if present
        if 'limit' in data:
            limit = data['limit']
            if not isinstance(limit, int) or limit <= 0:
                messages.append(LintMessage(
                    level=self.severity,
                    code='FEEDBACK_ITEMS_INVALID_LIMIT',
                    title='Invalid Limit Value',
                    message='FeedbackItems "limit" must be a positive integer.',
                    suggestion='Set "limit" to a positive integer (e.g., 100, 500, 1000).',
                    doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
                    context={'current_value': limit}
                ))
        
        # Validate limit_per_cell is positive integer if present
        if 'limit_per_cell' in data:
            limit_per_cell = data['limit_per_cell']
            if not isinstance(limit_per_cell, int) or limit_per_cell <= 0:
                messages.append(LintMessage(
                    level=self.severity,
                    code='FEEDBACK_ITEMS_INVALID_LIMIT_PER_CELL',
                    title='Invalid Limit Per Cell Value',
                    message='FeedbackItems "limit_per_cell" must be a positive integer.',
                    suggestion='Set "limit_per_cell" to a positive integer (e.g., 10, 50, 100).',
                    doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
                    context={'current_value': limit_per_cell}
                ))
        
        # Validate scorecard and score are strings
        for field in ['scorecard', 'score']:
            if field in data:
                value = data[field]
                if not isinstance(value, (str, int)):
                    messages.append(LintMessage(
                        level=self.severity,
                        code=f'FEEDBACK_ITEMS_INVALID_{field.upper()}',
                        title=f'Invalid {field.title()} Value',
                        message=f'FeedbackItems "{field}" must be a string or integer.',
                        suggestion=f'Set "{field}" to a string name, key, or integer ID.',
                        doc_url='https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
                        context={'field': field, 'current_value': value}
                    ))
        
        return messages


def create_data_source_validation_rules() -> List[ValidationRule]:
    """Create the complete set of data source validation rules."""
    from .rules import RequiredFieldRule, AllowedValuesRule, TypeValidationRule
    
    return [
        # Required fields
        RequiredFieldRule('class'),
        
        # Type validation
        TypeValidationRule('class', str),
        
        # Allowed data source classes
        AllowedValuesRule('class', ['CallCriteriaDBCache', 'FeedbackItems']),
        
        # Custom data source rules
        DataSourceQueriesOrSearchesRule(),
        DataSourceQueryStructureRule(),
        DataSourceSearchStructureRule(),
        FeedbackItemsValidationRule(),
        
        # Validate balance field
        TypeValidationRule('balance', bool)
    ]