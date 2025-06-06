'use client';

import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
import EvaluationCard from '@/components/EvaluationCard'
import { Gauge, Segment } from "@/components/gauge"
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import {
  fixedAccuracyGaugeSegments, // For illustrating uncontextualized view if needed
  alwaysSafeEmailAccuracy,
  alwaysSafeEmailGwetAC1,
  alwaysSafeEmailClassDistribution,
  alwaysSafeEmailConfusionMatrix,
  alwaysSafeEmailPredictedDistribution,
  alwaysSafeEmailAccuracySegments,
  stackedDeckAlwaysRedAccuracy,
  stackedDeckAlwaysRedGwetAC1,
  stackedDeckAlwaysRedClassDistribution,
  stackedDeckAlwaysRedConfusionMatrix,
  stackedDeckAlwaysRedPredictedDistribution,
  stackedDeckAlwaysRedAccuracySegments,
  // Article topic labeler can be a good contrast if needed for solution section
  articleTopicLabelerExampleData,
  articleTopicLabelerClassDistribution,
  articleTopicLabelerConfusionMatrix,
  articleTopicLabelerPredictedDistribution,
  articleTopicLabelerFullContextSegments
} from "@/app/[locale]/documentation/evaluation-metrics/examples-data"
import { useTranslationContext } from '@/app/contexts/TranslationContext'

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

export default function ClassImbalanceProblemPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">El Desafío: Interpretando la Precisión con Datos Desbalanceados</h1>
        <p className="text-lg text-muted-foreground mb-2">
          Podrías estar aquí porque una evaluación en Plexus resaltó un <strong>desbalance de clases</strong> en tu conjunto de datos. Esta es una situación común donde algunas categorías (o clases) de datos son mucho más frecuentes que otras. Por ejemplo, en un conjunto de datos de emails, los emails "normales" podrían superar vastamente en número a los emails "spam". O, en manufactura, los elementos no defectuosos podrían ser mucho más comunes que los defectuosos.
        </p>
        <p className="text-lg text-muted-foreground mb-8">
          Aunque tener datos desbalanceados no es un error en sí mismo, puede hacer que los puntajes de precisión tradicionales sean altamente engañosos. Exploremos por qué el desbalance de clases es un factor crítico en entender el verdadero rendimiento de tu clasificador y cómo interpretar correctamente las métricas de evaluación en estos escenarios.
        </p>

        <div className="space-y-10">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Cuando la Precisión Engaña: La Trampa de la Clase Mayoritaria</h2>
            <p className="text-muted-foreground mb-4">
              El problema principal con el desbalance de clases es que un clasificador puede lograr un puntaje alto de precisión simplemente prediciendo siempre la clase mayoritaria, incluso si no ha aprendido nada sobre distinguir entre clases, especialmente las raras. Esto crea una falsa sensación de buen rendimiento.
            </p>

            <EvaluationCard
              title="El Filtro de Email 'Siempre Seguro' (97% Seguros, 3% Prohibidos)"
              subtitle="Estrategia: Etiquetar TODOS los emails como 'Seguros'. Datos Reales: 970 Seguros, 30 Prohibidos."
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
                    <p className="text-sm font-medium text-center">Precisión Cruda: {alwaysSafeEmailAccuracy}% !</p>
                  </div>
                  <div className="mt-3 p-2 bg-destructive rounded-md">
                    <p className="text-sm font-bold text-white text-center">¡Parece Genial, Pero Tiene Fallas Críticas!</p>
                    <p className="text-xs mt-1 text-white text-center">
                      Este filtro detecta CERO emails prohibidos. Parece preciso solo porque etiqueta correctamente la clase mayoritaria del 97%.
                    </p>
                  </div>
                </>
              }
            />

            <p className="text-muted-foreground mt-6 mb-4">
              En el ejemplo anterior, un filtro que marca cada email como "seguro" logra 97% de precisión. ¡Esto suena impresionante! Sin embargo, falla completamente en su tarea principal: identificar contenido prohibido. La alta precisión viene puramente del desbalance de datos.
            </p>

            <div className="mt-6 p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
              <h3 className="text-lg font-semibold mb-2">Percepción Clave: El Desbalance Infla la Precisión Ingenua</h3>
              <p className="text-muted-foreground">
                Los puntajes de precisión cruda son profundamente engañosos con datos desbalanceados. <strong className="text-foreground">Una alta precisión podría simplemente reflejar la proporción de la clase mayoritaria, no capacidad predictiva genuina a través de todas las clases.</strong> Lo que parece un rendimiento excelente podría indicar un modelo que ha aprendido muy poco, o peor, es completamente inefectivo para clases minoritarias.
              </p>
            </div>
          </section>

          <div className="flex flex-wrap gap-4 mt-12">
            <Link href="/es/documentation/evaluation-metrics">
              <DocButton variant="outline">Vista General de Métricas de Evaluación</DocButton>
            </Link>
            <Link href="/es/documentation/evaluation-metrics/gauges-with-context">
              <DocButton variant="outline">Detallado: Indicadores con Contexto</DocButton>
            </Link>
            <Link href="/es/documentation/evaluation-metrics/examples">
              <DocButton>Ver Más Ejemplos de Métricas</DocButton>
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
      <h1 className="text-4xl font-bold mb-4">The Challenge: Interpreting Accuracy with Imbalanced Data</h1>
      <p className="text-lg text-muted-foreground mb-2">
        You might be here because an evaluation in Plexus highlighted a <strong>class imbalance</strong> in your dataset. This is a common situation where some categories (or classes) of data are far more frequent than others. For example, in a dataset of emails, "normal" emails might vastly outnumber "spam" emails. Or, in manufacturing, non-defective items might be much more common than defective ones.
      </p>
      <p className="text-lg text-muted-foreground mb-8">
        While having imbalanced data isn't an error in itself, it can make traditional accuracy scores highly misleading. Let's explore why class imbalance is a critical factor in understanding your classifier's true performance and how to interpret evaluation metrics correctly in these scenarios.
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">When Accuracy Deceives: The Majority Class Trap</h2>
          <p className="text-muted-foreground mb-4">
            The primary issue with class imbalance is that a classifier can achieve a high accuracy score by simply always predicting the majority class, even if it has learned nothing about distinguishing between classes, especially the rare ones. This creates a false sense of good performance.
          </p>

          <EvaluationCard
            title="The 'Always Safe' Email Filter (97% Safe, 3% Prohibited)"
            subtitle="Strategy: Label ALL emails as 'Safe'. Actual Data: 970 Safe, 30 Prohibited."
            classDistributionData={alwaysSafeEmailClassDistribution}
            isBalanced={false}
            accuracy={alwaysSafeEmailAccuracy} // 97.0
            confusionMatrixData={alwaysSafeEmailConfusionMatrix}
            predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
            // No AC1 shown here to first highlight raw accuracy problem
            variant="oneGauge"
            disableAccuracySegments={true} // Show raw, uncontextualized gauge first
            gaugeDescription={
              <>
                <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                  <p className="text-sm font-medium text-center">Raw Accuracy: {alwaysSafeEmailAccuracy}% !</p>
                </div>
                <div className="mt-3 p-2 bg-destructive rounded-md">
                  <p className="text-sm font-bold text-white text-center">Seems Great, But It's Critically Flawed!</p>
                  <p className="text-xs mt-1 text-white text-center">
                    This filter detects ZERO prohibited emails. It appears accurate only because it correctly labels the 97% majority class.
                  </p>
                </div>
              </>
            }
          />

          <p className="text-muted-foreground mt-6 mb-4">
            In the example above, a filter that marks every email as "safe" achieves 97% accuracy. This sounds impressive! However, it completely fails at its primary task: identifying prohibited content. The high accuracy comes purely from the data imbalance.
          </p>

          <EvaluationCard
            title="Stacked Deck (75% Red Cards) - Always Guess Red"
            subtitle="Strategy: Always predict 'Red'. Actual Deck: 75% Red, 25% Black."
            classDistributionData={stackedDeckAlwaysRedClassDistribution}
            isBalanced={false}
            accuracy={stackedDeckAlwaysRedAccuracy} // 75.0
            confusionMatrixData={stackedDeckAlwaysRedConfusionMatrix}
            predictedClassDistributionData={stackedDeckAlwaysRedPredictedDistribution}
            variant="oneGauge"
            disableAccuracySegments={true} // Show raw, uncontextualized gauge first
            gaugeDescription={
              <>
                <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                  <p className="text-sm font-medium text-center">Raw Accuracy: {stackedDeckAlwaysRedAccuracy}% !</p>
                </div>
                <div className="mt-3 p-2 bg-destructive rounded-md">
                  <p className="text-sm font-bold text-white text-center">Also Deceptive!</p>
                  <p className="text-xs mt-1 text-white text-center">
                    This 75% accuracy is achieved by simply guessing the majority class. It reflects the data distribution, not predictive skill on black cards.
                  </p>
                </div>
              </>
            }
          />
          <div className="mt-6 p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Key Insight: Imbalance Inflates Naive Accuracy</h3>
            <p className="text-muted-foreground">
              Raw accuracy scores are profoundly misleading with imbalanced data. <strong className="text-foreground">A high accuracy might simply reflect the proportion of the majority class, not genuine predictive capability across all classes.</strong> What seems like excellent performance could indicate a model that has learned very little, or worse, is completely ineffective for minority classes.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Solution: Clarity Through Contextual Gauges</h2>
          <p className="text-muted-foreground mb-4">
            To cut through the confusion caused by class imbalance, it's essential to use evaluation tools that provide proper context. Plexus employs a two-pronged approach:
          </p>
          <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
            <li>
              <strong className="text-foreground">Contextualized Accuracy Gauges:</strong> The colored segments of the Accuracy gauge dynamically adjust based on the class distribution (including imbalance and number of classes). This means the definition of "good," "viable," etc., shifts to reflect the true baseline for that specific imbalanced dataset. An accuracy of 97% might be chance-level for a 97/3 split, and the gauge will show this.
            </li>
            <li>
              <strong className="text-foreground">Inherently Context-Aware Agreement Gauges:</strong> Metrics like Gwet's AC1 (used in the Agreement gauge) are designed to correct for chance agreement. They inherently account for class imbalance. An AC1 score of 0.0 indicates performance no better than chance (e.g., always guessing the majority class), regardless of how high the raw accuracy appears.
            </li>
          </ol>
          <p className="text-muted-foreground mb-6">
            Let's revisit our examples, this time with both gauges active, showing how they reveal the truth:
          </p>

          <div className="my-8 p-6 rounded-lg bg-card border">
            <h4 className="text-lg font-semibold mb-6 text-center">Visualizing How Contextual Gauges Adapt to Imbalance (65% Accuracy Example)</h4>
            <p className="text-sm text-muted-foreground mb-4 text-center">
              The examples below all show an accuracy of 65%. The top gauge in each column uses a fixed, uncontextualized scale. The bottom gauge dynamically adjusts its segments based on the specific class imbalance described. This illustrates how the interpretation of the same 65% accuracy score changes dramatically when the gauge reflects the underlying data distribution.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Balanced (50/50)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario1_segments} />
                 <p className="text-xs text-muted-foreground mt-2 text-center">65% is somewhat above the 50% chance baseline.</p>
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Imbalanced (75/25)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario2_segments} />
                 <p className="text-xs text-muted-foreground mt-2 text-center">65% is below the 75% majority baseline; poor performance.</p>
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">3-Class Imbal. (80/10/10)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario4_segments} />
                 <p className="text-xs text-muted-foreground mt-2 text-center">65% is below the 80% majority baseline; poor for this setup.</p>
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Highly Imbal. (95/5)</h5>
                <AccuracyGauge value={65.0} title="Fixed Scale" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Contextual Scale" segments={imbal_scenario3_segments} />
                <p className="text-xs text-muted-foreground mt-2 text-center">65% is far below the 95% majority baseline; very poor.</p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground mt-6 text-center">
              This visualization demonstrates that the Plexus Accuracy Gauge helps you avoid being misled by a raw accuracy percentage. By adapting its scale, it correctly shows that a 65% accuracy can range from mediocre (in a balanced scenario) to very poor (in highly imbalanced scenarios where simply guessing the majority class would yield a higher score).
            </p>
          </div>

          <p className="text-muted-foreground mb-6 mt-8">
            Now, let's look at the full `EvaluationCard` examples again, which combine the contextualized Accuracy Gauge with the Agreement Gauge for a complete picture:
          </p>

          <div className="space-y-8">
            <EvaluationCard
              title="The 'Always Safe' Email Filter - Plexus View"
              subtitle="97/3 Imbalance. Strategy: Always predict 'Safe'. Raw Accuracy: 97%."
              classDistributionData={alwaysSafeEmailClassDistribution}
              isBalanced={false}
              accuracy={alwaysSafeEmailAccuracy}
              gwetAC1={alwaysSafeEmailGwetAC1} // 0.0
              confusionMatrixData={alwaysSafeEmailConfusionMatrix}
              predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
              showBothGauges={true}
              variant="default"
              accuracyGaugeSegments={alwaysSafeEmailAccuracySegments}
              notes="The Agreement gauge (AC1=0.0) immediately shows ZERO predictive skill beyond chance. The contextualized Accuracy gauge confirms this: 97% is the baseline for this dataset; true skill would require higher. Both expose the filter as useless for finding prohibited content."
            />

            <EvaluationCard
              title="Stacked Deck (75% Red) - Plexus View"
              subtitle="75/25 Imbalance. Strategy: Always predict 'Red'. Raw Accuracy: 75%."
              classDistributionData={stackedDeckAlwaysRedClassDistribution}
              isBalanced={false}
              accuracy={stackedDeckAlwaysRedAccuracy}
              gwetAC1={stackedDeckAlwaysRedGwetAC1} // 0.0
              confusionMatrixData={stackedDeckAlwaysRedConfusionMatrix}
              predictedClassDistributionData={stackedDeckAlwaysRedPredictedDistribution}
              showBothGauges={true}
              variant="default"
              accuracyGaugeSegments={stackedDeckAlwaysRedAccuracySegments}
              notes="Despite 75% accuracy, the Agreement gauge (AC1=0.0) again correctly shows no predictive skill. The contextualized Accuracy gauge also marks 75% as the baseline chance level for this specific imbalance. No real learning has occurred."
            />
          </div>

          <div className="mt-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
            <h3 className="text-lg font-semibold mb-2">The Power of Two Gauges with Imbalanced Data</h3>
            <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
              <li>The <strong className="text-foreground">Contextualized Accuracy Gauge</strong> adjusts its scale to show what raw accuracy truly means given the imbalance.</li>
              <li>The <strong className="text-foreground">Agreement Gauge (Gwet's AC1)</strong> provides a single, chance-corrected score. An AC1 of 0.0, as seen in these "always guess majority" scenarios, definitively indicates no skill beyond chance, regardless of a high raw accuracy.</li>
            </ul>
            <p className="text-muted-foreground mt-3">
              If you see a high accuracy but an Agreement score near zero, it's a strong indicator that class imbalance is distorting the accuracy metric, and the model may not be performing well on minority classes.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">What About Moderately Imbalanced Data?</h2>
          <p className="text-muted-foreground mb-4">
            The principles are the same for less extreme imbalances. Consider our Article Topic Labeler, which has a 40% majority class (News) among 5 classes. This is imbalanced, though not as drastically as the 97/3 scenario.
          </p>
          <EvaluationCard
            title="Article Topic Labeler - Moderate Imbalance (40% News)"
            subtitle="5-class, 40% News. Accuracy: 62%, Gwet's AC1: 0.512"
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            gwetAC1={articleTopicLabelerExampleData.gwetAC1}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
            notes="Here, the AC1 of 0.512 indicates moderate skill beyond chance. The contextualized Accuracy gauge shows 62% as 'good' for this specific 5-class imbalanced problem—better than just guessing 'News' (40% accuracy) or random 5-class (20% accuracy). Both gauges provide a consistent, nuanced view that accounts for the imbalance."
          />
          <p className="text-muted-foreground mt-4">
            Even with moderate imbalance, relying solely on accuracy could be misleading. The combination of contextualized accuracy and a chance-corrected agreement score provides a more trustworthy assessment.
          </p>
        </section>
      </div>

      <div className="mt-12 p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
        <h3 className="text-lg font-semibold mb-2">For a Comprehensive Overview</h3>
        <p className="text-muted-foreground mb-3">
          This guide focuses on the "class imbalance" problem. For a broader understanding of how Plexus addresses various contextual factors in evaluation (including the number of classes and the full two-pronged solution strategy), please see our main guide:
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
          <Link href="/documentation/evaluation-metrics/gauges/class-number">
            <DocButton variant="outline">Impact of Class Numbers</DocButton>
          </Link>
          <Link href="/documentation/evaluation-metrics/examples">
            <DocButton>View More Metric Examples</DocButton>
          </Link>
        </div>
      </section>
    </div>
  );
} 