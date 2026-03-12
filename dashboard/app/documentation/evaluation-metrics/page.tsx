import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import EvaluationCard from '@/components/EvaluationCard'
import { Segment } from "@/components/gauge"

export const metadata: Metadata = {
  title: "Interpreting Evaluation Metrics - Plexus Documentation",
  description: "Understanding the challenges of interpreting classifier accuracy and an overview of Plexus solutions."
}

// Helper function to create sample score data for examples
const createExampleScore = (
  id: string,
  name: string,
  ac1: number,
  accuracy: number,
  itemCount: number,
  mismatches: number,
  labelDistribution?: Record<string, number>
) => ({
  id,
  score_name: name,
  cc_question_id: `example-${id}`,
  ac1,
  item_count: itemCount,
  mismatches,
  accuracy,
  label_distribution: labelDistribution
})

// Define fixed segments for the illustrative accuracy gauges in the initial scenarios (kept for initial coin flip examples if those are retained in narrative)
const fixedAccuracyGaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },
  { start: 50, end: 70, color: 'var(--gauge-converging)' },
  { start: 70, end: 80, color: 'var(--gauge-almost)' },
  { start: 80, end: 90, color: 'var(--gauge-viable)' },
  { start: 90, end: 100, color: 'var(--gauge-great)' },
];

export default function EvaluationMetricsPage() {
  // Article Topic Labeler - Our consistent example through the document
  const articleTopicLabelerExampleData = {
    id: 'article-topic-labeler',
    score_name: 'Article Topic Labeler Performance',
    cc_question_id: 'example-topic-labeler',
    accuracy: 62.0,
    item_count: 100,
    mismatches: 38, // 100 - 62
    gwetAC1: 0.512, // Lower AC1 reflecting 62% accuracy
    label_distribution: { 
      'News': 40, 
      'Sports': 15, 
      'Business': 15, 
      'Technology': 15, 
      'Lifestyle': 15 
    }
  };

  const articleTopicLabelerClassDistribution = [
    { label: "News", count: 40 },
    { label: "Sports", count: 15 },
    { label: "Business", count: 15 },
    { label: "Technology", count: 15 },
    { label: "Lifestyle", count: 15 }
  ];

  const articleTopicLabelerConfusionMatrix = {
    labels: ["News", "Sports", "Business", "Technology", "Lifestyle"],
    matrix: [
      { actualClassLabel: "News", predictedClassCounts: { "News": 28, "Sports": 3, "Business": 3, "Technology": 3, "Lifestyle": 3 } },
      { actualClassLabel: "Sports", predictedClassCounts: { "News": 3, "Sports": 9, "Business": 1, "Technology": 1, "Lifestyle": 1 } },
      { actualClassLabel: "Business", predictedClassCounts: { "News": 3, "Sports": 1, "Business": 8, "Technology": 2, "Lifestyle": 1 } },
      { actualClassLabel: "Technology", predictedClassCounts: { "News": 3, "Sports": 1, "Business": 2, "Technology": 8, "Lifestyle": 1 } },
      { actualClassLabel: "Lifestyle", predictedClassCounts: { "News": 3, "Sports": 1, "Business": 1, "Technology": 1, "Lifestyle": 9 } },
    ],
  };

  const articleTopicLabelerPredictedDistribution = [
    { label: "News", count: 40 }, 
    { label: "Sports", count: 15 },
    { label: "Business", count: 15 },
    { label: "Technology", count: 15 },
    { label: "Lifestyle", count: 15 }
  ];
  
  // Segments for the final Article Topic Labeler example (fully contextualized)
  const articleTopicLabelerFullContextSegments = GaugeThresholdComputer.createSegments(
    GaugeThresholdComputer.computeThresholds(articleTopicLabelerExampleData.label_distribution)
  );
  
  // Coin flip examples for the narrative
  const fairCoinData = createExampleScore(
    'fair-coin',
    'Randomly Guessing Coin Flips (50/50)',
    -0.04, 
    48.0, 
    100,  
    52,   
    { 'Heads': 50, 'Tails': 50 }
  )
  
  const alwaysHeadsData = createExampleScore(
    'always-heads',
    'Always Guessing "Heads" (50/50)',
    0.02, 
    51.0,
    100,
    49, 
    { 'Heads': 51, 'Tails': 49 }
  )

  const fairCoinDistribution = [
    { label: "Heads", count: 51 },
    { label: "Tails", count: 49 }
  ];
  
  const predictedFairCoinData = [
    { label: "Heads", count: 50 },
    { label: "Tails", count: 50 }
  ];

  const predictedAlwaysHeadsData = [
    { label: "Heads", count: 100 },
    { label: "Tails", count: 0 }
  ];

  const fairCoinConfusionMatrix = {
    labels: ["Heads", "Tails"],
    matrix: [
      { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 24, "Tails": 26 } },
      { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 26, "Tails": 24 } },
    ],
  };
  
  const alwaysHeadsConfusionMatrix = {
    labels: ["Heads", "Tails"],
    matrix: [
      { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 51, "Tails": 0 } },
      { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 49, "Tails": 0 } },
    ],
  };

  // Card Suit Guessing Example Data for narrative
  const cardSuitData = createExampleScore(
    'card-suit-guessing',
    'Predicting a Card Suit (4 Classes, Random Guessing)',
    -0.03, 
    23.0, 
    208,  
    160,  
    { '♥️': 52, '♦️': 52, '♣️': 52, '♠️': 52 }
  );

  const cardSuitActualDistribution = [
    { label: "♥️", count: 52 }, 
    { label: "♦️", count: 52 },
    { label: "♣️", count: 52 },
    { label: "♠️", count: 52 }
  ];

  const cardSuitConfusionMatrix = {
    labels: ["♥️", "♦️", "♣️", "♠️"],
    matrix: [
      { actualClassLabel: "♥️", predictedClassCounts: { "♥️": 12, "♦️": 13, "♣️": 13, "♠️": 14 } },
      { actualClassLabel: "♦️", predictedClassCounts: { "♥️": 13, "♦️": 12, "♣️": 14, "♠️": 13 } },
      { actualClassLabel: "♣️", predictedClassCounts: { "♥️": 13, "♦️": 14, "♣️": 12, "♠️": 13 } },
      { actualClassLabel: "♠️", predictedClassCounts: { "♥️": 14, "♦️": 13, "♣️": 13, "♠️": 12 } },
    ],
  };
  
  const cardSuitPredictedDistribution = [ 
    { label: "♥️", count: 12+13+13+14 },
    { label: "♦️", count: 13+12+14+13 },
    { label: "♣️", count: 13+14+12+13 },
    { label: "♠️", count: 14+13+13+12 }
  ];

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Interpreting Evaluation Metrics: The Challenge</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understanding metrics like accuracy is key to evaluating AI performance. However, raw numbers can be deceptive without proper context. This page explores common pitfalls and introduces Plexus's approach to clearer, more reliable evaluation.
      </p>

      <div className="space-y-10">
        <section className="mb-10">
          <h2 className="text-2xl font-semibold mb-4">The Big Question: Is This Classifier Good?</h2>
          <p className="text-muted-foreground mb-4">
            When developing an AI system, we need gauges to tell if our model is performing well. Let's consider an "Article Topic Labeler" that classifies articles into five categories: News, Sports, Business, Technology, and Lifestyle. Evaluated on 100 articles, it achieves 62% accuracy.
          </p>

          <EvaluationCard
            title="Article Topic Labeler (Initial View)"
            subtitle="Classifies articles into 5 categories. Accuracy: 62%."
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            variant="oneGauge"
            disableAccuracySegments={true} 
            gaugeDescription={
                <>
                  <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-4 border-l-4 border-violet-500">
                    <p className="text-sm font-medium">Is 62% accuracy good?</p>
                    <p className="text-sm mt-2">
                      This number seems mediocre. The uncontextualized gauge suggests it's just 'converging'. But is this poor performance, or is there more to the story?
                    </p>
                  </div>
                </>
              }
          />
          
          <p className="text-muted-foreground mt-4 mb-4">
            Intuitively, 62% seems somewhat weak—nearly 4 out of 10 articles are wrong. But to judge this, we need a baseline: what accuracy would random guessing achieve?
          </p>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Pitfall 1: Ignoring the Baseline (Chance Agreement)</h2>
          <p className="text-muted-foreground mb-4">
            Raw accuracy is meaningless without knowing the chance agreement rate. Consider predicting 100 coin flips:
          </p>
          
          <div className="grid md:grid-cols-2 gap-6 mb-6">
            <EvaluationCard
              title="Randomly Guessing Coin Flips"
              subtitle="100 fair coin flips (50/50). Random guesses."
              classDistributionData={fairCoinDistribution} // 50/50 effectively
              isBalanced={true}
              accuracy={fairCoinData.accuracy} // e.g., 48%
              confusionMatrixData={fairCoinConfusionMatrix}
              predictedClassDistributionData={predictedFairCoinData}
              variant="oneGauge"
              disableAccuracySegments={true} // Show raw gauge
              accuracyGaugeSegments={fixedAccuracyGaugeSegments} // Pass fixed segments for raw view
              gaugeDescription={
                <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                    <p className="text-sm font-medium text-center">~50% accuracy achieved.</p>
                    <p className="text-xs mt-1 text-center">
                        But is this good guessing without knowing the chance baseline?
                    </p>
                </div>
              }
            />

            <EvaluationCard
              title="Always Guessing &quot;Heads&quot;"
              subtitle="100 coin flips (e.g., 51 Heads, 49 Tails). Always predict &quot;Heads&quot;."
              classDistributionData={fairCoinDistribution} // Actual distribution
              isBalanced={true} // or false if actual distribution is skewed
              accuracy={alwaysHeadsData.accuracy} // e.g., 51%
              confusionMatrixData={alwaysHeadsConfusionMatrix}
              predictedClassDistributionData={predictedAlwaysHeadsData}
              variant="oneGauge"
              disableAccuracySegments={true} // Show raw gauge
              accuracyGaugeSegments={fixedAccuracyGaugeSegments} // Pass fixed segments for raw view
              gaugeDescription={
                <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                    <p className="text-sm font-medium text-center">~51% accuracy achieved.</p>
                    <p className="text-xs mt-1 text-center">
                        Slightly better, but still hovering around the 50% chance rate.
                    </p>
                </div>
              }
            />
          </div>

          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Key Insight: The Baseline Problem</h3>
            <p className="text-muted-foreground">
              Both strategies hover around 50% accuracy. This is the <strong className="text-foreground">base random-chance agreement rate</strong> for a binary task. Without understanding this baseline, raw accuracy numbers are uninterpretable. Any reported accuracy must be compared against what random chance would yield for that specific problem.
            </p>
          </div>
        </section>

        <section>
            <h2 className="text-2xl font-semibold mb-4">Pitfall 2: The Moving Target of Multiple Classes</h2>
            <p className="text-muted-foreground mb-6">
              The chance agreement rate isn't fixed; it changes with the number of classes. For example, consider guessing the suit of a randomly drawn card from a standard 4-suit deck:
            </p>

            <EvaluationCard
              title="Guessing Card Suits (4 Classes)"
              subtitle="Standard deck, four equally likely suits. Random guesses might yield ~23-25% accuracy."
              classDistributionData={cardSuitActualDistribution}
              isBalanced={true}
              accuracy={cardSuitData.accuracy} 
              confusionMatrixData={cardSuitConfusionMatrix}
              predictedClassDistributionData={cardSuitPredictedDistribution}
              variant="oneGauge"
              disableAccuracySegments={true} 
              accuracyGaugeSegments={fixedAccuracyGaugeSegments} 
              gaugeDescription={
                <>
                  <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                    <p className="text-sm font-medium text-center">~23% accuracy in this run.</p>
                    <p className="text-xs mt-1 text-center">
                        The fixed gauge makes this look terrible. Is it?
                    </p>
                  </div>
                  <div className="mt-3 p-2 bg-destructive rounded-md">
                    <p className="text-sm font-bold text-white text-center">Misleading Raw View</p>
                    <p className="text-xs mt-1 text-white text-center">
                      For a 4-class problem, 25% is the actual random chance baseline. The raw gauge is deceptive here.
                    </p>
                  </div>
                </>
              }
            />

            <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6 mb-6">
              <h3 className="text-lg font-semibold mb-2">Key Insight: Number of Classes Shifts the Baseline</h3>
              <p className="text-muted-foreground">
                The baseline random-chance agreement rate dropped from 50% (for 2 classes like coin flips) to 25% (for 4 classes like card suits). This is a critical concept: <strong className="text-foreground">as the number of equally likely options increases, the accuracy you'd expect from random guessing decreases</strong>. Therefore, a 30% accuracy is much better for a 10-class problem (10% chance) than for a 2-class problem (50% chance).
              </p>
            </div>
        </section>

        <section>
            <h2 className="text-2xl font-semibold mb-4">Pitfall 3: The Illusion of Class Imbalance</h2>
            <p className="text-muted-foreground mb-6">
              The distribution of classes in your data (class balance) adds another layer of complexity. If a dataset is imbalanced, a classifier can achieve high accuracy by simply always predicting the majority class, even if it has no real skill.
            </p>
            <div className="grid md:grid-cols-2 gap-6 mb-6">
                <EvaluationCard
                  title="Stacked Deck (75% Red): Random 50/50 Guess"
                  subtitle="Deck: 75% Red, 25% Black. Guess strategy: 50/50 Red/Black (ignores imbalance)."
                  classDistributionData={[{label: "Red", count: 75}, {label: "Black", count: 25}] } // Simplified distribution
                  isBalanced={false}
                  accuracy={52} // Example accuracy, around 50% as it doesn't use imbalance info
                  variant="oneGauge"
                  disableAccuracySegments={true}
                  gaugeDescription={
                    <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                        <p className="text-sm font-medium text-center">~52% accuracy.</p>
                        <p className="text-xs mt-1 text-center">Strategy doesn't exploit the deck's known 75/25 imbalance.</p>
                    </div>
                    }
                />
                <EvaluationCard
                  title="Stacked Deck (75% Red): Always Guess Red"
                  subtitle="Deck: 75% Red, 25% Black. Guess strategy: Always predict Red."
                  classDistributionData={[{label: "Red", count: 75}, {label: "Black", count: 25}] }
                  isBalanced={false}
                  accuracy={75.0} 
                  variant="oneGauge"
                  disableAccuracySegments={true}
                  gaugeDescription={
                    <>
                      <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                        <p className="text-sm font-medium text-center">75% accuracy!</p>
                      </div>
                      <div className="mt-3 p-2 bg-destructive rounded-md">
                        <p className="text-sm font-bold text-white text-center">Deceptively High!</p>
                        <p className="text-xs mt-1 text-white text-center">
                          This 75% is achieved by exploiting the imbalance (always guessing majority), not by skill.
                        </p>
                      </div>
                    </>
                  }
                />
            </div>
            <p className="text-muted-foreground mb-6">
              A more extreme example: an email filter claims 97% accuracy at detecting prohibited content. However, if only 3% of emails actually contain such content, a filter that labels *every single email* as "safe" (catching zero violations) will achieve 97% accuracy.
            </p>
             <EvaluationCard
                title="The &quot;Always Safe&quot; Email Filter (97/3 Imbalance)"
                subtitle="Labels all emails as 'safe'. Actual: 97% Safe, 3% Prohibited."
                classDistributionData={[{ label: "Safe", count: 970 }, { label: "Prohibited", count: 30 }]}
                isBalanced={false}
                accuracy={97.0}
                variant="oneGauge"
                disableAccuracySegments={true}
                gaugeDescription={
                  <>
                    <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                        <p className="text-sm font-medium text-center">97% accuracy! Sounds great?</p>
                    </div>
                    <div className="mt-3 p-2 bg-destructive rounded-md">
                      <p className="text-sm font-bold text-white text-center">CRITICAL FLAW!</p>
                      <p className="text-xs mt-1 text-white text-center">
                        This model detects ZERO prohibited content. It's worse than useless, providing a false sense of security.
                      </p>
                    </div>
                  </>
                }
              />
            <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6">
              <h3 className="text-lg font-semibold mb-2">Key Insight: Imbalance Inflates Naive Accuracy</h3>
              <p className="text-muted-foreground">
                Raw accuracy scores are deeply misleading without considering class imbalance. <strong className="text-foreground">A high accuracy might simply reflect the majority class proportion, not actual predictive power.</strong> A 97% accuracy could be excellent for a balanced problem, mediocre for a moderately imbalanced one, or indicative of complete failure in rare event detection.
              </p>
            </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Plexus's Solution: A Unified Approach to Clarity</h2>
          <p className="text-muted-foreground mb-4">
            To overcome these common pitfalls and provide a true understanding of classifier performance, Plexus employs a two-pronged strategy that combines contextualized raw metrics with inherently context-aware agreement scores:
          </p>
          <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
            <li>
              <strong className="text-foreground">Contextualized Accuracy Gauges:</strong> We don't just show raw accuracy; we show it on a dynamic visual scale. The colored segments of our Accuracy gauges adapt based on the number of classes *and* their distribution in your specific data. This immediately helps you interpret if an accuracy score is good, bad, or indifferent *for that particular problem context*.
            </li>
            <li>
              <strong className="text-foreground">Inherently Context-Aware Agreement Gauges:</strong> Alongside accuracy, we prominently feature an Agreement gauge (typically using Gwet's AC1). This metric is specifically designed to calculate a chance-corrected measure of agreement. It *internally* accounts for the number of classes and their distribution, providing a standardized score (0 = chance, 1 = perfect) that reflects skill beyond random guessing. This score is directly comparable across different problems and datasets.
            </li>
          </ol>
          <p className="text-muted-foreground mb-4">
            Let's see how this unified approach clarifies the performance of our Article Topic Labeler (which had 62% raw accuracy, 5 classes, and an imbalanced distribution with 40% "News"):
          </p>

          <EvaluationCard
            title="Article Topic Labeler - The Plexus View"
            subtitle="5-class, imbalanced (40% News). Accuracy: 62%, Gwet's AC1: 0.512"
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            gwetAC1={articleTopicLabelerExampleData.gwetAC1}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            showBothGauges={true} 
            variant="default" 
            accuracyGaugeSegments={articleTopicLabelerFullContextSegments} 
            notes="The contextualized Accuracy gauge (right) shows 62% as 'good' for this specific 5-class imbalanced problem—better than just guessing 'News' (40%) or random 5-class (20%). The Agreement gauge (left, AC1=0.512) confirms moderate skill beyond chance, consistently accounting for all contextual factors. Both gauges together provide a clear, reliable picture."
          />

          <div className="mt-6 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
            <h3 className="text-lg font-semibold mb-2">The Power of Two Gauges</h3>
            <p className="text-muted-foreground mb-3">
              This combined approach offers robust and intuitive understanding:
            </p>
            <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                <li>The <strong className="text-foreground">Contextualized Accuracy Gauge</strong> clarifies what the raw 62% accuracy means for *this specific task's complexities* (5 classes, imbalanced).</li>
                <li>The <strong className="text-foreground">Agreement Gauge</strong> provides a single, standardized score (AC1 of 0.512) measuring performance *above chance*, directly comparable across different problems.</li>
            </ul>
            <p className="text-muted-foreground mt-3">
              Together, they prevent misinterpretations of raw accuracy and offer true insight into a classifier's performance.
            </p>
          </div>
          
          <div className="mt-8 p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
            <h3 className="text-lg font-semibold mb-2">Dive Deeper into the Solutions</h3>
            <p className="text-muted-foreground mb-3">
              To understand the detailed mechanics of how Plexus contextualizes Accuracy gauges and how the Agreement gauge works across various scenarios, explore our dedicated guide:
            </p>
            <Link href="/documentation/evaluation-metrics/gauges-with-context">
              <DocButton>Understanding Gauges with Context</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Explore further documentation to enhance your understanding:
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/documentation/evaluation-metrics/gauges-with-context">
              <DocButton variant="outline">Detailed: Gauges with Context</DocButton>
            </Link>
            <Link href="/documentation/evaluation-metrics/examples">
              <DocButton>View More Examples</DocButton>
            </Link>
            <Link href="/documentation/basics/evaluations">
              <DocButton>Learn about Evaluations</DocButton>
            </Link>
            <Link href="/documentation/concepts/reports">
              <DocButton>Explore Reports</DocButton>
            </Link>
          </div>
        </section>

      </div>
    </div>
  );
} 