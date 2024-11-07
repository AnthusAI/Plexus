import { type ClientSchema, a, defineData } from "@aws-amplify/backend";

const schema = a.schema({
  Account: a
    .model({
      name: a.string().required(),
      key: a.string().required(),
      description: a.string(),
      scorecards: a.hasMany('Scorecard', 'accountId'),
      experiments: a.hasMany('Experiment', 'accountId'),
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
      inferences: a.integer(),
      cost: a.float(),
      accuracy: a.float(),
      accuracyType: a.string(),
      sensitivity: a.float(),
      specificity: a.float(),
      precision: a.float(),
      createdAt: a.datetime().required(),
      updatedAt: a.datetime().required(),
      status: a.string().required(),
      startedAt: a.datetime(),
      estimatedEndAt: a.datetime(),
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
      samples: a.hasMany('Sample', 'experimentId'),
      confusionMatrix: a.json(),
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

  Sample: a
    .model({
      experimentId: a.string().required(),
      experiment: a.belongsTo('Experiment', 'experimentId'),
      data: a.json(),
      prediction: a.string(),
      groundTruth: a.string(),
      isCorrect: a.boolean(),
      createdAt: a.datetime().required(),
      updatedAt: a.datetime().required(),
    })
    .authorization((allow) => [
      allow.publicApiKey(),
      allow.authenticated()
    ])
    .secondaryIndexes((idx) => [
      idx("experimentId")
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