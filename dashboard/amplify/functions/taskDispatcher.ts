import { DynamoDBStreamEvent } from 'aws-lambda';
import { unmarshall } from '@aws-sdk/util-dynamodb';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';

const sqs = new SQSClient({});
const CELERY_QUEUE_URL = process.env.CELERY_QUEUE_URL;

export const handler = async (event: DynamoDBStreamEvent) => {
    try {
        for (const record of event.Records) {
            // Only process new or modified records
            if (record.eventName !== 'INSERT' && record.eventName !== 'MODIFY') {
                continue;
            }

            // Get the new image of the record
            const newImage = record.dynamodb?.NewImage;
            if (!newImage) {
                continue;
            }

            // Convert DynamoDB record to regular JSON
            const task = unmarshall(newImage);

            // Only process tasks that need to be dispatched
            if (task.dispatchStatus !== 'PENDING') {
                continue;
            }

            // Prepare the Celery task message
            const celeryMessage = {
                task: 'plexus.execute_command',
                id: task.id,
                args: [task.command],
                kwargs: {
                    target: task.target,
                    task_id: task.id
                }
            };

            // Send to Celery queue
            await sqs.send(new SendMessageCommand({
                QueueUrl: CELERY_QUEUE_URL,
                MessageBody: JSON.stringify(celeryMessage)
            }));

            console.log(`Dispatched task ${task.id} to Celery queue`);
        }
    } catch (error) {
        console.error('Error processing DynamoDB stream event:', error);
        throw error;
    }
}; 