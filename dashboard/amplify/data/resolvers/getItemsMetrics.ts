import { LambdaClient, InvokeCommand, ListFunctionsCommand } from "@aws-sdk/client-lambda";
import type { AppSyncResolverHandler } from 'aws-lambda';

// Define the arguments for the resolver
type GetItemsMetricsArgs = {
  accountId: string;
  hours: number;
  bucketMinutes: number;
};

const lambdaClient = new LambdaClient({});

// Cache the function name to avoid repeated API calls
let cachedFunctionName: string | null = null;

async function getItemsMetricsCalculatorFunctionName(): Promise<string> {
    if (cachedFunctionName) {
        return cachedFunctionName;
    }

    try {
        const command = new ListFunctionsCommand({});
        const response = await lambdaClient.send(command);
        
        // Look for a function that matches our naming pattern
        const targetFunction = response.Functions?.find(func => 
            func.FunctionName?.includes('ItemsMetricsCalculator') ||
            func.FunctionName?.includes('itemsMetricsCalculator')
        );

        if (!targetFunction?.FunctionName) {
            throw new Error('ItemsMetricsCalculator Lambda function not found');
        }

        cachedFunctionName = targetFunction.FunctionName;
        return cachedFunctionName;
    } catch (error) {
        console.error('Error finding ItemsMetricsCalculator function:', error);
        throw new Error('Failed to locate ItemsMetricsCalculator Lambda function');
    }
}

export const handler: AppSyncResolverHandler<GetItemsMetricsArgs, any> = async (event) => {
    console.log('Invoking Python metrics calculator with event:', JSON.stringify(event, null, 2));
    
    const functionName = await getItemsMetricsCalculatorFunctionName();
    console.log('Using Lambda function:', functionName);

    // The payload for the Python lambda is the arguments from the GraphQL query
    const payload = event.arguments;

    const command = new InvokeCommand({
        FunctionName: functionName,
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