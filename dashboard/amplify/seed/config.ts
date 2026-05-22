import type { SeedConfig } from './types';

export async function loadConfig(): Promise<SeedConfig> {
  return {
    tables: {
      // Phase 1: Foundation (no dependencies)
      'Account': {
        name: 'Account',
        strategy: 'full',
        maxItems: 1,
        dependencies: []
      },
      'User': {
        name: 'User',
        strategy: 'full',
        enabled: false,
        maxItems: 0,
        dependencies: []
      },

      // Phase 2: Core Structure (scorecard hierarchy)
      'Scorecard': {
        name: 'Scorecard',
        strategy: 'full',
        maxItems: 100,
        dependencies: ['Account']
      },
      'ScorecardSection': {
        name: 'ScorecardSection',
        strategy: 'full',
        maxItems: 500,
        maxPerParent: 25,
        dependencies: ['Scorecard']
      },
      'Score': {
        name: 'Score',
        strategy: 'full',
        maxItems: 500,
        maxPerParent: 25,
        dependencies: ['ScorecardSection', 'Scorecard']
      },
      'ScoreVersion': {
        name: 'ScoreVersion',
        strategy: 'full',
        maxItems: 300,
        maxPerParent: 3,
        pageSize: 25,
        preferFeatured: true,
        dependencies: ['Score', 'User']
      },

      // Phase 3: Reference Data
      'ReportConfiguration': {
        name: 'ReportConfiguration',
        strategy: 'full',
        maxItems: 25,
        dependencies: ['Account']
      },
      'ShareLink': {
        name: 'ShareLink',
        strategy: 'full',
        maxItems: 25,
        dependencies: ['Account']
      },
      'DataSource': {
        name: 'DataSource',
        strategy: 'full',
        maxItems: 50,
        dependencies: ['Account', 'Scorecard', 'Score']
      },
      'DataSourceVersion': {
        name: 'DataSourceVersion',
        strategy: 'full',
        maxItems: 100,
        maxPerParent: 2,
        dependencies: ['DataSource']
      },
      'Procedure': {
        name: 'Procedure',
        strategy: 'full',
        maxItems: 12,
        dependencies: ['Account', 'Scorecard', 'Score', 'ScoreVersion']
      },

      // Phase 4: Operational Data (time-filtered)
      'Task': {
        name: 'Task',
        strategy: 'recent',
        maxItems: 100,
        gsiName: 'byAccountAndUpdatedAt',
        gsiKey: 'accountId',
        sortKey: 'updatedAt',
        dependencies: ['Account', 'Scorecard', 'Score']
      },
      'Evaluation': {
        name: 'Evaluation',
        strategy: 'recent',
        maxItems: 250,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'Scorecard', 'Score', 'User']
      },
      'Report': {
        name: 'Report',
        strategy: 'recent',
        maxItems: 25,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'ReportConfiguration', 'Task', 'User']
      },
      'ChatSession': {
        name: 'ChatSession',
        strategy: 'recent',
        maxItems: 25,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account']
      },
      'AggregatedMetrics': {
        name: 'AggregatedMetrics',
        strategy: 'recent',
        maxItems: 250,
        gsiName: 'byAccountRecordType',
        gsiKey: 'accountId',
        sortKey: 'timeRangeStart',
        dependencies: ['Account', 'Scorecard', 'Score']
      },

      // Phase 4: Large Scale Data (sampled)
      'Item': {
        name: 'Item',
        strategy: 'sampled',
        maxItems: 500,
        recentCount: 250,
        sampleCount: 250,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account']
      },
      'ScoreResult': {
        name: 'ScoreResult',
        strategy: 'sampled',
        maxItems: 500,
        maxPerParent: 5,
        recentCount: 250,
        sampleCount: 250,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'Scorecard', 'Item', 'ScoringJob', 'Evaluation', 'ScoreVersion', 'Score']
      },
      'ScoringJob': {
        name: 'ScoringJob',
        strategy: 'sampled',
        maxItems: 300,
        maxPerParent: 3,
        recentCount: 150,
        sampleCount: 150,
        gsiName: 'byAccountAndUpdatedAt',
        gsiKey: 'accountId',
        sortKey: 'updatedAt',
        dependencies: ['Account', 'Scorecard', 'Item', 'Score', 'Evaluation']
      },
      'FeedbackItem': {
        name: 'FeedbackItem',
        strategy: 'sampled',
        maxItems: 300,
        maxPerParent: 5,
        recentCount: 150,
        sampleCount: 150,
        gsiName: 'byAccountAndUpdatedAt',
        gsiKey: 'accountId',
        sortKey: 'updatedAt',
        dependencies: ['Account', 'Scorecard', 'Score', 'Item']
      },

      // Phase 5: Derived/Linked Data
      'TaskStage': {
        name: 'TaskStage',
        strategy: 'recent',
        maxItems: 100,
        maxPerParent: 10,
        dependencies: ['Task']
      },
      'ReportBlock': {
        name: 'ReportBlock',
        strategy: 'recent',
        maxItems: 100,
        maxPerParent: 10,
        dependencies: ['Report', 'DataSet']
      },
      'ChatMessage': {
        name: 'ChatMessage',
        strategy: 'recent',
        maxItems: 250,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'ChatSession']
      },
      'Identifier': {
        name: 'Identifier',
        strategy: 'sampled',
        maxItems: 250,
        recentCount: 250,
        sampleCount: 0,
        dependencies: ['Account', 'Item']
      },
      'DataSet': {
        name: 'DataSet',
        strategy: 'recent',
        maxItems: 100,
        gsiName: 'byAccountAndCreatedAt',
        gsiKey: 'accountId',
        sortKey: 'createdAt',
        dependencies: ['Account', 'Scorecard', 'Score', 'ScoreVersion', 'DataSourceVersion']
      },
      'ScorecardExampleItem': {
        name: 'ScorecardExampleItem',
        strategy: 'full',
        maxItems: 100,
        maxPerParent: 10,
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
