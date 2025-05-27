import { Metadata } from "next"
import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
import { Gauge, Segment } from "@/components/gauge"
import EvaluationCard from '@/components/EvaluationCard'
import {
  fixedAccuracyGaugeSegments, // Using as general 0-100% segments
  // Data for the \"Always Safe\" Email Filter (Prohibited is Positive Class)
  alwaysSafeEmailAccuracy,
  alwaysSafeEmailGwetAC1,
  alwaysSafeEmailClassDistribution,
  alwaysSafeEmailConfusionMatrix,
  alwaysSafeEmailPredictedDistribution,
} from "@/app/documentation/evaluation-metrics/examples-data"

export const metadata: Metadata = {
  title: "Recall Gauge - Plexus Documentation",
  description: "Understanding the Plexus Recall Gauge (Sensitivity) and its importance in evaluating classifier completeness, especially concerning False Negatives."
}

// Component to display a standalone Recall Gauge for illustration
const RecallGaugeDisplay = ({ value, title }: {
  value: number,
  title: string,
}) => (
  <div className="w-full max-w-[180px] mx-auto">
    <Gauge
      title={title}
      value={value} // Recall is 0-100
      min={0}
      max={100}
      showTicks={true}
      segments={fixedAccuracyGaugeSegments} // Using general 0-100 segments
    />
  </div>
);

// For the "Always Safe" filter, if "Prohibited" is the positive class:
// Actuals: 30 Prohibited, 970 Safe
// Model: Predicts ALL emails as "Safe"
// TP = 0 (Prohibited correctly ID'd as Prohibited)
// FP = 0 (Safe misclassified as Prohibited)
// FN = 30 (Prohibited misclassified as Safe)
// TN = 970 (Safe correctly ID'd as Safe)
const recallForProhibitedInAlwaysSafe = (0 / (0 + 30)) * 100; // 0%
const precisionForProhibitedInAlwaysSafe = 0; // 0 / (0 + 0) which is undefined, typically shown as 0 in this context

export default function RecallGaugePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">The Plexus Recall Gauge</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Recall, also known as Sensitivity or True Positive Rate (TPR), answers the question: <strong>"Of all the items that were actually positive, what proportion did the classifier correctly identify?"</strong> It measures the completeness or comprehensiveness of the classifier in finding all positive instances. A high recall score indicates that the classifier has a low rate of False Negatives (FN).
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Why is Recall Important?</h2>
          <p className="text-muted-foreground mb-4">
            Focusing on recall is critical in scenarios where the cost of a False Negative is high. A False Negative occurs when the model incorrectly predicts a positive instance as negative. Examples include:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>Medical Diagnosis:</strong> Failing to detect a serious disease in a patient who actually has it. This could delay treatment and have severe health consequences.</li>
            <li><strong>Fraud Detection:</strong> Missing a fraudulent transaction, leading to financial loss.</li>
            <li><strong>Safety Systems:</strong> An autonomous vehicle failing to detect an obstacle, or a security system failing to detect an intruder.</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            In these cases, high recall is paramount to ensure as few positive instances as possible are missed, even if it means accepting a higher number of False Positives (lower precision).
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How the Plexus Recall Gauge Works</h2>
          <p className="text-muted-foreground mb-4">
            The Recall Gauge in Plexus displays the calculated recall score, ranging from 0% to 100%. The formula is:
          </p>
          <p className="text-center text-lg font-semibold my-4 p-3 bg-muted rounded-md">
            Recall = True Positives / (True Positives + False Negatives)
          </p>
          <p className="text-muted-foreground mb-6">
            The visual segments on the Recall Gauge generally represent standard performance benchmarks. A recall score of 90% means the classifier successfully identified 90% of all actual positive instances. Like precision, the direct interpretation is straightforward, and the segments visually categorize this performance.
          </p>
          <div className="my-6 p-6 rounded-lg bg-card border flex flex-col items-center">
            <h4 className="text-lg font-semibold mb-4 text-center">Example: Recall Gauge</h4>
            <RecallGaugeDisplay value={75} title="Recall" />
            <p className="text-sm text-muted-foreground mt-3 text-center">
              A recall of 75% indicates that the classifier found 75% of all actual positive instances.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Recall in Action: Example Scenarios</h2>
          <p className="text-muted-foreground mb-4">
            Let's examine recall using our email filter context, where "Prohibited" is the positive class we aim to detect.
          </p>
          
          <div className="mb-8">
            <EvaluationCard
              title="The 'Always Safe' Email Filter (Low Recall Example for 'Prohibited')"
              subtitle="Strategy: Label ALL emails as 'Safe'. Actual Data: 3% Prohibited, 97% Safe."
              classDistributionData={alwaysSafeEmailClassDistribution}
              isBalanced={false}
              accuracy={alwaysSafeEmailAccuracy} // 97%
              gwetAC1={alwaysSafeEmailGwetAC1} // 0.0
              confusionMatrixData={alwaysSafeEmailConfusionMatrix}
              predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
              // EvaluationCard itself doesn\'t show per-class recall directly, so we explain in notes.
              notes={`Recall for 'Prohibited' class: ${recallForProhibitedInAlwaysSafe.toFixed(1)}%. Precision for 'Prohibited': N/A (or 0%). This filter misses ALL prohibited emails, resulting in 0% recall for that critical class, despite its high overall accuracy.`}
            />
          </div>

          <p className="text-muted-foreground mb-4">
            The "Always Safe" filter has 0% recall for the "Prohibited" class. This means it fails to identify any of the prohibited emails. While it achieves 97% accuracy by correctly labeling safe emails, it is useless for its primary task of catching prohibited content due to its catastrophic failure in recall for that class.
          </p>
          
          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Contrast: The Goal of High Recall</h3>
            <p className="text-muted-foreground">
              In critical medical screening (where "Disease Present" is positive), the goal is very high recall. You want to identify as many true cases as possible, even if it means some healthy individuals are flagged for further testing (False Positives, leading to lower precision for the "Disease Present" class).
            </p>
          </div>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Recall and Precision: The Trade-off</h2>
          <p className="text-muted-foreground mb-4">
            Recall and <Link href="/documentation/evaluation-metrics/gauges/precision" className="text-primary hover:underline">Precision</Link> often exhibit an inverse relationship. Increasing recall (e.g., by making a classifier more sensitive to positive cases) can sometimes lead to more False Positives, thereby reducing precision.
          </p>
          <p className="text-muted-foreground mb-4">
            The F1-score is a common metric that combines precision and recall into a single number (the harmonic mean), providing a balanced measure. Choosing whether to prioritize recall, precision, or a balance depends heavily on the specific application and the consequences of different types of errors.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Takeaways for Recall</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Recall (Sensitivity) measures the ability to find all actual positive instances: TP / (TP + FN).</li>
            <li>High recall means a low False Negative rate.</li>
            <li>Crucial when the cost of False Negatives is high.</li>
            <li>The Plexus Recall Gauge displays this score from 0-100%.</li>
            <li>Often considered in conjunction with Precision; the F1-score balances both.</li>
          </ul>
        </section>

        <div className="flex flex-wrap gap-4 mt-12">
          <Link href="/documentation/evaluation-metrics">
            <DocButton variant="outline">Back to Evaluation Metrics Overview</DocButton>
          </Link>
           <Link href="/documentation/evaluation-metrics/gauges/precision">
            <DocButton variant="outline">Learn about the Precision Gauge</DocButton>
          </Link>
          <Link href="/documentation/evaluation-metrics/gauges-with-context">
            <DocButton variant="outline">More on Gauges with Context</DocButton>
          </Link>
        </div>
      </div>
    </div>
  );
} 