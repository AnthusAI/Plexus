'use client';

import EvaluationTask from '@/components/EvaluationTask';

export default function EvaluationsPage() {
  // Sample evaluation data for the example
  const sampleEvaluation = {
    id: "eval-123",
    type: "evaluation",
    scorecard: "scorecard-123",
    score: "score-123",
    time: "2024-03-20T12:00:00Z",
    summary: "Sample evaluation summary",
    data: {
      id: "eval-123",
      title: "Sample Evaluation",
      accuracy: 0.85,
      metrics: [
        {
          name: "Accuracy",
          value: 85,
          unit: "%",
          maximum: 100,
          priority: true
        }
      ],
      metricsExplanation: "This evaluation shows strong performance across key metrics.",
      processedItems: 100,
      totalItems: 100,
      progress: 100,
      inferences: 100,
      cost: 0.50,
      status: "COMPLETED",
      elapsedSeconds: 120,
      estimatedRemainingSeconds: 0,
      startedAt: "2024-03-20T12:00:00Z",
      confusionMatrix: {
        matrix: [[45, 5], [10, 40]],
        labels: ["Positive", "Negative"]
      },
      scoreGoal: "Achieve 90% accuracy",
      datasetClassDistribution: [
        { label: "Positive", count: 50 },
        { label: "Negative", count: 50 }
      ],
      isDatasetClassDistributionBalanced: true,
      predictedClassDistribution: [
        { label: "Positive", count: 55 },
        { label: "Negative", count: 45 }
      ],
      isPredictedClassDistributionBalanced: true,
      scoreResults: [{
        id: "sr-1",
        value: "Positive",
        confidence: 0.95,
        explanation: "High confidence prediction",
        metadata: {
          human_label: "Positive",
          correct: true,
          human_explanation: "Clear positive signal in text",
          text: "Sample text"
        },
        itemId: "item-1",
        createdAt: "2024-03-20T12:00:00Z",
        updatedAt: "2024-03-20T12:00:00Z"
      }]
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="prose max-w-none">
        <h1>Understanding Evaluations</h1>
        <p>
          Evaluations help you understand how well your AI models are performing.
          Here's an example of what an evaluation looks like:
        </p>
      </div>
      <div className="mt-8">
        <EvaluationTask
          variant="detail"
          task={sampleEvaluation}
          isFullWidth={true}
        />
      </div>
    </div>
  );
} 