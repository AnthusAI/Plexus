import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import { Card, CardContent } from "@/components/ui/card"
import { ac1GaugeSegments } from "@/components/ui/feedback-analysis-evaluation"
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

  // Article Topic Labeler data for visualization components
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
    { label: "News", count: 40 }, // 28+3+3+3+3
    { label: "Sports", count: 15 }, // 3+9+1+1+1
    { label: "Business", count: 15 }, // 3+1+8+2+1
    { label: "Technology", count: 15 }, // 3+1+2+8+1
    { label: "Lifestyle", count: 15 }  // 3+1+1+1+9
  ];
  
  // Calculate segments for only the 5-class nature (balanced distribution)
  const balanced5ClassDistribution = { 'Class1': 20, 'Class2': 20, 'Class3': 20, 'Class4': 20, 'Class5': 20 };
  const articleTopicLabelerClassCountOnlySegments = GaugeThresholdComputer.createSegments(
    GaugeThresholdComputer.computeThresholds(balanced5ClassDistribution)
  );
  
  // Calculate segments for both 5-class nature AND the actual imbalanced distribution
  const articleTopicLabelerFullContextSegments = GaugeThresholdComputer.createSegments(
    GaugeThresholdComputer.computeThresholds(articleTopicLabelerExampleData.label_distribution)
  );

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
  

  
  const alwaysHeadsData = createExampleScore(
    'always-heads',
    'Always Guessing "Heads" (50/50)',
    0.02, // AC1 for 51% accuracy on 50/50 data when always guessing one class
    51.0,
    100,
    49, // 49 mismatches if 51 are Heads and 49 are Tails, and all are guessed Heads
    { 'Heads': 51, 'Tails': 49 } // Actual distribution is 51/49
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


  


  // Distribution data for visualization
  
  // Coin flip distribution data
  const fairCoinDistribution = [
    { label: "Heads", count: 51 },
    { label: "Tails", count: 49 }
  ];
  

  






  // Predicted distribution data for the examples at 75% accuracy

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
  






  // Compute dynamic segments for examples in the "Plexus's Approach" section
  const thresholds2Class = GaugeThresholdComputer.computeThresholds(scenario1Data.label_distribution!);
  const dynamicSegments2Class = GaugeThresholdComputer.createSegments(thresholds2Class);

  const thresholds4Class = GaugeThresholdComputer.computeThresholds(scenario2Data.label_distribution!);
  const dynamicSegments4Class = GaugeThresholdComputer.createSegments(thresholds4Class);

  // Compute dynamic segments for coin flip examples
  const thresholdsFairCoin = GaugeThresholdComputer.computeThresholds(fairCoinData.label_distribution!);
  const dynamicSegmentsFairCoin = GaugeThresholdComputer.createSegments(thresholdsFairCoin);
  


  // For the new visualization: 3-class and 12-class scenarios
  const label_distribution_3_class = { C1: 1, C2: 1, C3: 1 };
  const thresholds3Class = GaugeThresholdComputer.computeThresholds(label_distribution_3_class);
  const dynamicSegments3Class = GaugeThresholdComputer.createSegments(thresholds3Class);

  const label_distribution_12_class: Record<string, number> = {};
  for (let i = 1; i <= 12; i++) {
    label_distribution_12_class[`Class ${i}`] = 1;
  }
  const thresholds12Class = GaugeThresholdComputer.computeThresholds(label_distribution_12_class);
  const dynamicSegments12Class = GaugeThresholdComputer.createSegments(thresholds12Class);

  // Data for Class Imbalance Visualization
  const imbal_scenario1_dist = { C1: 50, C2: 50 }; // Balanced 50/50
  const imbal_scenario1_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario1_dist);
  const imbal_scenario1_segments = GaugeThresholdComputer.createSegments(imbal_scenario1_thresholds);

  const imbal_scenario2_dist = { C1: 75, C2: 25 }; // Imbalanced 75/25
  const imbal_scenario2_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario2_dist);
  const imbal_scenario2_segments = GaugeThresholdComputer.createSegments(imbal_scenario2_thresholds);

  const imbal_scenario3_dist = { C1: 95, C2: 5 }; // Highly Imbalanced 95/5
  const imbal_scenario3_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario3_dist);
  const imbal_scenario3_segments = GaugeThresholdComputer.createSegments(imbal_scenario3_thresholds);

  const imbal_scenario4_dist = { C1: 80, C2: 10, C3: 10 }; // Imbalanced 3-Class 80/10/10
  const imbal_scenario4_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario4_dist);
  const imbal_scenario4_segments = GaugeThresholdComputer.createSegments(imbal_scenario4_thresholds);

  // NEW data for 90/10 binary imbalance
  const imbal_scenario_moderate_dist = { C1: 90, C2: 10 };
  const imbal_scenario_moderate_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario_moderate_dist);
  const imbal_scenario_moderate_segments = GaugeThresholdComputer.createSegments(imbal_scenario_moderate_thresholds);







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
      { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 51, "Tails": 0 } },
      { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 49, "Tails": 0 } },
    ],
  };

  // Card Suit Guessing Example Data
      const cardSuitData = createExampleScore(
      'card-suit-guessing',
      'Predicting a Card Suit (4 Classes, Random Guessing)',
      -0.03,  // AC1 for 23% acc, 25% chance: (0.23-0.25)/(1-0.25) = -0.03
      23.0, // Accuracy slightly below the random chance level (25%)
      208,   // 4-deck shoe (like those used in casino games) - 208 cards total
      160,   // 208 items, 23% accuracy -> 160 mismatches (208-48=160)
      { '♥️': 52, '♦️': 52, '♣️': 52, '♠️': 52 } // 4-deck shoe has 52 cards of each suit
    );

  const cardSuitActualDistribution = [
    { label: "♥️", count: 52 * 4 }, // 208 cards in 4-deck shoe, 52 of each suit
    { label: "♦️", count: 52 * 4 },
    { label: "♣️", count: 52 * 4 },
    { label: "♠️", count: 52 * 4 }
  ];

  const cardSuitConfusionMatrix = {
    labels: ["♥️", "♦️", "♣️", "♠️"],
    matrix: [
      { actualClassLabel: "♥️", predictedClassCounts: { "♥️": 12*4, "♦️": 13*4, "♣️": 13*4, "♠️": 14*4 } },
      { actualClassLabel: "♦️", predictedClassCounts: { "♥️": 13*4, "♦️": 12*4, "♣️": 14*4, "♠️": 13*4 } },
      { actualClassLabel: "♣️", predictedClassCounts: { "♥️": 13*4, "♦️": 14*4, "♣️": 12*4, "♠️": 13*4 } },
      { actualClassLabel: "♠️", predictedClassCounts: { "♥️": 14*4, "♦️": 13*4, "♣️": 13*4, "♠️": 12*4 } },
    ],
  };
  
  const cardSuitPredictedDistribution = [ 
    { label: "♥️", count: (12+13+13+14) * 4 },   // Sum scaled to 4-deck shoe = 208
    { label: "♦️", count: (13+12+14+13) * 4 },   // Sum scaled to 4-deck shoe = 208 
    { label: "♣️", count: (13+14+12+13) * 4 },   // Sum scaled to 4-deck shoe = 208
    { label: "♠️", count: (14+13+13+12) * 4 }    // Sum scaled to 4-deck shoe = 208
  ];







  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluation Metrics</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understanding the metrics used in Plexus to evaluate the performance of scorecard scores.
      </p>

      <div className="space-y-10">
        <section className="mb-10">
          <h2 className="text-2xl font-semibold mb-4">The Big Question: Is This Classifier Good?</h2>
          <p className="text-muted-foreground mb-4">
            You can't optimize a metric that you're not measuring. When developing an AI system, we need some kind of gauge to tell us if our model is performing well or needs improvement. Let's look at a concrete example.
          </p>
          
          <p className="text-muted-foreground mb-4">
            Imagine we've built an "Article Topic Labeler" that classifies articles into one of five categories: News, Sports, Business, Technology, and Lifestyle. We evaluate it on 100 articles and get the following results:
          </p>

          <EvaluationCard
            title="Article Topic Labeler"
            subtitle="Classifies articles into 5 categories: News, Sports, Business, Technology, and Lifestyle"
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            variant="oneGauge"
            disableAccuracySegments={true}
                          gaugeDescription={
                <>
                  <p>
                    <strong>Is 62% accuracy good for this classifier?</strong>
                  </p>
                  <p className="mt-2 text-sm">
                    This seems like a fairly mediocre number. The gauge suggests it's in the "converging but not quite there" range. But without additional context, it's hard to determine if this represents genuinely poor performance or if there's more to the story.
                  </p>
                </>
              }
          />
          
          <p className="text-muted-foreground mt-4 mb-4">
            Our Article Topic Labeler shows 62% accuracy. Intuitively, that seems somewhat weak—after all, it's getting nearly 4 out of 10 articles wrong. But is this actually poor performance? How do we judge whether this is good or bad? The gauge doesn't provide much insight without context.
          </p>
          
          <p className="text-muted-foreground mb-4">
            To interpret this number, we need to understand what would be considered "bad" performance. If we were to just randomly guess topics instead of using our classifier, what number would we expect to see?
          </p>
        </section>
        
      </div>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">The Problem with Accuracy</h2>

          <p className="text-muted-foreground mb-4">
            Not so fast.  The problem is that we don't have enough information to know if 97% is good or bad.  We need to know what number would be bad.  If we just flip a coin instead of using our scorecard, then what number would we expect?
          </p>

          <p className="text-muted-foreground mb-4">
            That's easy to demonstrate with a simple game: predicting coin flips. Imagine someone flips a coin 100 times, and your job is to predict each outcome before it happens. You'll need to make your prediction before each flip, and then we'll track how many you get right.
          </p>
          
          <div className="space-y-8 mb-8">

            <EvaluationCard
              title="Randomly Guessing Coin Flips"
              subtitle="For 100 fair coin flips (50/50 chance), you make random guesses for each flip.  The green squares in the confusion matrix represent the correct guesses."
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
              subtitle="For 100 coin flips (51 Heads, 49 Tails), you always predict &quot;Heads&quot; on every flip."
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
              Interpreting accuracy requires understanding the baseline performance for the specific prediction task. Without this context, raw accuracy numbers are meaningless - we need to know what accuracy level would be expected by chance alone.  You have to understand the concept of chance agreement to understand accuracy.
            </p>

            <h3 className="text-xl font-medium mb-3">A Complication: Multiple Classes</h3>
            <p className="text-muted-foreground mb-6">
              The problem is that the chance agreement rate is a moving target.  The baseline random chance agreement rate changes when we introduce more than two classes. To illustrate this, let's look at a simple example: guessing the suit of a card.
            </p>

            <p className="text-muted-foreground mb-6">
              Imagine you're in a casino playing blackjack, where the dealer uses a multi-deck shoe containing 4 decks of cards (208 cards total). You're trying to guess the suit of each card before it's revealed.
            </p>

            <p className="text-muted-foreground mb-6">
              Since there are four suits distributed evenly across the multi-deck shoe, you'd expect to be right about 25% of the time if you're just guessing randomly. The casino uses multiple decks specifically to prevent card counting, making each draw effectively independent and random.
            </p>

            <EvaluationCard
              title="Guessing Card Suits in a Casino"
              subtitle="For a multi-deck shoe (208 cards) with four equally likely suits, you make random guesses."
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

              <div className="mb-8">
                <h3 className="text-xl font-medium mb-4">Decoding Accuracy: Why Baselines Are Essential</h3>
                
                <p className="text-muted-foreground mb-4">
                  When we hear about an AI model achieving a certain accuracy, say 90% or 95%, it's easy to assume that's a good result. But is it always? Many people believe that a high accuracy percentage inherently signifies strong performance, yet this overlooks a crucial aspect of evaluation.
                </p>
                
                <p className="text-muted-foreground mb-4">
                  <strong className="text-foreground">Think of it like a scientific measurement.</strong> If a physicist tells you a measurement is '12', your immediate question would be, '12 what?'. Twelve meters? Twelve seconds? Twelve kilograms? Without the unit, the number '12' is just an abstract figure, devoid of meaning in the real world. It cannot be interpreted or compared.
                </p>
                
                <p className="text-muted-foreground mb-4">
                  <strong className="text-foreground">Accuracy scores need their 'unit' too.</strong> An accuracy percentage (e.g., 90%) is a value. But to determine if it's good, bad, or indifferent, we need its contextual 'unit': the baseline performance for that specific task. What accuracy would random guessing achieve?
                </p>
                
                <p className="text-muted-foreground mb-4">
                  <strong className="text-foreground">Consider a coin flip (or any binary choice).</strong> For a task with two equally likely outcomes, random guessing yields about 50% accuracy. This isn't just <em>any</em> number; it's often the fundamental reference point. It's the <em>base random-chance agreement rate</em>—the score you would expect from pure guessing when outcomes are equally likely. Without knowing this baseline—whether it's 50% for a binary choice, or a different value for a multi-class problem—the reported accuracy doesn't truly tell us how much skill the model demonstrates beyond mere chance.
                </p>
                
                <p className="text-muted-foreground mb-4">
                  <strong className="text-foreground">The Takeaway: Raw Accuracy is Meaningless in Isolation.</strong> Interpreting any accuracy score <em>requires</em> understanding this baseline for the specific prediction task. Without this critical context, raw accuracy numbers can be deeply misleading. To truly evaluate a model, we must first grasp the concept of chance agreement relevant to the task.
                </p>
              </div>

              <div> <h3 className="text-xl font-medium mb-2">Solution: Adding Context to Accuracy</h3>

            <p className="text-muted-foreground mt-6 mb-4">
              To address this, context can be added to the raw accuracy metric. One way to do this is by dynamically adjusting the visual representation of the accuracy gauge based on the problem's characteristics. For example, the number of classes significantly impacts the baseline random-chance agreement. A 50% accuracy means something very different for a 2-class problem than for a 12-class problem. By visualizing this context directly on the gauge, the raw accuracy number can be made more interpretable.
            </p>

            <p className="text-muted-foreground mt-2 mb-4">
                By calculating a "chance level" or baseline for a specific dataset, the gauge's colors can visually indicate whether the achieved accuracy is substantially better than random guessing, just slightly better, or even close to what chance would predict. For example, 75% accuracy might look very different on a gauge for a 2-class balanced problem (50% chance) versus a 4-class balanced problem (25% chance). This contextual scaling helps in interpreting the raw number more effectively.
              </p>
              
              <p className="text-muted-foreground mb-4">
                The first approach is to retain raw accuracy but enhance its interpretability by providing crucial context. This is achieved by using dynamic visual scales on Accuracy gauges. This means the background colors and threshold markers on the Accuracy gauge adapt based on the data's characteristics – specifically, the number of classes and the distribution of items among those classes.
              </p>
 

              {/* Coin Flip Example Card */}
              <EvaluationCard
                title="Coin Flip Prediction (50/50)"
                subtitle="A fair coin has a 50% chance of heads or tails. Random guessing achieves about 50% accuracy (this run: 48%)."
                classDistributionData={fairCoinDistribution}
                isBalanced={true}
                accuracy={50}
                variant="default"
                notes="Without context (left gauge), the 50% accuracy has no meaning. With proper contextual segments (right gauge), 
                we can see that 50% is exactly at the chance level for a balanced binary problem, indicating no prediction skill."
              />

              {/* Card Suit Example Card */}
              <EvaluationCard
                title="Card Suit Prediction (25/25/25/25)"
                subtitle="A standard deck has four equally likely suits. Random guessing achieves 25% accuracy. This run: 23%."
                classDistributionData={cardSuitActualDistribution}
                isBalanced={true}
                accuracy={25}
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
              
            </div>

            <div className="my-8 p-6 rounded-lg">
              <h3 className="text-xl font-semibold mb-6 text-center">Visualizing Context: Impact of Number of Classes on Accuracy Interpretation</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
                {/* Column 1: Binary (2-Class) */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Binary</h4>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">No Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={[{ start: 0, end: 100, color: 'var(--gauge-inviable)' }]} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">With Class Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={dynamicSegments2Class} />
                  </div>
                </div>

                {/* Column 2: Ternary (3-Class) */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Ternary</h4>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">No Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={[{ start: 0, end: 100, color: 'var(--gauge-inviable)' }]} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">With Class Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={dynamicSegments3Class} />
                  </div>
                </div>

                {/* Column 3: 4-Class */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Four-Class</h4>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">No Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={[{ start: 0, end: 100, color: 'var(--gauge-inviable)' }]} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">With Class Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={dynamicSegments4Class} />
                  </div>
                </div>
                
                {/* Column 4: 12-Class */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Twelve-Class</h4>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">No Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={[{ start: 0, end: 100, color: 'var(--gauge-inviable)' }]} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">With Class Context</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={dynamicSegments12Class} />
                  </div>
                </div>
              </div>
            </div>


            <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
                <h4 className="text-lg font-semibold mb-2">Key Insight: Context is Essential</h4>
              <p className="text-muted-foreground mb-3">
                  These examples demonstrate a critical point: <strong className="text-foreground">you cannot interpret accuracy numbers without understanding the context</strong> - specifically:
                </p>
                <ul className="list-disc pl-6 space-y-2 mb-3 text-muted-foreground">
                  <li>The number of possible classes (2, 4, or more)</li>
                  <li>The baseline accuracy from random guessing</li>
              </ul>
                <p className="text-muted-foreground">
                  A 65% accuracy score might be weak for a binary classifier but strong performance for a 4-class problem. Without this context, raw accuracy numbers are essentially meaningless.
              </p>
            </div>
            
            {/* Our Article Topic Labeler revisited with class count context */}
            <div className="my-8">
              <h3 className="text-xl font-medium mb-4">Revisiting Our Article Topic Labeler</h3>
              <p className="text-muted-foreground mb-6">
                Remember our Article Topic Labeler from the beginning? Let's apply what we've learned about multiple classes to understand its performance better. With five classes (News, Sports, Business, Technology, and Lifestyle), the baseline random guessing accuracy would be just 20% if the classes were equally distributed. This completely changes how we should interpret that 62% accuracy.
              </p>
              
              <EvaluationCard
                title="Article Topic Labeler - With Class Count Context"
                                  subtitle="The same 5-class classifier with 62% accuracy, now with proper context for interpretation"
                classDistributionData={articleTopicLabelerClassDistribution}
                isBalanced={false}
                accuracy={articleTopicLabelerExampleData.accuracy}
                confusionMatrixData={articleTopicLabelerConfusionMatrix}
                predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
                variant="default"
                accuracyGaugeSegments={articleTopicLabelerClassCountOnlySegments}
                notes="Without context (left gauge), 62% accuracy seems mediocre. With contextual segments (right gauge) that account for the 5-class nature of the problem, the same 62% accuracy is revealed to be excellent performance! It's triple the 20% random chance baseline for a 5-class problem and falls well into the 'great' segment of the gauge."
              />
              
              <p className="text-muted-foreground mt-4 mb-4">
                What a difference context makes! The dynamic gauge segments show that for a 5-class problem with balanced classes (where random guessing would yield 20% accuracy), our model's 62% accuracy actually represents excellent performance. What initially appeared mediocre is now revealed to be quite impressive. The contextual gauge visualization makes this clear by shifting the colored segments to reflect the 5-class nature of the problem. In this view, we're only factoring in the number of classes, not yet accounting for their imbalanced distribution.
              </p>
            </div>

          </div>
        </section>

        <section>
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
                              accuracy={52}
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
                              accuracy={62}
              variant="oneGauge"
              disableAccuracySegments={true}
              gaugeDescription={
                <p className="text-sm">
                  <strong>Better than random guessing, but still no skill:</strong> By matching the known distribution, your accuracy jumps to around 62.5% (0.75×0.75 + 0.25×0.25 = 0.625). This appears better than 50% random guessing, but you're still not demonstrating any card-specific prediction skill—you're just exploiting knowledge of the overall distribution. Gwet's AC1 would still be near 0.
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
                    <strong>No real insight:</strong> Gwet's AC1 would be 0.0, correctly showing that you have no predictive ability beyond exploiting the class distribution.
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
              If someone says that a model has 97% accuracy, they're not really telling you anything about the model's performance.  You need to know the context of the task to understand what that means.
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
            </div>

            <div className="mt-8">
              <h3 className="text-xl font-medium mb-2">Another Solution: Adding Class Balance Context to Accuracy</h3>
              <p className="text-muted-foreground mb-4">
                Let's revisit our examples with a different approach: adjusting the accuracy gauge to account for class imbalance. When classes are imbalanced, 
                the gauge thresholds should shift to reflect what's actually achievable by simple strategies like "always guess the majority class."
              </p>
              
              <div className="mt-6 mb-8 p-5">
                <h4 className="text-lg font-medium mb-3 text-center">Visualizing the Impact of Context Adjustment</h4>
                <p className="text-muted-foreground mb-4">
                  Consider our stacked deck example where 75% of cards are red and 25% are black. With this imbalanced distribution, a raw accuracy of 75% has a different meaning than it would with balanced classes. When we adapt the gauge segments to account for the underlying class distribution, we can better represent what different accuracy levels mean in this specific context.
                </p>
                <p className="text-muted-foreground mb-4">
                  By adjusting the visual gauge thresholds based on the class distribution, we provide vital context that helps interpret accuracy numbers. In imbalanced scenarios, these adjusted segments help show the relative performance compared to what would be expected given the specific data distribution.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Left column - Standard fixed segments */}
                  <div className="p-4 bg-card rounded-md">
                    <h5 className="text-base font-medium mb-2 text-center">Without Class Distribution Context</h5>
                    <p className="text-sm text-muted-foreground mb-4 text-center">
                      Standard fixed gauge segments (0-60: poor, 60-70: converging, 70-80: almost, 80-90: viable, 90-100: great)
                    </p>
                    
                    <div className="w-full max-w-[200px] mx-auto">
                      <Gauge
                        title="Accuracy"
                        value={75.0}
                        segments={fixedAccuracyGaugeSegments}
                        showTicks={true}
                      />
                    </div>
                    
                    <p className="text-sm text-muted-foreground mt-4">
                      <strong>Incorrect Interpretation:</strong> 75% accuracy appears to be "almost viable" performance, suggesting the classifier has some skill.
                    </p>
                  </div>
                  
                  {/* Right column - Class distribution adjusted segments */}
                  <div className="p-4 bg-card rounded-md">
                    <h5 className="text-base font-medium mb-2 text-center">With Class Distribution Context</h5>
                    <p className="text-sm text-muted-foreground mb-4 text-center">
                      Dynamically adjusted segments based on class distribution (75% red, 25% black)
                    </p>
                    
                    <div className="w-full max-w-[200px] mx-auto">
                      <Gauge
                        title="Accuracy"
                        value={75.0}
                        segments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Red': 75, 'Black': 25 }))}
                        showTicks={true}
                      />
                    </div>
                    
                    <p className="text-sm text-muted-foreground mt-4">
                      <strong>Correct Interpretation:</strong> 75% accuracy is shown to be at the "chance" level - exactly what you'd expect from always guessing the majority class.
                    </p>
                  </div>
                </div>
                

              </div>
              
              {/* Stacked deck example with contextual segments */}
              <EvaluationCard
                title="Guessing Stacked Card Decks - With Class Balance Context"
                subtitle="Same scenario: a stacked deck with 75% red cards where we always guess 'Red'. But now with contextual gauge segments."
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
                disableAccuracySegments={false}
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Red': 39, 'Black': 13 }))}
                gaugeDescription={
                  <>
                    <p className="text-sm">
                      <strong>Context is everything:</strong> With contextual gauge segments that account for the 75/25 class imbalance, the gauge now 
                      correctly shows that this 75% accuracy is merely at the "chance" level - exactly what you'd expect from always guessing the majority class.
                    </p>
                    
                    <p className="mt-2 text-sm">
                      Notice how the colored segments have shifted to reflect that 75% is actually the minimum expected accuracy for this imbalanced distribution.
                    </p>                  
                  </>
                }
              />

              {/* Email content moderation example with contextual segments */}
              <div className="mt-8">
                <EvaluationCard
                  title="The &quot;Always Safe&quot; Email Filter - With Class Balance Context"
                  subtitle="Same 'Always Safe' content filter with 97% accuracy, but now with contextual gauge segments"
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
                  disableAccuracySegments={false}
                  accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Safe': 970, 'Prohibited': 30 }))}
                  gaugeDescription={
                    <>
                      <p className="text-sm">
                        <strong>Exposed as meaningless:</strong> With contextual gauge segments, the 97% accuracy is now shown to be precisely at 
                        the "chance" level - exactly what you'd get by always predicting "Safe" given the 97/3 class distribution.
                      </p>
                      
                      <div className="p-3 bg-amber-100 dark:bg-amber-900/40 rounded-md mt-4">
                        <p className="text-sm font-medium">Notice the gauge segments</p>
                        <p className="text-xs mt-1">
                          The colored segments are compressed to the right side of the gauge, showing that with this extreme imbalance, 
                          even 97% accuracy is at the bare minimum expected by chance. Any meaningful performance would need to exceed this baseline.
                        </p>
                      </div>                  
                    </>
                  }
                />
              </div>
              
              <p className="text-muted-foreground mt-6 mb-6">
                These examples demonstrate how adding class distribution context to accuracy gauges transforms our interpretation. 
                What initially appeared to be good performance (75% accuracy in one case, 97% in another) is revealed to be merely at the baseline 
                chance level once we account for the imbalanced distribution of classes. The gauge segments shift accordingly, showing that 
                genuinely good performance requires exceeding what simple strategies like "always guess the majority class" would achieve.
              </p>
              
              {/* Third instance of Article Topic Labeler - Now with both class count and imbalance context */}
              <div className="my-8">
                <h3 className="text-xl font-medium mb-4">Article Topic Labeler: Accounting for Class Imbalance</h3>
                <p className="text-muted-foreground mb-6">
                  Let's revisit our Article Topic Labeler once more. We've already seen how its 62% accuracy looks excellent when considering that it's a 5-class problem. But not so fast—we also need to account for the fact that our dataset is imbalanced—40% of the articles are "News," while the other categories each represent just 15% of the data.
                </p>
                
                <p className="text-muted-foreground mb-4">
                  Given this imbalance, simply guessing "News" for every article would achieve 40% accuracy—far better than the 20% baseline for a balanced 5-class problem. This means the bar for truly "great" performance should be higher, and our classifier's 62% accuracy might not be as impressive as we initially thought. In this example, the gauge segments have been adjusted to account for both the number of classes AND their imbalanced distribution, resulting in a noticeably different gauge appearance than our previous example.
                </p>
                
                                 <EvaluationCard
                  title="Article Topic Labeler - With Class Imbalance Context"
                  subtitle="The same 5-class classifier with 62% accuracy, accounting for both multiple classes and class imbalance (40% News, 15% each for other categories)"
                  classDistributionData={articleTopicLabelerClassDistribution}
                  isBalanced={false}
                  accuracy={articleTopicLabelerExampleData.accuracy}
                  confusionMatrixData={articleTopicLabelerConfusionMatrix}
                  predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
                  variant="oneGauge"
                  disableAccuracySegments={false}
                  accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
                  gaugeDescription={
                    <>
                      <p className="text-sm">
                        <strong>Context-aware interpretation:</strong> With gauge segments that account for both the 5 classes and the 40/15/15/15/15 distribution, our 62% accuracy now appears good but not excellent. Notice how the gauge segments have shifted compared to our previous example - the threshold for "good" performance has increased to reflect that a naive classifier could achieve 40% just by always guessing "News".
                      </p>
                      
                      <div className="p-3 bg-amber-100 dark:bg-amber-900/40 rounded-md mt-4">
                        <p className="text-sm font-medium">A More Nuanced Picture</p>
                        <p className="text-xs mt-1">
                          While our 62% accuracy is still decent—it's better than the 40% we'd get from always predicting "News"—it's no longer in the highest performance tier once we account for the class imbalance. The threshold for "great" performance has shifted from around 60% to around 65%.
                        </p>
                      </div>
                    </>
                  }
                />
                
                <p className="text-muted-foreground mt-4 mb-4">
                  The contextual accuracy gauge now gives us a much more nuanced picture of our classifier's performance. By accounting for both the number of classes and their imbalanced distribution, we can see that 62% accuracy represents good but not exceptional performance for this specific task. It's significantly better than naive strategies, but there's room for improvement.
                </p>
              </div>
            </div>

            <div className="my-8 p-6 rounded-lg">
              <h3 className="text-xl font-semibold mb-6 text-center">Visualizing Context: Impact of Class Imbalance on Accuracy Interpretation</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
              
                {/* Column 1: 2 Classes */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Balanced</h4>
                  <p className="text-xs text-center text-muted-foreground mb-2">50/50 Distribution</p>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Fixed Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Contextual Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={imbal_scenario1_segments} />
                  </div>
                </div>

                {/* Column 2: Imbalanced 75/25 */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Imbalanced</h4>
                  <p className="text-xs text-center text-muted-foreground mb-2">75/25 Distribution</p>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Fixed Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Contextual Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={imbal_scenario2_segments} />
                  </div>
                </div>

                {/* Column 3: Imbalanced 3-Class 80/10/10 */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Imbalanced</h4>
                  <p className="text-xs text-center text-muted-foreground mb-2">80/10/10 Distribution</p>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Fixed Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Contextual Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={imbal_scenario4_segments} />
                  </div>
                </div>
                
                {/* Column 4: Highly Imbalanced 95/5 */}
                <div className="flex flex-col items-center space-y-3 p-4 bg-card rounded-md">
                  <h4 className="text-md font-medium text-center">Imbalanced</h4>
                  <p className="text-xs text-center text-muted-foreground mb-2">95/5 Distribution</p>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Fixed Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                  </div>
                  <div className="w-full">
                    <p className="text-xs text-center text-muted-foreground mb-1">Contextual Thresholds</p>
                    <AccuracyGauge value={65.0} title="Accuracy" segments={imbal_scenario3_segments} />
                  </div>
                </div>
              </div>
            </div>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold mb-4">Solution 3: The Agreement Gauge - Context-Aware by Design</h2>
              
              <p className="text-muted-foreground mb-4">
                We've discussed two approaches to make accuracy more interpretable: providing context about the number of classes and their distribution. Both approaches help users understand what a raw accuracy percentage means in specific scenarios. Now, let's explore a third solution that takes a fundamentally different approach.
              </p>

              <p className="text-muted-foreground mb-4">
                Rather than adding context to help interpret the position of the needle on a gauge, what if the gauge itself could interpret this information for you? This is exactly what the Agreement gauge in Plexus does.
              </p>

              <h3 className="text-xl font-medium mb-3">The Agreement Gauge: Standardized Interpretation</h3>
              
              <p className="text-muted-foreground mb-4">
                The Agreement gauge uses a metric (specifically Gwet's AC1) that inherently factors in both the number of classes and their distribution. This creates a standardized scale where 0.0 always means random chance agreement (equivalent to guessing randomly), 1.0 means perfect agreement (every prediction is correct), and -1.0 means perfect disagreement (every prediction is incorrect). Values between 0 and 1 indicate degrees of agreement better than chance.
              </p>
              
              <p className="text-muted-foreground mb-4">
                The beauty of this approach is its consistency. Whether you're evaluating a binary classifier, a 4-class problem, or dealing with severe class imbalance, the Agreement score always means the same thing. A score of 0.6 represents the same level of performance above chance regardless of the underlying data distribution.
              </p>
              
              {/* Three-column visualization showing the three states */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-6">
                <div className="flex flex-col items-center p-4 bg-card rounded-md">
                  <h4 className="text-xl font-semibold mb-2">Opposite</h4>
                  <div className="w-full max-w-[150px] mx-auto mb-2">
                    <Gauge
                      title="Agreement"
                      value={-1.0}
                      min={-1}
                      max={1}
                      segments={ac1GaugeSegments}
                      showTicks={false}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground text-center">
                    Perfect disagreement. Every prediction is incorrect.
                  </p>
                </div>
                
                <div className="flex flex-col items-center p-4 bg-card rounded-md">
                  <h4 className="text-xl font-semibold mb-2">Random</h4>
                  <div className="w-full max-w-[150px] mx-auto mb-2">
                    <Gauge
                      title="Agreement"
                      value={0.0}
                      min={-1}
                      max={1}
                      segments={ac1GaugeSegments}
                      showTicks={false}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground text-center">
                    No skill beyond chance. Equivalent to random guessing.
                  </p>
                </div>
                
                <div className="flex flex-col items-center p-4 bg-card rounded-md">
                  <h4 className="text-xl font-semibold mb-2">Perfect</h4>
                  <div className="w-full max-w-[150px] mx-auto mb-2">
                    <Gauge
                      title="Agreement"
                      value={1.0}
                      min={-1}
                      max={1}
                      segments={ac1GaugeSegments}
                      showTicks={false}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground text-center">
                    Perfect agreement. Every prediction is correct.
                  </p>
                </div>
              </div>

              <p className="text-muted-foreground mb-4">
                Now let's see how the random coin flip would look if we combine the Agreement gauge with an Accuracy gauge. This shows how both metrics represent the same underlying performance in different ways.
              </p>

              <div className="p-5 bg-card rounded-lg my-6">
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
              </div>

              <p className="text-muted-foreground mb-4">
                Now let's see how this works with a more complex scenario. Instead of a binary choice like a coin flip, we'll examine a 4-class problem – predicting the suit of a playing card. As we move from 2 classes to 4 classes, the baseline chance level drops from 50% to 25%. This is where the Agreement gauge really shines, as it automatically adjusts to maintain consistency across different problem types.
              </p>

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

              <p className="text-muted-foreground mb-4">
                The true power of the Agreement gauge lies in how it naturally adapts to your specific data. Like a smart GPS that reroutes when traffic conditions change, the gauge automatically recalibrates based on how many classes you have and how common each class is. It doesn't require complex calculations from the user – it simply shows whether your model is actually learning patterns or just making educated guesses. Whether you're classifying emails into two categories or medical images into dozens of different conditions, the Agreement gauge gives you a consistent way to understand performance: 0 means "no better than guessing," and 1 means "perfect predictions."
              </p>

              <h3 className="text-xl font-medium mb-3">Benefits of the Agreement Gauge</h3>
              
              <p className="text-muted-foreground mb-4">
                The Agreement gauge offers several advantages:
              </p>
              
              <ul className="list-disc pl-6 space-y-2 mb-4 text-muted-foreground">
                <li><strong className="text-foreground">Simplified Interpretation:</strong> Users don't need to mentally factor in class distribution or number of classes - the gauge does it for them</li>
                <li><strong className="text-foreground">Direct Comparability:</strong> Agreement scores can be directly compared across different classifiers and datasets</li>
                <li><strong className="text-foreground">Immediate Insight:</strong> Instantly reveals whether a classifier has actual predictive power beyond chance</li>
                <li><strong className="text-foreground">Resistance to Deception:</strong> Exposes seemingly high accuracy numbers that actually represent no real predictive skill</li>
              </ul>

              <div className="p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6 mb-4">
                <h4 className="text-lg font-semibold mb-2">Case Study: The "Always Safe" Email Filter Revisited</h4>
                <p className="text-muted-foreground mb-3">
                  Remember our email content filter that achieved 97% accuracy by simply labeling everything as "safe"? With only 3% of emails containing prohibited content, this approach produced seemingly impressive accuracy.
                </p>
                <p className="text-muted-foreground mb-3">
                  However, the Agreement gauge would immediately expose this strategy, showing a score of exactly 0.0. This instantly reveals that the classifier has zero predictive skill beyond random chance, regardless of its high raw accuracy.
                </p>
                <p className="text-muted-foreground">
                  This illustrates the power of an inherently context-aware metric - it cuts through potentially misleading accuracy numbers to reveal the true performance relative to what would be expected by chance.
                </p>
              </div>

              {/* Always Red Example - Using EvaluationCard */}
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
                notes="Despite achieving 75% accuracy (which sounds impressive), the Agreement gauge correctly shows AC1 = 0.00, indicating no predictive skill beyond chance. By always guessing 'red' for all cards in a deck that's 75% red, we match the majority class percentage but demonstrate zero discriminative ability."
              />
              
              {/* Email Content Filter Example - Using EvaluationCard */}
              <EvaluationCard
                title="The &quot;Always Safe&quot; Email Filter - With Both Gauges"
                subtitle="A content filter that labels all emails as 'safe' in a dataset where only 3% contain prohibited content."
                classDistributionData={[
                  { label: "Safe", count: 970 },
                  { label: "Prohibited", count: 30 }
                ]}
                isBalanced={false}
                accuracy={97.0}
                gwetAC1={0.0}
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
                showBothGauges={true}
                variant="default"
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Safe': 970, 'Prohibited': 30 }))}
                notes="The extremity of this example makes it particularly powerful. Despite a seemingly impressive 97% accuracy, both gauges reveal the truth: this model has zero predictive skill. The Agreement gauge shows AC1 = 0.0, and the contextual Accuracy gauge shows that 97% is exactly at the baseline chance level for this highly imbalanced distribution. This filter catches none of the prohibited content, making it worse than useless."
              />
              
              <p className="text-muted-foreground mt-4 mb-6">
                The Agreement gauge provides a more intuitive measure of classifier performance, especially for users without extensive machine learning expertise. Instead of requiring users to interpret accuracy in the context of baseline chance rates and class distributions, it directly shows how much better (or worse) than chance the classifier performs.
              </p>
              
              {/* Fourth and final instance of Article Topic Labeler - Now with both gauges */}
              <div className="my-8">
                <h3 className="text-xl font-medium mb-4">Our Article Topic Labeler: The Complete Picture</h3>
                <p className="text-muted-foreground mb-6">
                  Let's complete our journey with the Article Topic Labeler. We've seen how adding context dramatically changed our interpretation of its 62% accuracy—from seemingly mediocre, to excellent when considering the 5-class nature, and back to "good but not great" when factoring in class imbalance. Now, let's see how the Agreement gauge adds even more interpretability.
                </p>
                
                <EvaluationCard
                  title="Article Topic Labeler - With Both Gauges"
                  subtitle="Our 5-class imbalanced classifier with 62% accuracy, now showing both the contextualized Accuracy gauge and the Agreement gauge"
                  classDistributionData={articleTopicLabelerClassDistribution}
                  isBalanced={false}
                  accuracy={articleTopicLabelerExampleData.accuracy}
                  gwetAC1={articleTopicLabelerExampleData.gwetAC1}
                  confusionMatrixData={articleTopicLabelerConfusionMatrix}
                  predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
                  showBothGauges={true}
                  variant="default"
                  accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
                  notes="The Agreement gauge (AC1 = 0.512) immediately shows moderate agreement beyond chance, providing a nuanced view of our classifier's performance. It inherently accounts for both the 5-class nature and the 40/15/15/15/15 distribution. The gauge confirms what our contextualized accuracy gauge showed: the classifier is performing reasonably well, but there's definite room for improvement."
                />
                
                <p className="text-muted-foreground mt-4 mb-4">
                  The Agreement gauge (AC1 = 0.512) instantly provides a clear assessment: our Article Topic Labeler demonstrates moderate predictive skill. This score shows that the classifier performs notably better than chance, but isn't achieving the highest levels of agreement. The Agreement gauge has internally adjusted for both the number of classes and their distribution, providing a single, comparable measure of performance.
                </p>
                
                <p className="text-muted-foreground mb-4">
                  While the contextualized Accuracy gauge is helpful, the Agreement gauge offers the most straightforward interpretation: a value of 0.512 on a scale from -1 to 1 indicates moderate agreement beyond what would be expected by chance. This aligns with our final interpretation of the accuracy—the classifier is performing reasonably well, but there's room for improvement. The Agreement gauge delivers this insight in a single, easily interpretable number.
                </p>
              </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">A Unified Approach to Evaluation Clarity</h2>
          <p className="text-muted-foreground mb-4">
            Interpreting raw accuracy scores like "75% accurate" is challenging without considering crucial context, primarily the number of classes and their distribution within the data. Plexus advocates for a unified, multi-faceted approach to bring clarity to classifier performance. This approach combines strategies that work in tandem:
          </p>
          <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
            <li>
              <strong className="text-foreground">Enhancing Raw Accuracy's Interpretability:</strong> We provide essential context directly to the raw accuracy metric. This is done by dynamically adjusting the visual scales (colors and thresholds) of the Accuracy gauge based on both the number of classes and the class distribution. This strategy, detailed first below, makes the raw accuracy number itself more immediately understandable.
            </li>
            <li>
              <strong className="text-foreground">Employing an Inherently Context-Aware Agreement Metric:</strong> Alongside the contextualized Accuracy gauge, we introduce a distinct "Agreement" metric, such as Gwet's AC1. This type of metric is designed to <em>internally</em> account for the complexities of chance agreement, the number of classes, and their distribution. This second strategy, also detailed below, provides a stable, chance-corrected perspective that is directly comparable across different evaluation scenarios.
            </li>
          </ol>
          <p className="text-muted-foreground mb-4">
            By using these strategies together—presenting both a contextualized Accuracy gauge and a self-contextualizing Agreement gauge—Plexus offers a comprehensive and robust understanding of classifier performance. The following sections detail each of these complementary strategies.
          </p>

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
            Gwet's AC1 Agreement gauge, on the other hand, adapts to the number of classes in a different but equally powerful way. The AC1 calculation inherently accounts for chance agreement based on the number of classes and their distribution. This means Gwet's AC1 itself (ranging from -1 to 1) can be interpreted consistently: a score of 0.0 always indicates performance no better than chance, 1.0 indicates perfect agreement, and values in between (e.g., 0.2-0.4 for fair, 0.4-0.6 for moderate, 0.6-0.8 for substantial, 0.8-1.0 for almost perfect agreement) carry a similar meaning regardless of whether you have two, three, or ten classes. This consistency makes the Agreement gauge a very reliable indicator of true classifier skill, corrected for chance.
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
            Gwet's AC1 Agreement gauge proves especially invaluable for imbalanced datasets. Because it inherently corrects for chance agreement that arises from the specific class distribution (no matter how skewed), Gwet's AC1 provides a stable and reliable measure of a classifier's ability to agree with true labels beyond what random chance would produce for that particular imbalance. For instance, if a model achieves a high Gwet's AC1 on an imbalanced dataset, it indicates genuine skill in distinguishing between classes, including the rarer ones. Conversely, as we will see in the \"Always No\" example, a strategy that yields high raw accuracy by ignoring the minority class will correctly result in a Gwet's AC1 of 0.0, exposing its lack of true predictive power across the full spectrum of classes.
          </p>
          {/* Binary classifier, imbalanced (5% \"Yes\" prevalence), 90/100 correct */}
          {(() => {
            const scoreData = { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'Yes': 5, 'No': 95 } };
            const gwetAC1 = 0.401; // Calculated: (0.90 - ((0.05×0.13)+(0.95×0.87))) / (1 - ((0.05×0.13)+(0.95×0.87)))
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
            const gwetAC1 = 0.819; // Calculated: (0.90 - Pe) / (1-Pe) where Pe = (0.05×0.07) + (0.45×0.44) + (0.50×0.49) = 0.4465
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
            const gwetAC1 = 0.843; // Calculated: (0.90 - Pe) / (1-Pe) where Pe = (0.05×0.06) + (0.15×0.15) + (0.30×0.29) + (0.50×0.50) = 0.3625
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
            Now that you understand how to interpret these agreement gauges, explore related concepts
            to get the most out of your evaluation data.
          </p>
          <div className="flex gap-4">
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