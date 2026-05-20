import type { Schema } from '../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';

export type CopyStrategy = 'full' | 'recent' | 'sampled';

export interface TableConfig {
  name: string;
  strategy: CopyStrategy;
  recentCount?: number;
  sampleCount?: number;
  gsiName?: string;
  gsiKey?: string;
  sortKey?: string;
  dependencies?: string[];
}

export interface SeedConfig {
  tables: Record<string, TableConfig>;
  s3Buckets: string[];
  parallelism: number;
}

export interface SeedContext {
  sandboxClient: V6Client<Schema>;
  productionClient: V6Client<Schema>;
  accountId: string;
  daysRecent: number;
  config: SeedConfig;
  logger: Logger;
}

export interface Logger {
  start(message: string): void;
  phase(message: string): void;
  table(tableName: string, message: string): void;
  progress(tableName: string, message: string): void;
  info(context: string, message: string): void;
  success(tableName: string, message: string): void;
  warn(tableName: string, message: string): void;
  error(tableName: string, message: string): void;
  complete(message: string): void;
}
