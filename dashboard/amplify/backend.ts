import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import { Stack } from 'aws-cdk-lib';
import { Policy, PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import { StartingPosition } from 'aws-cdk-lib/aws-lambda';
import { DynamoEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

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

// Enable streams on the Task table using L1 construct
const cfnTable = taskTable.node.defaultChild as dynamodb.CfnTable;
if (cfnTable) {
    cfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

// Create stream policy
const policy = new Policy(Stack.of(taskTable), 'TaskDispatcherStreamPolicy', {
    statements: [
        new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'dynamodb:DescribeStream',
                'dynamodb:GetRecords',
                'dynamodb:GetShardIterator',
                'dynamodb:ListStreams'
            ],
            resources: [taskTable.tableArn + '/stream/*']
        })
    ]
});

// Attach the policy to the Lambda function
taskDispatcherStack.taskDispatcherFunction.role?.attachInlinePolicy(policy);

// Create event source mapping
const eventSource = new DynamoEventSource(taskTable, {
    startingPosition: StartingPosition.LATEST,
    batchSize: 1,
    retryAttempts: 3,
    enabled: true
});

// Add the event source to the Lambda function
taskDispatcherStack.taskDispatcherFunction.addEventSource(eventSource);

// Add SQS permissions
taskDispatcherStack.taskDispatcherFunction.addToRolePolicy(
    new PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [process.env.CELERY_QUEUE_URL || '*']
    })
);

export { backend };
