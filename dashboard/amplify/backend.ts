import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource.js';
import { auth } from './auth/resource.js';
import { reportBlockDetails, attachments, scoreResultAttachments } from './storage/resource.js';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource.js';
import { ItemsMetricsCalculatorStack } from "./functions/itemsMetricsCalculator/resource.ts";
import { Stack, CfnOutput, Fn } from 'aws-cdk-lib';
import { PolicyStatement, PolicyDocument, Role, ServicePrincipal, Effect } from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as appsync from 'aws-cdk-lib/aws-appsync';
import { IFunction } from 'aws-cdk-lib/aws-lambda';
import { IGraphqlApi, CfnGraphQLApi, CfnApiKey } from 'aws-cdk-lib/aws-appsync';

// Create the backend
const backend = defineBackend({
    auth,
    data,
    reportBlockDetails,
    attachments,
    scoreResultAttachments
});

if (!backend.data.resources.cfnResources.cfnApiKey) {
    throw new Error('API Key is not configured for this backend and is required by the ItemsMetricsCalculator.');
}

// Export GraphQL API URL and API key for ItemsMetricsCalculator to import
new CfnOutput(backend.data.resources.cfnResources.cfnGraphqlApi.stack, 'GraphQLAPIURLExport', {
    value: backend.data.resources.cfnResources.cfnGraphqlApi.attrGraphQlUrl,
    exportName: 'amplify-data-GraphQLAPIURL'
});

new CfnOutput(backend.data.resources.cfnResources.cfnGraphqlApi.stack, 'APIKeyExport', {
    value: backend.data.resources.cfnResources.cfnApiKey.attrApiKey,
    exportName: 'amplify-data-APIKey'
});

// Create the ItemsMetricsCalculator as a separate stack without props dependency
const itemsMetricsCalculatorStack = new ItemsMetricsCalculatorStack(
    backend.createStack('ItemsMetricsCalculatorStack'),
    'ItemsMetricsCalculator',
    {}
);

// Import the function ARN from the ItemsMetricsCalculator stack
const functionArn = Fn.importValue(`${itemsMetricsCalculatorStack.stackName}-ItemsMetricsCalculatorFunctionArn`);

// Create IAM role for AppSync to invoke Lambda functions
const appSyncServiceRole = new Role(
    backend.data.resources.cfnResources.cfnGraphqlApi.stack,
    'AppSyncServiceRole',
    {
        assumedBy: new ServicePrincipal('appsync.amazonaws.com'),
        inlinePolicies: {
            LambdaInvokePolicy: new PolicyDocument({
                statements: [
                    new PolicyStatement({
                        effect: Effect.ALLOW,
                        actions: ['lambda:InvokeFunction'],
                        resources: [functionArn]
                    })
                ]
            })
        }
    }
);

// Create AppSync data source for the Python Lambda function
const itemsMetricsDataSource = new appsync.CfnDataSource(
    backend.data.resources.cfnResources.cfnGraphqlApi.stack,
    'ItemsMetricsDataSource',
    {
        apiId: backend.data.resources.cfnResources.cfnGraphqlApi.attrApiId,
        name: 'ItemsMetricsDataSource',
        type: 'AWS_LAMBDA',
        lambdaConfig: {
            lambdaFunctionArn: functionArn
        },
        serviceRoleArn: appSyncServiceRole.roleArn
    }
);

// Create resolver for the getItemsMetrics query
const itemsMetricsResolver = new appsync.CfnResolver(
    backend.data.resources.cfnResources.cfnGraphqlApi.stack,
    'GetItemsMetricsResolver',
    {
        apiId: backend.data.resources.cfnResources.cfnGraphqlApi.attrApiId,
        typeName: 'Query',
        fieldName: 'getItemsMetrics',
        dataSourceName: itemsMetricsDataSource.name,
        requestMappingTemplate: `{
            "version": "2017-02-28",
            "operation": "Invoke",
            "payload": $util.toJson($ctx.args)
        }`,
        responseMappingTemplate: `$util.toJson($ctx.result)`
    }
);

// Ensure proper dependency ordering
itemsMetricsResolver.addDependency(itemsMetricsDataSource);
itemsMetricsDataSource.addDependency(backend.data.resources.cfnResources.cfnGraphqlApi);

// Get access to the getResourceByShareToken function
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

// // Force backend to generate an identity pool with unauthenticated access
// if (backend.auth.resources.cfnResources?.cfnIdentityPool) {
//     backend.auth.resources.cfnResources.cfnIdentityPool.allowUnauthenticatedIdentities = true;
// }

// Get reference to the Task table and enable streams
const taskTable = backend.data.resources.tables.Task;
const cfnTable = taskTable.node.defaultChild as dynamodb.CfnTable;
if (cfnTable) {
    cfnTable.streamSpecification = {
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

const cfnApi = backend.data.resources.cfnResources.cfnGraphqlApi;
const cfnApiKey = backend.data.resources.cfnResources.cfnApiKey;

if (!cfnApiKey) {
    throw new Error('API Key is not configured for this backend and is required by the ItemsMetricsCalculator.');
}

export { backend };
