"""
Utility for discovering Amplify-created DynamoDB table ARNs via CloudFormation API.

This module provides functions to locate the Amplify Gen2 CloudFormation stack
and extract DynamoDB table ARNs for tables created by Amplify.
"""

import boto3
from typing import Dict, Optional, List
from botocore.exceptions import ClientError


class AmplifyTableDiscovery:
    """
    Discovers DynamoDB table ARNs from Amplify CloudFormation stacks.
    
    Amplify Gen2 creates nested CloudFormation stacks with auto-generated names.
    This class navigates the stack hierarchy to find DynamoDB table resources.
    """
    
    def __init__(self, region: str = 'us-west-2'):
        """
        Initialize the discovery client.
        
        Args:
            region: AWS region where Amplify stack is deployed
        """
        self.cfn_client = boto3.client('cloudformation', region_name=region)
        self.region = region
    
    def find_amplify_stack(self, stack_name_pattern: str = 'amplify-plexusdashboard') -> Optional[str]:
        """
        Find the Amplify root stack by name pattern.
        
        Args:
            stack_name_pattern: Pattern to match in stack names
            
        Returns:
            Stack name if found, None otherwise
        """
        try:
            paginator = self.cfn_client.get_paginator('list_stacks')
            
            # Collect matching stacks
            matching_stacks = []
            for page in paginator.paginate(
                StackStatusFilter=[
                    'CREATE_COMPLETE',
                    'UPDATE_COMPLETE',
                    'UPDATE_ROLLBACK_COMPLETE'
                ]
            ):
                for stack in page['StackSummaries']:
                    if stack_name_pattern in stack['StackName']:
                        matching_stacks.append(stack['StackName'])
            
            # Find the root stack (one without a ParentId)
            for stack_name in matching_stacks:
                try:
                    response = self.cfn_client.describe_stacks(StackName=stack_name)
                    if response['Stacks']:
                        stack_info = response['Stacks'][0]
                        # Root stacks have no ParentId
                        if stack_info.get('ParentId') is None:
                            return stack_name
                except ClientError:
                    continue
            
            return None
        except ClientError as e:
            print(f"Error finding Amplify stack: {e}")
            return None
    
    def get_nested_stacks(self, parent_stack_name: str) -> List[str]:
        """
        Get all nested stack names from a parent stack.
        
        Args:
            parent_stack_name: Name of the parent CloudFormation stack
            
        Returns:
            List of nested stack names
        """
        nested_stacks = []
        
        try:
            response = self.cfn_client.describe_stack_resources(
                StackName=parent_stack_name
            )
            
            for resource in response['StackResources']:
                if resource['ResourceType'] == 'AWS::CloudFormation::Stack':
                    nested_stacks.append(resource['PhysicalResourceId'])
            
            return nested_stacks
        except ClientError as e:
            print(f"Error getting nested stacks for {parent_stack_name}: {e}")
            return []
    
    def find_table_in_stack(self, stack_name: str, logical_id_pattern: str) -> Optional[Dict[str, str]]:
        """
        Find a DynamoDB table resource in a specific stack.
        
        Args:
            stack_name: CloudFormation stack name
            logical_id_pattern: Pattern to match in logical resource IDs (e.g., 'Item', 'ScoreResult')
            
        Returns:
            Dict with 'arn' and 'stream_arn' if found, None otherwise
        """
        try:
            response = self.cfn_client.describe_stack_resources(
                StackName=stack_name
            )
            
            for resource in response['StackResources']:
                # Amplify Gen2 uses Custom::AmplifyDynamoDBTable instead of AWS::DynamoDB::Table
                is_table = (resource['ResourceType'] == 'AWS::DynamoDB::Table' or 
                           resource['ResourceType'] == 'Custom::AmplifyDynamoDBTable')
                
                # Match pattern in logical ID - look for exact match with "Table" suffix
                # e.g., "ItemTable", "ScoreResultTable", "TaskTable", "EvaluationTable"
                matches_pattern = (f"{logical_id_pattern}Table" == resource['LogicalResourceId'])
                
                if is_table and matches_pattern:
                    table_name = resource['PhysicalResourceId']
                    table_arn = f"arn:aws:dynamodb:{self.region}:{self._get_account_id()}:table/{table_name}"
                    
                    # Get the actual stream ARN from DynamoDB
                    actual_stream_arn = self._get_stream_arn(table_name)
                    
                    return {
                        'table_name': table_name,
                        'table_arn': table_arn,
                        'stream_arn': actual_stream_arn,
                        'logical_id': resource['LogicalResourceId']
                    }
            
            return None
        except ClientError as e:
            print(f"Error finding table in stack {stack_name}: {e}")
            return None
    
    def _get_stream_arn(self, table_name: str) -> str:
        """
        Get the actual stream ARN from a DynamoDB table.
        
        Args:
            table_name: DynamoDB table name
            
        Returns:
            Stream ARN or wildcard pattern if not found
        """
        try:
            dynamodb = boto3.client('dynamodb', region_name=self.region)
            response = dynamodb.describe_table(TableName=table_name)
            stream_arn = response['Table'].get('LatestStreamArn')
            
            if stream_arn:
                return stream_arn
            else:
                # Fallback to wildcard if no stream (shouldn't happen)
                account_id = self._get_account_id()
                return f"arn:aws:dynamodb:{self.region}:{account_id}:table/{table_name}/stream/*"
                
        except Exception as e:
            print(f"Warning: Could not get stream ARN for {table_name}: {e}")
            # Fallback to wildcard pattern
            account_id = self._get_account_id()
            return f"arn:aws:dynamodb:{self.region}:{account_id}:table/{table_name}/stream/*"
    
    def find_table_recursively(self, stack_name: str, logical_id_pattern: str) -> Optional[Dict[str, str]]:
        """
        Recursively search for a table in a stack and all its nested stacks.
        
        Args:
            stack_name: CloudFormation stack name to search
            logical_id_pattern: Pattern to match in logical resource IDs
            
        Returns:
            Dict with table information if found, None otherwise
        """
        # First check the current stack
        table_info = self.find_table_in_stack(stack_name, logical_id_pattern)
        if table_info:
            return table_info
        
        # If not found, search nested stacks
        nested_stacks = self.get_nested_stacks(stack_name)
        for nested_stack in nested_stacks:
            table_info = self.find_table_recursively(nested_stack, logical_id_pattern)
            if table_info:
                return table_info
        
        return None
    
    def discover_amplify_tables(self, 
                                table_patterns: Dict[str, str],
                                amplify_stack_pattern: str = 'amplify-plexusdashboard') -> Dict[str, Dict[str, str]]:
        """
        Discover multiple Amplify DynamoDB tables.
        
        Args:
            table_patterns: Dict mapping table keys to logical ID patterns
                           e.g., {'item': 'Item', 'scoreResult': 'ScoreResult'}
            amplify_stack_pattern: Pattern to find Amplify root stack
            
        Returns:
            Dict mapping table keys to table information dicts
        """
        results = {}
        
        # Find the Amplify root stack
        root_stack = self.find_amplify_stack(amplify_stack_pattern)
        if not root_stack:
            print(f"Could not find Amplify stack matching pattern: {amplify_stack_pattern}")
            return results
        
        print(f"Found Amplify root stack: {root_stack}")
        
        # Search for each table
        for table_key, pattern in table_patterns.items():
            print(f"Searching for {table_key} table (pattern: {pattern})...")
            table_info = self.find_table_recursively(root_stack, pattern)
            
            if table_info:
                results[table_key] = table_info
                print(f"  Found: {table_info['table_name']}")
            else:
                print(f"  Not found: {table_key}")
        
        return results
    
    def _get_account_id(self) -> str:
        """Get the AWS account ID."""
        sts_client = boto3.client('sts')
        return sts_client.get_caller_identity()['Account']


def discover_tables_for_metrics_aggregation(region: str = 'us-west-2', 
                                            stack_pattern: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """
    Convenience function to discover all tables needed for metrics aggregation.
    
    Args:
        region: AWS region
        stack_pattern: CloudFormation stack name pattern to search for.
                      If not provided, will use AMPLIFY_STACK_PATTERN env var.
        
    Returns:
        Dict with 'item', 'scoreResult', 'task', 'evaluation' table information
        
    Raises:
        ValueError: If stack_pattern is not provided and AMPLIFY_STACK_PATTERN env var is not set
    """
    import os
    
    # Get stack pattern from parameter or environment variable
    if stack_pattern is None:
        stack_pattern = os.environ.get('AMPLIFY_STACK_PATTERN')
        if not stack_pattern:
            raise ValueError(
                "AMPLIFY_STACK_PATTERN environment variable must be set. "
                "Example: AMPLIFY_STACK_PATTERN='amplify-d1cegb1ft4iove-main-branch'"
            )
    
    discovery = AmplifyTableDiscovery(region=region)
    
    table_patterns = {
        'item': 'Item',
        'scoreResult': 'ScoreResult',
        'task': 'Task',
        'evaluation': 'Evaluation'
    }
    
    return discovery.discover_amplify_tables(table_patterns, stack_pattern)


if __name__ == '__main__':
    # Test the discovery
    print("Testing Amplify table discovery...")
    tables = discover_tables_for_metrics_aggregation()
    
    print("\nDiscovered tables:")
    for key, info in tables.items():
        print(f"\n{key}:")
        print(f"  Table Name: {info['table_name']}")
        print(f"  Table ARN: {info['table_arn']}")
        print(f"  Stream ARN: {info['stream_arn']}")

