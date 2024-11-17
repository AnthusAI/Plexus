import { type ClientSchema, a, defineData } from "@aws-amplify/backend";

const schema = a.schema({
  Account: a
    .model({
      name: a.string().required(),
      key: a.string().required(),
      description: a.string(),
      scorecards: a.hasMany('Scorecard', 'accountId'),
      experiments: a.hasMany('Experiment', 'accountId'),
      batchJobs: a.hasMany('BatchJob', 'accountId'),
      items: a.hasMany('Item', 'accountId'),
      scoringJobs: a.hasMany('ScoringJob', 'accountId'),
      scoreResults: a.hasMany('ScoreResult', 'accountId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("key")
    ]),

  Scorecard: a
    .model({
      name: a.string().required(),
      key: a.string().required(),
      externalId: a.string().required(),
      description: a.string(),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      sections: a.hasMany('ScorecardSection', 'scorecardId'),
      experiments: a.hasMany('Experiment', 'scorecardId'),
      batchJobs: a.hasMany('BatchJob', 'scorecardId'),
      itemId: a.string(),
      item: a.belongsTo('Item', 'itemId'),
      scoringJobs: a.hasMany('ScoringJob', 'scorecardId'),
      scoreResults: a.hasMany('ScoreResult', 'scorecardId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("accountId"),
      idx("key"),
      idx("externalId")
    ]),

  ScorecardSection: a
    .model({
      name: a.string().required(),
      order: a.integer().required(),
      scorecardId: a.string().required(),
      scorecard: a.belongsTo('Scorecard', 'scorecardId'),
      scores: a.hasMany('Score', 'sectionId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("scorecardId")
    ]),

  Score: a
    .model({
      name: a.string().required(),
      type: a.string().required(),
      order: a.integer().required(),
      accuracy: a.float(),
      version: a.string(),
      sectionId: a.string().required(),
      section: a.belongsTo('ScorecardSection', 'sectionId'),
      aiProvider: a.string(),
      aiModel: a.string(),
      isFineTuned: a.boolean(),
      configuration: a.json(),
      distribution: a.json(),
      versionHistory: a.json(),
      experiments: a.hasMany('Experiment', 'scoreId'),
      batchJobs: a.hasMany('BatchJob', 'scoreId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("sectionId")
    ]),

  Experiment: a
    .model({
      type: a.string().required(),
      parameters: a.json(),
      metrics: a.json(),
      metricsExplanation: a.string(),
      inferences: a.integer(),
      accuracy: a.float(),
      cost: a.float(),
      createdAt: a.datetime().required(),
      updatedAt: a.datetime().required(),
      status: a.string().required(),
      startedAt: a.datetime(),
      elapsedSeconds: a.integer(),
      estimatedRemainingSeconds: a.integer(),
      totalItems: a.integer(),
      processedItems: a.integer(),
      errorMessage: a.string(),
      errorDetails: a.json(),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      scorecardId: a.string(),
      scorecard: a.belongsTo('Scorecard', 'scorecardId'),
      scoreId: a.string(),
      score: a.belongsTo('Score', 'scoreId'),
      confusionMatrix: a.json(),
      items: a.hasMany('Item', 'experimentId'),
      scoreResults: a.hasMany('ScoreResult', 'experimentId'),
      scoringJobs: a.hasMany('ScoringJob', 'experimentId'),
      scoreGoal: a.string(),
      datasetClassDistribution: a.json(),
      isDatasetClassDistributionBalanced: a.boolean(),
      predictedClassDistribution: a.json(),
      isPredictedClassDistributionBalanced: a.boolean(),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("accountId"),
      idx("scorecardId"),
      idx("scoreId")
    ]),

  BatchJob: a
    .model({
      provider: a.string().required(),
      type: a.string().required(),
      batchId: a.string().required(),
      status: a.string().required(),
      startedAt: a.datetime(),
      estimatedEndAt: a.datetime(),
      completedAt: a.datetime(),
      totalRequests: a.integer(),
      completedRequests: a.integer(),
      failedRequests: a.integer(),
      errorMessage: a.string(),
      errorDetails: a.json(),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      scorecardId: a.string(),
      scorecard: a.belongsTo('Scorecard', 'scorecardId'),
      scoreId: a.string(),
      score: a.belongsTo('Score', 'scoreId'),
      scoringJobs: a.hasMany('BatchJobScoringJob', 'batchJobId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("accountId"),
      idx("scorecardId"),
      idx("scoreId"),
      idx("batchId")
    ]),

  Item: a
    .model({
      name: a.string().required(),
      description: a.string(),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      scoringJobs: a.hasMany('ScoringJob', 'itemId'),
      scoreResults: a.hasMany('ScoreResult', 'itemId'),
      scorecards: a.hasMany('Scorecard', 'itemId'),
      experimentId: a.string(),
      experiment: a.belongsTo('Experiment', 'experimentId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("accountId")
    ]),

  ScoringJob: a
    .model({
      status: a.string().required(),
      startedAt: a.datetime(),
      completedAt: a.datetime(),
      errorMessage: a.string(),
      errorDetails: a.json(),
      itemId: a.string().required(),
      item: a.belongsTo('Item', 'itemId'),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      scorecardId: a.string().required(),
      scorecard: a.belongsTo('Scorecard', 'scorecardId'),
      experimentId: a.string(),
      experiment: a.belongsTo('Experiment', 'experimentId'),
      batchJobLinks: a.hasMany('BatchJobScoringJob', 'scoringJobId'),
      scoreResults: a.hasMany('ScoreResult', 'scoringJobId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("accountId"),
      idx("itemId"),
      idx("scorecardId"),
      idx("experimentId")
    ]),

  ScoreResult: a
    .model({
      value: a.float().required(),
      confidence: a.float(),
      metadata: a.json(),
      correct: a.boolean(),
      itemId: a.string().required(),
      item: a.belongsTo('Item', 'itemId'),
      accountId: a.string().required(),
      account: a.belongsTo('Account', 'accountId'),
      scoringJobId: a.string(),
      scoringJob: a.belongsTo('ScoringJob', 'scoringJobId'),
      experimentId: a.string(),
      experiment: a.belongsTo('Experiment', 'experimentId'),
      scorecardId: a.string().required(),
      scorecard: a.belongsTo('Scorecard', 'scorecardId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("accountId"),
      idx("itemId"),
      idx("scoringJobId"),
      idx("experimentId"),
      idx("scorecardId")
    ]),

  BatchJobScoringJob: a
    .model({
      batchJobId: a.string().required(),
      scoringJobId: a.string().required(),
      batchJob: a.belongsTo('BatchJob', 'batchJobId'),
      scoringJob: a.belongsTo('ScoringJob', 'scoringJobId'),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
    apiKeyAuthorizationMode: {
      expiresInDays: 0  // Never expires
    }
  },
});