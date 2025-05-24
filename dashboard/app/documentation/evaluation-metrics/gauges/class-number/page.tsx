import { Metadata } from "next"
import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
import EvaluationCard from '@/components/EvaluationCard'
import { Gauge, Segment } from "@/components/gauge"
import {
  fixedAccuracyGaugeSegments,
  fairCoinData,
  fairCoinDistribution,
  fairCoinConfusionMatrix,
  predictedFairCoinData,
  dynamicSegments2Class,
  cardSuitData,
  cardSuitActualDistribution,
  cardSuitConfusionMatrix,
  cardSuitPredictedDistribution,
  dynamicSegments4Class,
  dynamicSegments3Class,
  dynamicSegments12Class,
  articleTopicLabelerExampleData,
  articleTopicLabelerClassDistribution,
  articleTopicLabelerConfusionMatrix,
  articleTopicLabelerPredictedDistribution,
  articleTopicLabelerFullContextSegments,
} from "@/app/documentation/evaluation-metrics/examples-data"

export const metadata: Metadata = {
  title: "Interpreting Accuracy with Varying Number of Classes - Plexus Documentation",
  description: "Understanding how the number of classes impacts accuracy interpretation and how Plexus addresses this challenge."
}

// Simplified AccuracyGauge component for this page if needed, or use the main one if it fits.
// For now, let's assume we might want a local one for focused examples.
const AccuracyGaugeDisplay = ({ value, title, segments }: { 
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
)

export default function NumberOfClassesProblemPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">The Challenge: Number of Classes and Accuracy</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Raw accuracy scores can be deceptive. One of the most significant factors affecting how we interpret accuracy is the <strong>number of classes</strong> a classifier is trying to predict. This page focuses specifically on this challenge and how Plexus helps provide clarity.
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Why Number of Classes Matters: A Tale of Two Games</h2>
          <p className="text-muted-foreground mb-4">
            Imagine two guessing games. In the first, you predict a coin flip (2 options: Heads or Tails). In the second, you predict the suit of a drawn card (4 options: Hearts, Diamonds, Clubs, Spades). 
            If you guess randomly in both games, your expected accuracy is vastly different:
          </p>
          <ul className="list-disc pl-6 space-y-1 mb-4 text-muted-foreground">
            <li><strong>Coin Flip (2 Classes):</strong> You have a 1 in 2 chance (50%) of being correct randomly.</li>
            <li><strong>Card Suit (4 Classes):</strong> You have a 1 in 4 chance (25%) of being correct randomly.</li>
          </ul>
          <p className="text-muted-foreground mb-6">
            This simple illustration highlights a core problem: <strong className="text-foreground">a raw accuracy score (e.g., 60%) means very different things depending on the number of classes.</strong> 
            60% accuracy is only slightly better than chance for a coin flip, but significantly better than chance for predicting a card suit.
          </p>

          <div className="grid md:grid-cols-2 gap-6 mb-6">
            <EvaluationCard
              title="Randomly Guessing Coin Flips (2 Classes)"
              subtitle={`Achieved ${fairCoinData.accuracy}% accuracy. Chance baseline: 50%.`}
              classDistributionData={fairCoinDistribution}
              isBalanced={true}
              accuracy={fairCoinData.accuracy}
              confusionMatrixData={fairCoinConfusionMatrix}
              predictedClassDistributionData={predictedFairCoinData}
              variant="oneGauge"
              disableAccuracySegments={false} // Use contextual segments
              accuracyGaugeSegments={dynamicSegments2Class} 
              gaugeDescription={
                <>
                  <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                    <p className="text-sm font-medium text-center">{fairCoinData.accuracy}% accuracy.</p>
                    <p className="text-xs mt-1 text-center">
                      The contextual gauge shows this is near the 50% chance level for 2 classes.
                    </p>
                  </div>
                </>
              }
            />
            <EvaluationCard
              title="Guessing Card Suits (4 Classes)"
              subtitle={`Achieved ${cardSuitData.accuracy}% accuracy. Chance baseline: 25%.`}
              classDistributionData={cardSuitActualDistribution}
              isBalanced={true}
              accuracy={cardSuitData.accuracy} 
              confusionMatrixData={cardSuitConfusionMatrix}
              predictedClassDistributionData={cardSuitPredictedDistribution}
              variant="oneGauge"
              disableAccuracySegments={false} // Use contextual segments
              accuracyGaugeSegments={dynamicSegments4Class}
              gaugeDescription={
                <>
                  <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                    <p className="text-sm font-medium text-center">{cardSuitData.accuracy}% accuracy.</p>
                    <p className="text-xs mt-1 text-center">
                      The contextual gauge shows this is near the 25% chance level for 4 classes.
                    </p>
                  </div>
                </>
              }
            />
          </div>

          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Key Insight: Baseline Shifts with Class Count</h3>
            <p className="text-muted-foreground">
              The random chance baseline drops as the number of classes increases (assuming balanced classes). A 50% accuracy is poor for a 2-class problem but excellent for a 10-class problem (where chance is 10%). Without understanding this shifting baseline, raw accuracy is uninterpretable.
            </p>
          </div>
        </section>

        <section className="my-8 p-6 rounded-lg bg-card">
          <h3 className="text-xl font-semibold mb-6 text-center">Visualizing the Impact: 65% Accuracy Across Different Class Counts</h3>
          <p className="text-sm text-muted-foreground mb-6 text-center">
            Each scenario below shows a 65% accuracy. The left gauge uses a fixed, uncontextualized scale. The right gauge dynamically adjusts its colored segments based on the number of classes (assuming a balanced distribution for this illustration), providing immediate context.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
            <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
              <h4 className="text-md font-medium text-center">Two-Class</h4>
              <AccuracyGaugeDisplay value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
              <AccuracyGaugeDisplay value={65.0} title="With Class Context" segments={dynamicSegments2Class} />
              <p className="text-xs text-muted-foreground text-center pt-2">Contextual: 65% is 'converging', just above the 50% chance.</p>
            </div>
            <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
              <h4 className="text-md font-medium text-center">Three-Class</h4>
              <AccuracyGaugeDisplay value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
              <AccuracyGaugeDisplay value={65.0} title="With Class Context" segments={dynamicSegments3Class} />
              <p className="text-xs text-muted-foreground text-center pt-2">Contextual: 65% is 'viable', well above the ~33% chance.</p>
            </div>
            <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
              <h4 className="text-md font-medium text-center">Four-Class</h4>
              <AccuracyGaugeDisplay value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
              <AccuracyGaugeDisplay value={65.0} title="With Class Context" segments={dynamicSegments4Class} />
              <p className="text-xs text-muted-foreground text-center pt-2">Contextual: 65% is 'great', significantly above the 25% chance.</p>
            </div>
            <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
              <h4 className="text-md font-medium text-center">Twelve-Class</h4>
              <AccuracyGaugeDisplay value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
              <AccuracyGaugeDisplay value={65.0} title="With Class Context" segments={dynamicSegments12Class} />
              <p className="text-xs text-muted-foreground text-center pt-2">Contextual: 65% is outstanding, far exceeding the ~8.3% chance.</p>
            </div>
          </div>
          <div className="mt-6 p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
            <h4 className="text-lg font-semibold mb-2">The Takeaway</h4>
            <p className="text-muted-foreground">
              The same 65% accuracy score transitions from mediocre to excellent as the number of classes increases. Fixed gauges are misleading. Contextual gauges, which adapt to the number of classes, are essential for correct interpretation.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Solution: Clarity Through Context</h2>
          <p className="text-muted-foreground mb-4">
            To address the challenge of varying class numbers, a two-pronged approach provides a clear and reliable understanding of classifier performance. This ensures metrics are interpretable whether dealing with few or many classes, or situations involving class imbalance (a related challenge discussed elsewhere).
          </p>
          <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
            <li>
              <strong className="text-foreground">Contextualized Accuracy Gauges:</strong> As demonstrated previously, Accuracy gauges should not use a fixed scale. Their colored segments dynamically adjust based on problem characteristics like the number of classes (and class distribution). This provides an immediate visual cue: is the observed accuracy good *for this specific problem*?
            </li>
            <li>
              <strong className="text-foreground">Inherently Context-Aware Agreement Gauges:</strong> Alongside accuracy, Agreement gauges (typically Gwet's AC1) offer a mathematically robust solution. These metrics are designed to calculate a chance-corrected measure of agreement. They *internally* account for the number of classes and their distribution, yielding a standardized score (0 = chance, 1 = perfect) that reflects skill beyond random guessing. This score is directly comparable across different problems.
            </li>
          </ol>
          <p className="text-muted-foreground mb-6">
            The contextualized Accuracy gauge helps interpret raw accuracy correctly for the current task, while the Agreement gauge provides a robust, comparable measure of skill. Let's examine how these two gauges work together:
          </p>

          <div className="space-y-8">
            <EvaluationCard
              title="Two-Class (Coin Flip) - Near Chance Performance"
              subtitle="Random guessing on 100 coin flips. Expect ~50% accuracy, ~0.0 AC1."
              classDistributionData={fairCoinDistribution}
              isBalanced={true}
              accuracy={fairCoinData.accuracy}
              gwetAC1={fairCoinData.ac1}
              confusionMatrixData={fairCoinConfusionMatrix}
              predictedClassDistributionData={predictedFairCoinData}
              showBothGauges={true}
              variant="default" 
              accuracyGaugeSegments={dynamicSegments2Class} 
              notes="Here, both gauges clearly indicate performance at (or slightly below) random chance. The Agreement (AC1) is near zero. The contextualized Accuracy gauge shows 48% is at the baseline for a 2-class problem."
            />

            <EvaluationCard
              title="Multi-Class (Article Topic Labeler) - Moderate Performance"
              subtitle="5-class imbalanced problem. Accuracy: 62%, Gwet's AC1: 0.512."
              classDistributionData={articleTopicLabelerClassDistribution}
              isBalanced={false} // Data is imbalanced
              accuracy={articleTopicLabelerExampleData.accuracy}
              gwetAC1={articleTopicLabelerExampleData.gwetAC1}
              confusionMatrixData={articleTopicLabelerConfusionMatrix}
              predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
              showBothGauges={true}
              variant="default"
              accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
              notes="For this more complex 5-class imbalanced task, the Agreement gauge (AC1=0.512) shows moderate skill beyond chance. The contextualized Accuracy gauge interprets 62% as 'good' for this specific setup, confirming a performance level that's meaningfully above simple guessing strategies."
            />
          </div>
          <p className="text-muted-foreground mt-6 mb-4">
            These examples illustrate how combining a contextualized Accuracy gauge with an Agreement score like Gwet's AC1 offers a much clearer and more reliable assessment of classifier performance than looking at raw accuracy in isolation, especially when the number of classes varies.
          </p>
        </section>
      </div>

      <div className="mt-12 p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
        <h3 className="text-lg font-semibold mb-2">For a Comprehensive Overview</h3>
        <p className="text-muted-foreground mb-3">
          This page focuses specifically on the "number of classes" problem. For a broader understanding of how Plexus addresses various contextual factors in evaluation (including class imbalance and the full two-pronged solution strategy), please see our main guide:
        </p>
        <Link href="/documentation/evaluation-metrics/gauges-with-context">
          <DocButton>Understanding Gauges with Context</DocButton>
        </Link>
      </div>

      <section className="mt-10">
        <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
        <p className="text-muted-foreground mb-4">
          Continue exploring our documentation for a deeper understanding of evaluation:
        </p>
        <div className="flex flex-wrap gap-4">
          <Link href="/documentation/evaluation-metrics">
            <DocButton variant="outline">Evaluation Metrics Overview</DocButton>
          </Link>
          <Link href="/documentation/evaluation-metrics/gauges-with-context">
            <DocButton variant="outline">Detailed: Gauges with Context</DocButton>
          </Link>
          <Link href="/documentation/evaluation-metrics/examples">
            <DocButton>View More Metric Examples</DocButton>
          </Link>
        </div>
      </section>
    </div>
  );
} 