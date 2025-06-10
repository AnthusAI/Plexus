import { LambdaClient, InvokeCommand } from "@aws-sdk/client-lambda";
import type { AppSyncResolverHandler } from 'aws-lambda';

// Define the arguments for the resolver
type GetItemsMetricsArgs = {
  accountId: string;
  hours: number;
  bucketMinutes: number;
};

// Amplify will inject this environment variable. The name is derived from the function resource name.
const ITEMS_METRICS_CALCULATOR_LAMBDA_NAME = process.env.ITEMS_METRICS_CALCULATOR_LAMBDA_NAME;
const lambdaClient = new LambdaClient({});

export const handler: AppSyncResolverHandler<GetItemsMetricsArgs, any> = async (event) => {
    console.log('Invoking Python metrics calculator with event:', JSON.stringify(event, null, 2));
    
    if (!ITEMS_METRICS_CALCULATOR_LAMBDA_NAME) {
        throw new Error("ITEMS_METRICS_CALCULATOR_LAMBDA_NAME environment variable not set.");
    }

    // The payload for the Python lambda is the arguments from the GraphQL query
    const payload = event.arguments;

    const command = new InvokeCommand({
        FunctionName: ITEMS_METRICS_CALCULATOR_LAMBDA_NAME,
        Payload: JSON.stringify(payload)
    });

    try {
        const { Payload, FunctionError } = await lambdaClient.send(command);

        if (FunctionError) {
            const errorPayload = Payload ? JSON.parse(Buffer.from(Payload).toString()) : { errorMessage: 'Unknown error' };
            console.error('Python Lambda returned an error:', JSON.stringify(errorPayload, null, 2));
            throw new Error(errorPayload.errorMessage || `Lambda execution failed: ${FunctionError}`);
        }
        
        if (Payload) {
            const result = JSON.parse(Buffer.from(Payload).toString());
            return result;
        }

        return null;
    } catch (error) {
        console.error("Error invoking ItemsMetricsCalculatorLambda:", error);
        const e = error as Error;
        throw new Error(`Failed to fetch items metrics: ${e.message}`);
    }
}; 