/* tslint:disable */
/* eslint-disable */
// this is an auto generated file. This will be overwritten

import * as APITypes from "./API";
type GeneratedQuery<InputType, OutputType> = string & {
  __generatedQueryInput: InputType;
  __generatedQueryOutput: OutputType;
};

export const getAccount = /* GraphQL */ `query GetAccount($id: ID!) {
  getAccount(id: $id) {
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
` as GeneratedQuery<
  APITypes.GetAccountQueryVariables,
  APITypes.GetAccountQuery
>;
export const getScore = /* GraphQL */ `query GetScore($id: ID!) {
  getScore(id: $id) {
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
` as GeneratedQuery<APITypes.GetScoreQueryVariables, APITypes.GetScoreQuery>;
export const getScorecard = /* GraphQL */ `query GetScorecard($id: ID!) {
  getScorecard(id: $id) {
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
` as GeneratedQuery<
  APITypes.GetScorecardQueryVariables,
  APITypes.GetScorecardQuery
>;
export const getScorecardSection = /* GraphQL */ `query GetScorecardSection($id: ID!) {
  getScorecardSection(id: $id) {
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
` as GeneratedQuery<
  APITypes.GetScorecardSectionQueryVariables,
  APITypes.GetScorecardSectionQuery
>;
export const listAccountByKey = /* GraphQL */ `query ListAccountByKey(
  $filter: ModelAccountFilterInput
  $key: String!
  $limit: Int
  $nextToken: String
  $sortDirection: ModelSortDirection
) {
  listAccountByKey(
    filter: $filter
    key: $key
    limit: $limit
    nextToken: $nextToken
    sortDirection: $sortDirection
  ) {
    items {
      createdAt
      description
      id
      key
      name
      updatedAt
      __typename
    }
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListAccountByKeyQueryVariables,
  APITypes.ListAccountByKeyQuery
>;
export const listAccounts = /* GraphQL */ `query ListAccounts(
  $filter: ModelAccountFilterInput
  $limit: Int
  $nextToken: String
) {
  listAccounts(filter: $filter, limit: $limit, nextToken: $nextToken) {
    items {
      createdAt
      description
      id
      key
      name
      updatedAt
      __typename
    }
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListAccountsQueryVariables,
  APITypes.ListAccountsQuery
>;
export const listScoreBySectionId = /* GraphQL */ `query ListScoreBySectionId(
  $filter: ModelScoreFilterInput
  $limit: Int
  $nextToken: String
  $sectionId: String!
  $sortDirection: ModelSortDirection
) {
  listScoreBySectionId(
    filter: $filter
    limit: $limit
    nextToken: $nextToken
    sectionId: $sectionId
    sortDirection: $sortDirection
  ) {
    items {
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
      sectionId
      type
      updatedAt
      version
      versionHistory
      __typename
    }
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScoreBySectionIdQueryVariables,
  APITypes.ListScoreBySectionIdQuery
>;
export const listScorecardByAccountId = /* GraphQL */ `query ListScorecardByAccountId(
  $accountId: String!
  $filter: ModelScorecardFilterInput
  $limit: Int
  $nextToken: String
  $sortDirection: ModelSortDirection
) {
  listScorecardByAccountId(
    accountId: $accountId
    filter: $filter
    limit: $limit
    nextToken: $nextToken
    sortDirection: $sortDirection
  ) {
    items {
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
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScorecardByAccountIdQueryVariables,
  APITypes.ListScorecardByAccountIdQuery
>;
export const listScorecardByExternalId = /* GraphQL */ `query ListScorecardByExternalId(
  $externalId: String!
  $filter: ModelScorecardFilterInput
  $limit: Int
  $nextToken: String
  $sortDirection: ModelSortDirection
) {
  listScorecardByExternalId(
    externalId: $externalId
    filter: $filter
    limit: $limit
    nextToken: $nextToken
    sortDirection: $sortDirection
  ) {
    items {
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
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScorecardByExternalIdQueryVariables,
  APITypes.ListScorecardByExternalIdQuery
>;
export const listScorecardByKey = /* GraphQL */ `query ListScorecardByKey(
  $filter: ModelScorecardFilterInput
  $key: String!
  $limit: Int
  $nextToken: String
  $sortDirection: ModelSortDirection
) {
  listScorecardByKey(
    filter: $filter
    key: $key
    limit: $limit
    nextToken: $nextToken
    sortDirection: $sortDirection
  ) {
    items {
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
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScorecardByKeyQueryVariables,
  APITypes.ListScorecardByKeyQuery
>;
export const listScorecardSectionByScorecardId = /* GraphQL */ `query ListScorecardSectionByScorecardId(
  $filter: ModelScorecardSectionFilterInput
  $limit: Int
  $nextToken: String
  $scorecardId: String!
  $sortDirection: ModelSortDirection
) {
  listScorecardSectionByScorecardId(
    filter: $filter
    limit: $limit
    nextToken: $nextToken
    scorecardId: $scorecardId
    sortDirection: $sortDirection
  ) {
    items {
      createdAt
      id
      name
      order
      scorecardId
      updatedAt
      __typename
    }
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScorecardSectionByScorecardIdQueryVariables,
  APITypes.ListScorecardSectionByScorecardIdQuery
>;
export const listScorecardSections = /* GraphQL */ `query ListScorecardSections(
  $filter: ModelScorecardSectionFilterInput
  $limit: Int
  $nextToken: String
) {
  listScorecardSections(filter: $filter, limit: $limit, nextToken: $nextToken) {
    items {
      createdAt
      id
      name
      order
      scorecardId
      updatedAt
      __typename
    }
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScorecardSectionsQueryVariables,
  APITypes.ListScorecardSectionsQuery
>;
export const listScorecards = /* GraphQL */ `query ListScorecards(
  $filter: ModelScorecardFilterInput
  $limit: Int
  $nextToken: String
) {
  listScorecards(filter: $filter, limit: $limit, nextToken: $nextToken) {
    items {
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
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScorecardsQueryVariables,
  APITypes.ListScorecardsQuery
>;
export const listScores = /* GraphQL */ `query ListScores(
  $filter: ModelScoreFilterInput
  $limit: Int
  $nextToken: String
) {
  listScores(filter: $filter, limit: $limit, nextToken: $nextToken) {
    items {
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
      sectionId
      type
      updatedAt
      version
      versionHistory
      __typename
    }
    nextToken
    __typename
  }
}
` as GeneratedQuery<
  APITypes.ListScoresQueryVariables,
  APITypes.ListScoresQuery
>;
