import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { execSync } from 'child_process';
import { Policy, PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';

// Interface for ItemsMetricsCalculator stack props
interface ItemsMetricsCalculatorStackProps extends StackProps {
  graphqlEndpoint: string;
  apiKey: string;
}

// Custom CDK stack for the Python Items Metrics Calculator function
export class ItemsMetricsCalculatorStack extends Stack {
  public readonly itemsMetricsCalculatorFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ItemsMetricsCalculatorStackProps) {
    super(scope, id, props);
    
    // Get the directory containing the function code
    const functionDir = path.join(process.cwd(), 'amplify/functions/itemsMetricsCalculator');

    this.itemsMetricsCalculatorFunction = new lambda.Function(this, 'ItemsMetricsCalculatorFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              try {
                const command = `
                    # Copy handler and requirements
                    cp ${path.join(functionDir, 'index.py')} ${outputDir}
                    cp ${path.join(functionDir, 'requirements.txt')} ${outputDir}

                    # Copy the shared plexus metrics module
                    rsync -av --exclude '__pycache__' ${path.join(process.cwd(), '../plexus/metrics/')} ${path.join(outputDir, 'plexus/metrics/')}
                    
                    # Create __init__.py to make plexus a package
                    touch ${path.join(outputDir, 'plexus/__init__.py')}

                    # Install python dependencies
                    python3 -m pip install -r ${path.join(outputDir, 'requirements.txt')} -t ${outputDir} --platform manylinux2014_x86_64 --implementation cp --python 3.11 --only-binary=:all: --upgrade
                `;
                execSync(command, { stdio: 'inherit' });
                return true;
              } catch (e) {
                console.error("Bundling failed:", e);
                return false;
              }
            }
          }
        }
      }),
      timeout: Duration.minutes(10),
      memorySize: 512,
      environment: {
        PLEXUS_API_URL: props.graphqlEndpoint,
        PLEXUS_API_KEY: props.apiKey
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