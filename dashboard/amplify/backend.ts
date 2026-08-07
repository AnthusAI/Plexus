import { defineBackend } from '@aws-amplify/backend';
import { cancelCommandHandler, createArtifactTransferTicketsHandler, data, dispatchConsoleChatHandler, submitCommandHandler } from './data/resource.js';
import { auth } from './auth/resource.js';
import { reportBlockDetails, dataSources, scoreResultAttachments, taskAttachments, rubricMemory } from './storage/resource.js';
import { CommandServiceStack, isLongLivedCommandServiceEnvironment } from './command-service/resource.js';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource.js';
import { denyDashboardIdentityTaskMutations, grantCancelCommandTaskAccess, grantSubmitCommandTaskAccess } from './data/task-iam.js';
import { ConsoleChatResponderStack } from './functions/consoleRunWorker/resource.js';
import { McpStack } from './mcp/mcp_stack.js';
import { TopicMemoryVectorStoreStack } from './semantic-memory/vector_store_stack.js';
import { ArnFormat, Duration, Stack } from 'aws-cdk-lib';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as backup from 'aws-cdk-lib/aws-backup';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';

// Create the backend
const backend = defineBackend({
    auth,
    data,
    reportBlockDetails,
    dataSources,
    scoreResultAttachments,
    taskAttachments,
    rubricMemory,
    dispatchConsoleChatHandler,
    createArtifactTransferTicketsHandler,
    submitCommandHandler,
    cancelCommandHandler,
});

// Enable PITR on all Amplify Data DynamoDB tables (AWS default retention is 35 days).
const { amplifyDynamoDbTables } = backend.data.resources.cfnResources;
for (const table of Object.values(amplifyDynamoDbTables)) {
    table.pointInTimeRecoverySpecification = {
        pointInTimeRecoveryEnabled: true
    };
}

const getResourceByShareTokenFunction = backend.data.resources.functions.getResourceByShareToken;
const dispatchConsoleChatFunction = backend.dispatchConsoleChatHandler.resources.lambda;
const createArtifactTransferTicketsFunction = backend.createArtifactTransferTicketsHandler.resources.lambda;
const submitCommandFunction = backend.submitCommandHandler.resources.lambda;
const cancelCommandFunction = backend.cancelCommandHandler.resources.lambda;

// Add AppSync permissions to the getResourceByShareToken function
if (getResourceByShareTokenFunction) {
    getResourceByShareTokenFunction.addToRolePolicy(
        new PolicyStatement({
            actions: ['appsync:*'],  // Allow all AppSync actions
            resources: ['*']
        })
    );
}

if (cancelCommandFunction) {
    const cancelCommandCfn = cancelCommandFunction.node.defaultChild as lambda.CfnFunction;
    const api = backend.data.resources.cfnResources.cfnGraphqlApi;
    cancelCommandCfn.addPropertyOverride('Environment.Variables.PLEXUS_API_URL', api.attrGraphQlUrl);
    grantCancelCommandTaskAccess(cancelCommandFunction, api.attrArn);
}

if (submitCommandFunction) {
    const submitCommandCfn = submitCommandFunction.node.defaultChild as lambda.CfnFunction;
    submitCommandCfn.addPropertyOverride('Environment.Variables.ACCOUNT_TABLE_NAME', backend.data.resources.tables.Account.tableName);
    const api = backend.data.resources.cfnResources.cfnGraphqlApi;
    submitCommandCfn.addPropertyOverride('Environment.Variables.PLEXUS_API_URL', api.attrGraphQlUrl);
    submitCommandFunction.addToRolePolicy(new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['dynamodb:GetItem'],
        resources: [backend.data.resources.tables.Account.tableArn],
    }));
    grantSubmitCommandTaskAccess(submitCommandFunction, api.attrArn);
}

// This has to be part of the base backend rather than the long-lived command
// stack: sandboxes expose the same AppSync API and identity-pool roles.
const dataApi = backend.data.resources.cfnResources.cfnGraphqlApi;
const authIamResources = backend.auth.resources as unknown as {
    unauthenticatedUserIamRole?: iam.IRole;
};
denyDashboardIdentityTaskMutations(
    [
        backend.auth.resources.authenticatedUserIamRole,
        ...(authIamResources.unauthenticatedUserIamRole ? [authIamResources.unauthenticatedUserIamRole] : []),
    ],
    dataApi.attrArn,
);

if (createArtifactTransferTicketsFunction) {
    const ticketedResources = [
        {
            table: backend.data.resources.tables.DataSet,
            tableEnvironmentName: 'DATA_SET_TABLE_NAME',
            bucket: backend.dataSources.resources.bucket,
            bucketEnvironmentName: 'DATA_SOURCES_BUCKET_NAME',
            objectPrefixes: ['datasets/*'],
        },
        {
            table: backend.data.resources.tables.Procedure,
            tableEnvironmentName: 'PROCEDURE_TABLE_NAME',
            bucket: backend.reportBlockDetails.resources.bucket,
            bucketEnvironmentName: 'REPORT_BLOCK_DETAILS_BUCKET_NAME',
            objectPrefixes: ['procedures/*', 'reportblocks/procedures/*'],
        },
        {
            table: backend.data.resources.tables.ScoreResult,
            tableEnvironmentName: 'SCORE_RESULT_TABLE_NAME',
            bucket: backend.scoreResultAttachments.resources.bucket,
            bucketEnvironmentName: 'SCORE_RESULT_ATTACHMENTS_BUCKET_NAME',
            objectPrefixes: ['scoreresults/*'],
        },
        {
            table: backend.data.resources.tables.Evaluation,
            tableEnvironmentName: 'EVALUATION_TABLE_NAME',
            bucket: backend.scoreResultAttachments.resources.bucket,
            bucketEnvironmentName: 'SCORE_RESULT_ATTACHMENTS_BUCKET_NAME',
            objectPrefixes: ['evaluations/*'],
        },
        {
            table: backend.data.resources.tables.Task,
            tableEnvironmentName: 'TASK_TABLE_NAME',
            bucket: backend.taskAttachments.resources.bucket,
            bucketEnvironmentName: 'TASK_ATTACHMENTS_BUCKET_NAME',
            objectPrefixes: ['tasks/*'],
        },
    ];

    for (const resource of ticketedResources) {
        backend.createArtifactTransferTicketsHandler.addEnvironment(
            resource.tableEnvironmentName,
            resource.table.tableName,
        );
        backend.createArtifactTransferTicketsHandler.addEnvironment(
            resource.bucketEnvironmentName,
            resource.bucket.bucketName,
        );
        createArtifactTransferTicketsFunction.addToRolePolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['dynamodb:GetItem'],
            resources: [resource.table.tableArn],
        }));
        createArtifactTransferTicketsFunction.addToRolePolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['s3:GetObject', 's3:PutObject'],
            resources: resource.objectPrefixes.map((prefix) => resource.bucket.arnForObjects(prefix)),
        }));
    }
}

// Detect sandbox environment
// Sandboxes are used for development/testing and don't need full infrastructure.
// We skip TaskDispatcher and ConsoleWorker stacks in sandbox mode to avoid
// requiring CELERY_* environment variables.
//
// Decision: Sandboxes are primarily for testing the seed script and Data API,
// not for running the full application with task dispatching and console workers.
//
// To enable full app in sandboxes in the future:
// 1. Set all required env vars (CELERY_*)
// 2. Remove or modify this isSandbox check
// 3. Ensure the local environment can build Lambda Docker image assets
const isSandbox = process.env.AWS_BRANCH === undefined &&
                  process.env.AMPLIFY_ENV === undefined;
const enableSandboxConsoleWorker = process.env.AMPLIFY_ENABLE_SANDBOX_CONSOLE_WORKER === 'true';
const enableSandboxTaskDispatcher = process.env.AMPLIFY_ENABLE_SANDBOX_TASK_DISPATCHER === 'true';

if (isSandbox) {
    if (enableSandboxConsoleWorker) {
        console.log('🏖️  Sandbox mode detected - ConsoleRunWorker explicitly enabled for this deployment');
    } else if (enableSandboxTaskDispatcher) {
        console.log('🏖️  Sandbox mode detected - TaskDispatcher explicitly enabled with its isolated command queue');
    } else {
        console.log('🏖️  Sandbox mode detected - skipping TaskDispatcher and ConsoleWorker stacks');
    }
}

// Enable streams on tables for metrics aggregation
const taskTable = backend.data.resources.tables.Task;
const taskAmplifyTable = amplifyDynamoDbTables.Task;
if (!taskAmplifyTable) {
    throw new Error('TaskDispatcher requires access to the generated Task table resource.');
}
taskAmplifyTable.streamSpecification = {
    streamViewType: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
};
if (!taskTable.tableStreamArn) {
    throw new Error('TaskDispatcher requires the Task table stream ARN.');
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

// Allow authenticated users to read procedure CloudWatch log streams from the dashboard.
backend.auth.resources.authenticatedUserIamRole.addToPrincipalPolicy(
    new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
            'logs:GetLogEvents',
            'logs:FilterLogEvents',
            'logs:DescribeLogStreams',
        ],
        resources: [
            'arn:aws:logs:*:*:log-group:/plexus/procedures/*',
            'arn:aws:logs:*:*:log-group:/plexus/procedures/*:*',
        ],
    })
);

// The command service is long-lived-environment only. Sandboxes intentionally
// have no command-service VPC, dispatcher, or ECS worker.
let commandServiceStack: CommandServiceStack | undefined;
let sandboxTaskDispatcherStack: TaskDispatcherStack | undefined;
let consoleRunWorkerStack: ConsoleChatResponderStack | undefined;

const commandServiceEnvironment = resolveEnvironmentName();
if (isLongLivedCommandServiceEnvironment(commandServiceEnvironment)) {
    const workerImageUri = (process.env.PLEXUS_COMMAND_WORKER_IMAGE_URI || '').trim();
    const foundationRepositoryUri = (process.env.PLEXUS_COMMAND_WORKER_FOUNDATION_REPOSITORY_URI || '').trim();
    const amplifyDeploymentRoleArn = (process.env.PLEXUS_AMPLIFY_DEPLOYMENT_ROLE_ARN || '').trim();
    if (!workerImageUri) {
        throw new Error('PLEXUS_COMMAND_WORKER_IMAGE_URI must provide repository@sha256 for command-service deployment');
    }
    if (!foundationRepositoryUri) {
        throw new Error('PLEXUS_COMMAND_WORKER_FOUNDATION_REPOSITORY_URI is required from the image handoff');
    }
    if (!amplifyDeploymentRoleArn) {
        throw new Error('PLEXUS_AMPLIFY_DEPLOYMENT_ROLE_ARN is required for the command activity gate');
    }
    const dataCfnResources = backend.data.resources.cfnResources as unknown as {
        cfnGraphqlApi?: { attrGraphQlUrl?: string; attrArn?: string };
    };
    const apiUrl = dataCfnResources.cfnGraphqlApi?.attrGraphQlUrl || '';
    const apiGraphqlArn = dataCfnResources.cfnGraphqlApi?.attrArn || '';
    if (!apiUrl || !apiGraphqlArn) {
        throw new Error('Command service requires generated AppSync API URL and ARN');
    }
    const configSecretName = (
        process.env.PLEXUS_CONFIG_SECRET_NAME || `plexus/${commandServiceEnvironment}/config`
    ).trim();
    const bedrockModelResources = (process.env.PLEXUS_COMMAND_WORKER_BEDROCK_MODEL_ARNS || 'arn:aws:bedrock:*::foundation-model/*')
        .split(',').map((value) => value.trim()).filter(Boolean);
    const commandServiceCdkStack = backend.createStack('CommandServiceStack');
    const servicePrefix = (process.env.PLEXUS_SERVICE_PREFIX || 'plexus').trim().toLowerCase();
    new ssm.StringParameter(commandServiceCdkStack, 'CommandServiceTaskTableName', {
        parameterName: `/${servicePrefix}/${commandServiceEnvironment}/command-service/task-table-name`,
        stringValue: taskTable.tableName,
    });
    new ssm.StringParameter(commandServiceCdkStack, 'CommandServiceCurrentWorkerImage', {
        parameterName: `/${servicePrefix}/${commandServiceEnvironment}/command-service/current-worker-image-uri`,
        stringValue: workerImageUri,
    });
    commandServiceStack = new CommandServiceStack(
        commandServiceCdkStack,
        'CommandService',
        {
            taskTable,
            taskTableStreamArn: taskTable.tableStreamArn,
            apiUrl,
            apiGraphqlArn,
            workerImageUri,
            foundationRepositoryUri,
            configSecretName,
            bedrockModelResources,
            environmentName: commandServiceEnvironment,
            amplifyDeploymentRoleArn,
            dataSourcesBucket: backend.dataSources.resources.bucket,
            reportBlockDetailsBucket: backend.reportBlockDetails.resources.bucket,
            scoreResultAttachmentsBucket: backend.scoreResultAttachments.resources.bucket,
        },
    );
}

// The legacy dispatcher exists only as an explicit sandbox proof harness. It
// never coexists with the long-lived command-service dispatcher and ECS worker.
if (isSandbox && enableSandboxTaskDispatcher) {
    sandboxTaskDispatcherStack = new TaskDispatcherStack(
        backend.createStack('SandboxTaskDispatcherStack'),
        'SandboxTaskDispatcher',
        { taskTable, taskTableStreamArn: taskTable.tableStreamArn },
    );
}

const shouldDeployConsoleWorker = !isSandbox || enableSandboxConsoleWorker;
if (shouldDeployConsoleWorker) {
    const dataCfnResources = backend.data.resources.cfnResources as unknown as {
        cfnGraphqlApi?: { attrGraphQlUrl?: string };
    };
    const sandboxGraphqlUrl = dataCfnResources.cfnGraphqlApi?.attrGraphQlUrl || '';
    const resolvedDataApiUrl = (
        isSandbox ? sandboxGraphqlUrl : (process.env.PLEXUS_API_URL || '')
    ).trim();
    const consoleWorkerEnvironmentName = normalizeForResourceName(resolveEnvironmentName());
    const consoleResponderParameterName = `/plexus/${consoleWorkerEnvironmentName}/console-chat/responder`;
    const consoleWorkerConfigSecretName = (
        process.env.PLEXUS_CONFIG_SECRET_NAME ||
        (isSandbox ? 'plexus/staging/config' : `plexus/${consoleWorkerEnvironmentName}/config`)
    ).trim();

    if (!resolvedDataApiUrl) {
        throw new Error(
            isSandbox
                ? 'Unable to resolve sandbox GraphQL URL for ConsoleRunWorkerStack deployment'
                : 'PLEXUS_API_URL must be set for ConsoleRunWorkerStack deployment'
        );
    }
    if (isSandbox && consoleWorkerConfigSecretName === 'plexus/production/config') {
        throw new Error('Sandbox ConsoleRunWorker must not use plexus/production/config');
    }

    consoleRunWorkerStack = new ConsoleChatResponderStack(
        backend.stack,
        'ConsoleChatResponder',
        {
            chatMessageTable,
            plexusApiUrl: resolvedDataApiUrl,
            environmentName: consoleWorkerEnvironmentName,
            asyncTasksAvailable: !isSandbox,
            responderParameterName: consoleResponderParameterName,
            configSecretName: consoleWorkerConfigSecretName,
            reportBlockDetailsBucket: backend.reportBlockDetails.resources.bucket,
        }
    );
    dispatchConsoleChatFunction.addToRolePolicy(
        new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: ['*'],
        }),
    );
    dispatchConsoleChatFunction.addToRolePolicy(
        new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['lambda:InvokeFunction'],
            resources: [
                Stack.of(dispatchConsoleChatFunction).formatArn({
                    service: 'lambda',
                    resource: 'function',
                    resourceName: 'amplify-*ConsoleChatResponder*',
                    arnFormat: ArnFormat.COLON_RESOURCE_NAME,
                }),
                Stack.of(dispatchConsoleChatFunction).formatArn({
                    service: 'lambda',
                    resource: 'function',
                    resourceName: 'amplify-*ConsoleChatResponder*:*',
                    arnFormat: ArnFormat.COLON_RESOURCE_NAME,
                }),
            ],
        }),
    );
}

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

// Production/staging own their backup plans. Sandboxes are ephemeral and must
// not claim a shared regional vault name while provisioning copied test data.
if (!isSandbox) {
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
}

// Create vector store (skip in sandbox mode - not needed for seed testing)
let topicMemoryVectorStoreStack: TopicMemoryVectorStoreStack | undefined;

if (!isSandbox) {
    topicMemoryVectorStoreStack = new TopicMemoryVectorStoreStack(
        backend.createStack('TopicMemoryVectorStoreStack'),
        'TopicMemoryVectorStore',
        {
            environmentName
        }
    );
}

export { backend, mcpStack, topicMemoryVectorStoreStack, consoleRunWorkerStack };
