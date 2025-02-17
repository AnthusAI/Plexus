import type { AmplifyTask } from '@/types/tasks/amplify';
import type { ProcessedTask } from '@/types/tasks/processed';

export async function transformAmplifyTask(task: AmplifyTask): Promise<ProcessedTask> {
  // Handle evaluation - if it's a function (LazyLoader), await it
  const evaluation = task.evaluation && typeof task.evaluation === 'function' ? 
    await task.evaluation() : task.evaluation;

  // Handle scorecard - if it's a function (LazyLoader), await it
  const scorecard = task.scorecard && typeof task.scorecard === 'function' ? 
    await task.scorecard() : task.scorecard;

  // Handle score - if it's a function (LazyLoader), await it
  const score = task.score && typeof task.score === 'function' ? 
    await task.score() : task.score;

  return {
    ...task,
    evaluation,
    scorecard,
    score,
    // Ensure description is never null, only undefined or string
    description: task.description || undefined
  };
} 