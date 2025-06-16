if (getItemsMetricsResolver) {
    // We need to grant it permission to invoke the Python lambda.
    itemsMetricsCalculatorStack.itemsMetricsCalculatorFunction.grantInvoke(getItemsMetricsResolver);

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