'use client';

import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { useTranslationContext } from '@/app/contexts/TranslationContext'

export default function ScoresPage() {
  const { locale } = useTranslationContext();
  
  if (locale === 'es') {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6">
        <h1 className="text-4xl font-bold mb-4">Puntuaciones</h1>
        <p className="text-lg text-muted-foreground mb-8">
          Las puntuaciones son los elementos fundamentales de evaluación en Plexus. Definen qué quieres medir 
          o evaluar sobre tu contenido.
        </p>

        <div className="space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">¿Qué son las Puntuaciones?</h2>
            <p className="text-muted-foreground mb-4">
              Las puntuaciones son criterios de evaluación individuales que definen aspectos específicos que quieres evaluar en tu contenido. 
              Aunque pueden ser preguntas, no se limitan solo a preguntas - pueden ser cualquier tipo de punto de evaluación 
              que ayude a analizar tu contenido.
            </p>

            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-medium mb-2">Tipos de Puntuaciones</h3>
                <p className="text-muted-foreground mb-4">
                  Las puntuaciones pueden tomar muchas formas, incluyendo:
                </p>
                <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                  <li>
                    <strong>Preguntas</strong>: "¿Se presentó el agente declarando el nombre de la empresa?"
                  </li>
                  <li>
                    <strong>Análisis de Sentimiento</strong>: Evaluar si el tono del contenido es positivo, negativo o neutral
                  </li>
                  <li>
                    <strong>Verificaciones de Cumplimiento</strong>: Verificar si elementos requeridos específicos están presentes
                  </li>
                  <li>
                    <strong>Métricas</strong>: Medidas cuantitativas como tiempo de respuesta o conteo de palabras
                  </li>
                </ul>
              </div>

              <div>
                <h3 className="text-xl font-medium mb-2">Cómo Funcionan las Puntuaciones</h3>
                <p className="text-muted-foreground mb-4">
                  Cada puntuación define:
                </p>
                <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                  <li><strong>Qué evaluar</strong>: El criterio específico o aspecto del contenido</li>
                  <li><strong>Cómo evaluar</strong>: El método o algoritmo utilizado para la evaluación</li>
                  <li><strong>Resultado esperado</strong>: El formato de la salida (ej., Sí/No, escala numérica, etiquetas)</li>
                </ul>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Organización de las Puntuaciones</h2>
            <p className="text-muted-foreground mb-4">
              Las puntuaciones se organizan dentro de Cuadros de Puntuación, que agrupan criterios de evaluación relacionados. 
              Esta organización ayuda a mantener tus evaluaciones estructuradas y manejables.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">Próximos Pasos</h2>
            <p className="text-muted-foreground mb-4">
              Para entender mejor cómo usar las puntuaciones en Plexus, explora estos temas relacionados:
            </p>
            <div className="space-y-3">
              <Link href="/es/documentation/concepts/scorecards">
                <DocButton variant="outline" className="w-full justify-start">
                  Cuadros de Puntuación - Organizar tus puntuaciones
                </DocButton>
              </Link>
              <Link href="/es/documentation/concepts/score-results">
                <DocButton variant="outline" className="w-full justify-start">
                  Resultados de Puntuación - Ver los resultados de evaluación
                </DocButton>
              </Link>
              <Link href="/es/documentation/concepts/evaluations">
                <DocButton variant="outline" className="w-full justify-start">
                  Evaluaciones - Ejecutar evaluaciones de rendimiento
                </DocButton>
              </Link>
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Scores</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Scores are the fundamental building blocks of evaluation in Plexus. They define what you want to measure 
        or assess about your content.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Scores?</h2>
          <p className="text-muted-foreground mb-4">
            Scores are individual evaluation criteria that define specific aspects you want to assess in your content. 
            While they can be questions, they're not limited to just questions - they can be any type of evaluation 
            point that helps analyze your content.
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Types of Scores</h3>
              <p className="text-muted-foreground mb-4">
                Scores can take many forms, including:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Questions</strong>: "Did the agent introduce themselves by stating the company name?"
                </li>
                <li>
                  <strong>Sentiment Analysis</strong>: Evaluating if the content's tone is positive, negative, or neutral
                </li>
                <li>
                  <strong>Compliance Checks</strong>: Verifying if specific required elements are present
                </li>
                <li>
                  <strong>Metrics</strong>: Quantitative measurements like response time or word count
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Score Components</h3>
              <p className="text-muted-foreground mb-4">
                Each score consists of:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Criteria</strong>: What exactly is being evaluated
                </li>
                <li>
                  <strong>Evaluation Method</strong>: How the score should be determined
                </li>
                <li>
                  <strong>Response Format</strong>: The type of result (yes/no, numeric, categorical, etc.)
                </li>
                <li>
                  <strong>Instructions</strong>: Guidelines for consistent evaluation
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Score Results</h2>
          <p className="text-muted-foreground mb-4">
            Plexus standardizes all score results around a common structure, ensuring consistency and enabling 
            powerful analysis capabilities across different types of evaluations.
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Result Structure</h3>
              <p className="text-muted-foreground mb-4">
                Every score result in Plexus contains these core components:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Result Value</strong>: The actual outcome of the evaluation (e.g., "yes"/"no", a numeric score, 
                  or a category)
                </li>
                <li>
                  <strong>Explanation</strong>: A detailed description of why this result was chosen, providing 
                  transparency into the decision-making process. For LLM-based scores, this often includes chain-of-thought 
                  reasoning similar to what you might see from models like OpenAI's GPT-4 o1/o3, Google's "thinking" models, or Deepseek R1.
                </li>
                <li>
                  <strong>Confidence Level</strong>: For applicable scores (like machine learning classifiers or LLM-based 
                  evaluations), this indicates how certain the system is about the result. This can be used for filtering, 
                  quality control, or triggering human review when needed.
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using Result Components</h3>
              <p className="text-muted-foreground mb-4">
                The standardized result structure enables powerful workflows:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  Use confidence levels to filter results or trigger additional review for low-confidence evaluations
                </li>
                <li>
                  Leverage explanations for quality assurance, training, and understanding model decision-making
                </li>
                <li>
                  Build consistent interfaces and analysis tools that work across all score types
                </li>
                <li>
                  Create automated workflows based on result values while maintaining full explainability
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using Scores</h2>
          <p className="text-muted-foreground mb-4">
            Scores are organized into scorecards, which group related evaluation criteria together. When you run an 
            evaluation, each score in the scorecard is applied to your content, building a comprehensive assessment.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Score Versions</h3>
              <p className="text-muted-foreground mb-4">
                Scores in Plexus support versioning, allowing you to track changes to score configurations over time.
                Each version represents a different configuration of the score, with one version designated as the
                "champion" (active) version that's used for evaluations.
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Champion Version</strong>: The currently active version used for evaluations
                </li>
                <li>
                  <strong>Featured Versions</strong>: Versions that are highlighted for importance or reference
                </li>
                <li>
                  <strong>Configuration</strong>: Each version contains its own configuration, including prompts, 
                  parameters, and other settings
                </li>
              </ul>
              <p className="text-muted-foreground mt-4">
                You can view score versions using the CLI command:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`plexus scores info --scorecard "Example Scorecard" --score "Example Score"`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground">
                This command displays up to 10 versions in reverse chronological order (newest first), showing which 
                version is the champion and which versions are featured.
              </p>
            </div>
          </div>
          
          <div className="flex gap-4 mt-6">
            <Link href="/documentation/concepts/scorecards">
              <DocButton>Learn about Scorecards</DocButton>
            </Link>
            <Link href="/documentation/advanced/sdk">
              <DocButton variant="outline">Python SDK Reference</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 