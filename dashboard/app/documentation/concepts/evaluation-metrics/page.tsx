import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import { Card, CardContent } from "@/components/ui/card"
import { ac1GaugeSegments } from "@/components/ui/feedback-score-card"
import { Gauge, Segment } from "@/components/gauge"
import ClassDistributionVisualizer from "@/components/ClassDistributionVisualizer"
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import PredictedClassDistributionVisualizer from "@/components/PredictedClassDistributionVisualizer"
import { ConfusionMatrix } from "@/components/confusion-matrix"
import EvaluationCard from '@/components/EvaluationCard'

export const metadata: Metadata = {
  title: "Evaluation Metrics - Plexus Documentation",
  description: "Understanding how to interpret alignment and accuracy gauges in Plexus"
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

// Component for displaying a score card in documentation
const DocScoreCard = ({ score, className }: { 
  score: ReturnType<typeof createExampleScore>;
  className?: string;
}) => {
  const agreements = score.item_count - score.mismatches;
  
  // Function to create accuracy gauge segments based on label distribution
  const getAccuracySegments = (labelDistribution?: Record<string, number>): Segment[] => {
    if (!labelDistribution) {
      // Default segments if no distribution data available
      return [
        { start: 0, end: 60, color: 'var(--gauge-inviable)' },
        { start: 60, end: 70, color: 'var(--gauge-converging)' },
        { start: 70, end: 80, color: 'var(--gauge-almost)' },
        { start: 80, end: 90, color: 'var(--gauge-viable)' },
        { start: 90, end: 100, color: 'var(--gauge-great)' }
      ];
    }
    const thresholds = GaugeThresholdComputer.computeThresholds(labelDistribution);
    return GaugeThresholdComputer.createSegments(thresholds);
  };

  // Function to create gauge information tooltip based on label distribution
  const getGaugeInformation = (labelDistribution?: Record<string, number>): string | undefined => {
    if (!labelDistribution) {
      return undefined;
    }
    const thresholds = GaugeThresholdComputer.computeThresholds(labelDistribution);
    return `Dynamic thresholds based on class distribution:
- Chance level (baseline): ${thresholds.chance.toFixed(1)}%
- Okay: ${thresholds.okayThreshold.toFixed(1)}%
- Good: ${thresholds.goodThreshold.toFixed(1)}%
- Great: ${thresholds.greatThreshold.toFixed(1)}%
- Perfect: ${thresholds.perfectThreshold.toFixed(1)}% and above`;
  };

  const accuracySegments = getAccuracySegments(score.label_distribution);
  const gaugeInfo = getGaugeInformation(score.label_distribution);

  return (
    <Card className={`bg-card shadow-none border-none ${className || ''}`}>
      <CardContent className="pt-6">
        <h4 className="font-bold mb-1">{score.score_name}</h4>
        <p className="text-sm text-muted-foreground mb-4">
          {agreements} agreement{agreements === 1 ? '' : 's'} / {score.item_count} feedback item{score.item_count === 1 ? '' : 's'}
        </p>
        <div className="flex flex-col sm:flex-row justify-around items-center gap-4 pt-2 pb-4">
          <div className="w-full sm:w-1/2 max-w-[200px] sm:max-w-none">
            <Gauge
              title="Agreement"
              value={score.ac1}
              min={-1}
              max={1}
              segments={ac1GaugeSegments}
              showTicks={false}
            />
          </div>
          <div className="w-full sm:w-1/2 max-w-[200px] sm:max-w-none">
            <Gauge
              title="Accuracy"
              value={score.accuracy}
              segments={accuracySegments}
              information={gaugeInfo}
              showTicks={false}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Component for displaying just accuracy gauge
const AccuracyGauge = ({ value, title, segments }: { 
  value: number, 
  title: string,
  segments?: Segment[] // Added optional segments prop
}) => (
  <div className="w-full max-w-[180px] mx-auto">
    <Gauge
      title={title}
      value={value}
      showTicks={true}
      segments={segments} // Pass segments to the Gauge component
    />
  </div>
);

// Define fixed segments for the illustrative accuracy gauges in the initial scenarios
const fixedAccuracyGaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },
  { start: 50, end: 70, color: 'var(--gauge-converging)' },
  { start: 70, end: 80, color: 'var(--gauge-almost)' },
  { start: 80, end: 90, color: 'var(--gauge-viable)' },
  { start: 90, end: 100, color: 'var(--gauge-great)' },
];

export default function EvaluationMetricsPage() {
  // Example scores for different scenarios - ALL NOW AT 75% ACCURACY
  const scenario1Data = createExampleScore( // Balanced 2-Class
    'scenario1-balanced-2class',
    'Scenario 1: Balanced 2-Class Data (50/50)',
    0.50, // AC1 for 75% acc, 50% chance: (0.75-0.5)/(1-0.5) = 0.50
    75.0,
    1000,
    250, // 1000 items, 75% accuracy -> 250 mismatches
    { 'Yes': 500, 'No': 500 }
  )
  
  // Added coin flip examples
  const fairCoinData = createExampleScore(
    'fair-coin',
    'Randomly Guessing Coin Flips (50/50)',
    -0.04, // AC1 for 48% acc, 50% chance: (0.48-0.5)/(1-0.5) = -0.04
    48.0, // Slightly below chance to emphasize stochastic nature
    100,  
    52,   // 52 mismatches out of 100
    { 'Heads': 50, 'Tails': 50 }
  )
  
  const weightedCoinData = createExampleScore(
    'weighted-coin',
    'Weighted Coin Prediction (75/25)',
    0.0,
    75.0,
    100,
    25,
    { 'Heads': 75, 'Tails': 25 }
  )
  
  const alwaysHeadsData = createExampleScore(
    'always-heads',
    'Always Guessing "Heads" (50/50)',
    0.0, // AC1 for 50% accuracy on 50/50 data when always guessing majority/one class
    50.0,
    100,
    50, // 50 mismatches if 50 are Tails and all are guessed Heads
    { 'Heads': 50, 'Tails': 50 } // Actual distribution is 50/50
  )
  
  const scenario2Data = createExampleScore( // Balanced 4-Class
    'scenario2-balanced-4class',
    'Scenario 2: Balanced 4-Class Data (25/25/25/25)',
    0.67, // AC1 for 75% acc, 25% chance: (0.75-0.25)/(1-0.25) = 0.666...
    75.0,
    1000,
    250,
    { 'Technical': 250, 'Marketing': 250, 'Legal': 250, 'Financial': 250 }
  )

  const scenario3Data = createExampleScore( // Imbalanced 2-Class
    'scenario3-imbalanced-2class',
    'Scenario 3: Imbalanced 2-Class Data (95/5)',
    -0.05, // AC1 for 75% acc on 95/5 (Yes/No). Po=0.75. With Pred Yes=790, Pred No=210: Pe=(0.95*0.79)+(0.05*0.21) = 0.7505 + 0.0105 = 0.761. AC1=(0.75-0.761)/(1-0.761) = -0.011/0.239 approx -0.05
    75.0,
    1000,
    250,
    { 'Yes': 950, 'No': 50 }
  )
  
  const scenario4Data = createExampleScore( // Naive Always-Yes classifier on 75/25 data
    'scenario4-naive-75yes',
    'Scenario 4: Imbalanced (75/25) - Naive Always-Yes Classifier',
    0.0,  // Po=0.75. Pred Yes=1.0, Pred No=0.0. Pe=(0.75*1.0)+(0.25*0.0)=0.75. AC1=(0.75-0.75)/(1-0.75)=0
    75.0,
    1000,
    250, // All 250 "No" cases are misclassified
    { 'Yes': 750, 'No': 250 }
  )

  // Distribution data for visualization
  const scenario1Distribution = [ // Balanced 2-Class
    { label: "Yes", count: 500 },
    { label: "No", count: 500 }
  ];
  
  // Coin flip distribution data
  const fairCoinDistribution = [
    { label: "Heads", count: 50 },
    { label: "Tails", count: 50 }
  ];
  
  const weightedCoinDistribution = [
    { label: "Heads", count: 75 },
    { label: "Tails", count: 25 }
  ];
  
  const scenario2Distribution = [ // Balanced 4-Class
    { label: "Technical", count: 250 },
    { label: "Marketing", count: 250 },
    { label: "Legal", count: 250 },
    { label: "Financial", count: 250 }
  ];

  const scenario3Distribution = [ // Imbalanced 2-Class
    { label: "Yes", count: 950 },
    { label: "No", count: 50 }
  ];

  const scenario4Distribution = [ // Imbalanced 2-Class (75/25)
    { label: "Yes", count: 750 },
    { label: "No", count: 250 }
  ];

  // Predicted distribution data for the examples at 75% accuracy
  const predictedScenario1Data = [
    { label: "Yes", count: 500 },
    { label: "No", count: 500 }
  ];

  // Predicted distributions for coin flip examples
  const predictedFairCoinData = [
    { label: "Heads", count: 50 }, // Random guessing should match distribution (50/50)
    { label: "Tails", count: 50 }
  ];
  
  const predictedWeightedCoinData = [
    { label: "Heads", count: 78 },
    { label: "Tails", count: 22 }
  ];
  
  const predictedAlwaysHeadsData = [
    { label: "Heads", count: 100 },
    { label: "Tails", count: 0 }
  ];
  
  const predictedScenario2Data = [
    { label: "Technical", count: 250 },
    { label: "Marketing", count: 250 },
    { label: "Legal", count: 250 },
    { label: "Financial", count: 250 }
  ];

  const predictedScenario3Data = [
    { label: "Yes", count: 790 }, 
    { label: "No", count: 210 }
  ];

  const predictedScenario4Data = [
    { label: "Yes", count: 1000 }, 
    { label: "No", count: 0 }
  ];

  // Compute dynamic segments for examples in the "Plexus's Approach" section
  const thresholds2Class = GaugeThresholdComputer.computeThresholds(scenario1Data.label_distribution!);
  const dynamicSegments2Class = GaugeThresholdComputer.createSegments(thresholds2Class);

  const thresholds4Class = GaugeThresholdComputer.computeThresholds(scenario2Data.label_distribution!);
  const dynamicSegments4Class = GaugeThresholdComputer.createSegments(thresholds4Class);

  // Compute dynamic segments for coin flip examples
  const thresholdsFairCoin = GaugeThresholdComputer.computeThresholds(fairCoinData.label_distribution!);
  const dynamicSegmentsFairCoin = GaugeThresholdComputer.createSegments(thresholdsFairCoin);
  
  const thresholdsWeightedCoin = GaugeThresholdComputer.computeThresholds(weightedCoinData.label_distribution!);
  const dynamicSegmentsWeightedCoin = GaugeThresholdComputer.createSegments(thresholdsWeightedCoin);

  // Fair coin confusion matrix data - showing the 48% accuracy
  const fairCoinConfusionMatrix = {
    labels: ["Heads", "Tails"],
    matrix: [
      { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 24, "Tails": 26 } },
      { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 26, "Tails": 24 } },
    ],
  };
  
  // Weighted coin confusion matrix
  const weightedCoinConfusionMatrix = {
    labels: ["Heads", "Tails"],
    matrix: [
      { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 60, "Tails": 18 } },
      { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 15, "Tails": 7 } },
    ],
  };
  
  // Always heads confusion matrix - showing 51% accuracy
  const alwaysHeadsConfusionMatrix = {
    labels: ["Heads", "Tails"],
    matrix: [
      { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 50, "Tails": 0 } },
      { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 50, "Tails": 0 } },
    ],
  };

  // Card Suit Guessing Example Data
  const cardSuitData = createExampleScore(
    'card-suit-guessing',
    'Predicting a Card Suit (4 Classes, Random Guessing)',
    -0.03,  // AC1 for 23% acc, 25% chance: (0.23-0.25)/(1-0.25) = -0.03
    23.0, // Accuracy slightly below the random chance level
    52,   // Standard deck size - 52 cards
    40,   // 52 items, 23% accuracy -> 40 mismatches (52-12=40)
    { '♥️': 13, '♦️': 13, '♣️': 13, '♠️': 13 } // Standard deck has 13 of each suit
  );

  const cardSuitActualDistribution = [
    { label: "♥️", count: 13 },
    { label: "♦️", count: 13 },
    { label: "♣️", count: 13 },
    { label: "♠️", count: 13 }
  ];

  const cardSuitConfusionMatrix = {
    labels: ["♥️", "♦️", "♣️", "♠️"],
    matrix: [
      { actualClassLabel: "♥️", predictedClassCounts: { "♥️": 3, "♦️": 3, "♣️": 3, "♠️": 4 } },
      { actualClassLabel: "♦️", predictedClassCounts: { "♥️": 3, "♦️": 3, "♣️": 4, "♠️": 3 } },
      { actualClassLabel: "♣️", predictedClassCounts: { "♥️": 3, "♦️": 4, "♣️": 3, "♠️": 3 } },
      { actualClassLabel: "♠️", predictedClassCounts: { "♥️": 4, "♦️": 3, "♣️": 3, "♠️": 3 } },
    ],
  };
  
  const cardSuitPredictedDistribution = [ 
    { label: "♥️", count: (3+3+4+3) },   // Sum of first column = 13
    { label: "♦️", count: (3+4+3+3) },   // Sum of second column = 13 
    { label: "♣️", count: (4+3+3+3) },   // Sum of third column = 13
    { label: "♠️", count: (3+3+3+4) }    // Sum of fourth column = 13
  ];

  // Stacked deck example data (75% Hearts)
  const stackedDeckData = createExampleScore(
    'stacked-deck-random-guessing',
    'Predicting a Stacked Deck (75% Hearts) with Random Guessing',
    -0.33,  // AC1 score for this scenario
    25.0,   // Accuracy with random guessing is still 25%
    52,     // Total predictions - standard deck size
    39,     // 39 wrong predictions
    { '♥️': 39, '♦️': 5, '♣️': 4, '♠️': 4 } // Distribution of actual cards (39+5+4+4=52)
  );

  const stackedDeckActualDistribution = [
    { label: "♥️", count: 39 },
    { label: "♦️", count: 5 },
    { label: "♣️", count: 4 },
    { label: "♠️", count: 4 }
  ];

  const stackedDeckRandomGuessingConfusionMatrix = {
    labels: ["♥️", "♦️", "♣️", "♠️"],
    matrix: [
      { actualClassLabel: "♥️", predictedClassCounts: { "♥️": 10, "♦️": 10, "♣️": 10, "♠️": 9 } },
      { actualClassLabel: "♦️", predictedClassCounts: { "♥️": 1, "♦️": 2, "♣️": 1, "♠️": 1 } },
      { actualClassLabel: "♣️", predictedClassCounts: { "♥️": 1, "♦️": 1, "♣️": 1, "♠️": 1 } },
      { actualClassLabel: "♠️", predictedClassCounts: { "♥️": 1, "♦️": 1, "♣️": 1, "♠️": 1 } }
    ],
  };
  
  const stackedDeckRandomPredictedDistribution = [ 
    { label: "♥️", count: 13 },  // We're guessing randomly, so ~13 for each suit
    { label: "♦️", count: 13 },
    { label: "♣️", count: 13 },
    { label: "♠️", count: 13 }
  ];

  // Always guessing Hearts for the stacked deck
  const alwaysHeartsStackedDeckData = createExampleScore(
    'stacked-deck-always-hearts',
    'Predicting a Stacked Deck (75% Hearts) by Always Guessing "Hearts"',
    0.0,    // AC1 score for always guessing the majority class
    75.0,   // Accuracy matches the majority class percentage
    52,     // Total predictions - standard deck size
    13,     // 13 wrong predictions (all non-Hearts)
    { '♥️': 39, '♦️': 5, '♣️': 4, '♠️': 4 } // Same distribution
  );

  const alwaysHeartsConfusionMatrix = {
    labels: ["♥️", "♦️", "♣️", "♠️"],
    matrix: [
      { actualClassLabel: "♥️", predictedClassCounts: { "♥️": 39, "♦️": 0, "♣️": 0, "♠️": 0 } },
      { actualClassLabel: "♦️", predictedClassCounts: { "♥️": 5, "♦️": 0, "♣️": 0, "♠️": 0 } },
      { actualClassLabel: "♣️", predictedClassCounts: { "♥️": 4, "♦️": 0, "♣️": 0, "♠️": 0 } },
      { actualClassLabel: "♠️", predictedClassCounts: { "♥️": 4, "♦️": 0, "♣️": 0, "♠️": 0 } }
    ],
  };
  
  const alwaysHeartsPredictedDistribution = [ 
    { label: "♥️", count: 52 },  // Always predicting Hearts for all 52 cards
    { label: "♦️", count: 0 },
    { label: "♣️", count: 0 },
    { label: "♠️", count: 0 }
  ];

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluation Metrics</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understanding how Plexus visualizes agreement and accuracy in evaluation data
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">The Problem with Raw Accuracy</h2>
          <p className="text-muted-foreground mb-4">
            Let's start with a simple game: predicting coin flips. Imagine someone flips a coin 100 times, and your job is to predict each outcome before it happens. You'll need to make your prediction before each flip, and then we'll track how many you get right.
          </p>
          
          <div className="space-y-8 mb-8">

            <EvaluationCard
              title="Randomly Guessing Coin Flips"
              subtitle="For 100 fair coin flips (50/50 chance), you make random guesses for each flip."
              classDistributionData={fairCoinDistribution}
              isBalanced={true}
              accuracy={fairCoinData.accuracy}
              confusionMatrixData={fairCoinConfusionMatrix}
              predictedClassDistributionData={predictedFairCoinData}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <>
                  <p>
                    <strong>Is this a good accuracy score?</strong>
                  </p>
                  <p className="mt-2 text-sm">
                    We got a number, but how do we know if that's good performance at guessing?
                  </p>
                </>
              }
              accuracyGaugeSegments={fixedAccuracyGaugeSegments}
            />

            <p className="text-muted-foreground mb-6">
              Maybe random guessing isn't the best strategy? Let's try something different. What if you always predict the same outcome for every flip? Let's see what happens when you always predict "Heads" for each of the 100 flips.
            </p>

            <EvaluationCard
              title="Always Guessing &quot;Heads&quot;"
              subtitle="For 100 fair coin flips, you always predict &quot;Heads&quot; on every flip."
              classDistributionData={fairCoinDistribution}
              isBalanced={true}
              accuracy={alwaysHeadsData.accuracy}
              confusionMatrixData={alwaysHeadsConfusionMatrix}
              predictedClassDistributionData={predictedAlwaysHeadsData}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <>
                  <p>
                    <strong>So, is this good?</strong>
                  </p>
                  <p className="mt-2 text-sm">
                    This is a higher number than random guessing, so that's good. Right?
                  </p>
                </>
              }
              accuracyGaugeSegments={fixedAccuracyGaugeSegments}
            />

            <p className="text-muted-foreground mb-6">
              Notice something interesting about both strategies? They both resulted in accuracy rates hovering around 50%. This is what we call the <strong className="text-foreground">base random-chance agreement rate</strong> - the accuracy you would expect from pure guessing when the outcomes are equally likely.
            </p>
            
            <p className="text-muted-foreground mb-6">
              With a perfectly fair coin, no strategy can consistently beat the 50% baseline because each flip is completely independent and random. Any accuracy above this baseline (over a large number of flips) would suggest either extraordinary luck or that you've discovered some actual pattern in the coin's behavior.
            </p>

            <p className="text-muted-foreground mb-6">
              This raises an important question: if you guess right 48% or 51% of the time with a coin flip, is that "good" performance? The answer depends entirely on what you're comparing it to - in this case, the baseline random chance of 50%.
            </p>

            <p className="text-muted-foreground mb-6">
              Interpreting accuracy requires understanding the baseline performance for the specific prediction task. Without this context, raw accuracy numbers are meaningless - we need to know what accuracy level would be expected by chance alone.
            </p>

            <h3 className="text-xl font-medium mb-3">A Complication: Multiple Classes</h3>
            <p className="text-muted-foreground mb-6">
              But it gets more complicated when we introduce more than two classes, because the baseline random chance agreement rate changes. To illustrate this, let's look at a simple example: guessing the suit of a card.
            </p>

            <p className="text-muted-foreground mb-6">
              Imagine you're in a Las Vegas casino, and the dealer has a shuffled deck of cards. You're trying to guess the suit of the top card before it's revealed.
            </p>

            <p className="text-muted-foreground mb-6">
              Since there are four suits, you'd expect to be right about 25% of the time if you're just guessing randomly.
            </p>

            <EvaluationCard
              title="Guessing Card Suits"
              subtitle="For a standard 52-card deck with four equally likely suits, you make random guesses."
              classDistributionData={cardSuitActualDistribution}
              isBalanced={true}
              confusionMatrixData={cardSuitConfusionMatrix}
              predictedClassDistributionData={cardSuitPredictedDistribution}
              accuracy={cardSuitData.accuracy}
              variant="oneGauge"
              accuracyGaugeSegments={fixedAccuracyGaugeSegments}
              disableAccuracySegments={true}
              gaugeDescription={
                <>
                  <p>
                    <strong>Wait, is 23% accuracy bad?</strong>
                  </p>
                  <p className="mt-2 text-sm">
                    The gauge shows this as poor performance, but is that the right interpretation for a 4-class problem?
                  </p>
                  
                  <div className="mt-4 p-3 bg-destructive rounded-md">
                    <p className="text-base font-bold text-white">Misleading Accuracy</p>
                    <p className="text-sm mt-1 text-white">
                      For a 4-class problem, 25% is actually the baseline random chance level. The fixed gauge incorrectly implies below-chance performance when you're approximately at the chance level.
                    </p>
                  </div>
                </>
              }
            />

            <p className="text-muted-foreground mb-6">
              Notice how the baseline random-chance agreement rate dropped from 50% with two choices (Heads/Tails) to 25% with four choices (Hearts/Diamonds/Clubs/Spades). This is a key concept: <strong className="text-foreground">as the number of equally likely options increases, the accuracy you'd expect from random guessing decreases</strong>.
            </p>

            <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
              <h4 className="text-lg font-semibold mb-2">Key Insight: Context is Essential</h4>
              <p className="text-muted-foreground mb-3">
                These examples demonstrate a critical point: <strong className="text-foreground">you cannot interpret accuracy numbers without understanding the context</strong> - specifically:
              </p>
              <ul className="list-disc pl-6 space-y-2 mb-3 text-muted-foreground">
                <li>The number of possible classes (2, 4, or more)</li>
                <li>The distribution of those classes (balanced or imbalanced)</li>
                <li>The baseline accuracy from random guessing</li>
              </ul>
              <p className="text-muted-foreground">
                A 25% accuracy score might be terrible for a binary classifier but perfectly at chance level for a 4-class problem. Without this context, raw accuracy numbers are essentially meaningless.
              </p>
            </div>

            {/* === END OF NEW Card Suit Guessing Example === */}

            {/* === START OF NEW Stacked Deck Examples (Color Version) === */}
            <h3 className="text-xl font-medium mb-3">Another Complication: Class Imbalance</h3>
            <p className="text-muted-foreground mb-6">
              And there's a second factor that can confuse the interpretation of raw accuracy: the distribution of the classes in the actual data.
            </p>
            <p className="text-muted-foreground mb-6">
              Let's go back to a simpler task: guessing whether a playing card is red or black. But here's the twist - this time our deck is stacked, with 75% red cards and only 25% black cards.
            </p>

            <EvaluationCard
              title="Guessing Card Colors in a Stacked Deck"
              subtitle="If you simply guess red or black with equal probability (50/50) for each card in our stacked deck, you'd still expect around 50% accuracy, regardless of the deck's imbalance. This strategy doesn't exploit or account for the skewed distribution."
              classDistributionData={[
                { label: "Red", count: 39 },
                { label: "Black", count: 13 }
              ]}
              isBalanced={false}
              confusionMatrixData={{
                labels: ["Red", "Black"],
                matrix: [
                  { actualClassLabel: "Red", predictedClassCounts: { "Red": 20, "Black": 19 } },
                  { actualClassLabel: "Black", predictedClassCounts: { "Red": 6, "Black": 7 } },
                ],
              }}
              predictedClassDistributionData={[
                { label: "Red", count: 26 },
                { label: "Black", count: 26 }
              ]}
              accuracy={52.0}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <p className="text-sm">
                  <strong>Still at basic chance level:</strong> Even with a stacked deck (75% red cards), random 50/50 guessing still gives you about 50% accuracy. This matches the baseline for a balanced binary prediction task. Your random strategy doesn't exploit the imbalance in the deck.
                </p>
              }
            />

            <p className="text-muted-foreground mb-6">
              But what if you knew about the imbalance in the deck? Could you use that information to your advantage?
            </p>

            {/* NEW: Matching distribution example */}
            <EvaluationCard
              title="Matching the Known Distribution"
              subtitle="Now suppose someone tells you that 75% of the cards are red. You could &quot;cheat&quot; by matching your guessing pattern to this distribution—guessing &quot;red&quot; 75% of the time and &quot;black&quot; 25% of the time, while still randomly assigning these guesses to specific cards."
              classDistributionData={[
                { label: "Red", count: 39 },
                { label: "Black", count: 13 }
              ]}
              isBalanced={false}
              confusionMatrixData={{
                labels: ["Red", "Black"],
                matrix: [
                  { actualClassLabel: "Red", predictedClassCounts: { "Red": 29, "Black": 10 } },
                  { actualClassLabel: "Black", predictedClassCounts: { "Red": 10, "Black": 3 } },
                ],
              }}
              predictedClassDistributionData={[
                { label: "Red", count: 39 },
                { label: "Black", count: 13 }
              ]}
              accuracy={62.0}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <p className="text-sm">
                  <strong>Better than random guessing, but still no skill:</strong> By matching the known distribution, your accuracy jumps to around 62.5% (0.75×0.75 + 0.25×0.25 = 0.625). This appears better than 50% random guessing, but you're still not demonstrating any card-specific prediction skill—you're just exploiting knowledge of the overall distribution. The AC1 score would still be near 0.
                </p>
              }
            />

            <p className="text-muted-foreground mb-6">
              There's an even simpler strategy that could achieve even higher accuracy with zero skill. What if you just always guessed the majority class?
            </p>

            {/* Second stacked deck example - Always guessing red */}
            <EvaluationCard
              title="Always Guessing Red"
              subtitle="The most extreme &quot;cheating&quot; strategy is simply to always guess the majority class. With 75% red cards in the deck, if you guess &quot;Red&quot; for every single card, you'll automatically get 75% accuracy without any genuine predictive ability."
              classDistributionData={[
                { label: "Red", count: 39 },
                { label: "Black", count: 13 }
              ]}
              isBalanced={false}
              confusionMatrixData={{
                labels: ["Red", "Black"],
                matrix: [
                  { actualClassLabel: "Red", predictedClassCounts: { "Red": 39, "Black": 0 } },
                  { actualClassLabel: "Black", predictedClassCounts: { "Red": 13, "Black": 0 } },
                ],
              }}
              predictedClassDistributionData={[
                { label: "Red", count: 52 },
                { label: "Black", count: 0 }
              ]}
              accuracy={75.0}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <>
                  <p className="text-sm">
                    <strong>No real insight:</strong> The AC1 score would be 0.0, correctly showing that you have no predictive ability beyond exploiting the class distribution.
                  </p>

                  <div className="p-3 bg-destructive rounded-md mt-4">
                    <p className="text-base font-bold text-white">Misleading Accuracy</p>
                    <p className="text-sm mt-1 text-white">
                      This 75% accuracy looks impressive compared to the typical 50% baseline for a binary task. But it's meaningless! With a 75/25 class imbalance, simply always predicting the majority class achieves 75% accuracy with zero predictive skill.
                    </p>
                  </div>                  
                </>
              }
            />

            <p className="text-muted-foreground mt-6 mb-6">
              These examples reveal how class imbalance creates a dangerous situation: as imbalance increases, so does the accuracy you can achieve with no actual skill. Moving from our first to third strategy, we've seen accuracy increase from 52% to 75% without any improvement in actual prediction ability. This shows why raw accuracy without context can be deeply misleading when classes aren't balanced.
            </p>

            {/* NEW: Email Prohibited Language Detection Example */}
            <h3 className="text-xl font-medium mb-3 mt-8">Real-world Example: Content Moderation in Email</h3>
            <p className="text-muted-foreground mb-6">
              Let's examine an extreme but common real-world scenario: detecting prohibited language in emails. In most business environments, legitimate prohibited content is rare—occurring in only about 3% of all communications. This severe class imbalance creates a dangerous situation where meaningless classifiers can appear highly effective.
            </p>
            
            <p className="text-muted-foreground mb-6">
              Imagine you're evaluating an email filtering system that claims 97% accuracy in detecting prohibited content. Sounds impressive! But upon investigation, you discover it achieves this by simply labeling every single email as "safe" regardless of content. With only 3% of emails actually containing prohibited content, this trivial classifier achieves 97% accuracy while catching exactly zero violations.
            </p>
            
            <EvaluationCard
              title="The &quot;Always Safe&quot; Email Filter"
              subtitle="A content filter that labels all emails as 'safe' regardless of actual content"
              classDistributionData={[
                { label: "Safe", count: 970 },
                { label: "Prohibited", count: 30 }
              ]}
              isBalanced={false}
              confusionMatrixData={{
                labels: ["Safe", "Prohibited"],
                matrix: [
                  { actualClassLabel: "Safe", predictedClassCounts: { "Safe": 970, "Prohibited": 0 } },
                  { actualClassLabel: "Prohibited", predictedClassCounts: { "Safe": 30, "Prohibited": 0 } },
                ],
              }}
              predictedClassDistributionData={[
                { label: "Safe", count: 1000 },
                { label: "Prohibited", count: 0 }
              ]}
              accuracy={97.0}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <>
                  <p className="text-sm">
                    <strong>Yay!:</strong> 97% accuracy is great, right?
                  </p>

                  <div className="p-3 bg-destructive rounded-md mt-4">
                    <p className="text-base font-bold text-white">CRITICAL FLAW</p>
                    <p className="text-sm mt-1 text-white">
                      This 97% accuracy is dangerously misleading! The model failed to detect ANY prohibited content (0% recall for violations). It simply labels everything as "safe" and benefits from the extreme class imbalance. This is worse than useless—it's a false sense of security.
                    </p>
                  </div>
                </>
              }
            />

            <p className="text-muted-foreground mb-6">
              If you let someone tell you that a model has 97% accuracy, they're not really telling you anything about the model's performance.  You need to know the context of the task to understand what that means.
            </p>
            
            <div className="mt-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
              <h3 className="text-xl font-semibold mb-2">The Core Problem: Accuracy Without Context Is Meaningless</h3>
              <p className="text-muted-foreground mb-3">
                As our examples demonstrate, <strong className="text-foreground">raw accuracy scores cannot be meaningfully interpreted without context</strong>. A 97% accuracy might represent:
              </p>
              <ul className="list-disc pl-6 space-y-2 mb-4 text-muted-foreground">
                <li>Excellent performance on a balanced dataset</li>
                <li>Mediocre performance on an imbalanced dataset</li> 
                <li>Complete failure that detects zero relevant cases in rare event detection</li>
              </ul>
              <p className="text-muted-foreground mb-3">
                How can we solve this fundamental problem? We have two primary approaches:
              </p>
              <ol className="list-decimal pl-6 space-y-2 mb-2 text-muted-foreground">
                <li><strong className="text-foreground">Add context to the accuracy metric</strong> by visually adjusting gauge thresholds based on class distribution</li>
                <li><strong className="text-foreground">Use alternative metrics</strong> that inherently account for class distribution (like Gwet's AC1)</li>
              </ol>
              <p className="text-sm text-muted-foreground mt-3">
                As we'll see next, Plexus provides both solutions to ensure you can correctly interpret classifier performance regardless of your data's characteristics.
              </p>
            </div>
            
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Two Solutions for More Meaningful Evaluation</h2>
          <p className="text-muted-foreground mb-4">
            When faced with a raw accuracy score, like "75% accurate," it's hard to know its true meaning without more information. Plexus addresses this challenge in two main ways to provide a clearer picture of classifier performance:
          </p>
          <div className="space-y-6 mb-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Solution 1: Adding Context to Accuracy</h3>
              <p className="text-muted-foreground">
                The first approach is to retain raw accuracy but enhance its interpretability by providing crucial context. Plexus achieves this by using dynamic visual scales on its Accuracy gauges. This means the background colors and threshold markers on the Accuracy gauge adapt based on your data's characteristics – specifically, the number of classes and the distribution of items among those classes.
              </p>
              <p className="text-muted-foreground mt-2 mb-4">
                By calculating a "chance level" or baseline for your specific dataset, the gauge's colors can visually indicate whether the achieved accuracy is substantially better than random guessing, just slightly better, or even close to what chance would predict. For example, 75% accuracy might look very different on a gauge for a 2-class balanced problem (50% chance) versus a 4-class balanced problem (25% chance). This contextual scaling helps you interpret the raw number more effectively.
              </p>

              {/* Coin Flip Example Card */}
              <EvaluationCard
                title="Coin Flip Prediction (50/50)"
                subtitle="A fair coin has a 50% chance of heads or tails. Random guessing achieves 50% accuracy."
                classDistributionData={fairCoinDistribution}
                isBalanced={true}
                accuracy={50.0}
                variant="default"
                notes="Without context (left gauge), the 50% accuracy has no meaning. With proper contextual segments (right gauge), 
                we can see that 50% is exactly at the chance level for a balanced binary problem, indicating no prediction skill."
              />

              {/* Card Suit Example Card */}
              <EvaluationCard
                title="Card Suit Prediction (25/25/25/25)"
                subtitle="A standard deck has four equally likely suits. Random guessing achieves 25% accuracy."
                classDistributionData={cardSuitActualDistribution}
                isBalanced={true}
                accuracy={25.0}
                variant="default"
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(cardSuitData.label_distribution!))}
                notes="Without context (left gauge), 25% accuracy appears very low. With proper contextual segments (right gauge), 
                we can see that 25% is exactly at the chance level for a balanced 4-class problem, indicating no prediction skill."
              />

              <p className="text-muted-foreground mt-4 mb-4">
                The dynamic gauges adjust their colors to match what "baseline random chance" means for each specific task. 
                Instead of misleadingly suggesting that random guessing is "poor performance" in multi-class problems, 
                the adjusted gauge shows it's exactly what you'd expect from chance. This makes it much easier to understand 
                when a model is actually performing better than random guessing.
              </p>

              <p className="text-muted-foreground mt-4 mb-4">
                Let's return to our card deck example to demonstrate how gauge thresholds adjust for imbalanced data. Remember our stacked deck with 75% red cards?
              </p>

              {/* Fair Deck Example Card */}
              <Card className="border-none shadow-none bg-card mb-6">
                <CardContent className="pt-6">
                  <h4 className="text-xl font-medium mb-3">Fair Deck Color Prediction (50/50)</h4>
                  <p className="text-sm text-muted-foreground mb-4">
                    A standard deck has equal numbers of red and black cards. Random guessing achieves 50% accuracy.
                  </p>
                  
                  <div className="w-full mb-4">
                    <ClassDistributionVisualizer 
                      data={[
                        { label: "Red", count: 26 },
                        { label: "Black", count: 26 }
                      ]} 
                      isBalanced={true} 
                    />
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                    <div className="flex flex-col items-center">
                      <p className="text-sm font-medium mb-2">Without Context</p>
                      <div className="max-w-[180px] mx-auto">
                        <Gauge
                          value={50.0}
                          title=""
                          showTicks={true}
                          segments={[
                            { start: 0, end: 100, color: 'var(--gauge-inviable)' }
                          ]}
                        />
                      </div>
                      <p className="text-sm mt-2 text-center">
                        <strong>50.0%</strong><br/>
                        <span className="text-xs text-muted-foreground">No context for interpretation</span>
                      </p>
                    </div>
                    
                    <div className="flex flex-col items-center">
                      <p className="text-sm font-medium mb-2">With Context</p>
                      <div className="max-w-[180px] mx-auto">
                        <AccuracyGauge 
                          value={50.0} 
                          title=""
                          segments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 26, "Black": 26 }))} 
                        />
                      </div>
                      <p className="text-sm mt-2 text-center">
                        <strong>50.0%</strong><br/>
                        <span className="text-xs text-muted-foreground">At baseline random chance</span>
                      </p>
                    </div>
                  </div>
                  
                  <div className="bg-card/50 rounded-md p-4 mt-6">
                    <div className="space-y-1 text-xs">
                      <p><strong>Random guessing strategy:</strong> 50% red, 50% black</p>
                      <p><strong>Expected accuracy:</strong> 50%</p>
                      <p><strong>Baseline chance level:</strong> 50.0%</p>
                      <p className="mt-2"><strong>Segment thresholds:</strong></p>
                      <p className="pl-2 text-[11px]">Poor: 0-50% (below chance)</p>
                      <p className="pl-2 text-[11px]">Okay: 50-70% (up to +20%)</p>
                      <p className="pl-2 text-[11px]">Good: 70-80% (up to +30%)</p>
                      <p className="pl-2 text-[11px]">Great: 80-90% (up to +40%)</p>
                      <p className="pl-2 text-[11px]">Perfect: 90-100% (above +40%)</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Stacked Deck Example Card */}
              <Card className="border-none shadow-none bg-card mb-6">
                <CardContent className="pt-6">
                  <h4 className="text-xl font-medium mb-3">Stacked Deck Color Prediction (75/25)</h4>
                  <p className="text-sm text-muted-foreground mb-4">
                    This deck is stacked with 75% red cards and 25% black cards. Distribution-aware random guessing achieves 62.5% accuracy.
                  </p>
                  
                  <div className="w-full mb-4">
                    <ClassDistributionVisualizer 
                      data={[
                        { label: "Red", count: 39 },
                        { label: "Black", count: 13 }
                      ]} 
                      isBalanced={false} 
                    />
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                    <div className="flex flex-col items-center">
                      <p className="text-sm font-medium mb-2">Without Context</p>
                      <div className="max-w-[180px] mx-auto">
                        <Gauge
                          value={62.5}
                          title=""
                          showTicks={true}
                          segments={[
                            { start: 0, end: 100, color: 'var(--gauge-inviable)' }
                          ]}
                        />
                      </div>
                      <p className="text-sm mt-2 text-center">
                        <strong>62.5%</strong><br/>
                        <span className="text-xs text-muted-foreground">No context for interpretation</span>
                      </p>
                    </div>
                    
                    <div className="flex flex-col items-center">
                      <p className="text-sm font-medium mb-2">With Context</p>
                      <div className="max-w-[180px] mx-auto">
                        <AccuracyGauge 
                          value={62.5} 
                          title=""
                          segments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }))}
                        />
                      </div>
                      <p className="text-sm mt-2 text-center">
                        <strong>62.5%</strong><br/>
                        <span className="text-xs text-muted-foreground">At baseline random chance</span>
                      </p>
                    </div>
                  </div>
                  
                  <div className="bg-card/50 rounded-md p-4 mt-6">
                    <div className="space-y-1 text-xs">
                      <p><strong>Distribution-aware guessing:</strong> 75% red, 25% black</p>
                      <p><strong>Expected accuracy:</strong> 0.75×0.75 + 0.25×0.25 = 62.5%</p>
                      <p><strong>Baseline chance level:</strong> {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance.toFixed(1)}%</p>
                      <p className="mt-2"><strong>Segment thresholds:</strong></p>
                      <p className="pl-2 text-[11px]">Poor: 0-{GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance.toFixed(1)}% (below chance)</p>
                      <p className="pl-2 text-[11px]">Okay: {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance.toFixed(1)}-{GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).okayThreshold.toFixed(1)}% (up to +20%)</p>
                      <p className="pl-2 text-[11px]">Good: {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).okayThreshold.toFixed(1)}-{GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).goodThreshold.toFixed(1)}% (up to +30%)</p>
                      <p className="pl-2 text-[11px]">Great: {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).goodThreshold.toFixed(1)}-{GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).greatThreshold.toFixed(1)}% (up to +40%)</p>
                      <p className="pl-2 text-[11px]">Perfect: {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).greatThreshold.toFixed(1)}-100% (above +40%)</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <div className="mt-6 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
                <h4 className="text-xl font-semibold mb-2">Key Insight: Notice how our gauge thresholds shift to counteract the advantage gained by simply matching the distribution.</h4>
                <p className="text-muted-foreground mb-3">
                  By correctly identifying that the baseline chance level for the stacked deck is around {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance.toFixed(1)}%, the gauge prevents us from being impressed by accuracy scores that could be achieved just by exploiting the skewed distribution.
                </p>
                
                <ul className="list-disc pl-6 space-y-2 mb-3 text-muted-foreground">
                  <li>With the stacked deck, <strong className="text-foreground">distribution-aware random guessing</strong> achieves 62.5% accuracy with zero real predictive skill</li>
                  <li>All the "success" segments (okay, good, great) are <strong className="text-foreground">crammed to the right</strong> of the gauge for imbalanced data, reflecting the higher baseline to beat</li>
                  <li>To achieve what would be considered "good" performance (30% above chance) on the stacked deck, you'd need accuracy of {(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance + 30).toFixed(1)}%!</li>
                </ul>
              </div>


            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Solution 2: Using a Context-Free Agreement Metric</h3>
              <p className="text-muted-foreground">
                The second, and often more dependable, approach is to employ metrics that inherently account for chance agreement and class distribution. Plexus prominently features Gwet's AC1 as its primary "Agreement" metric. This statistical measure provides a stable and reliable assessment of classifier performance without requiring additional contextual information.
              </p>
              <p className="text-muted-foreground mt-2 mb-6">
                An AC1 score of 0 typically indicates performance no better than chance, while a score of 1 indicates perfect agreement, and negative scores indicate systematic disagreement. Because this correction for chance is built into the AC1 calculation, its scale (and the interpretation of "good" or "poor" agreement) remains consistent regardless of the number of classes or the balance of the data distribution. This makes the Agreement gauge straightforward to interpret - you don't need to mentally adjust for the data's characteristics because the metric has already done that heavy lifting.
              </p>

              <p className="text-lg font-medium mb-4">Side-by-Side Comparison: Agreement vs. Accuracy</p>
              <p className="text-muted-foreground mb-6">
                Let's compare the Agreement (AC1) gauge with the Accuracy gauge for the same examples we showed earlier, to see how each metric handles different scenarios:
              </p>

              {/* Coin Flip Example - Using showBothGauges prop */}
              <EvaluationCard
                title="Random Coin Flip Prediction (50/50)"
                subtitle="A fair coin has a 50% chance of heads or tails. This single run achieved 48% accuracy."
                classDistributionData={fairCoinDistribution}
                isBalanced={true}
                accuracy={48.0}
                gwetAC1={-0.04}
                confusionMatrixData={{
                  labels: ["Heads", "Tails"],
                  matrix: [
                    { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 24, "Tails": 26 } },
                    { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 26, "Tails": 24 } },
                  ],
                }}
                predictedClassDistributionData={predictedFairCoinData}
                showBothGauges={true}
                variant="default"
                notes="Both gauges correctly indicate performance slightly below chance level for this particular run. The Agreement gauge shows AC1 = -0.04, and the Accuracy gauge shows 48% is just below the expected baseline for a balanced binary problem."
              />

              {/* Card Suit Example - Using showBothGauges prop */}
              <EvaluationCard
                title="Random Card Suit Prediction (25/25/25/25)"
                subtitle="A standard deck has four equally likely suits. This single run achieved 23% accuracy."
                classDistributionData={cardSuitActualDistribution}
                isBalanced={true}
                accuracy={23.0}
                gwetAC1={-0.03}
                confusionMatrixData={cardSuitConfusionMatrix}
                predictedClassDistributionData={cardSuitPredictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(cardSuitData.label_distribution!))}
                notes="Both gauges indicate performance slightly below chance for this particular run. The Agreement gauge shows AC1 = -0.03, and the contextual Accuracy gauge shows 23% is just below the baseline 25% for a balanced 4-class problem."
              />

              {/* Fair Deck Example - Using showBothGauges prop */}
              <EvaluationCard
                title="Fair Deck Color Prediction (50/50)"
                subtitle="A standard deck has equal numbers of red and black cards. This single run achieved 53% accuracy."
                classDistributionData={[
                  { label: "Red", count: 26 },
                  { label: "Black", count: 26 }
                ]}
                isBalanced={true}
                accuracy={53.0}
                gwetAC1={0.06}
                confusionMatrixData={{
                  labels: ["Red", "Black"],
                  matrix: [
                    { actualClassLabel: "Red", predictedClassCounts: { "Red": 14, "Black": 12 } },
                    { actualClassLabel: "Black", predictedClassCounts: { "Red": 12, "Black": 14 } },
                  ],
                }}
                predictedClassDistributionData={[
                  { label: "Red", count: 26 },
                  { label: "Black", count: 26 }
                ]}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 26, "Black": 26 }))}
                notes="Both gauges indicate performance slightly above chance for this particular run. The Agreement gauge shows AC1 = 0.06, and the contextual Accuracy gauge shows 53% is just above the baseline 50% for a balanced binary problem."
              />

              {/* Stacked Deck Example - Using EvaluationCard like the examples above */}
              <EvaluationCard
                title="Stacked Deck Color Prediction (75/25)"
                subtitle="This deck is stacked with 75% red cards and 25% black cards. This run achieved 51.9% accuracy, slightly below random chance."
                classDistributionData={[
                  { label: "Red", count: 39 },
                  { label: "Black", count: 13 }
                ]}
                isBalanced={false}
                accuracy={51.9}
                gwetAC1={-0.137}
                confusionMatrixData={{
                  labels: ["Red", "Black"],
                  matrix: [
                    { actualClassLabel: "Red", predictedClassCounts: { "Red": 24, "Black": 15 } },
                    { actualClassLabel: "Black", predictedClassCounts: { "Red": 10, "Black": 3 } },
                  ],
                }}
                predictedClassDistributionData={[
                  { label: "Red", count: 34 },
                  { label: "Black", count: 18 }
                ]}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }))}
                notes="With a stacked deck (75% red, 25% black), distribution-aware random guessing achieves 62.5% accuracy. This example shows slightly worse performance at 51.9% accuracy. The Agreement gauge shows AC1 = -0.137, correctly indicating below-chance performance despite what might seem like a decent accuracy score on its own."
              />

              {/* Always Red Example - Using EvaluationCard like the examples above */}
              <EvaluationCard
                title="Always Predicting Red (75/25 Stacked Deck)"
                subtitle="For a deck stacked with 75% red cards and 25% black cards, always predicting 'red' achieves 75% accuracy without any genuine predictive skill."
                classDistributionData={[
                  { label: "Red", count: 39 },
                  { label: "Black", count: 13 }
                ]}
                isBalanced={false}
                accuracy={75.0}
                gwetAC1={0.0}
                confusionMatrixData={{
                  labels: ["Red", "Black"],
                  matrix: [
                    { actualClassLabel: "Red", predictedClassCounts: { "Red": 39, "Black": 0 } },
                    { actualClassLabel: "Black", predictedClassCounts: { "Red": 13, "Black": 0 } },
                  ],
                }}
                predictedClassDistributionData={[
                  { label: "Red", count: 52 },
                  { label: "Black", count: 0 }
                ]}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }))}
                notes="Despite achieving 75% accuracy (which sounds impressive), the Agreement gauge correctly shows AC1 = 0.00, indicating no predictive skill beyond chance. By always guessing 'red' for all cards in a deck that's 75% red, we match the majority class percentage but demonstrate zero discriminative ability. The AC1 metric immediately exposes this 'cheating' strategy."
              />

            </div>
          </div>
        </section>



        <section>
          <h2 className="text-2xl font-semibold mb-4">Example Scenarios</h2>
          <p className="text-muted-foreground mb-4">
            Let's explore a variety of classifier scenarios to see how both Agreement (AC1) and Accuracy gauges represent different performance levels across different data distributions.
          </p>
        
          <p className="font-medium mb-2">Balanced Distributions</p>
          <p className="text-muted-foreground mt-2 mb-4">
            When dealing with balanced distributions, where each class has an equal (or nearly equal) number of instances, the number of classes itself becomes a critical factor in interpreting raw accuracy. A 65% accuracy score, for instance, means something very different for a 2-class problem (where chance is 50%) compared to a 4-class problem (where chance is 25%). The dynamically colored segments on the Accuracy gauge are designed to help with this: they visually adjust the 'chance', 'okay', 'good', and 'great' regions based on the number of classes, providing immediate visual context for how the achieved accuracy compares to the baseline random chance performance for that specific number of classes.
          </p>
          <p className="text-muted-foreground mt-2 mb-6">
            Gwet's AC1 Agreement gauge, on the other hand, adapts to the number of classes in a different but equally powerful way. The AC1 calculation inherently accounts for chance agreement based on the number of classes and their distribution. This means the AC1 score itself (ranging from -1 to 1) can be interpreted consistently: a score of 0.0 always indicates performance no better than chance, 1.0 indicates perfect agreement, and values in between (e.g., 0.2-0.4 for fair, 0.4-0.6 for moderate, 0.6-0.8 for substantial, 0.8-1.0 for almost perfect agreement) carry a similar meaning regardless of whether you have two, three, or ten classes. This consistency makes the Agreement gauge a very reliable indicator of true classifier skill, corrected for chance.
          </p>
          {/* Binary classifier, balanced distribution, 65% accuracy */}
          {(() => {
            const scoreData = { accuracy: 65.0, itemCount: 100, mismatches: 35, label_distribution: { 'Yes': 50, 'No': 50 } };
            const gwetAC1 = 0.30; // (0.65 - 0.5) / (1 - 0.5)
            const classDistribution = [ { label: "Yes", count: 50 }, { label: "No", count: 50 } ];
            const confusionMatrix = {
              labels: ["Yes", "No"],
              matrix: [
                { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 32, "No": 18 } }, // 50 Actual Yes, 32 correct
                { actualClassLabel: "No", predictedClassCounts: { "Yes": 17, "No": 33 } },  // 50 Actual No, 33 correct
              ], // Total correct: 32+33=65
            };
            const predictedDistribution = [ { label: "Yes", count: 32+17 }, { label: "No", count: 18+33 } ]; // Yes: 49, No: 51
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));

            return (
              <EvaluationCard
                title="Binary Classifier, Balanced (65% Accuracy)"
                subtitle="Two classes ('Yes', 'No'), 50 items each. Classifier achieves 65/100 correct."
                classDistributionData={classDistribution}
                isBalanced={true}
                accuracy={scoreData.accuracy}
                gwetAC1={gwetAC1}
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="With 65% accuracy on a balanced binary task (chance = 50%), the AC1 is 0.30. This is only 15 points above chance, suggesting mediocre performance. The contextual accuracy gauge shows this level."
              />
            );
          })()}

          {/* Ternary classifier ("Yes", "No", "NA"), balanced distribution, 65% accuracy */}
          {(() => {
            const scoreData = { accuracy: 65.0, itemCount: 100, mismatches: 35, label_distribution: { 'Yes': 34, 'No': 33, 'NA': 33 } };
            const gwetAC1 = 0.475; // Approx (0.65 - 0.3333) / (1 - 0.3333)
            const classDistribution = [ { label: "Yes", count: 34 }, { label: "No", count: 33 }, { label: "NA", count: 33 } ];
            const confusionMatrix = {
              labels: ["Yes", "No", "NA"],
              matrix: [
                { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 22, "No": 6, "NA": 6 } }, // 34 total, 22 correct (12 errors)
                { actualClassLabel: "No", predictedClassCounts: { "Yes": 6, "No": 22, "NA": 5 } },  // 33 total, 22 correct (11 errors)
                { actualClassLabel: "NA", predictedClassCounts: { "Yes": 6, "No": 6, "NA": 21 } },  // 33 total, 21 correct (12 errors)
              ], // Total correct: 22+22+21=65. Total errors: 12+11+12=35
            };
            const predictedDistribution = [ 
              { label: "Yes", count: 22+6+6 }, // 34
              { label: "No", count: 6+22+6 },   // 34
              { label: "NA", count: 6+5+21 }    // 32
            ];
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));

            return (
              <EvaluationCard
                title="Ternary Classifier, Balanced (65% Accuracy)"
                subtitle="Three classes ('Yes', 'No', 'NA'), roughly equal distribution. Classifier achieves 65/100 correct."
                classDistributionData={classDistribution}
                isBalanced={true}
                accuracy={scoreData.accuracy}
                gwetAC1={gwetAC1}
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="With 65% accuracy on a balanced 3-class task (chance approx 33.3%), the AC1 is ~0.475. This is ~31.7 points above chance, indicating fairly good performance. The gauges reflect this improvement over the binary case."
              />
            );
          })()}
          
          {/* Four-class classifier, balanced distribution, 65% accuracy */}
          {(() => {
            const scoreData = { accuracy: 65.0, itemCount: 100, mismatches: 35, label_distribution: { 'A': 25, 'B': 25, 'C': 25, 'D': 25 } };
            const gwetAC1 = 0.533; // (0.65 - 0.25) / (1 - 0.25)
            const classDistribution = [ { label: "A", count: 25 }, { label: "B", count: 25 }, { label: "C", count: 25 }, { label: "D", count: 25 } ];
            const confusionMatrix = {
              labels: ["A", "B", "C", "D"],
              matrix: [
                { actualClassLabel: "A", predictedClassCounts: { "A": 16, "B": 3, "C": 3, "D": 3 } }, // 25 total, 16 correct (9 errors)
                { actualClassLabel: "B", predictedClassCounts: { "A": 3, "B": 16, "C": 3, "D": 3 } }, // 25 total, 16 correct (9 errors)
                { actualClassLabel: "C", predictedClassCounts: { "A": 3, "B": 3, "C": 16, "D": 3 } }, // 25 total, 16 correct (9 errors)
                { actualClassLabel: "D", predictedClassCounts: { "A": 3, "B": 2, "C": 3, "D": 17 } }, // 25 total, 17 correct (8 errors)
              ], // Total correct: 16+16+16+17=65. Total errors: 9+9+9+8=35
            };
            const predictedDistribution = [ 
              { label: "A", count: 16+3+3+3 }, // 25
              { label: "B", count: 3+16+3+2 }, // 24
              { label: "C", count: 3+3+16+3 }, // 25
              { label: "D", count: 3+3+3+17 }  // 26
            ];
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));
            
            return (
              <EvaluationCard
                title="Four-Class Classifier, Balanced (65% Accuracy)"
                subtitle="Four classes ('A', 'B', 'C', 'D'), 25 items each. Classifier achieves 65/100 correct."
                classDistributionData={classDistribution}
                isBalanced={true}
                accuracy={scoreData.accuracy}
                gwetAC1={gwetAC1}
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="With 65% accuracy on a balanced 4-class task (chance = 25%), the AC1 is ~0.533. This is a substantial 40 points above chance, representing good performance. The gauges clearly show this as better than the binary and ternary examples with the same accuracy."
              />
            );
          })()}

          <div className="mt-6 mb-6 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
            <h4 className="text-lg font-semibold mb-2">Key Insight: Same Accuracy, Different Meanings</h4>
            <p className="text-muted-foreground mb-3">
              These three examples all showcase a classifier achieving 65% accuracy. However, the interpretation of this performance shifts dramatically when we consider the problem context, especially the number of classes and the baseline chance agreement. Gwet's AC1 and the contextualized Accuracy gauge help clarify these differences:
            </p>
            <ul className="list-disc pl-6 space-y-2 mb-3 text-muted-foreground">
              <li>For the <strong>binary classifier</strong> (2 classes, 50% chance baseline), 65% accuracy yields an AC1 of <strong>0.30</strong>. This is only 15 percentage points above chance, indicating somewhat <strong className="text-foreground">mediocre performance</strong>.</li>
              <li>For the <strong>ternary classifier</strong> (3 classes, ~33.3% chance baseline), the same 65% accuracy results in an AC1 of approximately <strong>0.475</strong>. This is about 31.7 points above chance, suggesting <strong className="text-foreground">fairly good performance</strong>.</li>
              <li>For the <strong>four-class classifier</strong> (4 classes, 25% chance baseline), 65% accuracy gives an AC1 of approximately <strong>0.533</strong>. This is a substantial 40 points above chance, representing <strong className="text-foreground">good performance</strong>.</li>
            </ul>
            <p className="text-muted-foreground">
              This clearly demonstrates that a raw accuracy score like 65% can be misleading on its own. Its true meaning heavily depends on the context of the task. Gwet's AC1 provides a more robust and comparable measure of agreement, highlighting how the same accuracy can correspond to vastly different levels of skill relative to chance.
            </p>
          </div>

          <p className="font-medium mt-4 mb-2">Imbalanced Distributions</p>
          <p className="text-muted-foreground mt-2 mb-4">
            Interpreting classifier performance becomes even more challenging with imbalanced distributions, where one or more classes are significantly over or underrepresented. Raw accuracy, in particular, can be dangerously misleading. A classifier might achieve a high accuracy score simply by predicting the majority class most of the time, while completely failing on minority classes. The Accuracy gauge, with its dynamically adjusting segments, remains a key tool. It calculates a baseline chance agreement level that considers the skewed distribution. This means the 'good' performance regions on the gauge will shift, often to higher accuracy values, reflecting that a higher raw accuracy is needed to demonstrate skill beyond merely guessing the dominant class. The upcoming \"Always No\" strategy example will starkly illustrate this: high apparent accuracy, but the gauge will reveal it as unimpressive once contextualized against the skewed baseline.
          </p>
          <p className="text-muted-foreground mt-2 mb-6">
            Gwet's AC1 Agreement gauge proves especially invaluable for imbalanced datasets. Because it inherently corrects for chance agreement that arises from the specific class distribution (no matter how skewed), an AC1 score provides a stable and reliable measure of a classifier's ability to agree with true labels beyond what random chance would produce for that particular imbalance. For instance, if a model achieves a high AC1 score on an imbalanced dataset, it indicates genuine skill in distinguishing between classes, including the rarer ones. Conversely, as we will see in the \"Always No\" example, a strategy that yields high raw accuracy by ignoring the minority class will correctly result in an AC1 score of 0.0, exposing its lack of true predictive power across the full spectrum of classes.
          </p>
          {/* Binary classifier, imbalanced (5% \"Yes\" prevalence), 90/100 correct */}
          {(() => {
            const scoreData = { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'Yes': 5, 'No': 95 } };
            const gwetAC1 = 0.401; // Calculated: (0.90 - ((0.05*0.13)+(0.95*0.87))) / (1 - ((0.05*0.13)+(0.95*0.87)))
            const classDistribution = [ { label: "Yes", count: 5 }, { label: "No", count: 95 } ];
            const isBalanced = false;
            const confusionMatrix = {
              labels: ["Yes", "No"],
              matrix: [
                { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 4, "No": 1 } }, // 5 Actual Yes: 4 TP, 1 FN
                { actualClassLabel: "No", predictedClassCounts: { "Yes": 9, "No": 86 } },  // 95 Actual No: 9 FP, 86 TN
              ], // Total correct: 4+86=90. Errors: 1+9=10.
            };
            const predictedDistribution = [ { label: "Yes", count: 4+9 }, { label: "No", count: 1+86 } ]; // Yes:13, No:87
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));

            return (
              <EvaluationCard
                title="Binary Classifier, Imbalanced (5% 'Yes'), 90% Accuracy"
                subtitle="Actual: 5 'Yes', 95 'No'. Classifier gets 90/100 correct."
                classDistributionData={classDistribution}
                isBalanced={isBalanced}
                accuracy={scoreData.accuracy}
                gwetAC1={gwetAC1}
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="Despite 90% raw accuracy, the severe imbalance (only 5% 'Yes') means this performance is not as strong as it seems. Gwet's AC1 of ~0.401 indicates moderate agreement above chance. The dynamic accuracy gauge also reflects that beating the ~90.5% chance level (Pe for accuracy) is harder here."
              />
            );
          })()}

          {/* Binary classifier, imbalanced (5% \"Yes\" prevalence), always answers "No" (cheating strategy) */}
          {(() => {
            const scoreData = { accuracy: 95.0, itemCount: 100, mismatches: 5, label_distribution: { 'Yes': 5, 'No': 95 } };
            const gwetAC1 = 0.0;
            const classDistribution = [ { label: "Yes", count: 5 }, { label: "No", count: 95 } ];
            const isBalanced = false;
            const confusionMatrix = {
              labels: ["Yes", "No"],
              matrix: [
                { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 0, "No": 5 } }, // All 5 'Yes' are missed
                { actualClassLabel: "No", predictedClassCounts: { "Yes": 0, "No": 95 } },  // All 95 'No' are correct
              ],
            };
            const predictedDistribution = [ { label: "Yes", count: 0 }, { label: "No", count: 100 } ];
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));

            return (
              <EvaluationCard
                title="Binary Classifier, Imbalanced (5% 'Yes'), 'Always No' Strategy"
                subtitle="Actual: 5 'Yes', 95 'No'. Classifier always predicts 'No'."
                classDistributionData={classDistribution}
                isBalanced={isBalanced}
                accuracy={scoreData.accuracy} // Achieves 95% accuracy by being right about all 'No' cases
                gwetAC1={gwetAC1} // AC1 is 0.0, showing no skill beyond chance for this strategy
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="This 'cheating' classifier achieves 95% accuracy simply by predicting the majority class ('No') every time. However, Gwet's AC1 is 0.0, correctly exposing that it has zero predictive skill for the minority 'Yes' class and offers no value despite the high accuracy."
              />
            );
          })()}

          {/* Ternary classifier, imbalanced distribution, 90/100 correct */}
          {(() => {
            const scoreData = { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'A': 5, 'B': 45, 'C': 50 } };
            const gwetAC1 = 0.819; // Calculated: (0.90 - Pe) / (1-Pe) where Pe = (0.05*0.07) + (0.45*0.44) + (0.50*0.49) = 0.4465
            const classDistribution = [ { label: "A", count: 5 }, { label: "B", count: 45 }, { label: "C", count: 50 } ];
            const isBalanced = false;
            const confusionMatrix = {
              labels: ["A", "B", "C"],
              matrix: [
                { actualClassLabel: "A", predictedClassCounts: { "A": 3, "B": 1, "C": 1 } },     // 5 total, 3 correct
                { actualClassLabel: "B", predictedClassCounts: { "A": 2, "B": 41, "C": 2 } },   // 45 total, 41 correct
                { actualClassLabel: "C", predictedClassCounts: { "A": 2, "B": 2, "C": 46 } },    // 50 total, 46 correct
              ], // Total Correct: 3+41+46 = 90. Errors: 2+4+4 = 10.
            };
            const predictedDistribution = [ 
              { label: "A", count: 3+2+2 },   // 7
              { label: "B", count: 1+41+2 },  // 44
              { label: "C", count: 1+2+46 }    // 49
            ];
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));

            return (
              <EvaluationCard
                title="Ternary Classifier, Imbalanced (90% Accuracy)"
                subtitle="Classes A:5, B:45, C:50. Classifier gets 90/100 correct."
                classDistributionData={classDistribution}
                isBalanced={isBalanced}
                accuracy={scoreData.accuracy}
                gwetAC1={gwetAC1}
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="Even with imbalanced classes (one very rare), 90% accuracy yields a strong Gwet's AC1 of ~0.819. This indicates genuine predictive skill well above what chance agreement (Pe ~0.4465) would suggest for this distribution."
              />
            );
          })()}

          {/* Four-class classifier, imbalanced distribution, 90/100 correct */}
          {(() => {
            const scoreData = { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'A': 5, 'B': 15, 'C': 30, 'D': 50 } };
            const gwetAC1 = 0.843; // Calculated: (0.90 - Pe) / (1-Pe) where Pe = (0.05*0.06) + (0.15*0.15) + (0.30*0.29) + (0.50*0.50) = 0.3625
            const classDistribution = [ { label: "A", count: 5 }, { label: "B", count: 15 }, { label: "C", count: 30 }, { label: "D", count: 50 } ];
            const isBalanced = false;
            const confusionMatrix = {
              labels: ["A", "B", "C", "D"],
              matrix: [
                { actualClassLabel: "A", predictedClassCounts: { "A": 3, "B": 1, "C": 1, "D": 0 } },   // 5 total, 3 correct
                { actualClassLabel: "B", predictedClassCounts: { "A": 1, "B": 12, "C": 1, "D": 1 } }, // 15 total, 12 correct
                { actualClassLabel: "C", predictedClassCounts: { "A": 1, "B": 1, "C": 27, "D": 1 } }, // 30 total, 27 correct
                { actualClassLabel: "D", predictedClassCounts: { "A": 1, "B": 1, "C": 0, "D": 48 } },  // 50 total, 48 correct
              ], // Total Correct: 3+12+27+48 = 90. Errors: 2+3+3+2=10.
            };
            const predictedDistribution = [
              { label: "A", count: 3+1+1+1 },    // 6
              { label: "B", count: 1+12+1+1 },   // 15
              { label: "C", count: 1+1+27+0 },   // 29
              { label: "D", count: 0+1+1+48 }    // 50
            ];
            const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds(scoreData.label_distribution));

            return (
              <EvaluationCard
                title="Four-Class Classifier, Imbalanced (90% Accuracy)"
                subtitle="Classes A:5, B:15, C:30, D:50. Classifier gets 90/100 correct."
                classDistributionData={classDistribution}
                isBalanced={isBalanced}
                accuracy={scoreData.accuracy}
                gwetAC1={gwetAC1}
                confusionMatrixData={confusionMatrix}
                predictedClassDistributionData={predictedDistribution}
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={accuracyGaugeSegments}
                notes="With a more complex 4-class imbalanced scenario, 90% accuracy achieves a Gwet's AC1 of ~0.843. This is excellent agreement, demonstrating robust performance significantly above the chance level (Pe ~0.3625) for this specific distribution."
              />
            );
          })()}

        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Now that you understand how to interpret Plexus's alignment gauges, explore related concepts
            to get the most out of your evaluation data.
          </p>
          <div className="flex gap-4">
            <Link href="/documentation/basics/evaluations">
              <DocButton>Learn about Evaluations</DocButton>
            </Link>
            <Link href="/documentation/concepts/reports">
              <DocButton variant="outline">Explore Reports</DocButton>
            </Link>
          </div>
        </section>

      </div>
    </div>
  );
} 