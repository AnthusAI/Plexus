import { Metadata } from "next"
import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
import { Gauge, Segment } from "@/components/gauge"
import EvaluationCard from '@/components/EvaluationCard'
import {
  fixedAccuracyGaugeSegments, // Using as general 0-100% segments
  // Data for the \"Always Prohibited\" example (newly defined for this page)
  // We also need data for the \"Always Safe\" filter for context or comparison if desired
  alwaysSafeEmailAccuracy, // Though not directly used, implies the dataset
  alwaysSafeEmailGwetAC1,
  alwaysSafeEmailClassDistribution,
  alwaysSafeEmailConfusionMatrix, // Will be for 'Always Safe', need to derive for 'Always Prohibited'
  alwaysSafeEmailPredictedDistribution,
}
 from "@/app/documentation/evaluation-metrics/examples-data"

export const metadata: Metadata = {
  title: "Precision Gauge - Plexus Documentation",
  description: "Understanding the Plexus Precision Gauge and its role in evaluating classifier performance, especially concerning False Positives."
}

// Component to display a standalone Precision Gauge for illustration
const PrecisionGaugeDisplay = ({ value, title }: {
  value: number,
  title: string,
}) => (
  <div className="w-full max-w-[180px] mx-auto">
    <Gauge
      title={title}
      value={value} // Precision is 0-100
      min={0}
      max={100}
      showTicks={true}
      segments={fixedAccuracyGaugeSegments} // Using general 0-100 segments
    />
  </div>
);

// Data for the "Always Prohibited" Email Filter example (Prohibited is Positive Class)
// Actuals: 30 Prohibited, 970 Safe
// Model: Predicts ALL emails as "Prohibited"
const alwaysProhibitedEmailData = {
  id: 'always-prohibited-filter',
  score_name: "'Always Prohibited' Email Filter Performance",
  accuracy: 3.0, // (30 TP + 0 TN) / 1000 = 3%
  item_count: 1000,
  // For "Prohibited" as positive:
  // TP = 30 (correctly ID'd Prohibited)
  // FP = 970 (Safe misclassified as Prohibited)
  // FN = 0 (Prohibited misclassified as Safe)
  // TN = 0 (Safe correctly ID'd as Safe)
  precision: (30 / (30 + 970)) * 100, // 30 / 1000 = 3%
  recall: (30 / (30 + 0)) * 100,      // 30 / 30 = 100%
  gwetAC1: -0.027, // Example AC1, would likely be poor
  label_distribution: { 'Prohibited': 30, 'Safe': 970 },
  classDistributionData: alwaysSafeEmailClassDistribution, // Actual distribution is the same
  confusionMatrixData: {
    labels: ["Prohibited", "Safe"],
    matrix: [
      { actualClassLabel: "Prohibited", predictedClassCounts: { "Prohibited": 30, "Safe": 0 } },
      { actualClassLabel: "Safe", predictedClassCounts: { "Prohibited": 970, "Safe": 0 } },
    ],
  },
  predictedClassDistributionData: [{label: "Prohibited", count: 1000}, {label: "Safe", count: 0}],
};

export default function PrecisionGaugePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">The Plexus Precision Gauge</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Precision is a key metric that answers the question: <strong>"Of all the items the classifier labeled as positive, what proportion were actually positive?"</strong> It measures the exactness or correctness of the positive predictions. A high precision score indicates that the classifier has a low rate of False Positives (FP).
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Why is Precision Important?</h2>
          <p className="text-muted-foreground mb-4">
            Focusing on precision is crucial in scenarios where the cost of a False Positive is high. A False Positive occurs when the model incorrectly predicts a negative instance as positive. Examples include:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>Spam Detection:</strong> Marking a legitimate email (ham) as spam. This could lead to users missing important communications.</li>
            <li><strong>Fraud Detection:</strong> Incorrectly flagging a legitimate transaction as fraudulent, causing inconvenience and potential loss of trust for the user.</li>
            <li><strong>Content Moderation:</strong> Wrongfully removing or flagging appropriate content as inappropriate, leading to censorship concerns or user frustration.</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            In these cases, high precision is desired to minimize these costly errors, even if it means some positive instances might be missed (lower recall).
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How the Plexus Precision Gauge Works</h2>
          <p className="text-muted-foreground mb-4">
            The Precision Gauge in Plexus displays the calculated precision score, ranging from 0% to 100%. The formula is:
          </p>
          <p className="text-center text-lg font-semibold my-4 p-3 bg-muted rounded-md">
            Precision = True Positives / (True Positives + False Positives)
          </p>
          <p className="text-muted-foreground mb-6">
            The visual segments on the Precision Gauge (e.g., colors indicating performance levels) typically represent general benchmarks of performance. A precision score of 90% is generally understood as meaning 9 out of 10 items flagged as positive by the model were indeed positive. While extreme class imbalance can make achieving high precision challenging, the interpretation of the precision score itself is fairly direct. The segments help visually categorize this performance (e.g., poor, fair, good, excellent).
          </p>
          <div className="my-6 p-6 rounded-lg bg-card border flex flex-col items-center">
            <h4 className="text-lg font-semibold mb-4 text-center">Example: Precision Gauge</h4>
            <PrecisionGaugeDisplay value={85} title="Precision" />
            <p className="text-sm text-muted-foreground mt-3 text-center">
              A precision of 85% indicates that 85% of the items predicted as positive were actually positive.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Precision in Action: Example Scenarios</h2>
          <p className="text-muted-foreground mb-4">
            Let's look at how precision plays out in different scenarios using our email filter context, where "Prohibited" is the positive class we want to detect.
          </p>
          
          <div className="mb-8">
            <EvaluationCard
              title="The 'Always Prohibited' Email Filter (Low Precision Example)"
              subtitle="Strategy: Label ALL emails as 'Prohibited'. Actual Data: 3% Prohibited, 97% Safe."
              classDistributionData={alwaysProhibitedEmailData.classDistributionData}
              isBalanced={false}
              accuracy={alwaysProhibitedEmailData.accuracy}
              // To show precision, we would need a way to pass it to EvaluationCard or use a custom display
              // For now, we are explaining it in notes.
              // precision={alwaysProhibitedEmailData.precision}
              // recall={alwaysProhibitedEmailData.recall}
              confusionMatrixData={alwaysProhibitedEmailData.confusionMatrixData}
              predictedClassDistributionData={alwaysProhibitedEmailData.predictedClassDistributionData}
              gwetAC1={alwaysProhibitedEmailData.gwetAC1} // Showing AC1 for context
              notes={`Precision for 'Prohibited' class: ${alwaysProhibitedEmailData.precision.toFixed(1)}%. Recall: ${alwaysProhibitedEmailData.recall.toFixed(1)}%. While recall is perfect (it catches all prohibited emails), precision is extremely low. 97% of emails it flags as 'Prohibited' are actually 'Safe', leading to a flood of False Positives.`}
            />
          </div>

          <p className="text-muted-foreground mb-4">
            The "Always Prohibited" filter has a precision of only 3%. This means that for every 100 emails it flags as prohibited, 97 of them are actually safe. This would be unusable in practice due to the overwhelming number of false alarms, despite its perfect recall for the prohibited class.
          </p>
          
          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Contrast: The Goal of High Precision</h3>
            <p className="text-muted-foreground">
              In a good spam filter (where "Spam" is the positive class), the goal would be very high precision. You want to be very sure that if an email is marked as Spam, it truly is Spam. This minimizes the chance of important, non-spam emails being lost.
            </p>
          </div>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Precision and Recall: The Trade-off</h2>
          <p className="text-muted-foreground mb-4">
            Precision and <Link href="/documentation/evaluation-metrics/gauges/recall" className="text-primary hover:underline">Recall</Link> often have an inverse relationship. Improving one can sometimes lead to a decrease in the other. For example, if you make a classifier more aggressive in identifying positive instances (to increase recall), it might start making more mistakes on negative instances, thus lowering precision.
          </p>
          <p className="text-muted-foreground mb-4">
            Understanding this trade-off is key. The choice of whether to optimize for precision or recall (or a balance like the F1-score) depends on the specific problem and the relative costs of False Positives versus False Negatives.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Takeaways for Precision</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Precision measures the accuracy of positive predictions: TP / (TP + FP).</li>
            <li>High precision means a low False Positive rate.</li>
            <li>Crucial when the cost of False Positives is high.</li>
            <li>The Plexus Precision Gauge displays this score from 0-100%.</li>
            <li>Often considered in conjunction with Recall due to their trade-off.</li>
          </ul>
        </section>

        <div className="flex flex-wrap gap-4 mt-12">
          <Link href="/documentation/evaluation-metrics">
            <DocButton variant="outline">Back to Evaluation Metrics Overview</DocButton>
          </Link>
           <Link href="/documentation/evaluation-metrics/gauges/recall">
            <DocButton variant="outline">Learn about the Recall Gauge</DocButton>
          </Link>
          <Link href="/documentation/evaluation-metrics/gauges-with-context">
            <DocButton variant="outline">More on Gauges with Context</DocButton>
          </Link>
        </div>
      </div>
    </div>
  );
} 