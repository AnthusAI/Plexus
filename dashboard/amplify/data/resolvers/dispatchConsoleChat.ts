import { InvokeCommand, LambdaClient } from '@aws-sdk/client-lambda';
import { GetParameterCommand, SSMClient } from '@aws-sdk/client-ssm';

import type { Schema } from '../resource';

const lambda = new LambdaClient({});
const ssm = new SSMClient({});
const responderParameterName = '/plexus/console-chat/responder';
let responderFunctionName: string | undefined;

const getResponderFunctionName = async (): Promise<string> => {
  if (responderFunctionName) return responderFunctionName;

  const result = await ssm.send(new GetParameterCommand({ Name: responderParameterName }));
  const value = result.Parameter?.Value?.trim();
  if (!value) throw new Error('Console responder target is not configured');
  responderFunctionName = value;
  return value;
};

/**
 * Starts the Console responder immediately after the user message is durable.
 * The DynamoDB Stream remains enabled: both delivery paths race through the
 * responder's conditional PENDING -> RUNNING claim, so only one can execute.
 */
export const handler: Schema['dispatchConsoleChat']['functionHandler'] = async (event) => {
  const messageId = event.arguments.messageId.trim();
  const responderFunctionName = await getResponderFunctionName();

  await lambda.send(new InvokeCommand({
    FunctionName: responderFunctionName,
    InvocationType: 'Event',
    Payload: Buffer.from(JSON.stringify({ directMessageId: messageId })),
  }));

  return { accepted: true };
};
