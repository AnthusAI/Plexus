import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { reportBlockDetails, attachments, scoreResultAttachments } from './storage/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import { ItemsMetricsCalculatorStack } from './functions/itemsMetricsCalculator/resource';
import { Stack } from 'aws-cdk-lib';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

// Create the backend
const backend = defineBackend({
    auth,
    data,
    reportBlockDetails,
    attachments,
    scoreResultAttachments
});

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
    'taskDispatcher',
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

// Create the ItemsMetricsCalculator stack
const itemsMetricsCalculatorStack = new ItemsMetricsCalculatorStack(
    backend.createStack('ItemsMetricsCalculatorStack'),
    'itemsMetricsCalculator',
    {
        // Pass the GraphQL endpoint ARN and AppSync API ID from the data backend
        graphqlEndpointArn: backend.data.resources.graphqlApi.graphQLEndpointArn,
        appSyncApiId: backend.data.resources.graphqlApi.apiId
    }
);

// Get the underlying L1 CfnFunction construct
const getItemsMetricsLambda = backend.data.resources.functions.getItemsMetrics.node.defaultChild as dynamodb.CfnTable;

// Add the environment variable to the function
getItemsMetricsLambda.addPropertyOverride('Environment.Variables.AMPLIFY_DASHBOARD_ITEMSMETRICSCALCULATOR_NAME', itemsMetricsCalculatorStack.itemsMetricsCalculatorFunction.functionName);

export { backend };
