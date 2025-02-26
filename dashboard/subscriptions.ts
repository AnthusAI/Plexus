/* tslint:disable */
/* eslint-disable */
// this is an auto generated file. This will be overwritten

import * as APITypes from "./API";
type GeneratedSubscription<InputType, OutputType> = string & {
  __generatedSubscriptionInput: InputType;
  __generatedSubscriptionOutput: OutputType;
};

export const onCreateAccount = /* GraphQL */ `subscription OnCreateAccount($filter: ModelSubscriptionAccountFilterInput) {
  onCreateAccount(filter: $filter) {
    createdAt
    description
    id
    key
    name
    scorecards {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnCreateAccountSubscriptionVariables,
  APITypes.OnCreateAccountSubscription
>;
export const onCreateScore = /* GraphQL */ `subscription OnCreateScore($filter: ModelSubscriptionScoreFilterInput) {
  onCreateScore(filter: $filter) {
    accuracy
    aiModel
    aiProvider
    configuration
    createdAt
    distribution
    id
    isFineTuned
    name
    order
    section {
      createdAt
      id
      name
      order
      scorecardId
      updatedAt
      __typename
    }
    sectionId
    type
    updatedAt
    version
    versionHistory
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnCreateScoreSubscriptionVariables,
  APITypes.OnCreateScoreSubscription
>;
export const onCreateScorecard = /* GraphQL */ `subscription OnCreateScorecard($filter: ModelSubscriptionScorecardFilterInput) {
  onCreateScorecard(filter: $filter) {
    account {
      createdAt
      description
      id
      key
      name
      updatedAt
      __typename
    }
    accountId
    createdAt
    description
    externalId
    id
    key
    name
    sections {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnCreateScorecardSubscriptionVariables,
  APITypes.OnCreateScorecardSubscription
>;
export const onCreateScorecardSection = /* GraphQL */ `subscription OnCreateScorecardSection(
  $filter: ModelSubscriptionScorecardSectionFilterInput
) {
  onCreateScorecardSection(filter: $filter) {
    createdAt
    id
    name
    order
    scorecard {
      accountId
      createdAt
      description
      externalId
      id
      key
      name
      updatedAt
      __typename
    }
    scorecardId
    scores {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnCreateScorecardSectionSubscriptionVariables,
  APITypes.OnCreateScorecardSectionSubscription
>;
export const onDeleteAccount = /* GraphQL */ `subscription OnDeleteAccount($filter: ModelSubscriptionAccountFilterInput) {
  onDeleteAccount(filter: $filter) {
    createdAt
    description
    id
    key
    name
    scorecards {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnDeleteAccountSubscriptionVariables,
  APITypes.OnDeleteAccountSubscription
>;
export const onDeleteScore = /* GraphQL */ `subscription OnDeleteScore($filter: ModelSubscriptionScoreFilterInput) {
  onDeleteScore(filter: $filter) {
    accuracy
    aiModel
    aiProvider
    configuration
    createdAt
    distribution
    id
    isFineTuned
    name
    order
    section {
      createdAt
      id
      name
      order
      scorecardId
      updatedAt
      __typename
    }
    sectionId
    type
    updatedAt
    version
    versionHistory
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnDeleteScoreSubscriptionVariables,
  APITypes.OnDeleteScoreSubscription
>;
export const onDeleteScorecard = /* GraphQL */ `subscription OnDeleteScorecard($filter: ModelSubscriptionScorecardFilterInput) {
  onDeleteScorecard(filter: $filter) {
    account {
      createdAt
      description
      id
      key
      name
      updatedAt
      __typename
    }
    accountId
    createdAt
    description
    externalId
    id
    key
    name
    sections {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnDeleteScorecardSubscriptionVariables,
  APITypes.OnDeleteScorecardSubscription
>;
export const onDeleteScorecardSection = /* GraphQL */ `subscription OnDeleteScorecardSection(
  $filter: ModelSubscriptionScorecardSectionFilterInput
) {
  onDeleteScorecardSection(filter: $filter) {
    createdAt
    id
    name
    order
    scorecard {
      accountId
      createdAt
      description
      externalId
      id
      key
      name
      updatedAt
      __typename
    }
    scorecardId
    scores {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnDeleteScorecardSectionSubscriptionVariables,
  APITypes.OnDeleteScorecardSectionSubscription
>;
export const onUpdateAccount = /* GraphQL */ `subscription OnUpdateAccount($filter: ModelSubscriptionAccountFilterInput) {
  onUpdateAccount(filter: $filter) {
    createdAt
    description
    id
    key
    name
    scorecards {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnUpdateAccountSubscriptionVariables,
  APITypes.OnUpdateAccountSubscription
>;
export const onUpdateScore = /* GraphQL */ `subscription OnUpdateScore($filter: ModelSubscriptionScoreFilterInput) {
  onUpdateScore(filter: $filter) {
    accuracy
    aiModel
    aiProvider
    configuration
    createdAt
    distribution
    id
    isFineTuned
    name
    order
    section {
      createdAt
      id
      name
      order
      scorecardId
      updatedAt
      __typename
    }
    sectionId
    type
    updatedAt
    version
    versionHistory
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnUpdateScoreSubscriptionVariables,
  APITypes.OnUpdateScoreSubscription
>;
export const onUpdateScorecard = /* GraphQL */ `subscription OnUpdateScorecard($filter: ModelSubscriptionScorecardFilterInput) {
  onUpdateScorecard(filter: $filter) {
    account {
      createdAt
      description
      id
      key
      name
      updatedAt
      __typename
    }
    accountId
    createdAt
    description
    externalId
    id
    key
    name
    sections {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnUpdateScorecardSubscriptionVariables,
  APITypes.OnUpdateScorecardSubscription
>;
export const onUpdateScorecardSection = /* GraphQL */ `subscription OnUpdateScorecardSection(
  $filter: ModelSubscriptionScorecardSectionFilterInput
) {
  onUpdateScorecardSection(filter: $filter) {
    createdAt
    id
    name
    order
    scorecard {
      accountId
      createdAt
      description
      externalId
      id
      key
      name
      updatedAt
      __typename
    }
    scorecardId
    scores {
      nextToken
      __typename
    }
    updatedAt
    __typename
  }
}
` as GeneratedSubscription<
  APITypes.OnUpdateScorecardSectionSubscriptionVariables,
  APITypes.OnUpdateScorecardSectionSubscription
>;
