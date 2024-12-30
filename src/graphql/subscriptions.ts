export const onUpdateScoringJob = /* GraphQL */ `
  subscription OnUpdateScoringJob {
    onUpdateScoringJob {
      id
      status
      accountId
      scorecardId
      itemId
      startedAt
      completedAt
      errorMessage
      errorDetails
      createdAt
      updatedAt
    }
  }
`; 