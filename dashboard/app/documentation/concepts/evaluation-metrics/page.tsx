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
    'Fair Coin Prediction (50/50)',
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
    'Always Guessing "Heads" (75/25)',
    0.0,
    75.0,
    100,
    25,
    { 'Heads': 75, 'Tails': 25 }
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
    { label: "Heads", count: 52 }, // Slightly favoring heads in predictions
    { label: "Tails", count: 48 }
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

  // Fair coin confusion matrix data - showing the 58% accuracy
  const fairCoinConfusionMatrix = {
    matrix: [
      [30, 22], // Predicted Heads, actual [Heads, Tails]
      [20, 28], // Predicted Tails, actual [Heads, Tails]
    ],
    labels: ["Heads", "Tails"],
  };
  
  // Weighted coin confusion matrix
  const weightedCoinConfusionMatrix = {
    matrix: [
      [60, 18], // Predicted Heads, actual [Heads, Tails]
      [15, 7],  // Predicted Tails, actual [Heads, Tails]
    ],
    labels: ["Heads", "Tails"],
  };
  
  // Always heads confusion matrix
  const alwaysHeadsConfusionMatrix = {
    matrix: [
      [75, 25], // Predicted Heads, actual [Heads, Tails]
      [0, 0],   // Predicted Tails, actual [Heads, Tails]
    ],
    labels: ["Heads", "Tails"],
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
    matrix: [
      [3,3,3,4], // Actual H: Pred H,D,C,S
      [3,3,4,3], // Actual D: Pred H,D,C,S
      [3,4,3,3], // Actual C: Pred H,D,C,S
      [4,3,3,3], // Actual S: Pred H,D,C,S
    ],
    labels: ["♥️", "♦️", "♣️", "♠️"],
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
    matrix: [
      [10, 10, 10, 9],  // Actual Hearts, Predicted H,D,C,S (each ~25% of 39)
      [1, 2, 1, 1],     // Actual Diamonds, Predicted H,D,C,S (each ~25% of 5)
      [1, 1, 1, 1],     // Actual Clubs, Predicted H,D,C,S (each ~25% of 4)
      [1, 1, 1, 1]      // Actual Spades, Predicted H,D,C,S (each ~25% of 4)
    ],
    labels: ["♥️", "♦️", "♣️", "♠️"],
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
    matrix: [
      [39, 0, 0, 0],  // Actual Hearts, all predicted as Hearts (correct)
      [5, 0, 0, 0],   // Actual Diamonds, all predicted as Hearts (wrong)
      [4, 0, 0, 0],   // Actual Clubs, all predicted as Hearts (wrong)
      [4, 0, 0, 0]    // Actual Spades, all predicted as Hearts (wrong)
    ],
    labels: ["♥️", "♦️", "♣️", "♠️"],
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
            Let's start with a simple game: predicting coin flips. Imagine someone flips a coin 100 times, and your job is to predict each outcome before it happens. 
            Since a fair coin has an equal chance of landing heads or tails, your best strategy might be to make random guesses. As you make more and more predictions, 
            your success rate should approach 50% - you'll be right about half the time, purely by chance.
          </p>
          
          <div className="space-y-8 mb-8">
            {/* Fair coin flip example */}
            <Card className="border-none shadow-none bg-card">
              <CardContent className="pt-6">
                <h3 className="text-xl font-medium mb-2">Predicting a Fair Coin</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  You're asked to predict 100 flips of a fair coin, where heads and tails are equally likely (50/50 chance). After making your predictions, you find you were correct for 58 flips - a 58% accuracy rate.
                </p>
                <div className="flex flex-col md:flex-row gap-6 items-start">
                  <div className="w-full md:w-1/2 space-y-4">
                    <div>
                      <ClassDistributionVisualizer data={fairCoinDistribution} isBalanced={true} />
                    </div>
                    
                    <div className="bg-card/50 rounded-md p-2">
                      <ConfusionMatrix data={fairCoinConfusionMatrix} />
                    </div>
                    
                    <div>
                      <PredictedClassDistributionVisualizer data={predictedFairCoinData} />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <p className="text-sm text-muted-foreground mb-2 text-center">
                      You achieved 58% accuracy:
                    </p>
                    <div className="max-w-[180px] mx-auto">
                      <AccuracyGauge value={fairCoinData.accuracy} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                    </div>
                    
                    <p className="text-sm mt-6">
                      <strong>Slightly better than chance:</strong> With a fair coin, your 58% accuracy is just slightly better than the 50% you'd expect from pure random guessing. This suggests you might have some very minimal insight into predicting this particular coin's behavior, but you're still not far from what luck would give you.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <p className="text-muted-foreground mb-6">
              This 50% represents what we call the <strong className="text-foreground">base random-chance agreement rate</strong> - the accuracy you would expect from pure guessing. 
              Any accuracy above this baseline suggests you have some actual insight or pattern recognition happening. 
            </p>
            
            <h3 className="text-xl font-medium mb-3">Complication: More than two classes</h3>
            <p className="text-muted-foreground mb-6">
              But what happens when we introduce a few twists into our simple game?
            </p>

            {/* === START OF NEW Card Suit Guessing Example - Demonstrating 25% Baseline === */}
            <Card className="border-none shadow-none bg-card">
              <CardContent className="pt-6">
                <h3 className="text-xl font-medium mb-2">Predicting Card Suits: Baseline Shifts to 25%</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Now, let's see what happens with four equally likely outcomes. You're asked to predict the suit (♥️ Hearts, ♦️ Diamonds, ♣️ Clubs, or ♠️ Spades) of a standard 52-card deck. Each suit has an equal 25% chance with 13 cards of each suit.
                  You make your 52 predictions by purely guessing, and, as expected, you get about 13 correct – a 25% accuracy rate.
                </p>
                <div className="flex flex-col md:flex-row gap-6 items-start">
                  <div className="w-full md:w-1/2 space-y-4">
                    <div>
                      <ClassDistributionVisualizer data={cardSuitActualDistribution} isBalanced={true} />
                    </div>
                    <div className="bg-card/50 rounded-md p-2">
                      <ConfusionMatrix data={cardSuitConfusionMatrix} />
                    </div>
                    <div>
                      <PredictedClassDistributionVisualizer data={cardSuitPredictedDistribution} />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <p className="text-sm text-muted-foreground mb-2 text-center">
                      You achieved 25% accuracy:
                    </p>
                    <div className="max-w-[180px] mx-auto">
                      <AccuracyGauge value={cardSuitData.accuracy} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                    </div>
                    <p className="text-sm mt-6">
                      <strong>Exactly at chance:</strong> With four equally likely suits, purely random guessing yields 25% accuracy. This means your performance is exactly at the baseline, and Gwet's AC1 score would be 0.0, indicating no predictive skill beyond chance.
                    </p>
                    
                    <div className="mt-4 p-3 bg-destructive rounded-md">
                      <p className="text-base font-bold text-white">Misleading Accuracy</p>
                      <p className="text-sm mt-1 text-white">
                        The gauge shows 25% near the bottom of the scale, suggesting poor performance. For a 4-class problem, 25% is actually the baseline random chance level. The fixed gauge incorrectly implies below-chance performance when you're precisely at the chance level.
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <p className="text-muted-foreground mb-6">
              Notice how the baseline random-chance agreement rate dropped from 50% with two choices (Heads/Tails) to 25% with four choices (Hearts/Diamonds/Clubs/Spades). This is a key concept: as the number of equally likely options increases, the accuracy you'd expect from random guessing decreases.
            </p>
            {/* === END OF NEW Card Suit Guessing Example === */}

            {/* === START OF NEW Stacked Deck Examples (Color Version) === */}
            <h3 className="text-xl font-medium mb-3">Complication: Class imbalance</h3>
            <p className="text-muted-foreground mb-6">
              And there's a second factor that can confuse the interpretation of raw accuracy: the distribution of the classes in the actual data.
            </p>
            <p className="text-muted-foreground mb-6">
              Let's explore this with a simpler binary prediction task: guessing the color of playing cards (red or black) instead of specific suits. But this time, our deck is stacked — 75% of the cards are red (hearts and diamonds) and only 25% are black (clubs and spades). With this imbalance, seemingly high accuracy can be achieved with no real skill, just by exploiting the distribution.
            </p>

            {/* First stacked deck example - Random guessing with colors */}
            <Card className="border-none shadow-none bg-card mb-8">
              <CardContent className="pt-6">
                <h3 className="text-xl font-medium mb-2">Strategy 1: Random Guessing (50/50)</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  If you simply guess red or black with equal probability (50/50) for each card in our stacked deck, you'd still expect around 50% accuracy, regardless of the deck's imbalance. This strategy doesn't exploit or account for the skewed distribution.
                </p>
                <div className="flex flex-col md:flex-row gap-6 items-start">
                  <div className="w-full md:w-1/2 space-y-4">
                    <div>
                      <ClassDistributionVisualizer 
                        data={[
                          { label: "Red", count: 39 },
                          { label: "Black", count: 13 }
                        ]} 
                        isBalanced={false} 
                      />
                    </div>
                    <div className="bg-card/50 rounded-md p-2">
                      <ConfusionMatrix 
                        data={{
                          matrix: [
                            [29, 10], // Predicted Red, actual [Red, Black]
                            [10, 3],   // Predicted Black, actual [Red, Black]
                          ],
                          labels: ["Red", "Black"],
                        }} 
                      />
                    </div>
                    <div>
                      <PredictedClassDistributionVisualizer 
                        data={[
                          { label: "Red", count: 26 },
                          { label: "Black", count: 26 }
                        ]} 
                      />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <p className="text-sm text-muted-foreground mb-2 text-center">
                      You achieved 52% accuracy:
                    </p>
                    <div className="max-w-[180px] mx-auto">
                      <AccuracyGauge value={52.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                    </div>
                    <p className="text-sm mt-6">
                      <strong>Still at basic chance level:</strong> Even with a stacked deck (75% red cards), random 50/50 guessing still gives you about 50% accuracy. This matches the baseline for a balanced binary prediction task. Your random strategy doesn't exploit the imbalance in the deck.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* NEW: Matching distribution example */}
            <Card className="border-none shadow-none bg-card mb-8">
              <CardContent className="pt-6">
                <h3 className="text-xl font-medium mb-2">Strategy 2: Matching the Known Distribution (75/25)</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Now suppose someone tells you that 75% of the cards are red. You could "cheat" by matching your guessing pattern to this distribution—guessing "red" 75% of the time and "black" 25% of the time, while still randomly assigning these guesses to specific cards.
                </p>
                <div className="flex flex-col md:flex-row gap-6 items-start">
                  <div className="w-full md:w-1/2 space-y-4">
                    <div>
                      <ClassDistributionVisualizer 
                        data={[
                          { label: "Red", count: 39 },
                          { label: "Black", count: 13 }
                        ]} 
                        isBalanced={false} 
                      />
                    </div>
                    <div className="bg-card/50 rounded-md p-2">
                      <ConfusionMatrix 
                        data={{
                          matrix: [
                            [25, 25], // Actual Heads: 25 Pred H, 25 Pred T
                            [27, 23], // Actual Tails: 27 Pred H, 23 Pred T
                          ],
                          labels: ["Heads", "Tails"],
                        }} 
                      />
                    </div>
                    <div>
                      <PredictedClassDistributionVisualizer 
                        data={[
                          { label: "Red", count: 39 },
                          { label: "Black", count: 13 }
                        ]} 
                      />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <p className="text-sm text-muted-foreground mb-2 text-center">
                      You achieved 62% accuracy:
                    </p>
                    <div className="max-w-[180px] mx-auto">
                      <AccuracyGauge value={62.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                    </div>
                    <p className="text-sm mt-6">
                      <strong>Better than random guessing, but still no skill:</strong> By matching the known distribution, your accuracy jumps to around 62.5% (0.75×0.75 + 0.25×0.25 = 0.625). This appears better than 50% random guessing, but you're still not demonstrating any card-specific prediction skill—you're just exploiting knowledge of the overall distribution. The AC1 score would still be near 0.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Second stacked deck example - Always guessing red */}
            <Card className="border-none shadow-none bg-card mb-6">
              <CardContent className="pt-6">
                <h4 className="text-xl font-medium mb-3">Always Guessing Red (75/25 Stacked Deck)</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  The most extreme "cheating" strategy is simply to always guess the majority class. With 75% red cards in the deck, if you guess "Red" for every single card, you'll automatically get 75% accuracy without any genuine predictive ability.
                </p>
                
                <div className="flex flex-col md:flex-row gap-6 items-start">
                  <div className="w-full md:w-1/2 space-y-4">
                    <div>
                      <ClassDistributionVisualizer 
                        data={[
                          { label: "Red", count: 39 },
                          { label: "Black", count: 13 }
                        ]} 
                        isBalanced={false} 
                      />
                    </div>
                    <div className="bg-card/50 rounded-md p-2">
                      <ConfusionMatrix 
                        data={{
                          matrix: [
                            [39, 0],  // Actual Red: 39 predicted as Red, 0 as Black
                            [13, 0],  // Actual Black: 13 predicted as Red, 0 as Black
                          ],
                          labels: ["Red", "Black"],
                        }} 
                      />
                    </div>
                    <div>
                      <PredictedClassDistributionVisualizer 
                        data={[
                          { label: "Red", count: 52 },
                          { label: "Black", count: 0 }
                        ]} 
                      />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <p className="text-sm text-muted-foreground mb-2 text-center">
                      You achieved 75% accuracy:
                    </p>
                    <div className="max-w-[180px] mx-auto">
                      <AccuracyGauge 
                        value={75.0} 
                        title="Accuracy" 
                        segments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }))} 
                      />
                    </div>
                    <p className="text-sm mt-6">
                      <strong>Misleading accuracy with no skill:</strong> By always guessing "Red", you achieve 75% accuracy - exactly matching the percentage of red cards in the deck. Despite appearing high, this represents zero predictive skill. You're simply exploiting the imbalanced distribution by always choosing the majority class. The AC1 score would be 0.0, correctly showing no real predictive ability.
                    </p>
                    <div className="mt-4 p-3 bg-destructive rounded-md">
                      <p className="text-base font-bold text-white">Misleading Accuracy</p>
                      <p className="text-sm mt-1 text-white">
                        This 75% accuracy appears well above the 50% baseline for a binary classifier. But this is misleading! With a 75/25 class imbalance, simply always predicting the majority class achieves 75% accuracy with zero skill. The context-aware gauge properly shows this as merely achieving the baseline level expected by chance.
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* NEW: Email Prohibited Language Detection Example */}
            <h3 className="text-xl font-medium mb-3 mt-8">Real-world Example: Content Moderation in Email</h3>
            <p className="text-muted-foreground mb-6">
              Let's examine an extreme but common real-world scenario: detecting prohibited language in emails. In most business environments, legitimate prohibited content is rare—occurring in only about 3% of all communications. This severe class imbalance creates a dangerous situation where meaningless classifiers can appear highly effective.
            </p>
            
            <Card className="border-none shadow-none bg-card">
              <CardContent className="pt-6">
                <h3 className="text-xl font-medium mb-2">The "Always Safe" Email Filter</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Imagine you're evaluating an email filtering system that claims 97% accuracy in detecting prohibited content. Sounds impressive! But upon investigation, you discover it achieves this by simply labeling <strong>every single email</strong> as "safe" regardless of content. With only 3% of emails actually containing prohibited content, this trivial classifier achieves 97% accuracy while catching exactly zero violations.
                </p>
                <div className="flex flex-col md:flex-row gap-6 items-start">
                  <div className="w-full md:w-1/2 space-y-4">
                    <div>
                      <ClassDistributionVisualizer 
                        data={[
                          { label: "Safe", count: 970 },
                          { label: "Prohibited", count: 30 }
                        ]} 
                        isBalanced={false} 
                      />
                    </div>
                    <div className="bg-card/50 rounded-md p-2">
                      <ConfusionMatrix 
                        data={{
                          matrix: [
                            [970, 30], // Predicted Safe, actual [Safe, Prohibited]
                            [0, 0],    // Predicted Prohibited, actual [Safe, Prohibited]
                          ],
                          labels: ["Safe", "Prohibited"],
                        }} 
                      />
                    </div>
                    <div>
                      <PredictedClassDistributionVisualizer 
                        data={[
                          { label: "Safe", count: 1000 },
                          { label: "Prohibited", count: 0 }
                        ]} 
                      />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <p className="text-sm text-muted-foreground mb-2 text-center">
                      The model achieved 97% accuracy:
                    </p>
                    <div className="max-w-[180px] mx-auto">
                      <AccuracyGauge value={97.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                    </div>
                    <div className="mt-4 p-3 bg-destructive rounded-md">
                      <p className="text-base font-bold text-white">CRITICAL FLAW</p>
                      <p className="text-sm mt-1 text-white">
                        This 97% accuracy is dangerously misleading! The model failed to detect ANY prohibited content (0% recall for violations). It simply labels everything as "safe" and benefits from the extreme class imbalance. This is worse than useless—it's a false sense of security.
                      </p>
                      <p className="text-sm mt-2 text-white">
                        The AC1 score would be 0.0, correctly showing no predictive ability beyond chance.
                      </p>
                    </div>
                    <p className="text-sm mt-4">
                      <strong>Business Impact:</strong> In security-sensitive contexts like content moderation, missing all true violations (0% recall) is catastrophic, regardless of overall accuracy. This highlights why accuracy alone is particularly dangerous for assessing rare-event detection systems.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <div className="mt-8 p-5 bg-amber-50 dark:bg-amber-950/50 rounded-lg border-l-4 border-amber-500">
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
              
              <div className="bg-muted/50 p-4 rounded-md mb-6">
                <p className="text-sm font-medium">Key Insight:</p>
                <p className="text-sm mt-1">
                  Notice how our gauge thresholds shift to counteract the advantage gained by simply matching the distribution! By correctly identifying that the baseline chance level for the stacked deck is around {GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance.toFixed(1)}%, the gauge prevents us from being impressed by accuracy scores that could be achieved just by exploiting the skewed distribution.
                </p>
                
                <ul className="list-disc pl-8 mt-3 space-y-2 text-sm">
                  <li>With the stacked deck, <strong>distribution-aware random guessing</strong> achieves 62.5% accuracy with zero real predictive skill</li>
                  <li>All the "success" segments (okay, good, great) are <strong>crammed to the right</strong> of the gauge for imbalanced data, reflecting the higher baseline to beat</li>
                  <li>To achieve what would be considered "good" performance (30% above chance) on the stacked deck, you'd need accuracy of {(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }).chance + 30).toFixed(1)}%!</li>
                </ul>
              </div>

              <div className="mt-6 p-4 bg-amber-50 dark:bg-amber-950 rounded-md">
                <p className="text-base font-medium">Important Limitation</p>
                <p className="text-sm mt-1">
                  While adjusted gauge thresholds help with interpreting accuracy in context, they don't automatically reveal all forms of "cheating." For example, a model that <strong>always</strong> guesses the majority class (100% red) would achieve 75% accuracy and still appear to be performing "at chance level" on our gauge.
                </p>
                <p className="text-sm mt-2">
                  This is why <strong>raw accuracy cannot be interpreted without context</strong>. We need either:
                </p>
                <ol className="list-decimal pl-5 mt-1 space-y-1">
                  <li>Additional contextual information about the distribution and prediction patterns, or</li>
                  <li>Alternative metrics that inherently account for class distribution (like Gwet's AC1)</li>
                </ol>
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
                  matrix: [
                    [25, 25], // Actual Heads: 25 Pred H, 25 Pred T
                    [27, 23], // Actual Tails: 27 Pred H, 23 Pred T
                  ],
                  labels: ["Heads", "Tails"],
                }}
                predictedClassDistributionData={predictedFairCoinData}
                showBothGauges={true}
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
                  matrix: [
                    [14, 12], // Predicted Red, actual [Red, Black]
                    [12, 14], // Predicted Black, actual [Red, Black]
                  ],
                  labels: ["Red", "Black"],
                }}
                predictedClassDistributionData={[
                  { label: "Red", count: 26 },
                  { label: "Black", count: 26 }
                ]}
                showBothGauges={true}
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
                  matrix: [
                    [24, 15], // Actual Red: 24 Pred R, 15 Pred B
                    [10, 3],  // Actual Black: 10 Pred R, 3 Pred B
                  ],
                  labels: ["Red", "Black"],
                }}
                predictedClassDistributionData={[
                  { label: "Red", count: 34 },
                  { label: "Black", count: 18 }
                ]}
                showBothGauges={true}
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
                  matrix: [
                    [39, 0],  // Actual Red: 39 predicted as Red, 0 as Black
                    [13, 0],  // Actual Black: 13 predicted as Red, 0 as Black
                  ],
                  labels: ["Red", "Black"],
                }}
                predictedClassDistributionData={[
                  { label: "Red", count: 52 },
                  { label: "Black", count: 0 }
                ]}
                showBothGauges={true}
                accuracyGaugeSegments={GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ "Red": 39, "Black": 13 }))}
                notes="Despite achieving 75% accuracy (which sounds impressive), the Agreement gauge correctly shows AC1 = 0.00, indicating no predictive skill beyond chance. By always guessing 'red' for all cards in a deck that's 75% red, we match the majority class percentage but demonstrate zero discriminative ability. The AC1 metric immediately exposes this 'cheating' strategy."
              />

              <div className="p-4 bg-amber-50 dark:bg-amber-950/40 rounded-lg my-6">
                <p className="text-base font-medium">Important Limitation</p>
                <p className="text-sm mt-1">
                  While adjusted gauge thresholds help with interpreting accuracy in context, they don't automatically reveal all forms of "cheating." For example, a model that <strong>always</strong> guesses the majority class (100% red) would achieve 75% accuracy and still appear to be performing "at chance level" on our gauge.
                </p>
                <p className="text-sm mt-2">
                  This is why <strong>raw accuracy cannot be interpreted without context</strong>. We need either:
                </p>
                <ol className="list-decimal pl-5 mt-1 space-y-1">
                  <li>Additional contextual information about the distribution and prediction patterns, or</li>
                  <li>Alternative metrics that inherently account for class distribution (like Gwet's AC1)</li>
                </ol>
              </div>
            </div>
          </div>
        </section>



        <section>
          <h2 className="text-2xl font-semibold mb-4">Example Scenarios</h2>
          <p className="text-muted-foreground mb-4">
            Let's explore a variety of classifier scenarios to see how both Agreement (AC1) and Accuracy gauges 
            represent different performance levels across different data distributions.
          </p>
          
          <h3 className="text-xl font-medium mb-3">To-Do: Implementation Examples</h3>
          <div className="p-4 bg-muted/50 rounded-md mb-6">
            <p className="font-medium mb-2">Balanced Distributions</p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Binary classifier, balanced distribution, 90/100 correct</li>
              <li>Ternary classifier ("Yes", "No", "NA"), balanced distribution, 90/100 correct</li>
              <li>Four-class classifier, balanced distribution, 90/100 correct</li>
            </ul>
            
            <p className="font-medium mt-4 mb-2">Imbalanced Distributions</p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Binary classifier, only 5% "Yes" prevalence in data, 90/100 correct</li>
              <li>Binary classifier, only 5% "Yes" prevalence, always answers "No" (cheating strategy)</li>
              <li>Ternary classifier, imbalanced distribution, 90/100 correct</li>
              <li>Four-class classifier, imbalanced distribution, 90/100 correct</li>
            </ul>
            
            <p className="font-medium mt-4 mb-2">Additional Suggested Examples</p>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>Binary classifier, balanced distribution, but with systematic error pattern (consistently wrong on certain subtypes)</li>
              <li>Multi-class classifier with different levels of confusion between specific pairs of classes</li>
              <li>High-uncertainty scenario: classifier that gives correct answers but with low confidence</li>
              <li>Real-world medical diagnosis example: disease with 1% prevalence, comparing screening vs. diagnostic tests</li>
              <li>Comparison of same system evaluated on different subsets of data with varying distributions</li>
            </ul>
          </div>
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