import { type ClientSchema, a, defineData } from "@aws-amplify/backend";

const schema = a.schema({
  Account: a
    .model({
      name: a.string().required(),
      key: a.string().required(),
      description: a.string(),
      scorecards: a.hasMany('Scorecard', 'accountId'),
    })
    .authorization((allow) => [allow.authenticated()])
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
    })
    .authorization((allow) => [allow.authenticated()])
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
    .authorization((allow) => [allow.authenticated()])
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
    })
    .authorization((allow) => [allow.authenticated()])
    .secondaryIndexes((idx) => [
      idx("sectionId")
    ]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool'
  },
});``