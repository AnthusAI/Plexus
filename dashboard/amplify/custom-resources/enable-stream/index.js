const { DynamoDBClient, UpdateTableCommand } = require('@aws-sdk/client-dynamodb');
const client = new DynamoDBClient();

exports.handler = async (event) => {
    if (event.RequestType === 'Delete') return;
    
    const command = new UpdateTableCommand({
        TableName: event.ResourceProperties.tableName,
        StreamSpecification: {
            StreamEnabled: true,
            StreamViewType: 'NEW_AND_OLD_IMAGES'
        }
    });
    
    await client.send(command);
}; 