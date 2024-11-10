import { BaseTaskData, BaseActivity } from '../base'

interface RingData {
  outerRing: Array<{ category: string; value: number; fill: string }>
  innerRing: Array<{ category: string; value: number; fill: string }>
}

export interface ScoreUpdatedTaskData extends BaseTaskData {
  before: RingData
  after: RingData
}

export interface ScoreUpdatedActivity extends BaseActivity {
  type: 'Score updated'
  data: ScoreUpdatedTaskData
} 