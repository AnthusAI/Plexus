'use client';

import Link from "next/link"
import { Button as DocButton } from "@/components/ui/button"
import { Gauge, Segment } from "@/components/gauge"
import EvaluationCard from '@/components/EvaluationCard'
import { ac1GaugeSegments } from "@/components/ui/scorecard-evaluation" // Standard segments for AC1
import {
  alwaysSafeEmailAccuracy,
  alwaysSafeEmailGwetAC1,
  alwaysSafeEmailClassDistribution,
  alwaysSafeEmailConfusionMatrix,
  alwaysSafeEmailPredictedDistribution,
  // We'll use the data for the 'Always Safe' example to show AC1 in action
  // We don't need the accuracy-specific segments here, as ac1GaugeSegments are standard.
} from "@/app/[locale]/documentation/evaluation-metrics/examples-data"
import { useTranslationContext } from '@/app/contexts/TranslationContext'

// Component to display a standalone Agreement Gauge for illustration
const AgreementGaugeDisplay = ({ value, title }: {
  value: number,
  title: string,
}) => (
  <div className="w-full max-w-[200px] mx-auto"> {/* Adjusted size for potentially more detailed segments */}
    <Gauge
      title={title}
      value={value}
      min={-1} // Gwet's AC1 can range from -1 to 1
      max={1}
      showTicks={true}
      segments={ac1GaugeSegments} // Using standard AC1 segments
    />
  </div>
);

export default function AgreementGaugePage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">El Indicador de Acuerdo de Plexus</h1>
        <p className="text-lg text-muted-foreground mb-8">
          El Indicador de Acuerdo en Plexus típicamente muestra un coeficiente de acuerdo corregido por casualidad, como el <strong>AC1 de Gwet</strong>. A diferencia de la precisión cruda, que puede ser engañosa, estas métricas están diseñadas para medir la concordancia (o rendimiento del modelo) mientras contabilizan el acuerdo que podría ocurrir puramente por casualidad. Esto proporciona una evaluación más confiable de la verdadera habilidad de un clasificador.
        </p>

        <div className="space-y-10">
          <section>
            <h2 className="text-2xl font-semibold mb-4">¿Por Qué Usar una Métrica Corregida por Casualidad?</h2>
            <p className="text-muted-foreground mb-4">
              Como se discutió en nuestra <Link href="/es/documentation/evaluation-metrics/gauges/accuracy" className="text-primary hover:underline">página del Indicador de Precisión</Link>, las cifras de precisión cruda pueden ser fácilmente malinterpretadas debido a factores como el número de clases y el desbalance de clases. Un puntaje de precisión alto podría no siempre indicar buen rendimiento si el acuerdo por casualidad también es alto.
            </p>
            <p className="text-muted-foreground mb-4">
              Los coeficientes de acuerdo, como el AC1 de Gwet, abordan esto factorizando el acuerdo por casualidad esperado. El puntaje resultante refleja la medida en que el acuerdo observado (o precisión del modelo) excede lo que se esperaría por casualidad, dadas las características específicas de los datos (incluyendo distribuciones de clases y número de clases).
            </p>
            <div className="p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
              <h3 className="text-lg font-semibold mb-2">Aprende Más Sobre Desafíos Contextuales</h3>
              <p className="text-muted-foreground mb-3">
                Para una discusión integral sobre cómo Plexus aborda varios factores contextuales en la evaluación, consulta:
              </p>
              <Link href="/es/documentation/evaluation-metrics/gauges-with-context">
                <DocButton>Entendiendo Indicadores con Contexto</DocButton>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Cómo Funciona el Indicador de Acuerdo de Plexus</h2>
            <p className="text-muted-foreground mb-4">
              El Indicador de Acuerdo muestra el coeficiente de acuerdo calculado, típicamente el AC1 de Gwet. Este puntaje usualmente va de -1 a +1:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
              <li><strong className="text-foreground">+1.0:</strong> Acuerdo perfecto.</li>
              <li><strong className="text-foreground">0.0:</strong> El acuerdo es exactamente lo que se esperaría por casualidad. El modelo no muestra habilidad más allá de adivinación aleatoria relativa a la distribución de clases.</li>
              <li><strong className="text-foreground">-1.0:</strong> Desacuerdo sistemático perfecto (significa que el modelo es consistentemente incorrecto de manera estructurada).</li>
              <li>Valores entre 0 y 1 indican grados variables de acuerdo mejor que la casualidad.</li>
            </ul>
            <p className="text-muted-foreground mb-6">
              Los segmentos visuales en el Indicador de Acuerdo (colores como rojo, amarillo, verde) se basan generalmente en puntos de referencia establecidos para interpretar la fuerza de los coeficientes de acuerdo (como los propuestos por Landis & Koch para Kappa, que a menudo se adaptan para AC1). Debido a que el puntaje AC1 <strong className="text-foreground">ya tiene el contexto de distribución de clases y acuerdo por casualidad incorporado en su cálculo</strong>, estos segmentos visuales tienden a ser fijos. La interpretación de un puntaje AC1 de, digamos, 0.7 (acuerdo sustancial) es consistente sin importar si es un problema de 2 clases o 10 clases, o si los datos están balanceados o desbalanceados.
            </p>
            <div className="my-6 p-6 rounded-lg bg-card border flex flex-col items-center">
              <h4 className="text-lg font-semibold mb-4 text-center">Ejemplo: Indicador AC1 de Gwet</h4>
              <AgreementGaugeDisplay value={0.65} title="AC1 de Gwet" />
              <p className="text-sm text-muted-foreground mt-3 text-center">
                Un puntaje AC1 de 0.65 indica acuerdo 'Sustancial', según puntos de referencia comunes. Esta interpretación es generalmente estable a través de diferentes contextos de problemas porque la métrica en sí misma está ajustada por contexto.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Indicador de Acuerdo en Acción: Exponiendo Precisión Engañosa</h2>
            <p className="text-muted-foreground mb-4">
              Uno de los usos más poderosos del Indicador de Acuerdo es su capacidad para revelar situaciones donde la precisión cruda alta es engañosa. Considera el ejemplo del Filtro de Email "Siempre Seguro":
            </p>
            <div className="my-6">
              <EvaluationCard
                title="El Filtro de Email 'Siempre Seguro' - Vista de Acuerdo"
                subtitle="Estrategia: Etiquetar TODOS los emails como 'Seguros'. Precisión Cruda: 97%. AC1 de Gwet: 0.0."
                classDistributionData={alwaysSafeEmailClassDistribution}
                isBalanced={false}
                accuracy={alwaysSafeEmailAccuracy}
                gwetAC1={alwaysSafeEmailGwetAC1}
                confusionMatrixData={alwaysSafeEmailConfusionMatrix}
                predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
                showBothGauges={true}
                variant="default"
                notes="A pesar de una precisión cruda del 97% (que se ve genial en una escala fija), el puntaje AC1 de Gwet de 0.0 inmediatamente señala que el filtro tiene CERO habilidad predictiva más allá de lo que se espera por casualidad para este conjunto de datos altamente desbalanceado. No es mejor que un proceso aleatorio que respeta las tasas base de 97/3."
              />
            </div>
            <p className="text-muted-foreground mb-4">
              En este escenario, el Indicador de Acuerdo corta a través de la ilusión. Mientras que la precisión (no contextualizada) podría sugerir alto rendimiento, el puntaje AC1 de 0.0 cuenta la historia verdadera: el modelo no ha aprendido nada útil para distinguir contenido prohibido.
            </p>
          </section>
          
          <section>
            <h2 className="text-2xl font-semibold mb-4">Interpretando Rangos de Puntaje de Acuerdo</h2>
            <p className="text-muted-foreground mb-4">
              Mientras que el contexto está incrustado en el puntaje, es útil tener puntos de referencia generales para interpretar la fuerza del acuerdo indicado por el AC1 de Gwet (similar al Kappa de Fleiss). Los siguientes rangos son ampliamente utilizados (adaptados de Landis & Koch, 1977, para Kappa):
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border bg-card">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Valor AC1</th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Fuerza del Acuerdo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  <tr><td className="px-6 py-4 whitespace-nowrap text-sm">&lt; 0.00</td><td className="px-6 py-4 whitespace-nowrap text-sm">Pobre (Peor que casualidad)</td></tr>
                  <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.00 – 0.20</td><td className="px-6 py-4 whitespace-nowrap text-sm">Ligero</td></tr>
                  <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.21 – 0.40</td><td className="px-6 py-4 whitespace-nowrap text-sm">Regular</td></tr>
                  <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.41 – 0.60</td><td className="px-6 py-4 whitespace-nowrap text-sm">Moderado</td></tr>
                  <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.61 – 0.80</td><td className="px-6 py-4 whitespace-nowrap text-sm">Sustancial</td></tr>
                  <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.81 – 1.00</td><td className="px-6 py-4 whitespace-nowrap text-sm">Casi Perfecto</td></tr>
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Nota: Estas son pautas generales. La significancia práctica de un puntaje de acuerdo también depende de la aplicación específica y las consecuencias de clasificación errónea.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Una Perspectiva Complementaria</h2>
            <p className="text-muted-foreground mb-4">
              El Indicador de Acuerdo ofrece una forma poderosa y estandarizada de evaluar el rendimiento corregido por casualidad. Se usa mejor junto con el <Link href="/es/documentation/evaluation-metrics/gauges/accuracy" className="text-primary hover:underline">Indicador de Precisión contextualizado</Link>.
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>El <strong>Indicador de Precisión</strong> (con sus segmentos dinámicos) te ayuda a entender qué significa un porcentaje crudo *para la estructura de clases específica de tu problema y desbalance*.</li>
              <li>El <strong>Indicador de Acuerdo</strong> te dice qué tan mejor que la casualidad está funcionando tu modelo, de una manera que es *comparable a través de diferentes problemas y conjuntos de datos*.</li>
            </ul>
            <p className="text-muted-foreground mt-2">
              Juntos, proporcionan una vista integral, ayudándote a evitar malinterpretaciones y obtener verdadera comprensión del rendimiento de tu clasificador.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Puntos Clave</h2>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>El Indicador de Acuerdo de Plexus típicamente muestra una métrica corregida por casualidad como el AC1 de Gwet.</li>
              <li>Esta métrica inherentemente contabiliza el número de clases y desbalance de clases, proporcionando un puntaje de "habilidad más allá de la casualidad".</li>
              <li>Un puntaje de 0.0 significa que el rendimiento no es mejor que la casualidad aleatoria para ese contexto; +1.0 es acuerdo perfecto.</li>
              <li>Los segmentos visuales en el Indicador de Acuerdo son generalmente fijos, ya que el valor de la métrica en sí mismo ya está normalizado por contexto.</li>
              <li>Es una herramienta poderosa para desenmascarar puntajes de precisión cruda engañosamente altos, especialmente en conjuntos de datos desbalanceados.</li>
              <li>Úsalo junto con el Indicador de Precisión contextualizado para una comprensión completa.</li>
            </ul>
          </section>

          <div className="flex flex-wrap gap-4 mt-12">
            <Link href="/es/documentation/evaluation-metrics">
              <DocButton variant="outline">Volver a la Vista General de Métricas de Evaluación</DocButton>
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
      <h1 className="text-4xl font-bold mb-4">The Plexus Agreement Gauge</h1>
      <p className="text-lg text-muted-foreground mb-8">
        The Agreement Gauge in Plexus typically displays a chance-corrected agreement coefficient, such as <strong>Gwet's AC1</strong>. Unlike raw accuracy, which can be misleading, these metrics are designed to measure concordance (or model performance) while accounting for agreement that could occur purely by chance. This provides a more reliable assessment of a classifier's true skill.
      </p>

      <div className="space-y-10">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Why Use a Chance-Corrected Metric?</h2>
          <p className="text-muted-foreground mb-4">
            As discussed on our <Link href="/documentation/evaluation-metrics/gauges/accuracy" className="text-primary hover:underline">Accuracy Gauge page</Link>, raw accuracy figures can be easily misinterpreted due to factors like the number of classes and class imbalance. A high accuracy score might not always indicate good performance if chance agreement is also high.
          </p>
          <p className="text-muted-foreground mb-4">
            Agreement coefficients, like Gwet's AC1, address this by factoring out the expected chance agreement. The resulting score reflects the extent to which the observed agreement (or model accuracy) exceeds what would be expected by chance, given the specific characteristics of the data (including class distributions and number of classes).
          </p>
           <div className="p-4 bg-primary/10 dark:bg-primary/20 rounded-lg border-l-4 border-primary">
            <h3 className="text-lg font-semibold mb-2">Learn More About Contextual Challenges</h3>
            <p className="text-muted-foreground mb-3">
              For a comprehensive discussion on how Plexus addresses various contextual factors in evaluation, see:
            </p>
            <Link href="/documentation/evaluation-metrics/gauges-with-context">
              <DocButton>Understanding Gauges with Context</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How the Plexus Agreement Gauge Works</h2>
          <p className="text-muted-foreground mb-4">
            The Agreement Gauge displays the calculated agreement coefficient, typically Gwet's AC1. This score usually ranges from -1 to +1:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong className="text-foreground">+1.0:</strong> Perfect agreement.</li>
            <li><strong className="text-foreground">0.0:</strong> Agreement is exactly what would be expected by chance. The model shows no skill beyond random guessing relative to the class distribution.</li>
            <li><strong className="text-foreground">-1.0:</strong> Perfect systematic disagreement (meaning the model is consistently wrong in a patterned way).</li>
            <li>Values between 0 and 1 indicate varying degrees of agreement better than chance.</li>
          </ul>
          <p className="text-muted-foreground mb-6">
            The visual segments on the Agreement Gauge (colors like red, yellow, green) are generally based on established benchmarks for interpreting the strength of agreement coefficients (like those proposed by Landis & Koch for Kappa, which are often adapted for AC1). Because the AC1 score <strong className="text-foreground">already has the context of class distribution and chance agreement baked into its calculation</strong>, these visual segments tend to be fixed. The interpretation of an AC1 score of, say, 0.7 (substantial agreement) is consistent regardless of whether it's a 2-class or 10-class problem, or whether the data is balanced or imbalanced.
          </p>
          <div className="my-6 p-6 rounded-lg bg-card border flex flex-col items-center">
            <h4 className="text-lg font-semibold mb-4 text-center">Example: Gwet's AC1 Gauge</h4>
            <AgreementGaugeDisplay value={0.65} title="Gwet's AC1" />
            <p className="text-sm text-muted-foreground mt-3 text-center">
              An AC1 score of 0.65 indicates 'Substantial' agreement, according to common benchmarks. This interpretation is generally stable across different problem contexts because the metric itself is context-adjusted.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Agreement Gauge in Action: Exposing Misleading Accuracy</h2>
          <p className="text-muted-foreground mb-4">
            One of the most powerful uses of the Agreement Gauge is its ability to reveal situations where high raw accuracy is deceptive. Consider the "Always Safe" Email Filter example:
          </p>
          <div className="my-6">
            <EvaluationCard
              title="The 'Always Safe' Email Filter - Agreement View"
              subtitle="Strategy: Label ALL emails as 'Safe'. Raw Accuracy: 97%. Gwet's AC1: 0.0."
              classDistributionData={alwaysSafeEmailClassDistribution}
              isBalanced={false}
              accuracy={alwaysSafeEmailAccuracy}
              gwetAC1={alwaysSafeEmailGwetAC1} // This will be 0.0
              confusionMatrixData={alwaysSafeEmailConfusionMatrix}
              predictedClassDistributionData={alwaysSafeEmailPredictedDistribution}
              showBothGauges={true} // Show both to highlight the contrast
              variant="default"
              // Accuracy segments can be dynamic here if shown, but focus is on AC1
              // accuracyGaugeSegments={... some appropriate segments for 97/3 split ...} 
              notes="Despite a 97% raw accuracy (which looks great on a fixed scale), the Gwet's AC1 score of 0.0 immediately signals that the filter has ZERO predictive skill beyond what's expected by chance for this highly imbalanced dataset. It's no better than a random process that respects the 97/3 base rates."
            />
          </div>
          <p className="text-muted-foreground mb-4">
            In this scenario, the Agreement Gauge cuts through the illusion. While the (uncontextualized) accuracy might suggest high performance, the AC1 score of 0.0 tells the true story: the model has learned nothing useful for distinguishing prohibited content.
          </p>
        </section>
        
        <section>
          <h2 className="text-2xl font-semibold mb-4">Interpreting Agreement Score Ranges</h2>
          <p className="text-muted-foreground mb-4">
            While context is embedded in the score, it's helpful to have general benchmarks for interpreting the strength of agreement indicated by Gwet's AC1 (similar to Fleiss' Kappa). The following ranges are widely used (adapted from Landis & Koch, 1977, for Kappa):
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border bg-card">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">AC1 Value</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider">Strength of Agreement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr><td className="px-6 py-4 whitespace-nowrap text-sm">&lt; 0.00</td><td className="px-6 py-4 whitespace-nowrap text-sm">Poor (Worse than chance)</td></tr>
                <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.00 – 0.20</td><td className="px-6 py-4 whitespace-nowrap text-sm">Slight</td></tr>
                <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.21 – 0.40</td><td className="px-6 py-4 whitespace-nowrap text-sm">Fair</td></tr>
                <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.41 – 0.60</td><td className="px-6 py-4 whitespace-nowrap text-sm">Moderate</td></tr>
                <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.61 – 0.80</td><td className="px-6 py-4 whitespace-nowrap text-sm">Substantial</td></tr>
                <tr><td className="px-6 py-4 whitespace-nowrap text-sm">0.81 – 1.00</td><td className="px-6 py-4 whitespace-nowrap text-sm">Almost Perfect</td></tr>
              </tbody>
            </table>
          </div>
           <p className="text-xs text-muted-foreground mt-2">
            Note: These are general guidelines. The practical significance of an agreement score also depends on the specific application and consequences of misclassification.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">A Complementary Perspective</h2>
          <p className="text-muted-foreground mb-4">
            The Agreement Gauge offers a powerful, standardized way to assess performance corrected for chance. It's best used alongside the <Link href="/documentation/evaluation-metrics/gauges/accuracy" className="text-primary hover:underline">contextualized Accuracy Gauge</Link>.
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>The <strong>Accuracy Gauge</strong> (with its dynamic segments) helps you understand what a raw percentage means *for your specific problem's class structure and imbalance*.</li>
            <li>The <strong>Agreement Gauge</strong> tells you how much better than chance your model is performing, in a way that's *comparable across different problems and datasets*.</li>
          </ul>
          <p className="text-muted-foreground mt-2">
            Together, they provide a comprehensive view, helping you avoid misinterpretations and gain true insight into your classifier's performance.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Takeaways</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>The Plexus Agreement Gauge typically displays a chance-corrected metric like Gwet's AC1.</li>
            <li>This metric inherently accounts for the number of classes and class imbalance, providing a score of "skill beyond chance."</li>
            <li>A score of 0.0 means performance is no better than random chance for that context; +1.0 is perfect agreement.</li>
            <li>The visual segments on the Agreement Gauge are generally fixed, as the metric value itself is already context-normalized.</li>
            <li>It's a powerful tool for unmasking misleadingly high raw accuracy scores, especially in imbalanced datasets.</li>
            <li>Use it alongside the contextualized Accuracy Gauge for a complete understanding.</li>
          </ul>
        </section>

        <div className="flex flex-wrap gap-4 mt-12">
          <Link href="/documentation/evaluation-metrics">
            <DocButton variant="outline">Back to Evaluation Metrics Overview</DocButton>
          </Link>
           <Link href="/documentation/evaluation-metrics/gauges-with-context">
            <DocButton variant="outline">More on Gauges with Context</DocButton>
          </Link>
        </div>
      </div>
    </div>
  );
} 