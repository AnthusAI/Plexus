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
        console.log('Listing functions to find the metrics calculator...');
        const command = new ListFunctionsCommand({});
        const response = await lambdaClient.send(command);
        
        if (response.Functions) {
            const functionNames = response.Functions.map(f => f.FunctionName).join(', ');
            console.log(`Found ${response.Functions.length} functions: [${functionNames}]`);
        } else {
            console.log('ListFunctions API call did not return any functions.');
        }
        
        // Look for a function that matches our naming pattern.
        // The deployed name will contain the Stack ID ('ItemsMetricsCalculator') and the Function ID ('ItemsMetricsCalculatorFunction').
        const targetFunction = response.Functions?.find(func => 
            func.FunctionName?.includes('ItemsMetricsCalculator') &&
            func.FunctionName?.includes('ItemsMetricsCalculatorFunction')
        );

        if (!targetFunction?.FunctionName) {
            // Be more specific in the error message.
            throw new Error('Could not find a Lambda function with "ItemsMetricsCalculator" and "ItemsMetricsCalculatorFunction" in its name.');
        }

        console.log(`Found target function: ${targetFunction.FunctionName}`);
        cachedFunctionName = targetFunction.FunctionName;
        return cachedFunctionName;
    } catch (error) {
        // Log the original error for better debugging.
        console.error('Error during Lambda function discovery:', error);
        throw new Error('Failed to locate ItemsMetricsCalculator Lambda function. Check the CloudWatch logs for the "get-items-metrics-ts-resolver" function for more details.');
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