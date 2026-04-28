import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource.js';
import { auth } from './auth/resource.js';
import { reportBlockDetails, dataSources, scoreResultAttachments, taskAttachments } from './storage/resource.js';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource.js';
import { ConsoleChatResponderStack } from './functions/consoleRunWorker/resource.js';
import { McpStack } from './mcp/mcp_stack.js';
import { TopicMemoryVectorStoreStack } from './semantic-memory/vector_store_stack.js';
import { Duration } from 'aws-cdk-lib';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import * as backup from 'aws-cdk-lib/aws-backup';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';

// Create the backend
const backend = defineBackend({
    auth,
    data,
    reportBlockDetails,
    dataSources,
    scoreResultAttachments,
    taskAttachments
});

// Enable PITR on all Amplify Data DynamoDB tables (AWS default retention is 35 days).
const { amplifyDynamoDbTables } = backend.data.resources.cfnResources;
for (const table of Object.values(amplifyDynamoDbTables)) {
    table.pointInTimeRecoverySpecification = {
        pointInTimeRecoveryEnabled: true
    };
}

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

const feedbackItemTable = backend.data.resources.tables.FeedbackItem;
const feedbackItemCfnTable = feedbackItemTable.node.defaultChild as dynamodb.CfnTable;
if (feedbackItemCfnTable) {
    feedbackItemCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

const procedureTable = backend.data.resources.tables.Procedure;
const procedureCfnTable = procedureTable.node.defaultChild as dynamodb.CfnTable;
if (procedureCfnTable) {
    procedureCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

const chatSessionTable = backend.data.resources.tables.ChatSession;
const chatSessionCfnTable = chatSessionTable.node.defaultChild as dynamodb.CfnTable;
if (chatSessionCfnTable) {
    chatSessionCfnTable.streamSpecification = {
        streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    };
}

const chatMessageTable = backend.data.resources.tables.ChatMessage;
const chatMessageCfnTable = chatMessageTable.node.defaultChild as dynamodb.CfnTable;
if (chatMessageCfnTable) {
    chatMessageCfnTable.streamSpecification = {
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

const resolvedDataApiUrl = (process.env.PLEXUS_API_URL || '').trim();
const resolvedDataApiKey = (process.env.PLEXUS_API_KEY || '').trim();
const consoleWorkerImageUri = (process.env.CONSOLE_WORKER_IMAGE_URI || '').trim();
const consoleWorkerEnvironmentName = ((process.env.AWS_BRANCH || 'staging').trim().toLowerCase().replace(/[^a-z0-9-]/g, '-')) || 'staging';
const resolvedAnthropicApiKey = (process.env.ANTHROPIC_API_KEY || '').trim();

if (!resolvedDataApiUrl || !resolvedDataApiKey) {
    throw new Error('PLEXUS_API_URL and PLEXUS_API_KEY must be set for ConsoleRunWorkerStack deployment');
}

if (!consoleWorkerImageUri) {
    throw new Error('CONSOLE_WORKER_IMAGE_URI must be set for ConsoleRunWorkerStack deployment');
}

const consoleRunWorkerStack = new ConsoleChatResponderStack(
    backend.stack,
    'ConsoleChatResponder',
    {
        chatMessageTable,
        plexusApiUrl: resolvedDataApiUrl,
        plexusApiKey: resolvedDataApiKey,
        workerImageUri: consoleWorkerImageUri,
        environmentName: consoleWorkerEnvironmentName,
        anthropicApiKey: resolvedAnthropicApiKey,
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

function resolveEnvironmentName(): string {
    if (process.env.ENVIRONMENT) {
        return process.env.ENVIRONMENT.toLowerCase();
    }
    if (process.env.AMPLIFY_ENV) {
        return process.env.AMPLIFY_ENV.toLowerCase();
    }
    const branch = process.env.AWS_BRANCH?.toLowerCase();
    if (!branch) {
        return 'development';
    }
    if (branch === 'main' || branch === 'production') {
        return 'production';
    }
    if (branch === 'staging') {
        return 'staging';
    }
    return branch;
}

function normalizeForResourceName(value: string): string {
    const normalized = (value || 'development')
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');
    return normalized || 'development';
}

const environmentName = normalizeForResourceName(resolveEnvironmentName());

// Create a backup plan and assign all Amplify Data DynamoDB tables.
const dynamoDbBackupStack = backend.createStack('DynamoDbBackupStack');
const backupVault = new backup.BackupVault(dynamoDbBackupStack, 'DynamoDbBackupVault', {
    backupVaultName: `plexus-dynamodb-${environmentName}-vault`
});
const backupPlan = new backup.BackupPlan(dynamoDbBackupStack, 'DynamoDbBackupPlan', {
    backupPlanName: `plexus-dynamodb-${environmentName}-plan`,
    backupVault
});
backupPlan.addRule(new backup.BackupPlanRule({
    ruleName: 'Daily35DayRetention',
    scheduleExpression: events.Schedule.cron({
        minute: '0',
        hour: '5'
    }),
    deleteAfter: Duration.days(35)
}));
const dynamoDbBackupResources = Object.values(backend.data.resources.tables).map((table) => {
    return backup.BackupResource.fromDynamoDbTable(table);
});
backupPlan.addSelection('AmplifyDataTablesSelection', {
    resources: dynamoDbBackupResources
});

const topicMemoryVectorStoreStack = new TopicMemoryVectorStoreStack(
    backend.createStack('TopicMemoryVectorStoreStack'),
    'TopicMemoryVectorStore',
    {
        environmentName
    }
);

export { backend, mcpStack, topicMemoryVectorStoreStack, consoleRunWorkerStack };
