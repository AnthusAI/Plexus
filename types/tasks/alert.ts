import { BaseTaskData, BaseActivity } from '../base'

export interface AlertTaskData extends BaseTaskData {
  iconType: 'siren' | 'warning' | 'info'
}

export interface AlertActivity extends BaseActivity {
  type: 'Alert'
  data: AlertTaskData
} 