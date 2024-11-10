import { BaseTaskData, BaseActivity } from '../base'

export interface ReportTaskData extends BaseTaskData {
  // Report-specific fields can be added here
}

export interface ReportActivity extends BaseActivity {
  type: 'Report'
  data: ReportTaskData
} 