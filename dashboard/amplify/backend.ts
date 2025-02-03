import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';
import { DynamoEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as aws_dynamodb from 'aws-cdk-lib/aws-dynamodb';

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

// Get the Task table and enable streams
const taskTable = backend.data.resources.tables.Task;
const cfnTable = taskTable.node.defaultChild as aws_dynamodb.CfnTable;
cfnTable.streamSpecification = {
    streamViewType: aws_dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
};

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
