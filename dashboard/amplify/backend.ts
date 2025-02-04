import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import { Stack } from 'aws-cdk-lib';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

// Create the backend
const backend = defineBackend({
    auth,
    data
});

// Get reference to the Task table and enable streams
const taskTable = backend.data.resources.tables.Task;
const cfnTable = taskTable.node.defaultChild as dynamodb.CfnTable;
if (cfnTable) {
    cfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

// Get Celery configuration from environment
const celeryAwsAccessKeyId = process.env.CELERY_AWS_ACCESS_KEY_ID;
const celeryAwsSecretAccessKey = process.env.CELERY_AWS_SECRET_ACCESS_KEY;
const celeryAwsRegion = process.env.CELERY_AWS_REGION_NAME;
const celeryResultBackendTemplate = process.env.CELERY_RESULT_BACKEND_TEMPLATE;

if (!celeryAwsAccessKeyId || !celeryAwsSecretAccessKey || !celeryResultBackendTemplate) {
    throw new Error(
        'Missing required Celery configuration. Please set the following environment variables:\n' +
        '  CELERY_AWS_ACCESS_KEY_ID\n' +
        '  CELERY_AWS_SECRET_ACCESS_KEY\n' +
        '  CELERY_RESULT_BACKEND_TEMPLATE'
    );
}

// Create the TaskDispatcher stack with the table reference and Celery config
const taskDispatcherStack = new TaskDispatcherStack(
    backend.createStack('TaskDispatcherStack'),
    'taskDispatcher',
    {
        taskTable,
        celeryAwsAccessKeyId,
        celeryAwsSecretAccessKey,
        celeryAwsRegion,
        celeryResultBackendTemplate
    }
);

// Add SQS permissions
taskDispatcherStack.taskDispatcherFunction.addToRolePolicy(
    new PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [process.env.CELERY_QUEUE_URL || '*']
    })
);

export { backend };
