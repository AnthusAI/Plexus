import { CfnOutput, Duration, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { cpSync, mkdirSync, mkdtempSync, readdirSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import * as path from 'path';
import { execFileSync } from 'child_process';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import * as sqs from 'aws-cdk-lib/aws-sqs';

// Interface for TaskDispatcher stack props
interface TaskDispatcherStackProps extends StackProps {
  readonly taskTable: ITable;
  readonly taskTableStreamArn: string;
}

/**
 * The complete Task-stream-to-command-queue delivery boundary.
 *
 * Both the long-lived ECS command service and the explicitly enabled sandbox
 * dispatcher use this construct. Keeping the queues, Lambda bundle, stream
 * mapping, and DynamoDB grants together prevents the two compositions from
 * silently diverging.
 */
export class TaskStreamDispatcher extends Construct {
  public readonly commandQueue: sqs.Queue;
  public readonly commandDeadLetterQueue: sqs.Queue;
  public readonly dispatcherFailureQueue: sqs.Queue;
  public readonly dispatcherFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: TaskDispatcherStackProps) {
    super(scope, id);

    const functionDir = path.join(process.cwd(), 'amplify/functions/taskDispatcher');

    this.commandDeadLetterQueue = new sqs.Queue(this, 'CommandDeadLetterQueue', {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      retentionPeriod: Duration.days(14),
    });
    this.dispatcherFailureQueue = new sqs.Queue(this, 'DispatcherFailureQueue', {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      retentionPeriod: Duration.days(14),
    });
    this.commandQueue = new sqs.Queue(this, 'CommandQueue', {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      visibilityTimeout: Duration.hours(12),
      receiveMessageWaitTime: Duration.seconds(20),
      deadLetterQueue: { queue: this.commandDeadLetterQueue, maxReceiveCount: 5 },
    });

    this.dispatcherFunction = new lambda.Function(this, 'TaskStreamDispatcher', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              const packageDir = mkdtempSync(path.join(tmpdir(), 'task-dispatcher-'));
              mkdirSync(outputDir, { recursive: true });

              try {
                execFileSync(
                  'python3',
                  [
                    '-m',
                    'pip',
                    'install',
                    '-r',
                    path.join(functionDir, 'requirements.txt'),
                    '-t',
                    packageDir,
                    '--platform',
                    'manylinux2014_x86_64',
                    '--implementation',
                    'cp',
                    '--python-version',
                    '3.11',
                    '--only-binary=:all:',
                    '--upgrade',
                  ],
                  { stdio: 'inherit' }
                );

                for (const entry of readdirSync(packageDir)) {
                  cpSync(path.join(packageDir, entry), path.join(outputDir, entry), {
                    recursive: true,
                    force: true,
                  });
                }

                for (const entry of readdirSync(functionDir)) {
                  cpSync(path.join(functionDir, entry), path.join(outputDir, entry), {
                    recursive: true,
                    force: true,
                  });
                }
              } finally {
                rmSync(packageDir, { recursive: true, force: true });
              }

              return true;
            }
          }
        }
      }),
      timeout: Duration.seconds(30),
      environment: {
        COMMAND_QUEUE_URL: this.commandQueue.queueUrl,
      }
    });

    // Add SQS permissions
    this.commandQueue.grantSendMessages(this.dispatcherFunction);
    this.dispatcherFailureQueue.grantSendMessages(this.dispatcherFunction);

    this.dispatcherFunction.addToRolePolicy(
      new PolicyStatement({
        actions: ['dynamodb:UpdateItem'],
        resources: [props.taskTable.tableArn]
      })
    );

    this.dispatcherFunction.addToRolePolicy(new PolicyStatement({
      actions: [
        'dynamodb:DescribeStream',
        'dynamodb:GetRecords',
        'dynamodb:GetShardIterator',
        'dynamodb:ListStreams',
      ],
      resources: [props.taskTableStreamArn],
    }));

    const eventSourceMapping = new lambda.CfnEventSourceMapping(this, 'TaskStreamMapping', {
      functionName: this.dispatcherFunction.functionName,
      eventSourceArn: props.taskTableStreamArn,
      startingPosition: 'LATEST',
      batchSize: 1,
      maximumRetryAttempts: 3,
      enabled: true,
    });
    // The pinned CDK L1 type predates DestinationConfig for DynamoDB streams,
    // but CloudFormation supports it. Keep failed records durable rather than
    // silently dropping a READY Task after stream retries are exhausted.
    eventSourceMapping.addPropertyOverride(
      'DestinationConfig.OnFailure.Destination',
      this.dispatcherFailureQueue.queueArn,
    );
  }
}

// Custom CDK stack for the sandbox-only Python Task Dispatcher function.
export class TaskDispatcherStack extends Stack {
  public readonly taskDispatcherFunction: lambda.Function;
  public readonly commandQueue: sqs.Queue;

  constructor(scope: Construct, id: string, props: TaskDispatcherStackProps) {
    super(scope, id, props);
    const dispatcher = new TaskStreamDispatcher(this, 'TaskStreamDispatcher', props);
    this.taskDispatcherFunction = dispatcher.dispatcherFunction;
    this.commandQueue = dispatcher.commandQueue;

    new CfnOutput(this, 'TaskDispatcherFunctionArn', {
      value: this.taskDispatcherFunction.functionArn,
      exportName: `${this.stackName}-TaskDispatcherFunctionArn`
    });
    new CfnOutput(this, 'TaskDispatcherCommandQueueUrl', { value: this.commandQueue.queueUrl });
  }
} 
