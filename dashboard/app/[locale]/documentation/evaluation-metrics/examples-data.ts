import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import { Segment } from "@/components/gauge"

// Helper function to create sample score data for examples
export const createExampleScore = (
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

// Fixed segments for illustrative accuracy gauges (used for raw/uncontextualized views)
export const fixedAccuracyGaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },
  { start: 50, end: 70, color: 'var(--gauge-converging)' },
  { start: 70, end: 80, color: 'var(--gauge-almost)' },
  { start: 80, end: 90, color: 'var(--gauge-viable)' },
  { start: 90, end: 100, color: 'var(--gauge-great)' },
];

// ===== ARTICLE TOPIC LABELER EXAMPLE =====
export const articleTopicLabelerExampleData = {
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

export const articleTopicLabelerClassDistribution = [
  { label: "News", count: 40 },
  { label: "Sports", count: 15 },
  { label: "Business", count: 15 },
  { label: "Technology", count: 15 },
  { label: "Lifestyle", count: 15 }
];

export const articleTopicLabelerConfusionMatrix = {
  labels: ["News", "Sports", "Business", "Technology", "Lifestyle"],
  matrix: [
    { actualClassLabel: "News", predictedClassCounts: { "News": 28, "Sports": 3, "Business": 3, "Technology": 3, "Lifestyle": 3 } },
    { actualClassLabel: "Sports", predictedClassCounts: { "News": 3, "Sports": 9, "Business": 1, "Technology": 1, "Lifestyle": 1 } },
    { actualClassLabel: "Business", predictedClassCounts: { "News": 3, "Sports": 1, "Business": 8, "Technology": 2, "Lifestyle": 1 } },
    { actualClassLabel: "Technology", predictedClassCounts: { "News": 3, "Sports": 1, "Business": 2, "Technology": 8, "Lifestyle": 1 } },
    { actualClassLabel: "Lifestyle", predictedClassCounts: { "News": 3, "Sports": 1, "Business": 1, "Technology": 1, "Lifestyle": 9 } },
  ],
};

export const articleTopicLabelerPredictedDistribution = [
  { label: "News", count: 40 }, 
  { label: "Sports", count: 15 },
  { label: "Business", count: 15 },
  { label: "Technology", count: 15 },
  { label: "Lifestyle", count: 15 }
];

// Segments for the Article Topic Labeler example
export const balanced5ClassDistribution = { 'Class1': 20, 'Class2': 20, 'Class3': 20, 'Class4': 20, 'Class5': 20 };
export const articleTopicLabelerClassCountOnlySegments = GaugeThresholdComputer.createSegments(
  GaugeThresholdComputer.computeThresholds(balanced5ClassDistribution)
);

export const articleTopicLabelerFullContextSegments = GaugeThresholdComputer.createSegments(
  GaugeThresholdComputer.computeThresholds(articleTopicLabelerExampleData.label_distribution)
);

// ===== COIN FLIP EXAMPLES =====
export const fairCoinData = createExampleScore(
  'fair-coin',
  'Randomly Guessing Coin Flips (50/50)',
  -0.04, 
  48.0, 
  100,  
  52,   
  { 'Heads': 50, 'Tails': 50 }
);

export const alwaysHeadsData = createExampleScore(
  'always-heads',
  'Always Guessing "Heads" (50/50)',
  0.02, 
  51.0,
  100,
  49, 
  { 'Heads': 51, 'Tails': 49 }
);

export const fairCoinDistribution = [
  { label: "Heads", count: 51 },
  { label: "Tails", count: 49 }
];

export const predictedFairCoinData = [
  { label: "Heads", count: 50 },
  { label: "Tails", count: 50 }
];

export const predictedAlwaysHeadsData = [
  { label: "Heads", count: 100 },
  { label: "Tails", count: 0 }
];

export const fairCoinConfusionMatrix = {
  labels: ["Heads", "Tails"],
  matrix: [
    { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 24, "Tails": 26 } },
    { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 26, "Tails": 24 } },
  ],
};

export const alwaysHeadsConfusionMatrix = {
  labels: ["Heads", "Tails"],
  matrix: [
    { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 51, "Tails": 0 } },
    { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 49, "Tails": 0 } },
  ],
};

// ===== CARD SUIT EXAMPLES =====
export const cardSuitData = createExampleScore(
  'card-suit-guessing',
  'Predicting a Card Suit (4 Classes, Random Guessing)',
  -0.03, 
  23.0, 
  208,  
  160,  
  { '♥️': 52, '♦️': 52, '♣️': 52, '♠️': 52 }
);

export const cardSuitActualDistribution = [
  { label: "♥️", count: 52 }, 
  { label: "♦️", count: 52 },
  { label: "♣️", count: 52 },
  { label: "♠️", count: 52 }
];

export const cardSuitConfusionMatrix = {
  labels: ["♥️", "♦️", "♣️", "♠️"],
  matrix: [
    { actualClassLabel: "♥️", predictedClassCounts: { "♥️": 12, "♦️": 13, "♣️": 13, "♠️": 14 } },
    { actualClassLabel: "♦️", predictedClassCounts: { "♥️": 13, "♦️": 12, "♣️": 14, "♠️": 13 } },
    { actualClassLabel: "♣️", predictedClassCounts: { "♥️": 13, "♦️": 14, "♣️": 12, "♠️": 13 } },
    { actualClassLabel: "♠️", predictedClassCounts: { "♥️": 14, "♦️": 13, "♣️": 13, "♠️": 12 } },
  ],
};

export const cardSuitPredictedDistribution = [ 
  { label: "♥️", count: 12+13+13+14 },
  { label: "♦️", count: 13+12+14+13 },
  { label: "♣️", count: 13+14+12+13 },
  { label: "♠️", count: 14+13+13+12 }
];

// ===== EMAIL FILTER EXAMPLES =====
export const alwaysSafeEmailClassDistribution = [
  { label: "Safe", count: 970 },
  { label: "Prohibited", count: 30 }
];

export const alwaysSafeEmailConfusionMatrix = {
  labels: ["Safe", "Prohibited"],
  matrix: [
    { actualClassLabel: "Safe", predictedClassCounts: { "Safe": 970, "Prohibited": 0 } },
    { actualClassLabel: "Prohibited", predictedClassCounts: { "Safe": 30, "Prohibited": 0 } },
  ],
};

export const alwaysSafeEmailPredictedDistribution = [
  { label: "Safe", count: 1000 }, 
  { label: "Prohibited", count: 0 }
];

export const alwaysSafeEmailAccuracy = 97.0;
export const alwaysSafeEmailGwetAC1 = 0.0;
export const alwaysSafeEmailAccuracySegments = GaugeThresholdComputer.createSegments(
  GaugeThresholdComputer.computeThresholds({ 'Safe': 970, 'Prohibited': 30 })
);

// ===== STACKED DECK EXAMPLES =====
export const stackedDeckAlwaysRedClassDistribution = [ 
  { label: "Red", count: 75 }, 
  { label: "Black", count: 25 } 
];

export const stackedDeckAlwaysRedConfusionMatrix = {
  labels: ["Red", "Black"],
  matrix: [
    { actualClassLabel: "Red", predictedClassCounts: { "Red": 75, "Black": 0 } },
    { actualClassLabel: "Black", predictedClassCounts: { "Red": 25, "Black": 0 } },
  ],
};

export const stackedDeckAlwaysRedPredictedDistribution = [ 
  { label: "Red", count: 100 }, 
  { label: "Black", count: 0 } 
];

export const stackedDeckAlwaysRedAccuracy = 75.0;
export const stackedDeckAlwaysRedGwetAC1 = 0.0;
export const stackedDeckAlwaysRedAccuracySegments = GaugeThresholdComputer.createSegments(
  GaugeThresholdComputer.computeThresholds({ 'Red': 75, 'Black': 25 })
);

// ===== SCENARIO DATA FOR GAUGES WITH CONTEXT =====
export const scenario1Data = createExampleScore(
  'scenario1-balanced-2class',
  'Scenario 1: Balanced 2-Class Data (50/50)',
  0.50, 
  75.0,
  1000,
  250,
  { 'Yes': 500, 'No': 500 }
);

export const scenario2Data = createExampleScore(
  'scenario2-balanced-4class',
  'Scenario 2: Balanced 4-Class Data (25/25/25/25)',
  0.67, 
  75.0,
  1000,
  250,
  { 'ClassA': 250, 'ClassB': 250, 'ClassC': 250, 'ClassD': 250 }
);

// Dynamic segments for different class counts
export const thresholds2Class = GaugeThresholdComputer.computeThresholds(scenario1Data.label_distribution!);
export const dynamicSegments2Class = GaugeThresholdComputer.createSegments(thresholds2Class);

export const thresholds4Class = GaugeThresholdComputer.computeThresholds(scenario2Data.label_distribution!);
export const dynamicSegments4Class = GaugeThresholdComputer.createSegments(thresholds4Class);

export const label_distribution_3_class = { C1: 1, C2: 1, C3: 1 };
export const thresholds3Class = GaugeThresholdComputer.computeThresholds(label_distribution_3_class);
export const dynamicSegments3Class = GaugeThresholdComputer.createSegments(thresholds3Class);

export const label_distribution_12_class: Record<string, number> = {};
for (let i = 1; i <= 12; i++) {
  label_distribution_12_class[`Class ${i}`] = 1;
}
export const thresholds12Class = GaugeThresholdComputer.computeThresholds(label_distribution_12_class);
export const dynamicSegments12Class = GaugeThresholdComputer.createSegments(thresholds12Class);

// Imbalance scenario segments
export const imbal_scenario1_dist = { C1: 50, C2: 50 };
export const imbal_scenario1_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario1_dist);
export const imbal_scenario1_segments = GaugeThresholdComputer.createSegments(imbal_scenario1_thresholds);

export const imbal_scenario2_dist = { C1: 75, C2: 25 };
export const imbal_scenario2_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario2_dist);
export const imbal_scenario2_segments = GaugeThresholdComputer.createSegments(imbal_scenario2_thresholds);

export const imbal_scenario3_dist = { C1: 95, C2: 5 };
export const imbal_scenario3_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario3_dist);
export const imbal_scenario3_segments = GaugeThresholdComputer.createSegments(imbal_scenario3_thresholds);

export const imbal_scenario4_dist = { C1: 80, C2: 10, C3: 10 };
export const imbal_scenario4_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario4_dist);
export const imbal_scenario4_segments = GaugeThresholdComputer.createSegments(imbal_scenario4_thresholds);

// ===== EXAMPLES PAGE SPECIFIC DATA =====

// Binary classifier examples for the examples page
export const binaryClassifierBalanced65Data = {
  scoreData: { accuracy: 65.0, itemCount: 100, mismatches: 35, label_distribution: { 'Yes': 50, 'No': 50 } },
  gwetAC1: 0.30, // (0.65 - 0.5) / (1 - 0.5)
  classDistribution: [ { label: "Yes", count: 50 }, { label: "No", count: 50 } ],
  confusionMatrix: {
    labels: ["Yes", "No"],
    matrix: [
      { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 32, "No": 18 } }, // 50 Actual Yes, 32 correct
      { actualClassLabel: "No", predictedClassCounts: { "Yes": 17, "No": 33 } },  // 50 Actual No, 33 correct
    ], // Total correct: 32+33=65
  },
  predictedDistribution: [ { label: "Yes", count: 32+17 }, { label: "No", count: 18+33 } ], // Yes: 49, No: 51
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Yes': 50, 'No': 50 }))
};

// Ternary classifier examples for the examples page
export const ternaryClassifierBalanced65Data = {
  scoreData: { accuracy: 65.0, itemCount: 100, mismatches: 35, label_distribution: { 'Yes': 34, 'No': 33, 'NA': 33 } },
  gwetAC1: 0.475, // Approx (0.65 - 0.3333) / (1 - 0.3333)
  classDistribution: [ { label: "Yes", count: 34 }, { label: "No", count: 33 }, { label: "NA", count: 33 } ],
  confusionMatrix: {
    labels: ["Yes", "No", "NA"],
    matrix: [
      { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 22, "No": 6, "NA": 6 } }, // 34 total, 22 correct (12 errors)
      { actualClassLabel: "No", predictedClassCounts: { "Yes": 6, "No": 22, "NA": 5 } },  // 33 total, 22 correct (11 errors)
      { actualClassLabel: "NA", predictedClassCounts: { "Yes": 6, "No": 6, "NA": 21 } },  // 33 total, 21 correct (12 errors)
    ], // Total correct: 22+22+21=65. Total errors: 12+11+12=35
  },
  predictedDistribution: [ 
    { label: "Yes", count: 22+6+6 }, // 34
    { label: "No", count: 6+22+6 },   // 34
    { label: "NA", count: 6+5+21 }    // 32
  ],
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Yes': 34, 'No': 33, 'NA': 33 }))
};

// Four-class classifier examples for the examples page
export const fourClassClassifierBalanced65Data = {
  scoreData: { accuracy: 65.0, itemCount: 100, mismatches: 35, label_distribution: { 'A': 25, 'B': 25, 'C': 25, 'D': 25 } },
  gwetAC1: 0.533, // (0.65 - 0.25) / (1 - 0.25)
  classDistribution: [ { label: "A", count: 25 }, { label: "B", count: 25 }, { label: "C", count: 25 }, { label: "D", count: 25 } ],
  confusionMatrix: {
    labels: ["A", "B", "C", "D"],
    matrix: [
      { actualClassLabel: "A", predictedClassCounts: { "A": 16, "B": 3, "C": 3, "D": 3 } }, // 25 total, 16 correct (9 errors)
      { actualClassLabel: "B", predictedClassCounts: { "A": 3, "B": 16, "C": 3, "D": 3 } }, // 25 total, 16 correct (9 errors)
      { actualClassLabel: "C", predictedClassCounts: { "A": 3, "B": 3, "C": 16, "D": 3 } }, // 25 total, 16 correct (9 errors)
      { actualClassLabel: "D", predictedClassCounts: { "A": 3, "B": 2, "C": 3, "D": 17 } }, // 25 total, 17 correct (8 errors)
    ], // Total correct: 16+16+16+17=65. Total errors: 9+9+9+8=35
  },
  predictedDistribution: [ 
    { label: "A", count: 16+3+3+3 }, // 25
    { label: "B", count: 3+16+3+2 }, // 24
    { label: "C", count: 3+3+16+3 }, // 25
    { label: "D", count: 3+3+3+17 }  // 26
  ],
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'A': 25, 'B': 25, 'C': 25, 'D': 25 }))
};

// Imbalanced examples for the examples page
export const binaryClassifierImbalanced90Data = {
  scoreData: { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'Yes': 5, 'No': 95 } },
  gwetAC1: 0.401, // Calculated: (0.90 - ((0.05×0.13)+(0.95×0.87))) / (1 - ((0.05×0.13)+(0.95×0.87)))
  classDistribution: [ { label: "Yes", count: 5 }, { label: "No", count: 95 } ],
  isBalanced: false,
  confusionMatrix: {
    labels: ["Yes", "No"],
    matrix: [
      { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 4, "No": 1 } }, // 5 Actual Yes: 4 TP, 1 FN
      { actualClassLabel: "No", predictedClassCounts: { "Yes": 9, "No": 86 } },  // 95 Actual No: 9 FP, 86 TN
    ], // Total correct: 4+86=90. Errors: 1+9=10.
  },
  predictedDistribution: [ { label: "Yes", count: 4+9 }, { label: "No", count: 1+86 } ], // Yes:13, No:87
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Yes': 5, 'No': 95 }))
};

export const binaryClassifierAlwaysNoData = {
  scoreData: { accuracy: 95.0, itemCount: 100, mismatches: 5, label_distribution: { 'Yes': 5, 'No': 95 } },
  gwetAC1: 0.0,
  classDistribution: [ { label: "Yes", count: 5 }, { label: "No", count: 95 } ],
  isBalanced: false,
  confusionMatrix: {
    labels: ["Yes", "No"],
    matrix: [
      { actualClassLabel: "Yes", predictedClassCounts: { "Yes": 0, "No": 5 } }, // All 5 'Yes' are missed
      { actualClassLabel: "No", predictedClassCounts: { "Yes": 0, "No": 95 } },  // All 95 'No' are correct
    ],
  },
  predictedDistribution: [ { label: "Yes", count: 0 }, { label: "No", count: 100 } ],
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Yes': 5, 'No': 95 }))
};

export const ternaryClassifierImbalanced90Data = {
  scoreData: { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'A': 5, 'B': 45, 'C': 50 } },
  gwetAC1: 0.819, // Calculated: (0.90 - Pe) / (1-Pe) where Pe = (0.05×0.07) + (0.45×0.44) + (0.50×0.49) = 0.4465
  classDistribution: [ { label: "A", count: 5 }, { label: "B", count: 45 }, { label: "C", count: 50 } ],
  isBalanced: false,
  confusionMatrix: {
    labels: ["A", "B", "C"],
    matrix: [
      { actualClassLabel: "A", predictedClassCounts: { "A": 3, "B": 1, "C": 1 } },     // 5 total, 3 correct
      { actualClassLabel: "B", predictedClassCounts: { "A": 2, "B": 41, "C": 2 } },   // 45 total, 41 correct
      { actualClassLabel: "C", predictedClassCounts: { "A": 2, "B": 2, "C": 46 } },    // 50 total, 46 correct
    ], // Total Correct: 3+41+46 = 90. Errors: 2+4+4 = 10.
  },
  predictedDistribution: [ 
    { label: "A", count: 3+2+2 },   // 7
    { label: "B", count: 1+41+2 },  // 44
    { label: "C", count: 1+2+46 }    // 49
  ],
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'A': 5, 'B': 45, 'C': 50 }))
};

export const fourClassClassifierImbalanced90Data = {
  scoreData: { accuracy: 90.0, itemCount: 100, mismatches: 10, label_distribution: { 'A': 5, 'B': 15, 'C': 30, 'D': 50 } },
  gwetAC1: 0.843, // Calculated: (0.90 - Pe) / (1-Pe) where Pe = (0.05×0.06) + (0.15×0.15) + (0.30×0.29) + (0.50×0.50) = 0.3625
  classDistribution: [ { label: "A", count: 5 }, { label: "B", count: 15 }, { label: "C", count: 30 }, { label: "D", count: 50 } ],
  isBalanced: false,
  confusionMatrix: {
    labels: ["A", "B", "C", "D"],
    matrix: [
      { actualClassLabel: "A", predictedClassCounts: { "A": 3, "B": 1, "C": 1, "D": 0 } },   // 5 total, 3 correct
      { actualClassLabel: "B", predictedClassCounts: { "A": 1, "B": 12, "C": 1, "D": 1 } }, // 15 total, 12 correct
      { actualClassLabel: "C", predictedClassCounts: { "A": 1, "B": 1, "C": 27, "D": 1 } }, // 30 total, 27 correct
      { actualClassLabel: "D", predictedClassCounts: { "A": 1, "B": 1, "C": 0, "D": 48 } },  // 50 total, 48 correct
    ], // Total Correct: 3+12+27+48 = 90. Errors: 2+3+3+2=10.
  },
  predictedDistribution: [
    { label: "A", count: 3+1+1+1 },    // 6
    { label: "B", count: 1+12+1+1 },   // 15
    { label: "C", count: 1+1+27+0 },   // 29
    { label: "D", count: 0+1+1+48 }    // 50
  ],
  accuracyGaugeSegments: GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'A': 5, 'B': 15, 'C': 30, 'D': 50 }))
}; 