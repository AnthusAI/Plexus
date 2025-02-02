import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';
import { DynamoEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';

// Create the backend with the function
const backend = defineBackend({
    auth,
    data
});

// Create the TaskDispatcher stack
const taskDispatcherStack = new TaskDispatcherStack(
    backend.createStack('TaskDispatcherStack'),
    'taskDispatcherResource',
    {}
);

// Get the Task table
const taskTable = backend.data.resources.tables.Task;

// Get the Lambda function from the stack outputs
const taskDispatcherLambda = lambda.Function.fromFunctionName(
    taskDispatcherStack,
    'TaskDispatcherFunction',
    'TaskDispatcherFunction'
);

// Create a DynamoDB stream event source
const eventSource = new DynamoEventSource(taskTable, {
    startingPosition: lambda.StartingPosition.LATEST,
    batchSize: 1,
    retryAttempts: 3,
    maxBatchingWindow: Duration.seconds(1)
});

// Add the event source to the Lambda function
taskDispatcherLambda.addEventSource(eventSource);

// Add DynamoDB stream permissions
taskDispatcherLambda.addToRolePolicy(
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
taskDispatcherLambda.addToRolePolicy(
    new iam.PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [process.env.CELERY_QUEUE_URL || '*']
    })
);

// Configure stream trigger in the data model schema
// Note: The stream configuration should be defined in the data/resource.ts schema
// using the appropriate stream directives

export { backend };
