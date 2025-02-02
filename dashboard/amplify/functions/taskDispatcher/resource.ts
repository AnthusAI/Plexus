import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import { execSync } from 'child_process';

// Get the directory path in ES module context
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Custom CDK stack for the Python Task Dispatcher function
export class TaskDispatcherStack extends Stack {
  public readonly taskDispatcherFunction: lambda.Function;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);
    
    // Get the directory containing the function code
    const functionDir = path.join(__dirname, '.');

    this.taskDispatcherFunction = new lambda.Function(this, 'TaskDispatcherFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              // Install Python dependencies using pip
              execSync(
                `python3 -m pip install -r ${path.join(functionDir, 'requirements.txt')} -t ${outputDir} --platform manylinux2014_x86_64 --only-binary=:all:`
              );
              // Copy function code to output directory
              execSync(`cp -r ${functionDir}/* ${outputDir}`);
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