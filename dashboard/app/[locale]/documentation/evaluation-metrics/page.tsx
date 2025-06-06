'use client';

import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import EvaluationCard from '@/components/EvaluationCard'
import { Segment } from "@/components/gauge"
import { useTranslationContext } from '@/app/contexts/TranslationContext'

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
  const { locale } = useTranslationContext();
  
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

  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Interpretando Métricas de Evaluación: El Desafío</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Entender métricas como la precisión es clave para evaluar el rendimiento de IA. Sin embargo, los números crudos pueden ser engañosos sin el contexto apropiado. Esta página explora errores comunes e introduce el enfoque de Plexus para una evaluación más clara y confiable.
        </p>

        <div className="space-y-10">
          <section className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">La Gran Pregunta: ¿Es Bueno Este Clasificador?</h2>
            <p className="text-muted-foreground mb-4">
              Al desarrollar un sistema de IA, necesitamos indicadores para saber si nuestro modelo está funcionando bien. Consideremos un "Etiquetador de Temas de Artículos" que clasifica artículos en cinco categorías: Noticias, Deportes, Negocios, Tecnología y Estilo de Vida. Evaluado en 100 artículos, logra 62% de precisión.
            </p>

            <EvaluationCard
              title="Etiquetador de Temas de Artículos (Vista Inicial)"
              subtitle="Clasifica artículos en 5 categorías. Precisión: 62%."
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
                    <p className="text-sm font-medium">¿Es buena una precisión del 62%?</p>
                    <p className="text-sm mt-2">
                      Este número parece mediocre. El indicador no contextualizado sugiere que solo está 'convergiendo'. ¿Pero es esto rendimiento pobre, o hay más en la historia?
                    </p>
                  </div>
                </>
              }
            />
            
            <p className="text-muted-foreground mt-4 mb-4">
              Intuitivamente, el 62% parece algo débil—casi 4 de cada 10 artículos están mal. Pero para juzgar esto, necesitamos una línea base: ¿qué precisión lograría adivinar aleatoriamente?
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Trampa 1: Ignorar la Línea Base (Acuerdo por Casualidad)</h2>
            <p className="text-muted-foreground mb-4">
              La precisión cruda no tiene sentido sin conocer la tasa de acuerdo por casualidad. Considera predecir 100 lanzamientos de moneda:
            </p>
            
            <p className="text-muted-foreground mb-4">
              Con un lanzamiento de moneda justo, la adivinación aleatoria debería lograr cerca del 50% de precisión. Cualquier cosa significativamente mejor que esto indica habilidad real.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Trampa 2: No Considerar el Desbalance de Clases</h2>
            <p className="text-muted-foreground mb-4">
              El desbalance de clases puede hacer que la precisión alta sea engañosa. Un clasificador puede lograr alta precisión simplemente prediciendo siempre la clase mayoritaria.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">La Solución de Plexus: Indicadores Contextualizados</h2>
            <p className="text-muted-foreground mb-4">
              Plexus aborda estos desafíos con un enfoque de dos partes:
            </p>
            
            <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground">
              <li>
                <strong className="text-foreground">Indicadores de Precisión Contextualizados:</strong> Ajustan dinámicamente sus escalas visuales basándose en el número de clases y distribución de clases específicas del problema.
              </li>
              <li>
                <strong className="text-foreground">Indicadores de Acuerdo Conscientes del Contexto:</strong> Métricas como el AC1 de Gwet que internamente contabilizan el acuerdo por casualidad y proporcionan puntajes estandarizados comparables.
              </li>
            </ol>

            <EvaluationCard
              title="Etiquetador de Temas de Artículos (Vista Completa)"
              subtitle="Con indicadores contextualizados y de acuerdo"
              classDistributionData={articleTopicLabelerClassDistribution}
              isBalanced={false}
              accuracy={articleTopicLabelerExampleData.accuracy}
              gwetAC1={articleTopicLabelerExampleData.gwetAC1}
              confusionMatrixData={articleTopicLabelerConfusionMatrix}
              predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
              showBothGauges={true}
              variant="default"
              accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
              notes="Con contexto completo, vemos que el 62% de precisión es realmente 'bueno' para este problema de 5 clases desbalanceado. El AC1 de 0.512 confirma un acuerdo moderado más allá de la casualidad."
            />
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximos Pasos</h2>
            <p className="text-muted-foreground mb-4">
              Explora los indicadores individuales y conceptos relacionados:
            </p>
            
            <div className="grid md:grid-cols-2 gap-4 mb-6">
              <div className="space-y-2">
                <h3 className="text-lg font-semibold">Indicadores Individuales</h3>
                <div className="space-y-1">
                  <Link href="/es/documentation/evaluation-metrics/gauges/accuracy">
                    <DocButton variant="outline" className="w-full justify-start">Indicador de Precisión</DocButton>
                  </Link>
                  <Link href="/es/documentation/evaluation-metrics/gauges/agreement">
                    <DocButton variant="outline" className="w-full justify-start">Indicador de Acuerdo</DocButton>
                  </Link>
                  <Link href="/es/documentation/evaluation-metrics/gauges/precision">
                    <DocButton variant="outline" className="w-full justify-start">Indicador de Precisión (Métrica)</DocButton>
                  </Link>
                  <Link href="/es/documentation/evaluation-metrics/gauges/recall">
                    <DocButton variant="outline" className="w-full justify-start">Indicador de Recuperación</DocButton>
                  </Link>
                </div>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-semibold">Conceptos Clave</h3>
                <div className="space-y-1">
                  <Link href="/es/documentation/evaluation-metrics/gauges-with-context">
                    <DocButton variant="outline" className="w-full justify-start">Indicadores con Contexto</DocButton>
                  </Link>
                  <Link href="/es/documentation/evaluation-metrics/gauges/class-number">
                    <DocButton variant="outline" className="w-full justify-start">Número de Clases</DocButton>
                  </Link>
                  <Link href="/es/documentation/evaluation-metrics/gauges/class-imbalance">
                    <DocButton variant="outline" className="w-full justify-start">Desbalance de Clases</DocButton>
                  </Link>
                  <Link href="/es/documentation/evaluation-metrics/examples">
                    <DocButton variant="outline" className="w-full justify-start">Ejemplos Detallados</DocButton>
                  </Link>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    );
  }

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
            <h2 className="text-2xl font-semibold mb-4">
              {locale === 'es' ? 'Trampa 3: La Ilusión del Desbalance de Clases' : 'Pitfall 3: The Illusion of Class Imbalance'}
            </h2>
            <p className="text-muted-foreground mb-6">
              {locale === 'es' 
                ? 'La distribución de clases en tus datos (balance de clases) añade otra capa de complejidad. Si un conjunto de datos está desbalanceado, un clasificador puede lograr alta precisión simplemente prediciendo siempre la clase mayoritaria, incluso si no tiene habilidad real.'
                : 'The distribution of classes in your data (class balance) adds another layer of complexity. If a dataset is imbalanced, a classifier can achieve high accuracy by simply always predicting the majority class, even if it has no real skill.'
              }
            </p>
            <div className="grid md:grid-cols-2 gap-6 mb-6">
                <EvaluationCard
                  title={locale === 'es' ? "Baraja Cargada (75% Rojo): Adivinanza Aleatoria 50/50" : "Stacked Deck (75% Red): Random 50/50 Guess"}
                  subtitle={locale === 'es' ? "Baraja: 75% Rojo, 25% Negro. Estrategia de adivinanza: 50/50 Rojo/Negro (ignora el desbalance)." : "Deck: 75% Red, 25% Black. Guess strategy: 50/50 Red/Black (ignores imbalance)."}
                  classDistributionData={locale === 'es' ? [{label: "Rojo", count: 75}, {label: "Negro", count: 25}] : [{label: "Red", count: 75}, {label: "Black", count: 25}]} // Simplified distribution
                  isBalanced={false}
                  accuracy={52} // Example accuracy, around 50% as it doesn't use imbalance info
                  variant="oneGauge"
                  disableAccuracySegments={true}
                  gaugeDescription={
                    <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                        <p className="text-sm font-medium text-center">
                          {locale === 'es' ? '~52% de precisión.' : '~52% accuracy.'}
                        </p>
                        <p className="text-xs mt-1 text-center">
                          {locale === 'es' 
                            ? 'La estrategia no explota el desbalance conocido 75/25 de la baraja.'
                            : 'Strategy doesn\'t exploit the deck\'s known 75/25 imbalance.'
                          }
                        </p>
                    </div>
                    }
                />
                <EvaluationCard
                  title={locale === 'es' ? "Baraja Cargada (75% Rojo): Siempre Adivinar Rojo" : "Stacked Deck (75% Red): Always Guess Red"}
                  subtitle={locale === 'es' ? "Baraja: 75% Rojo, 25% Negro. Estrategia de adivinanza: Siempre predecir Rojo." : "Deck: 75% Red, 25% Black. Guess strategy: Always predict Red."}
                  classDistributionData={locale === 'es' ? [{label: "Rojo", count: 75}, {label: "Negro", count: 25}] : [{label: "Red", count: 75}, {label: "Black", count: 25}]}
                  isBalanced={false}
                  accuracy={75.0} 
                  variant="oneGauge"
                  disableAccuracySegments={true}
                  gaugeDescription={
                    <>
                      <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                        <p className="text-sm font-medium text-center">
                          {locale === 'es' ? '¡75% de precisión!' : '75% accuracy!'}
                        </p>
                      </div>
                      <div className="mt-3 p-2 bg-destructive rounded-md">
                        <p className="text-sm font-bold text-white text-center">
                          {locale === 'es' ? '¡Engañosamente Alto!' : 'Deceptively High!'}
                        </p>
                        <p className="text-xs mt-1 text-white text-center">
                          {locale === 'es' 
                            ? 'Este 75% se logra explotando el desbalance (siempre adivinando la mayoría), no por habilidad.'
                            : 'This 75% is achieved by exploiting the imbalance (always guessing majority), not by skill.'
                          }
                        </p>
                      </div>
                    </>
                  }
                />
            </div>
            <p className="text-muted-foreground mb-6">
              {locale === 'es' 
                ? 'Un ejemplo más extremo: un filtro de correo electrónico afirma tener 97% de precisión al detectar contenido prohibido. Sin embargo, si solo el 3% de los correos realmente contiene tal contenido, un filtro que etiqueta *cada correo* como "seguro" (atrapando cero violaciones) logrará 97% de precisión.'
                : 'A more extreme example: an email filter claims 97% accuracy at detecting prohibited content. However, if only 3% of emails actually contain such content, a filter that labels *every single email* as "safe" (catching zero violations) will achieve 97% accuracy.'
              }
            </p>
             <EvaluationCard
                title={locale === 'es' ? "El Filtro de Correo \"Siempre Seguro\" (Desbalance 97/3)" : "The \"Always Safe\" Email Filter (97/3 Imbalance)"}
                subtitle={locale === 'es' ? "Etiqueta todos los correos como 'seguros'. Real: 97% Seguros, 3% Prohibidos." : "Labels all emails as 'safe'. Actual: 97% Safe, 3% Prohibited."}
                classDistributionData={locale === 'es' ? [{ label: "Seguro", count: 970 }, { label: "Prohibido", count: 30 }] : [{ label: "Safe", count: 970 }, { label: "Prohibited", count: 30 }]}
                isBalanced={false}
                accuracy={97.0}
                variant="oneGauge"
                disableAccuracySegments={true}
                gaugeDescription={
                  <>
                    <div className="p-3 bg-violet-50 dark:bg-violet-950/40 rounded-md mt-2 border-l-4 border-violet-500">
                        <p className="text-sm font-medium text-center">
                          {locale === 'es' ? '¡97% de precisión! ¿Suena genial?' : '97% accuracy! Sounds great?'}
                        </p>
                    </div>
                    <div className="mt-3 p-2 bg-destructive rounded-md">
                      <p className="text-sm font-bold text-white text-center">
                        {locale === 'es' ? '¡FALLA CRÍTICA!' : 'CRITICAL FLAW!'}
                      </p>
                      <p className="text-xs mt-1 text-white text-center">
                        {locale === 'es' 
                          ? 'Este modelo detecta CERO contenido prohibido. Es peor que inútil, proporcionando una falsa sensación de seguridad.'
                          : 'This model detects ZERO prohibited content. It\'s worse than useless, providing a false sense of security.'
                        }
                      </p>
                    </div>
                  </>
                }
              />
            <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6">
              <h3 className="text-lg font-semibold mb-2">
                {locale === 'es' ? 'Percepción Clave: El Desbalance Infla la Precisión Ingenua' : 'Key Insight: Imbalance Inflates Naive Accuracy'}
              </h3>
              <p className="text-muted-foreground">
                {locale === 'es' 
                  ? 'Los puntajes de precisión cruda son profundamente engañosos sin considerar el desbalance de clases. <strong className="text-foreground">Una alta precisión podría simplemente reflejar la proporción de la clase mayoritaria, no el poder predictivo real.</strong> Una precisión del 97% podría ser excelente para un problema balanceado, mediocre para uno moderadamente desbalanceado, o indicativo de falla completa en la detección de eventos raros.'
                  : 'Raw accuracy scores are deeply misleading without considering class imbalance. <strong className="text-foreground">A high accuracy might simply reflect the majority class proportion, not actual predictive power.</strong> A 97% accuracy could be excellent for a balanced problem, mediocre for a moderately imbalanced one, or indicative of complete failure in rare event detection.'
                }
              </p>
            </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">
            {locale === 'es' ? 'La Solución de Plexus: Un Enfoque Unificado para la Claridad' : 'Plexus\'s Solution: A Unified Approach to Clarity'}
          </h2>
          <p className="text-muted-foreground mb-4">
            {locale === 'es' 
              ? 'Para superar estas trampas comunes y proporcionar una verdadera comprensión del rendimiento del clasificador, Plexus emplea una estrategia de dos frentes que combina métricas crudas contextualizadas con puntajes de acuerdo inherentemente conscientes del contexto:'
              : 'To overcome these common pitfalls and provide a true understanding of classifier performance, Plexus employs a two-pronged strategy that combines contextualized raw metrics with inherently context-aware agreement scores:'
            }
          </p>
          <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
            <li>
              <strong className="text-foreground">
                {locale === 'es' ? 'Indicadores de Precisión Contextualizados:' : 'Contextualized Accuracy Gauges:'}
              </strong> {locale === 'es' 
                ? 'No solo mostramos la precisión cruda; la mostramos en una escala visual dinámica. Los segmentos coloreados de nuestros indicadores de Precisión se adaptan basados en el número de clases *y* su distribución en tus datos específicos. Esto inmediatamente te ayuda a interpretar si un puntaje de precisión es bueno, malo, o indiferente *para ese contexto de problema particular*.'
                : 'We don\'t just show raw accuracy; we show it on a dynamic visual scale. The colored segments of our Accuracy gauges adapt based on the number of classes *and* their distribution in your specific data. This immediately helps you interpret if an accuracy score is good, bad, or indifferent *for that particular problem context*.' 
              }
            </li>
            <li>
              <strong className="text-foreground">
                {locale === 'es' ? 'Indicadores de Acuerdo Inherentemente Conscientes del Contexto:' : 'Inherently Context-Aware Agreement Gauges:'}
              </strong> {locale === 'es' 
                ? 'Junto con la precisión, presentamos prominentemente un indicador de Acuerdo (típicamente usando AC1 de Gwet). Esta métrica está específicamente diseñada para calcular una medida de acuerdo corregida por casualidad. *Internamente* considera el número de clases y su distribución, proporcionando un puntaje estandarizado (0 = casualidad, 1 = perfecto) que refleja habilidad más allá de la adivinanza aleatoria. Este puntaje es directamente comparable entre diferentes problemas y conjuntos de datos.'
                : 'Alongside accuracy, we prominently feature an Agreement gauge (typically using Gwet\'s AC1). This metric is specifically designed to calculate a chance-corrected measure of agreement. It *internally* accounts for the number of classes and their distribution, providing a standardized score (0 = chance, 1 = perfect) that reflects skill beyond random guessing. This score is directly comparable across different problems and datasets.'
              }
            </li>
          </ol>
          <p className="text-muted-foreground mb-4">
            {locale === 'es' 
              ? 'Veamos cómo este enfoque unificado clarifica el rendimiento de nuestro Etiquetador de Temas de Artículos (que tenía 62% de precisión cruda, 5 clases, y una distribución desbalanceada con 40% "Noticias"):'
              : 'Let\'s see how this unified approach clarifies the performance of our Article Topic Labeler (which had 62% raw accuracy, 5 classes, and an imbalanced distribution with 40% "News"):'
            }
          </p>

          <EvaluationCard
            title={locale === 'es' ? "Etiquetador de Temas de Artículos - La Vista de Plexus" : "Article Topic Labeler - The Plexus View"}
            subtitle={locale === 'es' ? "5 clases, desbalanceado (40% Noticias). Precisión: 62%, AC1 de Gwet: 0.512" : "5-class, imbalanced (40% News). Accuracy: 62%, Gwet's AC1: 0.512"}
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            gwetAC1={articleTopicLabelerExampleData.gwetAC1}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            showBothGauges={true} 
            variant="default" 
            accuracyGaugeSegments={articleTopicLabelerFullContextSegments} 
            notes={locale === 'es' 
              ? "El indicador de Precisión contextualizado (derecha) muestra 62% como 'bueno' para este problema específico de 5 clases desbalanceado—mejor que solo adivinar 'Noticias' (40%) o aleatorio de 5 clases (20%). El indicador de Acuerdo (izquierda, AC1=0.512) confirma habilidad moderada más allá de la casualidad, considerando consistentemente todos los factores contextuales. Ambos indicadores juntos proporcionan una imagen clara y confiable."
              : "The contextualized Accuracy gauge (right) shows 62% as 'good' for this specific 5-class imbalanced problem—better than just guessing 'News' (40%) or random 5-class (20%). The Agreement gauge (left, AC1=0.512) confirms moderate skill beyond chance, consistently accounting for all contextual factors. Both gauges together provide a clear, reliable picture."
            }
          />

          <div className="mt-6 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
            <h3 className="text-lg font-semibold mb-2">
              {locale === 'es' ? 'El Poder de Dos Indicadores' : 'The Power of Two Gauges'}
            </h3>
            <p className="text-muted-foreground mb-3">
              {locale === 'es' 
                ? 'Este enfoque combinado ofrece una comprensión robusta e intuitiva:'
                : 'This combined approach offers robust and intuitive understanding:'
              }
            </p>
            <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                <li>
                  {locale === 'es' 
                    ? 'El <strong className="text-foreground">Indicador de Precisión Contextualizado</strong> clarifica lo que significa la precisión cruda del 62% para *las complejidades de esta tarea específica* (5 clases, desbalanceado).'
                    : 'The <strong className="text-foreground">Contextualized Accuracy Gauge</strong> clarifies what the raw 62% accuracy means for *this specific task\'s complexities* (5 classes, imbalanced).'
                  }
                </li>
                <li>
                  {locale === 'es' 
                    ? 'El <strong className="text-foreground">Indicador de Acuerdo</strong> proporciona un puntaje único y estandarizado (AC1 de 0.512) midiendo rendimiento *por encima de la casualidad*, directamente comparable entre diferentes problemas.'
                    : 'The <strong className="text-foreground">Agreement Gauge</strong> provides a single, standardized score (AC1 of 0.512) measuring performance *above chance*, directly comparable across different problems.'
                  }
                </li>
            </ul>
            <p className="text-muted-foreground mt-3">
              {locale === 'es' 
                ? 'Juntos, previenen malinterpretaciones de la precisión cruda y ofrecen una verdadera percepción del rendimiento de un clasificador.'
                : 'Together, they prevent misinterpretations of raw accuracy and offer true insight into a classifier\'s performance.'
              }
            </p>
          </div>
          
          <div className="mt-8 p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
            <h3 className="text-lg font-semibold mb-2">
              {locale === 'es' ? 'Profundiza en las Soluciones' : 'Dive Deeper into the Solutions'}
            </h3>
            <p className="text-muted-foreground mb-3">
              {locale === 'es' 
                ? 'Para entender las mecánicas detalladas de cómo Plexus contextualiza los indicadores de Precisión y cómo funciona el indicador de Acuerdo a través de varios escenarios, explora nuestra guía dedicada:'
                : 'To understand the detailed mechanics of how Plexus contextualizes Accuracy gauges and how the Agreement gauge works across various scenarios, explore our dedicated guide:'
              }
            </p>
            <Link href="/documentation/evaluation-metrics/gauges-with-context">
              <DocButton>
                {locale === 'es' ? 'Entendiendo Indicadores con Contexto' : 'Understanding Gauges with Context'}
              </DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">
            {locale === 'es' ? 'Próximos Pasos' : 'Next Steps'}
          </h2>
          <p className="text-muted-foreground mb-4">
            {locale === 'es' 
              ? 'Explora más documentación para mejorar tu comprensión:'
              : 'Explore further documentation to enhance your understanding:'
            }
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/documentation/evaluation-metrics/gauges-with-context">
              <DocButton variant="outline">
                {locale === 'es' ? 'Detallado: Indicadores con Contexto' : 'Detailed: Gauges with Context'}
              </DocButton>
            </Link>
            <Link href="/documentation/evaluation-metrics/examples">
              <DocButton>
                {locale === 'es' ? 'Ver Más Ejemplos' : 'View More Examples'}
              </DocButton>
            </Link>
            <Link href="/documentation/basics/evaluations">
              <DocButton>
                {locale === 'es' ? 'Aprender sobre Evaluaciones' : 'Learn about Evaluations'}
              </DocButton>
            </Link>
            <Link href="/documentation/concepts/reports">
              <DocButton>
                {locale === 'es' ? 'Explorar Reportes' : 'Explore Reports'}
              </DocButton>
            </Link>
          </div>
        </section>

      </div>
    </div>
  );
} 