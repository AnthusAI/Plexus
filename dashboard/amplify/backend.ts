import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource.js';
import { auth } from './auth/resource.js';
import { reportBlockDetails, attachments, scoreResultAttachments } from './storage/resource.js';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource.js';
import { ItemsMetricsCalculatorStack } from "./functions/itemsMetricsCalculator/resource.js";
import { Stack } from 'aws-cdk-lib';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import {
  Effect,
  Policy,
  Role,
  ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
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

// Instantiate the ItemsMetricsCalculator construct directly in the backend scope.
const itemsMetricsCalculator = new ItemsMetricsCalculatorStack(
    backend.data.resources.cfnResources.cfnGraphqlApi.stack, // Use the data resource's stack as the scope
    'ItemsMetricsCalculator',
    {
        graphqlEndpoint: backend.data.resources.cfnResources.cfnGraphqlApi.attrGraphQlUrl,
        apiKey: backend.data.resources.cfnResources.cfnApiKey.attrApiKey,
    }
);

// The getItemsMetrics query has a resolver function (a TypeScript lambda).
const getItemsMetricsResolver = backend.data.resources.functions.getItemsMetricsHandler;

if (getItemsMetricsResolver) {
    // We need to grant it permission to invoke the Python lambda.
    itemsMetricsCalculator.itemsMetricsCalculatorFunction.grantInvoke(getItemsMetricsResolver);

    // Add environment variable with the ItemsMetricsCalculator function name
    if (getItemsMetricsResolver.node.defaultChild) {
        const cfnFunction = getItemsMetricsResolver.node.defaultChild as lambda.CfnFunction;
        cfnFunction.addPropertyOverride('Environment.Variables.AMPLIFY_DASHBOARD_ITEMSMETRICSCALCULATOR_NAME', 
            itemsMetricsCalculator.itemsMetricsCalculatorFunction.functionName);
    }

    // Add permission to list Lambda functions so it can discover the function name
    getItemsMetricsResolver.addToRolePolicy(
        new PolicyStatement({
            actions: ['lambda:ListFunctions'],
            resources: ['*']
        })
    );
    
    // Add permissions for CloudWatch Logs
    getItemsMetricsResolver.addToRolePolicy(
        new PolicyStatement({
            actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
            ],
            resources: ['arn:aws:logs:*:*:*'],
        })
    );
}

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
