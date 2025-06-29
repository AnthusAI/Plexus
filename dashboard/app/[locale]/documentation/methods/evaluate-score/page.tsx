'use client';

import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function EvaluateScorePage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Evaluar una Puntuación</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Aprende cómo ejecutar evaluaciones usando puntuaciones individuales o cuadros de puntuación completos.
        </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Ejecutar una Evaluación</h2>
          <p className="text-muted-foreground mb-4">
            Puedes evaluar contenido usando puntuaciones individuales o cuadros de puntuación completos. El proceso de evaluación
            analiza tu contenido contra los criterios definidos y proporciona resultados detallados.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Usar el Dashboard</h3>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li>Selecciona tu contenido fuente</li>
                <li>Elige un cuadro de puntuación o puntuación individual</li>
                <li>Haz clic en "Ejecutar Evaluación"</li>
                <li>Monitorea el progreso de la evaluación</li>
                <li>Revisa los resultados</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Usar el SDK</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`from plexus import Plexus

plexus = Plexus(api_key="tu-clave-api")

# Evaluar usando una puntuación específica (acepta ID, nombre, clave, o ID externo)
evaluation = plexus.evaluations.create(
    source_id="id-fuente",
    score="Verificación Gramatical"  # Puede usar nombre, clave, ID, o ID externo
)

# O evaluar usando un cuadro de puntuación completo (acepta ID, nombre, clave, o ID externo)
evaluation = plexus.evaluations.create(
    source_id="id-fuente",
    scorecard="Calidad de Contenido"  # Puede usar nombre, clave, ID, o ID externo
)

# Obtener resultados de evaluación
results = evaluation.get_results()

# Imprimir valores de puntuación
for score in results.scores:
    print(f"{score.name}: {score.value}")`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                El SDK soporta el sistema de identificadores flexible, permitiéndote referenciar cuadros de puntuación y puntuaciones usando diferentes tipos de identificadores (nombre, clave, ID, o ID externo).
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Usar la CLI</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Evaluar usando un cuadro de puntuación
plexus evaluate accuracy --scorecard "Calidad de Contenido" --number-of-samples 100

# Listar resultados de evaluación
plexus evaluations list

# Ver resultados detallados para una evaluación específica
plexus evaluations list-results --evaluation id-evaluacion`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                La CLI soporta el sistema de identificadores flexible, permitiéndote referenciar cuadros de puntuación usando diferentes tipos de identificadores (nombre, clave, ID, o ID externo).
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Entender los Resultados</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Valores de Puntuación</h3>
              <p className="text-muted-foreground">
                Resultados numéricos o categóricos para cada criterio evaluado.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Explicaciones</h3>
              <p className="text-muted-foreground">
                Razonamiento detallado detrás del resultado de evaluación de cada puntuación.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Sugerencias</h3>
              <p className="text-muted-foreground">
                Recomendaciones para mejora basadas en los resultados de evaluación.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Evaluaciones por Lotes</h2>
          <p className="text-muted-foreground mb-4">
            Puedes evaluar múltiples fuentes a la vez usando procesamiento por lotes:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Crear una evaluación por lotes
batch = plexus.evaluations.create_batch(
    source_ids=["fuente-1", "fuente-2", "fuente-3"],
    scorecard="Aseguramiento de Calidad"  # Puede usar nombre, clave, ID, o ID externo
)

# Monitorear progreso del lote
status = batch.get_status()

# Obtener resultados cuando esté completo
results = batch.get_results()`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Al igual que las evaluaciones individuales, las evaluaciones por lotes también soportan el sistema de identificadores flexible para cuadros de puntuación y puntuaciones.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Próximamente</h2>
          <p className="text-muted-foreground">
            Se está desarrollando documentación detallada sobre evaluaciones. Regresa pronto para:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Opciones avanzadas de evaluación</li>
            <li>Formato personalizado de resultados</li>
            <li>Optimización de rendimiento de evaluaciones</li>
            <li>Técnicas de análisis de resultados</li>
          </ul>
        </section>
      </div>
    </div>
    );
  }

  // English content (default)
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluate a Score</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to run evaluations using individual scores or complete scorecards.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Running an Evaluation</h2>
          <p className="text-muted-foreground mb-4">
            You can evaluate content using individual scores or entire scorecards. The evaluation
            process analyzes your content against the defined criteria and provides detailed results.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Using the Dashboard</h3>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li>Select your source content</li>
                <li>Choose a scorecard or individual score</li>
                <li>Click "Run Evaluation"</li>
                <li>Monitor the evaluation progress</li>
                <li>Review the results</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the SDK</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Evaluate using a specific score (accepts ID, name, key, or external ID)
evaluation = plexus.evaluations.create(
    source_id="source-id",
    score="Grammar Check"  # Can use name, key, ID, or external ID
)

# Or evaluate using an entire scorecard (accepts ID, name, key, or external ID)
evaluation = plexus.evaluations.create(
    source_id="source-id",
    scorecard="Content Quality"  # Can use name, key, ID, or external ID
)

# Get evaluation results
results = evaluation.get_results()

# Print score values
for score in results.scores:
    print(f"{score.name}: {score.value}")`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                The SDK supports the flexible identifier system, allowing you to reference scorecards and scores using different types of identifiers (name, key, ID, or external ID).
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the CLI</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Evaluate using a scorecard
plexus evaluate accuracy --scorecard "Content Quality" --number-of-samples 100

# List evaluation results
plexus evaluations list

# View detailed results for a specific evaluation
plexus evaluations list-results --evaluation evaluation-id`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                The CLI supports the flexible identifier system, allowing you to reference scorecards using different types of identifiers (name, key, ID, or external ID).
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Results</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Score Values</h3>
              <p className="text-muted-foreground">
                Numerical or categorical results for each evaluated criterion.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Explanations</h3>
              <p className="text-muted-foreground">
                Detailed reasoning behind each score's evaluation result.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Suggestions</h3>
              <p className="text-muted-foreground">
                Recommendations for improvement based on the evaluation results.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Batch Evaluations</h2>
          <p className="text-muted-foreground mb-4">
            You can evaluate multiple sources at once using batch processing:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Create a batch evaluation
batch = plexus.evaluations.create_batch(
    source_ids=["source-1", "source-2", "source-3"],
    scorecard="Quality Assurance"  # Can use name, key, ID, or external ID
)

# Monitor batch progress
status = batch.get_status()

# Get results when complete
results = batch.get_results()`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like individual evaluations, batch evaluations also support the flexible identifier system for scorecards and scores.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about evaluations is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced evaluation options</li>
            <li>Custom result formatting</li>
            <li>Evaluation performance optimization</li>
            <li>Result analysis techniques</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 