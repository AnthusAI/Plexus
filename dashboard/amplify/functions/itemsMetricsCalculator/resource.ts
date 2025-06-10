import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import { execSync } from 'child_process';
import { Policy, PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';

// Get the directory path in ES module context
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Interface for ItemsMetricsCalculator stack props
interface ItemsMetricsCalculatorStackProps extends StackProps {
  graphqlEndpointArn?: string;
  appSyncApiId?: string;
}

// Custom CDK stack for the Python Items Metrics Calculator function
export class ItemsMetricsCalculatorStack extends Stack {
  public readonly itemsMetricsCalculatorFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ItemsMetricsCalculatorStackProps) {
    super(scope, id, props);
    
    // Get the directory containing the function code
    const functionDir = path.join(__dirname, '.');

    // Get GraphQL configuration from props or environment
    const graphqlEndpointArn = props.graphqlEndpointArn || process.env.GRAPHQL_ENDPOINT_ARN || 'WILL_BE_SET_AFTER_DEPLOYMENT';
    const appSyncApiId = props.appSyncApiId || process.env.APPSYNC_API_ID || 'WILL_BE_SET_AFTER_DEPLOYMENT';

    this.itemsMetricsCalculatorFunction = new lambda.Function(this, 'ItemsMetricsCalculatorFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              // Create a temporary directory for dependencies
              execSync('mkdir -p /tmp/package');
              
              // Install all dependencies with their sub-dependencies
              execSync(
                `python3 -m pip install -r ${path.join(functionDir, 'requirements.txt')} -t /tmp/package --platform manylinux2014_x86_64 --implementation cp --python 3.11 --only-binary=:all: --upgrade`
              );

              // Copy dependencies to the output directory
              execSync(`cp -r /tmp/package/* ${outputDir}`);
              
              // Copy function code to output directory
              execSync(`cp -r ${functionDir}/* ${outputDir}`);
              
              // Clean up
              execSync('rm -rf /tmp/package');
              
              return true;
            }
          }
        }
      }),
      timeout: Duration.minutes(5), // Longer timeout for potentially large data processing
      memorySize: 512, // More memory for processing large datasets
      environment: {
        // Use AWS-standard environment variable names that match the GraphQL resolver
        API_PLEXUSDASHBOARD_GRAPHQLAPIARNOUTPUT: graphqlEndpointArn
      }
    });

    // Add permissions for AppSync access
    this.itemsMetricsCalculatorFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'appsync:GraphQL'
        ],
        resources: [
          `arn:aws:appsync:${this.region}:${this.account}:apis/${appSyncApiId}/*`
        ]
      })
    );

    // Add logging permissions
    this.itemsMetricsCalculatorFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'logs:CreateLogGroup',
          'logs:CreateLogStream',
          'logs:PutLogEvents'
        ],
        resources: ['*']
      })
    );

    new CfnOutput(this, 'ItemsMetricsCalculatorFunctionArn', {
      value: this.itemsMetricsCalculatorFunction.functionArn,
      exportName: `${this.stackName}-ItemsMetricsCalculatorFunctionArn`
    });

    new CfnOutput(this, 'ItemsMetricsCalculatorFunctionName', {
      value: this.itemsMetricsCalculatorFunction.functionName,
      exportName: `${this.stackName}-ItemsMetricsCalculatorFunctionName`
    });
  }
} 