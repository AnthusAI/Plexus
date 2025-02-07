import { CfnOutput, Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';
import { execSync } from 'child_process';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { DynamoEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import { StartingPosition } from 'aws-cdk-lib/aws-lambda';
import { Policy, PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';

// Get the directory path in ES module context
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Interface for TaskDispatcher stack props
interface TaskDispatcherStackProps extends StackProps {
  taskTable: ITable;
  celeryAwsAccessKeyId?: string;
  celeryAwsSecretAccessKey?: string;
  celeryAwsRegion?: string;
  celeryResultBackendTemplate?: string;
}

// Custom CDK stack for the Python Task Dispatcher function
export class TaskDispatcherStack extends Stack {
  public readonly taskDispatcherFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: TaskDispatcherStackProps) {
    super(scope, id, props);
    
    // Get the directory containing the function code
    const functionDir = path.join(__dirname, '.');

    // Get Celery configuration from props or environment
    const celeryAwsAccessKeyId = props.celeryAwsAccessKeyId || process.env.CELERY_AWS_ACCESS_KEY_ID || 'WILL_BE_SET_AFTER_DEPLOYMENT';
    const celeryAwsSecretAccessKey = props.celeryAwsSecretAccessKey || process.env.CELERY_AWS_SECRET_ACCESS_KEY || 'WILL_BE_SET_AFTER_DEPLOYMENT';
    const celeryAwsRegion = props.celeryAwsRegion || process.env.CELERY_AWS_REGION_NAME || Stack.of(this).region;
    const celeryResultBackendTemplate = props.celeryResultBackendTemplate || process.env.CELERY_RESULT_BACKEND_TEMPLATE || 'WILL_BE_SET_AFTER_DEPLOYMENT';

    this.taskDispatcherFunction = new lambda.Function(this, 'TaskDispatcherFunction', {
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
      timeout: Duration.seconds(30),
      environment: {
        CELERY_AWS_ACCESS_KEY_ID: celeryAwsAccessKeyId,
        CELERY_AWS_SECRET_ACCESS_KEY: celeryAwsSecretAccessKey,
        CELERY_AWS_REGION_NAME: celeryAwsRegion,
        CELERY_RESULT_BACKEND_TEMPLATE: celeryResultBackendTemplate
      }
    });

    // Add SQS permissions
    this.taskDispatcherFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'sqs:SendMessage',
          'sqs:ReceiveMessage',
          'sqs:DeleteMessage',
          'sqs:GetQueueAttributes'
        ],
        resources: ['*'] // You might want to restrict this to specific queues
      })
    );

    // Create stream policy
    const policy = new Policy(this, 'TaskDispatcherStreamPolicy', {
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'dynamodb:DescribeStream',
            'dynamodb:GetRecords',
            'dynamodb:GetShardIterator',
            'dynamodb:ListStreams'
          ],
          resources: [props.taskTable.tableArn + '/stream/*']
        })
      ]
    });

    // Attach the policy to the Lambda function
    this.taskDispatcherFunction.role?.attachInlinePolicy(policy);

    // Create event source mapping
    const eventSource = new DynamoEventSource(props.taskTable, {
      startingPosition: StartingPosition.LATEST,
      batchSize: 1,
      retryAttempts: 3,
      enabled: true
    });

    // Add the event source to the Lambda function
    this.taskDispatcherFunction.addEventSource(eventSource);

    new CfnOutput(this, 'TaskDispatcherFunctionArn', {
      value: this.taskDispatcherFunction.functionArn,
      exportName: `${this.stackName}-TaskDispatcherFunctionArn`
    });
  }
} 