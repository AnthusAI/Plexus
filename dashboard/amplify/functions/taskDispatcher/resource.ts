import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { fileURLToPath } from 'url';

const functionDir = path.dirname(fileURLToPath(import.meta.url));

export class TaskDispatcherStack extends Stack {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Define the Lambda function
    this.function = new lambda.Function(this, 'TaskDispatcherFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
          ]
        }
      }),
      timeout: Duration.seconds(30),
      environment: {
        CELERY_BROKER_URL: process.env.CELERY_BROKER_URL || '',
        CELERY_RESULT_BACKEND: process.env.CELERY_RESULT_BACKEND || ''
      }
    });

    // Output the Lambda function ARN
    new CfnOutput(this, 'TaskDispatcherFunctionArn', {
      value: this.function.functionArn,
      exportName: 'TaskDispatcherFunctionArn'
    });
  }
} 