import { Metadata } from "next"
import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
// It might be useful to add a simple visual example if desired,
// but for now, we'll focus on textual explanation and links.
// import { Gauge, Segment } from "@/components/gauge"
// import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import { Gauge, Segment } from "@/components/gauge"
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import EvaluationCard from '@/components/EvaluationCard'
import {
  fixedAccuracyGaugeSegments,
  alwaysSafeEmailAccuracy,
  alwaysSafeEmailClassDistribution,
  alwaysSafeEmailConfusionMatrix,
  alwaysSafeEmailPredictedDistribution
} from "@/app/documentation/evaluation-metrics/examples-data"

export const metadata: Metadata = {
  title: "Accuracy Gauge - Plexus Documentation",
  description: "Understanding the Plexus Accuracy gauge and how its dynamic contextualization aids in interpreting classification performance."
}

// Example segments if we decide to add a simple visual:
// const fixedAccuracyGaugeSegments: Segment[] = [
//   { start: 0, end: 50, color: 'var(--gauge-inviable)' },
//   { start: 50, end: 70, color: 'var(--gauge-converging)' },
//   { start: 70, end: 80, color: 'var(--gauge-almost)' },
//   { start: 80, end: 90, color: 'var(--gauge-viable)' },
//   { start: 90, end: 100, color: 'var(--gauge-great)' },
// ];

// Added AccuracyGauge component definition
const AccuracyGauge = ({ value, title, segments }: {
  value: number,
  title: string,
  segments?: Segment[]
}) => (
  <div className="w-full max-w-[180px] mx-auto">
    <Gauge
      title={title}
      value={value}
      showTicks={true}
      segments={segments}
    />
  </div>
);

// Added segment definitions
// const fixedAccuracyGaugeSegments: Segment[] = [
//   { start: 0, end: 50, color: \'var(--gauge-inviable)\' },
//   { start: 50, end: 70, color: \'var(--gauge-converging)\' },
//   { start: 70, end: 80, color: \'var(--gauge-almost)\' },
//   { start: 80, end: 90, color: \'var(--gauge-viable)\' },
//   { start: 90, end: 100, color: \'var(--gauge-great)\' },
// ];

export default function AccuracyGaugePage() {
  // Added segment calculations for class number visualization
  const thresholds2Class = GaugeThresholdComputer.computeThresholds({ C1: 1, C2: 1}); // Simplified for example
  const dynamicSegments2Class = GaugeThresholdComputer.createSegments(thresholds2Class);

  const label_distribution_3_class = { C1: 1, C2: 1, C3: 1 };
  const thresholds3Class = GaugeThresholdComputer.computeThresholds(label_distribution_3_class);
  const dynamicSegments3Class = GaugeThresholdComputer.createSegments(thresholds3Class);

  const label_distribution_4_class = { C1: 1, C2: 1, C3: 1, C4: 1 }; // Simplified for example
  const thresholds4Class = GaugeThresholdComputer.computeThresholds(label_distribution_4_class);
  const dynamicSegments4Class = GaugeThresholdComputer.createSegments(thresholds4Class);

  const label_distribution_12_class: Record<string, number> = {};
  for (let i = 1; i <= 12; i++) {
    label_distribution_12_class[`Class ${i}`] = 1;
  }
  const thresholds12Class = GaugeThresholdComputer.computeThresholds(label_distribution_12_class);
  const dynamicSegments12Class = GaugeThresholdComputer.createSegments(thresholds12Class);

  // Added segment calculations for class imbalance visualization
  const imbal_scenario1_dist = { C1: 50, C2: 50 }; // Balanced
  const imbal_scenario1_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario1_dist);
  const imbal_scenario1_segments = GaugeThresholdComputer.createSegments(imbal_scenario1_thresholds);

  const imbal_scenario2_dist = { C1: 75, C2: 25 }; // Imbalanced
  const imbal_scenario2_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario2_dist);
  const imbal_scenario2_segments = GaugeThresholdComputer.createSegments(imbal_scenario2_thresholds);
  
  const imbal_scenario3_dist = { C1: 95, C2: 5 }; // Highly Imbalanced
  const imbal_scenario3_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario3_dist);
  const imbal_scenario3_segments = GaugeThresholdComputer.createSegments(imbal_scenario3_thresholds);

  const imbal_scenario4_dist = { C1: 80, C2: 10, C3: 10 }; // 3-Class Imbalanced
  const imbal_scenario4_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario4_dist);
  const imbal_scenario4_segments = GaugeThresholdComputer.createSegments(imbal_scenario4_thresholds);

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">The Plexus Accuracy Gauge</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Accuracy is a fundamental metric in classification, representing the proportion of correct predictions made by a model. While seemingly straightforward, interpreting raw accuracy figures can be challenging. The Plexus Accuracy Gauge is designed to provide a more nuanced and reliable understanding of your classifier's performance by incorporating crucial contextual information directly into its visual representation.
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Why Raw Accuracy Can Be Misleading</h2>
          <p className="text-muted-foreground mb-4">
            A raw accuracy score, such as "75% accurate," can be deceptive if viewed in isolation. Several factors can significantly influence its interpretation:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li>
              <strong className="text-foreground">Number of Classes:</strong> The baseline for random chance agreement changes dramatically with the number of possible outcomes. An accuracy of 50% is no better than random guessing for a binary (2-class) problem, but it would be excellent for a 10-class problem where random chance is 10%.
            </li>
            <li>
              <strong className="text-foreground">Class Imbalance:</strong> If the dataset has an uneven distribution of classes (e.g., 90% of samples belong to Class A and 10% to Class B), a model can achieve high accuracy simply by always predicting the majority class. This high accuracy score wouldn't reflect true predictive skill for the minority class.
            </li>
          </ul>
          <p className="text-muted-foreground mb-4">
            These factors mean that the same accuracy percentage can represent very different levels of performance depending on the specific characteristics of the classification task.
          </p>
          <div className="p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
            <h3 className="text-lg font-semibold mb-2">Learn More About These Challenges</h3>
            <p className="text-muted-foreground mb-3">
              For a comprehensive discussion on the pitfalls of interpreting raw metrics and how Plexus approaches these challenges, please see:
            </p>
            <Link href="/documentation/evaluation-metrics">
              <DocButton>Interpreting Evaluation Metrics</DocButton>
            </Link>
          </div>

          {/* Added "Always Safe" Email Filter Example */}
          <div className="my-6">
            <EvaluationCard
              title="Example: The 'Always Safe' Email Filter (97% Safe, 3% Prohibited)"
              subtitle="Strategy: Label ALL emails as 'Safe'. Actual Data: 970 Safe, 30 Prohibited."
              classDistributionData={alwaysSafeEmailClassDistribution}
              isBalanced={false}
              accuracy={alwaysSafeEmailAccuracy}
              confusionMatrixData={alwaysSafeEmailConfusionMatrix}
              predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <>
                  <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                    <p className="text-sm font-medium text-center">Raw Accuracy: {alwaysSafeEmailAccuracy}% !</p>
                  </div>
                  <div className="mt-3 p-2 bg-destructive rounded-md">
                    <p className="text-sm font-bold text-white text-center">Highly Misleading!</p>
                    <p className="text-xs mt-1 text-white text-center">
                      This 97% accuracy is achieved by a filter that detects ZERO prohibited emails. It only seems accurate because it correctly labels the 97% majority "Safe" class, completely failing its actual purpose.
                    </p>
                  </div>
                </>
              }
            />
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How the Plexus Accuracy Gauge Adds Clarity</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus Accuracy Gauge addresses these interpretation challenges by dynamically contextualizing its visual scale. The colored segments (e.g., indicating 'poor', 'fair', 'good', 'excellent') are not fixed; they adjust based on the specific context of your evaluation:
          </p>
          <ul className="list-disc pl-6 space-y-3 text-muted-foreground mb-4">
            <li>
              <strong className="text-foreground">Adjustment for Number of Classes:</strong> The gauge calculates a baseline performance level expected from random guessing given the number of classes in your problem (assuming a balanced distribution for this part of the calculation). The segments then shift to reflect whether the achieved accuracy is meaningfully above this baseline.
            </li>
            <li>
              <strong className="text-foreground">Adjustment for Class Imbalance:</strong> The gauge further refines its scale by considering the actual distribution of classes in your data. It identifies the performance level achievable by naive strategies (like always predicting the majority class). The segments adjust so that "good" or "excellent" performance truly represents skill beyond these naive baselines.
            </li>
          </ul>
          <p className="text-muted-foreground mb-4">
            By visually encoding this context, the Plexus Accuracy Gauge helps you quickly understand whether an observed accuracy score is genuinely good, merely acceptable, or poor for your specific dataset and classification task. It aims to turn a simple percentage into a more insightful measure of performance.
          </p>
          
          {/* Added Class Number Visualization */}
          <div className="my-8 p-6 rounded-lg bg-card border">
            <h4 className="text-lg font-semibold mb-6 text-center">Visualizing Context: Impact of Number of Classes (65% Accuracy Example)</h4>
            <p className="text-sm text-muted-foreground mb-4 text-center">
              Each scenario below shows a 65% accuracy. The top gauge has no context (fixed scale), while the bottom gauge adjusts its segments based on the number of classes (assuming balanced distribution for this visualization).
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Two-Class</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={dynamicSegments2Class} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Three-Class</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={dynamicSegments3Class} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Four-Class</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={dynamicSegments4Class} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Twelve-Class</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={dynamicSegments12Class} />
              </div>
            </div>
             <p className="text-xs text-muted-foreground mt-4 text-center">
              Observe how 65% accuracy appears increasingly strong as the number of classes (and thus the difficulty of random guessing) increases, when viewed on a contextual scale.
            </p>
          </div>

          {/* Added Class Imbalance Visualization */}
          <div className="my-8 p-6 rounded-lg bg-card border">
            <h4 className="text-lg font-semibold mb-6 text-center">Visualizing Context: Impact of Class Imbalance (65% Accuracy Example)</h4>
            <p className="text-sm text-muted-foreground mb-4 text-center">
              Each scenario below again shows 65% accuracy on a binary task. The top gauge uses fixed segments. The bottom gauge adjusts segments based on the specified class imbalance, showing how the baseline for "no skill" (e.g., always guessing majority) shifts.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Balanced (50/50)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario1_segments} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Imbalanced (75/25)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario2_segments} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">3-Class Imbal. (80/10/10)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario4_segments} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Highly Imbal. (95/5)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario3_segments} />
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-4 text-center">
              Notice how 65% accuracy, which looks 'converging' on a fixed scale, can appear poor or merely chance-level on a contextual scale if the imbalance is such that always guessing the majority class would yield a similar or higher score.
            </p>
          </div>
          
          <div className="p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
            <h3 className="text-lg font-semibold mb-2">Detailed Mechanics and Combined Strategy</h3>
            <p className="text-muted-foreground mb-3">
              To explore the detailed mechanics of how these contextual thresholds are computed and how the Accuracy gauge works in tandem with the Agreement gauge (like Gwet's AC1) for a complete picture, visit:
            </p>
            <Link href="/documentation/evaluation-metrics/gauges-with-context">
              <DocButton>Understanding Gauges with Context</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Takeaways</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>The Plexus Accuracy Gauge displays the percentage of correct predictions.</li>
            <li>Its visual scale (colors and thresholds) is <strong className="text-foreground">dynamically adjusted</strong> to account for the number of classes and class imbalance in your specific dataset.</li>
            <li>This contextualization provides a more intuitive and reliable interpretation of whether an accuracy score is truly good for your particular problem.</li>
            <li>It is best understood alongside the Agreement gauge for a complete performance picture.</li>
          </ul>
        </section>

        <div className="flex flex-wrap gap-4 mt-12">
          <Link href="/documentation/evaluation-metrics">
            <DocButton variant="outline">Back to Evaluation Metrics Overview</DocButton>
          </Link>
        </div>
      </div>
    </div>
  );
} 