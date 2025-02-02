import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export class TaskDispatcherStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Define the Lambda function
    const taskDispatcherFunction = new lambda.Function(this, 'TaskDispatcherFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(__dirname),
      functionName: 'TaskDispatcherFunction',
      description: 'Dispatches tasks from DynamoDB to Celery',
      timeout: Duration.seconds(30),
      environment: {
        CELERY_BROKER_URL: process.env.CELERY_BROKER_URL || '',
        CELERY_RESULT_BACKEND: process.env.CELERY_RESULT_BACKEND || ''
      }
    });

    // Output the Lambda function ARN
    new CfnOutput(this, 'TaskDispatcherFunctionArn', {
      value: taskDispatcherFunction.functionArn,
      exportName: 'TaskDispatcherFunctionArn'
    });
  }
} 