import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';

// Custom CDK stack for the Python Task Dispatcher function
export class TaskDispatcherStack extends Stack {
  public readonly taskDispatcherFunction: lambda.Function;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);
    
    // Assuming the function code is in the same directory as this file
    const functionDir = path.join(__dirname, '.');

    this.taskDispatcherFunction = new lambda.Function(this, 'TaskDispatcherFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              const child_process = require('child_process');
              // Install Python dependencies using pip
              child_process.execSync(
                `python3 -m pip install -r ${path.join(functionDir, 'requirements.txt')} -t ${outputDir} --platform manylinux2014_x86_64 --only-binary=:all:`
              );
              // Copy function code to output directory
              child_process.execSync(`cp -r ${functionDir}/* ${outputDir}`);
              return true;
            }
          }
        }
      }),
      timeout: Duration.seconds(30),
      environment: {
        CELERY_BROKER_URL: process.env.CELERY_BROKER_URL || '',
        CELERY_RESULT_BACKEND: process.env.CELERY_RESULT_BACKEND || ''
      }
    });

    new CfnOutput(this, 'TaskDispatcherFunctionArn', {
      value: this.taskDispatcherFunction.functionArn,
      exportName: 'TaskDispatcherFunctionArn'
    });
  }
} 