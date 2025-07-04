"""
Data source specific validation rules for YAML DSL linter.

These rules validate the CallCriteriaDBCache data source schema.
"""

from typing import List, Dict, Any
from .rules import ValidationRule


class DataSourceQueriesOrSearchesRule(ValidationRule):
    """Rule that ensures either queries or searches is present."""
    
    def __init__(self):
        super().__init__(
            rule_id='DATA_SOURCE_QUERIES_OR_SEARCHES_REQUIRED',
            description='Data source must have either queries or searches defined',
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
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


def create_data_source_validation_rules() -> List[ValidationRule]:
    """Create the complete set of data source validation rules."""
    from .rules import RequiredFieldRule, AllowedValuesRule, TypeValidationRule
    
    return [
        # Required fields
        RequiredFieldRule('class'),
        
        # Type validation
        TypeValidationRule('class', str),
        
        # Allowed data source classes
        AllowedValuesRule('class', ['CallCriteriaDBCache']),
        
        # Custom data source rules
        DataSourceQueriesOrSearchesRule(),
        DataSourceQueryStructureRule(),
        DataSourceSearchStructureRule(),
        
        # Validate balance field
        TypeValidationRule('balance', bool)
    ]