import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource.js';
import { auth } from './auth/resource.js';
import { reportBlockDetails, dataSources, scoreResultAttachments, taskAttachments } from './storage/resource.js';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource.js';
import { McpStack } from './mcp/mcp_stack.js';
import { Stack } from 'aws-cdk-lib';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

// Create the backend
const backend = defineBackend({
    auth,
    data,
    reportBlockDetails,
    dataSources,
    scoreResultAttachments,
    taskAttachments
});

// Get access to the functions
const getResourceByShareTokenFunction = backend.data.resources.functions.getResourceByShareToken;

// Add AppSync permissions to the getResourceByShareToken function
if (getResourceByShareTokenFunction) {
    getResourceByShareTokenFunction.addToRolePolicy(
        new PolicyStatement({
            actions: ['appsync:*'],  // Allow all AppSync actions
            resources: ['*']
        })
    );
}

// Enable streams on tables for metrics aggregation
const taskTable = backend.data.resources.tables.Task;
const taskCfnTable = taskTable.node.defaultChild as dynamodb.CfnTable;
if (taskCfnTable) {
    taskCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

const itemTable = backend.data.resources.tables.Item;
const itemCfnTable = itemTable.node.defaultChild as dynamodb.CfnTable;
if (itemCfnTable) {
    itemCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

const scoreResultTable = backend.data.resources.tables.ScoreResult;
const scoreResultCfnTable = scoreResultTable.node.defaultChild as dynamodb.CfnTable;
if (scoreResultCfnTable) {
    scoreResultCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

const evaluationTable = backend.data.resources.tables.Evaluation;
const evaluationCfnTable = evaluationTable.node.defaultChild as dynamodb.CfnTable;
if (evaluationCfnTable) {
    evaluationCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

// Create the TaskDispatcher stack with the table reference
const taskDispatcherStack = new TaskDispatcherStack(
    backend.createStack('TaskDispatcherStack'),
    'TaskDispatcher',
    {
        taskTable,
        // These will be set in the Lambda function's environment variables after deployment
        celeryAwsAccessKeyId: process.env.CELERY_AWS_ACCESS_KEY_ID || 'WILL_BE_SET_AFTER_DEPLOYMENT',
        celeryAwsSecretAccessKey: process.env.CELERY_AWS_SECRET_ACCESS_KEY || 'WILL_BE_SET_AFTER_DEPLOYMENT',
        celeryAwsRegion: process.env.CELERY_AWS_REGION_NAME || 'us-east-1', // Default to us-east-1 if not specified
        celeryResultBackendTemplate: process.env.CELERY_RESULT_BACKEND_TEMPLATE || 'WILL_BE_SET_AFTER_DEPLOYMENT'
    }
);

// Add SQS permissions
taskDispatcherStack.taskDispatcherFunction.addToRolePolicy(
    new PolicyStatement({
        actions: ['sqs:SendMessage'],
        resources: [process.env.CELERY_QUEUE_URL || '*']
    })
);

// Create the MCP stack
const mcpStack = new McpStack(
    backend.createStack('McpStack'),
    'McpStack',
    {
        deploymentTagKey: 'Environment',
        deploymentTagValue: 'production' // Match your EC2 instance tags
    }
);

export { backend, mcpStack };
