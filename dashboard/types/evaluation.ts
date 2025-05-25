export interface TaskStage {
  id: string;
  name: string;
  order: number;
  status: string;
  statusMessage?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  processedItems?: number;
  totalItems?: number;
}

export interface TaskData {
  id: string;
  accountId: string;
  type: string;
  status: string;
  target: string;
  command: string;
  description?: string;
  dispatchStatus?: 'DISPATCHED';
  metadata?: any;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: string;
  currentStageId?: string;
  stages?: {
    items: TaskStage[];
    nextToken?: string | null;
  };
}

export interface ConfusionMatrix {
  matrix: number[][];
  labels: string[];
}

export interface EvaluationMetric {
  name?: string;
  value?: number;
  unit?: string;
  maximum?: number;
  priority?: boolean;
}

export interface ScoreResult {
  id: string;
  value: string | number;
  confidence: number | null;
  explanation: string | null;
  metadata: {
    human_label: string | null;
    correct: boolean;
    human_explanation?: string | null;
    text?: string | null;
  };
  trace?: any | null;
  itemId: string | null;
}

export interface EvaluationTaskData {
  id: string;
  title: string;
  accuracy: number | null;
  metrics: EvaluationMetric[];
  processedItems: number;
  totalItems: number;
  progress: number;
  inferences: number;
  cost: number | null;
  status: string;
  elapsedSeconds: number | null;
  estimatedRemainingSeconds: number | null;
  startedAt?: string;
  errorMessage?: string;
  errorDetails: any;
  task: TaskData | null;
  universalCode?: string | null;
}

export interface EvaluationTaskPropsInternal {
  id: string;
  type: string;
  scorecard: string;
  score: string;
  time: string;
  data: EvaluationTaskData;
} 