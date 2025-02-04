'use client';

export default function EvaluationsPage() {
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
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running an Evaluation</h2>
          <p className="text-muted-foreground mb-4">
            To evaluate a scorecard's accuracy, use the <code>evaluate accuracy</code> command:
          </p>
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`plexus \\
  evaluate \\
  accuracy \\
  --scorecard-name "Inbound Leads" \\
  --number-of-samples 100 \\
  --visualize`}</code>
            </div>
          </pre>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Key Parameters</h3>
              <ul className="pl-4 space-y-2 text-muted-foreground">
                <li><code>--scorecard-name</code>: The name of your scorecard (e.g., "Inbound Leads")</li>
                <li><code>--number-of-samples</code>: How many samples to evaluate (recommended: 100 or more)</li>
                <li><code>--visualize</code>: Generate visual reports of the results</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">What to Expect</h3>
              <p className="text-muted-foreground">
                The evaluation process will:
              </p>
              <ul className="pl-4 space-y-2 text-muted-foreground">
                <li>Run your scorecard against the specified number of labeled samples</li>
                <li>Calculate accuracy metrics (precision, recall, specificity)</li>
                <li>Generate a confusion matrix when visualization is enabled</li>
                <li>Store the results for future reference</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Results</h2>
          <p className="text-muted-foreground mb-4">
            After running an evaluation, you can view the results:
          </p>
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`# List all evaluations
plexus \\
  evaluations \\
  list

# View detailed results
plexus \\
  evaluations \\
  list-results \\
  evaluation-id \\
  --limit 100`}</code>
            </div>
          </pre>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Key Metrics</h3>
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
                When you enable visualization, you'll get a confusion matrix showing the breakdown of predictions:
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