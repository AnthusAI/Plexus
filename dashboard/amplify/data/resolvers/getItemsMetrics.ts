import { LambdaClient, InvokeCommand } from "@aws-sdk/client-lambda";
import type { AppSyncResolverHandler } from 'aws-lambda';

// Define the arguments for the resolver
type GetItemsMetricsArgs = {
  accountId: string;
  hours: number;
  bucketMinutes: number;
};

const lambdaClient = new LambdaClient({});

// The ARN of the Python function is passed in as an environment variable.
const functionArn = process.env.ITEMS_METRICS_CALCULATOR_FUNCTION_ARN;

export const handler: AppSyncResolverHandler<GetItemsMetricsArgs, any> = async (event) => {
    console.log('Invoking Python metrics calculator with event:', JSON.stringify(event, null, 2));
    
    // Debug: Log all environment variables to understand what's available
    console.log('Available environment variables:', JSON.stringify(process.env, null, 2));
    console.log('ITEMS_METRICS_CALCULATOR_FUNCTION_ARN specifically:', process.env.ITEMS_METRICS_CALCULATOR_FUNCTION_ARN);

    if (!functionArn) {
        console.error('ITEMS_METRICS_CALCULATOR_FUNCTION_ARN environment variable is not set.');
        throw new Error('Items Metrics Calculator function ARN is not configured.');
    }
    
    console.log('Using Lambda function ARN:', functionArn);

    // The payload for the Python lambda is the arguments from the GraphQL query
    const payload = event.arguments;

    const command = new InvokeCommand({
        FunctionName: functionArn,
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