import { GraphQLResult } from '@aws-amplify/api';

export type LazyLoader<T> = T | (() => Promise<T>);

export type GraphQLResponse<T> = GraphQLResult<T>;

export type SubscriptionResponse<T> = {
  provider: any;
  value: {
    data: T;
  };
};

export type AmplifyListResult<T> = {
  data?: T[];
  nextToken?: string | null;
};

export type ConnectionState = 'connecting' | 'connected' | 'disconnected'; 