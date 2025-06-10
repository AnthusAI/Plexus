import { Stack, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';

// Get the directory name of the current module
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Interface for ItemsMetricsCalculator construct props
interface ItemsMetricsCalculatorProps {
  graphqlEndpoint: string;
  apiKey: string;
}

// Custom CDK construct for the Python Items Metrics Calculator function
export class ItemsMetricsCalculator extends Construct {
  public readonly itemsMetricsCalculatorFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ItemsMetricsCalculatorProps) {
    super(scope, id);
    
    const stack = Stack.of(this);

    this.itemsMetricsCalculatorFunction = new lambda.Function(this, 'ItemsMetricsCalculatorFunction', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '.')),
      environment: {
        GRAPHQL_ENDPOINT: props.graphqlEndpoint,
        API_KEY: props.apiKey,
      },
      timeout: Duration.seconds(60),
      memorySize: 512,
    });

    // Grant permissions to make AppSync GraphQL calls
    this.itemsMetricsCalculatorFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['appsync:GraphQL'],
        resources: [`arn:aws:appsync:${stack.region}:${stack.account}:apis/*`],
      })
    );
  }
} 