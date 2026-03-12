"""
Stack for metrics aggregation Lambda function.

This stack creates a Lambda function that processes DynamoDB streams from
Amplify-created tables and updates AggregatedMetrics in real-time.
"""

from aws_cdk import (
    Stack,
    Duration,
    Tags,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
)
from aws_cdk.aws_lambda_event_sources import DynamoEventSource
from aws_cdk.aws_lambda import StartingPosition
from constructs import Construct
import os

from .shared.naming import get_resource_name
from .shared.config import EnvironmentConfig


class MetricsAggregationStack(Stack):
    """
    CDK Stack for metrics aggregation Lambda function.
    
    Discovers Amplify DynamoDB tables via CloudFormation API and attaches
    stream event sources to update AggregatedMetrics in real-time.
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        **kwargs
    ) -> None:
        """
        Initialize the metrics aggregation stack.
        
        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment: Environment name ('staging' or 'production')
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)
        
        self.env_name = environment
        
        # Add environment tags
        Tags.of(self).add("Environment", environment)
        Tags.of(self).add("Service", "metrics-aggregation")
        Tags.of(self).add("ManagedBy", "CDK")

        # Load environment-specific configuration from Secrets Manager
        config = EnvironmentConfig(self, environment)
        
        # Load Amplify table ARNs from Secrets Manager
        # These are populated by running discover_and_save_tables.py and create-secrets-{environment}.sh
        print(f"Loading Amplify table ARNs from Secrets Manager for {environment}...")
        region = kwargs.get('env').region if kwargs.get('env') else 'us-west-2'

        # Build tables dict from Secrets Manager configuration
        tables = {}
        table_types = ['item', 'scoreresult', 'task', 'evaluation']

        for table_type in table_types:
            secret_prefix = f"table-{table_type.lower()}"
            table_name = config.get_value(f"{secret_prefix}-name")
            table_arn = config.get_value(f"{secret_prefix}-arn")
            stream_arn = config.get_value(f"{secret_prefix}-stream-arn")

            # Only add if all values exist (CDK tokens will be resolved at deploy time)
            tables[table_type] = {
                'table_name': table_name,
                'table_arn': table_arn,
                'stream_arn': stream_arn
            }
            print(f"  Loading {table_type} from Secrets Manager")

        print(f"Configured {len(tables)} table stream sources")
        
        # Get the build directory containing the Lambda function code
        # If it doesn't exist, run the build script to create it
        function_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'build',
            'metrics_aggregator'
        )

        if not os.path.exists(function_dir):
            print(f"⚠️  Lambda build directory not found, running build_lambda.sh...")
            import subprocess
            build_script = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'build_lambda.sh'
            )
            subprocess.run(['bash', build_script], check=True, cwd=os.path.dirname(build_script))
            print(f"✅ Lambda build completed")
        
        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self,
            "MetricsAggregatorRole",
            role_name=get_resource_name("lambda", self.env_name, "metrics-aggregator-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                # Basic Lambda execution (CloudWatch Logs)
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ]
        )
        
        # No Secrets Manager access needed - using environment variables
        
        # Grant DynamoDB stream read permissions for all discovered tables
        for table_key, table_info in tables.items():
            lambda_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        'dynamodb:DescribeStream',
                        'dynamodb:GetRecords',
                        'dynamodb:GetShardIterator',
                        'dynamodb:ListStreams'
                    ],
                    resources=[table_info['stream_arn']]
                )
            )
        
        # Grant DynamoDB write permissions for AggregatedMetrics table
        # Note: Using wildcard since we don't know the exact table name
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'dynamodb:Query',
                    'dynamodb:PutItem',
                    'dynamodb:UpdateItem',
                    'dynamodb:GetItem'
                ],
                resources=[
                    f"arn:aws:dynamodb:{region}:*:table/*AggregatedMetrics*",
                    f"arn:aws:dynamodb:{region}:*:table/*AggregatedMetrics*/index/*"
                ]
            )
        )
        
        # Grant AppSync/GraphQL API permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'appsync:GraphQL'
                ],
                resources=['*']  # AppSync doesn't support resource-level permissions for GraphQL
            )
        )

        # Grant read access to Secrets Manager
        config.secret.grant_read(lambda_role)

        # Create Lambda function
        self.lambda_function = lambda_.Function(
            self,
            "MetricsAggregatorFunction",
            function_name=get_resource_name("lambda", self.env_name, "metrics-aggregator"),
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.handler',
            code=lambda_.Code.from_asset(function_dir),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                'GRAPHQL_ENDPOINT': config.get_value("api-url"),
                'GRAPHQL_API_KEY': config.get_value("api-key"),
                'ENVIRONMENT': environment
            },
            description=f"Processes DynamoDB streams to update AggregatedMetrics ({environment})"
        )
        
        # Configure stream event sources with table-specific batch settings
        stream_configs = {
            'item': {'batch_size': 10, 'batch_window': 15},
            'scoreresult': {'batch_size': 100, 'batch_window': 15},  # Fixed: lowercase to match table_types
            'task': {'batch_size': 1, 'batch_window': 15},
            'evaluation': {'batch_size': 1, 'batch_window': 15}
        }
        
        # Add event sources for each discovered table
        for table_key, table_info in tables.items():
            if table_key not in stream_configs:
                print(f"Warning: No stream config for {table_key}, skipping")
                continue
            
            config_data = stream_configs[table_key]
            
            # Import the table with stream ARN
            table = dynamodb.Table.from_table_attributes(
                self,
                f"{table_key.capitalize()}Table",
                table_arn=table_info['table_arn'],
                table_stream_arn=table_info['stream_arn']
            )
            
            # Create event source
            event_source = DynamoEventSource(
                table,
                starting_position=StartingPosition.LATEST,
                batch_size=config_data['batch_size'],
                max_batching_window=Duration.seconds(config_data['batch_window']),
                retry_attempts=3,
                enabled=True,
                bisect_batch_on_error=True,  # Split batch on errors for better error handling
                report_batch_item_failures=True  # Report individual failures
            )
            
            # Add event source to Lambda
            self.lambda_function.add_event_source(event_source)
            
            print(f"Added stream event source for {table_key}: "
                  f"batch_size={config_data['batch_size']}, "
                  f"batch_window={config_data['batch_window']}s")

