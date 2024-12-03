export const listBatchJobScoringJobs = /* GraphQL */ `
  query ListBatchJobScoringJobs(
    $filter: ModelBatchJobScoringJobFilterInput
  ) {
    listBatchJobScoringJobs(filter: $filter) {
      items {
        batchJobId
        scoringJobId
      }
    }
  }
`;

export const getScoringJob = /* GraphQL */ `
  query GetScoringJob($id: ID!) {
    getScoringJob(id: $id) {
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