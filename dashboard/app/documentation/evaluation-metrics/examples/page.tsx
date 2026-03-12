import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import EvaluationCard from '@/components/EvaluationCard'
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"

export const metadata: Metadata = {
  title: "Evaluation Metrics Examples - Plexus Documentation",
  description: "Examples of evaluation metrics across different data distributions and scenarios"
}

export default function ExamplesPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Examples</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Let's explore a variety of classifier scenarios to see how both Agreement (AC1) and Accuracy gauges represent different performance levels across different data distributions.
      </p>

      <div className="space-y-10">
        <section>
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