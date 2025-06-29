'use client';

import Link from "next/link"
import { Card, CardContent } from "@/components/ui/card"
import { ac1GaugeSegments } from "@/components/ui/scorecard-evaluation"
import { Gauge, Segment } from "@/components/gauge"
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds"
import EvaluationCard from '@/components/EvaluationCard'
import { Button as DocButton } from "@/components/ui/button"
import { useTranslationContext } from '@/app/contexts/TranslationContext'

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

const fixedAccuracyGaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },
  { start: 50, end: 70, color: 'var(--gauge-converging)' },
  { start: 70, end: 80, color: 'var(--gauge-almost)' },
  { start: 80, end: 90, color: 'var(--gauge-viable)' },
  { start: 90, end: 100, color: 'var(--gauge-great)' },
];

export default function GaugesWithContextPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Agregando Contexto a los Indicadores de Evaluación</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Los puntajes de precisión cruda pueden ser engañosos sin el contexto apropiado. Esta plataforma emplea estrategias para hacer los indicadores de evaluación más interpretables al incorporar información sobre el número de clases, balance de clases, y usando métricas que son inherentemente conscientes del contexto.
        </p>

        <div className="space-y-10">
          <section>
            <h2 className="text-2xl font-semibold mb-4">Un Enfoque Unificado para la Claridad de Evaluación</h2>
            <p className="text-muted-foreground mb-4">
              Interpretar puntajes de precisión cruda como "75% preciso" es desafiante sin considerar el contexto crucial, principalmente el número de clases y su distribución dentro de los datos. Un enfoque unificado y multifacético aporta claridad al rendimiento del clasificador. Este enfoque combina estrategias que trabajan en conjunto:
            </p>
            <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
              <li>
                <strong className="text-foreground">Mejorando la Interpretabilidad de la Precisión Cruda:</strong> Se proporciona contexto esencial directamente a la métrica de precisión cruda ajustando dinámicamente las escalas visuales (colores y umbrales) del indicador de Precisión basado tanto en el número de clases como en la distribución de clases. Esta estrategia, detallada primero, hace que el número de precisión cruda en sí mismo sea más inmediatamente comprensible.
              </li>
              <li>
                <strong className="text-foreground">Empleando una Métrica de Acuerdo Inherentemente Consciente del Contexto:</strong> Junto con el indicador de Precisión contextualizado, se introduce una métrica distinta de "Acuerdo", como el AC1 de Gwet. Este tipo de métrica está diseñada para <em>internamente</em> considerar las complejidades del acuerdo por casualidad, el número de clases, y su distribución. Esta segunda estrategia, también detallada abajo, proporciona una perspectiva estable y corregida por casualidad que es directamente comparable entre diferentes escenarios de evaluación.
              </li>
            </ol>
            <p className="text-muted-foreground mb-4">
              Al usar estas estrategias juntas—presentando tanto un indicador de Precisión contextualizado como un indicador de Acuerdo auto-contextualizante—Plexus ofrece una comprensión integral y robusta del rendimiento del clasificador. Las siguientes explicaciones detallan cada una de estas estrategias complementarias.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Estrategia 1: Agregando Contexto al Indicador de Precisión</h2>
            <p className="text-muted-foreground mt-6 mb-4">
              Para abordar los desafíos de interpretar la precisión cruda, se puede agregar contexto directamente a la representación visual de la métrica. El indicador de Precisión en Plexus puede ajustar dinámicamente sus segmentos basándose en las características del problema. Esto involucra principalmente dos tipos de contexto: el número de clases y el balance de esas clases.
            </p>

            <h3 className="text-xl font-medium mt-6 mb-3">Tipo de Contexto A: Número de Clases</h3>
            <p className="text-muted-foreground mt-2 mb-4">
              El número de clases impacta significativamente el acuerdo de línea base por casualidad aleatoria. Una precisión del 50% significa algo muy diferente para un problema de 2 clases que para un problema de 12 clases. Al visualizar este contexto directamente en el indicador, el número de precisión cruda puede hacerse más interpretable.
            </p>

            <h3 className="text-xl font-medium mt-8 mb-3">Tipo de Contexto B: Desbalance de Clases</h3>
            <p className="text-muted-foreground mb-4">
              Ajustar el indicador de precisión para el desbalance de clases es el siguiente paso crítico. Incluso con el número correcto de clases, si las clases en sí mismas no están distribuidas uniformemente, la línea base para el rendimiento "por casualidad" o "sin habilidad" cambia.
            </p>

            <h3 className="text-xl font-medium mt-8 mb-3">Contexto Completo: Combinando Número de Clases Y Desbalance</h3>
            <p className="text-muted-foreground mb-4">
              Los indicadores de Precisión de Plexus, cuando están completamente contextualizados, contabilizan *tanto* el número de clases como su distribución simultáneamente. Esto proporciona la línea base más precisa contra la cual juzgar la precisión observada.
            </p>
          </section>

          <section className="mt-8">
            <h2 className="text-2xl font-semibold mb-4">Estrategia 2: El Indicador de Acuerdo - Inherentemente Consciente del Contexto</h2>
            <p className="text-muted-foreground mb-4">
              En lugar de agregar contexto externo para interpretar un indicador de precisión cruda, un enfoque alternativo y complementario es usar una métrica que inherentemente incorpore este contexto. El indicador de Acuerdo en Plexus (usando el AC1 de Gwet por defecto) hace exactamente esto.
            </p>

            <h3 className="text-xl font-medium mb-3">Interpretación Estandarizada A Través de Todos los Escenarios</h3>
            <p className="text-muted-foreground mb-4">
              Las métricas como el AC1 de Gwet están diseñadas para factorizar tanto el número de clases como su distribución para calcular un puntaje de acuerdo corregido por casualidad. Esto crea una escala estandarizada donde 0.0 siempre indica rendimiento equivalente al acuerdo por casualidad aleatoria para esa distribución de clases específica, y 1.0 indica acuerdo perfecto.
            </p>
          </section>

          <EvaluationCard
            title="Etiquetador de Temas de Artículos - Con Contexto de Conteo de Clases"
            subtitle="Nuestro clasificador de 5 clases (62% precisión). El indicador derecho está contextualizado para 5 clases balanceadas (línea base del 20% de casualidad)."
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            variant="default" 
            accuracyGaugeSegments={articleTopicLabelerClassCountOnlySegments}
            notes="Sin contexto (indicador izquierdo), 62% de precisión parece mediocre. Con segmentos contextuales para 5 clases balanceadas (indicador derecho), ¡la misma precisión del 62% se revela como un rendimiento excelente! Está muy por encima de la línea base de casualidad del 20% y cae bien dentro del segmento 'excelente' del indicador."
          />
          
          <p className="text-muted-foreground mt-4 mb-4">
            Al considerar solo la naturaleza de 5 clases (ignorando momentáneamente su desbalance), la precisión del 62% de nuestro Etiquetador de Temas de Artículos parece excelente, ya que está muy por encima de la línea base de casualidad del 20% para un problema balanceado de 5 clases. Sin embargo, esto es solo parte de la historia.
          </p>

          <h3 className="text-xl font-medium mt-8 mb-3">Tipo de Contexto B: Desbalance de Clases</h3>
          <p className="text-muted-foreground mb-4">
              Ajustar el indicador de precisión para el desbalance de clases es el siguiente paso crítico. Incluso con el número correcto de clases, si las clases en sí mismas no están distribuidas uniformemente, la línea base para el rendimiento "por casualidad" o "sin habilidad" cambia. Específicamente, una estrategia ingenua de siempre adivinar la clase mayoritaria puede lograr una precisión engañosamente alta. Los umbrales del indicador deben cambiar para reflejar esto.
          </p>
          
          <div className="mt-6 mb-8 p-5 bg-card">
            <h4 className="text-lg font-medium mb-3 text-center">Visualizando el Desbalance: Segmentos Fijos vs. Contexto de Distribución de Clases (Ejemplo de 75% de Precisión)</h4>
            <p className="text-sm text-muted-foreground mb-4 text-center">
              Considera un escenario con 75% de precisión en una tarea binaria donde las clases están desbalanceadas (75% Clase A, 25% Clase B).
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-4 bg-background rounded-md">
                <h5 className="text-base font-medium mb-2 text-center">Sin Contexto de Distribución de Clases</h5>
                <p className="text-xs text-muted-foreground mb-4 text-center">
                  Segmentos de indicador fijos estándar.
                </p>
                <AccuracyGauge value={75.0} title="Precisión" segments={fixedAccuracyGaugeSegments} />
                <p className="text-xs text-muted-foreground mt-4 text-center">
                  <strong>Potencialmente Engañoso:</strong> 75% de precisión parece "casi viable".
                </p>
              </div>
              <div className="p-4 bg-background rounded-md">
                <h5 className="text-base font-medium mb-2 text-center">Con Contexto de Distribución de Clases</h5>
                <p className="text-xs text-muted-foreground mb-4 text-center">
                  Segmentos ajustados dinámicamente para desbalance 75%/25%.
                </p>
                <AccuracyGauge value={75.0} title="Precisión" segments={imbal_scenario2_segments} />
                <p className="text-xs text-muted-foreground mt-4 text-center">
                  <strong>Interpretación Correcta:</strong> 75% de precisión está al nivel de "casualidad" (equivalente a siempre adivinar la clase mayoritaria).
                </p>
              </div>
            </div>
          </div>
          
          <EvaluationCard
            title="Baraja Sesgada (75% Roja) - Siempre Adivinando Roja"
            subtitle="Escenario: baraja con 75% de cartas rojas. Estrategia: siempre adivinar 'Roja'. Resultado: 75% de precisión. Indicador derecho contextualizado para este desbalance 75/25."
            classDistributionData={stackedDeckAlwaysRedClassDistribution}
            isBalanced={false}
            accuracy={stackedDeckAlwaysRedAccuracy}
            variant="default" 
            accuracyGaugeSegments={stackedDeckAlwaysRedAccuracySegments}
            notes="Con segmentos fijos (izquierda), 75% de precisión se ve 'casi viable'. Con segmentos contextualizados para el desbalance 75/25 (derecha), se muestra correctamente como rendimiento de nivel de casualidad, ya que siempre adivinar 'Roja' logra este 75%."
          />

          <EvaluationCard
            title="El Filtro de Email &quot;Siempre Seguro&quot; (97% Seguro)"
            subtitle="Escenario: 97% emails 'Seguros', 3% 'Prohibidos'. Estrategia: siempre predecir 'Seguro'. Resultado: 97% de precisión. Indicador derecho contextualizado para desbalance 97/3."
            classDistributionData={alwaysSafeEmailClassDistribution}
            isBalanced={false}
            accuracy={alwaysSafeEmailAccuracy}
            variant="default"
            accuracyGaugeSegments={alwaysSafeEmailAccuracySegments}
            notes="Con segmentos fijos (izquierda), 97% de precisión se ve 'excelente'. Con segmentos contextualizados para el desbalance 97/3 (derecha), se muestra correctamente como nivel de casualidad. La verdadera habilidad requiere >97% en este escenario. Los segmentos de colores 'bueno' y 'excelente' están comprimidos en el extremo derecho."
          />
          
          <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
            <h4 className="text-lg font-semibold mb-2">Insight Clave: El Desbalance de Clases Redefine la "Buena" Precisión</h4>
            <p className="text-muted-foreground mb-3">
              Estos ejemplos demuestran cómo agregar contexto de distribución de clases a los indicadores de precisión transforma la interpretación. <strong className="text-foreground">Lo que inicialmente parece como buen rendimiento con indicadores fijos puede revelarse como meramente línea base de casualidad una vez que se factoriza el desbalance de clases.</strong> Los segmentos del indicador deben cambiar para mostrar que el rendimiento genuinamente bueno requiere exceder lo que estrategias simples (como "siempre adivinar la clase mayoritaria") lograrían.
            </p>
          </div>
          
          <div className="my-8 p-6 rounded-lg bg-card">
            <h4 className="text-lg font-semibold mb-6 text-center">Visualizando Contexto: Impacto del Desbalance de Clases Variado (Ejemplo de 65% de Precisión)</h4>
            <p className="text-sm text-muted-foreground mb-4 text-center">
              Cada escenario abajo muestra una precisión del 65%. El indicador superior usa segmentos fijos, mientras que el indicador inferior ajusta segmentos basándose en el desbalance de clases especificado.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Balanceado (50/50)</h5>
                <AccuracyGauge value={65.0} title="Segmentos Fijos" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Segmentos Contextuales" segments={imbal_scenario1_segments} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Desbalanceado (75/25)</h5>
                <AccuracyGauge value={65.0} title="Segmentos Fijos" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Segmentos Contextuales" segments={imbal_scenario2_segments} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">3-Clases Desbal. (80/10/10)</h5>
                <AccuracyGauge value={65.0} title="Segmentos Fijos" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Segmentos Contextuales" segments={imbal_scenario4_segments} />
              </div>
              <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                <h5 className="text-md font-medium text-center">Muy Desbal. (95/5)</h5>
                <AccuracyGauge value={65.0} title="Segmentos Fijos" segments={fixedAccuracyGaugeSegments} />
                <AccuracyGauge value={65.0} title="Segmentos Contextuales" segments={imbal_scenario3_segments} />
              </div>
            </div>
          </div>

          <h3 className="text-xl font-medium mt-8 mb-3">Contexto Completo: Combinando Número de Clases Y Desbalance</h3>
          <p className="text-muted-foreground mb-4">
            Los indicadores de Precisión de Plexus, cuando están completamente contextualizados, contabilizan *tanto* el número de clases como su distribución simultáneamente. Esto proporciona la línea base más precisa contra la cual juzgar la precisión observada.
          </p>

          <EvaluationCard
            title="Etiquetador de Temas de Artículos - Con Contexto Completo (Conteo de Clases y Desbalance)"
            subtitle="Nuestro clasificador desbalanceado de 5 clases (62% precisión, 40% Noticias). Indicador derecho contextualizado para su naturaleza de 5 clases Y su distribución desbalanceada (40% Noticias, 15% otros)."
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            variant="default" 
            accuracyGaugeSegments={articleTopicLabelerFullContextSegments} 
            notes="El indicador (fijo) izquierdo sugiere que 62% es 'convergente'. El indicador (completamente contextualizado) derecho lo muestra como 'bueno', pero no 'excelente'. El nivel de casualidad, considerando una clase mayoritaria del 40% entre 5 opciones, es más alto que el simple 20% para un problema balanceado de 5 clases pero más bajo que solo adivinar la mayoría. Esto hace que 62% sea bueno, pero menos estelar que si las clases estuvieran balanceadas o si solo se considerara ingenuamente el conteo de clases sin desbalance."
          />
          
          <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
              <h4 className="text-lg font-semibold mb-2">Insight Clave: El Contexto Completo es Matizado</h4>
              <p className="text-muted-foreground">
                El indicador de precisión completamente contextualizado proporciona la imagen más matizada. Para el Etiquetador de Temas de Artículos (62% precisión, 5 clases, 40% clase mayoritaria), el rendimiento es bueno—significativamente mejor que estrategias ingenuas (ej., siempre adivinar 'Noticias' para 40% de precisión, o adivinanza aleatoria de 5 clases al 20%). Sin embargo, la barra para 'excelente' es más alta que si las clases estuvieran perfectamente balanceadas, reflejando la ligera ventaja obtenida del desbalance existente.
              </p>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold mb-4">Estrategia 2: El Indicador de Acuerdo - Inherentemente Consciente del Contexto</h2>
          <p className="text-muted-foreground mb-4">
            En lugar de agregar contexto externo para interpretar un indicador de precisión cruda, un enfoque alternativo y complementario es usar una métrica que inherentemente incorpore este contexto. El indicador de Acuerdo en Plexus (usando el AC1 de Gwet por defecto) hace exactamente esto.
          </p>

          <h3 className="text-xl font-medium mb-3">Interpretación Estandarizada A Través de Todos los Escenarios</h3>
          <p className="text-muted-foreground mb-4">
            Las métricas como el AC1 de Gwet están diseñadas para factorizar tanto el número de clases como su distribución para calcular un puntaje de acuerdo corregido por casualidad. Esto crea una escala estandarizada:
          </p>
          <ul className="list-disc pl-6 space-y-1 mb-4 text-muted-foreground">
            <li><strong className="text-foreground">0.0:</strong> Rendimiento equivalente al acuerdo de casualidad aleatoria para esa distribución de clases específica.</li>
            <li><strong className="text-foreground">1.0:</strong> Acuerdo perfecto (todas las predicciones correctas).</li>
            <li><strong className="text-foreground">-1.0:</strong> Desacuerdo sistemático perfecto (ej., siempre incorrecto cuando podría estar correcto).</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            Un puntaje de, por ejemplo, 0.6 en el indicador de Acuerdo representa el mismo nivel de rendimiento *por encima de la casualidad* sin importar si es un problema binario, un problema de 10 clases, o un conjunto de datos altamente desbalanceado.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-6">
            <div className="flex flex-col items-center p-4 bg-card rounded-md">
              <h4 className="text-xl font-semibold mb-2">Opuesto</h4>
              <div className="w-full max-w-[150px] mx-auto mb-2">
                <Gauge title="Acuerdo" value={-1.0} min={-1} max={1} segments={ac1GaugeSegments} showTicks={false} />
              </div>
              <p className="text-sm text-muted-foreground text-center">Desacuerdo sistemático perfecto.</p>
            </div>
            <div className="flex flex-col items-center p-4 bg-card rounded-md">
              <h4 className="text-xl font-semibold mb-2">Aleatorio</h4>
              <div className="w-full max-w-[150px] mx-auto mb-2">
                <Gauge title="Acuerdo" value={0.0} min={-1} max={1} segments={ac1GaugeSegments} showTicks={false} />
              </div>
              <p className="text-sm text-muted-foreground text-center">Sin habilidad más allá de la casualidad.</p>
            </div>
            <div className="flex flex-col items-center p-4 bg-card rounded-md">
              <h4 className="text-xl font-semibold mb-2">Perfecto</h4>
              <div className="w-full max-w-[150px] mx-auto mb-2">
                <Gauge title="Acuerdo" value={1.0} min={-1} max={1} segments={ac1GaugeSegments} showTicks={false} />
              </div>
              <p className="text-sm text-muted-foreground text-center">Acuerdo perfecto.</p>
            </div>
          </div>

          <p className="text-muted-foreground mb-4">
            Veamos cómo el indicador de Acuerdo y el indicador de Precisión completamente contextualizado trabajan juntos para varios escenarios.
          </p>

          <EvaluationCard
            title="Predicción Aleatoria de Lanzamiento de Moneda (50/50)"
            subtitle="Moneda justa, adivinanza aleatoria logró 48% de precisión en esta ejecución."
            classDistributionData={fairCoinDistribution}
            isBalanced={true}
            accuracy={fairCoinData.accuracy}
            gwetAC1={fairCoinData.ac1}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={dynamicSegments2Class}
            notes="Ambos indicadores muestran rendimiento ligeramente por debajo de la casualidad. Acuerdo (AC1=-0.04) está justo por debajo de 0. Precisión Contextual (48%) está justo por debajo de la línea base del 50% de casualidad para un problema binario balanceado."
          />

          <EvaluationCard
            title="Predicción Aleatoria de Palo de Carta (4 Clases Balanceadas)"
            subtitle="Cuatro palos igualmente probables, adivinanza aleatoria logró 23% de precisión."
            classDistributionData={cardSuitActualDistribution}
            isBalanced={true}
            accuracy={cardSuitData.accuracy}
            gwetAC1={cardSuitData.ac1}
            confusionMatrixData={cardSuitConfusionMatrix}
            predictedClassDistributionData={cardSuitPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={dynamicSegments4Class}
            notes="Ambos indicadores indican rendimiento ligeramente por debajo de la casualidad. Acuerdo (AC1=-0.03) está justo por debajo de 0. Precisión Contextual (23%) está justo por debajo de la línea base del 25% de casualidad para un problema balanceado de 4 clases."
          />
          
          <div className="p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6 mb-4">
            <h4 className="text-lg font-semibold mb-2">Insight Clave: El Indicador de Acuerdo Resiste el Engaño del Desbalance</h4>
            <p className="text-muted-foreground mb-3">
              El verdadero poder del indicador de Acuerdo se vuelve evidente en escenarios desbalanceados donde la precisión cruda puede ser altamente engañosa. El indicador de Acuerdo automáticamente se ajusta para esto, proporcionando una medida consistente de habilidad más allá de la casualidad.
            </p>
            <p className="text-muted-foreground">
               Por ejemplo, un clasificador que siempre adivina la clase mayoritaria en un conjunto de datos desbalanceado tendrá un puntaje de Acuerdo de 0.0 (o muy cerca), indicando claramente que no tiene capacidad predictiva real, incluso si su precisión cruda es alta. Esto expone un rendimiento aparentemente bueno como que no tiene habilidad real.
            </p>
          </div>

          <EvaluationCard
            title="Siempre Prediciendo Roja (Baraja Sesgada 75/25)"
            subtitle="La baraja es 75% Roja. Estrategia: siempre adivinar 'Roja'. Logra 75% de precisión."
            classDistributionData={stackedDeckAlwaysRedClassDistribution}
            isBalanced={false}
            accuracy={stackedDeckAlwaysRedAccuracy}
            gwetAC1={stackedDeckAlwaysRedGwetAC1}
            confusionMatrixData={stackedDeckAlwaysRedConfusionMatrix}
            predictedClassDistributionData={stackedDeckAlwaysRedPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={stackedDeckAlwaysRedAccuracySegments}
            notes="A pesar del 75% de precisión, el indicador de Acuerdo (AC1=0.00) muestra correctamente que no hay habilidad predictiva más allá de la casualidad (que es efectivamente lo que siempre adivinar la mayoría es en este contexto). El indicador de Precisión contextual también muestra correctamente que 75% es el nivel de línea base de casualidad aquí."
          />
          
          <EvaluationCard
            title="El Filtro de Email &quot;Siempre Seguro&quot; - Ambos Indicadores Revelan la Verdad"
            subtitle="Conjunto de datos: 97% 'Seguro', 3% 'Prohibido'. El filtro siempre predice 'Seguro', logrando 97% de precisión."
            classDistributionData={alwaysSafeEmailClassDistribution}
            isBalanced={false}
            accuracy={alwaysSafeEmailAccuracy}
            gwetAC1={alwaysSafeEmailGwetAC1}
            confusionMatrixData={alwaysSafeEmailConfusionMatrix}
            predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={alwaysSafeEmailAccuracySegments}
            notes="La extremidad de este ejemplo es poderosa. A pesar de una precisión del 97%, ambos indicadores revelan la verdad: cero habilidad predictiva. Acuerdo (AC1=0.0) y el indicador de Precisión contextual (mostrando que 97% es la línea base) ambos exponen este filtro como inútil para capturar contenido prohibido."
          />
          
          <div className="p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6 mb-4">
              <h4 className="text-lg font-semibold mb-2">Beneficios del Indicador de Acuerdo</h4>
              <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                <li><strong className="text-foreground">Interpretación Simplificada:</strong> Los usuarios no necesitan factorizar mentalmente la distribución de clases o el número de clases - el indicador lo hace por ellos. 0.0 siempre es casualidad.</li>
                <li><strong className="text-foreground">Comparabilidad Directa:</strong> Los puntajes de Acuerdo pueden compararse directamente entre diferentes clasificadores y conjuntos de datos, sin importar sus estructuras de clases subyacentes.</li>
                <li><strong className="text-foreground">Insight Inmediato:</strong> Revela instantáneamente si un clasificador tiene poder predictivo real más allá de lo que se espera por casualidad para ese problema específico.</li>
                <li><strong className="text-foreground">Resistencia al Engaño:</strong> Expone números de precisión aparentemente altos que en realidad no representan habilidad predictiva real en situaciones desbalanceadas.</li>
              </ul>
          </div>
          
          <EvaluationCard
            title="Etiquetador de Temas de Artículos - La Imagen Completa con Ambos Indicadores"
            subtitle="Nuestro clasificador desbalanceado de 5 clases (62% precisión, 40% Noticias). ¿Cómo cuentan ambos indicadores la historia?"
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            gwetAC1={articleTopicLabelerExampleData.gwetAC1}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
            notes="El indicador de Acuerdo (AC1 = 0.512) muestra acuerdo moderado más allá de la casualidad, contabilizando inherentemente la naturaleza de 5 clases y la distribución 40/15/15/15/15. Este puntaje nos dice directamente su nivel de habilidad por encima de la línea base. El indicador de Precisión completamente contextualizado confirma esto: 62% es 'bueno' para esta configuración específica, pero no en el nivel más alto. Ambos indicadores proporcionan una vista consistente y matizada."
          />
          
          <p className="text-muted-foreground mt-4 mb-4">
            Para el Etiquetador de Temas de Artículos, el puntaje de Acuerdo de 0.512 proporciona instantáneamente una evaluación clara: habilidad predictiva moderada. Este número único y estandarizado muestra que rinde notablemente mejor que la casualidad para su configuración específica, pero no está logrando acuerdo de nivel superior. Complementa el indicador de Precisión contextualizado, que muestra visualmente *por qué* 62% se considera "bueno" en este escenario particular de múltiples clases desbalanceadas.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Conclusión: Una Vista Multifacética para Verdadera Comprensión</h2>
          <p className="text-muted-foreground mb-4">
            Plexus utiliza tanto indicadores de Precisión contextualizados como indicadores de Acuerdo inherentemente conscientes del contexto (como el AC1 de Gwet). Este enfoque dual proporciona una comprensión integral y confiable del rendimiento del clasificador:
          </p>
          <ul className="list-disc pl-6 space-y-3 my-6 text-muted-foreground">
            <li>
                <strong className="text-foreground">Indicador de Precisión Contextualizado:</strong> Ayuda a interpretar la métrica familiar 'porcentaje correcto' ajustando visualmente su escala (colores y umbrales) basándose en el conteo de clases específico del problema y desbalance. Responde: "¿Qué tan buena es esta precisión cruda *para esta configuración particular del problema*?"
            </li>
            <li>
                <strong className="text-foreground">Indicador de Acuerdo (ej., AC1 de Gwet):</strong> Proporciona un puntaje estandarizado, corregido por casualidad. Inherentemente contabiliza el conteo de clases y desbalance. Responde: "¿Cuánta habilidad demuestra este clasificador *más allá de la casualidad aleatoria*, de una manera que sea comparable entre diferentes problemas?"
            </li>
          </ul>
          <p className="text-muted-foreground mb-4">
            Juntos, estos indicadores ofrecen insights robustos, previniendo la mala interpretación de números de precisión cruda y destacando claramente el verdadero rendimiento de un clasificador relativo a las expectativas de línea base y su habilidad inherente.
          </p>
          <div className="flex flex-wrap gap-4 mt-8">
            <Link href="/es/documentation/evaluation-metrics">
              <DocButton variant="outline">Volver a la Vista General de Métricas de Evaluación</DocButton>
            </Link>
            <Link href="/es/documentation/evaluation-metrics/examples">
              <DocButton>Ver Más Ejemplos de Métricas</DocButton>
            </Link>
          </div>
        </section>

          <div className="flex flex-wrap gap-4 mt-8">
            <Link href="/es/documentation/evaluation-metrics">
              <DocButton variant="outline">Volver a la Vista General de Métricas de Evaluación</DocButton>
            </Link>
            <Link href="/es/documentation/evaluation-metrics/examples">
              <DocButton>Ver Más Ejemplos de Métricas</DocButton>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // English content (default)
  const articleTopicLabelerExampleData = {
    id: 'article-topic-labeler',
    score_name: 'Article Topic Labeler Performance',
    cc_question_id: 'example-topic-labeler',
    accuracy: 62.0,
    item_count: 100,
    mismatches: 38,
    gwetAC1: 0.512,
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
  
  const balanced5ClassDistribution = { 'Class1': 20, 'Class2': 20, 'Class3': 20, 'Class4': 20, 'Class5': 20 };
  const articleTopicLabelerClassCountOnlySegments = GaugeThresholdComputer.createSegments(
    GaugeThresholdComputer.computeThresholds(balanced5ClassDistribution)
  );
  
  const articleTopicLabelerFullContextSegments = GaugeThresholdComputer.createSegments(
    GaugeThresholdComputer.computeThresholds(articleTopicLabelerExampleData.label_distribution)
  );

  const scenario1Data = createExampleScore(
    'scenario1-balanced-2class',
    'Scenario 1: Balanced 2-Class Data (50/50)',
    0.50, 
    75.0,
    1000,
    250,
    { 'Yes': 500, 'No': 500 }
  )
  
  const fairCoinData = createExampleScore(
    'fair-coin',
    'Randomly Guessing Coin Flips (50/50)',
    -0.04, 
    48.0, 
    100,  
    52,   
    { 'Heads': 50, 'Tails': 50 }
  )
    
  const scenario2Data = createExampleScore(
    'scenario2-balanced-4class',
    'Scenario 2: Balanced 4-Class Data (25/25/25/25)',
    0.67, 
    75.0,
    1000,
    250,
    { 'ClassA': 250, 'ClassB': 250, 'ClassC': 250, 'ClassD': 250 }
  )

  const fairCoinDistribution = [
    { label: "Heads", count: 51 },
    { label: "Tails", count: 49 }
  ];

  const thresholds2Class = GaugeThresholdComputer.computeThresholds(scenario1Data.label_distribution!);
  const dynamicSegments2Class = GaugeThresholdComputer.createSegments(thresholds2Class);

  const thresholds4Class = GaugeThresholdComputer.computeThresholds(scenario2Data.label_distribution!);
  const dynamicSegments4Class = GaugeThresholdComputer.createSegments(thresholds4Class);

  const label_distribution_3_class = { C1: 1, C2: 1, C3: 1 };
  const thresholds3Class = GaugeThresholdComputer.computeThresholds(label_distribution_3_class);
  const dynamicSegments3Class = GaugeThresholdComputer.createSegments(thresholds3Class);

  const label_distribution_12_class: Record<string, number> = {};
  for (let i = 1; i <= 12; i++) {
    label_distribution_12_class[`Class ${i}`] = 1;
  }
  const thresholds12Class = GaugeThresholdComputer.computeThresholds(label_distribution_12_class);
  const dynamicSegments12Class = GaugeThresholdComputer.createSegments(thresholds12Class);

  const imbal_scenario1_dist = { C1: 50, C2: 50 };
  const imbal_scenario1_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario1_dist);
  const imbal_scenario1_segments = GaugeThresholdComputer.createSegments(imbal_scenario1_thresholds);

  const imbal_scenario2_dist = { C1: 75, C2: 25 };
  const imbal_scenario2_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario2_dist);
  const imbal_scenario2_segments = GaugeThresholdComputer.createSegments(imbal_scenario2_thresholds);

  const imbal_scenario3_dist = { C1: 95, C2: 5 };
  const imbal_scenario3_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario3_dist);
  const imbal_scenario3_segments = GaugeThresholdComputer.createSegments(imbal_scenario3_thresholds);

  const imbal_scenario4_dist = { C1: 80, C2: 10, C3: 10 };
  const imbal_scenario4_thresholds = GaugeThresholdComputer.computeThresholds(imbal_scenario4_dist);
  const imbal_scenario4_segments = GaugeThresholdComputer.createSegments(imbal_scenario4_thresholds);

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

  const alwaysSafeEmailClassDistribution = [
    { label: "Safe", count: 970 },
    { label: "Prohibited", count: 30 }
  ];
  const alwaysSafeEmailConfusionMatrix = {
    labels: ["Safe", "Prohibited"],
    matrix: [
      { actualClassLabel: "Safe", predictedClassCounts: { "Safe": 970, "Prohibited": 0 } },
      { actualClassLabel: "Prohibited", predictedClassCounts: { "Safe": 30, "Prohibited": 0 } },
    ],
  };
  const alwaysSafeEmailPredictedDistribution = [
    { label: "Safe", count: 1000 }, { label: "Prohibited", count: 0 }
  ];
  const alwaysSafeEmailAccuracy = 97.0;
  const alwaysSafeEmailGwetAC1 = 0.0;
  const alwaysSafeEmailAccuracySegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Safe': 970, 'Prohibited': 30 }));

  const stackedDeckAlwaysRedClassDistribution = [ { label: "Red", count: 75 }, { label: "Black", count: 25 } ];
  const stackedDeckAlwaysRedConfusionMatrix = {
    labels: ["Red", "Black"],
    matrix: [
      { actualClassLabel: "Red", predictedClassCounts: { "Red": 75, "Black": 0 } },
      { actualClassLabel: "Black", predictedClassCounts: { "Red": 25, "Black": 0 } },
    ],
  };
  const stackedDeckAlwaysRedPredictedDistribution = [ { label: "Red", count: 100 }, { label: "Black", count: 0 } ];
  const stackedDeckAlwaysRedAccuracy = 75.0;
  const stackedDeckAlwaysRedGwetAC1 = 0.0;
  const stackedDeckAlwaysRedAccuracySegments = GaugeThresholdComputer.createSegments(GaugeThresholdComputer.computeThresholds({ 'Red': 75, 'Black': 25 }));

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Adding Context to Evaluation Gauges</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Raw accuracy scores can be misleading without appropriate context. This platform employs strategies for making evaluation gauges more interpretable by incorporating information about the number of classes, class balance, and by using metrics that are inherently context-aware.
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">A Unified Approach to Evaluation Clarity</h2>
          <p className="text-muted-foreground mb-4">
            Interpreting raw accuracy scores like "75% accurate" is challenging without considering crucial context, primarily the number of classes and their distribution within the data. A unified, multi-faceted approach brings clarity to classifier performance. This approach combines strategies that work in tandem:
          </p>
          <ol className="list-decimal pl-6 space-y-3 my-6 text-muted-foreground bg-card/50 p-4 rounded-md">
            <li>
              <strong className="text-foreground">Enhancing Raw Accuracy's Interpretability:</strong> Essential context is provided directly to the raw accuracy metric by dynamically adjusting the visual scales (colors and thresholds) of the Accuracy gauge based on both the number of classes and the class distribution. This strategy, detailed first, makes the raw accuracy number itself more immediately understandable.
            </li>
            <li>
              <strong className="text-foreground">Employing an Inherently Context-Aware Agreement Metric:</strong> Alongside the contextualized Accuracy gauge, a distinct "Agreement" metric, such as Gwet's AC1, is introduced. This type of metric is designed to <em>internally</em> account for the complexities of chance agreement, the number of classes, and their distribution. This second strategy, also detailed below, provides a stable, chance-corrected perspective that is directly comparable across different evaluation scenarios.
            </li>
          </ol>
          <p className="text-muted-foreground mb-4">
            By using these strategies together—presenting both a contextualized Accuracy gauge and a self-contextualizing Agreement gauge—Plexus offers a comprehensive and robust understanding of classifier performance. The following explanations detail each of these complementary strategies.
          </p>
        </section>

        <section>
            <h2 className="text-2xl font-semibold mb-2">Strategy 1: Adding Context to the Accuracy Gauge</h2>
            <p className="text-muted-foreground mt-6 mb-4">
              To address the challenges of interpreting raw accuracy, context can be added directly to the metric's visual representation. The Accuracy gauge in Plexus can dynamically adjust its segments based on the problem's characteristics. This primarily involves two types of context: the number of classes and the balance of those classes.
            </p>

            <h3 className="text-xl font-medium mt-6 mb-3">Context Type A: Number of Classes</h3>
            <p className="text-muted-foreground mt-2 mb-4">
                The number of classes significantly impacts the baseline random-chance agreement. A 50% accuracy means something very different for a 2-class problem than for a 12-class problem. By visualizing this context directly on the gauge, the raw accuracy number can be made more interpretable. By calculating a "chance level" or baseline for a specific dataset (based on the number of classes, assuming a balanced distribution for this specific adjustment), the gauge's colors can visually indicate whether the achieved accuracy is substantially better than random guessing, just slightly better, or even close to what chance would predict.
            </p>
            
            <p className="text-muted-foreground mb-4">
              This approach retains raw accuracy but enhances its interpretability by providing crucial context through dynamic visual scales on Accuracy gauges. The background colors and threshold markers on the Accuracy gauge adapt based on the number of classes (assuming balanced distributions for this part of the explanation).
            </p>

            <EvaluationCard
              title="Coin Flip Prediction (50/50)"
              subtitle="A fair coin has a 50% chance of heads or tails. Random guessing achieves about 50% accuracy."
              classDistributionData={fairCoinDistribution}
              isBalanced={true}
              accuracy={50}
              variant="default"
              accuracyGaugeSegments={dynamicSegments2Class}
              notes="Without context (left gauge), 50% accuracy is just a number. With proper contextual segments for a 2-class problem (right gauge), we see that 50% is exactly at the chance level, indicating no prediction skill beyond random guessing."
            />

            <EvaluationCard
              title="Card Suit Prediction (4 Balanced Classes)"
              subtitle="A standard deck has four equally likely suits. Random guessing achieves about 25% accuracy."
              classDistributionData={cardSuitActualDistribution}
              isBalanced={true}
              accuracy={25}
              variant="default"
              accuracyGaugeSegments={dynamicSegments4Class}
              notes="Without context (left gauge), 25% accuracy appears very low. With proper contextual segments for a 4-class problem (right gauge), we see that 25% is exactly at the chance level, indicating no prediction skill beyond random guessing."
            />

            <p className="text-muted-foreground mt-4 mb-4">
              The dynamic gauges adjust their colors to match what "baseline random chance" means for each specific task based on class count (assuming balanced classes for this specific point). 
              Instead of misleadingly suggesting that random guessing is "poor performance" in multi-class problems, 
              the adjusted gauge shows it's exactly what you'd expect from chance. This makes it much easier to understand 
              when a model is actually performing better than random guessing.
            </p>
            
            <div className="my-8 p-6 rounded-lg bg-card">
              <h4 className="text-lg font-semibold mb-6 text-center">Visualizing Context: Impact of Number of Classes on Accuracy Interpretation (65% Accuracy Example)</h4>
              <p className="text-sm text-muted-foreground mb-4 text-center">
                Each scenario below shows a 65% accuracy. The left gauge has no context (fixed scale), while the right gauge adjusts its segments based on the number of classes (assuming balanced distribution for this visualization).
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Two-Class</h5>
                  <AccuracyGauge value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="With Class Context" segments={dynamicSegments2Class} />
                </div>
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Three-Class</h5>
                  <AccuracyGauge value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="With Class Context" segments={dynamicSegments3Class} />
                </div>
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Four-Class</h5>
                  <AccuracyGauge value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="With Class Context" segments={dynamicSegments4Class} />
                </div>
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Twelve-Class</h5>
                  <AccuracyGauge value={65.0} title="No Context" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="With Class Context" segments={dynamicSegments12Class} />
                </div>
              </div>
            </div>

            <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
                <h4 className="text-lg font-semibold mb-2">Key Insight: Number of Classes Drastically Alters Accuracy Perception</h4>
              <p className="text-muted-foreground mb-3">
                  These examples demonstrate a critical point: <strong className="text-foreground">you cannot interpret accuracy numbers without understanding the context of class count</strong>. 
                  A 65% accuracy score might be weak for a binary classifier (where chance is 50%) but represents strong performance for a 12-class problem (where chance is ~8.3%). Contextualizing the gauge for the number of classes (assuming balance for this step) is crucial for meaningful interpretation.
              </p>
            </div>
            
            <EvaluationCard
              title="Article Topic Labeler - With Class Count Context"
              subtitle="Our 5-class classifier (62% accuracy). The right gauge is contextualized for 5 balanced classes (20% chance baseline)."
              classDistributionData={articleTopicLabelerClassDistribution}
              isBalanced={false}
              accuracy={articleTopicLabelerExampleData.accuracy}
              confusionMatrixData={articleTopicLabelerConfusionMatrix}
              predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
              variant="default" 
              accuracyGaugeSegments={articleTopicLabelerClassCountOnlySegments}
              notes="Without context (left gauge), 62% accuracy seems mediocre. With contextual segments for 5 balanced classes (right gauge), the same 62% accuracy is revealed to be excellent performance! It's far above the 20% random chance baseline and falls well into the 'great' segment of the gauge."
            />
            
            <p className="text-muted-foreground mt-4 mb-4">
              When accounting only for the 5-class nature (momentarily ignoring its imbalance), our Article Topic Labeler's 62% accuracy appears excellent, as it's far above the 20% random chance baseline for a balanced 5-class problem. However, this is only part of the story.
            </p>

            <h3 className="text-xl font-medium mt-8 mb-3">Context Type B: Class Imbalance</h3>
            <p className="text-muted-foreground mb-4">
                Adjusting the accuracy gauge for class imbalance is the next critical step. Even with the correct number of classes, if the classes themselves are not evenly distributed, the baseline for "chance" or "no skill" performance changes. Specifically, a naive strategy of always guessing the majority class can achieve deceptively high accuracy. The gauge thresholds must shift to reflect this.
            </p>
            
            <div className="mt-6 mb-8 p-5 bg-card">
              <h4 className="text-lg font-medium mb-3 text-center">Visualizing Imbalance: Fixed vs. Class Distribution Context (75% Accuracy Example)</h4>
              <p className="text-sm text-muted-foreground mb-4 text-center">
                Consider a scenario with 75% accuracy on a binary task where classes are imbalanced (75% Class A, 25% Class B).
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-4 bg-background rounded-md">
                  <h5 className="text-base font-medium mb-2 text-center">Without Class Distribution Context</h5>
                  <p className="text-xs text-muted-foreground mb-4 text-center">
                    Standard fixed gauge segments.
                  </p>
                  <AccuracyGauge value={75.0} title="Accuracy" segments={fixedAccuracyGaugeSegments} />
                  <p className="text-xs text-muted-foreground mt-4 text-center">
                    <strong>Potentially Misleading:</strong> 75% accuracy appears "almost viable."
                  </p>
                </div>
                <div className="p-4 bg-background rounded-md">
                  <h5 className="text-base font-medium mb-2 text-center">With Class Distribution Context</h5>
                  <p className="text-xs text-muted-foreground mb-4 text-center">
                    Dynamically adjusted segments for 75%/25% imbalance.
                  </p>
                  <AccuracyGauge value={75.0} title="Accuracy" segments={imbal_scenario2_segments} />
                  <p className="text-xs text-muted-foreground mt-4 text-center">
                    <strong>Correct Interpretation:</strong> 75% accuracy is at "chance" level (equivalent to always guessing the majority class).
                  </p>
                </div>
              </div>
            </div>
            
            <EvaluationCard
              title="Stacked Deck (75% Red) - Always Guessing Red"
              subtitle="Scenario: deck with 75% red cards. Strategy: always guess 'Red'. Result: 75% accuracy. Right gauge contextualized for this 75/25 imbalance."
              classDistributionData={stackedDeckAlwaysRedClassDistribution}
              isBalanced={false}
              accuracy={stackedDeckAlwaysRedAccuracy}
              variant="default" 
              accuracyGaugeSegments={stackedDeckAlwaysRedAccuracySegments}
              notes="With fixed segments (left), 75% accuracy looks 'almost viable'. With segments contextualized for the 75/25 imbalance (right), it's correctly shown as chance-level performance, as always guessing 'Red' achieves this 75%."
            />

            <EvaluationCard
              title="The &quot;Always Safe&quot; Email Filter (97% Safe)"
              subtitle="Scenario: 97% 'Safe' emails, 3% 'Prohibited'. Strategy: always predict 'Safe'. Result: 97% accuracy. Right gauge contextualized for 97/3 imbalance."
              classDistributionData={alwaysSafeEmailClassDistribution}
              isBalanced={false}
              accuracy={alwaysSafeEmailAccuracy}
              variant="default"
              accuracyGaugeSegments={alwaysSafeEmailAccuracySegments}
              notes="With fixed segments (left), 97% accuracy looks 'great'. With segments contextualized for the 97/3 imbalance (right), it's correctly shown as chance-level. True skill requires >97% in this scenario. The colored 'good' and 'great' segments are compressed to the far right."
            />
            
            <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
              <h4 className="text-lg font-semibold mb-2">Key Insight: Class Imbalance Redefines "Good" Accuracy</h4>
              <p className="text-muted-foreground mb-3">
                These examples demonstrate how adding class distribution context to accuracy gauges transforms interpretation. <strong className="text-foreground">What initially appears as good performance with fixed gauges can be revealed as merely baseline chance once class imbalance is factored in.</strong> The gauge segments must shift to show that genuinely good performance requires exceeding what simple strategies (like "always guess the majority class") would achieve.
              </p>
            </div>
            
            <div className="my-8 p-6 rounded-lg bg-card">
              <h4 className="text-lg font-semibold mb-6 text-center">Visualizing Context: Impact of Varying Class Imbalance (65% Accuracy Example)</h4>
              <p className="text-sm text-muted-foreground mb-4 text-center">
                Each scenario below shows a 65% accuracy. The top gauge uses fixed segments, while the bottom gauge adjusts segments based on the specified class imbalance.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Balanced (50/50)</h5>
                  <AccuracyGauge value={65.0} title="Fixed Segments" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="Contextual Segments" segments={imbal_scenario1_segments} />
                </div>
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Imbalanced (75/25)</h5>
                  <AccuracyGauge value={65.0} title="Fixed Segments" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="Contextual Segments" segments={imbal_scenario2_segments} />
                </div>
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">3-Class Imbal. (80/10/10)</h5>
                  <AccuracyGauge value={65.0} title="Fixed Segments" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="Contextual Segments" segments={imbal_scenario4_segments} />
                </div>
                <div className="flex flex-col items-center space-y-3 p-4 bg-background rounded-md">
                  <h5 className="text-md font-medium text-center">Highly Imbal. (95/5)</h5>
                  <AccuracyGauge value={65.0} title="Fixed Segments" segments={fixedAccuracyGaugeSegments} />
                  <AccuracyGauge value={65.0} title="Contextual Segments" segments={imbal_scenario3_segments} />
                </div>
              </div>
            </div>

            <h3 className="text-xl font-medium mt-8 mb-3">Full Context: Combining Number of Classes AND Imbalance</h3>
            <p className="text-muted-foreground mb-4">
              Plexus's Accuracy gauges, when fully contextualized, account for *both* the number of classes and their distribution simultaneously. This provides the most accurate baseline against which to judge the observed accuracy.
            </p>

            <EvaluationCard
              title="Article Topic Labeler - With Full Context (Class Count & Imbalance)"
              subtitle="Our 5-class imbalanced classifier (62% accuracy, 40% News). Right gauge contextualized for its 5-class nature AND its imbalanced distribution (40% News, 15% others)."
              classDistributionData={articleTopicLabelerClassDistribution}
              isBalanced={false}
              accuracy={articleTopicLabelerExampleData.accuracy}
              confusionMatrixData={articleTopicLabelerConfusionMatrix}
              predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
              variant="default" 
              accuracyGaugeSegments={articleTopicLabelerFullContextSegments} 
              notes="The left (fixed) gauge suggests 62% is 'converging'. The right (fully contextualized) gauge shows it as 'good', but not 'great'. The chance level, accounting for a 40% majority class among 5 options, is higher than the simple 20% for a balanced 5-class problem but lower than just guessing majority. This makes 62% good, but less stellar than if classes were balanced or if only class count was naively considered without imbalance."
            />
            
            <div className="mt-4 mb-8 p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500">
                <h4 className="text-lg font-semibold mb-2">Key Insight: Full Context is Nuanced</h4>
                <p className="text-muted-foreground">
                  The fully contextualized accuracy gauge provides the most nuanced picture. For the Article Topic Labeler (62% accuracy, 5 classes, 40% majority class), the performance is good—significantly better than naive strategies (e.g., always guessing 'News' for 40% accuracy, or random 5-class guessing at 20%). However, the bar for 'great' is higher than if the classes were perfectly balanced, reflecting the slight advantage gained from the existing imbalance.
                </p>
            </div>
        </section>

        <section className="mt-8">
          <h2 className="text-2xl font-semibold mb-4">Strategy 2: The Agreement Gauge - Inherently Context-Aware</h2>
          <p className="text-muted-foreground mb-4">
            Rather than adding external context to interpret a raw accuracy gauge, an alternative and complementary approach is to use a metric that inherently incorporates this context. The Agreement gauge in Plexus (using Gwet's AC1 by default) does exactly this.
          </p>

          <h3 className="text-xl font-medium mb-3">Standardized Interpretation Across All Scenarios</h3>
          <p className="text-muted-foreground mb-4">
            Metrics like Gwet's AC1 are designed to factor in both the number of classes and their distribution to calculate a chance-corrected agreement score. This creates a standardized scale:
          </p>
          <ul className="list-disc pl-6 space-y-1 mb-4 text-muted-foreground">
            <li><strong className="text-foreground">0.0:</strong> Performance equivalent to random chance agreement for that specific class distribution.</li>
            <li><strong className="text-foreground">1.0:</strong> Perfect agreement (all predictions correct).</li>
            <li><strong className="text-foreground">-1.0:</strong> Perfect systematic disagreement (e.g., always wrong when it could be right).</li>
          </ul>
          <p className="text-muted-foreground mb-4">
            A score of, for example, 0.6 on the Agreement gauge represents the same level of performance *above chance* regardless of whether it's a binary problem, a 10-class problem, or a highly imbalanced dataset.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 my-6">
            <div className="flex flex-col items-center p-4 bg-card rounded-md">
              <h4 className="text-xl font-semibold mb-2">Opposite</h4>
              <div className="w-full max-w-[150px] mx-auto mb-2">
                <Gauge title="Agreement" value={-1.0} min={-1} max={1} segments={ac1GaugeSegments} showTicks={false} />
              </div>
              <p className="text-sm text-muted-foreground text-center">Perfect systematic disagreement.</p>
            </div>
            <div className="flex flex-col items-center p-4 bg-card rounded-md">
              <h4 className="text-xl font-semibold mb-2">Random</h4>
              <div className="w-full max-w-[150px] mx-auto mb-2">
                <Gauge title="Agreement" value={0.0} min={-1} max={1} segments={ac1GaugeSegments} showTicks={false} />
              </div>
              <p className="text-sm text-muted-foreground text-center">No skill beyond chance.</p>
            </div>
            <div className="flex flex-col items-center p-4 bg-card rounded-md">
              <h4 className="text-xl font-semibold mb-2">Perfect</h4>
              <div className="w-full max-w-[150px] mx-auto mb-2">
                <Gauge title="Agreement" value={1.0} min={-1} max={1} segments={ac1GaugeSegments} showTicks={false} />
              </div>
              <p className="text-sm text-muted-foreground text-center">Perfect agreement.</p>
            </div>
          </div>

          <p className="text-muted-foreground mb-4">
            Let's see how the Agreement gauge and the fully contextualized Accuracy gauge work together for various scenarios.
          </p>

          <EvaluationCard
            title="Random Coin Flip Prediction (50/50)"
            subtitle="Fair coin, random guessing achieved 48% accuracy in this run."
            classDistributionData={fairCoinDistribution}
            isBalanced={true}
            accuracy={fairCoinData.accuracy}
            gwetAC1={fairCoinData.ac1}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={dynamicSegments2Class}
            notes="Both gauges show performance slightly below chance. Agreement (AC1=-0.04) is just under 0. Contextual Accuracy (48%) is just under the 50% chance baseline for a balanced binary problem."
          />

          <EvaluationCard
            title="Random Card Suit Prediction (4 Balanced Classes)"
            subtitle="Four equally likely suits, random guessing achieved 23% accuracy."
            classDistributionData={cardSuitActualDistribution}
            isBalanced={true}
            accuracy={cardSuitData.accuracy}
            gwetAC1={cardSuitData.ac1}
            confusionMatrixData={cardSuitConfusionMatrix}
            predictedClassDistributionData={cardSuitPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={dynamicSegments4Class}
            notes="Both gauges indicate performance slightly below chance. Agreement (AC1=-0.03) is just under 0. Contextual Accuracy (23%) is just below the 25% chance baseline for a balanced 4-class problem."
          />
          
          <div className="p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6 mb-4">
            <h4 className="text-lg font-semibold mb-2">Key Insight: Agreement Gauge Resists Deception from Imbalance</h4>
            <p className="text-muted-foreground mb-3">
              The true power of the Agreement gauge becomes evident in imbalanced scenarios where raw accuracy can be highly misleading. The Agreement gauge automatically adjusts for this, providing a consistent measure of skill beyond chance.
            </p>
            <p className="text-muted-foreground">
               For example, a classifier that always guesses the majority class in an imbalanced dataset will have an Agreement score of 0.0 (or very close to it), clearly indicating no actual predictive ability, even if its raw accuracy is high. This exposes seemingly good performance as having no real skill.
            </p>
          </div>

          <EvaluationCard
            title="Always Predicting Red (75/25 Stacked Deck)"
            subtitle="Deck is 75% Red. Strategy: always guess 'Red'. Achieves 75% accuracy."
            classDistributionData={stackedDeckAlwaysRedClassDistribution}
            isBalanced={false}
            accuracy={stackedDeckAlwaysRedAccuracy}
            gwetAC1={stackedDeckAlwaysRedGwetAC1}
            confusionMatrixData={stackedDeckAlwaysRedConfusionMatrix}
            predictedClassDistributionData={stackedDeckAlwaysRedPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={stackedDeckAlwaysRedAccuracySegments}
            notes="Despite 75% accuracy, Agreement gauge (AC1=0.00) correctly shows no predictive skill beyond chance (which is effectively what always guessing majority is in this context). The contextual Accuracy gauge also correctly shows 75% is the baseline chance level here."
          />
          
          <EvaluationCard
            title="The &quot;Always Safe&quot; Email Filter - Both Gauges Revealing the Truth"
            subtitle="Dataset: 97% 'Safe', 3% 'Prohibited'. Filter always predicts 'Safe', achieving 97% accuracy."
            classDistributionData={alwaysSafeEmailClassDistribution}
            isBalanced={false}
            accuracy={alwaysSafeEmailAccuracy}
            gwetAC1={alwaysSafeEmailGwetAC1}
            confusionMatrixData={alwaysSafeEmailConfusionMatrix}
            predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={alwaysSafeEmailAccuracySegments}
            notes="The extremity of this example is powerful. Despite a 97% accuracy, both gauges reveal the truth: zero predictive skill. Agreement (AC1=0.0) and the contextual Accuracy gauge (showing 97% is the baseline) both expose this filter as useless for catching prohibited content."
          />
          
          <div className="p-5 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mt-6 mb-4">
              <h4 className="text-lg font-semibold mb-2">Benefits of the Agreement Gauge</h4>
              <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                <li><strong className="text-foreground">Simplified Interpretation:</strong> Users don't need to mentally factor in class distribution or number of classes - the gauge does it for them. 0.0 is always chance.</li>
                <li><strong className="text-foreground">Direct Comparability:</strong> Agreement scores can be directly compared across different classifiers and datasets, regardless of their underlying class structures.</li>
                <li><strong className="text-foreground">Immediate Insight:</strong> Instantly reveals whether a classifier has actual predictive power beyond what's expected by chance for that specific problem.</li>
                <li><strong className="text-foreground">Resistance to Deception:</strong> Exposes seemingly high accuracy numbers that actually represent no real predictive skill in imbalanced situations.</li>
              </ul>
          </div>
          
          <EvaluationCard
            title="Article Topic Labeler - The Complete Picture with Both Gauges"
            subtitle="Our 5-class imbalanced classifier (62% accuracy, 40% News). How do both gauges tell the story?"
            classDistributionData={articleTopicLabelerClassDistribution}
            isBalanced={false}
            accuracy={articleTopicLabelerExampleData.accuracy}
            gwetAC1={articleTopicLabelerExampleData.gwetAC1}
            confusionMatrixData={articleTopicLabelerConfusionMatrix}
            predictedClassDistributionData={articleTopicLabelerPredictedDistribution}
            showBothGauges={true}
            variant="default"
            accuracyGaugeSegments={articleTopicLabelerFullContextSegments}
            notes="The Agreement gauge (AC1 = 0.512) shows moderate agreement beyond chance, inherently accounting for the 5-class nature and the 40/15/15/15/15 distribution. This score directly tells us its skill level above baseline. The fully contextualized Accuracy gauge confirms this: 62% is 'good' for this specific setup, but not in the highest tier. Both gauges provide a consistent, nuanced view."
          />
          
          <p className="text-muted-foreground mt-4 mb-4">
            For the Article Topic Labeler, the Agreement score of 0.512 instantly provides a clear assessment: moderate predictive skill. This single, standardized number shows it performs notably better than chance for its specific configuration, but isn't achieving top-tier agreement. It complements the contextualized Accuracy gauge, which visually shows *why* 62% is considered "good" in this particular imbalanced multi-class scenario.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Conclusion: A Multi-Faceted View for True Insight</h2>
          <p className="text-muted-foreground mb-4">
            Plexus utilizes both contextualized Accuracy gauges and inherently context-aware Agreement gauges (like Gwet's AC1). This dual approach provides a comprehensive and reliable understanding of classifier performance:
          </p>
          <ul className="list-disc pl-6 space-y-3 my-6 text-muted-foreground">
            <li>
                <strong className="text-foreground">Contextualized Accuracy Gauge:</strong> Helps interpret the familiar 'percent correct' metric by visually adjusting its scale (colors and thresholds) based on the specific problem's class count and imbalance. It answers: "How good is this raw accuracy *for this particular problem setup*?"
            </li>
            <li>
                <strong className="text-foreground">Agreement Gauge (e.g., Gwet's AC1):</strong> Provides a standardized, chance-corrected score. It inherently accounts for class count and imbalance. It answers: "How much skill does this classifier demonstrate *beyond random chance*, in a way that's comparable across different problems?"
            </li>
          </ul>
          <p className="text-muted-foreground mb-4">
            Together, these gauges offer robust insights, preventing misinterpretation of raw accuracy numbers and clearly highlighting a classifier's true performance relative to baseline expectations and its inherent skill.
          </p>
          <div className="flex flex-wrap gap-4 mt-8">
            <Link href="/documentation/evaluation-metrics">
              <DocButton variant="outline">Back to Evaluation Metrics Overview</DocButton>
            </Link>
            <Link href="/documentation/evaluation-metrics/examples">
              <DocButton>View More Metric Examples</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
} 