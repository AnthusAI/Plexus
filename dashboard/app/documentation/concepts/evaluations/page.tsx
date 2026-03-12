'use client';

import EvaluationTask from '@/components/EvaluationTask';
import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"

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
        updatedAt: "2024-03-20T12:00:00Z",
        trace: null,
        feedbackItem: {
          editCommentValue: "agree"
        }
      }]
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluations</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Evaluations in Plexus are how you validate and assess your scorecards to ensure they align with your 
        policies and stakeholder needs. They help you measure the effectiveness and accuracy of your scoring criteria 
        before deploying them to production.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Evaluations?</h2>
          <p className="text-muted-foreground mb-4">
            An evaluation is like a machine learning evaluation process - it's how you test and validate your 
            scorecards against known correct answers. This helps ensure your scoring criteria are properly calibrated 
            and will produce reliable results when deployed.
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Evaluation Components</h3>
              <p className="text-muted-foreground mb-4">
                Each evaluation consists of:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Test Dataset</strong>: A set of content with known correct answers
                </li>
                <li>
                  <strong>Scorecard</strong>: The scoring criteria being evaluated
                </li>
                <li>
                  <strong>Results</strong>: How well the scorecard's predictions match the known correct answers
                </li>
                <li>
                  <strong>Metrics</strong>: Performance indicators like accuracy, precision, and recall
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Evaluation Process</h3>
              <p className="text-muted-foreground mb-4">
                When you run an evaluation:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Your scorecard is applied to a test dataset with known correct answers</li>
                <li>The scorecard's predictions are compared against the ground truth</li>
                <li>Performance metrics are calculated to measure accuracy and reliability</li>
                <li>A comprehensive report helps you identify areas for improvement</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Example Evaluation</h2>
          <p className="text-muted-foreground mb-4">
            Here's an example of what a scorecard evaluation looks like in Plexus:
          </p>
          <div className="mt-4 border rounded-lg overflow-hidden">
            <EvaluationTask
              variant="detail"
              task={sampleEvaluation}
              isFullWidth={true}
            />
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Results</h2>
          <p className="text-muted-foreground mb-4">
            Evaluation results help you understand how well your scorecard performs and where it needs improvement:
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Score Results</h3>
              <p className="text-muted-foreground mb-4">
                For each score in your scorecard, you get:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>How well the predictions match known correct answers</li>
                <li>Detailed explanations of where and why mismatches occurred</li>
                <li>Confidence levels to identify uncertain predictions</li>
                <li>Insights for improving score accuracy</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Performance Metrics</h3>
              <p className="text-muted-foreground mb-4">
                Overall evaluation metrics help you assess scorecard quality:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Accuracy, precision, and recall statistics</li>
                <li>Performance trends as you refine your scorecard</li>
                <li>Comparison with baseline benchmarks</li>
                <li>Quality indicators to guide improvements</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using Evaluations</h2>
          <p className="text-muted-foreground mb-4">
            Evaluations are essential tools for developing reliable scorecards. Use them to:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Validate that scorecards align with your policies and requirements</li>
            <li>Identify and fix biases or gaps in scoring criteria</li>
            <li>Track scorecard improvement over time</li>
            <li>Build confidence in your scoring system before deployment</li>
          </ul>
          
          <div className="flex gap-4 mt-6">
            <Link href="/documentation/methods/evaluate-score">
              <DocButton>Learn How to Run Evaluations</DocButton>
            </Link>
            <Link href="/documentation/advanced/sdk">
              <DocButton variant="outline">Python SDK Reference</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
} 