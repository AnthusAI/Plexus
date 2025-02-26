export const GET_SCORECARD_WITH_SECTIONS_AND_SCORES = `
  query GetScorecardWithSectionsAndScores($id: ID!) {
    getScorecard(id: $id) {
      id
      name
      key
      description
      externalId
      accountId
      itemId
      createdAt
      updatedAt
      sections {
        items {
          id
          name
          order
          scorecardId
          createdAt
          updatedAt
          scores {
            items {
              id
              name
              key
              description
              order
              type
              accuracy
              version
              aiProvider
              aiModel
              sectionId
              externalId
              createdAt
              updatedAt
              championVersionId
              championVersion {
                id
                configuration
                createdAt
                updatedAt
              }
            }
          }
        }
      }
    }
  }
`;

export const LIST_SCORECARDS_WITH_SECTIONS_AND_SCORES = `
  query ListScorecardsWithSectionsAndScores($filter: ModelScorecardFilterInput, $limit: Int, $nextToken: String) {
    listScorecards(filter: $filter, limit: $limit, nextToken: $nextToken) {
      items {
        id
        name
        key
        description
        externalId
        accountId
        itemId
        createdAt
        updatedAt
        sections {
          items {
            id
            name
            order
            scorecardId
            createdAt
            updatedAt
            scores {
              items {
                id
                name
                key
                description
                order
                type
                accuracy
                version
                aiProvider
                aiModel
                sectionId
                externalId
                createdAt
                updatedAt
                championVersionId
                championVersion {
                  id
                  configuration
                  createdAt
                  updatedAt
                }
              }
            }
          }
        }
      }
      nextToken
    }
  }
`;

export const LIST_SCORECARDS_BY_ACCOUNT_ID = `
  query ListScorecardsByAccountId($accountId: ID!, $limit: Int, $nextToken: String) {
    listScorecards(filter: {accountId: {eq: $accountId}}, limit: $limit, nextToken: $nextToken, sortDirection: DESC) {
      items {
        id
        name
        key
        description
        externalId
        accountId
        itemId
        createdAt
        updatedAt
        sections {
          items {
            id
            name
            order
            scorecardId
            createdAt
            updatedAt
            scores {
              items {
                id
                name
                key
                description
                order
                type
                accuracy
                version
                aiProvider
                aiModel
                sectionId
                externalId
                createdAt
                updatedAt
                championVersionId
                championVersion {
                  id
                  configuration
                  createdAt
                  updatedAt
                }
              }
            }
          }
        }
      }
      nextToken
    }
  }
`;

export const SCORECARD_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateScorecard {
    onUpdateScorecard {
      id
      name
      key
      description
      externalId
      accountId
      itemId
      createdAt
      updatedAt
    }
  }
`;

export const SCORECARD_CREATE_SUBSCRIPTION = `
  subscription OnCreateScorecard {
    onCreateScorecard {
      id
      name
      key
      description
      externalId
      accountId
      itemId
      createdAt
      updatedAt
    }
  }
`;

export const SCORECARD_DELETE_SUBSCRIPTION = `
  subscription OnDeleteScorecard {
    onDeleteScorecard {
      id
    }
  }
`; 