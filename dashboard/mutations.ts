/* tslint:disable */
/* eslint-disable */
// this is an auto generated file. This will be overwritten

import * as APITypes from "./API";
type GeneratedMutation<InputType, OutputType> = string & {
  __generatedMutationInput: InputType;
  __generatedMutationOutput: OutputType;
};

export const createAccount = /* GraphQL */ `mutation CreateAccount(
  $condition: ModelAccountConditionInput
  $input: CreateAccountInput!
) {
  createAccount(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.CreateAccountMutationVariables,
  APITypes.CreateAccountMutation
>;
export const createScore = /* GraphQL */ `mutation CreateScore(
  $condition: ModelScoreConditionInput
  $input: CreateScoreInput!
) {
  createScore(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.CreateScoreMutationVariables,
  APITypes.CreateScoreMutation
>;
export const createScorecard = /* GraphQL */ `mutation CreateScorecard(
  $condition: ModelScorecardConditionInput
  $input: CreateScorecardInput!
) {
  createScorecard(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.CreateScorecardMutationVariables,
  APITypes.CreateScorecardMutation
>;
export const createScorecardSection = /* GraphQL */ `mutation CreateScorecardSection(
  $condition: ModelScorecardSectionConditionInput
  $input: CreateScorecardSectionInput!
) {
  createScorecardSection(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.CreateScorecardSectionMutationVariables,
  APITypes.CreateScorecardSectionMutation
>;
export const deleteAccount = /* GraphQL */ `mutation DeleteAccount(
  $condition: ModelAccountConditionInput
  $input: DeleteAccountInput!
) {
  deleteAccount(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.DeleteAccountMutationVariables,
  APITypes.DeleteAccountMutation
>;
export const deleteScore = /* GraphQL */ `mutation DeleteScore(
  $condition: ModelScoreConditionInput
  $input: DeleteScoreInput!
) {
  deleteScore(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.DeleteScoreMutationVariables,
  APITypes.DeleteScoreMutation
>;
export const deleteScorecard = /* GraphQL */ `mutation DeleteScorecard(
  $condition: ModelScorecardConditionInput
  $input: DeleteScorecardInput!
) {
  deleteScorecard(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.DeleteScorecardMutationVariables,
  APITypes.DeleteScorecardMutation
>;
export const deleteScorecardSection = /* GraphQL */ `mutation DeleteScorecardSection(
  $condition: ModelScorecardSectionConditionInput
  $input: DeleteScorecardSectionInput!
) {
  deleteScorecardSection(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.DeleteScorecardSectionMutationVariables,
  APITypes.DeleteScorecardSectionMutation
>;
export const updateAccount = /* GraphQL */ `mutation UpdateAccount(
  $condition: ModelAccountConditionInput
  $input: UpdateAccountInput!
) {
  updateAccount(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.UpdateAccountMutationVariables,
  APITypes.UpdateAccountMutation
>;
export const updateScore = /* GraphQL */ `mutation UpdateScore(
  $condition: ModelScoreConditionInput
  $input: UpdateScoreInput!
) {
  updateScore(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.UpdateScoreMutationVariables,
  APITypes.UpdateScoreMutation
>;
export const updateScorecard = /* GraphQL */ `mutation UpdateScorecard(
  $condition: ModelScorecardConditionInput
  $input: UpdateScorecardInput!
) {
  updateScorecard(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.UpdateScorecardMutationVariables,
  APITypes.UpdateScorecardMutation
>;
export const updateScorecardSection = /* GraphQL */ `mutation UpdateScorecardSection(
  $condition: ModelScorecardSectionConditionInput
  $input: UpdateScorecardSectionInput!
) {
  updateScorecardSection(condition: $condition, input: $input) {
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
` as GeneratedMutation<
  APITypes.UpdateScorecardSectionMutationVariables,
  APITypes.UpdateScorecardSectionMutation
>;
