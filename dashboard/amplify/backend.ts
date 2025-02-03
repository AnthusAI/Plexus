import { defineBackend } from '@aws-amplify/backend';
import { data } from './data/resource';
import { auth } from './auth/resource';
import { TaskDispatcherStack } from './functions/taskDispatcher/resource';
import { Stack } from 'aws-cdk-lib';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';

// Create the backend
const backend = defineBackend({
    auth,
    data
});

// Get reference to the Task table
const taskTable = backend.data.resources.tables.Task;

// Create the TaskDispatcher stack with the table reference
const taskDispatcherStack = new TaskDispatcherStack(
    backend.createStack('TaskDispatcherStack'),
    'taskDispatcher',
    {
        taskTable
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
