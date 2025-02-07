export default function EvaluationsPage() {
  // Sample evaluation data for the example
  const sampleEvaluation = {
    id: 'example-1',
    type: 'Evaluation finished',
    scorecard: 'Lead Qualification',
    score: 'Qualified Lead?',
    time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    summary: 'Understanding evaluation results',
    data: {
      id: 'example-1',
      title: 'Lead Qualification Evaluation',
      accuracy: 85.5,
      metrics: [
        { name: "Accuracy", value: 85.5, unit: "%", maximum: 100, priority: true },
        { name: "Precision", value: 88.2, unit: "%", maximum: 100, priority: true },
        { name: "Sensitivity", value: 82.1, unit: "%", maximum: 100, priority: true },
        { name: "Specificity", value: 91.3, unit: "%", maximum: 100, priority: true }
      ],
      metricsExplanation: "",
      scoreGoal: "Accuracy",
      processedItems: 200,
      totalItems: 200,
      progress: 100,
      inferences: 200,
      cost: 0.30,
      status: 'complete',
      elapsedSeconds: 4800,
      estimatedRemainingSeconds: 0,
      confusionMatrix: {
        matrix: [
          [45, 5],
          [10, 40]
        ],
        labels: ["Qualified", "Not Qualified"]
      },
      datasetClassDistribution: [
        { label: "Qualified", count: 55 },
        { label: "Not Qualified", count: 45 }
      ],
      isDatasetClassDistributionBalanced: true,
      predictedClassDistribution: [
        { label: "Qualified", count: 50 },
        { label: "Not Qualified", count: 50 }
      ],
      isPredictedClassDistributionBalanced: true,
      scoreResults: Array.from({ length: 20 }, (_, i) => {
        const isQualified = Math.random() > 0.4;
        const correctPrediction = Math.random() > 0.15;
        const sampleText = [
          "Hi, I'm interested in implementing AI for our customer service team of 500+ agents. We're looking to improve efficiency and reduce response times. What kind of solutions can you offer?",
          "Just browsing your website. Not really looking to buy anything right now.",
          "We need help with our call center operations. Currently handling about 10,000 calls per month and want to implement quality monitoring. What's your pricing?",
          "I'm a student doing research on AI companies. Can I get some information about your technology?",
          "Looking for an enterprise solution for our insurance claims processing. We process over 50,000 claims monthly and need to improve accuracy."
        ][i % 5];
        
        const predictedLabel = correctPrediction ? 
          (isQualified ? "Qualified" : "Not Qualified") :
          (isQualified ? "Not Qualified" : "Qualified");
        
        const explanation = isQualified ?
          (correctPrediction ?
            "Shows clear interest in enterprise-level solution with specific requirements and scale indicators." :
            "Missed qualification signals: Mentioned team size and specific use case requirements.") :
          (correctPrediction ?
            "No clear buying intent or business requirements mentioned." :
            "Incorrectly interpreted general interest as qualified lead.");

        return {
          id: `result-${i}`,
          value: predictedLabel,
          confidence: 0.7 + (Math.random() * 0.3),
          explanation,
          metadata: JSON.stringify({
            human_label: isQualified ? "Qualified" : "Not Qualified",
            correct: correctPrediction,
            human_explanation: isQualified ?
              "Represents enterprise client with clear needs and scale" :
              "No clear business need or purchasing authority indicated",
            text: sampleText
          }),
          createdAt: new Date(Date.now() - Math.floor(Math.random() * 7200000)).toISOString(), // Random time in last 2 hours
          itemId: `item-${i}`,
          EvaluationId: 'eval-1',
          scorecardId: 'scorecard-1'
        }
      })
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <style jsx>{`
        .code-container {
          position: relative;
          overflow-x: auto;
          white-space: pre;
          -webkit-overflow-scrolling: touch;
        }
        
        .code-container::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 16px;
          background: linear-gradient(to right, transparent, var(--background-muted));
          opacity: 0;
          transition: opacity 0.2s;
          pointer-events: none;
        }
        
        .code-container:hover::after {
          opacity: 1;
        }
      `}</style>

      <h1 className="text-4xl font-bold mb-4">Evaluations</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to evaluate your scorecards and analyze their performance.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            Evaluations help you measure and improve your scorecard's performance by analyzing its predictions
            against labeled samples. This process is essential for ensuring your scorecards are accurate and reliable.
          </p>
          <p className="text-muted-foreground mb-4">
            When you run an evaluation, Plexus will:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Test your scorecard against a set of labeled examples</li>
            <li>Calculate key performance metrics like accuracy and precision</li>
            <li>Generate visualizations to help understand the results</li>
            <li>Store the results for future reference and comparison</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Evaluation Results</h2>
          <p className="text-muted-foreground mb-4">
            Here's an example of what an evaluation looks like in the dashboard:
          </p>
          <div className="my-6">
            <EvaluationTask
              variant="detail"
              task={sampleEvaluation}
              isFullWidth={true}
            />
          </div>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Key Components</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Performance Metrics</strong>: See accuracy, precision, sensitivity, and specificity scores
                  at a glance
                </li>
                <li>
                  <strong>Class Distribution</strong>: Understand the balance of your test data and predictions
                </li>
                <li>
                  <strong>Confusion Matrix</strong>: Visualize where your scorecard excels or needs improvement
                </li>
                <li>
                  <strong>Individual Results</strong>: Review specific examples to understand prediction patterns
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Metrics Explained</h2>
          <div className="space-y-3">
            <div>
              <h4 className="font-medium">Accuracy</h4>
              <p className="text-muted-foreground">
                The percentage of correct predictions. For example, if your "Qualified Lead?" score 
                correctly identifies 95 out of 100 leads, the accuracy is 95%.
              </p>
            </div>
            <div>
              <h4 className="font-medium">Precision</h4>
              <p className="text-muted-foreground">
                Of the leads marked as qualified by the "Qualified Lead?" score, what percentage were actually qualified? 
                High precision means fewer false positives.
              </p>
            </div>
            <div>
              <h4 className="font-medium">Recall (Sensitivity)</h4>
              <p className="text-muted-foreground">
                Of all actually qualified leads, what percentage did we identify? High recall means 
                fewer missed opportunities.
              </p>
            </div>
            <div>
              <h4 className="font-medium">Specificity</h4>
              <p className="text-muted-foreground">
                Of all unqualified leads, what percentage did we correctly identify? High specificity 
                means better filtering of poor leads.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running Evaluations</h2>
          <p className="text-muted-foreground mb-4">
            You can run evaluations in two ways:
          </p>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">1. Using the Dashboard</h3>
              <p className="text-muted-foreground">
                Navigate to your scorecard and click the "Evaluate" button. You can specify:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-2">
                <li>Number of samples to evaluate</li>
                <li>Whether to generate visualizations</li>
                <li>Specific data filters or criteria</li>
              </ul>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">2. Using the CLI</h3>
              <p className="text-muted-foreground mb-4">
                For advanced users, you can use the CLI tool:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`plexus \\
  evaluate \\
  accuracy \\
  --scorecard-name "Lead Qualification" \\
  --number-of-samples 100 \\
  --visualize`}</code>
                </div>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Use at least 100 samples for reliable results</li>
            <li>Include a diverse range of cases in your evaluation dataset</li>
            <li>Run evaluations regularly to monitor performance over time</li>
            <li>Pay attention to both precision and recall - high accuracy alone isn't enough</li>
            <li>Use visualizations to identify patterns in misclassifications</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Advanced Features</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Confusion Matrix</h3>
              <p className="text-muted-foreground mb-4">
                The confusion matrix shows the breakdown of predictions:
              </p>
              <ul className="pl-4 space-y-2 text-muted-foreground">
                <li>True Positives: Correctly identified qualified leads</li>
                <li>False Positives: Unqualified leads mistakenly marked as qualified</li>
                <li>True Negatives: Correctly identified unqualified leads</li>
                <li>False Negatives: Qualified leads mistakenly marked as unqualified</li>
              </ul>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
} 