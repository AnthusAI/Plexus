export * from './base'
export * from './tasks/alert'
export * from './tasks/experiment'
export * from './tasks/optimization'
export * from './tasks/feedback'
export * from './tasks/scoring'
export * from './tasks/report'
export * from './tasks/score-updated'
export * from './tasks/batch-job'

import { AlertActivity } from './tasks/alert'
import { ExperimentActivity } from './tasks/experiment'
import { OptimizationActivity } from './tasks/optimization'
import { FeedbackActivity } from './tasks/feedback'
import { ScoringJobActivity } from './tasks/scoring'
import { ReportActivity } from './tasks/report'
import { ScoreUpdatedActivity } from './tasks/score-updated'
import { BatchJobActivity } from './tasks/batch-job'

// Simple union type
export type ActivityData = 
  | AlertActivity
  | ExperimentActivity
  | OptimizationActivity
  | FeedbackActivity
  | ScoringJobActivity
  | ReportActivity
  | ScoreUpdatedActivity
  | BatchJobActivity

// Type guards
export const isExperimentActivity = (activity: ActivityData): activity is ExperimentActivity => {
  return (activity.type === 'Experiment started' || activity.type === 'Experiment completed')
} 