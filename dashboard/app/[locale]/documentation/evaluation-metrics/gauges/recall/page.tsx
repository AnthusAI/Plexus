'use client';

import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
import { Gauge, Segment } from "@/components/gauge"
import EvaluationCard from '@/components/EvaluationCard'
import {
  fixedAccuracyGaugeSegments, // Using as general 0-100% segments
  // Data for the \"Always Safe\" Email Filter (Prohibited is Positive Class)
  alwaysSafeEmailAccuracy,
  alwaysSafeEmailGwetAC1,
  alwaysSafeEmailClassDistribution,
  alwaysSafeEmailConfusionMatrix,
  alwaysSafeEmailPredictedDistribution,
} from "@/app/[locale]/documentation/evaluation-metrics/examples-data"
import { useTranslationContext } from '@/app/contexts/TranslationContext'

// Component to display a standalone Recall Gauge for illustration
const RecallGaugeDisplay = ({ value, title }: {
  value: number,
  title: string,
}) => (
  <div className="w-full max-w-[180px] mx-auto">
    <Gauge
      title={title}
      value={value} // Recall is 0-100
      min={0}
      max={100}
      showTicks={true}
      segments={fixedAccuracyGaugeSegments} // Using general 0-100 segments
    />
  </div>
);

// For the "Always Safe" filter, if "Prohibited" is the positive class:
// Actuals: 30 Prohibited, 970 Safe
// Model: Predicts ALL emails as "Safe"
// TP = 0 (Prohibited correctly ID'd as Prohibited)
// FP = 0 (Safe misclassified as Prohibited)
// FN = 30 (Prohibited misclassified as Safe)
// TN = 970 (Safe correctly ID'd as Safe)
const recallForProhibitedInAlwaysSafe = (0 / (0 + 30)) * 100; // 0%
const precisionForProhibitedInAlwaysSafe = 0; // 0 / (0 + 0) which is undefined, typically shown as 0 in this context

export default function RecallGaugePage() {
  const { locale } = useTranslationContext();

  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">El Indicador de Recuperación de Plexus</h1>
        <p className="text-lg text-muted-foreground mb-8">
          La recuperación, también conocida como Sensibilidad o Tasa de Verdaderos Positivos (TVP), responde la pregunta: <strong>"De todos los items que fueron realmente positivos, ¿qué proporción identificó correctamente el clasificador?"</strong> Mide la integridad o exhaustividad del clasificador para encontrar todas las instancias positivas. Un puntaje alto de recuperación indica que el clasificador tiene una tasa baja de Falsos Negativos (FN).
        </p>

        <div className="space-y-10">
          <section>
            <h2 className="text-2xl font-semibold mb-4">¿Por Qué es Importante la Recuperación?</h2>
            <p className="text-muted-foreground mb-4">
              Enfocarse en la recuperación es crítico en escenarios donde el costo de un Falso Negativo es alto. Un Falso Negativo ocurre cuando el modelo predice incorrectamente una instancia positiva como negativa. Ejemplos incluyen:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
              <li><strong>Diagnóstico Médico:</strong> No detectar una enfermedad seria en un paciente que realmente la tiene. Esto podría retrasar el tratamiento y tener consecuencias graves para la salud.</li>
              <li><strong>Detección de Fraude:</strong> Perder una transacción fraudulenta, llevando a pérdidas financieras.</li>
              <li><strong>Sistemas de Seguridad:</strong> Un vehículo autónomo no detectando un obstáculo, o un sistema de seguridad no detectando a un intruso.</li>
            </ul>
            <p className="text-muted-foreground mb-4">
              En estos casos, la alta recuperación es primordial para asegurar que se pierdan la menor cantidad posible de instancias positivas, incluso si eso significa aceptar un mayor número de Falsos Positivos (menor precisión).
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Cómo Funciona el Indicador de Recuperación de Plexus</h2>
            <p className="text-muted-foreground mb-4">
              El Indicador de Recuperación en Plexus muestra el puntaje de recuperación calculado, yendo de 0% a 100%. La fórmula es:
            </p>
            <p className="text-center text-lg font-semibold my-4 p-3 bg-muted rounded-md">
              Recuperación = Verdaderos Positivos / (Verdaderos Positivos + Falsos Negativos)
            </p>
            <p className="text-muted-foreground mb-6">
              Los segmentos visuales en el Indicador de Recuperación generalmente representan puntos de referencia estándar de rendimiento. Un puntaje de recuperación del 90% significa que el clasificador identificó exitosamente el 90% de todas las instancias positivas reales. Como la precisión, la interpretación directa es sencilla, y los segmentos categorizan visualmente este rendimiento.
            </p>
            <div className="my-6 p-6 rounded-lg bg-card border flex flex-col items-center">
              <h4 className="text-lg font-semibold mb-4 text-center">Ejemplo: Indicador de Recuperación</h4>
              <RecallGaugeDisplay value={75} title="Recuperación" />
              <p className="text-sm text-muted-foreground mt-3 text-center">
                Una recuperación del 75% indica que el clasificador encontró el 75% de todas las instancias positivas reales.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Recuperación en Acción: Escenarios de Ejemplo</h2>
            <p className="text-muted-foreground mb-4">
              Examinemos la recuperación usando nuestro contexto de filtro de email, donde "Prohibido" es la clase positiva que queremos detectar.
            </p>
            
            <div className="mb-8">
              <EvaluationCard
                title="El Filtro de Email 'Siempre Seguro' (Ejemplo de Baja Recuperación para 'Prohibido')"
                subtitle="Estrategia: Etiquetar TODOS los emails como 'Seguros'. Datos Reales: 3% Prohibidos, 97% Seguros."
                classDistributionData={alwaysSafeEmailClassDistribution}
                isBalanced={false}
                accuracy={alwaysSafeEmailAccuracy} // 97%
                gwetAC1={alwaysSafeEmailGwetAC1} // 0.0
                confusionMatrixData={alwaysSafeEmailConfusionMatrix}
                predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
                notes={`Recuperación para la clase 'Prohibido': ${recallForProhibitedInAlwaysSafe.toFixed(1)}%. Precisión para 'Prohibido': N/A (o 0%). Este filtro pierde TODOS los emails prohibidos, resultando en 0% de recuperación para esa clase crítica, a pesar de su alta precisión general.`}
              />
            </div>

            <p className="text-muted-foreground mb-4">
              El filtro "Siempre Seguro" tiene 0% de recuperación para la clase "Prohibido". Esto significa que falla en identificar cualquiera de los emails prohibidos. Aunque logra 97% de precisión al etiquetar correctamente los emails seguros, es inútil para su tarea principal de atrapar contenido prohibido debido a su falla catastrófica en recuperación para esa clase.
            </p>
            
            <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
              <h3 className="text-lg font-semibold mb-2">Contraste: El Objetivo de Alta Recuperación</h3>
              <p className="text-muted-foreground">
                En el tamizaje médico crítico (donde "Enfermedad Presente" es positivo), el objetivo es muy alta recuperación. Quieres identificar tantos casos verdaderos como sea posible, incluso si eso significa que algunos individuos sanos sean marcados para más pruebas (Falsos Positivos, llevando a menor precisión para la clase "Enfermedad Presente").
              </p>
            </div>
          </section>
          
          <section>
            <h2 className="text-2xl font-semibold mb-4">Recuperación y Precisión: El Intercambio</h2>
            <p className="text-muted-foreground mb-4">
              La recuperación y la <Link href="/es/documentation/evaluation-metrics/gauges/precision" className="text-primary hover:underline">Precisión</Link> a menudo exhiben una relación inversa. Aumentar la recuperación (ej., haciendo que un clasificador sea más sensible a casos positivos) puede a veces llevar a más Falsos Positivos, así reduciendo la precisión.
            </p>
            <p className="text-muted-foreground mb-4">
              El puntaje F1 es una métrica común que combina precisión y recuperación en un solo número (la media armónica), proporcionando una medida balanceada. Elegir si priorizar recuperación, precisión, o un balance depende enormemente de la aplicación específica y las consecuencias de diferentes tipos de errores.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Puntos Clave para la Recuperación</h2>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>La recuperación (Sensibilidad) mide la habilidad de encontrar todas las instancias positivas reales: VP / (VP + FN).</li>
              <li>Alta recuperación significa una tasa baja de Falsos Negativos.</li>
              <li>Crucial cuando el costo de los Falsos Negativos es alto.</li>
              <li>El Indicador de Recuperación de Plexus muestra este puntaje de 0-100%.</li>
              <li>A menudo se considera en conjunto con la Precisión; el puntaje F1 balancea ambos.</li>
            </ul>
          </section>

          <div className="flex flex-wrap gap-4 mt-12">
            <Link href="/es/documentation/evaluation-metrics">
              <DocButton variant="outline">Volver a la Vista General de Métricas de Evaluación</DocButton>
            </Link>
             <Link href="/es/documentation/evaluation-metrics/gauges/precision">
              <DocButton variant="outline">Aprende sobre el Indicador de Precisión</DocButton>
            </Link>
            <Link href="/es/documentation/evaluation-metrics/gauges-with-context">
              <DocButton variant="outline">Más sobre Indicadores con Contexto</DocButton>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">The Plexus Recall Gauge</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Recall, also known as Sensitivity or True Positive Rate (TPR), answers the question: <strong>"Of all the items that were actually positive, what proportion did the classifier correctly identify?"</strong> It measures the completeness or comprehensiveness of the classifier in finding all positive instances. A high recall score indicates that the classifier has a low rate of False Negatives (FN).
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Why is Recall Important?</h2>
          <p className="text-muted-foreground mb-4">
            Focusing on recall is critical in scenarios where the cost of a False Negative is high. A False Negative occurs when the model incorrectly predicts a positive instance as negative. Examples include:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>Medical Diagnosis:</strong> Failing to detect a serious disease in a patient who actually has it. This could delay treatment and have severe health consequences.</li>
            <li><strong>Fraud Detection:</strong> Missing a fraudulent transaction, leading to financial loss.</li>
            <li><strong>Safety Systems:</strong> An autonomous vehicle failing to detect an obstacle, or a security system failing to detect an intruder.</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            In these cases, high recall is paramount to ensure as few positive instances as possible are missed, even if it means accepting a higher number of False Positives (lower precision).
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How the Plexus Recall Gauge Works</h2>
          <p className="text-muted-foreground mb-4">
            The Recall Gauge in Plexus displays the calculated recall score, ranging from 0% to 100%. The formula is:
          </p>
          <p className="text-center text-lg font-semibold my-4 p-3 bg-muted rounded-md">
            Recall = True Positives / (True Positives + False Negatives)
          </p>
          <p className="text-muted-foreground mb-6">
            The visual segments on the Recall Gauge generally represent standard performance benchmarks. A recall score of 90% means the classifier successfully identified 90% of all actual positive instances. Like precision, the direct interpretation is straightforward, and the segments visually categorize this performance.
          </p>
          <div className="my-6 p-6 rounded-lg bg-card border flex flex-col items-center">
            <h4 className="text-lg font-semibold mb-4 text-center">Example: Recall Gauge</h4>
            <RecallGaugeDisplay value={75} title="Recall" />
            <p className="text-sm text-muted-foreground mt-3 text-center">
              A recall of 75% indicates that the classifier found 75% of all actual positive instances.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Recall in Action: Example Scenarios</h2>
          <p className="text-muted-foreground mb-4">
            Let's examine recall using our email filter context, where "Prohibited" is the positive class we aim to detect.
          </p>
          
          <div className="mb-8">
            <EvaluationCard
              title="The 'Always Safe' Email Filter (Low Recall Example for 'Prohibited')"
              subtitle="Strategy: Label ALL emails as 'Safe'. Actual Data: 3% Prohibited, 97% Safe."
              classDistributionData={alwaysSafeEmailClassDistribution}
              isBalanced={false}
              accuracy={alwaysSafeEmailAccuracy} // 97%
              gwetAC1={alwaysSafeEmailGwetAC1} // 0.0
              confusionMatrixData={alwaysSafeEmailConfusionMatrix}
              predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
              // EvaluationCard itself doesn\'t show per-class recall directly, so we explain in notes.
              notes={`Recall for 'Prohibited' class: ${recallForProhibitedInAlwaysSafe.toFixed(1)}%. Precision for 'Prohibited': N/A (or 0%). This filter misses ALL prohibited emails, resulting in 0% recall for that critical class, despite its high overall accuracy.`}
            />
          </div>

          <p className="text-muted-foreground mb-4">
            The "Always Safe" filter has 0% recall for the "Prohibited" class. This means it fails to identify any of the prohibited emails. While it achieves 97% accuracy by correctly labeling safe emails, it is useless for its primary task of catching prohibited content due to its catastrophic failure in recall for that class.
          </p>
          
          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Contrast: The Goal of High Recall</h3>
            <p className="text-muted-foreground">
              In critical medical screening (where "Disease Present" is positive), the goal is very high recall. You want to identify as many true cases as possible, even if it means some healthy individuals are flagged for further testing (False Positives, leading to lower precision for the "Disease Present" class).
            </p>
          </div>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Recall and Precision: The Trade-off</h2>
          <p className="text-muted-foreground mb-4">
            Recall and <Link href="/documentation/evaluation-metrics/gauges/precision" className="text-primary hover:underline">Precision</Link> often exhibit an inverse relationship. Increasing recall (e.g., by making a classifier more sensitive to positive cases) can sometimes lead to more False Positives, thereby reducing precision.
          </p>
          <p className="text-muted-foreground mb-4">
            The F1-score is a common metric that combines precision and recall into a single number (the harmonic mean), providing a balanced measure. Choosing whether to prioritize recall, precision, or a balance depends heavily on the specific application and the consequences of different types of errors.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Takeaways for Recall</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Recall (Sensitivity) measures the ability to find all actual positive instances: TP / (TP + FN).</li>
            <li>High recall means a low False Negative rate.</li>
            <li>Crucial when the cost of False Negatives is high.</li>
            <li>The Plexus Recall Gauge displays this score from 0-100%.</li>
            <li>Often considered in conjunction with Precision; the F1-score balances both.</li>
          </ul>
        </section>

        <div className="flex flex-wrap gap-4 mt-12">
          <Link href="/documentation/evaluation-metrics">
            <DocButton variant="outline">Back to Evaluation Metrics Overview</DocButton>
          </Link>
           <Link href="/documentation/evaluation-metrics/gauges/precision">
            <DocButton variant="outline">Learn about the Precision Gauge</DocButton>
          </Link>
          <Link href="/documentation/evaluation-metrics/gauges-with-context">
            <DocButton variant="outline">More on Gauges with Context</DocButton>
          </Link>
        </div>
      </div>
    </div>
  );
} 