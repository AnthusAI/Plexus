import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { defineFunction } from '@aws-amplify/backend-function';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import type { Schema } from './data/resource';
import { Duration, Stack } from 'aws-cdk-lib';

// First define the function
const taskDispatcher = defineFunction({
    name: 'taskDispatcher',
    entry: './functions/taskDispatcher.ts',
    environment: {
        CELERY_QUEUE_URL: process.env.CELERY_QUEUE_URL || ''
    },
    timeoutSeconds: 30
});

// Create the backend with the function
const backend = defineBackend({
    auth,
    data,
    taskDispatcher
});

// Get the actual Lambda resource and add the policy to it
const taskDispatcherLambda = backend.taskDispatcher.resources.lambda;

// Add SQS permissions
taskDispatcherLambda.addToRolePolicy(
    new iam.PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [process.env.CELERY_QUEUE_URL || '*']
    })
);

// Get the Task table and enable streams
const taskTable = backend.data.resources.tables.Task;
const taskTableCfn = taskTable.node.defaultChild as dynamodb.CfnTable;
taskTableCfn.streamSpecification = {
    streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
};

// Add DynamoDB stream permissions
const streamArn = taskTableCfn.attrStreamArn;
if (streamArn) {
    taskDispatcherLambda.addToRolePolicy(
        new iam.PolicyStatement({
            actions: [
                'dynamodb:GetRecords',
                'dynamodb:GetShardIterator',
                'dynamodb:DescribeStream',
                'dynamodb:ListStreams'
            ],
            resources: [streamArn]
        })
    );

    // Add the stream as an event source
    taskDispatcherLambda.addEventSourceMapping('TaskStreamTrigger', {
        eventSourceArn: streamArn,
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 1,
        retryAttempts: 3,
        maxBatchingWindow: Duration.seconds(1)
    });
}

// Configure stream trigger in the data model schema
// Note: The stream configuration should be defined in the data/resource.ts schema
// using the appropriate stream directives

export { backend };
