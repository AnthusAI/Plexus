import { LambdaClient, InvokeCommand } from "@aws-sdk/client-lambda";
import type { AppSyncResolverHandler } from 'aws-lambda';

// Define the arguments for the resolver
type GetItemsMetricsArgs = {
  accountId: string;
  hours: number;
  bucketMinutes: number;
};

// Get the Lambda function name from environment variables
// Amplify will inject this environment variable for functions within the same project.
// The name is derived from the function resource name in the backend definition.
const ITEMS_METRICS_CALCULATOR_LAMBDA_NAME = process.env.AMPLIFY_DASHBOARD_ITEMSMETRICSCALCULATOR_NAME;

const lambdaClient = new LambdaClient({});

export const handler: AppSyncResolverHandler<GetItemsMetricsArgs, any> = async (event) => {
    console.log('Received event:', JSON.stringify(event, null, 2));
    const { accountId, hours = 24, bucketMinutes = 60 } = event.arguments;

    if (!ITEMS_METRICS_CALCULATOR_LAMBDA_NAME) {
        console.error("AMPLIFY_DASHBOARD_ITEMSMETRICSCALCULATOR_NAME environment variable not set.");
        throw new Error("AMPLIFY_DASHBOARD_ITEMSMETRICSCALCULATOR_NAME environment variable not set.");
    }
    console.log(`Invoking Lambda: ${ITEMS_METRICS_CALCULATOR_LAMBDA_NAME}`);

    const payload = {
        accountId,
        hours,
        bucketMinutes
    };
    console.log('Sending payload:', JSON.stringify(payload, null, 2));

    const command = new InvokeCommand({
        FunctionName: ITEMS_METRICS_CALCULATOR_LAMBDA_NAME,
        Payload: JSON.stringify(payload),
        // InvocationType: 'RequestResponse' // This is the default
    });

    try {
        const { Payload, FunctionError } = await lambdaClient.send(command);

        if (FunctionError) {
            const errorPayload = Payload ? JSON.parse(Buffer.from(Payload).toString()) : 'Unknown error';
            console.error('Lambda function returned an error:', JSON.stringify(errorPayload, null, 2));
            throw new Error(`Lambda execution failed: ${FunctionError}`);
        }
        
        if (Payload) {
            const resultString = Buffer.from(Payload).toString();
            console.log('Received raw payload from Lambda:', resultString);
            const result = JSON.parse(resultString);
            
            // The lambda might return a JSON string inside the 'body' property if it's set up as an API gateway proxy integration
            // Or it could return the object directly. We need to handle both.
            if (typeof result.body === 'string') {
                return JSON.parse(result.body);
            }
            
            return result;
        }

        console.log('Lambda returned no payload.');
        return null;
    } catch (error) {
        console.error("Error invoking ItemsMetricsCalculatorLambda:", error);
        // Casting to Error to satisfy typescript
        const e = error as Error
        throw new Error(`Failed to fetch items metrics: ${e.message}`);
    }
}; 