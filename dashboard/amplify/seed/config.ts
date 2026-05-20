import type { SeedConfig } from './types';

export async function loadConfig(): Promise<SeedConfig> {
  return {
    tables: {
      // Phase 1: Foundation (no dependencies)
      'Account': {
        name: 'Account',
        strategy: 'full',
        dependencies: []
      },
      'User': {
        name: 'User',
        strategy: 'full',
        dependencies: []
      },

      // Phase 2: Core Structure (scorecard hierarchy)
      'Scorecard': {
        name: 'Scorecard',
        strategy: 'full',
        dependencies: ['Account']
      },
      'ScorecardSection': {
        name: 'ScorecardSection',
        strategy: 'full',
        dependencies: ['Scorecard']
      },
      'Score': {
        name: 'Score',
        strategy: 'full',
        dependencies: ['ScorecardSection', 'Scorecard']
      },
      'ScoreVersion': {
        name: 'ScoreVersion',
        strategy: 'full',
        dependencies: ['Score', 'User']
      },

      // Phase 3: Reference Data
      'ReportConfiguration': {
        name: 'ReportConfiguration',
        strategy: 'full',
        dependencies: ['Account']
      },
      'ShareLink': {
        name: 'ShareLink',
        strategy: 'full',
        dependencies: ['Account']
      },
      'DataSource': {
        name: 'DataSource',
        strategy: 'full',
        dependencies: ['Account', 'Scorecard', 'Score']
      },
      'DataSourceVersion': {
        name: 'DataSourceVersion',
        strategy: 'full',
        dependencies: ['DataSource']
      },
      'Procedure': {
        name: 'Procedure',
        strategy: 'full',
        dependencies: ['Account', 'Scorecard', 'Score', 'ScoreVersion']
      },

      // Phase 4: Operational Data (time-filtered)
      'Task': {
        name: 'Task',
        strategy: 'recent',
        gsiName: 'byAccountAndUpdatedAt',
        gsiKey: 'accountId',
        sortKey: 'updatedAt',
        dependencies: ['Account', 'Scorecard', 'Score']
      },
      'Evaluation': {
        name: 'Evaluation',
        strategy: 'recent',
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'Scorecard', 'Score', 'User']
      },
      'Report': {
        name: 'Report',
        strategy: 'recent',
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'ReportConfiguration', 'Task', 'User']
      },
      'ChatSession': {
        name: 'ChatSession',
        strategy: 'recent',
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account']
      },
      'AggregatedMetrics': {
        name: 'AggregatedMetrics',
        strategy: 'recent',
        gsiName: 'byAccountRecordType',
        gsiKey: 'accountId',
        sortKey: 'timeRangeStart',
        dependencies: ['Account', 'Scorecard', 'Score']
      },

      // Phase 4: Large Scale Data (sampled)
      'Item': {
        name: 'Item',
        strategy: 'sampled',
        recentCount: 1000,
        sampleCount: 1000,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account']
      },
      'ScoreResult': {
        name: 'ScoreResult',
        strategy: 'sampled',
        recentCount: 1000,
        sampleCount: 1000,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'Scorecard', 'Item', 'ScoringJob', 'Evaluation', 'ScoreVersion', 'Score']
      },
      'ScoringJob': {
        name: 'ScoringJob',
        strategy: 'sampled',
        recentCount: 1000,
        sampleCount: 1000,
        gsiName: 'byAccountAndUpdatedAt',
        gsiKey: 'accountId',
        sortKey: 'updatedAt',
        dependencies: ['Account', 'Scorecard', 'Item', 'Score', 'Evaluation']
      },
      'FeedbackItem': {
        name: 'FeedbackItem',
        strategy: 'sampled',
        recentCount: 1000,
        sampleCount: 1000,
        gsiName: 'byAccountAndUpdatedAt',
        gsiKey: 'accountId',
        sortKey: 'updatedAt',
        dependencies: ['Account', 'Scorecard', 'Score', 'Item']
      },

      // Phase 5: Derived/Linked Data
      'TaskStage': {
        name: 'TaskStage',
        strategy: 'recent',
        dependencies: ['Task']
      },
      'ReportBlock': {
        name: 'ReportBlock',
        strategy: 'recent',
        dependencies: ['Report', 'DataSet']
      },
      'ChatMessage': {
        name: 'ChatMessage',
        strategy: 'recent',
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'ChatSession']
      },
      'Identifier': {
        name: 'Identifier',
        strategy: 'sampled',
        recentCount: 2000,
        sampleCount: 0,
        dependencies: ['Account', 'Item']
      },
      'DataSet': {
        name: 'DataSet',
        strategy: 'recent',
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'Scorecard', 'Score', 'ScoreVersion', 'DataSourceVersion']
      },
      'ScorecardExampleItem': {
        name: 'ScorecardExampleItem',
        strategy: 'full',
        dependencies: ['Scorecard', 'Item']
      }
    },

    s3Buckets: [
      'reportBlockDetails',
      'dataSources',
      'scoreResultAttachments',
      'taskAttachments',
      'rubricMemory'
    ],

    parallelism: 3
  };
}
