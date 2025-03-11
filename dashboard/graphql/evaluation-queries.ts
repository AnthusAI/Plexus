export const EVALUATION_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateEvaluation {
    onUpdateEvaluation {
      id
      type
      parameters
      metrics
      metricsExplanation
      inferences
      accuracy
      cost
      createdAt
      updatedAt
      status
      startedAt
      elapsedSeconds
      estimatedRemainingSeconds
      totalItems
      processedItems
      errorMessage
      errorDetails
      accountId
      scorecardId
      scoreId
      confusionMatrix
      scoreGoal
      datasetClassDistribution
      isDatasetClassDistributionBalanced
      predictedClassDistribution
      isPredictedClassDistributionBalanced
      taskId
      task {
        id
        type
        status
        target
        command
        description
        dispatchStatus
        metadata
        createdAt
        startedAt
        completedAt
        estimatedCompletionAt
        errorMessage
        errorDetails
        currentStageId
        stages {
          items {
            id
            name
            order
            status
            statusMessage
            startedAt
            completedAt
            estimatedCompletionAt
            processedItems
            totalItems
          }
        }
      }
      scoreResults {
        items {
          id
          value
          confidence
          metadata
          explanation
          trace
          itemId
          createdAt
        }
        nextToken
      }
    }
  }
`;

export const TASK_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateTask {
    onUpdateTask {
      id
      type
      status
      target
      command
      description
      dispatchStatus
      metadata
      createdAt
      startedAt
      completedAt
      estimatedCompletionAt
      errorMessage
      errorDetails
      currentStageId
      stages {
        items {
          id
          name
          order
          status
          statusMessage
          startedAt
          completedAt
          estimatedCompletionAt
          processedItems
          totalItems
        }
      }
    }
  }
`;

export const TASK_STAGE_UPDATE_SUBSCRIPTION = `
  subscription OnUpdateTaskStage {
    onUpdateTaskStage {
      id
      taskId
      name
      order
      status
      statusMessage
      startedAt
      completedAt
      estimatedCompletionAt
      processedItems
      totalItems
    }
  }
`;

export const GET_TASK_QUERY = `
  query GetTask($id: ID!) {
    getTask(id: $id) {
      id
      type
      status
      target
      command
      description
      dispatchStatus
      metadata
      createdAt
      startedAt
      completedAt
      estimatedCompletionAt
      errorMessage
      errorDetails
      currentStageId
      stages {
        items {
          id
          name
          order
          status
          statusMessage
          startedAt
          completedAt
          estimatedCompletionAt
          processedItems
          totalItems
        }
      }
    }
  }
`;

export const ITEM_CREATE_SUBSCRIPTION = `
  subscription OnCreateItem {
    onCreateItem {
      id
      externalId
      description
      accountId
      scorecardId
      scoreId
      evaluationId
      updatedAt
      createdAt
      isEvaluation
    }
  }
`; 