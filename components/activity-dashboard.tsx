stages: { items: [] } 

dispatchStatus: ['PENDING'], 

datasetClassDistribution: [],
isDatasetClassDistributionBalanced: null,
predictedClassDistribution: [],
confusionMatrix: null,
scoreGoal: null,
isPredictedClassDistributionBalanced: null,
scoreResults: [],

command: task.data?.command,

console.debug('Rendering selected task in Activity Dashboard:', {
  taskId: task.id,
  type: task.type,
  command: task.data?.command,
  isEvaluation: task.type.toLowerCase().includes('evaluation'),
  commandDisplay: 'full'
});