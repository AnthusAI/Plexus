import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Duration, CustomResource } from 'aws-cdk-lib';
import { DynamoEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as aws_dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Get the directory path in ES module context
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Create the backend
const backend = defineBackend({
    auth,
    data
});

// Create the TaskDispatcher stack
const taskDispatcherStack = new TaskDispatcherStack(
    backend.createStack('TaskDispatcherStack'),
    'taskDispatcher'
);

// Get the Task table
const taskTable = backend.data.resources.tables.Task;

// Create a custom resource to enable DynamoDB streams
const enableStreamProvider = new cr.Provider(taskDispatcherStack, 'EnableStreamProvider', {
    onEventHandler: new lambda.Function(taskDispatcherStack, 'EnableStreamFunction', {
        runtime: lambda.Runtime.NODEJS_18_X,
        handler: 'index.handler',
        code: lambda.Code.fromAsset(path.join(__dirname, 'custom-resources/enable-stream'), {
            bundling: {
                image: lambda.Runtime.NODEJS_18_X.bundlingImage,
                command: [
                    'bash', '-c', [
                        'npm install @aws-sdk/client-dynamodb',
                        'cp -r /asset-input/* /asset-output/'
                    ].join(' && ')
                ]
            }
        }),
        timeout: Duration.seconds(30)
    })
});

enableStreamProvider.onEventHandler.addToRolePolicy(
    new iam.PolicyStatement({
        actions: ['dynamodb:UpdateTable'],
        resources: [taskTable.tableArn]
    })
);

new CustomResource(taskDispatcherStack, 'EnableTaskTableStream', {
    serviceToken: enableStreamProvider.serviceToken,
    properties: {
        tableName: taskTable.tableName
    }
});

// Create a DynamoDB stream event source
const eventSource = new DynamoEventSource(taskTable, {
    startingPosition: lambda.StartingPosition.LATEST,
    batchSize: 1,
    retryAttempts: 3,
    maxBatchingWindow: Duration.seconds(1),
    enabled: true
});

// Add the event source to the Lambda function
taskDispatcherStack.taskDispatcherFunction.addEventSource(eventSource);

// Add DynamoDB stream permissions
taskDispatcherStack.taskDispatcherFunction.addToRolePolicy(
    new iam.PolicyStatement({
        actions: [
            'dynamodb:GetRecords',
            'dynamodb:GetShardIterator',
            'dynamodb:DescribeStream',
            'dynamodb:ListStreams'
        ],
        resources: [taskTable.tableArn + '/stream/*']
    })
);

// Add SQS permissions
taskDispatcherStack.taskDispatcherFunction.addToRolePolicy(
    new iam.PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [process.env.CELERY_QUEUE_URL || '*']
    })
);

// Configure stream trigger in the data model schema
// Note: The stream configuration should be defined in the data/resource.ts schema
// using the appropriate stream directives

export { backend };
