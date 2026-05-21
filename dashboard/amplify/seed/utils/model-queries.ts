import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';

type ModelClient = Record<string, any>;

export type ResolvedAccount = {
  id: string;
  key?: string;
  name?: string;
};

function getModel(client: V6Client<Schema>, tableName: string): ModelClient {
  return (client.models as any)[tableName];
}

export function getAccountIndexQueryName(tableName: string): string {
  return `list${tableName}ByAccountId`;
}

export function findAccountIndexQueryName(model: ModelClient, tableName: string): string | null {
  const exactName = getAccountIndexQueryName(tableName);

  if (typeof model[exactName] === 'function') {
    return exactName;
  }

  const prefix = `${exactName}And`;
  const queryName = Object.keys(model)
    .filter((key) => key.startsWith(prefix) && typeof model[key] === 'function')
    .sort()[0];

  return queryName || null;
}

export async function listAccountScopedPage(
  client: V6Client<Schema>,
  tableName: string,
  accountId: string,
  options: Record<string, unknown> = {}
): Promise<any> {
  const model = getModel(client, tableName);

  if (tableName === 'Account') {
    const result = await model.get({ id: accountId });
    if (!result.data && !options.nextToken) {
      const sampleResult = await model.list({ limit: 10 });
      const sampleAccounts = (sampleResult.data || [])
        .map((account: any) => `${account.id}${account.key ? ` (${account.key})` : ''}`)
        .join(', ');

      throw new Error(
        [
          `Production account ${accountId} was not found.`,
          sampleAccounts ? `Available account ids from this API: ${sampleAccounts}` : 'No accounts were visible from this API.'
        ].join(' ')
      );
    }

    return {
      data: result.data ? [result.data] : [],
      nextToken: null
    };
  }

  const queryName = findAccountIndexQueryName(model, tableName);
  if (queryName) {
    return model[queryName]({
      accountId,
      ...options
    });
  }

  throw new Error(`No account-scoped query is configured for ${tableName}`);
}

export async function listVisibleAccounts(client: V6Client<Schema>, limit = 10): Promise<ResolvedAccount[]> {
  const model = getModel(client, 'Account');
  const result = await model.list({ limit });

  return (result.data || []).map((account: any) => ({
    id: account.id,
    key: account.key,
    name: account.name
  }));
}

export async function resolveAccountByKey(
  client: V6Client<Schema>,
  accountKey: string
): Promise<ResolvedAccount | null> {
  const model = getModel(client, 'Account');

  if (typeof model.listAccountByKey === 'function') {
    const result = await model.listAccountByKey({ key: accountKey, limit: 2 });
    const account = result.data?.[0];

    return account
      ? {
          id: account.id,
          key: account.key,
          name: account.name
        }
      : null;
  }

  const result = await model.list({
    filter: { key: { eq: accountKey } },
    limit: 2
  });
  const account = result.data?.[0];

  return account
    ? {
        id: account.id,
        key: account.key,
        name: account.name
      }
    : null;
}

export async function resolveAccountById(
  client: V6Client<Schema>,
  accountId: string
): Promise<ResolvedAccount | null> {
  const model = getModel(client, 'Account');
  const result = await model.get({ id: accountId });
  const account = result.data;

  return account
    ? {
        id: account.id,
        key: account.key,
        name: account.name
      }
    : null;
}
