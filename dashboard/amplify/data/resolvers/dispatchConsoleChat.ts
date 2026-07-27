import { InvokeCommand, LambdaClient } from '@aws-sdk/client-lambda';
import { GetParameterCommand, SSMClient } from '@aws-sdk/client-ssm';

import type { Schema } from '../resource';

const lambda = new LambdaClient({});
const ssm = new SSMClient({});
const responderParameterName = process.env.CONSOLE_RESPONDER_PARAMETER_NAME?.trim();
let responderFunctionName: string | undefined;

const getResponderFunctionName = async (): Promise<string> => {
  if (responderFunctionName) return responderFunctionName;
  if (!responderParameterName) {
    throw new Error('Console responder parameter is not configured');
  }

  const result = await ssm.send(new GetParameterCommand({ Name: responderParameterName }));
  const value = result.Parameter?.Value?.trim();
  if (!value) throw new Error('Console responder target is not configured');
  responderFunctionName = value;
  return value;
};

/**
 * Starts the Console responder immediately after the user message is durable.
 * This is the sole cloud delivery mechanism. The responder's conditional
 * PENDING -> RUNNING claim remains the exactly-once guard for invocations.
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
