export interface FeedbackItem {
  id: string
  scorecard: string
  inferences: string
  results: string
  cost: string
  status: string
  date: string
  sampleMetadata: Array<{ key: string; value: string }>
  sampleTranscript: Array<{ speaker: string; text: string }>
  sampleScoreResults: Array<{
    section: string
    scores: Array<{
      name: string
      value: string
      explanation: string
      isAnnotated: boolean
      allowFeedback: boolean
      annotations: Array<{
        value: string
        explanation: string
        annotation?: string
        timestamp: string
        user?: {
          name: string
          initials: string
        }
        isSystem?: boolean
        isThumbsUp?: boolean
      }>
    }>
  }>
} 