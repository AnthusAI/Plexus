import { CfnOutput, Stack, StackProps, Duration, Fn } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { Policy, PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';

// Interface for ItemsMetricsCalculator stack props
interface ItemsMetricsCalculatorStackProps extends StackProps {
  // Remove direct props to break cyclic dependency
  // graphqlEndpoint and apiKey will be imported from CloudFormation exports
}

// Custom CDK stack for the TypeScript Items Metrics Calculator function
export class ItemsMetricsCalculatorStack extends Stack {
  public readonly itemsMetricsCalculatorFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ItemsMetricsCalculatorStackProps) {
    super(scope, id, props);

    // Get the directory containing the function code
    const functionDir = path.join(process.cwd(), 'amplify/functions/itemsMetricsCalculator');

    // Import GraphQL API URL and API key from the main stack exports
    const graphqlEndpoint = Fn.importValue('amplify-data-GraphQLAPIURL');
    const apiKey = Fn.importValue('amplify-data-APIKey');

    this.itemsMetricsCalculatorFunction = new lambda.Function(this, 'ItemsMetricsCalculatorFunction', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
              bundling: {
        image: lambda.Runtime.NODEJS_18_X.bundlingImage,
        command: [
          'bash', '-c',
          'npm install && npm run build && cp -au . /asset-output'
        ],
      }
      }),
      timeout: Duration.minutes(10),
      memorySize: 512,
      environment: {
        PLEXUS_API_URL: graphqlEndpoint,
        PLEXUS_API_KEY: apiKey
      }
    });

    // Grant permissions to make AppSync GraphQL calls
    this.itemsMetricsCalculatorFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['appsync:GraphQL'],
        resources: [`arn:aws:appsync:${this.region}:${this.account}:apis/*`],
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